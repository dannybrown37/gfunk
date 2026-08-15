import argparse
import json
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gfunk",
        description="Programmatic Google Workspace access — CLI and MCP server.",
    )
    parser.add_argument("--version", action="version", version=version("gfunk"))
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    mount_up = sub.add_parser(
        "mount-up", help="First-run OAuth against your own GCP client"
    )
    mount_up.add_argument(
        "--client-secrets",
        type=Path,
        help="Path to your downloaded OAuth client JSON",
    )
    mount_up.add_argument("--token", type=Path, help="Where to cache the token")

    snoop = sub.add_parser("snoop", help="Search Drive by file name")
    snoop.add_argument("term", nargs="?", help="What to search for")
    snoop.add_argument("--limit", type=int, default=50)

    sample = sub.add_parser("sample", help="Pull rows from a spreadsheet range")
    sample.add_argument("spreadsheet_id", nargs="?")
    sample.add_argument("cell_range", nargs="?", help="e.g. 'Sheet1!A1:D50'")
    sample.add_argument("--limit", type=int, default=None)

    mix = sub.add_parser("mix", help="Join Drive files onto sheet rows")
    mix.add_argument("spreadsheet_id", nargs="?")
    mix.add_argument("cell_range", nargs="?")
    mix.add_argument("--key", help="Column whose value is matched against Drive")
    mix.add_argument("--limit", type=int, default=None)

    sub.add_parser("mothership", help="Start the MCP server on stdio")
    return parser


def prompt(text: str, flag: str) -> str:
    """Ask for a missing value, but never off a TTY — CI must fail, not hang."""
    if not sys.stdin.isatty():
        message = f"Not a TTY, so nothing can be prompted for. Pass {flag}."
        raise SystemExit(message)
    return input(text).strip()


def emit(payload: Any, replay: str) -> int:
    print(json.dumps(payload, indent=2))
    print(f"\nRun again with:\n  {replay}", file=sys.stderr)
    return 0


def quote(value: str) -> str:
    from shlex import quote as shell_quote

    return shell_quote(value)


def cmd_mount_up(args: argparse.Namespace) -> int:
    from gfunk.auth import (
        DEFAULT_CLIENT_SECRETS,
        DEFAULT_TOKEN_PATH,
        MissingClientSecretsError,
        mount_up,
    )

    client_secrets = args.client_secrets or DEFAULT_CLIENT_SECRETS
    token_path = args.token or DEFAULT_TOKEN_PATH

    try:
        mount_up(client_secrets=client_secrets, token_path=token_path)
    except MissingClientSecretsError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Mounted up. Token cached at {token_path}")
    print("Run again with:")
    print(f"  gfunk mount-up --client-secrets {client_secrets} --token {token_path}")
    return 0


def cmd_snoop(args: argparse.Namespace) -> int:
    from gfunk.workspace import Workspace

    term = args.term or prompt("Search Drive for: ", "a search term")
    found = Workspace.connect().snoop(term, limit=args.limit)
    return emit(found, f"gfunk snoop {quote(term)} --limit {args.limit}")


def cmd_sample(args: argparse.Namespace) -> int:
    from gfunk.workspace import Workspace

    sheet = args.spreadsheet_id or prompt("Spreadsheet id: ", "a spreadsheet id")
    cell_range = args.cell_range or prompt("Range (e.g. A1:D50): ", "a range")
    rows = Workspace.connect().sample(sheet, cell_range, limit=args.limit)
    return emit(rows, f"gfunk sample {quote(sheet)} {quote(cell_range)}")


def cmd_mix(args: argparse.Namespace) -> int:
    from gfunk.workspace import Workspace

    sheet = args.spreadsheet_id or prompt("Spreadsheet id: ", "a spreadsheet id")
    cell_range = args.cell_range or prompt("Range (e.g. A1:D50): ", "a range")
    key = args.key or prompt("Column to match on: ", "--key")

    try:
        mixed = Workspace.connect().mix(sheet, cell_range, key, limit=args.limit)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    return emit(
        mixed,
        f"gfunk mix {quote(sheet)} {quote(cell_range)} --key {quote(key)}",
    )


def cmd_mothership(_: argparse.Namespace) -> int:
    from gfunk.mothership import run

    run()
    return 0


COMMANDS = {
    "mount-up": cmd_mount_up,
    "snoop": cmd_snoop,
    "sample": cmd_sample,
    "mix": cmd_mix,
    "mothership": cmd_mothership,
}


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        raise SystemExit(2)

    raise SystemExit(COMMANDS[args.command](args))
