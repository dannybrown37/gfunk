import argparse
from unittest.mock import patch

import pytest

from gfunk.cli import cmd_dj


def dj_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"page": None}
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
    assert "gfunk dj runs" in out.out
    assert "gfunk dj triggers" in out.out
    assert "gfunk dj <script_id>" in out.out


def test_dj_runs_opens_executions_page(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("gfunk.cli.webbrowser.open") as opened,
        patch("gfunk.browser.register"),
    ):
        rc = cmd_dj(dj_args(page="runs"))

    assert rc == 0
    opened.assert_called_once_with("https://script.google.com/home/executions")
    assert "failed" in capsys.readouterr().out.lower()


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


def test_dj_fzf_picker_opens_selected_page() -> None:
    with (
        patch("gfunk.cli.can_browse", return_value=True),
        patch(
            "gfunk.cli.fzf_pick",
            return_value="Recent Runs          What ran, what failed, and when",
        ),
        patch("gfunk.cli.webbrowser.open") as opened,
        patch("gfunk.browser.register"),
    ):
        rc = cmd_dj(dj_args())

    assert rc == 0
    opened.assert_called_once_with("https://script.google.com/home/executions")


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
            return_value="My Projects          All your Apps Script projects",
        ),
        patch("gfunk.cli.webbrowser.open") as opened,
        patch("gfunk.browser.register"),
    ):
        rc = cmd_dj(dj_args())

    assert rc == 0
    opened.assert_called_once_with("https://script.google.com/home")
