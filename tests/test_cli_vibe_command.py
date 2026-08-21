import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import COMMANDS, cmd_vibe
from gfunk.workspace import SHEET_MIME


def vibe_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "target": None,
        "cell_range": None,
        "json": False,
        "limit": None,
        "output": None,
        "raw": False,
    }
    return argparse.Namespace(**{**defaults, **overrides})


SHEET_FILE = {
    "id": "s1",
    "name": "Budget",
    "mimeType": SHEET_MIME,
}


def test_vibe_with_target_skips_picker() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"A": "1"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_spreadsheet") as mock_pick,
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
    ):
        assert cmd_vibe(vibe_args(target="s1", raw=True)) == 0

    mock_pick.assert_not_called()


def test_vibe_bare_call_uses_spreadsheet_picker(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"A": "1"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_spreadsheet", return_value="s1") as mock_pick,
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
    ):
        assert cmd_vibe(vibe_args(raw=True)) == 0

    mock_pick.assert_called_once_with(workspace)
    assert "A" in capsys.readouterr().out


def test_vibe_bare_call_aborted_picker_returns_zero() -> None:
    workspace = MagicMock()

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_spreadsheet", return_value=None),
    ):
        assert cmd_vibe(vibe_args()) == 0

    workspace.file_meta.assert_not_called()


def test_vibe_and_sheet_alias_registered() -> None:
    assert COMMANDS["vibe"] is cmd_vibe
    assert COMMANDS["sheet"] is cmd_vibe
