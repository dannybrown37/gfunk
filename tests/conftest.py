from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from gfunk.cache import Cache

BatchCallback = Callable[[str, Any, "Exception | None"], None]


def build_drive(pages: list[dict[str, Any]]) -> MagicMock:
    """A Drive service whose files().list() walks `pages`.

    The last page repeats rather than raising StopIteration, so a test that
    calls a search twice is exercising the code rather than the fixture.
    """
    drive = MagicMock()
    remaining = list(pages)

    def next_page() -> dict[str, Any]:
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    drive.files.return_value.list.return_value.execute.side_effect = next_page
    drive.files.return_value.list_next.return_value = None
    return drive


def build_gmail(
    message_ids: list[str],
    messages_by_id: dict[str, Any],
    labels: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """A Gmail service whose messages().list() returns `message_ids`, one page.

    `.get(id=...)` looks up the full message from `messages_by_id`. `labels`, if
    given, backs `users().labels().list()`/`.get()` (each entry needs `id`, `name`,
    `type`, `messagesTotal`, `messagesUnread`).
    """
    gmail = MagicMock()
    list_execute = (
        gmail.users.return_value.messages.return_value.list.return_value.execute
    )
    list_execute.return_value = {"messages": [{"id": mid} for mid in message_ids]}
    gmail.users.return_value.messages.return_value.list_next.return_value = None

    def get(**kwargs: str) -> MagicMock:
        result = MagicMock()
        result.execute.return_value = messages_by_id[kwargs["id"]]
        return result

    gmail.users.return_value.messages.return_value.get.side_effect = get

    def modify(**kwargs: str | dict[str, list[str]]) -> MagicMock:
        mid = str(kwargs["id"])
        body = kwargs["body"]
        assert isinstance(body, dict)
        message = dict(messages_by_id[mid])
        label_ids = set(message.get("labelIds", []))
        label_ids |= set(body.get("addLabelIds", []))
        label_ids -= set(body.get("removeLabelIds", []))
        message["labelIds"] = sorted(label_ids)
        result = MagicMock()
        result.execute.return_value = message
        return result

    gmail.users.return_value.messages.return_value.modify.side_effect = modify

    labels = labels or []
    labels_by_id = {entry["id"]: entry for entry in labels}
    labels_list_execute = (
        gmail.users.return_value.labels.return_value.list.return_value.execute
    )
    labels_list_execute.return_value = {
        "labels": [{"id": entry["id"]} for entry in labels]
    }

    def labels_get(**kwargs: str) -> MagicMock:
        result = MagicMock()
        result.execute.return_value = labels_by_id[kwargs["id"]]
        return result

    gmail.users.return_value.labels.return_value.get.side_effect = labels_get

    responses_by_id = {**messages_by_id, **labels_by_id}

    def new_batch_http_request() -> MagicMock:
        added: list[tuple[str, BatchCallback]] = []

        def add(_request: object, callback: BatchCallback, request_id: str) -> None:
            added.append((request_id, callback))

        def execute() -> None:
            for request_id, callback in added:
                callback(request_id, responses_by_id[request_id], None)

        batch = MagicMock()
        batch.add.side_effect = add
        batch.execute.side_effect = execute
        return batch

    gmail.new_batch_http_request.side_effect = new_batch_http_request
    return gmail


def build_sheets(values: list[list[str]]) -> MagicMock:
    """A Sheets service whose values().get() returns `values`."""
    sheets = MagicMock()
    get = sheets.spreadsheets.return_value.values.return_value.get
    get.return_value.execute.return_value = {"values": values}
    return sheets


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    return Cache(tmp_path / "cache.db")
