"""Interactive TUI spreadsheet viewer powered by Textual."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import DataTable, Footer, Header, Input


class VibeApp(App[None]):
    ENABLE_COMMAND_PALETTE = False
    TITLE = "gfunk vibe"
    CSS = """
    Input {
        dock: top;
        display: none;
    }
    Input.visible {
        display: block;
    }
    DataTable {
        height: 1fr;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "↓"),
        Binding("k", "cursor_up", "↑"),
        Binding("h", "cursor_left", "←"),
        Binding("l", "cursor_right", "→"),
        Binding("g", "scroll_top", "top"),
        Binding("G", "scroll_bottom", "bottom", key_display="G"),
        Binding("/", "search", "search"),
        Binding("escape", "clear_search", "clear", show=False),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self, rows: list[dict[str, str]], title: str = "gfunk vibe") -> None:
        super().__init__()
        self._rows = rows
        self._all_rows = rows
        self._title = title

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Type to filter rows…", id="search")
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._title
        table = self.query_one(DataTable)
        table.cursor_type = "cell"
        table.zebra_stripes = True
        if self._rows:
            for col in self._rows[0]:
                table.add_column(col, key=col)
            self._populate(self._rows)
        table.focus()

    def _populate(self, rows: list[dict[str, str]]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for row in rows:
            table.add_row(*row.values())

    def action_cursor_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_cursor_left(self) -> None:
        self.query_one(DataTable).action_cursor_left()

    def action_cursor_right(self) -> None:
        self.query_one(DataTable).action_cursor_right()

    def action_scroll_top(self) -> None:
        table = self.query_one(DataTable)
        table.move_cursor(row=0, column=0)

    def action_scroll_bottom(self) -> None:
        table = self.query_one(DataTable)
        table.move_cursor(row=table.row_count - 1)

    def action_search(self) -> None:
        search = self.query_one("#search", Input)
        search.add_class("visible")
        search.focus()

    def action_clear_search(self) -> None:
        search = self.query_one("#search", Input)
        search.value = ""
        search.remove_class("visible")
        self._populate(self._all_rows)
        self.query_one(DataTable).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        term = event.value.lower()
        if not term:
            self._populate(self._all_rows)
            return
        filtered = [
            row
            for row in self._all_rows
            if any(term in v.lower() for v in row.values())
        ]
        self._populate(filtered)

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self.query_one("#search", Input).remove_class("visible")
        self.query_one(DataTable).focus()
