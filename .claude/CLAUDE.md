# gfunk

CLI and MCP server for Google Workspace. Python 3.13+, uv, strict mypy.

## Quick reference

```bash
uv sync                       # install
uv run pytest tests/ -q       # run tests (uses -n 6 via xdist)
uv run pre-commit run --all-files  # lint, format, type-check, test
uv run gfunk --version        # smoke test
```

## Stack

- **Runtime:** Python 3.13+, uv
- **CLI framework:** argparse (src/gfunk/cli.py)
- **TUI:** Textual (src/gfunk/vibe.py)
- **MCP server:** mcp library, stdio transport (src/gfunk/mothership.py)
- **Auth:** Google OAuth2 Desktop flow, token cached at ~/.config/gfunk/
- **Cache:** SQLite at ~/.local/share/gfunk/cache.db
- **Linting:** ruff (strict rule set in .ruff.toml), mypy strict
- **Tests:** pytest + pytest-xdist (`-n 6`)

## Layout

- `src/gfunk/` — all source
- `tests/` — one test file per module, named `test_<module>.py` or `test_cli_<command>.py`
- `pyproject.toml` — deps, mypy config, commitizen config
- `.ruff.toml` — linter/formatter rules
- `.pre-commit-config.yaml` — full hook suite

## Conventions

- Every subcommand has exactly two names: one flavorful, one literal (e.g. `vibe` / `sheet`, `mothership` / `mcp`). No more, no less.
- Commit messages follow Conventional Commits (commitizen enforced).
- No comments unless the "why" is non-obvious.
- Type hints on all function signatures (mypy strict).
- Tests use synthetic fixtures only — never real customer data, names, or IDs.
- `block-private-terms` pre-commit hook catches PII in fixtures.

## Auth and scopes

Scopes are declared in `src/gfunk/auth.py`. A test asserts the exact scope list — any
change to scopes must update the test. Start read-only, widen deliberately.

## Adding a subcommand

1. Add the parser in `src/gfunk/cli.py` (with aliases).
2. Add the handler function in cli.py or a new module.
3. If it's an MCP tool too, register it in `src/gfunk/mothership.py`.
4. Write tests: `tests/test_cli_<name>.py`.
5. Update the vocabulary table in `README.md`.
