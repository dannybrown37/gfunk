import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_bounce
from gfunk.workspace import DOC_MIME, SHEET_MIME


def bounce_args(**overrides: object) -> argparse.Namespace:
    defaults = {"file_id": None, "fmt": None, "output": None, "tab": None}
    return argparse.Namespace(**{**defaults, **overrides})


SHEET_FILE = {
    "id": "s1",
    "name": "Budget",
    "mimeType": SHEET_MIME,
    "webViewLink": "https://docs.google.com/spreadsheets/d/s1",
}

DOC_FILE = {
    "id": "d1",
    "name": "Proposal",
    "mimeType": DOC_MIME,
    "webViewLink": "https://docs.google.com/document/d/d1",
}


def test_bounce_sheet_csv_exports_via_drive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.export.return_value = b"Name,Value\nAlice,42\n"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_bounce(bounce_args(file_id="s1", fmt="csv")) == 0

    workspace.export.assert_called_once_with("s1", "text/csv")
    assert "Alice" in capsys.readouterr().out


def test_bounce_sheet_json_uses_sheets_api(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sheet_tabs.return_value = ["Sheet1"]
    workspace.sample.return_value = [{"Name": "Alice", "Value": "42"}]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_bounce(bounce_args(file_id="s1", fmt="json")) == 0

    out = capsys.readouterr().out
    assert '"Name": "Alice"' in out


def test_bounce_doc_txt_exports_via_drive() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"Hello world"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_bounce(bounce_args(file_id="d1", fmt="txt")) == 0

    workspace.export.assert_called_once_with("d1", "text/plain")


def test_bounce_to_file(tmp_path: Path) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.export.return_value = b"Name,Value\nAlice,42\n"
    out_file = tmp_path / "out.csv"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_bounce(bounce_args(file_id="s1", fmt="csv", output=out_file)) == 0

    assert out_file.read_bytes() == b"Name,Value\nAlice,42\n"


def test_bounce_invalid_format() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_bounce(bounce_args(file_id="s1", fmt="pdf")) == 1


def test_bounce_defaults_csv_for_sheets() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.export.return_value = b"data"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_bounce(bounce_args(file_id="s1")) == 0

    workspace.export.assert_called_once_with("s1", "text/csv")


def test_bounce_defaults_txt_for_docs() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE
    workspace.export.return_value = b"text"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_bounce(bounce_args(file_id="d1")) == 0

    workspace.export.assert_called_once_with("d1", "text/plain")


def test_bounce_echoes_replayable_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.export.return_value = b"data"

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_bounce(bounce_args(file_id="s1", fmt="csv"))

    assert "gfunk bounce" in capsys.readouterr().err
