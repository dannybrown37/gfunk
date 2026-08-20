import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_snoop, snoop_entries
from gfunk.workspace import FOLDER_MIME

FOLDER = {"id": "f1", "name": "Reports", "mimeType": FOLDER_MIME}
FILE = {"id": "d1", "name": "Budget", "webViewLink": "https://x"}


def snoop_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "target": None,
        "cell_range": None,
        "fmt": None,
        "json": False,
        "limit": 200,
        "output": None,
        "open": False,
        "raw": False,
    }
    return argparse.Namespace(**{**defaults, **overrides})


def test_folders_are_marked_with_a_trailing_slash_like_a_directory() -> None:
    entries = snoop_entries([FOLDER, FILE], up=False)
    labels = list(entries)
    folder_label = next(lbl for lbl in labels if lbl.startswith("Reports/"))
    file_label = next(lbl for lbl in labels if lbl.startswith("Budget"))
    assert folder_label.startswith("Reports/")
    assert not file_label.startswith("Budget/")


def test_the_parent_entry_leads_the_listing_only_below_the_root() -> None:
    assert next(iter(snoop_entries([FILE], up=True))) == "../"
    assert "../" not in snoop_entries([FILE], up=False)


def test_without_fzf_it_prints_the_folder_as_json_instead_of_hanging(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.file_meta.return_value = {
        "id": "f1",
        "name": "Reports",
        "mimeType": FOLDER_MIME,
    }
    workspace.children.return_value = [FILE]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=False),
    ):
        assert cmd_snoop(snoop_args(target="f1")) == 0

    assert '"id": "d1"' in capsys.readouterr().out
