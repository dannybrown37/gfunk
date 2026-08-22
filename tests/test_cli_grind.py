import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_grind


def grind_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"days": 7, "json": False, "since": 0}
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


def test_grind_launches_tui() -> None:
    ws = _mock_workspace()
    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("gfunk.grind_tui.GrindApp") as mock_app_cls,
    ):
        rc = cmd_grind(grind_args())

    assert rc == 0
    mock_app_cls.return_value.run.assert_called_once()


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


def test_grind_passes_since_through_to_workspace() -> None:
    ws = _mock_workspace()
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        cmd_grind(grind_args(json=True, since=7))

    ws.grind.assert_called_once_with(days=7, since_days=7)


def test_grind_replay_line_echoes_since(capsys: pytest.CaptureFixture[str]) -> None:
    ws = _mock_workspace()
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        cmd_grind(grind_args(json=True, since=3))

    assert "--since 3" in capsys.readouterr().err
