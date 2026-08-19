"""Filter and summarise Gmail messages already fetched from the API.

Pure functions, no I/O — mirrors regulate.py's shape so the filtering logic
(the part a bad name or a false match actually hurts) is testable on its own.
"""

import base64
import email
import email.policy
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

BLOCK_TAGS = frozenset({"br", "p", "div", "tr", "li"})
SKIPPED_TAGS = frozenset({"script", "style"})

SLUG_MAX_LEN = 40

ARCHIVABLE_ATTACHMENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
)


def is_archivable_attachment(content_type: str) -> bool:
    """True for attachments worth keeping (images, PDFs, Office docs).

    False for incidental parts that ride along with an email but aren't a
    "real" attachment a person meant to send — inline HTML alternatives,
    signature images embedded as text/plain, etc.
    """
    return (
        content_type.startswith("image/") or content_type in ARCHIVABLE_ATTACHMENT_TYPES
    )


def decode_raw_message(raw: str) -> bytes:
    """Decode Gmail's urlsafe-base64 `raw` message field to RFC 822 bytes."""
    return base64.urlsafe_b64decode(raw + "==")


def _iso_date(internal_date: str) -> tuple[str, str]:
    """`internalDate` (ms since epoch, as a string) to (year, iso-timestamp)."""
    millis = int(internal_date) if internal_date else 0
    dt = datetime.fromtimestamp(millis / 1000, tz=UTC)
    return dt.strftime("%Y"), dt.strftime("%Y-%m-%dT%H%M%SZ")


def backup_filename(message_id: str, internal_date: str, suffix: str = ".eml") -> str:
    """ISO-timestamp-prefixed filename for a Gmail backup, sortable by date.

    Uses the message's own date (`internalDate`, ms since epoch), not backup
    time, so re-running a backup doesn't reshuffle the sort order.
    """
    _, timestamp = _iso_date(internal_date)
    return f"{timestamp}_{message_id}{suffix}"


def slugify(text: str, max_len: int = SLUG_MAX_LEN) -> str:
    """Lowercase, hyphenated, filesystem-safe stub of a string."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-") or "message"


def archive_year(internal_date: str) -> str:
    """Year folder (e.g. `2026`) a message's long-term archive copy belongs in."""
    year, _ = _iso_date(internal_date)
    return year


def archive_filename(message_id: str, internal_date: str, subject: str) -> str:
    """ISO-date + subject-slug + id filename for a long-term Drive archive PDF."""
    _, timestamp = _iso_date(internal_date)
    date_only = timestamp.split("T")[0]
    return f"{date_only}_{slugify(subject)}_{message_id}.pdf"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skipping = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],  # noqa: ARG002
    ) -> None:
        if tag in SKIPPED_TAGS:
            self._skipping = True
        elif tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED_TAGS:
            self._skipping = False

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self._chunks.append(data)

    def text(self) -> str:
        lines = "".join(self._chunks).splitlines()
        return "\n".join(line.strip() for line in lines if line.strip())


def html_to_text(html: str) -> str:
    """Strip an HTML email body down to readable plain text."""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


def parse_email_backup(raw_bytes: bytes) -> dict[str, Any]:
    """Split raw RFC 822 bytes into readable metadata, body text, and attachments."""
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
    metadata = {
        "from": str(msg.get("From", "")),
        "to": str(msg.get("To", "")),
        "cc": str(msg.get("Cc", "")),
        "subject": str(msg.get("Subject", "")),
        "date": str(msg.get("Date", "")),
    }

    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part is None:
        body = ""
        body_html = ""
    elif body_part.get_content_type() == "text/html":
        body_html = str(body_part.get_content())
        body = html_to_text(body_html)
    else:
        body = str(body_part.get_content()).strip()
        body_html = f"<pre>{_escape_html(body)}</pre>"

    # `iter_attachments()` doesn't recurse into nested multipart/related
    # parts, so a PDF attached inside one (common in service-invoice emails)
    # is invisible to it. Walking the whole tree and keying off "has a
    # filename" catches attachments regardless of how deep they're nested.
    attachments = [
        {
            "filename": part.get_filename() or "attachment",
            "content": part.get_payload(decode=True) or b"",
            "content_type": part.get_content_type(),
        }
        for part in msg.walk()
        if part is not body_part
        and part.get_content_maintype() != "multipart"
        and part.get_filename() is not None
        and is_archivable_attachment(part.get_content_type())
    ]

    return {
        "metadata": metadata,
        "body": body,
        "body_html": body_html,
        "attachments": attachments,
    }


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_STYLE_TAG_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)


def _strip_style_tags(html: str) -> str:
    """Drop `<style>` blocks from an email body before PDF rendering.

    xhtml2pdf's CSS parser predates modern selector syntax (e.g. Outlook's
    `[class*=MsoHyperlink]`) and raises instead of skipping what it can't
    parse — stripping the original page styling avoids the crash. Content
    still renders, just without the sender's stylesheet.
    """
    return _STYLE_TAG_RE.sub("", html)


def render_archive_pdf(metadata: dict[str, str], body_html: str) -> bytes:
    """Render an email as a PDF: a metadata header block, then the body.

    Renders the body's own HTML (tables, receipt layout included) rather than
    flattening it to text, since a receipt's structure is part of what makes
    it readable years later.
    """
    from io import BytesIO

    from xhtml2pdf import pisa

    header_rows = "".join(
        f"<tr><td><b>{_escape_html(name.title())}:</b></td>"
        f"<td>{_escape_html(value)}</td></tr>"
        for name, value in metadata.items()
    )
    html = f"""
    <html><body>
    <table>{header_rows}</table>
    <hr/>
    {_strip_style_tags(body_html)}
    </body></html>
    """
    buffer = BytesIO()
    pisa.CreatePDF(html, dest=buffer)
    return buffer.getvalue()


def header(message: dict[str, Any], name: str) -> str:
    headers = message.get("payload", {}).get("headers", [])
    for entry in headers:
        if str(entry.get("name", "")).lower() == name.lower():
            return str(entry.get("value", ""))
    return ""


def summarise(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": message.get("id"),
        "from": header(message, "From"),
        "subject": header(message, "Subject"),
        "snippet": message.get("snippet", ""),
        "labels": list(message.get("labelIds", [])),
        "date": message.get("internalDate", ""),
        "size": message.get("sizeEstimate", 0),
    }


def filter_by_label(messages: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    return [m for m in messages if label in m.get("labelIds", [])]


def filter_by_term(messages: list[dict[str, Any]], term: str) -> list[dict[str, Any]]:
    if not term:
        return messages
    needle = term.lower()
    return [
        m
        for m in messages
        if needle in header(m, "Subject").lower()
        or needle in header(m, "From").lower()
        or needle in str(m.get("snippet", "")).lower()
    ]
