import asyncio
from collections.abc import Callable
from unittest.mock import MagicMock, call, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import ListView

from gfunk.holla_tui import (
    FolderBrowseScreen,
    FolderItem,
    HollaApp,
    LabelItem,
    MessageItem,
    format_date,
    format_size,
    gmail_web_url,
    matches_filter,
)

DOCS_FOLDER = {
    "id": "f-docs",
    "name": "Docs",
    "mimeType": "application/vnd.google-apps.folder",
}
RECEIPT_FILE = {"id": "file-1", "name": "receipt.pdf", "mimeType": "application/pdf"}
NESTED_FOLDER = {
    "id": "f-nested",
    "name": "Nested",
    "mimeType": "application/vnd.google-apps.folder",
}

INBOX = {
    "id": "INBOX",
    "name": "INBOX",
    "type": "system",
    "messages_total": 2,
    "messages_unread": 1,
}
PROMO = {
    "id": "CATEGORY_PROMOTIONS",
    "name": "CATEGORY_PROMOTIONS",
    "type": "system",
    "messages_total": 300,
    "messages_unread": 290,
}
MSG_1 = {
    "id": "m1",
    "from": "billing@example.com",
    "subject": "Invoice #42",
    "snippet": "",
    "labels": ["INBOX"],
    "date": "1704153600000",
    "size": 5000,
}
MSG_2 = {
    "id": "m2",
    "from": "friend@example.com",
    "subject": "Coffee?",
    "snippet": "",
    "labels": ["INBOX"],
    "date": "1704067200000",
    "size": 200000,
}


@pytest.mark.parametrize(
    ("num_bytes", "expected"),
    [
        (500, "500B"),
        (2048, "2KB"),
        (5 * 1024 * 1024, "5.0MB"),
    ],
)
def test_format_size(num_bytes: int, expected: str) -> None:
    assert format_size(num_bytes) == expected


def test_gmail_web_url() -> None:
    assert gmail_web_url("m1") == "https://mail.google.com/mail/u/0/#all/m1"


def test_format_date() -> None:
    assert format_date("1704067200000") == "2024-01-01"
    assert format_date("") == ""


@pytest.mark.parametrize(
    ("message", "query", "expected"),
    [
        (MSG_1, "", True),
        (MSG_1, "billing", True),
        (MSG_1, "BILLING", True),
        (MSG_1, "invoice", True),
        (MSG_1, "friend", False),
    ],
)
def test_matches_filter(
    message: dict[str, object], query: str, *, expected: bool
) -> None:
    assert matches_filter(message, query) is expected


def test_starts_on_label_overview_with_counts() -> None:
    async def run() -> list[str]:
        app = HollaApp([INBOX, PROMO], workspace=MagicMock())
        async with app.run_test() as pilot:
            await pilot.pause()
            items = app.query_one(ListView).query(LabelItem)
            return [item.label_row["id"] for item in items]

    assert asyncio.run(run()) == ["INBOX", "CATEGORY_PROMOTIONS"]


def test_selecting_a_label_loads_its_messages() -> None:
    async def run() -> list[str]:
        ws = MagicMock()
        ws.gmail_preview.return_value = ""
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            items = app.query_one(ListView).query(MessageItem)
            return [item.message["id"] for item in items]

    assert asyncio.run(run()) == ["m1", "m2"]


def test_messages_default_sorted_newest_first() -> None:
    async def run() -> list[str]:
        ws = MagicMock()
        ws.gmail_preview.return_value = ""
        ws.gmail_messages.return_value = [MSG_2, MSG_1]
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            items = app.query_one(ListView).query(MessageItem)
            return [item.message["id"] for item in items]

    assert asyncio.run(run()) == ["m1", "m2"]


def test_escape_from_messages_returns_to_labels() -> None:
    async def run() -> list[str]:
        ws = MagicMock()
        ws.gmail_preview.return_value = ""
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            items = app.query_one(ListView).query(LabelItem)
            return [item.label_row["id"] for item in items]

    assert asyncio.run(run()) == ["INBOX", "CATEGORY_PROMOTIONS"]


def test_slash_filters_messages_by_sender() -> None:
    async def run() -> int:
        ws = MagicMock()
        ws.gmail_preview.return_value = ""
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("/")
            await pilot.press(*"billing")
            await pilot.pause()
            return len(app.query_one(ListView).query(MessageItem))

    assert asyncio.run(run()) == 1


def test_a_archives_the_highlighted_message() -> None:
    async def run() -> MagicMock:
        ws = MagicMock()
        ws.gmail_preview.return_value = ""
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        ws.gmail_archive_message.return_value = {
            "id": "d1",
            "name": "2024-01-01_invoice-42_m1.pdf",
            "webViewLink": "https://drive.google.com/file/d/d1",
        }
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            return ws

    ws = asyncio.run(run())
    ws.gmail_archive_message.assert_called_once_with("m1")


class _ScreenHost(App[None]):
    """Minimal host app — pushes one screen on mount, optionally captures dismiss."""

    def __init__(
        self,
        screen: FolderBrowseScreen,
        callback: Callable[[str | None], None] | None = None,
    ) -> None:
        super().__init__()
        self._screen = screen
        self._callback = callback

    def compose(self) -> ComposeResult:
        return iter(())

    def on_mount(self) -> None:
        self.push_screen(self._screen, self._callback)


def test_folder_browse_lists_folders_only_and_a_select_option() -> None:
    async def run() -> list[str]:
        ws = MagicMock()
        ws.children.return_value = [DOCS_FOLDER, RECEIPT_FILE]
        screen = FolderBrowseScreen(ws)
        async with _ScreenHost(screen).run_test() as pilot:
            await pilot.pause()
            items = screen.query_one(ListView).query(FolderItem)
            return [item.folder["id"] for item in items]

    assert asyncio.run(run()) == ["__select__", "f-docs"]


def test_folder_browse_enter_on_folder_drills_in() -> None:
    async def run() -> list[object]:
        ws = MagicMock()
        ws.children.side_effect = [[DOCS_FOLDER], [NESTED_FOLDER]]
        screen = FolderBrowseScreen(ws)
        async with _ScreenHost(screen).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            return list(ws.children.call_args_list)

    assert asyncio.run(run()) == [call("root"), call("f-docs")]


def test_folder_browse_up_returns_to_parent() -> None:
    async def run() -> list[object]:
        ws = MagicMock()
        ws.children.return_value = [DOCS_FOLDER]
        screen = FolderBrowseScreen(ws)
        async with _ScreenHost(screen).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")  # root -> select item -> docs item
            await pilot.press("enter")  # drill into f-docs
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("down")  # select -> up -> docs item
            await pilot.press("enter")  # drill into nested f-docs
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("enter")  # select -> up: back to f-docs
            await pilot.pause()
            return list(ws.children.call_args_list)

    calls = asyncio.run(run())
    assert calls[-1] == call("f-docs")


def test_folder_browse_select_here_dismisses_with_current_folder() -> None:
    async def run() -> str | None:
        ws = MagicMock()
        ws.children.return_value = [DOCS_FOLDER]
        screen = FolderBrowseScreen(ws)
        result: str | None = "unset"

        def capture(value: str | None) -> None:
            nonlocal result
            result = value

        async with _ScreenHost(screen, capture).run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
        return result

    assert asyncio.run(run()) == "root"


def test_folder_browse_escape_dismisses_with_none() -> None:
    async def run() -> str | None:
        ws = MagicMock()
        ws.children.return_value = [DOCS_FOLDER]
        screen = FolderBrowseScreen(ws)
        result: str | None = "unset"

        def capture(value: str | None) -> None:
            nonlocal result
            result = value

        async with _ScreenHost(screen, capture).run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        return result

    assert asyncio.run(run()) is None


def test_shift_a_opens_folder_browser_and_archives_to_chosen_folder() -> None:
    async def run() -> MagicMock:
        ws = MagicMock()
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        ws.gmail_preview.return_value = "body text"
        ws.children.return_value = [DOCS_FOLDER]
        ws.gmail_archive_message.return_value = {
            "id": "d1",
            "name": "2024-01-01_invoice-42_m1.pdf",
            "webViewLink": "https://drive.google.com/file/d/d1",
        }
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("shift+a")
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("enter")  # drill into Docs
            await pilot.pause()
            await pilot.press("enter")  # select here (index 0)
            await pilot.pause()
        return ws

    ws = asyncio.run(run())
    ws.gmail_archive_message.assert_called_once_with("m1", parent="f-docs")


def test_o_opens_the_highlighted_message_in_browser() -> None:
    async def run() -> str:
        ws = MagicMock()
        ws.gmail_preview.return_value = ""
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        app = HollaApp([INBOX, PROMO], workspace=ws)
        with (
            patch("gfunk.holla_tui.register"),
            patch("gfunk.holla_tui.webbrowser.open", return_value=True) as opened,
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("o")
                await pilot.pause()
        return str(opened.call_args.args[0])

    assert asyncio.run(run()) == "https://mail.google.com/mail/u/0/#all/m1"


def test_s_sorts_messages_by_size_descending() -> None:
    async def run() -> list[str]:
        ws = MagicMock()
        ws.gmail_preview.return_value = ""
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            items = app.query_one(ListView).query(MessageItem)
            return [item.message["id"] for item in items]

    assert asyncio.run(run()) == ["m2", "m1"]


def test_preview_is_not_fetched_until_debounce_elapses() -> None:
    async def run() -> tuple[int, int]:
        ws = MagicMock()
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        ws.gmail_preview.return_value = "body text"
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            calls_immediately = ws.gmail_preview.call_count
            await pilot.pause(0.5)
            calls_after_debounce = ws.gmail_preview.call_count
            return calls_immediately, calls_after_debounce

    immediately, after_debounce = asyncio.run(run())
    assert immediately == 0
    assert after_debounce == 1


def test_preview_fetches_only_the_final_highlighted_message_after_rapid_moves() -> None:
    async def run() -> list[object]:
        ws = MagicMock()
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        ws.gmail_preview.return_value = "body text"
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("j")
            await pilot.pause()
            await pilot.press("k")
            await pilot.pause(0.5)
            return list(ws.gmail_preview.call_args_list)

    calls = asyncio.run(run())
    assert calls == [call("m1")]


def test_preview_is_cached_and_not_refetched_for_the_same_message() -> None:
    async def run() -> int:
        ws = MagicMock()
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        ws.gmail_preview.return_value = "body text"
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause(0.5)
            await pilot.press("j")
            await pilot.pause(0.5)
            await pilot.press("k")
            await pilot.pause(0.5)
            return int(ws.gmail_preview.call_count)

    assert asyncio.run(run()) == 2


def test_d_prompts_and_trashes_the_highlighted_message_on_confirm() -> None:
    async def run() -> MagicMock:
        ws = MagicMock()
        ws.gmail_preview.return_value = ""
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        ws.gmail_trash_message.return_value = {"id": "m1"}
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            return ws

    ws = asyncio.run(run())
    ws.gmail_trash_message.assert_called_once_with("m1")


def test_d_then_n_cancels_and_does_not_trash() -> None:
    async def run() -> MagicMock:
        ws = MagicMock()
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        ws.gmail_preview.return_value = "body text"
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            return ws

    ws = asyncio.run(run())
    ws.gmail_trash_message.assert_not_called()


def test_d_removes_the_message_from_the_list_on_confirm() -> None:
    async def run() -> list[str]:
        ws = MagicMock()
        ws.gmail_preview.return_value = ""
        ws.gmail_messages.return_value = [MSG_1, MSG_2]
        ws.gmail_trash_message.return_value = {"id": "m1"}
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            items = app.query_one(ListView).query(MessageItem)
            return [item.message["id"] for item in items]

    assert asyncio.run(run()) == ["m2"]


EMPTY_LABEL = {
    "id": "EMPTY",
    "name": "Empty",
    "type": "user",
    "messages_total": 0,
    "messages_unread": 0,
}


def test_d_on_empty_label_prompts_and_deletes_on_confirm() -> None:
    async def run() -> MagicMock:
        ws = MagicMock()
        app = HollaApp([EMPTY_LABEL, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            return ws

    ws = asyncio.run(run())
    ws.gmail_delete_label.assert_called_once_with("EMPTY")


def test_d_on_empty_label_then_n_cancels_and_does_not_delete() -> None:
    async def run() -> MagicMock:
        ws = MagicMock()
        app = HollaApp([EMPTY_LABEL, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            return ws

    ws = asyncio.run(run())
    ws.gmail_delete_label.assert_not_called()


def test_d_on_empty_label_removes_it_from_the_list_on_confirm() -> None:
    async def run() -> list[str]:
        ws = MagicMock()
        app = HollaApp([EMPTY_LABEL, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            items = app.query_one(ListView).query(LabelItem)
            return [item.label_row["id"] for item in items]

    assert asyncio.run(run()) == ["CATEGORY_PROMOTIONS"]


def test_d_on_non_empty_label_warns_and_does_not_prompt() -> None:
    async def run() -> MagicMock:
        ws = MagicMock()
        app = HollaApp([PROMO, EMPTY_LABEL], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            return ws

    ws = asyncio.run(run())
    ws.gmail_delete_label.assert_not_called()


def test_s_toggles_labels_by_message_count_descending() -> None:
    async def run() -> list[str]:
        app = HollaApp([INBOX, PROMO], workspace=MagicMock())
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            items = app.query_one(ListView).query(LabelItem)
            return [item.label_row["id"] for item in items]

    assert asyncio.run(run()) == ["CATEGORY_PROMOTIONS", "INBOX"]


def test_d_on_builtin_label_warns_and_does_not_prompt() -> None:
    async def run() -> MagicMock:
        ws = MagicMock()
        app = HollaApp([INBOX, PROMO], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            return ws

    ws = asyncio.run(run())
    ws.gmail_delete_label.assert_not_called()
