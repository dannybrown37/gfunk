"""Drive search, Sheets reads, file operations, and the join between them."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from googleapiclient.discovery import build

from gfunk import gmail
from gfunk.auth import get_down
from gfunk.cache import Cache

DRIVE_FIELDS = (
    "nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, webViewLink, "
    "owners(emailAddress))"
)

FOLDER_MIME = "application/vnd.google-apps.folder"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
DOC_MIME = "application/vnd.google-apps.document"
SCRIPT_MIME = "application/vnd.google-apps.script"

SCRIPT_TYPE_EXTENSIONS = {"SERVER_JS": ".gs", "HTML": ".html", "JSON": ".json"}
SCRIPT_EXTENSION_TYPES = {ext: type_ for type_, ext in SCRIPT_TYPE_EXTENSIONS.items()}

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

DUBS_FIELDS = (
    "nextPageToken, files(id, name, mimeType, size, md5Checksum, parents, "
    "webViewLink, owners(emailAddress))"
)


def escape_drive_query(term: str) -> str:
    """Escape a term for Drive's `q` syntax, which is its own injection surface."""
    return term.replace("\\", "\\\\").replace("'", "\\'")


def write_script_files(files: list[dict[str, Any]], out_dir: Path) -> list[Path]:
    """Write Apps Script source files to a local directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for f in files:
        ext = SCRIPT_TYPE_EXTENSIONS.get(f.get("type", ""), "")
        path = out_dir / f"{f['name']}{ext}"
        path.write_text(f.get("source", ""))
        written.append(path)
    return written


def read_script_files(in_dir: Path) -> list[dict[str, Any]]:
    """Read a local directory back into Apps Script API file format."""
    files = []
    for path in sorted(in_dir.iterdir()):
        script_type = SCRIPT_EXTENSION_TYPES.get(path.suffix)
        if script_type is None:
            continue
        files.append(
            {"name": path.stem, "type": script_type, "source": path.read_text()}
        )
    return files


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

    def __init__(
        self,
        drive: Any,
        sheets: Any,
        cache: Cache,
        script: Any = None,
        gmail: Any = None,
    ) -> None:
        self.drive = drive
        self.sheets = sheets
        self.cache = cache
        self.script = script
        self.gmail = gmail

    @classmethod
    def connect(cls, cache: Cache | None = None) -> Workspace:
        creds = get_down()
        return cls(
            drive=build("drive", "v3", credentials=creds),
            sheets=build("sheets", "v4", credentials=creds),
            script=build("script", "v1", credentials=creds),
            gmail=build("gmail", "v1", credentials=creds),
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

    def dubs(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Files you own, with what duplicate-detection needs: hash, size, mime."""
        request = self.drive.files().list(
            q="'me' in owners and trashed = false",
            orderBy="name",
            fields=DUBS_FIELDS,
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
        """Resolve folder IDs to names in a single HTTP round-trip.

        Drive's query language has no `id =` filter, so a real batch — many
        `get` calls bundled into one HTTP request — is the only way to avoid
        one round-trip per folder.
        """
        if not folder_ids:
            return {}
        names: dict[str, str] = {}
        remaining = {fid for fid in folder_ids if fid != "root"}
        if "root" in folder_ids:
            names["root"] = "My Drive"
        if remaining:

            def collect(
                request_id: str,
                response: dict[str, Any] | None,
                _exception: Exception | None,
            ) -> None:
                if response is not None:
                    names[request_id] = response.get("name", request_id)

            batch = self.drive.new_batch_http_request()
            for fid in remaining:
                batch.add(
                    self.drive.files().get(fileId=fid, fields="name"),
                    callback=collect,
                    request_id=fid,
                )
            batch.execute()
        for fid in remaining - names.keys():
            names[fid] = fid
        return names

    def folder_paths(self, folder_ids: set[str]) -> dict[str, str]:
        """Resolve folder IDs to full paths from My Drive root.

        Drive has no path API, so this walks each folder's parent chain one
        level at a time, batching every folder that still needs a name at
        that depth into a single HTTP request — one round trip per level of
        nesting shared across all folders, not one per folder.
        """
        if not folder_ids:
            return {}

        info: dict[str, tuple[str, str | None]] = {}
        pending = {fid for fid in folder_ids if fid != "root"}
        while pending:

            def collect(
                request_id: str,
                response: dict[str, Any] | None,
                _exception: Exception | None,
            ) -> None:
                if response is not None:
                    parents = response.get("parents") or []
                    info[request_id] = (
                        response.get("name", request_id),
                        parents[0] if parents else None,
                    )
                else:
                    info[request_id] = (request_id, None)

            batch = self.drive.new_batch_http_request()
            for fid in pending:
                batch.add(
                    self.drive.files().get(fileId=fid, fields="name, parents"),
                    callback=collect,
                    request_id=fid,
                )
            batch.execute()

            pending = {
                parent
                for fid in pending
                for _, parent in (info[fid],)
                if parent and parent != "root" and parent not in info
            }

        def path_for(fid: str) -> str:
            parts: list[str] = []
            current: str | None = fid
            seen: set[str] = set()
            while current and current != "root" and current not in seen:
                seen.add(current)
                name, parent = info.get(current, (current, None))
                parts.append(name)
                current = parent
            parts.append("My Drive")
            return "/".join(reversed(parts))

        return {
            fid: ("My Drive" if fid == "root" else path_for(fid)) for fid in folder_ids
        }

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

    def scripts(self, limit: int = 50) -> list[dict[str, Any]]:
        """Apps Script projects — they're Drive files with a special MIME type."""
        query = f"mimeType = '{SCRIPT_MIME}' and trashed = false"
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

    def script_content(self, script_id: str) -> list[dict[str, Any]]:
        """Source files for an Apps Script project."""
        response = self.script.projects().getContent(scriptId=script_id).execute()
        return list(response.get("files", []))

    def update_script_content(
        self, script_id: str, files: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Push source files to an Apps Script project, replacing its content."""
        return dict(
            self.script.projects()
            .updateContent(scriptId=script_id, body={"files": files})
            .execute()
        )

    def processes(self, limit: int = 50) -> list[dict[str, Any]]:
        """Recent Apps Script executions, across all your projects."""
        response = self.script.processes().list(pageSize=min(limit, 50)).execute()
        return list(response.get("processes", [])[:limit])

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
            .get(fileId=file_id, fields="id,name,mimeType,webViewLink,parents")
            .execute()
        )

    def move(
        self, file_id: str, *, add_parent: str, remove_parent: str
    ) -> dict[str, Any]:
        """Move a file from one folder to another."""
        return dict(
            self.drive.files()
            .update(
                fileId=file_id,
                addParents=add_parent,
                removeParents=remove_parent,
                fields="id, name, parents",
            )
            .execute()
        )

    def upload(self, path: Path, *, parent: str = "root") -> dict[str, Any]:
        """Upload a local file to Drive."""
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(path), resumable=True)
        metadata: dict[str, Any] = {"name": path.name, "parents": [parent]}
        return dict(
            self.drive.files()
            .create(body=metadata, media_body=media, fields="id, name, webViewLink")
            .execute()
        )

    def trash(self, file_id: str) -> dict[str, Any]:
        """Move a file to trash — recoverable, unlike permanent delete."""
        return dict(
            self.drive.files()
            .update(fileId=file_id, body={"trashed": True}, fields="id, name, trashed")
            .execute()
        )

    def revoke(self, file_id: str, permission_id: str) -> None:
        """Remove one sharing permission from a file."""
        self.drive.permissions().delete(
            fileId=file_id, permissionId=permission_id
        ).execute()

    def export(self, file_id: str, mime_type: str) -> bytes:
        """Export a Google Workspace file to the given MIME type."""
        return bytes(
            self.drive.files().export(fileId=file_id, mimeType=mime_type).execute()
        )

    def gmail_messages(
        self, label: str | None = None, term: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Recent messages, filtered by label and/or term, as summaries."""
        request = (
            self.gmail.users().messages().list(userId="me", maxResults=min(limit, 100))
        )

        ids: list[str] = []
        while request is not None and len(ids) < limit:
            response = request.execute()
            ids.extend(m["id"] for m in response.get("messages", []))
            request = self.gmail.users().messages().list_next(request, response)
        ids = ids[:limit]

        messages = [
            self.gmail.users()
            .messages()
            .get(userId="me", id=mid, format="full")
            .execute()
            for mid in ids
        ]

        if label:
            messages = gmail.filter_by_label(messages, label)
        if term:
            messages = gmail.filter_by_term(messages, term)

        return [gmail.summarise(m) for m in messages]
