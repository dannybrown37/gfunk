import asyncio
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import ListView

from gfunk.dubs import flatten_groups
from gfunk.dubs_tui import DubsApp, GroupHeader, RowItem, matches_filter


A1 = {"id": "a1", "name": "report.pdf", "path": "Reports/report.pdf", "size": "100"}
A2 = {
    "id": "a2",
    "name": "report (1).pdf",
    "path": "Reports/report (1).pdf",
    "size": "100",
}


def rows() -> list[dict[str, object]]:
    return flatten_groups([[A1, A2]], [])


@pytest.mark.parametrize(
    ("row", "query", "expected"),
    [
        (A1, "", True),
        (A1, "reports", True),
        (A1, "REPORTS", True),
        (A1, "notes", False),
    ],
)
def test_matches_filter(row: dict[str, object], query: str, *, expected: bool) -> None:
    assert matches_filter(row, query) is expected


def test_group_headers_are_not_selectable() -> None:
    async def run() -> bool:
        app = DubsApp(rows(), workspace=None)
        async with app.run_test() as pilot:
            await pilot.pause()
            headers = app.query_one(ListView).query(GroupHeader)
            return all(header.disabled for header in headers)

    assert asyncio.run(run()) is True


def test_singleton_groups_are_not_shown() -> None:
    async def run() -> int:
        app = DubsApp(rows(), workspace=None)
        async with app.run_test() as pilot:
            await pilot.pause()
            return len(app.query_one(ListView).query(RowItem))

    assert asyncio.run(run()) == 2


def test_slash_filters_by_group_keeping_siblings_visible() -> None:
    async def run() -> int:
        app = DubsApp(rows(), workspace=None)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"report (1)")
            await pilot.pause()
            return len(app.query_one(ListView).query(RowItem))

    # Only A2's path contains "report (1)", but its sibling A1 stays visible
    # since the whole group is a duplicate together.
    assert asyncio.run(run()) == 2


def test_slash_hides_groups_with_no_matching_member() -> None:
    async def run() -> int:
        app = DubsApp(rows(), workspace=None)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"nonexistent")
            await pilot.pause()
            return len(app.query_one(ListView).query(RowItem))

    assert asyncio.run(run()) == 0


def test_capital_o_opens_the_highlighted_row_without_exiting() -> None:
    async def run() -> tuple[bool, int]:
        app = DubsApp(rows(), workspace=None)
        with patch("gfunk.dubs_tui.open_in_browser") as opened:
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("O")
                await pilot.pause()
                return opened.called, len(app.query_one(ListView).query(RowItem))

    opened, row_count = asyncio.run(run())
    assert opened is True
    assert row_count == 2


def test_capital_d_trashes_the_row_after_pressing_y() -> None:
    async def run() -> tuple[bool, int]:
        ws = MagicMock()
        app = DubsApp(rows(), workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("D")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            return ws.trash.called, len(app.query_one(ListView).query(RowItem))

    trashed, row_count = asyncio.run(run())
    assert trashed is True
    # The one remaining copy is no longer a duplicate, so the group vanishes.
    assert row_count == 0


def test_capital_d_cancelled_leaves_the_row() -> None:
    async def run() -> tuple[bool, int]:
        ws = MagicMock()
        app = DubsApp(rows(), workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("D")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            return ws.trash.called, len(app.query_one(ListView).query(RowItem))

    trashed, row_count = asyncio.run(run())
    assert trashed is False
    assert row_count == 2


def test_capital_k_keeps_the_row_and_trashes_the_rest_of_the_group() -> None:
    async def run() -> tuple[list[object], int]:
        ws = MagicMock()
        third = {"id": "a3", "name": "report (2).pdf", "path": "x", "size": "100"}
        big_group = flatten_groups([[A1, A2, third]], [])
        app = DubsApp(big_group, workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("K")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            trashed_ids = [call.args[0] for call in ws.trash.call_args_list]
            return trashed_ids, len(app.query_one(ListView).query(RowItem))

    trashed_ids, row_count = asyncio.run(run())
    assert set(trashed_ids) == {"a2", "a3"}
    assert row_count == 0


def test_capital_k_cancelled_trashes_nothing() -> None:
    async def run() -> bool:
        ws = MagicMock()
        app = DubsApp(rows(), workspace=ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("K")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            return bool(ws.trash.called)

    assert asyncio.run(run()) is False
