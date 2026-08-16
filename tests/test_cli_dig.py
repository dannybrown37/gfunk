import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_dig
from gfunk.workspace import DOC_MIME, SHEET_MIME


def dig_args(**overrides: object) -> argparse.Namespace:
    defaults = {"file_id": None, "rows": 20}
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


def test_dig_sheet_shows_tail_rows(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sheet_tabs.return_value = ["Sheet1"]
    workspace.sample.return_value = [{"A": str(i)} for i in range(50)]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_dig(dig_args(file_id="s1")) == 0

    out = capsys.readouterr()
    assert '"A": "30"' in out.out
    assert '"A": "49"' in out.out
    assert '"A": "0"' not in out.out


def test_dig_sheet_custom_rows(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE
    workspace.sheet_tabs.return_value = ["Sheet1"]
    workspace.sample.return_value = [{"A": str(i)} for i in range(10)]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_dig(dig_args(file_id="s1", rows=5)) == 0

    out = capsys.readouterr()
    assert '"A": "5"' in out.out
    assert '"A": "4"' not in out.out


def test_dig_doc_opens_browser() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        assert cmd_dig(dig_args(file_id="d1")) == 0

    opened.assert_called_once_with(DOC_FILE)


def test_dig_echoes_replayable_command(capsys: pytest.CaptureFixture[str]) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.open_in_browser"),
    ):
        cmd_dig(dig_args(file_id="d1"))

    assert "gfunk dig" in capsys.readouterr().err


@pytest.mark.parametrize(
    "file_meta",
    [SHEET_FILE, DOC_FILE],
    ids=["sheet", "doc"],
)
def test_dig_picks_file_via_fzf_when_no_id(
    file_meta: dict[str, str],
) -> None:
    workspace = MagicMock()
    workspace.recent.return_value = [file_meta]
    workspace.file_meta.return_value = file_meta
    workspace.sheet_tabs.return_value = ["Sheet1"]
    workspace.sample.return_value = [{"A": "1"}]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch(
            "gfunk.cli.fzf_pick",
            return_value=f"{file_meta['name']}\t{file_meta['id']}",
        ),
        patch("gfunk.cli.open_in_browser"),
    ):
        assert cmd_dig(dig_args()) == 0
