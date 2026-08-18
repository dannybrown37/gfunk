from unittest.mock import MagicMock

from conftest import build_gmail

from gfunk.cache import Cache
from gfunk.workspace import Workspace

MSG_1 = {
    "id": "m1",
    "snippet": "Your invoice is ready",
    "labelIds": ["INBOX", "IMPORTANT"],
    "payload": {
        "headers": [
            {"name": "From", "value": "billing@example.com"},
            {"name": "Subject", "value": "Invoice #42"},
        ]
    },
}

MSG_2 = {
    "id": "m2",
    "snippet": "Let's catch up",
    "labelIds": ["INBOX"],
    "payload": {
        "headers": [
            {"name": "From", "value": "friend@example.com"},
            {"name": "Subject", "value": "Coffee?"},
        ]
    },
}


def test_gmail_messages_returns_summaries(cache: Cache) -> None:
    gmail = build_gmail(["m1", "m2"], {"m1": MSG_1, "m2": MSG_2})
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    found = ws.gmail_messages()

    assert [m["id"] for m in found] == ["m1", "m2"]
    assert found[0]["subject"] == "Invoice #42"


def test_gmail_messages_filters_by_label(cache: Cache) -> None:
    gmail = build_gmail(["m1", "m2"], {"m1": MSG_1, "m2": MSG_2})
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    found = ws.gmail_messages(label="IMPORTANT")

    assert [m["id"] for m in found] == ["m1"]


def test_gmail_messages_filters_by_term(cache: Cache) -> None:
    gmail = build_gmail(["m1", "m2"], {"m1": MSG_1, "m2": MSG_2})
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    found = ws.gmail_messages(term="invoice")

    assert [m["id"] for m in found] == ["m1"]


def test_gmail_messages_respects_limit(cache: Cache) -> None:
    gmail = build_gmail(["m1", "m2"], {"m1": MSG_1, "m2": MSG_2})
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    found = ws.gmail_messages(limit=1)

    assert len(found) == 1
