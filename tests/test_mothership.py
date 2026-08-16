import asyncio
from pathlib import Path

import pytest

from gfunk.cache import Cache
from gfunk.mothership import TOOL_PREFIX, build_server
from conftest import build_drive, build_sheets

from gfunk.workspace import Workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    return Workspace(
        drive=build_drive([{"files": [{"id": "1", "name": "Q3"}]}]),
        sheets=build_sheets([["Name"], ["Ada"]]),
        cache=Cache(tmp_path / "c.db"),
    )


def test_building_the_server_does_not_require_credentials() -> None:
    def explode() -> Workspace:
        raise AssertionError("the factory must not run until a tool is called")

    build_server(explode)


def test_every_tool_is_namespaced(workspace: Workspace) -> None:
    server = build_server(lambda: workspace)
    tools = asyncio.run(server.list_tools())
    assert tools
    assert all(t.name.startswith(TOOL_PREFIX) for t in tools)


@pytest.mark.parametrize(
    "verb",
    [
        f"{TOOL_PREFIX}snoop",
        f"{TOOL_PREFIX}sample",
        f"{TOOL_PREFIX}regulate",
        f"{TOOL_PREFIX}dig",
    ],
)
def test_the_expected_verbs_are_registered(workspace: Workspace, verb: str) -> None:
    server = build_server(lambda: workspace)
    tools = asyncio.run(server.list_tools())
    assert verb in {t.name for t in tools}


def test_every_tool_documents_itself(workspace: Workspace) -> None:
    server = build_server(lambda: workspace)
    tools = asyncio.run(server.list_tools())
    assert all(t.description for t in tools)


def test_snoop_tool_reaches_the_workspace(workspace: Workspace) -> None:
    server = build_server(lambda: workspace)
    result = asyncio.run(server.call_tool(f"{TOOL_PREFIX}snoop", {"term": "Q3"}))
    assert "Q3" in str(result)


def test_the_workspace_is_connected_once_and_reused(workspace: Workspace) -> None:
    calls = []

    def factory() -> Workspace:
        calls.append(1)
        return workspace

    server = build_server(factory)
    asyncio.run(server.call_tool(f"{TOOL_PREFIX}snoop", {"term": "a"}))
    asyncio.run(server.call_tool(f"{TOOL_PREFIX}snoop", {"term": "b"}))
    assert len(calls) == 1
