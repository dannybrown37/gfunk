"""Guided setup for the one thing gfunk cannot ship: your own OAuth client."""

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Kind = Literal["installed", "web", "service_account", "unknown", "missing", "malformed"]

PROJECT_PLACEHOLDER = "YOUR_PROJECT_ID"

CONSOLE = "https://console.cloud.google.com"
_URLS = {
    "sheets_api": f"{CONSOLE}/apis/library/sheets.googleapis.com",
    "drive_api": f"{CONSOLE}/apis/library/drive.googleapis.com",
    "consent": f"{CONSOLE}/auth/overview",
    "clients": f"{CONSOLE}/auth/clients",
}


@dataclass(frozen=True)
class Step:
    number: int
    title: str
    lines: list[str] = field(default_factory=list)
    url: str | None = None


def classify(path: Path) -> Kind:
    """Name the credential family, because every family fails differently."""
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError:
        return "missing"
    except json.JSONDecodeError, UnicodeDecodeError:
        return "malformed"

    if not isinstance(payload, dict):
        return "unknown"
    for marker in ("installed", "web"):
        if marker in payload:
            return marker
    return "service_account" if payload.get("type") == "service_account" else "unknown"


def diagnose(kind: Kind, path: Path) -> str:
    """Turn a wrong credential file into instructions for getting the right one."""
    messages = {
        "missing": (
            f"No OAuth client secrets at {path}. "
            "Run `gfunk mount-up` to be walked through creating one."
        ),
        "malformed": (
            f"{path} is not valid JSON. Re-download the client JSON "
            "from the Google console, or run `gfunk mount-up`."
        ),
        "web": (
            f"{path} is a Web application OAuth client, but gfunk signs in from "
            "your terminal. Create the client again choosing application type "
            "'Desktop app', then run `gfunk mount-up`."
        ),
        "service_account": (
            f"{path} is a service account key, not an OAuth client. Service "
            "accounts have their own identity and see only files explicitly "
            "shared with them; gfunk signs in as you. Run `gfunk mount-up` to "
            "create a Desktop app OAuth client instead."
        ),
        "unknown": (
            f"{path} is not an OAuth client JSON — it has no 'installed' "
            "section. Run `gfunk mount-up` to download the right file."
        ),
    }
    if kind == "installed":
        message = (
            "'installed' is the credential gfunk wants; there is nothing to diagnose."
        )
        raise ValueError(message)
    return messages[kind]


def project_of(path: Path) -> str | None:
    """The client JSON names its own project; asking the user for it is redundant."""
    try:
        payload = json.loads(path.read_text())
    except OSError, json.JSONDecodeError, UnicodeDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    section = payload.get("installed") or payload.get("web") or {}
    project = section.get("project_id") if isinstance(section, dict) else None
    return str(project) if project else None


def console_urls(project: str | None) -> dict[str, str]:
    suffix = f"?project={project}" if project else ""
    return {name: url + suffix for name, url in _URLS.items()}


def walkthrough(project: str | None) -> list[Step]:
    urls = console_urls(project)
    named = project or "your Google Cloud project"
    return [
        Step(
            1,
            f"Enable the Sheets API in {named}",
            [
                "It should read 'API enabled'. If it offers 'Enable', click that.",
                "Check the project picker up top really says this project.",
            ],
            urls["sheets_api"],
        ),
        Step(
            2,
            "Enable the Drive API — a separate switch, not covered by step 1",
            [
                "Every Google API is enabled per project, one at a time.",
                "gfunk needs both: Sheets to read rows, Drive to find the files.",
                "Skip this and every `gfunk snoop` fails with 403 accessNotConfigured.",
            ],
            urls["drive_api"],
        ),
        Step(
            3,
            "Configure the OAuth consent screen (first time only)",
            [
                "Get started -> App name 'gfunk' -> your email -> Audience: External.",
                "Then Audience -> Test users -> + Add users -> your account.",
                "Skipping the test user step causes access_denied later:",
                "in Testing mode only listed test users may sign in.",
            ],
            urls["consent"],
        ),
        Step(
            4,
            "Create the client",
            [
                "+ Create client -> Application type: Desktop app -> Create.",
                "'Desktop app' matters: a Web client cannot finish this flow.",
                "Download JSON in the dialog that follows.",
            ],
            urls["clients"],
        ),
        Step(
            5,
            "Install the downloaded JSON",
            [
                "Save it as ~/.config/gfunk/credentials.json:",
                "  mkdir -p ~/.config/gfunk && chmod 700 ~/.config/gfunk",
                "  mv ~/Downloads/client_secret*.json ~/.config/gfunk/credentials.json",
                "  chmod 600 ~/.config/gfunk/credentials.json",
                "Or let gfunk do it:",
                "  gfunk mount-up --client-secrets <path/to/downloaded.json>",
                "Then: gfunk get-down",
            ],
        ),
    ]


def default_download_dirs() -> list[Path]:
    """Downloads, plus the Windows-side one that WSL users actually download into."""
    dirs = [Path.home() / "Downloads"]
    dirs.extend(sorted(Path("/mnt/c/Users").glob("*/Downloads")))
    return dirs


def find_candidates(dirs: list[Path]) -> list[Path]:
    found = [
        path for directory in dirs for path in directory.glob("client_secret*.json")
    ]
    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)


def install(source: Path, dest: Path) -> Path:
    kind = classify(source)
    if kind != "installed":
        raise ValueError(diagnose(kind, source))

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.parent.chmod(0o700)
    shutil.copyfile(source, dest)
    dest.chmod(0o600)
    return dest
