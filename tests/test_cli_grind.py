import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_grind


def grind_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"days": 7, "json": False}
    return argparse.Namespace(**{**defaults, **overrides})


FAKE_EVENTS = [
    {
        "id": "e1",
        "summary": "Standup",
        "start": {"dateTime": "2026-08-24T09:00:00-05:00"},
        "location": "Zoom",
    },
]


def _mock_workspace(*, has_calendar: bool = True) -> MagicMock:
    ws = MagicMock()
    ws.calendar = MagicMock() if has_calendar else None
    ws.grind.return_value = FAKE_EVENTS
    return ws


def test_grind_shows_events_as_a_table(capsys: pytest.CaptureFixture[str]) -> None:
    ws = _mock_workspace()
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_grind(grind_args())

    assert rc == 0
    assert "Standup" in capsys.readouterr().out


def test_grind_json_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    ws = _mock_workspace()
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_grind(grind_args(json=True))

    assert rc == 0
    out = capsys.readouterr().out
    assert '"summary": "Standup"' in out


def test_grind_reports_when_no_events(capsys: pytest.CaptureFixture[str]) -> None:
    ws = _mock_workspace()
    ws.grind.return_value = []
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_grind(grind_args())

    assert rc == 0
    assert "No events" in capsys.readouterr().out


def test_grind_tells_you_to_opt_in_when_calendar_not_connected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ws = _mock_workspace(has_calendar=False)
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_grind(grind_args())

    assert rc == 1
    err = capsys.readouterr().err
    assert "--with-calendar" in err
    ws.grind.assert_not_called()
