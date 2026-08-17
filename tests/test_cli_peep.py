import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_snoop
from gfunk.workspace import DOC_MIME, FOLDER_MIME, SHEET_MIME


def snoop_args(**overrides: object) -> argparse.Namespace:
    defaults = {
        "target": None,
        "cell_range": None,
        "fmt": None,
        "json": False,
        "limit": None,
        "output": None,
        "open": False,
        "raw": False,
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


def test_snoop_doc_txt(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"Hello world"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_snoop(snoop_args(target="d1")) == 0

    workspace.export.assert_called_once_with("d1", "text/plain")
    assert "Hello world" in capsys.readouterr().out


def test_snoop_doc_html(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"<html><body>Hello</body></html>"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_snoop(snoop_args(target="d1", fmt="html")) == 0

    workspace.export.assert_called_once_with("d1", "text/html")
    assert "<html>" in capsys.readouterr().out


def test_snoop_doc_to_file(tmp_path: Path) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"Hello world"
    out = tmp_path / "doc.txt"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_snoop(snoop_args(target="d1", output=out)) == 0

    assert out.read_text() == "Hello world"


# --- Sheets ---


def test_snoop_sheet_table(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sheet_tabs.return_value = ["Sheet1"]
    workspace.sample.return_value = [{"Name": "Alice", "Value": "42"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
    ):
        assert cmd_snoop(snoop_args(target="s1", raw=True)) == 0

    out = capsys.readouterr().out
    assert "Alice" in out


def test_snoop_sheet_json(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"Name": "Alice", "Value": "42"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.pick_range", return_value="Sheet1"),
    ):
        assert cmd_snoop(snoop_args(target="s1", json=True)) == 0

    out = capsys.readouterr().out
    assert '"Name": "Alice"' in out


def test_snoop_sheet_with_range() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"A": "1"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert (
            cmd_snoop(snoop_args(target="s1", cell_range="Sheet1!A1:B5", raw=True)) == 0
        )

    workspace.sample.assert_called_once_with("s1", "Sheet1!A1:B5", limit=None)


# --- Rejection ---


def test_snoop_rejects_non_doc_non_sheet() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = {
        "id": "x1",
        "name": "image.png",
        "mimeType": "image/png",
    }

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_snoop(snoop_args(target="x1")) == 1


# --- Replay ---


def test_snoop_doc_echoes_replay(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"text"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_snoop(snoop_args(target="d1"))

    assert "gfunk snoop" in capsys.readouterr().err


def test_snoop_sheet_echoes_replay(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sample.return_value = [{"A": "1"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_snoop(snoop_args(target="s1", cell_range="Sheet1", raw=True))

    assert "gfunk snoop" in capsys.readouterr().err
