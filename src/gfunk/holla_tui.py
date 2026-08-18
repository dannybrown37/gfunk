"""Interactive TUI for `holla` — junk-mail triage over Gmail.

Two screens in one app: a label overview (counts, no message fetch) and a
per-label message list (metadata only — sender/subject, no body). From the
message list you can filter by sender/subject, archive a message to Drive
as a long-term PDF, or open it in the browser.
"""

from __future__ import annotations

import webbrowser
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from gfunk.browser import register
from gfunk.workspace import FOLDER_MIME

if TYPE_CHECKING:
    from textual.timer import Timer

    from gfunk.workspace import Workspace


def matches_filter(message: dict[str, Any], query: str) -> bool:
    """A message matches if the query is a substring of its sender or subject."""
    if not query:
        return True
    needle = query.lower()
    haystack = [str(message.get("from", "")), str(message.get("subject", ""))]
    return any(needle in h.lower() for h in haystack)


KB = 1024
MB = 1024 * 1024


def format_size(num_bytes: int) -> str:
    if num_bytes < KB:
        return f"{num_bytes}B"
    if num_bytes < MB:
        return f"{num_bytes / KB:.0f}KB"
    return f"{num_bytes / MB:.1f}MB"


def gmail_web_url(message_id: str) -> str:
    return f"https://mail.google.com/mail/u/0/#all/{message_id}"


def format_date(internal_date: str) -> str:
    """`internalDate` (ms since epoch, as a string) to a short display date."""
    if not internal_date:
        return ""
    millis = int(internal_date)
    return datetime.fromtimestamp(millis / 1000, tz=UTC).strftime("%Y-%m-%d")


class LabelItem(ListItem):
    def __init__(self, label: dict[str, Any]) -> None:
        counts = f"{label['messages_total']}, {label['messages_unread']} unread"
        text = f"{label['name']} ({counts})"
        super().__init__(Static(text))
        self.label_row = label


class MessageItem(ListItem):
    def __init__(self, message: dict[str, Any]) -> None:
        size = format_size(int(message.get("size", 0)))
        date = format_date(str(message.get("date", "")))
        text = (
            f"{date}  {message.get('from', '')}  —  "
            f"{message.get('subject', '')}  ({size})"
        )
        super().__init__(Static(text))
        self.message = message


SELECT_HERE_ID = "__select__"
UP_ID = "__up__"
SELECT_HERE = {"id": SELECT_HERE_ID, "name": "· archive here ·"}
UP = {"id": UP_ID, "name": ".. (up)"}


class FolderItem(ListItem):
    def __init__(self, folder: dict[str, Any]) -> None:
        super().__init__(Static(folder["name"]))
        self.folder = folder


class FolderBrowseScreen(ModalScreen[str | None]):
    """Drive folder picker — snoop-style: drill into folders, pick one to archive."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "esc cancel"),
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
        folders = [c for c in children if c.get("mimeType") == FOLDER_MIME]
        list_view = self.query_one(ListView)
        list_view.clear()
        list_view.append(FolderItem(SELECT_HERE))
        if self._stack:
            list_view.append(FolderItem(UP))
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


PREVIEW_DEBOUNCE_SECONDS = 0.3
PREVIEW_CHARS = 2000


class ConfirmTrashScreen(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "dismiss_true", "y confirm", show=False),
        Binding("n", "dismiss_false", "n cancel", show=False),
        Binding("escape", "dismiss_false", "esc cancel", show=False),
    ]

    def __init__(self, subject: str) -> None:
        super().__init__()
        self._subject = subject

    def compose(self) -> ComposeResult:
        yield Static(f"Trash '{self._subject}'? Recoverable for 30 days. [y/n]")
        yield Footer()

    def action_dismiss_true(self) -> None:
        self.dismiss(result=True)

    def action_dismiss_false(self) -> None:
        self.dismiss(result=False)


class ConfirmDeleteLabelScreen(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "dismiss_true", "y confirm", show=False),
        Binding("n", "dismiss_false", "n cancel", show=False),
        Binding("escape", "dismiss_false", "esc cancel", show=False),
    ]

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def compose(self) -> ComposeResult:
        yield Static(f"Delete empty label '{self._name}'? Not recoverable. [y/n]")
        yield Footer()

    def action_dismiss_true(self) -> None:
        self.dismiss(result=True)

    def action_dismiss_false(self) -> None:
        self.dismiss(result=False)


class HollaApp(App[None]):
    """Browse Gmail labels, drill into one, back messages up, filter by sender."""

    ENABLE_COMMAND_PALETTE = False
    TITLE = "gfunk holla"
    CSS = """
    ListView {
        height: 2fr;
    }
    ListItem {
        padding: 0 1;
    }
    Input {
        display: none;
    }
    Input.visible {
        display: block;
    }
    #preview {
        display: none;
        height: 3fr;
        border-top: solid $accent;
        padding: 0 1;
        overflow-y: auto;
    }
    #preview.visible {
        display: block;
    }
    #preview:focus {
        border-top: solid $success;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "j ↓"),
        Binding("k", "cursor_up", "k ↑"),
        Binding("enter", "open_label", "open", show=False),
        Binding("tab", "toggle_preview_focus", "tab preview"),
        Binding("/", "filter", "/ filter"),
        Binding("a", "archive_message", "archive"),
        Binding("shift+a", "archive_to", "archive to…", key_display="A"),
        Binding("d", "delete_message", "delete (label if empty)"),
        Binding("o", "open_message", "open"),
        Binding("s", "toggle_sort", "s date/size"),
        Binding("escape", "escape", "esc back", show=False),
        Binding("q", "quit", "q quit"),
    ]

    def __init__(self, labels: list[dict[str, Any]], workspace: Workspace) -> None:
        super().__init__()
        self._labels = labels
        self._workspace = workspace
        self._current_label: dict[str, Any] | None = None
        self._messages: list[dict[str, Any]] = []
        self._query = ""
        self._sort_by_size = False
        self._preview_cache: dict[str, str] = {}
        self._preview_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Input(placeholder="filter by sender or subject…", id="filter-input")
            yield ListView(*[LabelItem(label) for label in self._sorted_labels()])
            with VerticalScroll(id="preview", can_focus=True):
                yield Static(id="preview-text", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.title = self.TITLE
        self.query_one(ListView).focus()

    def _sorted_labels(self) -> list[dict[str, Any]]:
        if not self._sort_by_size:
            return self._labels
        return sorted(self._labels, key=lambda label: -label["messages_total"])

    def _visible_messages(self) -> list[dict[str, Any]]:
        messages = [m for m in self._messages if matches_filter(m, self._query)]
        if self._sort_by_size:
            return sorted(messages, key=lambda m: -int(m.get("size", 0)))
        return sorted(messages, key=lambda m: -int(m.get("date", "0") or 0))

    def _show_labels(self) -> None:
        self._current_label = None
        self._query = ""
        self._clear_preview()
        list_view = self.query_one(ListView)
        list_view.clear()
        labels = self._sorted_labels()
        for item in [LabelItem(label) for label in labels]:
            list_view.append(item)
        if labels:
            list_view.index = 0
        self.sub_title = ""

    def _show_messages(self) -> None:
        list_view = self.query_one(ListView)
        list_view.clear()
        messages = self._visible_messages()
        for item in [MessageItem(m) for m in messages]:
            list_view.append(item)
        if messages:
            list_view.index = 0
            # `clear()` removes old children asynchronously, so the Highlighted
            # event posted by the `index = 0` assignment above can still see a
            # stale (pre-rebuild) item — sync the preview explicitly instead of
            # relying on that event for this rebuild.
            self._schedule_preview(messages[0])
        else:
            self._clear_preview()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, LabelItem):
            self._open_label(item.label_row)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        # `ListView.clear()` removes old children asynchronously, so a rebuild
        # (opening/leaving a label) can deliver a Highlighted event for the
        # *previous* screen's item after the rebuild already ran. Cross-check
        # against which screen we're actually on before acting on it.
        item = event.item
        if isinstance(item, MessageItem) and self._current_label is not None:
            self._schedule_preview(item.message)
        elif isinstance(item, LabelItem) and self._current_label is None:
            self._clear_preview()

    def action_open_label(self) -> None:
        item = self.query_one(ListView).highlighted_child
        if isinstance(item, LabelItem):
            self._open_label(item.label_row)

    def _open_label(self, label: dict[str, Any]) -> None:
        self._current_label = label
        self._messages = self._workspace.gmail_messages(label=label["id"], limit=100)
        self.sub_title = f"{label['name']} ({len(self._messages)})"
        self._show_messages()

    def action_filter(self) -> None:
        if self._current_label is None:
            return
        input_widget = self.query_one("#filter-input", Input)
        input_widget.add_class("visible")
        input_widget.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "filter-input":
            return
        self._query = event.value
        self._show_messages()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "filter-input":
            return
        self.query_one(ListView).focus()

    def action_escape(self) -> None:
        input_widget = self.query_one("#filter-input", Input)
        if input_widget.has_class("visible"):
            input_widget.value = ""
            input_widget.remove_class("visible")
            self._query = ""
            self._show_messages()
            self.query_one(ListView).focus()
            return
        if self._current_label is not None:
            self._show_labels()
            return
        self.exit()

    def action_toggle_sort(self) -> None:
        """Toggle sort order. Messages default to newest-first (`internalDate`),

        toggling to real byte size (`sizeEstimate`). Labels default to API order,
        toggling to message count — Gmail's label resource carries no byte-size
        total, so count is the closest available proxy for "how big is this pile."
        """
        self._sort_by_size = not self._sort_by_size
        if self._current_label is None:
            self._show_labels()
        else:
            self._show_messages()

    def action_open_message(self) -> None:
        message = self._highlighted_message()
        if message is None:
            return
        register()
        url = gmail_web_url(str(message["id"]))
        if not webbrowser.open(url):
            self.notify(f"Could not open a browser. The link is:\n{url}")

    def _preview_focused(self) -> bool:
        preview = self.query_one("#preview", VerticalScroll)
        return preview.has_focus

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
        if not preview.has_class("visible"):
            return
        if self._preview_focused():
            self.query_one(ListView).focus()
        else:
            preview.focus()

    def _highlighted_message(self) -> dict[str, Any] | None:
        item = self.query_one(ListView).highlighted_child
        if not isinstance(item, MessageItem):
            return None
        return item.message

    def _highlighted_label(self) -> dict[str, Any] | None:
        item = self.query_one(ListView).highlighted_child
        if not isinstance(item, LabelItem):
            return None
        return item.label_row

    def _schedule_preview(self, message: dict[str, Any]) -> None:
        """Debounced, lazy preview load — cursor moves cancel any pending fetch.

        Only the message the cursor settles on for `PREVIEW_DEBOUNCE_SECONDS`
        actually gets fetched, and each message's body is fetched at most once
        per session (cached by id).
        """
        if self._preview_timer is not None:
            self._preview_timer.stop()
            self._preview_timer = None
        self.query_one("#preview", VerticalScroll).add_class("visible")
        preview_text = self.query_one("#preview-text", Static)
        message_id = str(message["id"])
        cached = self._preview_cache.get(message_id)
        if cached is not None:
            preview_text.update(cached)
            return
        preview_text.update("")
        self._preview_timer = self.set_timer(
            PREVIEW_DEBOUNCE_SECONDS, lambda: self._load_preview(message_id)
        )

    def _load_preview(self, message_id: str) -> None:
        text = self._workspace.gmail_preview(message_id)[:PREVIEW_CHARS]
        self._preview_cache[message_id] = text
        self.query_one("#preview-text", Static).update(text)

    def _clear_preview(self) -> None:
        if self._preview_timer is not None:
            self._preview_timer.stop()
            self._preview_timer = None
        self.query_one("#preview", VerticalScroll).remove_class("visible")
        self.query_one("#preview-text", Static).update("")

    def action_delete_message(self) -> None:
        if self._current_label is None:
            self.action_delete_label()
            return

        message = self._highlighted_message()
        if message is None:
            return

        def handle_confirm(confirmed: bool | None) -> None:  # noqa: FBT001
            if not confirmed:
                return
            message_id = str(message["id"])
            self._workspace.gmail_trash_message(message_id)
            self._messages = [m for m in self._messages if m["id"] != message["id"]]
            self._preview_cache.pop(message_id, None)
            self._show_messages()
            self.notify("Trashed.")

        subject = str(message.get("subject", "(no subject)"))
        self.push_screen(ConfirmTrashScreen(subject), handle_confirm)

    def action_delete_label(self) -> None:
        label = self._highlighted_label()
        if label is None:
            return
        if label.get("type") != "user":
            self.notify(
                f"'{label['name']}' is a built-in Gmail label — can't be deleted.",
                severity="warning",
            )
            return
        if int(label.get("messages_total", 0)) > 0:
            self.notify(
                f"'{label['name']}' has {label['messages_total']} messages — "
                "empty it before deleting.",
                severity="warning",
            )
            return

        def handle_confirm(confirmed: bool | None) -> None:  # noqa: FBT001
            if not confirmed:
                return
            self._workspace.gmail_delete_label(label["id"])
            self._labels = [item for item in self._labels if item["id"] != label["id"]]
            self._show_labels()
            self.notify("Label deleted.")

        self.push_screen(ConfirmDeleteLabelScreen(label["name"]), handle_confirm)

    def action_archive_message(self) -> None:
        message = self._highlighted_message()
        if message is None:
            return
        result = self._workspace.gmail_archive_message(message["id"])
        self.notify(f"Archived to Drive: {result['name']}")

    def action_archive_to(self) -> None:
        message = self._highlighted_message()
        if message is None:
            return

        def handle_folder(folder_id: str | None) -> None:
            if folder_id is None:
                return
            result = self._workspace.gmail_archive_message(
                message["id"], parent=folder_id
            )
            self.notify(f"Archived to Drive: {result['name']}")

        self.push_screen(FolderBrowseScreen(self._workspace), handle_folder)
