from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from gfunk.cli import _snoop_peek
from gfunk.workspace import DOC_MIME, SHEET_MIME


def test_snoop_peek_prints_a_doc_excerpt(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.export.return_value = b"x" * 3000
    meta = {"id": "d1", "name": "Notes", "mimeType": DOC_MIME}

    assert _snoop_peek(workspace, meta) == 0

    workspace.export.assert_called_once_with("d1", "text/plain")
    assert len(capsys.readouterr().out.strip()) <= 2000


def test_snoop_peek_prints_the_first_sheet_tabs_rows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.sheet_tabs.return_value = ["Sheet1", "Sheet2"]
    workspace.sample.return_value = [{"Name": "Ada"}]
    meta = {"id": "s1", "name": "Budget", "mimeType": SHEET_MIME}

    assert _snoop_peek(workspace, meta) == 0

    workspace.sample.assert_called_once_with("s1", "Sheet1", limit=10)
    assert "Ada" in capsys.readouterr().out


def test_snoop_peek_handles_a_spreadsheet_with_no_tabs() -> None:
    workspace = MagicMock()
    workspace.sheet_tabs.return_value = []
    meta = {"id": "s1", "name": "Budget", "mimeType": SHEET_MIME}

    assert _snoop_peek(workspace, meta) == 0

    workspace.sample.assert_not_called()


def test_snoop_peek_shows_metadata_for_other_file_types(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    meta = {"id": "f1", "name": "photo.png", "mimeType": "image/png"}

    assert _snoop_peek(workspace, meta) == 0

    out = capsys.readouterr().out
    assert "photo.png" in out


def test_snoop_peek_swallows_api_errors(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.export.side_effect = HttpError(MagicMock(status=403), b"nope")
    meta = {"id": "d1", "name": "Notes", "mimeType": DOC_MIME}

    assert _snoop_peek(workspace, meta) == 0

    assert "unavailable" in capsys.readouterr().out
