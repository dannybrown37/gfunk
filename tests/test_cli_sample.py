import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_vibe, pick_spreadsheet, pick_range


def sample_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "spreadsheet_id": None,
        "cell_range": None,
        "limit": None,
        "json": False,
        "raw": True,
    }
    return argparse.Namespace(**{**defaults, **overrides})


SHEET = {"id": "s1", "name": "Budget"}


def test_sample_with_args_skips_pickers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.sample.return_value = [{"A": "1"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_vibe(sample_args(spreadsheet_id="s1", cell_range="Sheet1")) == 0

    workspace.sample.assert_called_once_with("s1", "Sheet1", limit=None)
    assert "A" in capsys.readouterr().out


def test_sample_json_flag(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.sample.return_value = [{"A": "1"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert (
            cmd_vibe(sample_args(spreadsheet_id="s1", cell_range="Sheet1", json=True))
            == 0
        )

    assert '"A": "1"' in capsys.readouterr().out


def test_pick_spreadsheet_uses_fzf() -> None:
    workspace = MagicMock()
    workspace.spreadsheets.return_value = [SHEET]

    with (
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", return_value="Budget\ts1") as fzf,
    ):
        result = pick_spreadsheet(workspace)

    assert result == "s1"
    fzf.assert_called_once()


def test_pick_spreadsheet_returns_none_without_fzf() -> None:
    workspace = MagicMock()
    with patch("gfunk.cli.can_browse", return_value=False):
        assert pick_spreadsheet(workspace) is None


def test_pick_range_returns_single_tab_without_prompting() -> None:
    workspace = MagicMock()
    workspace.sheet_tabs.return_value = ["Sheet1"]

    with patch("gfunk.cli.can_browse", return_value=True):
        assert pick_range(workspace, "s1") == "Sheet1"


def test_pick_range_offers_fzf_for_multiple_tabs() -> None:
    workspace = MagicMock()
    workspace.sheet_tabs.return_value = ["Sheet1", "Sheet2"]

    with (
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", return_value="Sheet2"),
    ):
        assert pick_range(workspace, "s1") == "Sheet2"


def test_sample_echoes_replayable_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.sample.return_value = []

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_vibe(sample_args(spreadsheet_id="s1", cell_range="A1:B2"))

    assert "gfunk vibe" in capsys.readouterr().err
