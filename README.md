# gfunk

Programmatic Google Workspace access — a CLI and an MCP server. Google-only by design.

It exists to do what a general assistant's built-in Gmail/Calendar/Drive connectors can't:
**Sheets and Docs, bulk analytical reads, cross-service joins, and writes.**

## Security and privacy

**gfunk ships zero credentials.** You register your own Google Cloud project, create your own
OAuth client, and supply your own `credentials.json`. Nothing in this repo grants access to
anything.

- Config lives at `~/.config/gfunk/` — never in the repo. The cached token is written `0600`.
- Scopes start at **read-only** (`spreadsheets.readonly`, `drive.readonly`) and widen only
  deliberately; a test asserts the exact list, so a widening cannot land unnoticed.
- `credentials.json`, `token.json` and `.env` are gitignored, and `gitleaks` +
  `detect-private-key` run on every commit as the backstop.
- **Test fixtures are the real leak risk here**, not secrets — a real customer name, address
  or spreadsheet ID in a fixture is a PII commit that no secret scanner will catch. Fixtures
  must be synthetic. The `block-private-terms` hook is the machine-side half of that rule.

Found a security issue? Open a GitHub security advisory rather than a public issue.

## Install

```bash
uv sync
```

## Usage

First run, once per machine:

```bash
gfunk mount-up                              # guided: create your OAuth client, then sign in
```

`mount-up` prints the five Google Cloud console screens (with direct links — pass
`--project <id>` to point them at your project), finds the downloaded
`client_secret*.json` in your Downloads folders, checks it is a **Desktop app** client,
installs it to `~/.config/gfunk/credentials.json` mode 0600, and offers to sign you in.
`gfunk setup` is an alias, since that is what people type blind. Off a TTY it prints the
walkthrough and the scriptable form, `gfunk mount-up --client-secrets <file>`.

Already have a token? Everything else just works:

```bash
gfunk get-down                              # sign in (OAuth), on its own
gfunk snoop "Q3 report"                     # search Drive
gfunk sample <sheet-id> 'Sheet1!A1:D50'     # pull rows as records
gfunk mix <sheet-id> 'Sheet1!A1:D50' --key Name   # join Drive files onto rows
gfunk mothership                            # start the MCP server on stdio
```

Every command prints JSON on stdout and the replayable invocation on stderr, so
`gfunk snoop x | jq` works and the echoed line is safe to paste into a script.

Run any of them with arguments missing and you'll be prompted — except off a TTY, where
gfunk names the missing flag and exits rather than hanging a CI job.

### As an MCP server

```json
{
  "mcpServers": {
    "gfunk": { "command": "uv", "args": ["run", "--project", "/path/to/gfunk", "gfunk", "mothership"] }
  }
}
```

Tools are namespaced `gfunk__snoop`, `gfunk__sample`, `gfunk__mix`. **stdio only** — an HTTP
listener holding live Workspace credentials is attack surface this project doesn't need yet.

### The local cache

Bulk reads land in a SQLite database at `~/.local/share/gfunk/cache.db`, created `0600`.
SQLite rather than Parquet: stdlib, queryable without a second engine, and one file that can
be chmod-ed. It holds real Workspace content, so it lives outside the repo and is never
committed.

```bash
sqlite3 ~/.local/share/gfunk/cache.db \
  "SELECT service, kind, count(*) FROM records GROUP BY 1, 2"
```

## The vocabulary

| Command | What it does |
|---|---|
| `gfunk snoop` | Search across mail/drive/calendar |
| `gfunk dig` | Deep archive search — the slow, thorough one |
| `gfunk sample` | Pull a subset of records for analysis |
| `gfunk mix` | Join data across services |
| `gfunk hook` | Webhooks / event triggers |
| `gfunk loop` | Scheduled and recurring jobs |
| `gfunk bounce` | Export |
| `gfunk regulate` | Admin ops — permissions, cleanup, quotas |
| `gfunk mount-up` | Guided first-run: create, install, sign in |
| `gfunk get-down` | Sign in — the OAuth flow itself |
| `gfunk mothership` | Start the MCP server |

`mount-up`, `get-down`, `snoop`, `sample`, `mix` and `mothership` are implemented. The rest are the
planned surface.

## Development

```bash
uv sync
uv run pytest
pre-commit install
```

<!-- tree:start -->

```
gfunk/
|-- .github/
|   |-- workflows/
|   |   `-- ci.yml
|   `-- dependabot.yml
|-- src/
|   `-- gfunk/
|       |-- __init__.py
|       |-- __main__.py
|       |-- auth.py
|       |-- bootstrap.py
|       |-- browser.py
|       |-- cache.py
|       |-- cli.py
|       |-- mothership.py
|       `-- workspace.py
|-- tests/
|   |-- conftest.py
|   |-- test_auth.py
|   |-- test_bootstrap.py
|   |-- test_browser.py
|   |-- test_cache.py
|   |-- test_cli.py
|   |-- test_cli_mount_up.py
|   |-- test_mothership.py
|   `-- test_workspace.py
|-- .gitignore
|-- .pre-commit-config.yaml
|-- .ruff.toml
|-- pyproject.toml
|-- README.md
`-- uv.lock
```

<!-- tree:end -->
