import argparse
from collections.abc import Callable
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


def label_for(items: list[dict[str, object]], name_prefix: str) -> str:
    """Find the snoop_entries key that starts with `name_prefix`."""
    entries = snoop_entries(items, up=False)
    return next(k for k in entries if k.startswith(name_prefix))


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


def _label(candidate: object) -> str:
    """The display half of an "id\\tlabel" fzf candidate."""
    _, _, label = str(candidate).partition("\t")
    return label


def _pick_by_name(
    name_prefix: str,
) -> Callable[[list[object], str], str | None]:
    """Return a fzf_pick side_effect that picks the entry matching name_prefix."""

    def picker(candidates: list[object], _header: str, **_kw: bool) -> str | None:
        for c in candidates:
            if _label(c).startswith(name_prefix):
                return str(c)
        return None

    return picker


def test_picking_a_folder_descends_and_lists_it() -> None:
    workspace = MagicMock()
    workspace.children.side_effect = [[FOLDER], [FILE], [FOLDER]]

    call_count = 0

    def pick_then_none(
        candidates: list[object], _header: str, **_kw: bool
    ) -> str | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            for c in candidates:
                if _label(c).startswith("Reports/"):
                    return str(c)
        return None

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", side_effect=pick_then_none),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        assert cmd_snoop(snoop_args()) == 0

    assert [c.args[0] for c in workspace.children.call_args_list][:2] == ["root", "f1"]
    opened.assert_not_called()


def test_picking_a_file_opens_it_and_emits_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = MagicMock()
    workspace.children.return_value = [FILE]

    call_count = 0

    def pick_file_then_open(
        candidates: list[object], _header: str, **_kw: bool
    ) -> str | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            for c in candidates:
                if _label(c).startswith("Budget"):
                    return str(c)
        return "Open in browser"

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", side_effect=pick_file_then_open),
        patch("gfunk.cli.open_in_browser") as opened,
    ):
        assert cmd_snoop(snoop_args()) == 0

    opened.assert_called_once_with(FILE)
    out = capsys.readouterr()
    assert '"id": "d1"' in out.out
    assert "gfunk snoop" in out.err, "echo the replayable command"


def test_escape_at_the_root_leaves_rather_than_looping() -> None:
    workspace = MagicMock()
    workspace.children.return_value = [FILE]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", return_value=None),
    ):
        assert cmd_snoop(snoop_args()) == 0

    workspace.children.assert_called_once()


def test_escape_below_the_root_climbs_back_up_a_level() -> None:
    workspace = MagicMock()
    workspace.children.side_effect = [[FOLDER], [FILE], [FOLDER]]

    call_count = 0

    def pick_then_none(
        candidates: list[object], _header: str, **_kw: bool
    ) -> str | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            for c in candidates:
                if _label(c).startswith("Reports/"):
                    return str(c)
        return None

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", side_effect=pick_then_none),
    ):
        assert cmd_snoop(snoop_args()) == 0

    assert [c.args[0] for c in workspace.children.call_args_list] == [
        "root",
        "f1",
        "root",
    ], "escaping in a subfolder re-lists the parent"


def test_the_parent_entry_climbs_the_same_way_escape_does() -> None:
    workspace = MagicMock()
    workspace.children.side_effect = [[FOLDER], [FILE], [FOLDER]]

    call_count = 0

    def pick_folder_then_up_then_none(
        candidates: list[object], _header: str, **_kw: bool
    ) -> str | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            for c in candidates:
                if _label(c).startswith("Reports/"):
                    return str(c)
        if call_count == 2:
            for c in candidates:
                if _label(c) == "../":
                    return str(c)
        return None

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", side_effect=pick_folder_then_up_then_none),
    ):
        assert cmd_snoop(snoop_args()) == 0

    assert workspace.children.call_count == 3


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


def test_the_header_shows_the_path_walked_so_far() -> None:
    workspace = MagicMock()
    workspace.children.side_effect = [[FOLDER], [FILE], [FOLDER]]
    headers: list[str] = []

    def record(candidates: list[object], header: str, **_kw: bool) -> str | None:
        headers.append(header)
        if len(headers) == 1:
            for c in candidates:
                if _label(c).startswith("Reports/"):
                    return str(c)
        return None

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick", side_effect=record),
    ):
        cmd_snoop(snoop_args())

    assert headers[0].startswith("My Drive")
    assert "My Drive/Reports" in headers[1]
