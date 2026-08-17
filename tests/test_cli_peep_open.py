import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_peep
from gfunk.workspace import DOC_MIME, SHEET_MIME


def peep_open_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "file_id": None,
        "cell_range": None,
        "fmt": None,
        "json": False,
        "limit": None,
        "output": None,
        "open": True,
    }
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


def test_peep_open_opens_file_in_browser() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        assert cmd_peep(peep_open_args(file_id="d1")) == 0

    opened.assert_called_once_with(DOC_FILE)


def test_peep_open_opens_sheets_in_browser_too() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = SHEET_FILE

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        assert cmd_peep(peep_open_args(file_id="s1")) == 0

    opened.assert_called_once_with(SHEET_FILE)


def test_peep_open_echoes_replayable_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = DOC_FILE

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.open_in_browser"),
    ):
        cmd_peep(peep_open_args(file_id="d1"))

    assert "gfunk peep" in capsys.readouterr().err


@pytest.mark.parametrize(
    "file_meta",
    [SHEET_FILE, DOC_FILE],
    ids=["sheet", "doc"],
)
def test_peep_open_picks_file_via_fzf_when_no_id(
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
        assert cmd_peep(peep_open_args()) == 0

    opened.assert_called_once()


def test_peep_open_exits_cleanly_when_user_cancels_fzf() -> None:
    workspace = MagicMock()
    workspace.recent.return_value = [DOC_FILE]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", return_value=None),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        assert cmd_peep(peep_open_args()) == 0

    opened.assert_not_called()
