"""The MCP server.

stdio only, deliberately. An HTTP listener holding live Workspace credentials
is attack surface this project does not need yet; the SDK supports adding it
later without touching the tools below.
"""

from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer

from gfunk import __version__
from gfunk.workspace import Workspace

TOOL_PREFIX = "gfunk__"

ALL_TOOLS = frozenset({"snoop", "sample", "regulate", "dubs", "peep"})


def _validate_tools(tools: set[str] | None) -> frozenset[str]:
    if tools is None:
        return ALL_TOOLS
    unknown = tools - ALL_TOOLS
    if unknown:
        valid = ", ".join(sorted(ALL_TOOLS))
        bad = ", ".join(sorted(unknown))
        msg = f"Unknown tools: {bad}. Valid: {valid}"
        raise ValueError(msg)
    return frozenset(tools)


def _register_snoop(server: MCPServer, connect: Callable[[], Workspace]) -> None:
    @server.tool(name=f"{TOOL_PREFIX}snoop")
    def snoop(term: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search Drive for files whose name contains `term`."""
        return connect().snoop(term, limit=limit)


def _register_sample(server: MCPServer, connect: Callable[[], Workspace]) -> None:
    @server.tool(name=f"{TOOL_PREFIX}sample")
    def sample(
        spreadsheet_id: str,
        cell_range: str,
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        """Pull rows from a spreadsheet range as records."""
        return connect().sample(spreadsheet_id, cell_range, limit=limit)


def _register_regulate(server: MCPServer, connect: Callable[[], Workspace]) -> None:
    @server.tool(name=f"{TOOL_PREFIX}regulate")
    def regulate(limit: int = 200, *, shared_only: bool = True) -> list[dict[str, Any]]:
        """Audit Drive files you own, ranked by exposure."""
        from gfunk.regulate import audit

        ws = connect()
        files = ws.sharing(limit=limit)
        return audit(files, shared_only=shared_only)


def _register_dubs(server: MCPServer, connect: Callable[[], Workspace]) -> None:
    @server.tool(name=f"{TOOL_PREFIX}dubs")
    def dubs(limit: int = 1000) -> dict[str, Any]:
        """Find duplicate files in Drive you own."""
        from gfunk.dubs import (
            find_exact_duplicates,
            find_possible_duplicates,
        )

        files = connect().dubs(limit=limit)
        return {
            "exact": find_exact_duplicates(files),
            "possible": find_possible_duplicates(files),
        }


def _register_peep(server: MCPServer, connect: Callable[[], Workspace]) -> None:
    @server.tool(name=f"{TOOL_PREFIX}peep")
    def peep(file_id: str) -> dict[str, Any]:
        """Get metadata and webViewLink for a Drive file."""
        return connect().file_meta(file_id)


_REGISTRARS: dict[str, Callable[[MCPServer, Callable[[], Workspace]], None]] = {
    "snoop": _register_snoop,
    "sample": _register_sample,
    "regulate": _register_regulate,
    "dubs": _register_dubs,
    "peep": _register_peep,
}


def build_server(
    workspace_factory: Callable[[], Workspace] = Workspace.connect,
    *,
    tools: set[str] | None = None,
) -> MCPServer:
    """Register the gfunk tools against a lazily-connected Workspace.

    Pass *tools* to register only a subset (e.g. ``{"snoop", "sample"}``).
    ``None`` registers all tools.
    """
    enabled = _validate_tools(tools)

    server: MCPServer = MCPServer(
        name="gfunk",
        version=__version__,
        instructions=(
            "Google Workspace reads: Drive search, Sheets pulls, "
            "and the join between them. Read-only."
        ),
    )
    workspace: list[Workspace] = []

    def connect() -> Workspace:
        if not workspace:
            workspace.append(workspace_factory())
        return workspace[0]

    for name in enabled:
        _REGISTRARS[name](server, connect)

    return server


def run(tools: set[str] | None = None) -> None:
    """Serve over stdio until the client disconnects."""
    build_server(tools=tools).run(transport="stdio")
