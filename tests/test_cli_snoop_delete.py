from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import _snoop_delete

FILE = {"id": "f1", "name": "Budget"}


def test_snoop_delete_trashes_on_y_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = MagicMock()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    with patch("gfunk.cli._read_single_key", return_value="y"):
        assert _snoop_delete(workspace, FILE) == 0

    workspace.trash.assert_called_once_with("f1")


def test_snoop_delete_aborts_on_anything_else(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = MagicMock()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    with patch("gfunk.cli._read_single_key", return_value="n"):
        assert _snoop_delete(workspace, FILE) == 0

    workspace.trash.assert_not_called()


def test_snoop_delete_refuses_off_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = MagicMock()
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    with pytest.raises(SystemExit):
        _snoop_delete(workspace, FILE)

    workspace.trash.assert_not_called()


def test_snoop_delete_prints_confirmation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = MagicMock()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    with patch("gfunk.cli._read_single_key", return_value="y"):
        _snoop_delete(workspace, FILE)

    assert "Trashed Budget" in capsys.readouterr().err
