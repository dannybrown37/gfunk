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


LABELS = [
    {
        "id": "INBOX",
        "name": "INBOX",
        "type": "system",
        "messagesTotal": 42,
        "messagesUnread": 3,
    },
    {
        "id": "CATEGORY_PROMOTIONS",
        "name": "CATEGORY_PROMOTIONS",
        "type": "system",
        "messagesTotal": 300,
        "messagesUnread": 290,
    },
]


def test_gmail_labels_returns_counts_with_no_message_fetch(cache: Cache) -> None:
    gmail = build_gmail([], {}, labels=LABELS)
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    found = ws.gmail_labels()

    assert found == [
        {
            "id": "INBOX",
            "name": "INBOX",
            "type": "system",
            "messages_total": 42,
            "messages_unread": 3,
        },
        {
            "id": "CATEGORY_PROMOTIONS",
            "name": "CATEGORY_PROMOTIONS",
            "type": "system",
            "messages_total": 300,
            "messages_unread": 290,
        },
    ]
    gmail.users.return_value.messages.return_value.get.assert_not_called()


def test_gmail_messages_uses_one_batch_call_not_n(cache: Cache) -> None:
    gmail = build_gmail(["m1", "m2"], {"m1": MSG_1, "m2": MSG_2})
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    ws.gmail_messages()

    assert gmail.new_batch_http_request.call_count == 1
    gmail.users.return_value.messages.return_value.get.return_value.execute.assert_not_called()


def test_gmail_labels_uses_one_batch_call_not_n(cache: Cache) -> None:
    gmail = build_gmail([], {}, labels=LABELS)
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    ws.gmail_labels()

    assert gmail.new_batch_http_request.call_count == 1


def _build_raw_message() -> bytes:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "billing@example.com"
    msg["Subject"] = "Invoice #42"
    msg.set_content("Your invoice is ready")
    msg.add_attachment(
        b"pdf-bytes", maintype="application", subtype="pdf", filename="invoice.pdf"
    )
    return msg.as_bytes()


def test_gmail_archive_message_uploads_pdf_under_year_folder(
    cache: Cache,
) -> None:
    import base64

    raw = base64.urlsafe_b64encode(_build_raw_message()).rstrip(b"=")
    gmail = MagicMock()
    get_execute = (
        gmail.users.return_value.messages.return_value.get.return_value.execute
    )
    get_execute.return_value = {
        "raw": raw.decode(),
        "internalDate": "1704067200000",
    }
    drive = MagicMock()
    # First list() call (gfunk-archive lookup) finds nothing, so it's created;
    # second (2024 lookup) also finds nothing, so it's created too.
    drive.files.return_value.list.return_value.execute.return_value = {"files": []}
    drive.files.return_value.create.return_value.execute.side_effect = [
        {"id": "root-folder"},
        {"id": "year-folder"},
        {
            "id": "d1",
            "name": "2024-01-01_invoice-42_m1.pdf",
            "webViewLink": "https://drive.google.com/file/d/d1",
        },
    ]
    ws = Workspace(drive=drive, sheets=MagicMock(), cache=cache, gmail=gmail)

    result = ws.gmail_archive_message("m1")

    assert result["name"] == "2024-01-01_invoice-42_m1.pdf"
    gmail.users.return_value.messages.return_value.get.assert_called_once_with(
        userId="me", id="m1", format="raw"
    )
    create_calls = drive.files.return_value.create.call_args_list
    assert create_calls[0].kwargs["body"]["name"] == "gfunk-archive"
    assert create_calls[1].kwargs["body"]["name"] == "2024"
    assert create_calls[1].kwargs["body"]["parents"] == ["root-folder"]
    upload_kwargs = create_calls[2].kwargs
    assert upload_kwargs["body"] == {
        "name": "2024-01-01_invoice-42_m1.pdf",
        "parents": ["year-folder"],
    }
    media_body = upload_kwargs["media_body"]
    uploaded_bytes = media_body.getbytes(0, media_body.size())
    assert uploaded_bytes.startswith(b"%PDF")


def test_gmail_archive_message_reuses_existing_year_folder(cache: Cache) -> None:
    import base64

    raw = base64.urlsafe_b64encode(_build_raw_message()).rstrip(b"=")
    gmail = MagicMock()
    get_execute = (
        gmail.users.return_value.messages.return_value.get.return_value.execute
    )
    get_execute.return_value = {"raw": raw.decode(), "internalDate": "1704067200000"}
    drive = MagicMock()
    drive.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "existing-folder"}]
    }
    drive.files.return_value.create.return_value.execute.return_value = {
        "id": "d1",
        "name": "2024-01-01_invoice-42_m1.pdf",
        "webViewLink": "https://drive.google.com/file/d/d1",
    }
    ws = Workspace(drive=drive, sheets=MagicMock(), cache=cache, gmail=gmail)

    ws.gmail_archive_message("m1")

    # No folder creation calls — only the final PDF upload.
    assert drive.files.return_value.create.call_count == 1
    upload_kwargs = drive.files.return_value.create.call_args.kwargs
    assert upload_kwargs["body"]["parents"] == ["existing-folder"]


def test_gmail_preview_returns_plain_text_body(cache: Cache) -> None:
    import base64

    raw = base64.urlsafe_b64encode(_build_raw_message()).rstrip(b"=")
    gmail = MagicMock()
    get_execute = (
        gmail.users.return_value.messages.return_value.get.return_value.execute
    )
    get_execute.return_value = {"raw": raw.decode()}
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    preview = ws.gmail_preview("m1")

    assert "invoice" in preview.lower()
    gmail.users.return_value.messages.return_value.get.assert_called_once_with(
        userId="me", id="m1", format="raw"
    )


def test_gmail_trash_message_moves_to_trash(cache: Cache) -> None:
    gmail = MagicMock()
    trash_execute = (
        gmail.users.return_value.messages.return_value.trash.return_value.execute
    )
    trash_execute.return_value = {"id": "m1", "labelIds": ["TRASH"]}
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    result = ws.gmail_trash_message("m1")

    assert result["id"] == "m1"
    gmail.users.return_value.messages.return_value.trash.assert_called_once_with(
        userId="me", id="m1"
    )


def test_gmail_delete_label_deletes_by_id(cache: Cache) -> None:
    gmail = MagicMock()
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, gmail=gmail)

    ws.gmail_delete_label("EMPTY")

    gmail.users.return_value.labels.return_value.delete.assert_called_once_with(
        userId="me", id="EMPTY"
    )
