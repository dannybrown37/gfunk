import asyncio

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
        app = RegulateApp([SHARED_FILE, OTHER_FILE])
        async with app.run_test() as pilot:
            await pilot.pause()
            list_view = app.query_one(ListView)
            headers = list_view.query(FolderHeader)
            return all(header.disabled for header in headers)

    assert asyncio.run(run()) is True


def test_slash_filters_the_visible_rows() -> None:
    async def run() -> int:
        app = RegulateApp([SHARED_FILE, OTHER_FILE])
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"reports")
            await pilot.pause()
            rows = app.query_one(ListView).query(RowItem)
            return len(rows)

    assert asyncio.run(run()) == 1


def test_escape_clears_the_filter() -> None:
    async def run() -> int:
        app = RegulateApp([SHARED_FILE, OTHER_FILE])
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"reports")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            rows = app.query_one(ListView).query(RowItem)
            return len(rows)

    assert asyncio.run(run()) == 2
