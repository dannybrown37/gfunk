import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import COMMANDS, cmd_snoop
from gfunk.workspace import SHEET_MIME


def snoop_sheet_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "target": None,
        "cell_range": None,
        "fmt": None,
        "json": False,
        "limit": None,
        "output": None,
        "open": False,
        "raw": False,
    }
    return argparse.Namespace(**{**defaults, **overrides})


SHEET_FILE = {
    "id": "s1",
    "name": "Budget",
    "mimeType": SHEET_MIME,
    "webViewLink": "https://docs.google.com/spreadsheets/d/s1",
}


def test_snoop_sheet_raw_prints_tabulate_table(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"Name": "Alice", "Score": "95"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
    ):
        assert cmd_snoop(snoop_sheet_args(target="s1", raw=True)) == 0

    out = capsys.readouterr().out
    assert "Name" in out
    assert "Alice" in out


def test_snoop_sheet_json_flag(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"A": "1"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
    ):
        assert cmd_snoop(snoop_sheet_args(target="s1", json=True)) == 0

    assert '"A": "1"' in capsys.readouterr().out


def test_snoop_sheet_echoes_replayable_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = []

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_range", return_value="A1:B2"),
    ):
        cmd_snoop(snoop_sheet_args(target="s1", raw=True))

    assert "gfunk snoop" in capsys.readouterr().err


def test_snoop_sheet_with_limit() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"A": "1"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
    ):
        cmd_snoop(snoop_sheet_args(target="s1", limit=5, raw=True))

    workspace.sample.assert_called_once_with("s1", "Sheet1", limit=5)


def test_snoop_sheet_no_tty_falls_back_to_raw(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"X": "1"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
        patch("sys.stdin") as mock_stdin,
    ):
        mock_stdin.isatty.return_value = False
        assert cmd_snoop(snoop_sheet_args(target="s1")) == 0

    assert "X" in capsys.readouterr().out


def test_browse_alias_still_works() -> None:
    assert COMMANDS["browse"] is cmd_snoop
