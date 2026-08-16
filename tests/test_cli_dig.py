import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_dig
from gfunk.workspace import DOC_MIME, SHEET_MIME


def dig_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"file_id": None}
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


def test_dig_opens_file_in_browser() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        assert cmd_dig(dig_args(file_id="d1")) == 0

    opened.assert_called_once_with(DOC_FILE)


def test_dig_opens_sheets_in_browser_too() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        assert cmd_dig(dig_args(file_id="s1")) == 0

    opened.assert_called_once_with(SHEET_FILE)


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

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch(
            "gfunk.cli.fzf_pick",
            return_value=f"{file_meta['name']}\t{file_meta['id']}",
        ),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        assert cmd_dig(dig_args()) == 0

    opened.assert_called_once()
