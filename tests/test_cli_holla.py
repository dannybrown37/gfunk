import argparse
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import cmd_holla


INVOICE = {
    "id": "m1",
    "from": "billing@example.com",
    "subject": "Invoice #42",
    "snippet": "Your invoice is ready",
    "labels": ["INBOX", "IMPORTANT"],
    "date": "1700000000000",
}
COFFEE = {
    "id": "m2",
    "from": "friend@example.com",
    "subject": "Coffee?",
    "snippet": "Let's catch up",
    "labels": ["INBOX"],
    "date": "1700000001000",
}


def holla_args(**overrides: object) -> argparse.Namespace:
    defaults = {"label": None, "term": None, "limit": 50, "json": False}
    return argparse.Namespace(**{**defaults, **overrides})


def mock_workspace(messages: list[dict[str, Any]]) -> MagicMock:
    ws = MagicMock()
    ws.gmail_messages.return_value = messages
    return ws


def test_no_messages_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    ws = mock_workspace([])

    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        assert cmd_holla(holla_args()) == 0

    assert "No messages found" in capsys.readouterr().out


def test_messages_are_printed_as_a_table(capsys: pytest.CaptureFixture[str]) -> None:
    ws = mock_workspace([INVOICE, COFFEE])

    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        cmd_holla(holla_args())

    out = capsys.readouterr().out
    assert "Invoice #42" in out
    assert "billing@example.com" in out
    assert "Coffee?" in out


def test_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    ws = mock_workspace([INVOICE])

    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        cmd_holla(holla_args(json=True))

    payload = json.loads(capsys.readouterr().out)
    assert payload == [INVOICE]


def test_label_and_term_are_passed_through() -> None:
    ws = mock_workspace([INVOICE])

    with patch("gfunk.workspace.Workspace.connect", return_value=ws):
        cmd_holla(holla_args(label="IMPORTANT", term="invoice", limit=10))

    ws.gmail_messages.assert_called_once_with(
        label="IMPORTANT", term="invoice", limit=10
    )
