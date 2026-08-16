"""The read surface: Drive search, Sheets reads, and the join between them.

Everything here is read-only, matching the scopes `get-down` requests.
"""

from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gfunk.auth import get_down
from gfunk.cache import Cache

DRIVE_FIELDS = (
    "nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, webViewLink, "
    "owners(emailAddress))"
)

FOLDER_MIME = "application/vnd.google-apps.folder"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
DOC_MIME = "application/vnd.google-apps.document"

EXPORT_MIME_MAP: dict[str, dict[str, str]] = {
    SHEET_MIME: {
        "csv": "text/csv",
        "tsv": "text/tab-separated-values",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    DOC_MIME: {
        "txt": "text/plain",
        "html": "text/html",
        "docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        "md": "text/plain",
    },
}

SHARING_FIELDS = (
    "nextPageToken, files(id, name, webViewLink, parents, owners(emailAddress), "
    "permissions(id, type, role, emailAddress, domain, allowFileDiscovery))"
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

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Newest files first — what to fuzzy-find through when there is no term yet."""
        response = (
            self.drive.files()
            .list(
                q="trashed = false",
                orderBy="modifiedTime desc",
                fields=DRIVE_FIELDS,
                pageSize=min(limit, 100),
            )
            .execute()
        )
        found: list[dict[str, Any]] = response.get("files", [])[:limit]
        self.cache.put_many("drive", "file", [(f["id"], f) for f in found])
        return found

    def children(
        self, folder_id: str = "root", limit: int = 200
    ) -> list[dict[str, Any]]:
        """One folder's contents, folders first — the unit a directory walk needs."""
        query = f"'{escape_drive_query(folder_id)}' in parents and trashed = false"
        request = self.drive.files().list(
            q=query,
            orderBy="folder,name",
            fields=DRIVE_FIELDS,
            pageSize=min(limit, 100),
        )

        found: list[dict[str, Any]] = []
        while request is not None and len(found) < limit:
            response = request.execute()
            page = response.get("files", [])
            if not page:
                break  # an empty page cannot become a full one; stop asking
            found.extend(page)
            request = self.drive.files().list_next(request, response)

        found = found[:limit]
        self.cache.put_many("drive", "file", [(f["id"], f) for f in found])
        return found

    def sharing(self, limit: int = 200) -> list[dict[str, Any]]:
        """Files you own, with their permissions, for the exposure audit.

        `permissions` rides along on the file listing rather than costing a
        request per file — an audit worth running is an audit over everything.
        """
        request = self.drive.files().list(
            q="'me' in owners and trashed = false",
            orderBy="modifiedTime desc",
            fields=SHARING_FIELDS,
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

    def folder_names(self, folder_ids: set[str]) -> dict[str, str]:
        """Resolve folder IDs to names in a single batch."""
        if not folder_ids:
            return {}
        names: dict[str, str] = {}
        for fid in folder_ids:
            if fid == "root":
                names[fid] = "My Drive"
                continue
            try:
                meta = self.drive.files().get(fileId=fid, fields="name").execute()
                names[fid] = meta.get("name", fid)
            except HttpError:
                names[fid] = fid
        return names

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

    def spreadsheets(self, limit: int = 50) -> list[dict[str, Any]]:
        """Recent spreadsheets, for interactive pickers."""
        query = f"mimeType = '{SHEET_MIME}' and trashed = false"
        response = (
            self.drive.files()
            .list(
                q=query,
                orderBy="modifiedTime desc",
                fields=DRIVE_FIELDS,
                pageSize=min(limit, 100),
            )
            .execute()
        )
        return list(response.get("files", [])[:limit])

    def sheet_tabs(self, spreadsheet_id: str) -> list[str]:
        """Tab names in a spreadsheet, for range pickers."""
        meta = (
            self.sheets.spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )
        return [str(s["properties"]["title"]) for s in meta.get("sheets", [])]

    def file_meta(self, file_id: str) -> dict[str, Any]:
        """Metadata for a single file."""
        return dict(
            self.drive.files()
            .get(fileId=file_id, fields="id,name,mimeType,webViewLink")
            .execute()
        )

    def export(self, file_id: str, mime_type: str) -> bytes:
        """Export a Google Workspace file to the given MIME type."""
        return bytes(
            self.drive.files().export(fileId=file_id, mimeType=mime_type).execute()
        )
