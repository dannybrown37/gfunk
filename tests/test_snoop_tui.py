import asyncio
from unittest.mock import MagicMock, patch

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


def test_view_mode_recent_shows_recent_files() -> None:
    async def run() -> str:
        ws = _workspace()
        ws.recent.return_value = [ROOT_FILE]
        app = SnoopApp(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("2")
            await pilot.pause()
            return str(app.sub_title)

    assert asyncio.run(run()) == "Recent files"


def test_view_mode_largest_shows_largest_files() -> None:
    async def run() -> str:
        ws = _workspace()
        ws.largest.return_value = [ROOT_FILE]
        app = SnoopApp(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            return str(app.sub_title)

    assert asyncio.run(run()) == "Largest files"


def test_view_mode_home_restores_path() -> None:
    async def run() -> str:
        ws = _workspace()
        ws.recent.return_value = [ROOT_FILE]
        app = SnoopApp(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("2")
            await pilot.pause()
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            await pilot.pause()
            return str(app.sub_title)

    assert asyncio.run(run()) == "My Drive"


def test_tab_toggles_preview_focus() -> None:
    async def run() -> bool:
        from textual.containers import VerticalScroll

        app = SnoopApp(_workspace())
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            return app.query_one("#preview", VerticalScroll).has_focus

    assert asyncio.run(run()) is True


def test_css_class_for_mime_known() -> None:
    from gfunk.snoop_tui import _css_class_for_mime

    assert _css_class_for_mime("application/vnd.google-apps.folder") == "mime-folder"
    assert _css_class_for_mime("application/vnd.google-apps.document") == "mime-doc"


def test_css_class_for_mime_prefix() -> None:
    from gfunk.snoop_tui import _css_class_for_mime

    assert _css_class_for_mime("image/png") == "mime-image"
    assert _css_class_for_mime("video/mp4") == "mime-video"


def test_css_class_for_mime_unknown() -> None:
    from gfunk.snoop_tui import _css_class_for_mime

    assert _css_class_for_mime("application/octet-stream") is None


def test_natural_sort_key_numeric_first() -> None:
    from gfunk.snoop_tui import _natural_sort_key

    assert _natural_sort_key("10 report")[0] == 0
    assert _natural_sort_key("report")[0] == 1


def test_build_legend_has_all_types() -> None:
    from gfunk.snoop_tui import _build_legend

    legend = _build_legend()
    assert "folder" in legend
    assert "sheet" in legend
    assert "pdf" in legend


def test_action_menu_screen_composes() -> None:
    from textual.app import App as BaseApp

    from gfunk.snoop_tui import ActionMenuScreen

    async def run() -> int:
        screen = ActionMenuScreen("test.txt", ["Open", "Delete"])
        app: BaseApp[None] = BaseApp()
        async with app.run_test() as pilot:
            app.push_screen(screen)
            await pilot.pause()
            items = screen.query_one(ListView).query(FileRowItem)
            return len(items)

    assert asyncio.run(run()) == 2


def test_confirm_trash_screen_composes() -> None:
    from textual.app import App as BaseApp

    from gfunk.snoop_tui import ConfirmTrashScreen

    async def run() -> str:
        screen = ConfirmTrashScreen("report.pdf")
        app: BaseApp[None] = BaseApp()
        async with app.run_test() as pilot:
            app.push_screen(screen)
            await pilot.pause()
            return str(screen.query_one(Static).content)

    text = asyncio.run(run())
    assert "report.pdf" in text


SHEET_FILE = {
    "id": "sheet-1",
    "name": "Budget",
    "mimeType": "application/vnd.google-apps.spreadsheet",
    "createdTime": "2024-01-01T00:00:00.000Z",
    "modifiedTime": "2024-01-01T00:00:00.000Z",
}
DOC_FILE = {
    "id": "doc-1",
    "name": "Notes",
    "mimeType": "application/vnd.google-apps.document",
    "createdTime": "2024-01-01T00:00:00.000Z",
    "modifiedTime": "2024-01-01T00:00:00.000Z",
}


def _ws_with_files() -> MagicMock:
    ws = MagicMock()
    ws.children.return_value = [SHEET_FILE, DOC_FILE, ROOT_FILE]
    ws.export.return_value = b"Hello doc content"
    ws.sheet_tabs.return_value = ["Sheet1"]
    ws.sample.return_value = [{"A": 1}]
    ws.folder_names.return_value = {"root": "My Drive"}
    return ws


def test_file_action_menu_opens_on_enter() -> None:
    from gfunk.snoop_tui import ActionMenuScreen

    async def run() -> bool:
        ws = _ws_with_files()
        app = SnoopApp(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            return any(isinstance(s, ActionMenuScreen) for s in app._screen_stack)

    assert asyncio.run(run()) is True


def test_open_in_browser_action() -> None:
    async def run() -> bool:
        ws = _ws_with_files()
        app = SnoopApp(ws)
        with patch("gfunk.snoop_tui.open_in_browser") as mock_open:
            async with app.run_test() as pilot:
                await pilot.pause()
                # navigate to first file (SHEET_FILE)
                await pilot.press("enter")
                await pilot.pause()
                # "View (Vibe TUI)" is first for sheets, "Open in browser" is second
                await pilot.press("j")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                return mock_open.called

    assert asyncio.run(run()) is True


def test_action_menu_escape_cancels() -> None:
    from gfunk.snoop_tui import ActionMenuScreen

    async def run() -> bool:
        ws = _ws_with_files()
        app = SnoopApp(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            return not any(isinstance(s, ActionMenuScreen) for s in app._screen_stack)

    assert asyncio.run(run()) is True


def test_j_k_scroll_in_preview_mode() -> None:
    async def run() -> bool:
        from textual.containers import VerticalScroll

        app = SnoopApp(_workspace())
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            await pilot.press("j")
            await pilot.pause()
            return app.query_one("#preview", VerticalScroll).has_focus

    assert asyncio.run(run()) is True


def test_tab_back_to_list() -> None:
    async def run() -> bool:
        app = SnoopApp(_workspace())
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            return app.query_one(ListView).has_focus

    assert asyncio.run(run()) is True


def test_folder_pick_screen_select_here() -> None:
    from gfunk.snoop_tui import FolderPickScreen

    async def run() -> str | None:
        from textual.app import App as BaseApp

        ws = MagicMock()
        ws.children.return_value = []
        result: list[str | None] = []

        app: BaseApp[None] = BaseApp()
        async with app.run_test() as pilot:
            screen = FolderPickScreen(ws, start="root")
            app.push_screen(screen, result.append)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            return result[0] if result else None

    assert asyncio.run(run()) == "root"


def test_folder_pick_screen_escape_cancels() -> None:
    from gfunk.snoop_tui import FolderPickScreen

    async def run() -> str | None:
        from textual.app import App as BaseApp

        ws = MagicMock()
        ws.children.return_value = []
        result: list[str | None] = [None]

        app: BaseApp[None] = BaseApp()
        async with app.run_test() as pilot:
            screen = FolderPickScreen(ws, start="root")
            app.push_screen(screen, result.append)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            return result[-1]

    assert asyncio.run(run()) is None


def test_confirm_trash_y_returns_true() -> None:
    from gfunk.snoop_tui import ConfirmTrashScreen

    async def run() -> bool | None:
        from textual.app import App as BaseApp

        result: list[bool | None] = []
        app: BaseApp[None] = BaseApp()
        async with app.run_test() as pilot:
            screen = ConfirmTrashScreen("test.txt")
            app.push_screen(screen, result.append)
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            return result[0] if result else None

    assert asyncio.run(run()) is True


def test_confirm_trash_n_returns_false() -> None:
    from gfunk.snoop_tui import ConfirmTrashScreen

    async def run() -> bool | None:
        from textual.app import App as BaseApp

        result: list[bool | None] = []
        app: BaseApp[None] = BaseApp()
        async with app.run_test() as pilot:
            screen = ConfirmTrashScreen("test.txt")
            app.push_screen(screen, result.append)
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            return result[0] if result else None

    assert asyncio.run(run()) is False


def test_escape_at_root_quits() -> None:
    async def run() -> bool:
        app = SnoopApp(_workspace())
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            return app.is_running

    assert asyncio.run(run()) is False
