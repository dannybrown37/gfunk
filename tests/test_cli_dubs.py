import argparse
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_dubs


PDF_A1 = {
    "id": "a1",
    "name": "report.pdf",
    "mimeType": "application/pdf",
    "md5Checksum": "aaa",
    "size": "100",
    "parents": ["folder1"],
    "webViewLink": "https://x/a1",
}
PDF_A2 = {
    "id": "a2",
    "name": "report (1).pdf",
    "mimeType": "application/pdf",
    "md5Checksum": "aaa",
    "size": "100",
    "parents": ["folder1"],
    "webViewLink": "https://x/a2",
}
PDF_B = {
    "id": "b1",
    "name": "other.pdf",
    "mimeType": "application/pdf",
    "md5Checksum": "bbb",
    "size": "50",
    "parents": [],
}


def dubs_args(**overrides: object) -> argparse.Namespace:
    defaults = {"limit": 1000, "json": False}
    return argparse.Namespace(**{**defaults, **overrides})


def mock_workspace(files: list[dict[str, Any]]) -> MagicMock:
    ws = MagicMock()
    ws.dubs.return_value = files
    ws.folder_paths.return_value = {"folder1": "My Drive/Team/Reports"}
    return ws


def test_no_duplicates_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    ws = mock_workspace([PDF_B])

    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        assert cmd_dubs(dubs_args()) == 0

    assert "No duplicates found" in capsys.readouterr().out


def test_exact_duplicates_are_reported_with_paths_and_waste(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ws = mock_workspace([PDF_A1, PDF_A2, PDF_B])

    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        assert cmd_dubs(dubs_args()) == 0

    out = capsys.readouterr().out
    assert "My Drive/Team/Reports/report.pdf" in out
    assert "My Drive/Team/Reports/report (1).pdf" in out
    assert "100.0KB" not in out
    assert "100B" in out
    assert "other.pdf" not in out


def test_json_emits_exact_and_possible_groups() -> None:
    ws = mock_workspace([PDF_A1, PDF_A2, PDF_B])

    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        cmd_dubs(dubs_args(json=True))


@pytest.mark.parametrize("flag", [True, False])
def test_json_flag_controls_output_shape(
    *, flag: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    ws = mock_workspace([PDF_A1, PDF_A2])

    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        cmd_dubs(dubs_args(json=flag))

    out = capsys.readouterr().out
    if flag:
        payload = json.loads(out)
        assert len(payload["exact"]) == 1
    else:
        assert "Exact duplicates" in out


def test_tty_launches_the_picker_with_flattened_rows() -> None:
    ws = mock_workspace([PDF_A1, PDF_A2, PDF_B])

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.dubs_tui.DubsApp") as app_cls,
    ):
        app_cls.return_value.run.return_value = None
        cmd_dubs(dubs_args())

    rows = app_cls.call_args[0][0]
    assert app_cls.call_args[0][1] is ws
    assert {r["id"] for r in rows} == {"a1", "a2"}


def test_no_tty_skips_the_picker() -> None:
    ws = mock_workspace([PDF_A1, PDF_A2])

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=ws),
        patch("sys.stdin.isatty", return_value=False),
        patch("gfunk.dubs_tui.DubsApp") as app_cls,
    ):
        cmd_dubs(dubs_args())

    assert not app_cls.called
