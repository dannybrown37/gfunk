"""Tests for src/gfunk/gmail.py — pure functions, no API calls."""

import pytest

from gfunk.gmail import (
    archive_filename,
    archive_year,
    backup_filename,
    decode_raw_message,
    filter_by_label,
    filter_by_term,
    header,
    html_to_text,
    parse_email_backup,
    render_archive_pdf,
    slugify,
    summarise,
)


def _message(
    *,
    msg_id: str = "m1",
    label_ids: list[str] | None = None,
    subject: str = "",
    sender: str = "",
    snippet: str = "",
    internal_date: str = "0",
    size_estimate: int = 0,
) -> dict[str, object]:
    return {
        "id": msg_id,
        "labelIds": label_ids or [],
        "snippet": snippet,
        "internalDate": internal_date,
        "sizeEstimate": size_estimate,
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
        size_estimate=4096,
    )
    assert summarise(message) == {
        "id": "m1",
        "from": "billing@example.com",
        "subject": "Receipt",
        "snippet": "Thanks for your order",
        "labels": ["INBOX", "Label_1"],
        "date": "1700000000000",
        "size": 4096,
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


def test_backup_filename_is_iso_timestamp_prefixed_and_sortable() -> None:
    earlier = backup_filename("m1", "1704067200000")
    later = backup_filename("m2", "1704153600000")
    assert earlier == "2024-01-01T000000Z_m1.eml"
    assert later == "2024-01-02T000000Z_m2.eml"
    assert sorted([later, earlier]) == [earlier, later]


def test_backup_filename_handles_missing_date() -> None:
    assert backup_filename("m1", "") == "1970-01-01T000000Z_m1.eml"


def test_decode_raw_message_round_trips_urlsafe_base64() -> None:
    import base64

    original = b"From: a@b.com\r\nSubject: hi\r\n\r\nbody"
    encoded = base64.urlsafe_b64encode(original).rstrip(b"=").decode()
    assert decode_raw_message(encoded) == original


def test_html_to_text_strips_tags_and_drops_script_and_style() -> None:
    html = (
        "<style>.x{color:red}</style>"
        "<p>Hello <b>World</b></p>"
        "<script>evil()</script>"
        "<div>Line two</div>"
    )
    assert html_to_text(html) == "Hello World\nLine two"


def _build_raw_message(
    *, html_only: bool = False, attachment: bytes | None = b"file-bytes"
) -> bytes:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "billing@example.com"
    msg["To"] = "me@example.com"
    msg["Subject"] = "Invoice #42"
    msg["Date"] = "Mon, 01 Jan 2024 00:00:00 +0000"
    if html_only:
        msg.set_content("<p>Your invoice is ready</p>", subtype="html")
    else:
        msg.set_content("Your invoice is ready")
    if attachment is not None:
        msg.add_attachment(
            attachment, maintype="text", subtype="plain", filename="invoice.txt"
        )
    return msg.as_bytes()


def test_parse_email_backup_extracts_metadata_body_and_attachments() -> None:
    parsed = parse_email_backup(_build_raw_message())

    assert parsed["metadata"]["from"] == "billing@example.com"
    assert parsed["metadata"]["subject"] == "Invoice #42"
    assert parsed["body"] == "Your invoice is ready"
    assert parsed["body_html"] == "<pre>Your invoice is ready</pre>"
    assert parsed["attachments"] == [
        {
            "filename": "invoice.txt",
            "content": b"file-bytes",
            "content_type": "text/plain",
        }
    ]


def test_parse_email_backup_converts_html_only_body_to_text() -> None:
    parsed = parse_email_backup(_build_raw_message(html_only=True, attachment=None))

    assert parsed["body"] == "Your invoice is ready"
    assert parsed["body_html"].strip() == "<p>Your invoice is ready</p>"
    assert parsed["attachments"] == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Amazon.com Order #123", "amazon-com-order-123"),
        ("  spaced -- out  ", "spaced-out"),
        ("", "message"),
        ("!!!", "message"),
    ],
)
def test_slugify_produces_filesystem_safe_stub(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_slugify_truncates_long_text() -> None:
    assert len(slugify("word " * 20)) <= 40


def test_archive_year_reads_the_message_own_date() -> None:
    assert archive_year("1704067200000") == "2024"


def test_archive_filename_is_date_subject_slug_and_id() -> None:
    name = archive_filename("m1", "1704067200000", "Amazon.com Order #123")
    assert name == "2024-01-01_amazon-com-order-123_m1.pdf"


def test_render_archive_pdf_produces_pdf_bytes() -> None:
    metadata = {"from": "a@b.com", "subject": "hi"}
    pdf_bytes = render_archive_pdf(metadata, "<p>Receipt body</p>")
    assert pdf_bytes.startswith(b"%PDF")
