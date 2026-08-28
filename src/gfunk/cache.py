"""Local store for bulk Workspace reads.

SQLite rather than Parquet: it is in the stdlib, it is queryable without a
second engine, and it is one file that can be chmod-ed. The file holds real
Workspace content, so it is created 0600 and lives outside the repo.
"""

import json
import sqlite3
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_CACHE_PATH = Path.home() / ".local" / "share" / "gfunk" / "cache.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    service    TEXT NOT NULL,
    kind       TEXT NOT NULL,
    record_id  TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    payload    TEXT NOT NULL,
    PRIMARY KEY (service, kind, record_id)
);
"""


class Cache:
    """Records keyed by (service, kind, record_id), payloads as JSON text."""

    def __init__(self, path: Path = DEFAULT_CACHE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Create the file before writing to it so the 0600 is in place first;
        # sqlite would otherwise create it 0644 and the content would sit
        # world-readable for the width of the connect.
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def put(self, service: str, kind: str, record_id: str, payload: Any) -> None:
        self.put_many(service, kind, [(record_id, payload)])

    def put_many(
        self, service: str, kind: str, records: Iterable[tuple[str, Any]]
    ) -> None:
        now = datetime.now(UTC).isoformat()
        rows = [
            (service, kind, record_id, now, json.dumps(payload))
            for record_id, payload in records
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO records (service, kind, record_id, fetched_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (service, kind, record_id) DO UPDATE SET
                    fetched_at = excluded.fetched_at,
                    payload    = excluded.payload
                """,
                rows,
            )

    def get(self, service: str, kind: str, record_id: str) -> Any | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM records
                WHERE service = ? AND kind = ? AND record_id = ?
                """,
                (service, kind, record_id),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def fetched_at(self, service: str, kind: str, record_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT fetched_at FROM records
                WHERE service = ? AND kind = ? AND record_id = ?
                """,
                (service, kind, record_id),
            ).fetchone()
        return str(row[0]) if row else None

    def records(self, service: str, kind: str, limit: int | None = None) -> list[Any]:
        sql = """
            SELECT payload FROM records
            WHERE service = ? AND kind = ?
            ORDER BY record_id
        """
        params: tuple[Any, ...] = (service, kind)
        if limit is not None:
            sql += " LIMIT ?"
            params = (*params, limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [json.loads(row[0]) for row in rows]

    def clear(self, service: str, kind: str | None = None) -> None:
        with self._connect() as conn:
            if kind is None:
                conn.execute("DELETE FROM records WHERE service = ?", (service,))
            else:
                conn.execute(
                    "DELETE FROM records WHERE service = ? AND kind = ?",
                    (service, kind),
                )
