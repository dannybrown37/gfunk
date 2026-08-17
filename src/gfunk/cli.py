import argparse
import json
import sys
import webbrowser
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gfunk",
        description="Programmatic Google Workspace access — CLI and MCP server.",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=40),
    )
    parser.add_argument("--version", action="version", version=version("gfunk"))
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # "setup" is the word a new user types blind; "mount-up" is the one we mean.
    mount_up = sub.add_parser(
        "mount-up",
        aliases=["setup", "login"],
        help="Create and install your own OAuth client, then sign in",
    )
    mount_up.add_argument(
        "--project", help="Your Google Cloud project id, for exact console links"
    )
    mount_up.add_argument(
        "--client-secrets",
        type=Path,
        help="Downloaded OAuth client JSON to install, skipping the interactive search",
    )
    mount_up.add_argument("--dest", type=Path, help="Where to install it")
    mount_up.add_argument(
        "--reinstall",
        action="store_true",
        help="Replace an already-installed client instead of reporting it",
    )
    mount_up.add_argument("--token", type=Path, help="Where the token is cached")
    mount_up.add_argument(
        "--steps",
        action="store_true",
        help="Print the console walkthrough and stop, set up or not",
    )
    mount_up.add_argument(
        "--no-sign-in", action="store_true", help="Install only; don't sign in"
    )

    # "browse" is the word a new user types blind; "snoop" is the one we mean.
    snoop = sub.add_parser(
        "snoop",
        aliases=["browse"],
        help="Walk your Drive folders — open or move files",
    )
    snoop.add_argument(
        "folder", nargs="?", help="Folder id to start in (default: root)"
    )
    snoop.add_argument("--limit", type=int, default=200)

    # "sheet"/"sample" are aliases; "vibe" is the one we mean.
    vibe = sub.add_parser(
        "vibe",
        aliases=["sample", "sheet"],
        help="Interactive spreadsheet viewer — filter and search",
    )
    vibe.add_argument("spreadsheet_id", nargs="?")
    vibe.add_argument("cell_range", nargs="?", help="e.g. 'Sheet1!A1:D50'")
    vibe.add_argument("--limit", type=int, default=None)
    vibe.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table"
    )
    vibe.add_argument("--raw", action="store_true", help="Plain table output (no TUI)")

    dig = sub.add_parser(
        "dig",
        aliases=["open"],
        help="Pick a recent Drive file and open it in your browser",
    )
    dig.add_argument("file_id", nargs="?", help="Drive file id")

    regulate = sub.add_parser(
        "regulate",
        aliases=["audit"],
        help="Audit who can reach the Drive files you own",
    )
    regulate.add_argument("--limit", type=int, default=200)
    regulate.add_argument(
        "--all", action="store_true", help="Include files you have not shared"
    )
    regulate.add_argument(
        "--json", action="store_true", help="Emit the audit as JSON instead of a table"
    )

    # "read" is the word a new user types blind; "peep" is the one we mean.
    peep = sub.add_parser(
        "peep",
        aliases=["read"],
        help="Read a Doc or Sheet in the terminal",
    )
    peep.add_argument("file_id", nargs="?", help="Drive file id")
    peep.add_argument("cell_range", nargs="?", help="e.g. 'Sheet1!A1:D50' (sheets)")
    peep.add_argument(
        "--format",
        dest="fmt",
        default=None,
        choices=["txt", "md", "html"],
        help="Doc output format (default: txt)",
    )
    peep.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table (sheets)"
    )
    peep.add_argument("--limit", type=int, default=None, help="Max rows (sheets)")
    peep.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write to file instead of stdout",
    )

    bounce = sub.add_parser(
        "bounce",
        aliases=["export"],
        help="Export a Google Workspace file (Sheets→CSV/JSON, Docs→txt/html)",
    )
    bounce.add_argument("file_id", nargs="?", help="Drive file id")
    bounce.add_argument(
        "--format",
        dest="fmt",
        help="Export format: csv, tsv, xlsx, json, txt, html, docx, md",
    )
    bounce.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write to file instead of stdout",
    )
    bounce.add_argument(
        "--tab",
        help="Sheet tab name (defaults to first tab)",
    )

    dj = sub.add_parser(
        "dj",
        aliases=["scripts"],
        help="Open your Apps Script dashboard, triggers, runs, or a project",
    )
    dj.add_argument(
        "page",
        nargs="?",
        help="'runs', 'triggers', or a script id to open directly",
    )

    mothership = sub.add_parser(
        "mothership",
        aliases=["mcp"],
        help="MCP server — install into clients or serve over stdio",
    )
    ms_sub = mothership.add_subparsers(dest="mothership_command", metavar="<action>")

    install = ms_sub.add_parser(
        "install",
        help="Add gfunk to a client's MCP config",
    )
    install.add_argument(
        "--client",
        choices=["claude", "copilot", "all"],
        default="all",
        help="Which client to configure (default: all)",
    )
    install.add_argument(
        "--global",
        dest="global_scope",
        action="store_true",
        help="Write to user-level config instead of project-level",
    )
    install.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove gfunk from the client config",
    )

    ms_sub.add_parser("serve", help="Start the MCP server on stdio")
    return parser


def prompt(text: str, flag: str) -> str:
    """Ask for a missing value, but never off a TTY — CI must fail, not hang."""
    if not sys.stdin.isatty():
        message = f"Not a TTY, so nothing can be prompted for. Pass {flag}."
        raise SystemExit(message)
    return input(text).strip()


def prompt_required(text: str, flag: str) -> str:
    """An empty answer is not a value; asking again beats querying for nothing."""
    while True:
        answer = prompt(text, flag)
        if answer:
            return answer
        print(f"Nothing entered. Ctrl-C to quit, or pass {flag}.", file=sys.stderr)


def emit(payload: Any, replay: str) -> int:
    print(json.dumps(payload, indent=2))
    print(f"\nRun again with:\n  {replay}", file=sys.stderr)
    return 0


def emit_table(rows: list[dict[str, str]], replay: str) -> int:
    from tabulate import tabulate

    if not rows:
        print("(no rows)")
    else:
        print(tabulate(rows, headers="keys", tablefmt="simple"))
    print(f"\nRun again with:\n  {replay}", file=sys.stderr)
    return 0


@contextmanager
def status(message: str) -> Iterator[None]:
    """Say what the wait is for.

    Silent network work is indistinguishable from a hang."""
    if not sys.stderr.isatty():
        yield
        return
    sys.stderr.write(f"{message}...")
    sys.stderr.flush()
    try:
        yield
    finally:
        sys.stderr.write("\r\033[2K")
        sys.stderr.flush()


def quote(value: str) -> str:
    from shlex import quote as shell_quote

    return shell_quote(value)


def sign_in(client_secrets: Path, token_path: Path) -> int:
    from gfunk.auth import MissingClientSecretsError, get_down

    try:
        get_down(client_secrets=client_secrets, token_path=token_path)
    except MissingClientSecretsError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Signed in. Token cached at {token_path}")
    return 0


def print_walkthrough(project: str | None) -> None:
    from gfunk.bootstrap import walkthrough

    print("\nCreating your own OAuth client — five screens, once per machine:\n")
    for step in walkthrough(project):
        print(f"{step.number}. {step.title}")
        if step.url:
            print(f"     {step.url}")
        for line in step.lines:
            print(f"     {line}")
        print()


def fzf_pick(
    candidates: list[Any], header: str, *, abort_ok: bool = False
) -> str | None:
    """fzf when it is on PATH; None means fall back to whatever the caller has."""
    import subprocess
    from shutil import which

    # fzf paints its interface on stderr and reads keys from /dev/tty. Capturing
    # stderr, or launching it with no terminal, gives an invisible picker that
    # silently swallows the session — which reads as a hang, not as a prompt.
    if not which("fzf") or not sys.stdin.isatty():
        return None
    result = subprocess.run(  # noqa: S603
        ["fzf", "--header", header, "--height", "40%", "--reverse"],  # noqa: S607
        input="\n".join(str(item) for item in candidates),
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    chosen = result.stdout.strip()
    if chosen:
        return chosen
    if abort_ok:
        return None  # browsing is optional; esc just means "done looking"
    raise KeyboardInterrupt  # esc in fzf means abort, not "ask me again"


def choose_download() -> Path | None:
    """Offer what was actually downloaded rather than asking for a path blind."""
    from gfunk.bootstrap import default_download_dirs, find_candidates

    prompt("Press enter once the JSON is downloaded: ", "--client-secrets")
    candidates = find_candidates(default_download_dirs())[:9]

    if not candidates:
        typed = prompt("Path to the downloaded JSON: ", "--client-secrets")
        return Path(typed).expanduser() if typed else None

    picked = fzf_pick(candidates, "Which downloaded OAuth client JSON?")
    if picked is not None:
        return Path(picked)

    print("\nFound:")
    for index, path in enumerate(candidates, start=1):
        print(f"  {index}. {path}")
    answer = prompt(
        f"Install which? [1-{len(candidates)}, or a path]: ", "--client-secrets"
    )

    if answer.isdigit() and 1 <= int(answer) <= len(candidates):
        return candidates[int(answer) - 1]
    return Path(answer).expanduser() if answer else None


def offer_sign_in(dest: Path, token: Path | None = None, *, skip: bool = False) -> int:
    from gfunk.auth import DEFAULT_TOKEN_PATH, token_state

    token = token or DEFAULT_TOKEN_PATH
    if token_state(token) in ("signed-in", "refreshable"):
        print(f"\nAlready signed in; token cached at {token}.")
        print("Try:")
        print("  gfunk snoop <name>")
        return 0

    if skip or not sys.stdin.isatty():
        print("\nNow sign in:")
        print("  gfunk mount-up")
        return 0
    if prompt("\nSign in now? [Y/n]: ", "--no-sign-in").lower().startswith("n"):
        print("\nWhen you are ready:")
        print("  gfunk mount-up")
        return 0
    return sign_in(client_secrets=dest, token_path=token)


def already_installed(dest: Path, token: Path | None = None) -> int:
    print(f"OAuth client already installed at {dest}.")
    print("Replace it with:")
    print(f"  gfunk mount-up --reinstall --dest {quote(str(dest))}")
    print("Re-read the console steps with:")
    print("  gfunk mount-up --steps")
    return offer_sign_in(dest, token)


def cmd_mount_up(args: argparse.Namespace) -> int:
    from gfunk.auth import DEFAULT_CLIENT_SECRETS
    from gfunk.bootstrap import classify, diagnose, install, project_of

    dest = args.dest or DEFAULT_CLIENT_SECRETS
    source = args.client_secrets

    if args.steps:
        print_walkthrough(args.project or project_of(dest))
        return 0

    if source is None and not args.reinstall:
        installed = classify(dest)
        if installed == "installed":
            return already_installed(dest, args.token)
        if installed != "missing":
            print(diagnose(installed, dest), file=sys.stderr)

    if source is None:
        print_walkthrough(args.project or project_of(dest))
        if not sys.stdin.isatty():
            print("Then install it with:")
            print(f"  gfunk mount-up --client-secrets <file.json> --dest {dest}")
            return 0
        source = choose_download()

    if source is None:
        print("Nothing to install.", file=sys.stderr)
        return 1

    try:
        install(source, dest)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"\nInstalled {source} -> {dest} (0600).")
    print("Run again with:")
    print(
        f"  gfunk mount-up --client-secrets {quote(str(source))} "
        f"--dest {quote(str(dest))}"
    )

    return offer_sign_in(dest, args.token, skip=args.no_sign_in)


def pick(found: list[dict[str, Any]], header: str) -> dict[str, Any] | None:
    """Fuzzy-find over what Drive returned; fzf does the filtering as you type."""
    labels = {f"{item['name']}\t{item.get('id', '')}": item for item in found}
    chosen = fzf_pick(list(labels), header, abort_ok=True)
    return labels[chosen] if chosen is not None else None


def open_in_browser(item: dict[str, Any]) -> None:
    from gfunk.browser import register as register_browser

    link = item.get("webViewLink") or f"https://drive.google.com/open?id={item['id']}"
    register_browser()
    if not webbrowser.open(link):
        print(f"Could not open a browser. The link is:\n  {link}", file=sys.stderr)


def browse(found: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick a hit and open it where the human can read it: their browser."""
    item = pick(found, "Open which in your browser?")
    if item is None:
        return None
    open_in_browser(item)
    return item


def can_browse() -> bool:
    from shutil import which

    return sys.stdin.isatty() and which("fzf") is not None


UP = "../"


def is_folder(item: dict[str, Any]) -> bool:
    from gfunk.workspace import FOLDER_MIME

    return bool(item.get("mimeType") == FOLDER_MIME)


def _natural_key(name: str) -> list[int | str]:
    """Split a string into text/number chunks for natural sort order."""
    import re

    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", name)]


def _fmt_date(iso: str) -> str:
    """'2024-06-15T10:30:00.000Z' → '2024-06-15'."""
    return iso[:10] if iso else ""


def snoop_entries(
    items: list[dict[str, Any]], *, up: bool
) -> dict[str, dict[str, Any] | None]:
    """Label every child the way `ls` would: a trailing slash means you can enter it."""
    entries: dict[str, dict[str, Any] | None] = {UP: None} if up else {}
    sorted_items = sorted(items, key=lambda i: _natural_key(i.get("name", "")))
    if not sorted_items:
        return entries
    max_name = max(
        len(i.get("name", "")) + (1 if is_folder(i) else 0) for i in sorted_items
    )
    for item in sorted_items:
        slash = "/" if is_folder(item) else ""
        name = f"{item['name']}{slash}"
        created = _fmt_date(item.get("createdTime", ""))
        modified = _fmt_date(item.get("modifiedTime", ""))
        label = f"{name:<{max_name}}  created {created}  modified {modified}"
        entries[label] = item
    return entries


def cmd_snoop(args: argparse.Namespace) -> int:
    """Walk Drive like a filesystem: descend into folders, escape to climb back."""
    from gfunk.workspace import Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    root = args.folder or "root"
    stack: list[tuple[str, str]] = [(root, "My Drive" if root == "root" else root)]

    if not can_browse():
        listing = workspace.children(root, limit=args.limit)
        return emit(listing, f"gfunk snoop {quote(root)} --limit {args.limit}")

    while stack:
        folder_id, _ = stack[-1]
        path = "/".join(name for _, name in stack)
        with status(f"Listing {path}"):
            items = workspace.children(folder_id, limit=args.limit)

        entries = snoop_entries(items, up=len(stack) > 1)
        chosen = fzf_pick(
            list(entries),
            f"{path} — enter opens, esc goes up",
            abort_ok=True,
        )

        if chosen is None or chosen == UP:
            stack.pop()
            continue

        item = entries[chosen]
        assert item is not None
        if is_folder(item):
            stack.append((item["id"], item["name"]))
            continue

        action = fzf_pick(SNOOP_ACTIONS, item["name"], abort_ok=True)
        if action is None or action == "Open in browser":
            open_in_browser(item)
            return emit(item, f"gfunk snoop {quote(folder_id)} --limit {args.limit}")
        if action == "Move":
            return _snoop_move(workspace, item)

    return 0


SNOOP_ACTIONS = ["Open in browser", "Move"]


def _snoop_move(workspace: Any, file_meta: dict[str, Any]) -> int:
    file_id = file_meta["id"]
    name = file_meta.get("name", file_id)
    parents = file_meta.get("parents", [])
    current_parent = parents[0] if parents else "root"

    parent_names = workspace.folder_names({current_parent})
    current_folder_name = parent_names.get(current_parent, current_parent)
    print(f"Moving {name} (currently in {current_folder_name})", file=sys.stderr)

    result = pick_destination(workspace)
    if result is None:
        return 0
    destination, dest_name = result

    workspace.move(file_id, add_parent=destination, remove_parent=current_parent)
    print(f"Moved {name} → {dest_name}", file=sys.stderr)
    return 0


def pick_file(
    workspace: Any,
    *,
    mime_types: set[str] | None = None,
    header: str = "Pick a file",
) -> dict[str, Any] | None:
    """fzf over recent Drive files; returns file metadata dict or None."""
    if not can_browse():
        return None
    with status("Loading recent files"):
        files = workspace.recent()
    if mime_types:
        files = [f for f in files if f.get("mimeType") in mime_types]
    if not files:
        return None
    labels = {f"{f['name']}\t{f['id']}": f for f in files}
    chosen = fzf_pick(list(labels), header, abort_ok=True)
    return labels[chosen] if chosen else None


def cmd_dig(args: argparse.Namespace) -> int:
    from gfunk.workspace import Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    file_id = args.file_id
    file_meta = None

    if not file_id:
        file_meta = pick_file(workspace)
        if not file_meta:
            return 0

    if file_meta:
        file_id = file_meta["id"]
    else:
        with status("Reading file metadata"):
            file_meta = workspace.file_meta(file_id)

    name = file_meta.get("name", file_id)
    open_in_browser(file_meta)
    print(f"Opened {name} in your browser.", file=sys.stderr)
    return emit(
        file_meta,
        f"gfunk dig {quote(file_id)}",
    )


def pick_spreadsheet(workspace: Any) -> str | None:
    """fzf over recent spreadsheets when interactive; None otherwise."""
    if not can_browse():
        return None
    with status("Finding your spreadsheets"):
        sheets = workspace.spreadsheets()
    if not sheets:
        return None
    labels = {f"{s['name']}\t{s['id']}": s["id"] for s in sheets}
    chosen = fzf_pick(list(labels), "Pick a spreadsheet", abort_ok=True)
    return labels[chosen] if chosen else None


def pick_range(workspace: Any, spreadsheet_id: str) -> str | None:
    """fzf over sheet tabs; returns 'TabName' or None."""
    if not can_browse():
        return None
    with status("Reading sheet tabs"):
        tabs: list[str] = workspace.sheet_tabs(spreadsheet_id)
    if not tabs:
        return None
    if len(tabs) == 1:
        return tabs[0]
    return fzf_pick(tabs, "Pick a tab", abort_ok=True)


def cmd_vibe(args: argparse.Namespace) -> int:
    from gfunk.workspace import Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    sheet = args.spreadsheet_id
    if not sheet:
        sheet = pick_spreadsheet(workspace)
    if not sheet:
        sheet = prompt_required("Spreadsheet id: ", "a spreadsheet id")

    cell_range = args.cell_range
    if not cell_range:
        cell_range = pick_range(workspace, sheet)
    if not cell_range:
        cell_range = prompt_required("Range (e.g. A1:D50): ", "a range")

    with status("Pulling rows"):
        rows = workspace.sample(sheet, cell_range, limit=args.limit)
    replay = f"gfunk vibe {quote(sheet)} {quote(cell_range)}"
    if args.json:
        return emit(rows, replay + " --json")
    if args.raw or not sys.stdin.isatty():
        return emit_table(rows, replay + " --raw")

    from gfunk.vibe import VibeApp

    print(f"\nRun again with:\n  {replay}", file=sys.stderr)
    VibeApp(rows).run()
    return 0


def _default_format(mime: str) -> str:
    from gfunk.workspace import DOC_MIME, SHEET_MIME

    if mime == SHEET_MIME:
        return "csv"
    if mime == DOC_MIME:
        return "txt"
    return "csv"


def _bounce_as_json(
    workspace: Any, file_id: str, tab: str | None, output: Path | None
) -> int:
    """Export a sheet as JSON records via the Sheets API (not Drive export)."""
    if not tab:
        tabs = workspace.sheet_tabs(file_id)
        tab = tabs[0] if tabs else "Sheet1"
    rows = workspace.sample(file_id, tab)
    payload = json.dumps(rows, indent=2)
    if output:
        output.write_text(payload)
        print(f"Wrote {len(rows)} records to {output}", file=sys.stderr)
    else:
        print(payload)
    return 0


PEEP_MIME_MAP = {
    "txt": "text/plain",
    "md": "text/plain",
    "html": "text/html",
}


def cmd_peep(args: argparse.Namespace) -> int:
    from gfunk.workspace import DOC_MIME, SHEET_MIME, Workspace

    peepable = {DOC_MIME, SHEET_MIME}

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    file_id = args.file_id
    file_meta = None

    if not file_id:
        file_meta = pick_file(
            workspace,
            mime_types=peepable,
            header="Pick a Doc or Sheet to read",
        )
        if not file_meta:
            return 0

    if file_meta:
        file_id = file_meta["id"]
    else:
        with status("Reading file metadata"):
            file_meta = workspace.file_meta(file_id)

    mime = file_meta.get("mimeType", "")
    name = file_meta.get("name", file_id)

    if mime not in peepable:
        print(
            f"{name} is not a Doc or Sheet. Use 'bounce' for other file types.",
            file=sys.stderr,
        )
        return 1

    if mime == SHEET_MIME:
        return _peep_sheet(args, workspace, file_id, name)
    return _peep_doc(args, workspace, file_id, name)


def _peep_doc(args: argparse.Namespace, workspace: Any, file_id: str, name: str) -> int:
    fmt = args.fmt or "txt"
    export_mime = PEEP_MIME_MAP[fmt]

    with status(f"Reading {name}"):
        data = workspace.export(file_id, export_mime)

    text = data.decode()
    if args.output:
        args.output.write_text(text)
        print(f"Wrote {len(text)} chars to {args.output}", file=sys.stderr)
    else:
        print(text, end="")

    replay = f"gfunk peep {quote(file_id)} --format {fmt}"
    if args.output:
        replay += f" -o {quote(str(args.output))}"
    print(f"\nRun again with:\n  {replay}", file=sys.stderr)
    return 0


def _peep_sheet(
    args: argparse.Namespace, workspace: Any, file_id: str, name: str
) -> int:
    cell_range = args.cell_range
    if not cell_range:
        cell_range = pick_range(workspace, file_id)
    if not cell_range:
        cell_range = prompt_required("Range (e.g. Sheet1 or A1:D50): ", "a range")

    with status(f"Reading {name}"):
        rows = workspace.sample(file_id, cell_range, limit=args.limit)

    replay = f"gfunk peep {quote(file_id)} {quote(cell_range)}"
    if args.json:
        if args.output:
            args.output.write_text(json.dumps(rows, indent=2))
            print(f"Wrote {len(rows)} records to {args.output}", file=sys.stderr)
            print(
                f"\nRun again with:\n  {replay} --json -o {quote(str(args.output))}",
                file=sys.stderr,
            )
            return 0
        return emit(rows, replay + " --json")
    if args.output:
        from tabulate import tabulate

        args.output.write_text(tabulate(rows, headers="keys", tablefmt="simple"))
        print(f"Wrote {len(rows)} rows to {args.output}", file=sys.stderr)
        print(
            f"\nRun again with:\n  {replay} -o {quote(str(args.output))}",
            file=sys.stderr,
        )
        return 0
    return emit_table(rows, replay)


def cmd_bounce(args: argparse.Namespace) -> int:
    import sys as _sys

    from gfunk.workspace import EXPORT_MIME_MAP, SHEET_MIME, Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    file_id = args.file_id
    file_meta = None

    if not file_id:
        file_meta = pick_file(workspace)
        if not file_meta:
            return 0

    if file_meta:
        file_id = file_meta["id"]
    else:
        with status("Reading file metadata"):
            file_meta = workspace.file_meta(file_id)

    mime = file_meta.get("mimeType", "")
    name = file_meta.get("name", file_id)
    fmt = args.fmt or _default_format(mime)

    if fmt == "json" and mime == SHEET_MIME:
        rc = _bounce_as_json(workspace, file_id, args.tab, args.output)
        replay = f"gfunk bounce {quote(file_id)} --format json"
        if args.output:
            replay += f" -o {quote(str(args.output))}"
        print(f"\nRun again with:\n  {replay}", file=_sys.stderr)
        return rc

    mime_map = EXPORT_MIME_MAP.get(mime, {})
    if fmt not in mime_map:
        valid = ", ".join(sorted(mime_map)) if mime_map else "(no exports available)"
        print(
            f"Cannot export {name} ({mime}) as {fmt}. Valid: {valid}",
            file=sys.stderr,
        )
        return 1

    with status(f"Exporting {name} as {fmt}"):
        data = workspace.export(file_id, mime_map[fmt])

    if args.output:
        args.output.write_bytes(data)
        print(f"Wrote {len(data)} bytes to {args.output}", file=sys.stderr)
    else:
        _sys.stdout.buffer.write(data)

    replay = f"gfunk bounce {quote(file_id)} --format {fmt}"
    if args.output:
        replay += f" -o {quote(str(args.output))}"
    print(f"\nRun again with:\n  {replay}", file=_sys.stderr)
    return 0


def cmd_mothership(args: argparse.Namespace) -> int:
    action = getattr(args, "mothership_command", None)
    if action is None:
        build_parser().parse_args(["mothership", "--help"])
        return 0
    if action == "install":
        return _mothership_install(args)
    return _mothership_serve()


def _mothership_install(args: argparse.Namespace) -> int:
    from gfunk.mcp_config import install, uninstall

    root = Path.cwd()
    fn = uninstall if args.uninstall else install
    paths = fn(root, client=args.client, global_scope=args.global_scope)
    verb = "Removed from" if args.uninstall else "Installed to"
    if not paths:
        print("Nothing to do — gfunk is not installed in those configs.")
        return 0
    for p in paths:
        print(f"{verb}: {p}")

    if not args.uninstall:
        flags = f" --client {args.client}" if args.client != "all" else ""
        if args.global_scope:
            flags += " --global"
        print(f"\nRun again with:\n  gfunk mothership install{flags}")
        print(f"Uninstall with:\n  gfunk mothership install --uninstall{flags}")
    return 0


def _mothership_serve() -> int:
    from gfunk.mothership import run

    if sys.stdin.isatty():
        print(
            "mothership serve speaks JSON-RPC over stdio — not meant for\n"
            "direct use. Install it into a client instead:\n"
            "  gfunk mothership install",
            file=sys.stderr,
        )
        return 1
    run()
    return 0


EXPOSURE_LABELS = {
    "public": "PUBLIC  ",
    "external": "EXTERNAL",
    "internal": "INTERNAL",
    "unknown": "UNKNOWN ",
    "private": "private ",
}


def _resolve_folders(
    files: list[dict[str, Any]],
    workspace: Any,
) -> tuple[dict[str, str], dict[str, str]]:
    parent_ids: set[str] = set()
    file_parents: dict[str, str] = {}
    for f in files:
        parents = f.get("parents", [])
        if parents:
            parent_ids.add(parents[0])
            file_parents[f["id"]] = parents[0]

    if parent_ids:
        with status("Resolving folder names"):
            folder_names = workspace.folder_names(parent_ids)
    else:
        folder_names = {}
    return file_parents, folder_names


def cmd_regulate(args: argparse.Namespace) -> int:
    from gfunk.regulate import audit, summarise
    from gfunk.workspace import Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()
    with status(f"Reading sharing on up to {args.limit} files you own"):
        files = workspace.sharing(limit=args.limit)

    rows = audit(files, shared_only=not args.all)
    file_parents, folder_names = _resolve_folders(files, workspace)

    if args.json:
        for row in rows:
            pid = file_parents.get(row["id"])
            row["folder"] = folder_names.get(pid, "") if pid else ""
        return emit(rows, f"gfunk regulate --limit {args.limit} --json")

    if not rows:
        print(f"Nothing is shared. Checked {len(files)} files you own.")
        return 0

    for row in rows:
        label = EXPOSURE_LABELS.get(str(row["exposure"]), str(row["exposure"]))
        pid = file_parents.get(row["id"])
        folder = folder_names.get(pid, "") if pid else ""
        path = f"{folder}/{row['name']}" if folder else row["name"]
        print(f"{label}  {path}")
        for reach in row["reached_by"]:
            print(f"            └─ {reach}")
        if row["link"]:
            print(f"            {row['link']}")

    counts = summarise(rows)
    tally = ", ".join(f"{count} {level}" for level, count in counts.items() if count)
    print(f"\n{tally or 'nothing shared'} — out of {len(files)} files you own.")
    print("\nRun again with:\n  gfunk regulate", file=sys.stderr)

    if can_browse() and rows:
        regulate_pick(rows)

    return 0


REGULATE_ACTIONS = ["Open in browser", "Move", "Delete", "Change permissions"]
WRITE_ACTIONS = frozenset({"Move", "Delete", "Change permissions"})


def regulate_pick(rows: list[dict[str, Any]]) -> None:
    labels: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = EXPOSURE_LABELS.get(str(row["exposure"]), str(row["exposure"]))
        labels[f"{label}  {row['name']}"] = row

    chosen = fzf_pick(list(labels), "Pick a file to act on", abort_ok=True)
    if chosen is None:
        return

    row = labels[chosen]
    action = fzf_pick(REGULATE_ACTIONS, row["name"], abort_ok=True)
    if action is None:
        return

    if action == "Open in browser":
        open_in_browser(row)
        return

    if action in WRITE_ACTIONS:
        print(
            f"{action} requires write scopes. Re-authenticate with:\n  gfunk mount-up",
            file=sys.stderr,
        )
        return


SELECT_HERE = ">> Move here <<"


def pick_destination(workspace: Any, start: str = "root") -> tuple[str, str] | None:
    """Snoop-style folder navigation; returns (folder_id, folder_name) or None."""
    stack: list[tuple[str, str]] = [(start, "My Drive" if start == "root" else start)]

    while stack:
        folder_id, _ = stack[-1]
        path = "/".join(name for _, name in stack)
        with status(f"Listing {path}"):
            items = workspace.children(folder_id, limit=200)

        folders = [i for i in items if is_folder(i)]
        entries: dict[str, dict[str, Any] | None] = {}
        entries[SELECT_HERE] = None
        if len(stack) > 1:
            entries[UP] = None
        for label, item in snoop_entries(folders, up=False).items():
            entries[label] = item

        chosen = fzf_pick(
            list(entries),
            f"Destination: {path}",
            abort_ok=True,
        )

        if chosen is None:
            return None

        if chosen == SELECT_HERE:
            return folder_id, path

        if chosen == UP:
            stack.pop()
            continue

        item = entries[chosen]
        assert item is not None
        stack.append((item["id"], item["name"]))

    return None


DJ_PAGES: dict[str, tuple[str, str]] = {
    "runs": (
        "https://script.google.com/home/executions",
        "Recent executions — see what ran, what failed, and when",
    ),
    "triggers": (
        "https://script.google.com/home/triggers",
        "Your triggers — what's scheduled, what's firing",
    ),
}
DJ_HOME = "https://script.google.com/home"
DJ_PROJECT = "https://script.google.com/d/{script_id}/edit"


def cmd_dj(args: argparse.Namespace) -> int:
    from gfunk.browser import register as register_browser

    page = args.page

    if page and page in DJ_PAGES:
        url, description = DJ_PAGES[page]
        register_browser()
        webbrowser.open(url)
        print(description)
        print(f"\nRun again with:\n  gfunk dj {page}", file=sys.stderr)
        return 0

    if page:
        url = DJ_PROJECT.format(script_id=page)
        register_browser()
        webbrowser.open(url)
        print(f"Opened script {page} in your browser.")
        print(f"\nRun again with:\n  gfunk dj {quote(page)}", file=sys.stderr)
        return 0

    if can_browse():
        pages = {
            "My Projects          All your Apps Script projects": "home",
            "Recent Runs          What ran, what failed, and when": "runs",
            "My Triggers          What's scheduled, what's firing": "triggers",
        }
        chosen = fzf_pick(list(pages), "Apps Script — pick a page", abort_ok=True)
        if chosen is None:
            return 0
        picked = pages[chosen]
        if picked == "home":
            url = DJ_HOME
        else:
            url, _ = DJ_PAGES[picked]
        register_browser()
        webbrowser.open(url)
        print(
            f"\nRun again with:\n  gfunk dj{'' if picked == 'home' else ' ' + picked}",
            file=sys.stderr,
        )
        return 0

    register_browser()
    webbrowser.open(DJ_HOME)
    print("Apps Script dashboard")
    print("\nPages:")
    print("  gfunk dj              Your projects")
    print("  gfunk dj runs         Recent executions")
    print("  gfunk dj triggers     Your triggers")
    print("  gfunk dj <script_id>  Open a specific project")
    return 0


COMMANDS = {
    "mount-up": cmd_mount_up,
    "setup": cmd_mount_up,
    "login": cmd_mount_up,
    "snoop": cmd_snoop,
    "browse": cmd_snoop,
    "dig": cmd_dig,
    "open": cmd_dig,
    "vibe": cmd_vibe,
    "sample": cmd_vibe,
    "sheet": cmd_vibe,
    "peep": cmd_peep,
    "read": cmd_peep,
    "bounce": cmd_bounce,
    "export": cmd_bounce,
    "regulate": cmd_regulate,
    "audit": cmd_regulate,
    "dj": cmd_dj,
    "scripts": cmd_dj,
    "mothership": cmd_mothership,
    "mcp": cmd_mothership,
}


def main(argv: list[str] | None = None) -> None:
    from googleapiclient.errors import HttpError

    from gfunk.auth import MissingClientSecretsError
    from gfunk.errors import explain

    try:
        parser = build_parser()
        args = parser.parse_args(argv)

        if args.command is None:
            parser.print_help()
            raise SystemExit(2)

        raise SystemExit(COMMANDS[args.command](args))
    except HttpError as exc:
        print(explain(exc), file=sys.stderr)
        raise SystemExit(1) from None
    except MissingClientSecretsError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from None
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130) from None
