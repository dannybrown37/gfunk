import argparse
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_regulate


OWNER = "danny@example.com"
SHARED_FILE = {
    "id": "a",
    "name": "Q3 Numbers",
    "webViewLink": "https://x/a",
    "parents": ["folder1"],
    "owners": [{"emailAddress": OWNER}],
    "permissions": [
        {"type": "user", "role": "owner", "emailAddress": OWNER},
        {"type": "anyone", "role": "reader"},
    ],
}
PRIVATE_FILE = {
    "id": "b",
    "name": "Notes",
    "webViewLink": "https://x/b",
    "parents": ["folder1"],
    "owners": [{"emailAddress": OWNER}],
    "permissions": [{"type": "user", "role": "owner", "emailAddress": OWNER}],
}


def regulate_args(**overrides: object) -> argparse.Namespace:
    defaults = {"limit": 200, "all": False, "json": False}
    return argparse.Namespace(**{**defaults, **overrides})


def mock_workspace(files: list[dict[str, Any]]) -> MagicMock:
    ws = MagicMock()
    ws.sharing.return_value = files
    ws.folder_names.return_value = {"folder1": "Reports"}
    return ws


def test_picking_a_row_and_choosing_open_opens_it_in_a_browser() -> None:
    ws = mock_workspace([SHARED_FILE])

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.regulate_tui.RegulateApp.run") as run,
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        run.return_value = ({"id": "a", "name": "Q3 Numbers"}, "Open in browser")
        cmd_regulate(regulate_args())

    opened.assert_called_once()
    assert opened.call_args[0][0]["id"] == "a"


def test_escaping_the_picker_skips_any_action() -> None:
    ws = mock_workspace([SHARED_FILE])

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.regulate_tui.RegulateApp.run", return_value=None),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        cmd_regulate(regulate_args())

    opened.assert_not_called()


def test_no_tty_skips_the_picker_entirely(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ws = mock_workspace([SHARED_FILE])

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("sys.stdin.isatty", return_value=False),
    ):
        assert cmd_regulate(regulate_args()) == 0

    out = capsys.readouterr()
    assert "Q3 Numbers" in out.out


def test_write_actions_explain_they_need_write_scopes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ws = mock_workspace([SHARED_FILE])

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.regulate_tui.RegulateApp.run") as run,
    ):
        run.return_value = ({"id": "a", "name": "Q3 Numbers"}, "Move")
        cmd_regulate(regulate_args())

    err = capsys.readouterr().err
    assert "write" in err.lower() or "scope" in err.lower()
