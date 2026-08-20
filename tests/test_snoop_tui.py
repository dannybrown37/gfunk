import asyncio
from unittest.mock import MagicMock

from textual.widgets import ListView, Static

from gfunk.snoop_tui import FileRowItem, SnoopApp

ROOT_FOLDER = {
    "id": "f-docs",
    "name": "Docs",
    "mimeType": "application/vnd.google-apps.folder",
    "createdTime": "2024-01-01T00:00:00.000Z",
    "modifiedTime": "2024-01-01T00:00:00.000Z",
}
ROOT_FILE = {
    "id": "file-1",
    "name": "notes.txt",
    "mimeType": "text/plain",
    "createdTime": "2024-01-02T00:00:00.000Z",
    "modifiedTime": "2024-01-02T00:00:00.000Z",
}
NESTED_FILE = {
    "id": "file-2",
    "name": "nested.txt",
    "mimeType": "text/plain",
    "createdTime": "2024-01-03T00:00:00.000Z",
    "modifiedTime": "2024-01-03T00:00:00.000Z",
}


def _workspace() -> MagicMock:
    ws = MagicMock()

    def children(folder_id: str, **_kwargs: object) -> list[dict[str, str]]:
        if folder_id == "root":
            return [ROOT_FOLDER, ROOT_FILE]
        if folder_id == "f-docs":
            return [NESTED_FILE]
        return []

    ws.children.side_effect = children
    return ws


def test_loads_root_folder_on_mount() -> None:
    async def run() -> list[str]:
        app = SnoopApp(_workspace())
        async with app.run_test() as pilot:
            await pilot.pause()
            items = app.query_one(ListView).query(FileRowItem)
            return [item.item["name"] for item in items if item.item is not None]

    assert asyncio.run(run()) == ["Docs", "notes.txt"]


def test_entering_a_folder_shows_its_children() -> None:
    async def run() -> list[str]:
        app = SnoopApp(_workspace())
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            items = app.query_one(ListView).query(FileRowItem)
            return [item.item["name"] for item in items if item.item is not None]

    assert asyncio.run(run()) == ["nested.txt"]


def test_escape_pops_back_a_level() -> None:
    async def run() -> list[str]:
        app = SnoopApp(_workspace())
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            items = app.query_one(ListView).query(FileRowItem)
            return [item.item["name"] for item in items if item.item is not None]

    assert asyncio.run(run()) == ["Docs", "notes.txt"]


def test_preview_pane_updates_on_highlight() -> None:
    async def run() -> str:
        ws = _workspace()
        app = SnoopApp(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause(0.5)
            return str(app.query_one("#preview-text", Static).content)

    text = asyncio.run(run())
    assert "notes.txt" in text
