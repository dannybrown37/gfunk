import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import SELECT_HERE, cmd_slide
from gfunk.workspace import FOLDER_MIME


def slide_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"file_id": None, "destination": None}
    return argparse.Namespace(**{**defaults, **overrides})


FILE = {
    "id": "f1",
    "name": "Budget",
    "mimeType": "application/vnd.google-apps.spreadsheet",
    "parents": ["src-folder"],
    "webViewLink": "https://docs.google.com/spreadsheets/d/f1",
}

FOLDER_A = {
    "id": "folderA",
    "name": "Reports",
    "mimeType": FOLDER_MIME,
    "createdTime": "2024-01-01T00:00:00.000Z",
    "modifiedTime": "2024-06-01T00:00:00.000Z",
}
FOLDER_B = {
    "id": "folderB",
    "name": "Archive",
    "mimeType": FOLDER_MIME,
    "createdTime": "2024-01-01T00:00:00.000Z",
    "modifiedTime": "2024-06-01T00:00:00.000Z",
}


def test_slide_moves_file_with_both_ids() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = FILE
    workspace.folder_names.return_value = {
        "src-folder": "Source",
        "dest-folder": "Dest",
    }
    workspace.move.return_value = {**FILE, "parents": ["dest-folder"]}

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        assert cmd_slide(slide_args(file_id="f1", destination="dest-folder")) == 0

    workspace.move.assert_called_once_with(
        "f1", add_parent="dest-folder", remove_parent="src-folder"
    )


def test_slide_picks_file_via_snoop_when_no_id() -> None:
    file_with_dates = {
        **FILE,
        "createdTime": "2024-01-01T00:00:00.000Z",
        "modifiedTime": "2024-06-01T00:00:00.000Z",
    }
    workspace = MagicMock()
    workspace.children.side_effect = [
        [file_with_dates],  # root listing for file pick
        [FOLDER_A],  # root listing for dest pick
    ]
    workspace.folder_names.return_value = {"src-folder": "Source"}
    workspace.move.return_value = {**FILE, "parents": ["folderA"]}

    def pick_side_effect(
        candidates: list[str], _header: str, **_kw: object
    ) -> str | None:
        for c in candidates:
            if c.startswith("Budget"):
                return c
        if SELECT_HERE in candidates:
            return SELECT_HERE
        return None

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", side_effect=pick_side_effect),
    ):
        assert cmd_slide(slide_args()) == 0

    workspace.move.assert_called_once()


def test_slide_navigates_into_subfolder_then_selects() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = FILE
    workspace.folder_names.return_value = {"src-folder": "Source"}
    workspace.children.side_effect = [
        [FOLDER_A],  # root listing
        [FOLDER_B],  # inside Reports
    ]
    workspace.move.return_value = {**FILE, "parents": ["folderA"]}

    fzf_calls = iter(
        [
            "Reports/",  # descend into Reports — matches snoop_entries label start
            SELECT_HERE,  # select Reports as destination
        ]
    )

    def pick_side_effect(candidates: list[str], _header: str, **_kw: object) -> str:
        val = next(fzf_calls)
        if val == "Reports/":
            for c in candidates:
                if c.startswith("Reports/"):
                    return c
        return val

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", side_effect=pick_side_effect),
    ):
        assert cmd_slide(slide_args(file_id="f1")) == 0

    workspace.move.assert_called_once_with(
        "f1", add_parent="folderA", remove_parent="src-folder"
    )


def test_slide_exits_cleanly_when_user_cancels_file_pick() -> None:
    workspace = MagicMock()
    workspace.children.return_value = [
        {
            **FILE,
            "createdTime": "2024-01-01T00:00:00.000Z",
            "modifiedTime": "2024-06-01T00:00:00.000Z",
        },
    ]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", return_value=None),
    ):
        assert cmd_slide(slide_args()) == 0

    workspace.move.assert_not_called()


def test_slide_exits_cleanly_when_user_cancels_dest_pick() -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = FILE
    workspace.children.return_value = [FOLDER_A]
    workspace.folder_names.return_value = {"src-folder": "Source"}

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", return_value=None),
    ):
        assert cmd_slide(slide_args(file_id="f1")) == 0

    workspace.move.assert_not_called()


def test_slide_echoes_replayable_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = FILE
    workspace.folder_names.return_value = {"src-folder": "Source", "dest": "Dest"}
    workspace.move.return_value = {**FILE, "parents": ["dest"]}

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_slide(slide_args(file_id="f1", destination="dest"))

    err = capsys.readouterr().err
    assert "gfunk slide" in err
    assert "f1" in err
    assert "dest" in err
