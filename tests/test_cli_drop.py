from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_drop


def make_args(
    files: list[Path],
    *,
    to: str | None = None,
) -> MagicMock:
    args = MagicMock()
    args.files = files
    args.to = to
    args.command = "drop"
    return args


def test_drop_single_file_to_root(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")

    workspace = MagicMock()
    workspace.upload.return_value = {"id": "new-id", "name": "data.csv"}

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        rc = cmd_drop(make_args([f]))

    assert rc == 0
    workspace.upload.assert_called_once_with(f, parent="root")


def test_drop_single_file_to_folder(tmp_path: Path) -> None:
    f = tmp_path / "report.pdf"
    f.write_bytes(b"%PDF-fake")

    workspace = MagicMock()
    workspace.upload.return_value = {"id": "new-id", "name": "report.pdf"}

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        rc = cmd_drop(make_args([f], to="folder-123"))

    assert rc == 0
    workspace.upload.assert_called_once_with(f, parent="folder-123")


def test_drop_multiple_files(tmp_path: Path) -> None:
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("hello")
    f2.write_text("world")

    workspace = MagicMock()
    workspace.upload.side_effect = [
        {"id": "id-a", "name": "a.txt"},
        {"id": "id-b", "name": "b.txt"},
    ]

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        rc = cmd_drop(make_args([f1, f2]))

    assert rc == 0
    assert workspace.upload.call_count == 2


def test_drop_missing_file(tmp_path: Path) -> None:
    f = tmp_path / "nope.txt"

    workspace = MagicMock()

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        rc = cmd_drop(make_args([f]))

    assert rc == 1
    workspace.upload.assert_not_called()


def test_drop_prints_confirmation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "notes.md"
    f.write_text("# Notes")

    workspace = MagicMock()
    workspace.upload.return_value = {"id": "new-id", "name": "notes.md"}

    with patch("gfunk.workspace.Workspace.connect", return_value=workspace):
        cmd_drop(make_args([f]))

    out = capsys.readouterr()
    assert "notes.md" in out.err or "notes.md" in out.out


def test_drop_interactive_destination(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")

    workspace = MagicMock()
    workspace.upload.return_value = {"id": "new-id", "name": "data.csv"}

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=True),
        patch(
            "gfunk.cli.pick_destination", return_value=("dest-id", "My Drive/Reports")
        ),
    ):
        rc = cmd_drop(make_args([f]))

    assert rc == 0
    workspace.upload.assert_called_once_with(f, parent="dest-id")


def test_drop_cli_parser_parses() -> None:
    from gfunk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["drop", "file.txt", "--to", "folder-abc"])
    assert args.command == "drop"
    assert args.to == "folder-abc"


def test_drop_cli_upload_alias() -> None:
    from gfunk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["upload", "file.txt"])
    assert args.command == "upload"
