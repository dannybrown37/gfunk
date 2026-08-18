import asyncio

import pytest
from textual.widgets import ListView

from gfunk.regulate_tui import RegulateApp, matches_filter

SHARED_FILE = {
    "id": "a",
    "name": "Q3 Numbers",
    "path": "Reports/Q3 Numbers",
    "exposure": "public",
    "reached_by": ["anyone with the link"],
    "link": "https://example.com/a",
}
OTHER_FILE = {
    "id": "b",
    "name": "Roadmap",
    "path": "Planning/Roadmap",
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


def test_slash_filters_the_visible_rows() -> None:
    async def run() -> int:
        app = RegulateApp([SHARED_FILE, OTHER_FILE])
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"reports")
            await pilot.pause()
            return len(app.query_one(ListView))

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
            return len(app.query_one(ListView))

    assert asyncio.run(run()) == 2
