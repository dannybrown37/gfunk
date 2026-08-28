"""Tests for _bounce_as_json."""

from __future__ import annotations

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    import pytest

from gfunk.cli import _bounce_as_json


def mock_ws() -> MagicMock:
    ws = MagicMock()
    ws.sheet_tabs.return_value = ["Data"]
    ws.sample.return_value = [{"A": 1}, {"A": 2}]
    return ws


def test_bounce_json_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    ws = mock_ws()
    rc = _bounce_as_json(ws, "s1", "Data", None)

    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert len(parsed) == 2


def test_bounce_json_to_file(tmp_path: object) -> None:
    from pathlib import Path

    out = Path(str(tmp_path)) / "out.json"
    ws = mock_ws()
    rc = _bounce_as_json(ws, "s1", "Data", out)

    assert rc == 0
    assert len(json.loads(out.read_text())) == 2


def test_bounce_json_picks_first_tab_when_none() -> None:
    ws = mock_ws()
    _bounce_as_json(ws, "s1", None, None)

    ws.sample.assert_called_once_with("s1", "Data")


def test_bounce_json_defaults_to_sheet1_when_no_tabs() -> None:
    ws = mock_ws()
    ws.sheet_tabs.return_value = []
    _bounce_as_json(ws, "s1", None, None)

    ws.sample.assert_called_once_with("s1", "Sheet1")
