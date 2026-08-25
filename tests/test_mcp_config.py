import json
from pathlib import Path
from typing import Any

import pytest

from gfunk.mcp_config import install, uninstall, CLIENTS


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A fake project root with .claude/ and .vscode/ dirs."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".vscode").mkdir()
    return tmp_path


class TestInstall:
    @pytest.mark.parametrize("client", ["claude", "copilot"])
    def test_creates_config_file_if_missing(self, tree: Path, client: str) -> None:
        install(tree, client=client, global_scope=False)
        cfg = _read_config(tree, client, global_scope=False)
        assert "gfunk" in _mcp_servers(cfg, client)

    @pytest.mark.parametrize("client", ["claude", "copilot"])
    def test_idempotent(self, tree: Path, client: str) -> None:
        install(tree, client=client, global_scope=False)
        install(tree, client=client, global_scope=False)
        cfg = _read_config(tree, client, global_scope=False)
        assert "gfunk" in _mcp_servers(cfg, client)

    @pytest.mark.parametrize("client", ["claude", "copilot"])
    def test_preserves_existing_keys(self, tree: Path, client: str) -> None:
        path = _config_path(tree, client, global_scope=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {"someOtherKey": True}
        if client == "copilot":
            existing = {"servers": {"other": {"command": "x"}}}
        path.write_text(json.dumps(existing))

        install(tree, client=client, global_scope=False)
        cfg = _read_config(tree, client, global_scope=False)
        assert "gfunk" in _mcp_servers(cfg, client)
        if client == "copilot":
            assert "other" in cfg["servers"]
        else:
            assert cfg["someOtherKey"] is True

    def test_all_installs_both(self, tree: Path) -> None:
        install(tree, client="all", global_scope=False)
        for c in CLIENTS:
            cfg = _read_config(tree, c, global_scope=False)
            assert "gfunk" in _mcp_servers(cfg, c)

    @pytest.mark.parametrize("client", ["claude", "copilot"])
    def test_global_scope(self, tmp_path: Path, client: str) -> None:
        home = tmp_path / "home"
        home.mkdir()
        install(home, client=client, global_scope=True, home=home)
        cfg = _read_config(home, client, global_scope=True, home=home)
        assert "gfunk" in _mcp_servers(cfg, client)

    def test_entry_has_correct_shape(self, tree: Path) -> None:
        install(tree, client="claude", global_scope=False)
        cfg = _read_config(tree, "claude", global_scope=False)
        entry = cfg["mcpServers"]["gfunk"]
        assert entry["command"] == "gfunk"
        assert entry["args"] == ["mothership", "serve"]


class TestUninstall:
    @pytest.mark.parametrize("client", ["claude", "copilot"])
    def test_removes_entry(self, tree: Path, client: str) -> None:
        install(tree, client=client, global_scope=False)
        uninstall(tree, client=client, global_scope=False)
        cfg = _read_config(tree, client, global_scope=False)
        assert "gfunk" not in _mcp_servers(cfg, client)

    @pytest.mark.parametrize("client", ["claude", "copilot"])
    def test_noop_when_not_installed(self, tree: Path, client: str) -> None:
        uninstall(tree, client=client, global_scope=False)

    @pytest.mark.parametrize("client", ["claude", "copilot"])
    def test_preserves_other_servers(self, tree: Path, client: str) -> None:
        install(tree, client=client, global_scope=False)
        path = _config_path(tree, client, global_scope=False)
        cfg = json.loads(path.read_text())
        servers = _mcp_servers(cfg, client)
        servers["other"] = {"command": "other"}
        path.write_text(json.dumps(cfg, indent=2))

        uninstall(tree, client=client, global_scope=False)
        cfg = json.loads(path.read_text())
        assert "other" in _mcp_servers(cfg, client)
        assert "gfunk" not in _mcp_servers(cfg, client)

    def test_all_removes_both(self, tree: Path) -> None:
        install(tree, client="all", global_scope=False)
        uninstall(tree, client="all", global_scope=False)
        for c in CLIENTS:
            cfg = _read_config(tree, c, global_scope=False)
            assert "gfunk" not in _mcp_servers(cfg, c)


class TestToolsFilter:
    def test_install_with_tools_adds_flag_to_args(self, tree: Path) -> None:
        install(tree, client="claude", global_scope=False, tools="snoop,peep")
        cfg = _read_config(tree, "claude", global_scope=False)
        entry = _mcp_servers(cfg, "claude")["gfunk"]
        assert "--tools" in entry["args"]
        idx = entry["args"].index("--tools")
        assert entry["args"][idx + 1] == "snoop,peep"

    def test_install_without_tools_has_no_flag(self, tree: Path) -> None:
        install(tree, client="claude", global_scope=False)
        cfg = _read_config(tree, "claude", global_scope=False)
        entry = _mcp_servers(cfg, "claude")["gfunk"]
        assert "--tools" not in entry["args"]


# --- helpers ---


def _config_path(
    root: Path, client: str, *, global_scope: bool, home: Path | None = None
) -> Path:
    from gfunk.mcp_config import config_path

    return config_path(
        root, client, global_scope=global_scope, home=home or Path.home()
    )


def _read_config(
    root: Path, client: str, *, global_scope: bool, home: Path | None = None
) -> dict[str, Any]:
    path = _config_path(root, client, global_scope=global_scope, home=home)
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def _mcp_servers(cfg: dict[str, Any], client: str) -> dict[str, Any]:
    if client == "claude":
        return cfg.get("mcpServers", {})  # type: ignore[no-any-return]
    return cfg.get("servers", {})  # type: ignore[no-any-return]
