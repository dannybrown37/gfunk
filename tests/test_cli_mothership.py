"""Tests for cmd_mothership, _mothership_install, _mothership_serve."""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest

from gfunk.cli import _mothership_install, _mothership_serve, cmd_mothership


def mothership_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "mothership_command": None,
        "tools": None,
    }
    return argparse.Namespace(**{**defaults, **overrides})


def test_cmd_mothership_no_subcommand_prints_help() -> None:
    with pytest.raises(SystemExit):
        cmd_mothership(mothership_args())


def test_cmd_mothership_install_delegates() -> None:
    args = mothership_args(
        mothership_command="install",
        uninstall=False,
        client="all",
        global_scope=False,
    )
    with patch("gfunk.cli._mothership_install", return_value=0) as mock:
        rc = cmd_mothership(args)

    assert rc == 0
    mock.assert_called_once_with(args)


def test_cmd_mothership_serve_delegates() -> None:
    with patch("gfunk.cli._mothership_serve", return_value=0) as mock:
        rc = cmd_mothership(
            mothership_args(mothership_command="serve", tools="tool1,tool2")
        )

    assert rc == 0
    mock.assert_called_once_with(tools={"tool1", "tool2"})


def test_mothership_install_installs(capsys: pytest.CaptureFixture[str]) -> None:
    from pathlib import Path

    args = argparse.Namespace(
        uninstall=False,
        client="all",
        global_scope=False,
        tools=None,
    )
    with patch("gfunk.mcp_config.install", return_value=[Path("/foo/config.json")]):
        rc = _mothership_install(args)

    assert rc == 0
    assert "Installed to" in capsys.readouterr().out


def test_mothership_install_uninstalls(capsys: pytest.CaptureFixture[str]) -> None:
    from pathlib import Path

    args = argparse.Namespace(
        uninstall=True,
        client="all",
        global_scope=False,
        tools=None,
    )
    with patch("gfunk.mcp_config.uninstall", return_value=[Path("/foo/config.json")]):
        rc = _mothership_install(args)

    assert rc == 0
    assert "Removed from" in capsys.readouterr().out


def test_mothership_install_nothing_to_do(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        uninstall=True,
        client="all",
        global_scope=False,
        tools=None,
    )
    with patch("gfunk.mcp_config.uninstall", return_value=[]):
        rc = _mothership_install(args)

    assert rc == 0
    assert "Nothing to do" in capsys.readouterr().out


def test_mothership_serve_refuses_tty() -> None:
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        rc = _mothership_serve()

    assert rc == 1


def test_mothership_serve_runs_on_pipe() -> None:
    with (
        patch("sys.stdin") as mock_stdin,
        patch("gfunk.mothership.run") as mock_run,
    ):
        mock_stdin.isatty.return_value = False
        rc = _mothership_serve(tools={"a"})

    assert rc == 0
    mock_run.assert_called_once_with(tools={"a"})
