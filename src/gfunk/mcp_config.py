"""Install / uninstall the gfunk MCP server into client configs."""

import json
from pathlib import Path
from typing import Any

CLIENTS = ("claude", "copilot")

_HOME = Path.home()

SERVER_ENTRY = {
    "command": "gfunk",
    "args": ["mothership", "serve"],
}


def config_path(
    root: Path,
    client: str,
    *,
    global_scope: bool,
    home: Path = _HOME,
) -> Path:
    if client == "claude":
        if global_scope:
            return home / ".claude" / "settings.json"
        return root / ".claude" / "settings.json"
    if global_scope:
        return home / ".vscode-server" / "data" / "Machine" / "settings.json"
    return root / ".vscode" / "mcp.json"


def _read(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    return {}


def _write(path: Path, cfg: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n")


def _servers_key(client: str) -> str:
    return "mcpServers" if client == "claude" else "servers"


def install(
    root: Path,
    *,
    client: str = "all",
    global_scope: bool = False,
    home: Path = _HOME,
) -> list[Path]:
    """Add gfunk to MCP configs. Returns paths written."""
    targets = CLIENTS if client == "all" else (client,)
    written: list[Path] = []
    for c in targets:
        path = config_path(root, c, global_scope=global_scope, home=home)
        cfg = _read(path)
        key = _servers_key(c)
        servers = cfg.setdefault(key, {})
        if c == "copilot":
            servers["gfunk"] = {**SERVER_ENTRY, "type": "stdio"}
        else:
            servers["gfunk"] = dict(SERVER_ENTRY)
        _write(path, cfg)
        written.append(path)
    return written


def uninstall(
    root: Path,
    *,
    client: str = "all",
    global_scope: bool = False,
    home: Path = _HOME,
) -> list[Path]:
    """Remove gfunk from MCP configs. Returns paths modified."""
    targets = CLIENTS if client == "all" else (client,)
    modified: list[Path] = []
    for c in targets:
        path = config_path(root, c, global_scope=global_scope, home=home)
        cfg = _read(path)
        key = _servers_key(c)
        servers = cfg.get(key, {})
        if "gfunk" in servers:
            del servers["gfunk"]
            _write(path, cfg)
            modified.append(path)
    return modified
