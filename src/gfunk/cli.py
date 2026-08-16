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

    # "setup" is the word a new user types blind; "mount-up" is the one we mean.
    mount_up = sub.add_parser(
        "mount-up",
        aliases=["setup"],
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
    mount_up.add_argument(
        "--no-sign-in", action="store_true", help="Install only; don't run get-down"
    )

    get_down = sub.add_parser(
        "get-down", help="Sign in — OAuth against your own GCP client"
    )
    get_down.add_argument(
        "--client-secrets",
        type=Path,
        help="Path to your installed OAuth client JSON",
    )
    get_down.add_argument("--token", type=Path, help="Where to cache the token")

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


def cmd_get_down(args: argparse.Namespace) -> int:
    from gfunk.auth import (
        DEFAULT_CLIENT_SECRETS,
        DEFAULT_TOKEN_PATH,
        MissingClientSecretsError,
        get_down,
    )

    client_secrets = args.client_secrets or DEFAULT_CLIENT_SECRETS
    token_path = args.token or DEFAULT_TOKEN_PATH

    try:
        get_down(client_secrets=client_secrets, token_path=token_path)
    except MissingClientSecretsError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Got down. Token cached at {token_path}")
    print("Run again with:")
    print(f"  gfunk get-down --client-secrets {client_secrets} --token {token_path}")
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


def fzf_pick(candidates: list[Path], header: str) -> Path | None:
    """fzf when it is on PATH; None means fall back to the numbered prompt."""
    import subprocess
    from shutil import which

    if not which("fzf"):
        return None
    result = subprocess.run(  # noqa: S603
        ["fzf", "--header", header, "--height", "40%", "--reverse"],  # noqa: S607
        input="\n".join(str(path) for path in candidates),
        capture_output=True,
        text=True,
        check=False,
    )
    chosen = result.stdout.strip()
    if not chosen:
        raise KeyboardInterrupt  # esc in fzf means abort, not "ask me again"
    return Path(chosen)


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
        return picked

    print("\nFound:")
    for index, path in enumerate(candidates, start=1):
        print(f"  {index}. {path}")
    answer = prompt(
        f"Install which? [1-{len(candidates)}, or a path]: ", "--client-secrets"
    )

    if answer.isdigit() and 1 <= int(answer) <= len(candidates):
        return candidates[int(answer) - 1]
    return Path(answer).expanduser() if answer else None


def offer_sign_in(dest: Path, *, skip: bool = False) -> int:
    if skip or not sys.stdin.isatty():
        print("\nNow sign in:")
        print("  gfunk get-down")
        return 0
    if prompt("\nSign in now? [Y/n]: ", "--no-sign-in").lower().startswith("n"):
        print("\nWhen you are ready:")
        print("  gfunk get-down")
        return 0
    return cmd_get_down(argparse.Namespace(client_secrets=dest, token=None))


def already_installed(dest: Path) -> int:
    print(f"OAuth client already installed at {dest}.")
    print("Replace it with:")
    print(f"  gfunk mount-up --reinstall --dest {quote(str(dest))}")
    return offer_sign_in(dest)


def cmd_mount_up(args: argparse.Namespace) -> int:
    from gfunk.auth import DEFAULT_CLIENT_SECRETS
    from gfunk.bootstrap import classify, diagnose, install

    dest = args.dest or DEFAULT_CLIENT_SECRETS
    source = args.client_secrets

    if source is None and not args.reinstall:
        installed = classify(dest)
        if installed == "installed":
            return already_installed(dest)
        if installed != "missing":
            print(diagnose(installed, dest), file=sys.stderr)

    if source is None:
        print_walkthrough(args.project)
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

    return offer_sign_in(dest, skip=args.no_sign_in)


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
    "setup": cmd_mount_up,
    "get-down": cmd_get_down,
    "snoop": cmd_snoop,
    "sample": cmd_sample,
    "mix": cmd_mix,
    "mothership": cmd_mothership,
}


def main(argv: list[str] | None = None) -> None:
    try:
        parser = build_parser()
        args = parser.parse_args(argv)

        if args.command is None:
            parser.print_help()
            raise SystemExit(2)

        raise SystemExit(COMMANDS[args.command](args))
    except KeyboardInterrupt, EOFError:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130) from None
