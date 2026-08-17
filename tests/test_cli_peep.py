import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_peep
from gfunk.workspace import DOC_MIME, FOLDER_MIME, SHEET_MIME


def peep_args(**overrides: object) -> argparse.Namespace:
    defaults = {
        "file_id": None,
        "cell_range": None,
        "fmt": None,
        "json": False,
        "limit": None,
        "output": None,
    }
    return argparse.Namespace(**{**defaults, **overrides})


DOC_FILE = {
    "id": "d1",
    "name": "Proposal",
    "mimeType": DOC_MIME,
    "webViewLink": "https://docs.google.com/document/d/d1",
}

SHEET_FILE = {
    "id": "s1",
    "name": "Budget",
    "mimeType": SHEET_MIME,
    "webViewLink": "https://docs.google.com/spreadsheets/d/s1",
}

FOLDER_FILE = {
    "id": "f1",
    "name": "My Folder",
    "mimeType": FOLDER_MIME,
}


# --- Docs ---


def test_peep_doc_txt(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"Hello world"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_peep(peep_args(file_id="d1")) == 0

    workspace.export.assert_called_once_with("d1", "text/plain")
    assert "Hello world" in capsys.readouterr().out


def test_peep_doc_html(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"<html><body>Hello</body></html>"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_peep(peep_args(file_id="d1", fmt="html")) == 0

    workspace.export.assert_called_once_with("d1", "text/html")
    assert "<html>" in capsys.readouterr().out


def test_peep_doc_to_file(tmp_path: Path) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"Hello world"
    out = tmp_path / "doc.txt"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_peep(peep_args(file_id="d1", output=out)) == 0

    assert out.read_text() == "Hello world"


# --- Sheets ---


def test_peep_sheet_table(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sheet_tabs.return_value = ["Sheet1"]
    workspace.sample.return_value = [{"Name": "Alice", "Value": "42"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
    ):
        assert cmd_peep(peep_args(file_id="s1")) == 0

    out = capsys.readouterr().out
    assert "Alice" in out


def test_peep_sheet_json(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"Name": "Alice", "Value": "42"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
    ):
        assert cmd_peep(peep_args(file_id="s1", json=True)) == 0

    out = capsys.readouterr().out
    assert '"Name": "Alice"' in out


def test_peep_sheet_with_range() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"A": "1"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_peep(peep_args(file_id="s1", cell_range="Sheet1!A1:B5")) == 0

    workspace.sample.assert_called_once_with("s1", "Sheet1!A1:B5", limit=None)


# --- Rejection ---


def test_peep_rejects_non_doc_non_sheet() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = FOLDER_FILE

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_peep(peep_args(file_id="f1")) == 1


# --- Replay ---


def test_peep_doc_echoes_replay(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"text"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_peep(peep_args(file_id="d1"))

    assert "gfunk peep" in capsys.readouterr().err


def test_peep_sheet_echoes_replay(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"A": "1"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_peep(peep_args(file_id="s1", cell_range="Sheet1"))

    assert "gfunk peep" in capsys.readouterr().err
