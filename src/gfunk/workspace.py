"""Drive search, Sheets reads, file operations, and the join between them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from googleapiclient.discovery import build

from gfunk import gmail
from gfunk.auth import (
    CALENDAR_SCOPE,
    SCOPES,
    DEFAULT_TOKEN_PATH,
    get_down,
    granted_scopes,
)
from gfunk.cache import Cache

if TYPE_CHECKING:
    from pathlib import Path

DRIVE_FIELDS = (
    "nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, webViewLink, "
    "owners(emailAddress))"
)

FOLDER_MIME = "application/vnd.google-apps.folder"
ARCHIVE_ROOT_NAME = "gfunk-archive"
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
        *,
        calendar: Any = None,
    ) -> None:
        self.drive = drive
        self.sheets = sheets
        self.cache = cache
        self.script = script
        self.gmail = gmail
        self.calendar = calendar

    @classmethod
    def connect(cls, cache: Cache | None = None) -> Workspace:
        existing = granted_scopes(DEFAULT_TOKEN_PATH)
        has_calendar = CALENDAR_SCOPE in existing
        scopes = [*SCOPES, CALENDAR_SCOPE] if has_calendar else None
        creds = get_down(scopes=scopes)
        return cls(
            drive=build("drive", "v3", credentials=creds),
            sheets=build("sheets", "v4", credentials=creds),
            script=build("script", "v1", credentials=creds),
            gmail=build("gmail", "v1", credentials=creds),
            calendar=build("calendar", "v3", credentials=creds)
            if has_calendar
            else None,
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

    def _gmail_batch_get(
        self, requests: list[tuple[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Run a set of (request_id, request) Gmail calls in one HTTP batch.

        One round trip for all N requests instead of N — this is what makes
        `gmail_labels`/`gmail_messages` fast instead of N+1.
        """
        results: dict[str, dict[str, Any]] = {}

        def collect(
            request_id: str, response: dict[str, Any], exception: Exception | None
        ) -> None:
            if exception is None:
                results[request_id] = response

        if not requests:
            return results

        batch = self.gmail.new_batch_http_request()
        for request_id, request in requests:
            batch.add(request, callback=collect, request_id=request_id)
        batch.execute()
        return results

    def gmail_labels(self) -> list[dict[str, Any]]:
        """All labels with their message counts — one batched round trip."""
        response = self.gmail.users().labels().list(userId="me").execute()
        label_ids = [entry["id"] for entry in response.get("labels", [])]

        details = self._gmail_batch_get(
            [
                (label_id, self.gmail.users().labels().get(userId="me", id=label_id))
                for label_id in label_ids
            ]
        )

        return [
            {
                "id": label_id,
                "name": details[label_id].get("name", label_id),
                "type": details[label_id].get("type", "user"),
                "messages_total": details[label_id].get("messagesTotal", 0),
                "messages_unread": details[label_id].get("messagesUnread", 0),
            }
            for label_id in label_ids
            if label_id in details
        ]

    def _gmail_list_message_ids(self, label: str | None, limit: int) -> list[str]:
        list_kwargs: dict[str, Any] = {"userId": "me", "maxResults": min(limit, 100)}
        if label:
            list_kwargs["labelIds"] = [label]
        request = self.gmail.users().messages().list(**list_kwargs)

        ids: list[str] = []
        while request is not None and len(ids) < limit:
            response = request.execute()
            ids.extend(m["id"] for m in response.get("messages", []))
            request = self.gmail.users().messages().list_next(request, response)
        return ids[:limit]

    def gmail_messages(
        self, label: str | None = None, term: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Recent message metadata (sender/subject/snippet/labels), filtered.

        Fetches headers only (`format="metadata"`), never the message body — this is
        an inventory tool, not a reader. `label` narrows the listing itself (fewer ids
        fetched); `term` still has to filter client-side, applied after. The N
        per-message `.get()` calls run as one batched round trip, not N.
        """
        ids = self._gmail_list_message_ids(label, limit)

        fetched = self._gmail_batch_get(
            [
                (
                    mid,
                    self.gmail.users()
                    .messages()
                    .get(
                        userId="me",
                        id=mid,
                        format="metadata",
                        metadataHeaders=["From", "Subject"],
                    ),
                )
                for mid in ids
            ]
        )
        messages = [fetched[mid] for mid in ids if mid in fetched]

        if label:
            messages = gmail.filter_by_label(messages, label)
        if term:
            messages = gmail.filter_by_term(messages, term)

        return [gmail.summarise(m) for m in messages]

    def _find_or_create_folder(self, name: str, parent: str) -> str:
        """Drive folder id for `name` under `parent`, creating it if absent."""
        query = (
            f"name = '{escape_drive_query(name)}' and '{parent}' in parents "
            f"and mimeType = '{FOLDER_MIME}' and trashed = false"
        )
        response = (
            self.drive.files().list(q=query, fields="files(id)", pageSize=1).execute()
        )
        found = response.get("files", [])
        if found:
            return str(found[0]["id"])

        created = (
            self.drive.files()
            .create(
                body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent]},
                fields="id",
            )
            .execute()
        )
        return str(created["id"])

    def gmail_archive_message(
        self, message_id: str, *, parent: str = "root", group: str | None = None
    ) -> dict[str, Any]:
        """Archive one message to Drive as a PDF, filed under a group folder.

        Long-term home for messages worth keeping past Gmail's normal
        cleanup cycle (receipts, records) — `<parent>/gfunk-archive/<group>/
        <date>_<subject>_<id>.pdf`, not a zip, so it opens and searches like
        any other document years from now. `group` defaults to the message's
        year; pass an explicit `group` (e.g. a label name) to file everything
        together instead of splitting by year.

        A message with attachments gets its own `<date>_<subject>_<id>/`
        subfolder holding the rendered PDF plus every attachment, so the
        pieces of one email stay together instead of scattering loose files
        across the group folder. A message with no attachments stays a
        single loose PDF — a folder for one file is just noise.
        """
        raw = (
            self.gmail.users()
            .messages()
            .get(userId="me", id=message_id, format="raw")
            .execute()
        )
        internal_date = str(raw.get("internalDate", ""))
        content = gmail.decode_raw_message(str(raw["raw"]))
        parsed = gmail.parse_email_backup(content)
        pdf_bytes = gmail.render_archive_pdf(parsed["metadata"], parsed["body_html"])
        name = gmail.archive_filename(
            message_id, internal_date, parsed["metadata"]["subject"]
        )

        archive_root = self._find_or_create_folder(ARCHIVE_ROOT_NAME, parent)
        group_name = group if group is not None else gmail.archive_year(internal_date)
        group_folder = self._find_or_create_folder(group_name, archive_root)

        if parsed["attachments"]:
            dest_folder = self._find_or_create_folder(
                name.removesuffix(".pdf"), group_folder
            )
        else:
            dest_folder = group_folder

        from googleapiclient.http import MediaInMemoryUpload

        media = MediaInMemoryUpload(pdf_bytes, mimetype="application/pdf")
        metadata: dict[str, Any] = {"name": name, "parents": [dest_folder]}
        result = dict(
            self.drive.files()
            .create(body=metadata, media_body=media, fields="id, name, webViewLink")
            .execute()
        )

        for attachment in parsed["attachments"]:
            attachment_media = MediaInMemoryUpload(
                attachment["content"], mimetype=attachment["content_type"]
            )
            attachment_metadata: dict[str, Any] = {
                "name": attachment["filename"],
                "parents": [dest_folder],
            }
            self.drive.files().create(
                body=attachment_metadata, media_body=attachment_media, fields="id"
            ).execute()

        return result

    ARCHIVE_LABEL_LIMIT = 10_000

    def gmail_archive_label(
        self, label_id: str, label_name: str, *, parent: str = "root"
    ) -> list[dict[str, Any]]:
        """Archive every message in a label to Drive, one PDF each.

        All messages land in one `<label_name>` folder rather than split by
        year — a by-label archive is meant to be browsed as one pile, not
        chopped up by when it happened to arrive. Reuses `gmail_archive_message`
        per id — same recoverable (non-destructive) semantics: nothing is
        removed from Gmail.
        """
        ids = self._gmail_list_message_ids(label_id, self.ARCHIVE_LABEL_LIMIT)
        return [
            self.gmail_archive_message(mid, parent=parent, group=label_name)
            for mid in ids
        ]

    def gmail_preview(self, message_id: str) -> str:
        """Plain-text body of one message, for on-demand reading in the TUI.

        Fetches `format="raw"` (the same shape `gmail_archive_message` uses) so
        there's one decode path for full message content; only called when the
        user asks to preview a specific message, never as part of a listing.
        """
        raw = (
            self.gmail.users()
            .messages()
            .get(userId="me", id=message_id, format="raw")
            .execute()
        )
        content = gmail.decode_raw_message(str(raw["raw"]))
        parsed = gmail.parse_email_backup(content)
        return str(parsed["body"])

    def gmail_trash_message(self, message_id: str) -> dict[str, Any]:
        """Move a Gmail message to Trash — recoverable for 30 days, not a purge."""
        return dict(
            self.gmail.users().messages().trash(userId="me", id=message_id).execute()
        )

    def grind(self, days: int = 7, *, since_days: int = 0) -> list[dict[str, Any]]:
        """Events on the primary calendar, earliest first.

        Spans `since_days` back to `days` ahead. `since_days` exists because
        reviewing a week means looking at what actually happened as well as
        what is coming.

        Requires opt-in Calendar access (`gfunk mount-up --with-calendar`);
        caller must check `self.calendar is not None` first.
        """
        from datetime import UTC, datetime, timedelta

        assert self.calendar is not None
        now = datetime.now(UTC)
        response = (
            self.calendar.events()
            .list(
                calendarId="primary",
                timeMin=(now - timedelta(days=since_days)).isoformat(),
                timeMax=(now + timedelta(days=days)).isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return list(response.get("items", []))

    def gmail_delete_label(self, label_id: str) -> None:
        """Permanently delete a label. Not recoverable — caller must confirm."""
        self.gmail.users().labels().delete(userId="me", id=label_id).execute()
