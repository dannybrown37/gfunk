from unittest.mock import MagicMock

import pytest

from conftest import build_drive, build_sheets

from gfunk.cache import Cache
from gfunk.workspace import Workspace, rows_to_dicts


def test_rows_to_dicts_uses_the_header_row() -> None:
    rows = [["Name", "Email"], ["Ada", "ada@example.com"]]
    assert rows_to_dicts(rows) == [{"Name": "Ada", "Email": "ada@example.com"}]


def test_rows_to_dicts_pads_short_rows() -> None:
    # Sheets omits trailing empty cells rather than padding them.
    rows = [["Name", "Email"], ["Ada"]]
    assert rows_to_dicts(rows) == [{"Name": "Ada", "Email": ""}]


def test_rows_to_dicts_on_an_empty_sheet() -> None:
    assert rows_to_dicts([]) == []


def test_snoop_returns_files_and_caches_them(cache: Cache) -> None:
    drive = build_drive([{"files": [{"id": "1", "name": "Q3"}]}])
    ws = Workspace(drive=drive, sheets=MagicMock(), cache=cache)

    found = ws.snoop("report")

    assert found == [{"id": "1", "name": "Q3"}]
    assert cache.get("drive", "file", "1") == {"id": "1", "name": "Q3"}


def test_snoop_escapes_quotes_in_the_query(cache: Cache) -> None:
    # Drive's q syntax is its own injection surface: an unescaped apostrophe
    # in a user's search term changes the meaning of the query.
    drive = build_drive([{"files": []}])
    ws = Workspace(drive=drive, sheets=MagicMock(), cache=cache)

    ws.snoop("O'Brien")

    sent = drive.files.return_value.list.call_args.kwargs["q"]
    assert "O\\'Brien" in sent


def test_snoop_honours_its_limit(cache: Cache) -> None:
    files = [{"id": str(i), "name": f"f{i}"} for i in range(10)]
    drive = build_drive([{"files": files}])
    ws = Workspace(drive=drive, sheets=MagicMock(), cache=cache)

    assert len(ws.snoop("x", limit=3)) == 3


def test_sample_reads_a_range_and_caches_rows(cache: Cache) -> None:
    sheets = build_sheets([["Name", "Email"], ["Ada", "ada@example.com"]])
    ws = Workspace(drive=MagicMock(), sheets=sheets, cache=cache)

    rows = ws.sample("sheet-id", "A1:B2")

    assert rows == [{"Name": "Ada", "Email": "ada@example.com"}]
    assert len(cache.records("sheets", "sheet-id")) == 1


def test_sample_limit_applies_to_data_rows(cache: Cache) -> None:
    values = [["N"], *[[str(i)] for i in range(10)]]
    sheets = build_sheets(values)
    ws = Workspace(drive=MagicMock(), sheets=sheets, cache=cache)

    assert len(ws.sample("sheet-id", "A1:A11", limit=2)) == 2


def test_mix_joins_drive_files_onto_sheet_rows(cache: Cache) -> None:
    # The integrations verb: a column of names, matched against Drive.
    drive = build_drive([{"files": [{"id": "d1", "name": "Ada onboarding"}]}])
    sheets = build_sheets([["Name"], ["Ada"]])
    ws = Workspace(drive=drive, sheets=sheets, cache=cache)

    mixed = ws.mix("sheet-id", "A1:A2", key="Name")

    assert mixed == [
        {"Name": "Ada", "drive_matches": [{"id": "d1", "name": "Ada onboarding"}]}
    ]


def test_mix_raises_on_an_unknown_key_column(cache: Cache) -> None:
    sheets = build_sheets([["Name"], ["Ada"]])
    ws = Workspace(drive=MagicMock(), sheets=sheets, cache=cache)

    with pytest.raises(KeyError):
        ws.mix("sheet-id", "A1:A2", key="Nope")
