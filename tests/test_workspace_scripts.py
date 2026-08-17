from unittest.mock import MagicMock

from conftest import build_drive

from gfunk.cache import Cache
from gfunk.workspace import SCRIPT_MIME, Workspace


def test_scripts_returns_apps_script_projects(cache: Cache) -> None:
    files = [
        {"id": "s1", "name": "My Script", "mimeType": SCRIPT_MIME},
        {"id": "s2", "name": "Util Lib", "mimeType": SCRIPT_MIME},
    ]
    drive = build_drive([{"files": files}])
    ws = Workspace(drive=drive, sheets=MagicMock(), cache=cache)

    found = ws.scripts(limit=50)

    assert [f["id"] for f in found] == ["s1", "s2"]
    kwargs = drive.files.return_value.list.call_args.kwargs
    assert SCRIPT_MIME in kwargs["q"]
    assert "trashed = false" in kwargs["q"]
    assert kwargs["orderBy"] == "modifiedTime desc"


def test_scripts_respects_limit(cache: Cache) -> None:
    files = [{"id": str(i), "name": f"s{i}", "mimeType": SCRIPT_MIME} for i in range(5)]
    drive = build_drive([{"files": files}])
    ws = Workspace(drive=drive, sheets=MagicMock(), cache=cache)

    assert len(ws.scripts(limit=2)) == 2


def _build_script(processes: list[dict[str, str]]) -> MagicMock:
    script = MagicMock()
    script.processes.return_value.list.return_value.execute.return_value = {
        "processes": processes
    }
    return script


def test_processes_returns_recent_executions(cache: Cache) -> None:
    processes = [
        {
            "projectName": "Daily Report",
            "functionName": "sendReport",
            "processStatus": "COMPLETED",
            "startTime": "2026-08-10T12:00:00Z",
        },
        {
            "projectName": "Util Lib",
            "functionName": "cleanup",
            "processStatus": "FAILED",
            "startTime": "2026-08-01T09:00:00Z",
        },
    ]
    script = _build_script(processes)
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, script=script)

    found = ws.processes()

    assert [p["functionName"] for p in found] == ["sendReport", "cleanup"]
    kwargs = script.processes.return_value.list.call_args.kwargs
    assert kwargs["pageSize"] == 50


def test_processes_respects_limit(cache: Cache) -> None:
    processes = [
        {"functionName": f"fn{i}", "processStatus": "COMPLETED"} for i in range(5)
    ]
    script = _build_script(processes)
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, script=script)

    assert len(ws.processes(limit=2)) == 2


def test_script_content_returns_source_files(cache: Cache) -> None:
    files = [
        {"name": "Code", "type": "SERVER_JS", "source": "function main() {}"},
        {"name": "appsscript", "type": "JSON", "source": "{}"},
    ]
    script = MagicMock()
    script.projects.return_value.getContent.return_value.execute.return_value = {
        "scriptId": "abc123",
        "files": files,
    }
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, script=script)

    found = ws.script_content("abc123")

    assert found == files
    script.projects.return_value.getContent.assert_called_once_with(scriptId="abc123")


def test_update_script_content_pushes_files(cache: Cache) -> None:
    files = [{"name": "Code", "type": "SERVER_JS", "source": "function main() {}"}]
    script = MagicMock()
    script.projects.return_value.updateContent.return_value.execute.return_value = {
        "scriptId": "abc123",
        "files": files,
    }
    ws = Workspace(drive=MagicMock(), sheets=MagicMock(), cache=cache, script=script)

    result = ws.update_script_content("abc123", files)

    assert result["scriptId"] == "abc123"
    script.projects.return_value.updateContent.assert_called_once_with(
        scriptId="abc123", body={"files": files}
    )
