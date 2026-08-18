import asyncio
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import ListView

from gfunk.regulate_tui import (
    FolderHeader,
    RegulateApp,
    RowItem,
    group_by_folder,
    matches_filter,
)

SHARED_FILE = {
    "id": "a",
    "name": "Q3 Numbers",
    "path": "Reports/Q3 Numbers",
    "folder": "Reports",
    "exposure": "public",
    "reached_by": ["anyone with the link"],
    "permission_ids": ["anyone-perm"],
    "link": "https://example.com/a",
}
OTHER_FILE = {
    "id": "b",
    "name": "Roadmap",
    "path": "Planning/Roadmap",
    "folder": "Planning",
    "exposure": "external",
    "reached_by": ["ada@partner.com"],
    "link": "https://example.com/b",
}


@pytest.mark.parametrize(
    ("row", "query", "expected"),
    [
        (SHARED_FILE, "", True),
        (SHARED_FILE, "reports", True),
        (SHARED_FILE, "REPORTS", True),
        (SHARED_FILE, "anyone with the link", True),
        (SHARED_FILE, "planning", False),
        (OTHER_FILE, "ada@partner.com", True),
        (OTHER_FILE, "reports", False),
    ],
)
def test_matches_filter(row: dict[str, object], query: str, *, expected: bool) -> None:
    assert matches_filter(row, query) is expected


def test_group_by_folder_buckets_and_preserves_order() -> None:
    groups = group_by_folder([SHARED_FILE, OTHER_FILE])
    assert [folder for folder, _rows in groups] == ["Reports", "Planning"]
    assert groups[0][1] == [SHARED_FILE]
    assert groups[1][1] == [OTHER_FILE]


def test_group_by_folder_defaults_untagged_rows() -> None:
    untagged = {**SHARED_FILE, "folder": ""}
    groups = group_by_folder([untagged])
    assert groups[0][0] == "(no folder)"


def test_folder_headers_are_not_selectable() -> None:
    async def run() -> bool:
        app = RegulateApp([SHARED_FILE, OTHER_FILE], workspace=None)
        async with app.run_test() as pilot:
            await pilot.pause()
            list_view = app.query_one(ListView)
            headers = list_view.query(FolderHeader)
            return all(header.disabled for header in headers)

    assert asyncio.run(run()) is True


def test_slash_filters_the_visible_rows() -> None:
    async def run() -> int:
        app = RegulateApp([SHARED_FILE, OTHER_FILE], workspace=None)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"reports")
            await pilot.pause()
            rows = app.query_one(ListView).query(RowItem)
            return len(rows)

    assert asyncio.run(run()) == 1


def test_capital_o_opens_the_highlighted_row_without_exiting() -> None:
    async def run() -> tuple[bool, int]:
        app = RegulateApp([SHARED_FILE, OTHER_FILE], workspace=None)
        with patch("gfunk.regulate_tui.open_in_browser") as opened:
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("O")
                await pilot.pause()
                rows = app.query_one(ListView).query(RowItem)
                return opened.called, len(rows)

    opened, row_count = asyncio.run(run())
    assert opened is True
    assert row_count == 2


def test_capital_d_trashes_the_row_after_typing_trash() -> None:
    async def run() -> tuple[bool, int]:
        ws = MagicMock()
        app = RegulateApp([SHARED_FILE, OTHER_FILE], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("D")
            await pilot.pause()
            await pilot.press(*"trash")
            await pilot.press("enter")
            await pilot.pause()
            rows = app.query_one(ListView).query(RowItem)
            return ws.trash.called, len(rows)

    trashed, row_count = asyncio.run(run())
    assert trashed is True
    assert row_count == 1


def test_capital_d_cancelled_leaves_the_row() -> None:
    async def run() -> tuple[bool, int]:
        ws = MagicMock()
        app = RegulateApp([SHARED_FILE, OTHER_FILE], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("D")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            rows = app.query_one(ListView).query(RowItem)
            return ws.trash.called, len(rows)

    trashed, row_count = asyncio.run(run())
    assert trashed is False
    assert row_count == 2


def test_capital_r_revokes_the_row_after_typing_revoke() -> None:
    async def run() -> tuple[bool, int]:
        ws = MagicMock()
        app = RegulateApp([SHARED_FILE, OTHER_FILE], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("R")
            await pilot.pause()
            await pilot.press(*"revoke")
            await pilot.press("enter")
            await pilot.pause()
            rows = app.query_one(ListView).query(RowItem)
            return ws.revoke.called, len(rows)

    revoked, row_count = asyncio.run(run())
    assert revoked is True
    assert row_count == 1


def test_capital_r_revokes_every_permission_id_on_the_row() -> None:
    async def run() -> list[object]:
        ws = MagicMock()
        row = {**SHARED_FILE, "permission_ids": ["p1", "p2"]}
        app = RegulateApp([row], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("R")
            await pilot.pause()
            await pilot.press(*"revoke")
            await pilot.press("enter")
            await pilot.pause()
            return list(ws.revoke.call_args_list)

    calls = asyncio.run(run())
    assert calls == [(("a", "p1"),), (("a", "p2"),)]


def test_capital_r_cancelled_leaves_the_row() -> None:
    async def run() -> tuple[bool, int]:
        ws = MagicMock()
        app = RegulateApp([SHARED_FILE, OTHER_FILE], workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("R")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            rows = app.query_one(ListView).query(RowItem)
            return ws.revoke.called, len(rows)

    revoked, row_count = asyncio.run(run())
    assert revoked is False
    assert row_count == 2


def test_escape_clears_the_filter() -> None:
    async def run() -> int:
        app = RegulateApp([SHARED_FILE, OTHER_FILE], workspace=None)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"reports")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            rows = app.query_one(ListView).query(RowItem)
            return len(rows)

    assert asyncio.run(run()) == 2
