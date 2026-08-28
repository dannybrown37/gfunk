import asyncio

from textual.widgets import DataTable, Input

from gfunk.vibe import VibeApp

ROWS: list[dict[str, str]] = [
    {"Name": "Alice", "Score": "95"},
    {"Name": "Bob", "Score": "82"},
    {"Name": "Charlie", "Score": "91"},
]


def test_mount_with_rows() -> None:
    async def run() -> int:
        app = VibeApp(rows=ROWS, title="Test")
        async with app.run_test():
            return app.query_one(DataTable).row_count

    assert asyncio.run(run()) == 3


def test_mount_empty() -> None:
    async def run() -> int:
        app = VibeApp(rows=[], title="Empty")
        async with app.run_test():
            return app.query_one(DataTable).row_count

    assert asyncio.run(run()) == 0


def test_vim_navigation() -> None:
    async def run() -> None:
        app = VibeApp(rows=ROWS)
        async with app.run_test() as pilot:
            await pilot.press("j")
            await pilot.press("k")
            await pilot.press("l")
            await pilot.press("h")
            await pilot.press("g")
            await pilot.press("G")

    asyncio.run(run())


def test_search_filters_rows() -> None:
    async def run() -> int:
        app = VibeApp(rows=ROWS)
        async with app.run_test() as pilot:
            await pilot.press("slash")
            app.query_one("#search", Input).value = "alice"
            await pilot.pause()
            return app.query_one(DataTable).row_count

    assert asyncio.run(run()) == 1


def test_escape_clears_search() -> None:
    async def run() -> tuple[int, bool]:
        app = VibeApp(rows=ROWS)
        async with app.run_test() as pilot:
            await pilot.press("slash")
            app.query_one("#search", Input).value = "alice"
            await pilot.pause()
            await pilot.press("escape")
            search = app.query_one("#search", Input)
            table = app.query_one(DataTable)
            return table.row_count, "visible" not in search.classes

    count, cleared = asyncio.run(run())
    assert count == 3
    assert cleared


def test_search_no_match() -> None:
    async def run() -> int:
        app = VibeApp(rows=ROWS)
        async with app.run_test() as pilot:
            await pilot.press("slash")
            app.query_one("#search", Input).value = "zzzzz"
            await pilot.pause()
            return app.query_one(DataTable).row_count

    assert asyncio.run(run()) == 0


def test_search_submit_refocuses_table() -> None:
    async def run() -> bool:
        app = VibeApp(rows=ROWS)
        async with app.run_test() as pilot:
            await pilot.press("slash")
            await pilot.press("enter")
            return app.query_one(DataTable).has_focus

    assert asyncio.run(run())


def test_empty_search_restores_all() -> None:
    async def run() -> int:
        app = VibeApp(rows=ROWS)
        async with app.run_test() as pilot:
            await pilot.press("slash")
            search = app.query_one("#search", Input)
            search.value = "alice"
            await pilot.pause()
            search.value = ""
            await pilot.pause()
            return app.query_one(DataTable).row_count

    assert asyncio.run(run()) == 3
