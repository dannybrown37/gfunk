import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_vibe


def vibe_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "spreadsheet_id": None,
        "cell_range": None,
        "limit": None,
        "json": False,
        "raw": False,
    }
    return argparse.Namespace(**{**defaults, **overrides})


def test_vibe_raw_prints_tabulate_table(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.sample.return_value = [{"Name": "Alice", "Score": "95"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert (
            cmd_vibe(vibe_args(spreadsheet_id="s1", cell_range="Sheet1", raw=True)) == 0
        )

    out = capsys.readouterr().out
    assert "Name" in out
    assert "Alice" in out


def test_vibe_json_flag(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.sample.return_value = [{"A": "1"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert (
            cmd_vibe(vibe_args(spreadsheet_id="s1", cell_range="Sheet1", json=True))
            == 0
        )

    assert '"A": "1"' in capsys.readouterr().out


def test_vibe_echoes_replayable_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.sample.return_value = []

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_vibe(vibe_args(spreadsheet_id="s1", cell_range="A1:B2", raw=True))

    assert "gfunk vibe" in capsys.readouterr().err


def test_vibe_with_limit() -> None:
    workspace = MagicMock()
    workspace.sample.return_value = [{"A": "1"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_vibe(vibe_args(spreadsheet_id="s1", cell_range="Sheet1", limit=5, raw=True))

    workspace.sample.assert_called_once_with("s1", "Sheet1", limit=5)


def test_vibe_no_tty_falls_back_to_raw(capsys: pytest.CaptureFixture[str]) -> None:
    """When not a TTY and no --raw/--json, vibe should fall back to raw table output."""
    workspace = MagicMock()
    workspace.sample.return_value = [{"X": "1"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("sys.stdin") as mock_stdin,
    ):
        mock_stdin.isatty.return_value = False
        assert cmd_vibe(vibe_args(spreadsheet_id="s1", cell_range="Sheet1")) == 0

    assert "X" in capsys.readouterr().out


def test_sheet_alias_still_works() -> None:
    from gfunk.cli import COMMANDS

    assert COMMANDS["sheet"] is cmd_vibe
