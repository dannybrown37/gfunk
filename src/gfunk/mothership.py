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


def build_server(
    workspace_factory: Callable[[], Workspace] = Workspace.connect,
) -> MCPServer:
    """Register the gfunk tools against a lazily-connected Workspace.

    The factory is not called at import time: constructing the server must not
    require credentials, or an unauthenticated client cannot even list tools.
    """
    server: MCPServer = MCPServer(
        name="gfunk",
        version=__version__,
        instructions=(
            "Google Workspace reads: Drive search, Sheets pulls, and the join "
            "between them. Read-only."
        ),
    )
    workspace: list[Workspace] = []

    def connect() -> Workspace:
        if not workspace:
            workspace.append(workspace_factory())
        return workspace[0]

    @server.tool(name=f"{TOOL_PREFIX}snoop")
    def snoop(term: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search Drive for files whose name contains `term`."""
        return connect().snoop(term, limit=limit)

    @server.tool(name=f"{TOOL_PREFIX}sample")
    def sample(
        spreadsheet_id: str, cell_range: str, limit: int | None = None
    ) -> list[dict[str, str]]:
        """Pull rows from a spreadsheet range as records."""
        return connect().sample(spreadsheet_id, cell_range, limit=limit)

    @server.tool(name=f"{TOOL_PREFIX}regulate")
    def regulate(limit: int = 200, *, shared_only: bool = True) -> list[dict[str, Any]]:
        """Audit who can reach the Drive files you own, ranked by exposure."""
        from gfunk.regulate import audit

        ws = connect()
        files = ws.sharing(limit=limit)
        return audit(files, shared_only=shared_only)

    @server.tool(name=f"{TOOL_PREFIX}peep")
    def peep(file_id: str) -> dict[str, Any]:
        """Get metadata and webViewLink for a Drive file."""
        return connect().file_meta(file_id)

    return server


def run() -> None:
    """Serve over stdio until the client disconnects."""
    build_server().run(transport="stdio")
