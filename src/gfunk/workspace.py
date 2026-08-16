"""The read surface: Drive search, Sheets reads, and the join between them.

Everything here is read-only, matching the scopes `get-down` requests.
"""

from typing import Any

from googleapiclient.discovery import build

from gfunk.auth import get_down
from gfunk.cache import Cache

DRIVE_FIELDS = (
    "nextPageToken, files(id, name, mimeType, modifiedTime, owners(emailAddress))"
)


def escape_drive_query(term: str) -> str:
    """Escape a term for Drive's `q` syntax, which is its own injection surface."""
    return term.replace("\\", "\\\\").replace("'", "\\'")


def rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    """Turn a Sheets value range into dicts, padding the short rows Sheets returns."""
    if not rows:
        return []
    headers, *data = rows
    return [
        {h: (row[i] if i < len(row) else "") for i, h in enumerate(headers)}
        for row in data
    ]


class Workspace:
    """Read operations over Drive and Sheets, writing through to the cache."""

    def __init__(self, drive: Any, sheets: Any, cache: Cache) -> None:
        self.drive = drive
        self.sheets = sheets
        self.cache = cache

    @classmethod
    def connect(cls, cache: Cache | None = None) -> Workspace:
        creds = get_down()
        return cls(
            drive=build("drive", "v3", credentials=creds),
            sheets=build("sheets", "v4", credentials=creds),
            cache=cache or Cache(),
        )

    def snoop(self, term: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search Drive for `term`, caching what comes back."""
        query = f"name contains '{escape_drive_query(term)}' and trashed = false"
        request = self.drive.files().list(
            q=query,
            fields=DRIVE_FIELDS,
            pageSize=min(limit, 100),
        )

        found: list[dict[str, Any]] = []
        while request is not None and len(found) < limit:
            response = request.execute()
            found.extend(response.get("files", []))
            request = self.drive.files().list_next(request, response)

        found = found[:limit]
        self.cache.put_many("drive", "file", [(f["id"], f) for f in found])
        return found

    def sample(
        self, spreadsheet_id: str, cell_range: str, limit: int | None = None
    ) -> list[dict[str, str]]:
        """Pull a subset of a sheet as records, caching them."""
        response = (
            self.sheets.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=cell_range)
            .execute()
        )
        rows = rows_to_dicts(response.get("values", []))
        if limit is not None:
            rows = rows[:limit]

        self.cache.put_many(
            "sheets",
            spreadsheet_id,
            [(str(i), row) for i, row in enumerate(rows)],
        )
        return rows

    def mix(
        self,
        spreadsheet_id: str,
        cell_range: str,
        key: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Join Drive files onto each sheet row, matched on the `key` column."""
        rows = self.sample(spreadsheet_id, cell_range, limit=limit)

        mixed: list[dict[str, Any]] = []
        for row in rows:
            if key not in row:
                message = (
                    f"No column {key!r} in {sorted(row)}. Pass --key with one of those."
                )
                raise KeyError(message)
            mixed.append({**row, "drive_matches": self.snoop(row[key])})
        return mixed
