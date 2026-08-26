"""Interactive TUI for `snoop` — walk Drive folders, preview and act on files.

One screen: a folder listing with a live preview pane, styled like the
app's other Textual TUIs (`holla_tui.py`). Selecting a file opens an action
menu (view/open/print/move/delete); folders drill down in place.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from gfunk.browser import open_in_browser
from gfunk.cli import _snoop_actions, snoop_entries, snoop_preview_text
from gfunk.workspace import DOC_MIME, FOLDER_MIME, SCRIPT_MIME, SHEET_MIME

SLIDES_MIME = "application/vnd.google-apps.presentation"
FORM_MIME = "application/vnd.google-apps.form"

PDF_MIME = "application/pdf"

MIME_CSS_CLASSES: dict[str, str] = {
    FOLDER_MIME: "mime-folder",
    DOC_MIME: "mime-doc",
    SHEET_MIME: "mime-sheet",
    SLIDES_MIME: "mime-slides",
    FORM_MIME: "mime-form",
    SCRIPT_MIME: "mime-script",
    PDF_MIME: "mime-pdf",
}

PREFIX_CSS_CLASSES: list[tuple[str, str]] = [
    ("image/", "mime-image"),
    ("video/", "mime-video"),
    ("audio/", "mime-audio"),
]

LEGEND_ITEMS: list[tuple[str, str]] = [
    ("folder", "bright_blue"),
    ("doc", "medium_purple"),
    ("sheet", "green"),
    ("slides", "yellow"),
    ("form", "magenta"),
    ("script", "bright_cyan"),
    ("image", "dark_orange"),
    ("video", "red"),
    ("pdf", "indian_red"),
]

MIME_CSS = """
    .mime-folder { color: dodgerblue; }
    .mime-doc { color: mediumpurple; }
    .mime-sheet { color: green; }
    .mime-slides { color: gold; }
    .mime-form { color: magenta; }
    .mime-script { color: darkcyan; }
    .mime-image { color: darkorange; }
    .mime-video { color: red; }
    .mime-audio { color: orchid; }
    .mime-pdf { color: indianred; }
"""


def _css_class_for_mime(mime: str) -> str | None:
    cls = MIME_CSS_CLASSES.get(mime)
    if cls:
        return cls
    for prefix, css_cls in PREFIX_CSS_CLASSES:
        if mime.startswith(prefix):
            return css_cls
    return None


def _build_legend() -> str:
    parts = [f"[{color}]●[/{color}] {name}" for name, color in LEGEND_ITEMS]
    return "  ".join(parts)


if TYPE_CHECKING:
    from textual.timer import Timer

    from gfunk.workspace import Workspace


PREVIEW_DEBOUNCE_SECONDS = 0.3

SELECT_HERE_ID = "__select__"
UP_ID = "__up__"
SELECT_HERE = {"id": SELECT_HERE_ID, "name": "· move here ·"}
FOLDER_UP = {"id": UP_ID, "name": ".. (up)"}


def _natural_sort_key(name: str) -> tuple[int, int | str]:
    import re

    match = re.match(r"^(\d+)", name)
    return (0, int(match.group(1))) if match else (1, name.lower())


class FileRowItem(ListItem):
    def __init__(self, label: str, item: dict[str, Any] | None) -> None:
        super().__init__(Static(label))
        self.item = item
        if item is not None:
            css_cls = _css_class_for_mime(item.get("mimeType", ""))
            if css_cls:
                self.add_class(css_cls)


class FolderItem(ListItem):
    def __init__(self, folder: dict[str, Any]) -> None:
        super().__init__(Static(folder["name"]))
        self.folder = folder


class FolderPickScreen(ModalScreen[str | None]):
    """Drive folder picker for Move — drill into folders, pick one."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "↓"),
        Binding("k", "cursor_up", "↑"),
        Binding("escape", "cancel", "cancel"),
    ]

    def __init__(self, workspace: Workspace, start: str = "root") -> None:
        super().__init__()
        self._workspace = workspace
        self._folder_id = start
        self._stack: list[str] = []

    def compose(self) -> ComposeResult:
        yield ListView()

    def on_mount(self) -> None:
        self._load()
        self.query_one(ListView).focus()

    def _load(self) -> None:
        children = self._workspace.children(self._folder_id)
        folders = sorted(
            (c for c in children if c.get("mimeType") == FOLDER_MIME),
            key=lambda c: _natural_sort_key(str(c["name"])),
        )
        list_view = self.query_one(ListView)
        list_view.clear()
        list_view.append(FolderItem(SELECT_HERE))
        if self._stack:
            list_view.append(FolderItem(FOLDER_UP))
        for folder in folders:
            list_view.append(FolderItem(folder))
        list_view.index = 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, FolderItem):
            return
        folder = item.folder
        if folder["id"] == SELECT_HERE_ID:
            self.dismiss(self._folder_id)
        elif folder["id"] == UP_ID:
            self._folder_id = self._stack.pop()
            self._load()
        else:
            self._stack.append(self._folder_id)
            self._folder_id = str(folder["id"])
            self._load()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()


class ConfirmTrashScreen(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "dismiss_true", "y confirm", show=False),
        Binding("n", "dismiss_false", "n cancel", show=False),
        Binding("escape", "dismiss_false", "esc cancel", show=False),
    ]

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def compose(self) -> ComposeResult:
        yield Static(f"Trash '{self._name}'? Recoverable for 30 days. [y/n]")
        yield Footer()

    def action_dismiss_true(self) -> None:
        self.dismiss(result=True)

    def action_dismiss_false(self) -> None:
        self.dismiss(result=False)


class ActionMenuScreen(ModalScreen[str | None]):
    """Pick an action for the highlighted file."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "↓"),
        Binding("k", "cursor_up", "↑"),
        Binding("escape", "cancel", "cancel"),
    ]

    def __init__(self, name: str, actions: list[str]) -> None:
        super().__init__()
        self._name = name
        self._actions = actions

    def compose(self) -> ComposeResult:
        yield ListView(*[FileRowItem(action, None) for action in self._actions])
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, FileRowItem):
            self.dismiss(str(item.query_one(Static).content))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()


class SnoopApp(App[None]):
    """Walk folders, read files, view sheets — your Drive window."""

    ENABLE_COMMAND_PALETTE = False
    TITLE = "gfunk snoop"
    CSS = (
        """
    #body {
        height: 1fr;
    }
    ListView {
        width: 1fr;
    }
    ListItem {
        padding: 0 1;
    }
    #preview {
        width: 1fr;
        border-left: solid $accent;
        padding: 0 1;
        overflow-y: auto;
    }
    #preview:focus {
        border-left: solid $success;
    }
    #legend {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    """
        + MIME_CSS
    )
    VIEW_MODES: ClassVar[list[tuple[str, str]]] = [
        ("home", "Home"),
        ("recent", "Recent"),
        ("largest", "Largest"),
    ]
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "↓"),
        Binding("k", "cursor_up", "↑"),
        Binding("enter", "open_row", "open", show=False),
        Binding("tab", "toggle_preview_focus", "preview"),
        Binding("escape", "escape", "up/quit", show=False),
        Binding("1", "view_home", "home"),
        Binding("2", "view_recent", "recent"),
        Binding("3", "view_largest", "largest"),
        Binding("q", "quit", "quit"),
    ]

    def __init__(
        self,
        workspace: Workspace,
        *,
        start_id: str = "root",
        start_name: str | None = None,
        limit: int = 200,
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._limit = limit
        name = start_name or ("My Drive" if start_id == "root" else start_id)
        self._stack: list[tuple[str, str]] = [(start_id, name)]
        self._entries: dict[str, dict[str, Any] | None] = {}
        self._preview_timer: Timer | None = None
        self._preview_cache: dict[str, str] = {}
        self._view_mode: str = "home"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield ListView()
            with VerticalScroll(id="preview", can_focus=True):
                yield Static(id="preview-text", markup=False)
        yield Static(_build_legend(), id="legend", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = self.TITLE
        self._load()
        self.query_one(ListView).focus()

    def _path(self) -> str:
        return "/".join(name for _, name in self._stack)

    def _mode_label(self) -> str:
        return dict(self.VIEW_MODES).get(self._view_mode, "Home")

    def _load(self) -> None:
        folder_id, _ = self._stack[-1]
        if self._view_mode == "recent":
            items = self._workspace.recent(limit=self._limit)
            self.sub_title = "Recent files"
        elif self._view_mode == "largest":
            items = self._workspace.largest(limit=self._limit)
            self.sub_title = "Largest files"
        else:
            items = self._workspace.children(folder_id, limit=self._limit)
            self.sub_title = self._path()
        up = self._view_mode == "home" and len(self._stack) > 1
        self._entries = snoop_entries(
            items,
            up=up,
            mode=self._view_mode,
        )

        list_view = self.query_one(ListView)
        list_view.clear()
        for label, item in self._entries.items():
            list_view.append(FileRowItem(label, item))
        if self._entries:
            self.call_after_refresh(lambda: setattr(list_view, "index", 0))
        self._clear_preview()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, FileRowItem):
            return
        self._open_row(item)

    def action_open_row(self) -> None:
        item = self.query_one(ListView).highlighted_child
        if isinstance(item, FileRowItem):
            self._open_row(item)

    def _open_row(self, row: FileRowItem) -> None:
        if row.item is None:
            self._go_up()
            return
        if row.item.get("mimeType") == FOLDER_MIME:
            self._stack.append((row.item["id"], row.item["name"]))
            self._load()
            return
        self._show_action_menu(row.item)

    def _go_up(self) -> None:
        if len(self._stack) > 1:
            self._stack.pop()
            self._load()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, FileRowItem) and item.item is not None:
            self._schedule_preview(item.item)
        else:
            self._clear_preview()

    def _schedule_preview(self, item: dict[str, Any]) -> None:
        if self._preview_timer is not None:
            self._preview_timer.stop()
            self._preview_timer = None
        preview_text = self.query_one("#preview-text", Static)
        file_id = str(item["id"])
        cached = self._preview_cache.get(file_id)
        if cached is not None:
            preview_text.update(cached)
            return
        preview_text.update("")
        self._preview_timer = self.set_timer(
            PREVIEW_DEBOUNCE_SECONDS, lambda: self._load_preview(item)
        )

    def _load_preview(self, item: dict[str, Any]) -> None:
        file_id = str(item["id"])
        text = snoop_preview_text(self._workspace, item)
        self._preview_cache[file_id] = text
        self.query_one("#preview-text", Static).update(text)

    def _clear_preview(self) -> None:
        if self._preview_timer is not None:
            self._preview_timer.stop()
            self._preview_timer = None
        self.query_one("#preview-text", Static).update("")

    def _preview_focused(self) -> bool:
        return self.query_one("#preview", VerticalScroll).has_focus

    def action_cursor_down(self) -> None:
        if self._preview_focused():
            self.query_one("#preview", VerticalScroll).scroll_down()
        else:
            self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        if self._preview_focused():
            self.query_one("#preview", VerticalScroll).scroll_up()
        else:
            self.query_one(ListView).action_cursor_up()

    def action_toggle_preview_focus(self) -> None:
        preview = self.query_one("#preview", VerticalScroll)
        if self._preview_focused():
            self.query_one(ListView).focus()
        else:
            preview.focus()

    def _switch_view(self, mode: str) -> None:
        self._view_mode = mode
        self._preview_cache.clear()
        self._load()

    def action_view_home(self) -> None:
        self._switch_view("home")

    def action_view_recent(self) -> None:
        self._switch_view("recent")

    def action_view_largest(self) -> None:
        self._switch_view("largest")

    def action_escape(self) -> None:
        if len(self._stack) > 1:
            self._go_up()
        else:
            self.exit()

    def _show_action_menu(self, item: dict[str, Any]) -> None:
        actions = _snoop_actions(item)
        name = item.get("name", item["id"])

        def handle_action(action: str | None) -> None:
            if action is None:
                return
            self._run_action(item, action)

        self.push_screen(ActionMenuScreen(name, actions), handle_action)

    def _run_action(self, item: dict[str, Any], action: str) -> None:
        if action in ("View", "View (Vibe TUI)"):
            self._view(item)
        elif action == "Open in browser":
            open_in_browser(item)
            self.notify(f"Opened {item.get('name', item['id'])} in your browser.")
        elif action == "Print":
            self._print_file(item)
        elif action == "Move":
            self._move(item)
        elif action == "Delete":
            self._delete(item)

    def _view(self, item: dict[str, Any]) -> None:
        mime = item.get("mimeType", "")
        if mime == SHEET_MIME:
            self.run_worker(self._view_sheet(item))
            return
        if mime == DOC_MIME:
            data = self._workspace.export(item["id"], "text/plain")
            self.notify(data.decode(errors="replace")[:500])
            return
        self.notify(f"{item.get('name', item['id'])} is not a Doc or Sheet.")

    async def _view_sheet(self, item: dict[str, Any]) -> None:
        from gfunk.vibe import VibeApp

        rows = self._workspace.sample(item["id"], self._first_tab(item))
        with self.suspend():
            await VibeApp(rows).run_async()

    def _first_tab(self, item: dict[str, Any]) -> str:
        tabs = self._workspace.sheet_tabs(item["id"])
        return tabs[0] if tabs else "Sheet1"

    def _print_file(self, item: dict[str, Any]) -> None:
        mime = item.get("mimeType", "")
        if mime != DOC_MIME:
            self.notify(f"{item.get('name', item['id'])} is not a Doc — use View.")
            return
        data = self._workspace.export(item["id"], "text/plain")
        with self.suspend():
            sys.stdout.write(data.decode())

    def _move(self, item: dict[str, Any]) -> None:
        parents = item.get("parents", [])
        current_parent = parents[0] if parents else "root"

        def handle_folder(destination: str | None) -> None:
            if destination is None:
                return
            self._workspace.move(
                item["id"], add_parent=destination, remove_parent=current_parent
            )
            names = self._workspace.folder_names({destination})
            dest_name = names.get(destination, destination)
            self.notify(f"Moved {item.get('name', item['id'])} → {dest_name}")
            self._load()

        self.push_screen(FolderPickScreen(self._workspace), handle_folder)

    def _delete(self, item: dict[str, Any]) -> None:
        name = item.get("name", item["id"])

        def handle_confirm(confirmed: bool | None) -> None:  # noqa: FBT001
            if not confirmed:
                return
            self._workspace.trash(item["id"])
            self.notify(f"Trashed {name} (recoverable from Drive's trash)")
            self._load()

        self.push_screen(ConfirmTrashScreen(name), handle_confirm)
