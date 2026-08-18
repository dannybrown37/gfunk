"""Filter and summarise Gmail messages already fetched from the API.

Pure functions, no I/O — mirrors regulate.py's shape so the filtering logic
(the part a bad name or a false match actually hurts) is testable on its own.
"""

from typing import Any


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
