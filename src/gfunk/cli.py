import argparse
import json
import sys
import webbrowser
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Any

from gfunk.browser import open_in_browser


COMMAND_GROUPS: list[tuple[str, list[tuple[str, list[str], str]]]] = [
    (
        "the plug (auth)",
        [
            (
                "mount-up",
                ["setup", "login"],
                "Create/install your own OAuth client if needed + sign in",
            ),
        ],
    ),
    (
        "the stash (files)",
        [
            (
                "snoop",
                ["browse"],
                "Walk your Google Drive folders, act on docs and sheets",
            ),
            (
                "vibe",
                ["sheet"],
                "Open a spreadsheet in the interactive viewer (TUI)",
            ),
            ("drop", ["upload"], "Upload local files to Drive"),
            (
                "bounce",
                ["export"],
                "Export a Google Workspace file (Sheets→CSV/JSON, Docs→txt/html)",
            ),
        ],
    ),
    (
        "the game (management)",
        [
            (
                "regulate",
                ["audit"],
                "Audit and revoke who can reach your Drive files (TUI)",
            ),
            (
                "dubs",
                ["duplicates"],
                "Manage duplicate files on your Google Drive (TUI)",
            ),
            (
                "holla",
                ["emails"],
                "Email storage management and Drive backup (TUI)",
            ),
        ],
    ),
    (
        "the hustle (calendar)",
        [
            (
                "grind",
                ["agenda"],
                "Next week's Calendar events (needs `mount-up --with-calendar`)",
            ),
        ],
    ),
    (
        "the studio (apps)",
        [
            (
                "dj",
                ["scripts"],
                "Open your Apps Script dashboard/info; push/pull scripts",
            ),
            (
                "mothership",
                ["mcp"],
                "MCP server: install into clients or serve over stdio",
            ),
        ],
    ),
]


def _grouped_help(parser: argparse.ArgumentParser) -> str:
    import os
    import textwrap

    try:
        cols = os.get_terminal_size().columns
    except OSError:
        cols = 80
    indent = 30
    wrap_width = max(20, cols - indent)
    bold = "\033[1m"
    reset = "\033[0m"

    lines = [
        f"usage: {parser.prog} [-h] [--version] <command> ...\n",
        parser.description or "",
        "",
    ]
    for group_name, commands in COMMAND_GROUPS:
        lines.append(f"{bold}{group_name}:{reset}")
        for name, aliases, help_text in commands:
            label = f"  {name} ({', '.join(aliases)})"
            padding = max(2, indent - len(label))
            wrapped = textwrap.wrap(help_text, wrap_width)
            lines.append(f"{label}{' ' * padding}{wrapped[0]}")
            for cont in wrapped[1:]:
                lines.append(f"{' ' * indent}{cont}")
        lines.append("")
    lines.append(f"{bold}options:{reset}")
    lines.append(f"  {'--help':<{indent - 2}}show this help message and exit")
    lines.append(f"  {'--version':<{indent - 2}}show program's version number and exit")
    return "\n".join(lines) + "\n"


def _add_dubs_parser(sub: Any) -> None:
    dubs = sub.add_parser(
        "dubs",
        aliases=["duplicates"],
        help="Find duplicate files in Drive you own",
    )
    dubs.add_argument("--limit", type=int, default=1000)
    dubs.add_argument(
        "--json", action="store_true", help="Emit the report as JSON instead of a table"
    )


def _add_mount_up_parser(sub: Any) -> None:
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
    mount_up.add_argument(
        "--with-calendar",
        action="store_true",
        help="Also request read-only Calendar access, for `gfunk grind`",
    )


def _add_grind_parser(sub: Any) -> None:
    grind = sub.add_parser(
        "grind",
        aliases=["agenda"],
        help="Next week's Calendar events (opt-in: `mount-up --with-calendar`)",
    )
    grind.add_argument(
        "--days", type=int, default=7, help="How many days ahead to show (default: 7)"
    )
    grind.add_argument(
        "--since",
        type=int,
        default=0,
        metavar="DAYS",
        help="Also include this many days of past events (default: 0)",
    )
    grind.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table"
    )


def _add_snoop_parser(sub: Any) -> None:
    snoop = sub.add_parser(
        "snoop",
        aliases=["browse"],
        help="Walk folders, read files, view sheets — your Drive window",
    )
    snoop.add_argument(
        "target", nargs="?", help="File or folder id (default: root folder)"
    )
    snoop.add_argument(
        "cell_range", nargs="?", help="e.g. 'Sheet1!A1:D50' (sheets only)"
    )
    snoop.add_argument("--limit", type=int, default=None, help="Max items or rows")
    snoop.add_argument(
        "--format",
        dest="fmt",
        default=None,
        choices=["txt", "md", "html"],
        help="Doc output format (default: txt)",
    )
    snoop.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table (sheets)"
    )
    snoop.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write to file instead of stdout",
    )
    snoop.add_argument(
        "--open", action="store_true", help="Open in browser instead of reading"
    )
    snoop.add_argument(
        "--raw", action="store_true", help="Plain table output, no TUI (sheets)"
    )
    snoop.add_argument(
        "--peek",
        action="store_true",
        help="Quick, non-interactive preview (first lines or rows)",
    )


def _add_vibe_parser(sub: Any) -> None:
    vibe = sub.add_parser(
        "vibe",
        aliases=["sheet"],
        help="Open a spreadsheet in the interactive viewer (TUI)",
    )
    vibe.add_argument(
        "target", nargs="?", help="Spreadsheet id (default: pick from recent)"
    )
    vibe.add_argument("cell_range", nargs="?", help="e.g. 'Sheet1!A1:D50'")
    vibe.add_argument("--limit", type=int, default=None, help="Max rows")
    vibe.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table"
    )
    vibe.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write to file instead of stdout",
    )
    vibe.add_argument("--raw", action="store_true", help="Plain table output, no TUI")


def _add_drop_parser(sub: Any) -> None:
    drop = sub.add_parser(
        "drop",
        aliases=["upload"],
        help="Upload local files to Drive",
    )
    drop.add_argument("files", nargs="+", type=Path, help="Local files to upload")
    drop.add_argument("--to", help="Destination folder id (default: root, or pick)")


def _add_bounce_parser(sub: Any) -> None:
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


def _add_regulate_parser(sub: Any) -> None:
    regulate = sub.add_parser(
        "regulate",
        aliases=["audit"],
        help="Audit who can reach the Drive files you own",
    )
    regulate.add_argument("--limit", type=int, default=1000)
    regulate.add_argument(
        "--all", action="store_true", help="Include files you have not shared"
    )
    regulate.add_argument(
        "--json", action="store_true", help="Emit the audit as JSON instead of a table"
    )


def _add_holla_parser(sub: Any) -> None:
    holla = sub.add_parser(
        "holla",
        aliases=["email"],
        help="Browse Gmail labels/messages (TUI); filter by label/term to script it",
    )
    holla.add_argument("--label", help="Gmail label id to filter by, e.g. IMPORTANT")
    holla.add_argument(
        "--term", help="Search term to match against subject/from/snippet"
    )
    holla.add_argument("--limit", type=int, default=50)
    holla.add_argument(
        "--json",
        action="store_true",
        help="Emit the messages as JSON instead of a table",
    )


def _add_dj_parser(sub: Any) -> None:
    dj = sub.add_parser(
        "dj",
        aliases=["scripts"],
        help="Open your Apps Script dashboard, triggers, runs, or a project",
    )
    dj.add_argument(
        "page",
        nargs="?",
        help="'list', 'runs', 'triggers', 'pull', 'push', or a script id to open",
    )
    dj.add_argument(
        "script_id",
        nargs="?",
        help="Script id, required for 'pull' and 'push'",
    )
    dj.add_argument(
        "directory",
        nargs="?",
        type=Path,
        help="Local directory, required for 'push'",
    )
    dj.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table (list)"
    )
    dj.add_argument(
        "--out",
        type=Path,
        help="Output directory for 'pull' (default: ./<script_id>)",
    )
    dj.add_argument(
        "--yes",
        action="store_true",
        help="Skip the overwrite confirmation for 'push'",
    )


def _add_mothership_parser(sub: Any) -> None:
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
    install.add_argument(
        "--tools",
        help="Comma-separated list of tools to expose (default: all)",
    )

    serve = ms_sub.add_parser("serve", help="Start the MCP server on stdio")
    serve.add_argument(
        "--tools",
        help="Comma-separated list of tools to expose (default: all)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gfunk",
        description="Nuthin' but a G-Suite thang",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=40),
    )
    parser.format_help = lambda: _grouped_help(parser)  # type: ignore[method-assign]
    parser.add_argument("--version", action="version", version=version("gfunk"))
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    _add_mount_up_parser(sub)
    _add_grind_parser(sub)
    _add_snoop_parser(sub)
    _add_vibe_parser(sub)
    _add_drop_parser(sub)
    _add_bounce_parser(sub)
    _add_regulate_parser(sub)
    _add_dubs_parser(sub)
    _add_holla_parser(sub)
    _add_dj_parser(sub)
    _add_mothership_parser(sub)
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


def _read_single_key() -> str:
    """Read one keypress from stdin without waiting for Enter."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def confirm_yn(text: str) -> bool:
    """Ask for a single-keypress y/n confirmation, but never off a TTY."""
    if not sys.stdin.isatty():
        message = "Not a TTY, so nothing can be confirmed interactively."
        raise SystemExit(message)
    print(f"{text} [y/n] ", end="", file=sys.stderr, flush=True)
    key = _read_single_key()
    print(key, file=sys.stderr)
    return key.lower() == "y"


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


def sign_in(
    client_secrets: Path, token_path: Path, *, with_calendar: bool = False
) -> int:
    from gfunk.auth import CALENDAR_SCOPE, SCOPES, MissingClientSecretsError, get_down

    scopes = [*SCOPES, CALENDAR_SCOPE] if with_calendar else None
    try:
        get_down(client_secrets=client_secrets, token_path=token_path, scopes=scopes)
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
    candidates: list[Any],
    header: str,
    *,
    abort_ok: bool = False,
    preview: str | None = None,
) -> str | None:
    """fzf when it is on PATH; None means fall back to whatever the caller has.

    `preview` is a shell command shown in a side pane as the cursor moves.
    Candidates must be tab-delimited "id\\tlabel" pairs when it is given, so
    the command can address the highlighted row's id as `{1}`.
    """
    import subprocess
    from shutil import which

    # fzf paints its interface on stderr and reads keys from /dev/tty. Capturing
    # stderr, or launching it with no terminal, gives an invisible picker that
    # silently swallows the session — which reads as a hang, not as a prompt.
    if not which("fzf") or not sys.stdin.isatty():
        return None
    args = ["fzf", "--header", header, "--height", "40%", "--reverse"]
    if preview is not None:
        args += [
            "--delimiter",
            "\t",
            "--with-nth",
            "2..",
            "--preview",
            preview,
            "--preview-window",
            "right:60%:wrap",
        ]
    result = subprocess.run(  # noqa: S603
        args,
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


def fzf_pick_multi(
    candidates: list[Any],
    header: str,
    *,
    preview: str | None = None,
) -> list[str]:
    """Like `fzf_pick`, but tab toggles a row and enter confirms the set.

    Returns the selected lines, in fzf's own order. An empty list means
    nothing was on PATH, there was no TTY, or the picker was escaped —
    all "nothing selected" to a caller.
    """
    import subprocess
    from shutil import which

    if not which("fzf") or not sys.stdin.isatty():
        return []
    args = [
        "fzf",
        "--multi",
        "--header",
        header,
        "--height",
        "40%",
        "--reverse",
    ]
    if preview is not None:
        args += [
            "--delimiter",
            "\t",
            "--with-nth",
            "2..",
            "--preview",
            preview,
            "--preview-window",
            "right:60%:wrap",
        ]
    result = subprocess.run(  # noqa: S603
        args,
        input="\n".join(str(item) for item in candidates),
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line]


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


def offer_sign_in(
    dest: Path,
    token: Path | None = None,
    *,
    skip: bool = False,
    with_calendar: bool = False,
) -> int:
    from gfunk.auth import (
        CALENDAR_SCOPE,
        DEFAULT_TOKEN_PATH,
        granted_scopes,
        token_state,
    )

    token = token or DEFAULT_TOKEN_PATH
    needs_calendar_reauth = with_calendar and CALENDAR_SCOPE not in granted_scopes(
        token
    )
    if not needs_calendar_reauth and token_state(token) in ("signed-in", "refreshable"):
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
    return sign_in(client_secrets=dest, token_path=token, with_calendar=with_calendar)


def already_installed(
    dest: Path, token: Path | None = None, *, with_calendar: bool = False
) -> int:
    print(f"OAuth client already installed at {dest}.")
    print("Replace it with:")
    print(f"  gfunk mount-up --reinstall --dest {quote(str(dest))}")
    print("Re-read the console steps with:")
    print("  gfunk mount-up --steps")
    return offer_sign_in(dest, token, with_calendar=with_calendar)


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
            return already_installed(dest, args.token, with_calendar=args.with_calendar)
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

    return offer_sign_in(
        dest, args.token, skip=args.no_sign_in, with_calendar=args.with_calendar
    )


@dataclass
class GrindDay:
    date: date
    events: list[dict[str, Any]] = field(default_factory=list)
    all_day: list[str] = field(default_factory=list)
    total_hours: float = 0.0
    conflicts: int = 0
    time_spans: list[tuple[datetime, datetime]] = field(default_factory=list)


def _parse_dt(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


def grind_days(
    events: list[dict[str, Any]],
    *,
    start_date: date | None = None,
    num_days: int | None = None,
) -> list[GrindDay]:
    buckets: dict[date, GrindDay] = defaultdict(lambda: GrindDay(date=date.min))
    for event in events:
        start_raw = event.get("start", {})
        if "date" in start_raw and "dateTime" not in start_raw:
            d = date.fromisoformat(start_raw["date"])
            bucket = buckets[d]
            bucket.date = d
            bucket.all_day.append(event.get("summary", "(no title)"))
            continue

        dt_start = _parse_dt(start_raw["dateTime"])
        dt_end = _parse_dt(event.get("end", {}).get("dateTime", start_raw["dateTime"]))
        d = dt_start.date()
        bucket = buckets[d]
        bucket.date = d
        bucket.events.append(event)
        bucket.time_spans.append((dt_start, dt_end))
        hours = (dt_end - dt_start).total_seconds() / 3600
        bucket.total_hours += hours

    for bucket in buckets.values():
        spans = sorted(bucket.time_spans)
        for i in range(len(spans) - 1):
            if spans[i][1] > spans[i + 1][0]:
                bucket.conflicts += 1

    if start_date is not None and num_days is not None:
        for i in range(num_days):
            d = start_date + timedelta(days=i)
            if d not in buckets:
                buckets[d] = GrindDay(date=d)

    return sorted(buckets.values(), key=lambda d: d.date)


_BAR_START = 8
_BAR_END = 20
_BAR_SLOTS = (_BAR_END - _BAR_START) * 2  # half-hour slots


def grind_time_bar(
    spans: list[tuple[datetime, datetime]],
) -> str:
    slots = ["░"] * _BAR_SLOTS
    for start, end in spans:
        s_idx = max(0, (start.hour - _BAR_START) * 2 + start.minute // 30)
        e_idx = min(_BAR_SLOTS, (end.hour - _BAR_START) * 2 + end.minute // 30)
        for i in range(s_idx, e_idx):
            slots[i] = "█"
    return "".join(slots)


def _format_time(dt_str: str) -> str:
    dt = _parse_dt(dt_str)
    return dt.strftime("%-I:%M%p").lower()


_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_LOAD_LIGHT_HOURS = 2
_LOAD_HEAVY_HOURS = 5

_LOAD_LABEL = {
    "light": "\033[32m light \033[0m",
    "moderate": "\033[33m moderate \033[0m",
    "heavy": "\033[31m heavy \033[0m",
}


def _short_location(loc: str) -> str:
    if not loc:
        return ""
    return loc.split(",", maxsplit=1)[0]


def _grind_render(days: list[GrindDay]) -> str:
    lines: list[str] = []
    for day in days:
        day_name = _DAY_NAMES[day.date.weekday()]
        header = f"\033[1m{day_name} {day.date.strftime('%b %d')}\033[0m"

        if day.total_hours < _LOAD_LIGHT_HOURS:
            load = _LOAD_LABEL["light"]
        elif day.total_hours < _LOAD_HEAVY_HOURS:
            load = _LOAD_LABEL["moderate"]
        else:
            load = _LOAD_LABEL["heavy"]

        bar = grind_time_bar(day.time_spans)
        count = len(day.events)
        stats = f"{count} meeting{'s' if count != 1 else ''}, {day.total_hours:.1f}h"

        lines.append(f"{header}  {stats} {load}")
        lines.append(f"  8am {bar} 8pm")

        for ad in day.all_day:
            lines.append(f"  ▸ ALL DAY  {ad}")

        for ev in day.events:
            start_str = _format_time(ev["start"]["dateTime"])
            end_raw = ev.get("end", {}).get("dateTime", "")
            end_str = _format_time(end_raw) if end_raw else ""
            summary = ev.get("summary", "(no title)")
            loc = _short_location(ev.get("location", ""))
            line = f"  ▸ {start_str}-{end_str}  {summary}"
            if loc:
                line += f"  📍 {loc}"
            lines.append(line)

        if day.conflicts:
            lines.append(
                f"  ⚠ {day.conflicts} conflict{'s' if day.conflicts != 1 else ''}"
            )

        lines.append("")

    return "\n".join(lines)


def cmd_grind(args: argparse.Namespace) -> int:
    from gfunk.workspace import Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    if workspace.calendar is None:
        print("Calendar isn't connected yet.", file=sys.stderr)
        print("Opt in with:\n  gfunk mount-up --with-calendar", file=sys.stderr)
        return 1

    since = getattr(args, "since", 0)
    span = f"the next {args.days} days"
    if since:
        span = f"{since} days back and {args.days} forward"

    with status(f"Reading {span}"):
        events = workspace.grind(days=args.days, since_days=since)

    if args.json:
        return emit(events, f"gfunk grind --days {args.days} --since {since} --json")

    if not events:
        print(f"No events in {span}.")
        return 0

    from gfunk.grind_tui import GrindApp

    GrindApp(
        events=events,
        start_date=date.today() - timedelta(days=since),
        num_days=args.days + since,
    ).run()
    return 0


def pick(found: list[dict[str, Any]], header: str) -> dict[str, Any] | None:
    """Fuzzy-find over what Drive returned; fzf does the filtering as you type."""
    labels = {f"{item['name']}\t{item.get('id', '')}": item for item in found}
    chosen = fzf_pick(list(labels), header, abort_ok=True)
    return labels[chosen] if chosen is not None else None


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


_BYTES_PER_KIB = 1024


def _fmt_size(raw: str | int) -> str:
    """Human-readable file size from quotaBytesUsed."""
    b = int(raw) if raw else 0
    if b == 0:
        return "  —"
    size = float(b)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < _BYTES_PER_KIB:
            return f"{size:,.0f} {unit}" if unit == "B" else f"{size:,.1f} {unit}"
        size /= _BYTES_PER_KIB
    return f"{size:,.1f} PB"


def snoop_entries(
    items: list[dict[str, Any]],
    *,
    up: bool,
    mode: str = "home",
) -> dict[str, dict[str, Any] | None]:
    """Label every child the way `ls` would: a trailing slash means you can enter it."""
    entries: dict[str, dict[str, Any] | None] = {UP: None} if up else {}
    if mode == "home":
        sorted_items = sorted(items, key=lambda i: _natural_key(i.get("name", "")))
    elif mode == "recent":
        sorted_items = sorted(
            items, key=lambda i: i.get("modifiedTime", ""), reverse=True
        )
    elif mode == "largest":
        sorted_items = sorted(
            items,
            key=lambda i: int(i.get("quotaBytesUsed", 0) or 0),
            reverse=True,
        )
    else:
        sorted_items = list(items)
    if not sorted_items:
        return entries
    max_name = max(
        len(i.get("name", "")) + (1 if is_folder(i) else 0) for i in sorted_items
    )
    for item in sorted_items:
        slash = "/" if is_folder(item) else ""
        name = f"{item['name']}{slash}"
        if mode == "largest":
            size = _fmt_size(item.get("quotaBytesUsed", 0))
            modified = _fmt_date(item.get("modifiedTime", ""))
            label = f"{name:<{max_name}}  {size:>10}  modified {modified}"
        else:
            created = _fmt_date(item.get("createdTime", ""))
            modified = _fmt_date(item.get("modifiedTime", ""))
            label = f"{name:<{max_name}}  created {created}  modified {modified}"
        entries[label] = item
    return entries


def cmd_snoop(args: argparse.Namespace) -> int:
    """Walk folders, read files, view sheets — your Drive window."""
    from gfunk.workspace import Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    target = args.target

    if target:
        return _snoop_target(args, workspace, target)

    if getattr(args, "open", False):
        return _snoop_open_picker(workspace)

    return _snoop_walk(workspace, args)


def _snoop_target(args: argparse.Namespace, workspace: Any, target: str) -> int:
    from gfunk.workspace import DOC_MIME, FOLDER_MIME, SHEET_MIME

    with status("Reading file metadata"):
        meta = workspace.file_meta(target)
    mime = meta.get("mimeType", "")
    name = meta.get("name", target)

    if getattr(args, "peek", False):
        return _snoop_peek(workspace, meta)

    if mime == FOLDER_MIME:
        return _snoop_walk(workspace, args, start_id=target, start_name=name)

    if getattr(args, "open", False):
        open_in_browser(meta)
        print(f"Opened {name} in your browser.", file=sys.stderr)
        return emit(meta, f"gfunk snoop {quote(target)} --open")

    if mime == SHEET_MIME:
        return _snoop_sheet(args, workspace, target, name)

    if mime == DOC_MIME:
        return _snoop_doc(args, workspace, target, name)

    print(
        f"{name} is not a Doc or Sheet. Use 'bounce' for other file types.",
        file=sys.stderr,
    )
    return 1


def _snoop_open_picker(workspace: Any) -> int:
    file_meta = pick_file(workspace, mime_types=None, header="Pick a file")
    if not file_meta:
        return 0
    open_in_browser(file_meta)
    print(
        f"Opened {file_meta.get('name', '')} in your browser.",
        file=sys.stderr,
    )
    return emit(file_meta, f"gfunk snoop {quote(file_meta['id'])} --open")


SNOOP_ACTIONS_BASE = ["Open in browser", "Print", "Move", "Delete"]


def _snoop_actions(item: dict[str, Any]) -> list[str]:
    from gfunk.workspace import DOC_MIME, SHEET_MIME

    mime = item.get("mimeType", "")
    if mime == SHEET_MIME:
        return ["View (Vibe TUI)", *SNOOP_ACTIONS_BASE]
    if mime == DOC_MIME:
        return ["View", *SNOOP_ACTIONS_BASE]
    return list(SNOOP_ACTIONS_BASE)


def _snoop_walk(
    workspace: Any,
    args: argparse.Namespace,
    *,
    start_id: str = "root",
    start_name: str | None = None,
) -> int:
    limit = args.limit or 200
    name = start_name or ("My Drive" if start_id == "root" else start_id)

    if not can_browse():
        listing = workspace.children(start_id, limit=limit)
        return emit(listing, f"gfunk snoop {quote(start_id)} --limit {limit}")

    from gfunk.snoop_tui import SnoopApp

    SnoopApp(workspace, start_id=start_id, start_name=name, limit=limit).run()
    return 0


def _snoop_print(workspace: Any, file_meta: dict[str, Any]) -> int:
    from gfunk.workspace import DOC_MIME, SHEET_MIME

    file_id = file_meta["id"]
    name = file_meta.get("name", file_id)
    mime = file_meta.get("mimeType", "")

    if mime == DOC_MIME:
        data = workspace.export(file_id, "text/plain")
        print(data.decode(), end="")
        return 0

    if mime == SHEET_MIME:
        tab = pick_range(workspace, file_id)
        if not tab:
            return 0
        rows = workspace.sample(file_id, tab)
        return emit_table(rows, f"gfunk peep {quote(file_id)} {quote(tab)}")

    print(f"{name} is not a Doc or Sheet — cannot print.", file=sys.stderr)
    return 1


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


def _snoop_delete(workspace: Any, file_meta: dict[str, Any]) -> int:
    file_id = file_meta["id"]
    name = file_meta.get("name", file_id)

    if not confirm_yn(f"Trash '{name}'? This can be undone from Drive's trash."):
        print("Aborted.", file=sys.stderr)
        return 0

    workspace.trash(file_id)
    print(f"Trashed {name} (recoverable from Drive's trash)", file=sys.stderr)
    return 0


def snoop_preview_text(workspace: Any, file_meta: dict[str, Any]) -> str:
    """A fast, non-interactive look at a file — what a preview pane shows."""
    from googleapiclient.errors import HttpError

    from gfunk.workspace import DOC_MIME, SHEET_MIME

    file_id = file_meta["id"]
    name = file_meta.get("name", file_id)
    mime = file_meta.get("mimeType", "")

    try:
        if mime == DOC_MIME:
            data = workspace.export(file_id, "text/plain")
            return str(data.decode(errors="replace"))[:2000]
        if mime == SHEET_MIME:
            tabs = workspace.sheet_tabs(file_id)
            if not tabs:
                return f"{name} (empty spreadsheet)"
            rows = workspace.sample(file_id, tabs[0], limit=10)
            from tabulate import tabulate

            return str(tabulate(rows, headers="keys"))
    except HttpError:
        return "(preview unavailable)"
    else:
        return f"{name}\n{mime}"


def _snoop_peek(workspace: Any, file_meta: dict[str, Any]) -> int:
    print(snoop_preview_text(workspace, file_meta))
    return 0


SNOOP_MIME_MAP = {
    "txt": "text/plain",
    "md": "text/plain",
    "html": "text/html",
}


def _snoop_doc(
    args: argparse.Namespace, workspace: Any, file_id: str, name: str
) -> int:
    fmt = getattr(args, "fmt", None) or "txt"
    export_mime = SNOOP_MIME_MAP[fmt]

    with status(f"Reading {name}"):
        data = workspace.export(file_id, export_mime)

    text = data.decode()
    output = getattr(args, "output", None)
    if output:
        output.write_text(text)
        print(f"Wrote {len(text)} chars to {output}", file=sys.stderr)
    else:
        print(text, end="")

    replay = f"gfunk snoop {quote(file_id)} --format {fmt}"
    if output:
        replay += f" -o {quote(str(output))}"
    print(f"\nRun again with:\n  {replay}", file=sys.stderr)
    return 0


def cmd_vibe(args: argparse.Namespace) -> int:
    """Open a spreadsheet in the interactive viewer (TUI)."""
    from gfunk.workspace import Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    file_id = args.target
    if not file_id:
        file_id = pick_spreadsheet(workspace)
        if not file_id:
            return 0

    with status("Reading file metadata"):
        meta = workspace.file_meta(file_id)
    name = meta.get("name", file_id)

    return _snoop_sheet(args, workspace, file_id, name)


def _snoop_sheet(
    args: argparse.Namespace, workspace: Any, file_id: str, name: str
) -> int:
    cell_range = args.cell_range
    if not cell_range:
        cell_range = pick_range(workspace, file_id)
    if not cell_range:
        cell_range = prompt_required("Range (e.g. Sheet1 or A1:D50): ", "a range")

    with status(f"Reading {name}"):
        rows = workspace.sample(file_id, cell_range, limit=args.limit)

    replay = f"gfunk snoop {quote(file_id)} {quote(cell_range)}"
    output = getattr(args, "output", None)

    if getattr(args, "json", False):
        if output:
            output.write_text(json.dumps(rows, indent=2))
            print(f"Wrote {len(rows)} records to {output}", file=sys.stderr)
            print(
                f"\nRun again with:\n  {replay} --json -o {quote(str(output))}",
                file=sys.stderr,
            )
            return 0
        return emit(rows, replay + " --json")

    if output:
        from tabulate import tabulate

        output.write_text(tabulate(rows, headers="keys", tablefmt="simple"))
        print(f"Wrote {len(rows)} rows to {output}", file=sys.stderr)
        print(
            f"\nRun again with:\n  {replay} -o {quote(str(output))}",
            file=sys.stderr,
        )
        return 0

    if getattr(args, "raw", False) or not sys.stdin.isatty():
        return emit_table(rows, replay + " --raw")

    from gfunk.vibe import VibeApp

    print(f"\nRun again with:\n  {replay}", file=sys.stderr)
    VibeApp(rows).run()
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


def cmd_drop(args: argparse.Namespace) -> int:
    from gfunk.workspace import Workspace

    for f in args.files:
        if not f.exists():
            print(f"File not found: {f}", file=sys.stderr)
            return 1

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    parent = args.to
    if not parent:
        if can_browse():
            result = pick_destination(workspace)
            if result is None:
                return 0
            parent, _ = result
        else:
            parent = "root"

    for f in args.files:
        with status(f"Uploading {f.name}"):
            meta = workspace.upload(f, parent=parent)
        print(f"Uploaded {meta['name']} → {meta.get('id', '?')}", file=sys.stderr)

    replay = f"gfunk drop {' '.join(quote(str(f)) for f in args.files)}"
    if args.to:
        replay += f" --to {quote(args.to)}"
    print(f"\nRun again with:\n  {replay}", file=sys.stderr)
    return 0


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
    tools_csv = getattr(args, "tools", None)
    tools = set(tools_csv.split(",")) if tools_csv else None
    return _mothership_serve(tools=tools)


def _mothership_install(args: argparse.Namespace) -> int:
    from gfunk.mcp_config import install, uninstall

    root = Path.cwd()
    if args.uninstall:
        paths = uninstall(root, client=args.client, global_scope=args.global_scope)
    else:
        paths = install(
            root, client=args.client, global_scope=args.global_scope, tools=args.tools
        )
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


def _mothership_serve(*, tools: set[str] | None = None) -> int:
    from gfunk.mothership import run

    if sys.stdin.isatty():
        print(
            "mothership serve speaks JSON-RPC over stdio — not meant for\n"
            "direct use. Install it into a client instead:\n"
            "  gfunk mothership install",
            file=sys.stderr,
        )
        return 1
    run(tools=tools)
    return 0


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
    from gfunk.regulate import EXPOSURE_LABELS, audit, summarise
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
        row["folder"] = folder
        row["path"] = f"{folder}/{row['name']}" if folder else row["name"]
        print(f"{label}  {row['path']}")
        for reach in row["reached_by"]:
            print(f"            └─ {reach}")
        if row["link"]:
            print(f"            {row['link']}")

    counts = summarise(rows)
    tally = ", ".join(f"{count} {level}" for level, count in counts.items() if count)
    print(f"\n{tally or 'nothing shared'} — out of {len(files)} files you own.")
    print("\nRun again with:\n  gfunk regulate", file=sys.stderr)

    if sys.stdin.isatty() and rows:
        regulate_pick(rows, workspace)

    return 0


def regulate_pick(rows: list[dict[str, Any]], workspace: Any) -> None:
    """Open and Delete happen inside the TUI; other actions come back here unhandled."""
    from gfunk.regulate_tui import RegulateApp

    result = RegulateApp(rows, workspace).run()
    if result is None:
        return

    _, action = result
    print(f"{action} isn't wired up in regulate yet.", file=sys.stderr)


def _dubs_rows(
    files: list[dict[str, Any]], workspace: Any
) -> tuple[list[list[dict[str, Any]]], list[list[dict[str, Any]]]]:
    from gfunk.dubs import (
        find_exact_duplicates,
        find_possible_duplicates,
        sort_by_waste,
    )

    file_parents: dict[str, str] = {}
    parent_ids: set[str] = set()
    for f in files:
        parents = f.get("parents", [])
        if parents:
            parent_ids.add(parents[0])
            file_parents[f["id"]] = parents[0]

    if parent_ids:
        with status("Resolving folder paths"):
            folder_paths = workspace.folder_paths(parent_ids)
    else:
        folder_paths = {}

    def with_path(f: dict[str, Any]) -> dict[str, Any]:
        pid = file_parents.get(f["id"])
        folder = folder_paths.get(pid, "") if pid else ""
        path = f"{folder}/{f['name']}" if folder else f["name"]
        return {**f, "folder": folder, "path": path}

    exact = [
        [with_path(f) for f in group]
        for group in sort_by_waste(find_exact_duplicates(files))
    ]
    possible = [
        [with_path(f) for f in group] for group in find_possible_duplicates(files)
    ]
    return exact, possible


def _print_dubs_group(group: list[dict[str, Any]]) -> None:
    for f in group:
        print(f"    {f['path']}")
        if f.get("webViewLink"):
            print(f"      {f['webViewLink']}")


def _print_dubs_report(
    exact: list[list[dict[str, Any]]], possible: list[list[dict[str, Any]]]
) -> None:
    from gfunk.dubs import human_bytes, wasted_bytes

    if exact:
        print("Exact duplicates (identical content):\n")
        for group in exact:
            print(f"  {human_bytes(wasted_bytes(group))} reclaimable")
            _print_dubs_group(group)
        print()

    if possible:
        print("Possible duplicates (same name, can't verify content):\n")
        for group in possible:
            _print_dubs_group(group)
        print()

    total_waste = sum(wasted_bytes(g) for g in exact)
    print(
        f"{len(exact)} exact duplicate group(s), {human_bytes(total_waste)} "
        f"reclaimable. {len(possible)} possible group(s) to check by hand."
    )
    print("\nRun again with:\n  gfunk dubs", file=sys.stderr)


def cmd_dubs(args: argparse.Namespace) -> int:
    from gfunk.workspace import Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()
    with status(f"Reading up to {args.limit} files you own"):
        files = workspace.dubs(limit=args.limit)

    exact, possible = _dubs_rows(files, workspace)

    if args.json:
        payload = {"exact": exact, "possible": possible}
        return emit(payload, f"gfunk dubs --limit {args.limit} --json")

    if not exact and not possible:
        print(f"No duplicates found. Checked {len(files)} files you own.")
        return 0

    _print_dubs_report(exact, possible)

    if sys.stdin.isatty():
        dubs_pick(exact, possible, workspace)

    return 0


def dubs_pick(
    exact: list[list[dict[str, Any]]],
    possible: list[list[dict[str, Any]]],
    workspace: Any,
) -> None:
    from gfunk.dubs import flatten_groups
    from gfunk.dubs_tui import DubsApp

    DubsApp(flatten_groups(exact, possible), workspace).run()


def cmd_holla(args: argparse.Namespace) -> int:
    from gfunk.workspace import Workspace

    with status("Signing in to Google"):
        workspace = Workspace.connect()

    if not args.json and not args.label and not args.term and sys.stdin.isatty():
        from gfunk.holla_tui import HollaApp

        with status("Reading label counts"):
            labels = workspace.gmail_labels()
        HollaApp(labels, workspace).run()
        return 0

    with status(f"Reading up to {args.limit} messages"):
        messages = workspace.gmail_messages(
            label=args.label, term=args.term, limit=args.limit
        )

    replay = "gfunk holla"
    if args.label:
        replay += f" --label {args.label}"
    if args.term:
        replay += f" --term {args.term}"

    if args.json:
        return emit(messages, f"{replay} --json")

    if not messages:
        print("No messages found.")
        return 0

    rows = [
        {"from": m["from"], "subject": m["subject"], "snippet": m["snippet"]}
        for m in messages
    ]
    return emit_table(rows, replay)


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
    "triggers": (
        "https://script.google.com/home/triggers",
        "Your triggers — what's scheduled, what's firing",
    ),
}
DJ_HOME = "https://script.google.com/home"
DJ_PROJECT = "https://script.google.com/d/{script_id}/edit"


def _dj_list(*, as_json: bool) -> int:
    from gfunk.workspace import Workspace

    with status("Fetching scripts"):
        ws = Workspace.connect()
        projects = ws.scripts()

    if as_json:
        print(json.dumps(projects, indent=2))
        return 0

    if not projects:
        print("(no scripts found)")
        print(
            "\nRun again with:\n  gfunk dj list",
            file=sys.stderr,
        )
        return 0

    rows = [
        {
            "Name": p["name"],
            "Modified": p.get("modifiedTime", "")[:10],
            "ID": p["id"],
        }
        for p in projects
    ]
    return emit_table(rows, "gfunk dj list")


def _dj_runs(*, as_json: bool) -> int:
    from gfunk.workspace import Workspace

    with status("Fetching executions"):
        ws = Workspace.connect()
        processes = ws.processes()

    if as_json:
        print(json.dumps(processes, indent=2))
        return 0

    if not processes:
        print("(no recent executions)")
        print(
            "\nRun again with:\n  gfunk dj runs",
            file=sys.stderr,
        )
        return 0

    rows = [
        {
            "Project": p.get("projectName", ""),
            "Function": p.get("functionName", ""),
            "Status": p.get("processStatus", ""),
            "Started": p.get("startTime", "")[:19],
        }
        for p in processes
    ]
    return emit_table(rows, "gfunk dj runs")


def _dj_pull(script_id: str, *, out: Path | None) -> int:
    from gfunk.workspace import Workspace, write_script_files

    with status("Pulling script source"):
        ws = Workspace.connect()
        files = ws.script_content(script_id)

    if not files:
        print("(no source files found)", file=sys.stderr)
        return 0

    out_dir = out or Path(script_id)
    written = write_script_files(files, out_dir)

    print(f"Pulled {len(written)} file(s) to {out_dir}/")
    for path in written:
        print(f"  {path.name}")
    print(
        f"\nRun again with:\n  gfunk dj pull {quote(script_id)}",
        file=sys.stderr,
    )
    return 0


def _dj_push(script_id: str, directory: Path, *, skip_confirm: bool) -> int:
    from gfunk.workspace import Workspace, read_script_files

    if not directory.is_dir():
        print(f"Directory not found: {directory}", file=sys.stderr)
        return 1

    files = read_script_files(directory)
    if not files:
        print(f"(no script source files found in {directory})", file=sys.stderr)
        return 1

    if not skip_confirm:
        answer = prompt(
            f"This replaces the live content of script {script_id}. "
            "Type 'push' to continue: ",
            "--yes",
        )
        if answer != "push":
            print("Aborted.", file=sys.stderr)
            return 0

    with status("Pushing script source"):
        ws = Workspace.connect()
        ws.update_script_content(script_id, files)

    print(f"Pushed {len(files)} file(s) to script {script_id}")
    replay = f"gfunk dj push {quote(script_id)} {quote(str(directory))}"
    print(f"\nRun again with:\n  {replay}", file=sys.stderr)
    return 0


def _dj_pull_or_push(page: str, args: argparse.Namespace) -> int:
    script_id = getattr(args, "script_id", None)
    if page == "pull":
        if not script_id:
            print("Usage: gfunk dj pull <script_id> [--out DIR]", file=sys.stderr)
            return 1
        return _dj_pull(script_id, out=getattr(args, "out", None))

    directory = getattr(args, "directory", None)
    if not script_id or not directory:
        print("Usage: gfunk dj push <script_id> <directory>", file=sys.stderr)
        return 1
    return _dj_push(script_id, directory, skip_confirm=getattr(args, "yes", False))


def cmd_dj(args: argparse.Namespace) -> int:
    from gfunk.browser import register as register_browser

    page = args.page

    as_json = getattr(args, "json", False)
    handlers: dict[str, Callable[[], int]] = {
        "list": lambda: _dj_list(as_json=as_json),
        "runs": lambda: _dj_runs(as_json=as_json),
        "pull": lambda: _dj_pull_or_push("pull", args),
        "push": lambda: _dj_pull_or_push("push", args),
    }
    if page in handlers:
        return handlers[page]()

    if page:
        if page in DJ_PAGES:
            url, description = DJ_PAGES[page]
            print(description)
        else:
            url = DJ_PROJECT.format(script_id=page)
            print(f"Opened script {page} in your browser.")
        register_browser()
        webbrowser.open(url)
        print(f"\nRun again with:\n  gfunk dj {quote(page)}", file=sys.stderr)
        return 0

    if can_browse():
        pages = {
            "List Projects        Your scripts in a table": "list",
            "My Projects          All your Apps Script projects (browser)": "home",
            "Recent Runs          What ran, what failed, and when": "runs",
            "My Triggers          What's scheduled, what's firing (browser)": (
                "triggers"
            ),
        }
        chosen = fzf_pick(list(pages), "Apps Script — pick a page", abort_ok=True)
        if chosen is None:
            return 0
        picked = pages[chosen]
        if picked in ("list", "runs"):
            handler = _dj_list if picked == "list" else _dj_runs
            return handler(as_json=False)
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
    print("  gfunk dj list                     Your projects (table)")
    print("  gfunk dj runs                     Recent executions")
    print("  gfunk dj triggers                 Your triggers")
    print("  gfunk dj pull <script_id>         Pull source to a local directory")
    print("  gfunk dj push <script_id> <dir>   Push local source to the script")
    print("  gfunk dj <script_id>              Open a specific project")
    return 0


COMMANDS = {
    "mount-up": cmd_mount_up,
    "setup": cmd_mount_up,
    "login": cmd_mount_up,
    "snoop": cmd_snoop,
    "browse": cmd_snoop,
    "vibe": cmd_vibe,
    "sheet": cmd_vibe,
    "drop": cmd_drop,
    "upload": cmd_drop,
    "bounce": cmd_bounce,
    "export": cmd_bounce,
    "regulate": cmd_regulate,
    "audit": cmd_regulate,
    "dubs": cmd_dubs,
    "duplicates": cmd_dubs,
    "holla": cmd_holla,
    "email": cmd_holla,
    "dj": cmd_dj,
    "scripts": cmd_dj,
    "mothership": cmd_mothership,
    "mcp": cmd_mothership,
    "grind": cmd_grind,
    "agenda": cmd_grind,
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
