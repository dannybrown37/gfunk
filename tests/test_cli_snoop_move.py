from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import SELECT_HERE, _snoop_move
from gfunk.workspace import FOLDER_MIME

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


def test_snoop_move_moves_file() -> None:
    workspace = MagicMock()
    workspace.folder_names.return_value = {"src-folder": "Source"}
    workspace.children.return_value = [FOLDER_A]
    workspace.move.return_value = {**FILE, "parents": ["folderA"]}

    def pick_side_effect(
        candidates: list[str], _header: str, **_kw: object
    ) -> str | None:
        if SELECT_HERE in candidates:
            return SELECT_HERE
        for c in candidates:
            if c.startswith("Reports/"):
                return c
        return None

    with patch("gfunk.cli.fzf_pick", side_effect=pick_side_effect):
        assert _snoop_move(workspace, FILE) == 0

    workspace.move.assert_called_once_with(
        "f1", add_parent="root", remove_parent="src-folder"
    )


def test_snoop_move_navigates_into_subfolder() -> None:
    workspace = MagicMock()
    workspace.folder_names.return_value = {"src-folder": "Source"}
    workspace.children.side_effect = [
        [FOLDER_A],
        [FOLDER_B],
    ]
    workspace.move.return_value = {**FILE, "parents": ["folderA"]}

    fzf_calls = iter(
        [
            "Reports/",
            SELECT_HERE,
        ]
    )

    def pick_side_effect(
        candidates: list[str], _header: str, **_kw: object
    ) -> str | None:
        val = next(fzf_calls)
        if val == "Reports/":
            for c in candidates:
                if c.startswith("Reports/"):
                    return c
        return val

    with patch("gfunk.cli.fzf_pick", side_effect=pick_side_effect):
        assert _snoop_move(workspace, FILE) == 0

    workspace.move.assert_called_once_with(
        "f1", add_parent="folderA", remove_parent="src-folder"
    )


def test_snoop_move_exits_cleanly_on_cancel() -> None:
    workspace = MagicMock()
    workspace.folder_names.return_value = {"src-folder": "Source"}
    workspace.children.return_value = [FOLDER_A]

    with patch("gfunk.cli.fzf_pick", return_value=None):
        assert _snoop_move(workspace, FILE) == 0

    workspace.move.assert_not_called()


def test_snoop_move_prints_move_confirmation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.folder_names.return_value = {"src-folder": "Source"}
    workspace.children.return_value = [FOLDER_A]
    workspace.move.return_value = {**FILE, "parents": ["folderA"]}

    def pick_side_effect(
        candidates: list[str], _header: str, **_kw: object
    ) -> str | None:
        if SELECT_HERE in candidates:
            return SELECT_HERE
        return None

    with patch("gfunk.cli.fzf_pick", side_effect=pick_side_effect):
        _snoop_move(workspace, FILE)

    err = capsys.readouterr().err
    assert "Moved Budget" in err
