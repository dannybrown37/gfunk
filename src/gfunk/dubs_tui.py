"""Interactive TUI picker for `dubs` results, powered by Textual.

Rows are grouped by duplicate group under a header. Trashing a copy — or
keeping one and trashing its siblings — can drop a group below two members,
at which point it is no longer a duplicate and disappears from the list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

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
from gfunk.dubs import group_label, group_rows, human_bytes

if TYPE_CHECKING:
    from gfunk.workspace import Workspace

ACTIONS = ["Open in browser", "Keep only this copy", "Delete this copy"]
MIN_GROUP_SIZE = 2


def matches_filter(row: dict[str, Any], query: str) -> bool:
    """A row matches if the query is a substring of its path."""
    if not query:
        return True
    return query.lower() in str(row.get("path", row.get("name", ""))).lower()


class ActionScreen(ModalScreen[str | None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_none", "back", show=False),
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


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "dismiss_true", "confirm", show=False),
        Binding("n", "dismiss_false", "cancel", show=False),
        Binding("escape", "dismiss_false", "cancel", show=False),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        yield Static(f"{self._message} [y/n]")
        yield Footer()

    def action_dismiss_true(self) -> None:
        self.dismiss(result=True)

    def action_dismiss_false(self) -> None:
        self.dismiss(result=False)


class GroupHeader(ListItem):
    def __init__(self, label: str) -> None:
        super().__init__(Static(label, classes="group-header"), disabled=True)


class RowItem(ListItem):
    def __init__(self, row: dict[str, Any]) -> None:
        path = str(row.get("path", row.get("name", "")))
        size = int(row.get("size", 0) or 0)
        text = f"{path}  ({human_bytes(size)})" if size else path
        super().__init__(Static(text, classes="row-text"))
        self.row = row


def build_items(rows: list[dict[str, Any]]) -> list[ListItem]:
    items: list[ListItem] = []
    for key, members in group_rows(rows):
        if len(members) < MIN_GROUP_SIZE:
            continue
        items.append(GroupHeader(group_label(key, members)))
        items.extend(RowItem(row) for row in members)
    return items


class DubsApp(App[tuple[dict[str, Any], str] | None]):
    """Group-select a duplicate copy, then pick an action for it."""

    ENABLE_COMMAND_PALETTE = False
    TITLE = "gfunk dubs"
    CSS = """
    ListView {
        height: 1fr;
    }
    ListItem {
        padding: 0 1;
    }
    .group-header {
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
        Binding("j", "cursor_down", "↓"),
        Binding("k", "cursor_up", "↑"),
        Binding("g", "scroll_top", "top"),
        Binding("G", "scroll_bottom", "bottom", key_display="G"),
        Binding("/", "filter", "filter"),
        Binding("O", "open_selected", "open", key_display="O"),
        Binding("K", "keep_selected", "keep only", key_display="K"),
        Binding("D", "delete_selected", "delete", key_display="D"),
        Binding("escape", "escape", "quit", show=False),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self, rows: list[dict[str, Any]], workspace: Workspace | None) -> None:
        super().__init__()
        self._rows = rows
        self._workspace = workspace
        self._query = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Input(placeholder="filter by path…", id="filter-input")
            yield ListView(*build_items(self._rows))
        yield Footer()

    def on_mount(self) -> None:
        self.title = self.TITLE
        self.query_one(ListView).focus()

    def _visible_rows(self) -> list[dict[str, Any]]:
        """A group is visible if any member matches, so siblings aren't orphaned."""
        if not self._query:
            return self._rows
        matching_keys = {
            row["group_key"] for row in self._rows if matches_filter(row, self._query)
        }
        return [row for row in self._rows if row["group_key"] in matching_keys]

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

    def action_keep_selected(self) -> None:
        row = self._highlighted_row()
        if row is not None:
            self._handle_action(row, "Keep only this copy")

    def action_delete_selected(self) -> None:
        row = self._highlighted_row()
        if row is not None:
            self._handle_action(row, "Delete this copy")

    def _handle_action(self, row: dict[str, Any], action: str) -> None:
        """Every action here is handled in place, so the TUI stays up."""
        if action == "Open in browser":
            open_in_browser(row)
            self.notify(f"Opened {row.get('name', '')} in browser")
            return
        if action == "Delete this copy":
            self._confirm_delete(row)
            return
        if action == "Keep only this copy":
            self._confirm_keep(row)
            return
        self.exit((row, action))

    def _group_members(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        key = row["group_key"]
        return [r for r in self._rows if r.get("group_key") == key]

    def _drop_rows(self, ids: set[str]) -> None:
        self._rows = [r for r in self._rows if r.get("id") not in ids]
        self._rebuild(self._visible_rows())

    def _confirm_delete(self, row: dict[str, Any]) -> None:
        def on_confirm(confirmed: bool | None) -> None:  # noqa: FBT001
            if not confirmed:
                return
            assert self._workspace is not None
            self._workspace.trash(row["id"])
            self._drop_rows({row["id"]})
            self.notify(f"Trashed {row.get('name', '')}")

        name = row.get("name", "")
        self.push_screen(
            ConfirmScreen(f"Trash '{name}'? This cannot be undone from here."),
            on_confirm,
        )

    def _confirm_keep(self, row: dict[str, Any]) -> None:
        others = [r for r in self._group_members(row) if r.get("id") != row.get("id")]

        def on_confirm(confirmed: bool | None) -> None:  # noqa: FBT001
            if not confirmed:
                return
            assert self._workspace is not None
            for other in others:
                self._workspace.trash(other["id"])
            self._drop_rows({o["id"] for o in others})
            self.notify(f"Kept {row.get('name', '')}, trashed {len(others)} other(s)")

        names = ", ".join(str(o.get("name", "")) for o in others)
        name = row.get("name", "")
        self.push_screen(
            ConfirmScreen(
                f"Keep '{name}' and trash {len(others)} other(s) ({names})? "
                "This cannot be undone from here."
            ),
            on_confirm,
        )
