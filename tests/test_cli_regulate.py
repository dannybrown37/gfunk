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


def test_escaping_the_picker_prints_nothing_extra(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ws = mock_workspace([SHARED_FILE])

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.regulate_tui.RegulateApp.run", return_value=None),
    ):
        cmd_regulate(regulate_args())

    assert "isn't wired up" not in capsys.readouterr().err


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


def test_unimplemented_actions_say_so(
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
    assert "Move" in err
    assert "isn't wired up" in err


def test_regulate_app_gets_the_workspace() -> None:
    ws = mock_workspace([SHARED_FILE])

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.regulate_tui.RegulateApp") as app_cls,
    ):
        app_cls.return_value.run.return_value = None
        cmd_regulate(regulate_args())

    assert app_cls.call_args[0][1] is ws
