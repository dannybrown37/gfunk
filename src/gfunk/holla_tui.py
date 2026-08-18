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
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from gfunk.browser import register
from gfunk.workspace import FOLDER_MIME

if TYPE_CHECKING:
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


class HollaApp(App[None]):
    """Browse Gmail labels, drill into one, back messages up, filter by sender."""

    ENABLE_COMMAND_PALETTE = False
    TITLE = "gfunk holla"
    CSS = """
    ListView {
        height: 1fr;
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
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "j ↓"),
        Binding("k", "cursor_up", "k ↑"),
        Binding("enter", "open_label", "open", show=False),
        Binding("/", "filter", "/ filter"),
        Binding("a", "archive_message", "archive"),
        Binding("shift+a", "archive_to", "archive to…", key_display="A"),
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

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Input(placeholder="filter by sender or subject…", id="filter-input")
            yield ListView(*[LabelItem(label) for label in self._sorted_labels()])
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

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, LabelItem):
            self._open_label(item.label_row)

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

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def _highlighted_message(self) -> dict[str, Any] | None:
        item = self.query_one(ListView).highlighted_child
        if not isinstance(item, MessageItem):
            return None
        return item.message

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
