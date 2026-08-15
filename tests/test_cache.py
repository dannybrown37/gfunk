import json
import sqlite3
import stat
from pathlib import Path

import pytest

from gfunk.cache import Cache


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    return Cache(tmp_path / "cache.db")


def test_creates_the_database_private_to_the_user(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "cache.db"
    Cache(path)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, (
        f"cache is {mode:o}; Workspace content must not be world-readable"
    )


def test_round_trips_a_record(cache: Cache) -> None:
    cache.put("drive", "file", "abc", {"name": "Q3 report"})
    assert cache.get("drive", "file", "abc") == {"name": "Q3 report"}


def test_get_returns_none_when_absent(cache: Cache) -> None:
    assert cache.get("drive", "file", "nope") is None


def test_put_is_an_upsert_not_a_duplicate(cache: Cache) -> None:
    cache.put("drive", "file", "abc", {"name": "old"})
    cache.put("drive", "file", "abc", {"name": "new"})
    assert cache.get("drive", "file", "abc") == {"name": "new"}
    assert len(cache.records("drive", "file")) == 1


def test_records_are_scoped_by_service_and_kind(cache: Cache) -> None:
    cache.put("drive", "file", "a", {"n": 1})
    cache.put("sheets", "row", "a", {"n": 2})
    assert cache.records("drive", "file") == [{"n": 1}]
    assert cache.records("sheets", "row") == [{"n": 2}]


def test_put_many_stores_every_record(cache: Cache) -> None:
    cache.put_many("drive", "file", [("a", {"n": 1}), ("b", {"n": 2})])
    assert len(cache.records("drive", "file")) == 2


def test_records_honours_a_limit(cache: Cache) -> None:
    cache.put_many("drive", "file", [(str(i), {"n": i}) for i in range(10)])
    assert len(cache.records("drive", "file", limit=3)) == 3


def test_fetched_at_is_recorded(cache: Cache) -> None:
    cache.put("drive", "file", "abc", {"name": "x"})
    assert cache.fetched_at("drive", "file", "abc") is not None


@pytest.mark.parametrize(
    "hostile",
    [
        "'; DROP TABLE records; --",
        '" OR 1=1 --',
        "abc'||'def",
    ],
)
def test_identifiers_are_parameterised_not_interpolated(
    cache: Cache, hostile: str
) -> None:
    # A Drive file name or sheet id is external input; it must never reach SQL
    # as text. If it does, the table is gone by the second call.
    cache.put("drive", "file", hostile, {"name": hostile})
    assert cache.get("drive", "file", hostile) == {"name": hostile}
    assert len(cache.records("drive", "file")) == 1


def test_clear_removes_only_the_named_scope(cache: Cache) -> None:
    cache.put("drive", "file", "a", {"n": 1})
    cache.put("sheets", "row", "a", {"n": 2})
    cache.clear("drive", "file")
    assert cache.records("drive", "file") == []
    assert cache.records("sheets", "row") == [{"n": 2}]


def test_payload_is_stored_as_json_text(cache: Cache, tmp_path: Path) -> None:
    cache.put("drive", "file", "abc", {"name": "Q3"})
    with sqlite3.connect(tmp_path / "cache.db") as conn:
        (payload,) = conn.execute(
            "SELECT payload FROM records WHERE record_id = ?", ("abc",)
        ).fetchone()
    assert json.loads(payload) == {"name": "Q3"}
