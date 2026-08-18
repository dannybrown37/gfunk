"""Tests for src/gfunk/gmail.py — pure functions, no API calls."""

import pytest

from gfunk.gmail import filter_by_label, filter_by_term, header, summarise


def _message(
    *,
    msg_id: str = "m1",
    label_ids: list[str] | None = None,
    subject: str = "",
    sender: str = "",
    snippet: str = "",
    internal_date: str = "0",
) -> dict[str, object]:
    return {
        "id": msg_id,
        "labelIds": label_ids or [],
        "snippet": snippet,
        "internalDate": internal_date,
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
            ]
        },
    }


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Subject", "hello"),
        ("subject", "hello"),
        ("From", "a@example.com"),
        ("Missing", ""),
    ],
)
def test_header_is_case_insensitive_and_defaults_empty(
    name: str, expected: str
) -> None:
    message = _message(subject="hello", sender="a@example.com")
    assert header(message, name) == expected


def test_summarise_extracts_the_fields_a_human_reads() -> None:
    message = _message(
        msg_id="m1",
        label_ids=["INBOX", "Label_1"],
        subject="Receipt",
        sender="billing@example.com",
        snippet="Thanks for your order",
        internal_date="1700000000000",
    )
    assert summarise(message) == {
        "id": "m1",
        "from": "billing@example.com",
        "subject": "Receipt",
        "snippet": "Thanks for your order",
        "labels": ["INBOX", "Label_1"],
        "date": "1700000000000",
    }


@pytest.mark.parametrize(
    ("labels_by_message", "label", "expected_ids"),
    [
        ([["INBOX"], ["Label_1"], ["INBOX", "Label_1"]], "Label_1", {"m1", "m2"}),
        ([["INBOX"], ["Label_1"]], "SENT", set()),
        ([["INBOX"], ["Label_1"]], "INBOX", {"m0"}),
    ],
)
def test_filter_by_label_keeps_messages_carrying_that_label(
    labels_by_message: list[list[str]], label: str, expected_ids: set[str]
) -> None:
    messages = [
        _message(msg_id=f"m{i}", label_ids=labels)
        for i, labels in enumerate(labels_by_message)
    ]
    kept = filter_by_label(messages, label)
    assert {m["id"] for m in kept} == expected_ids


@pytest.mark.parametrize(
    ("subject", "sender", "snippet", "term", "matches"),
    [
        ("Your receipt", "billing@example.com", "order confirmed", "receipt", True),
        ("Your receipt", "billing@example.com", "order confirmed", "RECEIPT", True),
        ("Your receipt", "billing@example.com", "order confirmed", "refund", False),
        ("Newsletter", "news@example.com", "weekly digest", "news@example.com", True),
        ("Newsletter", "news@example.com", "weekly digest", "digest", True),
    ],
)
def test_filter_by_term_matches_subject_sender_or_snippet_case_insensitively(
    subject: str, sender: str, snippet: str, term: str, *, matches: bool
) -> None:
    message = _message(subject=subject, sender=sender, snippet=snippet)
    result = filter_by_term([message], term)
    assert (len(result) == 1) is matches


def test_filter_by_term_empty_term_keeps_everything() -> None:
    messages = [_message(msg_id="m1"), _message(msg_id="m2")]
    assert filter_by_term(messages, "") == messages
