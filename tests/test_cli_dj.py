import argparse
import pathlib
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_dj


def dj_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "page": None,
        "json": False,
        "script_id": None,
        "directory": None,
        "out": None,
        "yes": False,
    }
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


def test_dj_pull_writes_source_files(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ws = MagicMock()
    ws.script_content.return_value = [
        {"name": "Code", "type": "SERVER_JS", "source": "function main() {}"}
    ]
    out_dir = tmp_path / "pulled"
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_dj(dj_args(page="pull", script_id="abc123", out=out_dir))

    assert rc == 0
    ws.script_content.assert_called_once_with("abc123")
    assert (out_dir / "Code.gs").read_text() == "function main() {}"
    assert "Code.gs" in capsys.readouterr().out


def test_dj_pull_missing_script_id_errors(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cmd_dj(dj_args(page="pull"))

    assert rc == 1
    assert "script_id" in capsys.readouterr().err


def test_dj_push_writes_to_script_after_confirmation(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "Code.gs").write_text("function main() {}")
    ws = MagicMock()
    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("gfunk.cli.prompt", return_value="push"),
    ):
        rc = cmd_dj(dj_args(page="push", script_id="abc123", directory=tmp_path))

    assert rc == 0
    ws.update_script_content.assert_called_once_with(
        "abc123",
        [{"name": "Code", "type": "SERVER_JS", "source": "function main() {}"}],
    )
    assert "Pushed" in capsys.readouterr().out


def test_dj_push_aborts_when_not_confirmed(tmp_path: pathlib.Path) -> None:
    (tmp_path / "Code.gs").write_text("1;")
    ws = MagicMock()
    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("gfunk.cli.prompt", return_value="no"),
    ):
        rc = cmd_dj(dj_args(page="push", script_id="abc123", directory=tmp_path))

    assert rc == 0
    ws.update_script_content.assert_not_called()


def test_dj_push_yes_skips_confirmation(tmp_path: pathlib.Path) -> None:
    (tmp_path / "Code.gs").write_text("1;")
    ws = MagicMock()
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_dj(
            dj_args(page="push", script_id="abc123", directory=tmp_path, yes=True)
        )

    assert rc == 0
    ws.update_script_content.assert_called_once()


def test_dj_push_missing_directory_errors(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cmd_dj(dj_args(page="push", script_id="abc123"))

    assert rc == 1
    assert "directory" in capsys.readouterr().err


def test_dj_push_nonexistent_directory_errors(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cmd_dj(
        dj_args(page="push", script_id="abc123", directory=tmp_path / "missing")
    )

    assert rc == 1
    assert "not found" in capsys.readouterr().err.lower()


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
