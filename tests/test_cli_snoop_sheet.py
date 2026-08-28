"""Tests for _snoop_sheet — the sheet-viewing branch of snoop."""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    import pytest

from gfunk.cli import _snoop_sheet


def sheet_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "cell_range": None,
        "limit": 200,
        "json": False,
        "raw": False,
        "output": None,
    }
    return argparse.Namespace(**{**defaults, **overrides})


def mock_ws() -> MagicMock:
    ws = MagicMock()
    ws.sample.return_value = [{"Name": "Ada", "Score": 100}]
    ws.sheet_tabs.return_value = ["Sheet1"]
    return ws


def test_snoop_sheet_json_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    ws = mock_ws()
    with patch("gfunk.cli.pick_range", return_value="Sheet1"):
        rc = _snoop_sheet(sheet_args(json=True), ws, "s1", "Budget")

    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed[0]["Name"] == "Ada"


def test_snoop_sheet_json_to_file(
    tmp_path: object, capsys: pytest.CaptureFixture[str]
) -> None:
    from pathlib import Path

    out = Path(str(tmp_path)) / "out.json"
    ws = mock_ws()
    with patch("gfunk.cli.pick_range", return_value="Sheet1"):
        rc = _snoop_sheet(sheet_args(json=True, output=out), ws, "s1", "Budget")

    assert rc == 0
    assert json.loads(out.read_text())[0]["Name"] == "Ada"
    assert "Wrote" in capsys.readouterr().err


def test_snoop_sheet_table_to_file(tmp_path: object) -> None:
    from pathlib import Path

    out = Path(str(tmp_path)) / "out.txt"
    ws = mock_ws()
    with patch("gfunk.cli.pick_range", return_value="Sheet1"):
        rc = _snoop_sheet(sheet_args(output=out), ws, "s1", "Budget")

    assert rc == 0
    assert "Ada" in out.read_text()


def test_snoop_sheet_raw_emits_table(capsys: pytest.CaptureFixture[str]) -> None:
    ws = mock_ws()
    with patch("gfunk.cli.pick_range", return_value="Sheet1"):
        rc = _snoop_sheet(sheet_args(raw=True), ws, "s1", "Budget")

    assert rc == 0
    assert "Ada" in capsys.readouterr().out


def test_snoop_sheet_explicit_range_skips_picker() -> None:
    ws = mock_ws()
    with patch("gfunk.cli.pick_range") as pick:
        _snoop_sheet(sheet_args(cell_range="A1:B5", raw=True), ws, "s1", "Budget")

    pick.assert_not_called()
    ws.sample.assert_called_once_with("s1", "A1:B5", limit=200)


def test_snoop_sheet_prompts_when_no_range_and_no_picker() -> None:
    ws = mock_ws()
    with (
        patch("gfunk.cli.pick_range", return_value=None),
        patch("gfunk.cli.prompt_required", return_value="MyTab"),
    ):
        _snoop_sheet(sheet_args(raw=True), ws, "s1", "Budget")

    ws.sample.assert_called_once_with("s1", "MyTab", limit=200)
