import argparse
import sys
from importlib.metadata import version
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gfunk",
        description="Programmatic Google Workspace access — CLI and MCP server.",
    )
    parser.add_argument("--version", action="version", version=version("gfunk"))
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    mount_up = sub.add_parser("mount-up", help="First-run OAuth against your own GCP client")
    mount_up.add_argument(
        "--client-secrets",
        type=Path,
        help="Path to your downloaded OAuth client JSON",
    )
    mount_up.add_argument("--token", type=Path, help="Where to cache the token")

    sub.add_parser("mothership", help="Start the MCP server (not implemented yet)")
    return parser


def cmd_mount_up(args: argparse.Namespace) -> int:
    from gfunk.auth import (
        DEFAULT_CLIENT_SECRETS,
        DEFAULT_TOKEN_PATH,
        MissingClientSecrets,
        mount_up,
    )

    client_secrets = args.client_secrets or DEFAULT_CLIENT_SECRETS
    token_path = args.token or DEFAULT_TOKEN_PATH

    try:
        mount_up(client_secrets=client_secrets, token_path=token_path)
    except MissingClientSecrets as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Mounted up. Token cached at {token_path}")
    print("Run again with:")
    print(f"  gfunk mount-up --client-secrets {client_secrets} --token {token_path}")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        raise SystemExit(2)

    if args.command == "mothership":
        print("gfunk mothership is not implemented yet.", file=sys.stderr)
        raise SystemExit(1)

    raise SystemExit(cmd_mount_up(args))
