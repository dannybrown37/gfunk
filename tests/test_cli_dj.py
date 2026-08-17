import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_dj


def dj_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"page": None, "json": False}
    return argparse.Namespace(**{**defaults, **overrides})


def test_dj_no_args_opens_dashboard_and_prints_pages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("gfunk.cli.can_browse", return_value=False),
        patch("gfunk.cli.webbrowser.open") as opened,
        patch("gfunk.browser.register"),
    ):
        rc = cmd_dj(dj_args())

    assert rc == 0
    opened.assert_called_once_with("https://script.google.com/home")
    out = capsys.readouterr()
    assert "gfunk dj list" in out.out
    assert "gfunk dj runs" in out.out
    assert "gfunk dj triggers" in out.out
    assert "gfunk dj <script_id>" in out.out


def test_dj_runs_shows_executions_as_table(capsys: pytest.CaptureFixture[str]) -> None:
    ws = MagicMock()
    ws.processes.return_value = [
        {
            "projectName": "Daily Report",
            "functionName": "sendReport",
            "processStatus": "FAILED",
            "startTime": "2026-08-10T12:00:00Z",
        }
    ]
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_dj(dj_args(page="runs"))

    assert rc == 0
    assert "failed" in capsys.readouterr().out.lower()


def test_dj_runs_empty(capsys: pytest.CaptureFixture[str]) -> None:
    ws = MagicMock()
    ws.processes.return_value = []
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_dj(dj_args(page="runs"))

    assert rc == 0
    assert "no" in capsys.readouterr().out.lower()


def test_dj_triggers_opens_triggers_page(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("gfunk.cli.webbrowser.open") as opened,
        patch("gfunk.browser.register"),
    ):
        rc = cmd_dj(dj_args(page="triggers"))

    assert rc == 0
    opened.assert_called_once_with("https://script.google.com/home/triggers")
    assert "trigger" in capsys.readouterr().out.lower()


def test_dj_script_id_opens_editor(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("gfunk.cli.webbrowser.open") as opened,
        patch("gfunk.browser.register"),
    ):
        rc = cmd_dj(dj_args(page="abc123"))

    assert rc == 0
    opened.assert_called_once_with("https://script.google.com/d/abc123/edit")
    assert "abc123" in capsys.readouterr().out


def test_dj_fzf_picker_recent_runs_shows_table(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ws = MagicMock()
    ws.processes.return_value = []
    with (
        patch("gfunk.cli.can_browse", return_value=True),
        patch(
            "gfunk.cli.fzf_pick",
            return_value="Recent Runs          What ran, what failed, and when",
        ),
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
    ):
        rc = cmd_dj(dj_args())

    assert rc == 0
    assert "no" in capsys.readouterr().out.lower()


def test_dj_fzf_picker_escape_does_nothing() -> None:
    with (
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", return_value=None),
        patch("gfunk.cli.webbrowser.open") as opened,
    ):
        rc = cmd_dj(dj_args())

    assert rc == 0
    opened.assert_not_called()


def test_dj_fzf_picker_my_projects_opens_home() -> None:
    with (
        patch("gfunk.cli.can_browse", return_value=True),
        patch(
            "gfunk.cli.fzf_pick",
            return_value="My Projects          All your Apps Script projects (browser)",
        ),
        patch("gfunk.cli.webbrowser.open") as opened,
        patch("gfunk.browser.register"),
    ):
        rc = cmd_dj(dj_args())

    assert rc == 0
    opened.assert_called_once_with("https://script.google.com/home")
