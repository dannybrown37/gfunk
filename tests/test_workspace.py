from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch


from conftest import build_drive, build_sheets

from gfunk.cache import Cache
from gfunk.workspace import FOLDER_MIME, Workspace, rows_to_dicts


def test_rows_to_dicts_uses_the_header_row() -> None:
    rows = [["Name", "Email"], ["Ada", "ada@example.com"]]
    assert rows_to_dicts(rows) == [{"Name": "Ada", "Email": "ada@example.com"}]


def test_rows_to_dicts_pads_short_rows() -> None:
    # Sheets omits trailing empty cells rather than padding them.
    rows = [["Name", "Email"], ["Ada"]]
    assert rows_to_dicts(rows) == [{"Name": "Ada", "Email": ""}]


def test_rows_to_dicts_on_an_empty_sheet() -> None:
    assert rows_to_dicts([]) == []


def test_connect_leaves_calendar_none_without_the_scope(cache: Cache) -> None:
    with (
        patch("gfunk.workspace.get_down", return_value=MagicMock()),
        patch("gfunk.workspace.granted_scopes", return_value=set()),
        patch("gfunk.workspace.build", return_value=MagicMock()),
    ):
        ws = Workspace.connect(cache=cache)

    assert ws.calendar is None


def test_connect_builds_calendar_when_scope_granted(cache: Cache) -> None:
    from gfunk.auth import CALENDAR_SCOPE

    with (
        patch("gfunk.workspace.get_down", return_value=MagicMock()),
        patch("gfunk.workspace.granted_scopes", return_value={CALENDAR_SCOPE}),
        patch("gfunk.workspace.build", return_value=MagicMock()) as build,
    ):
        ws = Workspace.connect(cache=cache)

    assert ws.calendar is not None
    calls = [c.args[0] for c in build.call_args_list]
    assert "calendar" in calls


def test_connect_re_requests_calendar_scope_so_get_down_does_not_drop_it(
    cache: Cache,
) -> None:
    """A prior --with-calendar grant must stay sticky on every later connect().

    Regression: get_down() defaults to the base SCOPES; if connect() didn't pass
    the calendar scope back in, get_down would see the cached token's scopes as
    'changed' (narrower than what it just asked for) and re-auth down to base
    scopes, silently dropping Calendar access the user already granted.
    """
    from gfunk.auth import CALENDAR_SCOPE, SCOPES

    with (
        patch("gfunk.workspace.granted_scopes", return_value={CALENDAR_SCOPE, *SCOPES}),
        patch("gfunk.workspace.get_down", return_value=MagicMock()) as get_down,
        patch("gfunk.workspace.build", return_value=MagicMock()),
    ):
        Workspace.connect(cache=cache)

    assert get_down.call_args.kwargs["scopes"] == [*SCOPES, CALENDAR_SCOPE]


def test_grind_asks_for_events_in_the_next_week(cache: Cache) -> None:
    calendar = MagicMock()
    calendar.events.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "1", "summary": "Standup"}]
    }
    ws = Workspace(
        drive=MagicMock(), sheets=MagicMock(), cache=cache, calendar=calendar
    )

    events = ws.grind(days=7)

    assert events == [{"id": "1", "summary": "Standup"}]
    kwargs = calendar.events.return_value.list.call_args.kwargs
    assert kwargs["calendarId"] == "primary"
    assert kwargs["singleEvents"] is True
    assert kwargs["orderBy"] == "startTime"


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


def test_recent_asks_drive_for_the_newest_files_first() -> None:
    drive = MagicMock()
    drive.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "a", "name": "Budget"}, {"id": "b", "name": "Notes"}]
    }
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    found = workspace.recent(limit=1)

    assert [f["id"] for f in found] == ["a"], "limit trims the page Drive returned"
    kwargs = drive.files.return_value.list.call_args.kwargs
    assert kwargs["orderBy"] == "modifiedTime desc"
    assert kwargs["q"] == "trashed = false"


def test_sharing_asks_only_for_files_you_own_and_their_permissions() -> None:
    """You only regulate what you own, and permissions ride in the same page."""
    drive = MagicMock()
    drive.files.return_value.list.return_value.execute.return_value = {"files": []}
    drive.files.return_value.list_next.return_value = None
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    workspace.sharing(limit=10)

    kwargs = drive.files.return_value.list.call_args.kwargs
    assert "'me' in owners" in kwargs["q"]
    assert "trashed = false" in kwargs["q"]
    assert "permissions(" in kwargs["fields"], "one call, not one per file"


def test_sharing_pages_until_the_limit_is_met() -> None:
    drive = MagicMock()
    pages = [
        {"files": [{"id": "a"}, {"id": "b"}]},
        {"files": [{"id": "c"}]},
    ]
    request = drive.files.return_value.list.return_value
    request.execute.side_effect = pages
    # The same request object comes back once, so page two runs through execute too.
    drive.files.return_value.list_next.side_effect = [request, None]
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    assert [f["id"] for f in workspace.sharing(limit=10)] == ["a", "b", "c"]


def test_dubs_asks_only_for_files_you_own_with_hash_and_size() -> None:
    drive = MagicMock()
    drive.files.return_value.list.return_value.execute.return_value = {"files": []}
    drive.files.return_value.list_next.return_value = None
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    workspace.dubs(limit=10)

    kwargs = drive.files.return_value.list.call_args.kwargs
    assert "'me' in owners" in kwargs["q"]
    assert "trashed = false" in kwargs["q"]
    assert "md5Checksum" in kwargs["fields"]
    assert "size" in kwargs["fields"]


def test_dubs_pages_until_the_limit_is_met() -> None:
    drive = MagicMock()
    pages = [
        {"files": [{"id": "a"}, {"id": "b"}]},
        {"files": [{"id": "c"}]},
    ]
    request = drive.files.return_value.list.return_value
    request.execute.side_effect = pages
    drive.files.return_value.list_next.side_effect = [request, None]
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    assert [f["id"] for f in workspace.dubs(limit=10)] == ["a", "b", "c"]


def test_children_lists_one_folders_contents_folders_first() -> None:
    drive = MagicMock()
    drive.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "f", "name": "Reports", "mimeType": FOLDER_MIME}]
    }
    drive.files.return_value.list_next.return_value = None
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    found = workspace.children("folder-id", limit=10)

    assert [f["id"] for f in found] == ["f"]
    kwargs = drive.files.return_value.list.call_args.kwargs
    assert kwargs["q"] == "'folder-id' in parents and trashed = false"
    assert kwargs["orderBy"] == "folder,name"


def test_children_escapes_the_folder_id_it_is_handed() -> None:
    """A folder id reaches the query string, so it is an injection surface too."""
    drive = MagicMock()
    drive.files.return_value.list.return_value.execute.return_value = {"files": []}
    drive.files.return_value.list_next.return_value = None
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    workspace.children("it's", limit=1)

    kwargs = drive.files.return_value.list.call_args.kwargs
    assert kwargs["q"] == "'it\\'s' in parents and trashed = false"


Callback = Callable[[str, dict[str, Any] | None, Exception | None], None]


class FakeBatch:
    """Stands in for googleapiclient's BatchHttpRequest.

    Collects `.add()` calls, then fires each stored callback on `.execute()`.
    """

    def __init__(self, responses: dict[str, dict[str, Any] | None]) -> None:
        self._responses = responses
        self.calls: list[tuple[Callback, str]] = []

    def add(self, _request: object, callback: Callback, request_id: str) -> None:
        self.calls.append((callback, request_id))

    def execute(self) -> None:
        for callback, request_id in self.calls:
            callback(request_id, self._responses.get(request_id), None)


def test_folder_names_resolves_root_without_a_request() -> None:
    drive = MagicMock()
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    names = workspace.folder_names({"root"})

    assert names == {"root": "My Drive"}
    drive.new_batch_http_request.assert_not_called()
    drive.files.return_value.get.assert_not_called()


def test_folder_names_resolves_many_ids_in_one_http_request() -> None:
    drive = MagicMock()
    batch = FakeBatch({"a": {"name": "Reports"}, "b": {"name": "Archive"}})
    drive.new_batch_http_request.return_value = batch
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    names = workspace.folder_names({"a", "b"})

    assert names == {"a": "Reports", "b": "Archive"}
    drive.new_batch_http_request.assert_called_once()
    assert len(batch.calls) == 2


def test_folder_names_falls_back_to_the_id_when_unresolved() -> None:
    # A folder that no longer exists (deleted, or access revoked) can't be
    # named, but the caller still needs an entry to key off.
    drive = MagicMock()
    batch = FakeBatch({"a": {"name": "Reports"}})
    drive.new_batch_http_request.return_value = batch
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    names = workspace.folder_names({"a", "missing"})

    assert names == {"a": "Reports", "missing": "missing"}


def test_folder_paths_resolves_root_without_a_request() -> None:
    drive = MagicMock()
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    paths = workspace.folder_paths({"root"})

    assert paths == {"root": "My Drive"}
    drive.new_batch_http_request.assert_not_called()


def test_folder_paths_resolves_a_folder_directly_under_root() -> None:
    drive = MagicMock()
    batch = FakeBatch({"a": {"name": "Reports", "parents": ["root"]}})
    drive.new_batch_http_request.return_value = batch
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    paths = workspace.folder_paths({"a"})

    assert paths == {"a": "My Drive/Reports"}


def test_folder_paths_walks_the_full_parent_chain() -> None:
    # Drive has no path API, so nested folders need one round trip per level
    # of depth: "a" is inside "b" which is inside root.
    drive = MagicMock()
    batches = [
        FakeBatch({"a": {"name": "Reports", "parents": ["b"]}}),
        FakeBatch({"b": {"name": "Archive", "parents": ["root"]}}),
    ]
    drive.new_batch_http_request.side_effect = batches
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    paths = workspace.folder_paths({"a"})

    assert paths == {"a": "My Drive/Archive/Reports"}
    assert drive.new_batch_http_request.call_count == 2


def test_folder_paths_falls_back_to_the_id_when_unresolved() -> None:
    drive = MagicMock()
    batch = FakeBatch({"a": {"name": "Reports", "parents": ["root"]}})
    drive.new_batch_http_request.return_value = batch
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    paths = workspace.folder_paths({"a", "missing"})

    assert paths == {"a": "My Drive/Reports", "missing": "My Drive/missing"}


def test_move_updates_parents() -> None:
    drive = MagicMock()
    drive.files.return_value.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "Budget",
        "parents": ["dest-folder"],
    }
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    result = workspace.move(
        "file1", add_parent="dest-folder", remove_parent="src-folder"
    )

    drive.files.return_value.update.assert_called_once_with(
        fileId="file1",
        addParents="dest-folder",
        removeParents="src-folder",
        fields="id, name, parents",
    )
    assert result["parents"] == ["dest-folder"]


def test_trash_marks_a_file_trashed() -> None:
    drive = MagicMock()
    drive.files.return_value.update.return_value.execute.return_value = {
        "id": "f1",
        "name": "Budget",
        "trashed": True,
    }
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    result = workspace.trash("f1")

    drive.files.return_value.update.assert_called_once_with(
        fileId="f1", body={"trashed": True}, fields="id, name, trashed"
    )
    assert result["trashed"] is True


def test_file_meta_includes_parents() -> None:
    drive = MagicMock()
    drive.files.return_value.get.return_value.execute.return_value = {
        "id": "f1",
        "name": "Budget",
        "mimeType": "text/plain",
        "parents": ["folder1"],
    }
    workspace = Workspace(drive=drive, sheets=MagicMock(), cache=MagicMock())

    workspace.file_meta("f1")

    fields = drive.files.return_value.get.call_args.kwargs["fields"]
    assert "parents" in fields
