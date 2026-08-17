import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_dj
from gfunk.workspace import SCRIPT_MIME


def dj_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"page": None, "json": False}
    return argparse.Namespace(**{**defaults, **overrides})


FAKE_SCRIPTS = [
    {
        "id": "s1",
        "name": "Daily Report",
        "mimeType": SCRIPT_MIME,
        "modifiedTime": "2026-08-10T12:00:00Z",
    },
    {
        "id": "s2",
        "name": "Util Lib",
        "mimeType": SCRIPT_MIME,
        "modifiedTime": "2026-08-01T09:00:00Z",
    },
]


def _mock_workspace(scripts: list[dict[str, object]] | None = None) -> MagicMock:
    ws = MagicMock()
    ws.scripts.return_value = scripts if scripts is not None else FAKE_SCRIPTS
    return ws


def test_dj_list_shows_projects_as_table(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ws = _mock_workspace()
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_dj(dj_args(page="list"))

    assert rc == 0
    out = capsys.readouterr().out
    assert "Daily Report" in out
    assert "Util Lib" in out


def test_dj_list_json_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    ws = _mock_workspace()
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_dj(dj_args(page="list", json=True))

    assert rc == 0
    import json

    data = json.loads(capsys.readouterr().out)
    assert len(data) == 2
    assert data[0]["id"] == "s1"


def test_dj_list_empty(capsys: pytest.CaptureFixture[str]) -> None:
    ws = _mock_workspace(scripts=[])
    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        rc = cmd_dj(dj_args(page="list"))

    assert rc == 0
    assert "no" in capsys.readouterr().out.lower()
