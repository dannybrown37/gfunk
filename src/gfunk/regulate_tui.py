"""Interactive TUI picker for `regulate` results, powered by Textual.

Each result renders as its own box, same text as the plain-terminal report
(label, path, one line per reach) — just boxed up and selectable, not
condensed onto a single row. The link is left out; "Open in browser" covers it.
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

from gfunk.regulate import EXPOSURE_LABELS

ACTIONS = ["Open in browser", "Move", "Delete", "Change permissions"]


def matches_filter(row: dict[str, Any], query: str) -> bool:
    """A row matches if the query is a substring of its folder/path or any viewer."""
    if not query:
        return True
    needle = query.lower()
    haystack = [str(row.get("path", row.get("name", "")))]
    haystack += [str(reach) for reach in row.get("reached_by", [])]
    return any(needle in h.lower() for h in haystack)


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


class RowItem(ListItem):
    def __init__(self, row: dict[str, Any]) -> None:
        label = EXPOSURE_LABELS.get(str(row["exposure"]), str(row["exposure"]))
        path = row.get("path", row["name"])
        lines = [f"{label}  {path}"]
        lines += [f"            └─ {reach}" for reach in row["reached_by"]]
        super().__init__(Static("\n".join(lines)))
        self.row = row


class RegulateApp(App[tuple[dict[str, Any], str] | None]):
    """Box-select a shared file, then pick an action for it — link stays hidden."""

    ENABLE_COMMAND_PALETTE = False
    TITLE = "gfunk regulate"
    CSS = """
    ListView {
        height: 1fr;
    }
    ListItem {
        border: round $panel;
        padding: 0 1;
        margin-bottom: 1;
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
        Binding("escape", "escape", "esc quit", show=False),
        Binding("q", "quit", "q quit"),
    ]

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        super().__init__()
        self._rows = rows
        self._query = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Input(placeholder="filter by folder or viewer…")
            yield ListView(*(RowItem(row) for row in self._rows))
        yield Footer()

    def on_mount(self) -> None:
        self.title = self.TITLE
        self.query_one(ListView).focus()

    def _visible_rows(self) -> list[dict[str, Any]]:
        return [row for row in self._rows if matches_filter(row, self._query)]

    def action_filter(self) -> None:
        input_widget = self.query_one(Input)
        input_widget.add_class("visible")
        input_widget.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._query = event.value
        list_view = self.query_one(ListView)
        list_view.clear()
        for row in self._visible_rows():
            list_view.append(RowItem(row))

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self.query_one(ListView).focus()

    def action_escape(self) -> None:
        input_widget = self.query_one(Input)
        if not input_widget.has_class("visible"):
            self.exit()
            return
        input_widget.value = ""
        input_widget.remove_class("visible")
        self._query = ""
        list_view = self.query_one(ListView)
        list_view.clear()
        for row in self._rows:
            list_view.append(RowItem(row))
        list_view.focus()

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def action_scroll_top(self) -> None:
        self.query_one(ListView).index = 0

    def action_scroll_bottom(self) -> None:
        list_view = self.query_one(ListView)
        list_view.index = len(list_view) - 1

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        assert isinstance(item, RowItem)
        row = item.row

        def on_action(action: str | None) -> None:
            if action is not None:
                self.exit((row, action))

        self.push_screen(ActionScreen(), on_action)
