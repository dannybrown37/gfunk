"""Interactive TUI picker for `regulate` results, powered by Textual.

Rows are grouped by folder under a header, one compact line per file —
label, name, and who can reach it. The link is left out; "Open in browser"
covers it.
"""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Footer,
    Header,
    Input,
    ListItem,
    ListView,
    OptionList,
    Static,
)

from gfunk.browser import open_in_browser
from gfunk.regulate import EXPOSURE_LABELS

ACTIONS = ["Open in browser", "Move", "Delete", "Revoke access", "Change permissions"]
NO_FOLDER = "(no folder)"


def matches_filter(row: dict[str, Any], query: str) -> bool:
    """A row matches if the query is a substring of its folder/path or any viewer."""
    if not query:
        return True
    needle = query.lower()
    haystack = [str(row.get("path", row.get("name", "")))]
    haystack += [str(reach) for reach in row.get("reached_by", [])]
    return any(needle in h.lower() for h in haystack)


def group_by_folder(
    rows: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Bucket rows by folder, preserving first-seen folder order."""
    order: list[str] = []
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        folder = str(row.get("folder") or "") or NO_FOLDER
        if folder not in groups:
            order.append(folder)
            groups[folder] = []
        groups[folder].append(row)
    return [(folder, groups[folder]) for folder in order]


class ActionScreen(ModalScreen[str | None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_none", "esc back", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield OptionList(*ACTIONS, id="actions")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.prompt))

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


class ConfirmDeleteScreen(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "dismiss_true", "y confirm", show=False),
        Binding("n", "dismiss_false", "n cancel", show=False),
        Binding("escape", "dismiss_false", "esc cancel", show=False),
    ]

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def compose(self) -> ComposeResult:
        yield Static(f"Trash '{self._name}'? This cannot be undone from here. [y/n]")
        yield Footer()

    def action_dismiss_true(self) -> None:
        self.dismiss(result=True)

    def action_dismiss_false(self) -> None:
        self.dismiss(result=False)


class ConfirmRevokeScreen(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "dismiss_true", "y confirm", show=False),
        Binding("n", "dismiss_false", "n cancel", show=False),
        Binding("escape", "dismiss_false", "esc cancel", show=False),
    ]

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def compose(self) -> ComposeResult:
        yield Static(
            f"Revoke all access to '{self._name}'? "
            "This cannot be undone from here. [y/n]"
        )
        yield Footer()

    def action_dismiss_true(self) -> None:
        self.dismiss(result=True)

    def action_dismiss_false(self) -> None:
        self.dismiss(result=False)


class FolderHeader(ListItem):
    def __init__(self, folder: str, count: int) -> None:
        super().__init__(
            Static(f"{folder} ({count})"), classes="folder-header", disabled=True
        )


class RowItem(ListItem):
    def __init__(self, row: dict[str, Any]) -> None:
        label = EXPOSURE_LABELS.get(str(row["exposure"]), str(row["exposure"]))
        name = row.get("name", "")
        reach = ", ".join(row.get("reached_by", []))
        text = f"{label}  {name}"
        if reach:
            text += f"  — {reach}"
        super().__init__(Static(text, classes="row-text"))
        self.row = row


def build_items(rows: list[dict[str, Any]]) -> list[ListItem]:
    items: list[ListItem] = []
    for folder, folder_rows in group_by_folder(rows):
        items.append(FolderHeader(folder, len(folder_rows)))
        items.extend(RowItem(row) for row in folder_rows)
    return items


class RegulateApp(App[tuple[dict[str, Any], str] | None]):
    """Group-select a shared file, then pick an action for it — link stays hidden."""

    ENABLE_COMMAND_PALETTE = False
    TITLE = "gfunk regulate"
    CSS = """
    ListView {
        height: 1fr;
    }
    ListItem {
        padding: 0 1;
    }
    .folder-header {
        background: $panel;
        text-style: bold;
    }
    .row-text {
        color: $text-muted;
    }
    Input {
        display: none;
    }
    Input.visible {
        display: block;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "j ↓"),
        Binding("k", "cursor_up", "k ↑"),
        Binding("g", "scroll_top", "gg top"),
        Binding("G", "scroll_bottom", "G bottom", key_display="G"),
        Binding("/", "filter", "/ filter"),
        Binding("O", "open_selected", "O open", key_display="O"),
        Binding("D", "delete_selected", "D delete", key_display="D"),
        Binding("R", "revoke_selected", "R revoke", key_display="R"),
        Binding("escape", "escape", "esc quit", show=False),
        Binding("q", "quit", "q quit"),
    ]

    def __init__(self, rows: list[dict[str, Any]], workspace: Any) -> None:
        super().__init__()
        self._rows = rows
        self._workspace = workspace
        self._query = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Input(placeholder="filter by folder or viewer…", id="filter-input")
            yield ListView(*build_items(self._rows))
        yield Footer()

    def on_mount(self) -> None:
        self.title = self.TITLE
        self.query_one(ListView).focus()

    def _visible_rows(self) -> list[dict[str, Any]]:
        return [row for row in self._rows if matches_filter(row, self._query)]

    def _rebuild(self, rows: list[dict[str, Any]]) -> None:
        list_view = self.query_one(ListView)
        list_view.clear()
        for item in build_items(rows):
            list_view.append(item)

    def action_filter(self) -> None:
        input_widget = self.query_one("#filter-input", Input)
        input_widget.add_class("visible")
        input_widget.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "filter-input":
            return
        self._query = event.value
        self._rebuild(self._visible_rows())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "filter-input":
            return
        self.query_one(ListView).focus()

    def action_escape(self) -> None:
        input_widget = self.query_one("#filter-input", Input)
        if not input_widget.has_class("visible"):
            self.exit()
            return
        input_widget.value = ""
        input_widget.remove_class("visible")
        self._query = ""
        self._rebuild(self._rows)
        self.query_one(ListView).focus()

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def action_scroll_top(self) -> None:
        list_view = self.query_one(ListView)
        for index, item in enumerate(list_view.children):
            if not item.disabled:
                list_view.index = index
                break

    def action_scroll_bottom(self) -> None:
        list_view = self.query_one(ListView)
        for index in range(len(list_view) - 1, -1, -1):
            if not list_view.children[index].disabled:
                list_view.index = index
                break

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, RowItem):
            return
        row = item.row

        def on_action(action: str | None) -> None:
            if action is not None:
                self._handle_action(row, action)

        self.push_screen(ActionScreen(), on_action)

    def _highlighted_row(self) -> dict[str, Any] | None:
        item = self.query_one(ListView).highlighted_child
        if not isinstance(item, RowItem):
            return None
        return item.row

    def action_open_selected(self) -> None:
        row = self._highlighted_row()
        if row is not None:
            self._handle_action(row, "Open in browser")

    def action_delete_selected(self) -> None:
        row = self._highlighted_row()
        if row is not None:
            self._handle_action(row, "Delete")

    def action_revoke_selected(self) -> None:
        row = self._highlighted_row()
        if row is not None:
            self._handle_action(row, "Revoke access")

    def _handle_action(self, row: dict[str, Any], action: str) -> None:
        """Open, Delete, and Revoke are handled in place, so the TUI stays up."""
        if action == "Open in browser":
            open_in_browser(row)
            self.notify(f"Opened {row.get('name', '')} in browser")
            return
        if action == "Delete":
            self._confirm_delete(row)
            return
        if action == "Revoke access":
            self._confirm_revoke(row)
            return
        self.exit((row, action))

    def _confirm_delete(self, row: dict[str, Any]) -> None:
        def on_confirm(confirmed: bool | None) -> None:  # noqa: FBT001
            if not confirmed:
                return
            self._workspace.trash(row["id"])
            self._rows = [r for r in self._rows if r.get("id") != row.get("id")]
            self._rebuild(self._visible_rows())
            self.notify(f"Trashed {row.get('name', '')}")

        self.push_screen(ConfirmDeleteScreen(str(row.get("name", ""))), on_confirm)

    def _confirm_revoke(self, row: dict[str, Any]) -> None:
        def on_confirm(confirmed: bool | None) -> None:  # noqa: FBT001
            if not confirmed:
                return
            for permission_id in row.get("permission_ids", []):
                self._workspace.revoke(row["id"], permission_id)
            self._rows = [r for r in self._rows if r.get("id") != row.get("id")]
            self._rebuild(self._visible_rows())
            self.notify(f"Revoked access to {row.get('name', '')}")

        self.push_screen(ConfirmRevokeScreen(str(row.get("name", ""))), on_confirm)
