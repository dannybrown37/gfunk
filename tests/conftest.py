from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from gfunk.cache import Cache


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


def build_sheets(values: list[list[str]]) -> MagicMock:
    """A Sheets service whose values().get() returns `values`."""
    sheets = MagicMock()
    get = sheets.spreadsheets.return_value.values.return_value.get
    get.return_value.execute.return_value = {"values": values}
    return sheets


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    return Cache(tmp_path / "cache.db")
