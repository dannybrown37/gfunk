import subprocess
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import (
    SELECT_HERE,
    _snoop_act_bulk,
    _snoop_delete_bulk,
    _snoop_move_bulk,
    fzf_pick_multi,
)

FILE_A = {"id": "a1", "name": "Budget"}
FILE_B = {"id": "b1", "name": "Notes"}


def test_fzf_pick_multi_returns_selected_lines() -> None:
    done = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="id1\talpha\nid2\tbeta\n"
    )
    with (
        patch("shutil.which", return_value="/usr/bin/fzf"),
        patch("sys.stdin.isatty", return_value=True),
        patch("subprocess.run", return_value=done) as run,
    ):
        assert fzf_pick_multi(["id1\talpha", "id2\tbeta"], "pick") == [
            "id1\talpha",
            "id2\tbeta",
        ]
        args = run.call_args.args[0]
        assert "--multi" in args


def test_fzf_pick_multi_returns_empty_list_off_a_tty() -> None:
    with patch("sys.stdin.isatty", return_value=False):
        assert fzf_pick_multi(["alpha"], "pick") == []


def test_snoop_act_bulk_moves_selected_items() -> None:
    workspace = MagicMock()
    workspace.move.return_value = {}

    def pick_side_effect(candidates: object, _header: str, **_kw: object) -> str | None:
        if candidates == ["Move", "Delete"]:
            return "Move"
        assert isinstance(candidates, list)
        if SELECT_HERE in candidates:
            return SELECT_HERE
        return None

    with patch("gfunk.cli.fzf_pick", side_effect=pick_side_effect):
        assert _snoop_act_bulk(workspace, [FILE_A, FILE_B], folder_id="src") == 0

    assert workspace.move.call_count == 2
    workspace.move.assert_any_call("a1", add_parent="root", remove_parent="src")
    workspace.move.assert_any_call("b1", add_parent="root", remove_parent="src")


def test_snoop_act_bulk_deletes_selected_items(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = MagicMock()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    with (
        patch("gfunk.cli.fzf_pick", return_value="Delete"),
        patch("builtins.input", return_value="trash"),
    ):
        assert _snoop_act_bulk(workspace, [FILE_A, FILE_B], folder_id="src") == 0

    workspace.trash.assert_any_call("a1")
    workspace.trash.assert_any_call("b1")
    assert workspace.trash.call_count == 2


def test_snoop_act_bulk_does_nothing_when_action_menu_escaped() -> None:
    workspace = MagicMock()

    with patch("gfunk.cli.fzf_pick", return_value=None):
        assert _snoop_act_bulk(workspace, [FILE_A, FILE_B], folder_id="src") == 0

    workspace.move.assert_not_called()
    workspace.trash.assert_not_called()


def test_snoop_move_bulk_exits_cleanly_on_destination_cancel() -> None:
    workspace = MagicMock()

    with patch("gfunk.cli.fzf_pick", return_value=None):
        assert _snoop_move_bulk(workspace, [FILE_A, FILE_B], folder_id="src") == 0

    workspace.move.assert_not_called()


def test_snoop_delete_bulk_aborts_on_anything_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = MagicMock()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    with patch("builtins.input", return_value="no"):
        assert _snoop_delete_bulk(workspace, [FILE_A, FILE_B]) == 0

    workspace.trash.assert_not_called()


def test_snoop_delete_bulk_refuses_off_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = MagicMock()
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    with pytest.raises(SystemExit):
        _snoop_delete_bulk(workspace, [FILE_A, FILE_B])

    workspace.trash.assert_not_called()


def test_snoop_walk_routes_multiple_tab_selections_to_bulk_action() -> None:
    from argparse import Namespace

    from gfunk.cli import _snoop_walk

    workspace = MagicMock()
    workspace.children.return_value = [FILE_A, FILE_B]
    workspace.move.return_value = {}

    def multi_side_effect(
        candidates: list[str], _header: str, **_kw: object
    ) -> list[str]:
        return [c for c in candidates if c]

    def pick_side_effect(candidates: object, _header: str, **_kw: object) -> str | None:
        if candidates == ["Move", "Delete"]:
            return "Move"
        assert isinstance(candidates, list)
        if SELECT_HERE in candidates:
            return SELECT_HERE
        return None

    with (
        patch("gfunk.cli.can_browse", return_value=True),
        patch("gfunk.cli.fzf_pick_multi", side_effect=multi_side_effect),
        patch("gfunk.cli.fzf_pick", side_effect=pick_side_effect),
    ):
        result = _snoop_walk(workspace, Namespace(limit=None))

    assert result == 0
    assert workspace.move.call_count == 2
