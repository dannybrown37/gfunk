from pathlib import Path
from typing import Literal

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from gfunk.bootstrap import classify, diagnose
from gfunk.browser import hyperlink
from gfunk.browser import register as register_browser

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "gfunk"
DEFAULT_CLIENT_SECRETS = DEFAULT_CONFIG_DIR / "credentials.json"
DEFAULT_TOKEN_PATH = DEFAULT_CONFIG_DIR / "token.json"


def _scopes_changed(token_path: Path, expected: list[str]) -> bool:
    """True when the cached token was issued for different scopes."""
    import json

    try:
        stored = json.loads(token_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    saved = stored.get("scopes")
    if not saved:
        return False
    return set(expected) != set(saved)


TokenState = Literal["none", "signed-in", "refreshable", "stale"]


def token_state(
    token_path: Path = DEFAULT_TOKEN_PATH, scopes: list[str] | None = None
) -> TokenState:
    """What the cached token is still good for, without touching the network."""
    if not token_path.exists():
        return "none"
    expected = scopes if scopes is not None else SCOPES
    if _scopes_changed(token_path, expected):
        return "stale"
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), expected)
    except (ValueError, OSError):
        return "stale"

    if creds.valid:
        return "signed-in"
    return "refreshable" if creds.expired and creds.refresh_token else "stale"


def authorize_prompt() -> str:
    """A one-click link; the raw URL only where clicking is impossible anyway."""
    link = hyperlink("Authorize gfunk in Google", "{url}")
    return f"\nOpening your browser to sign in.\nIf nothing opens, visit:\n  {link}\n"


class MissingClientSecretsError(Exception):
    """gfunk ships no credentials; the user registers their own GCP OAuth client."""


def get_down(
    client_secrets: Path = DEFAULT_CLIENT_SECRETS,
    token_path: Path = DEFAULT_TOKEN_PATH,
    scopes: list[str] | None = None,
) -> Credentials:
    """Complete first-run OAuth and cache the resulting token."""
    scopes = scopes if scopes is not None else SCOPES
    creds: Credentials | None = None

    if token_path.exists():
        if _scopes_changed(token_path, scopes):
            token_path.unlink()
        else:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        kind = classify(client_secrets)
        if kind != "installed":
            raise MissingClientSecretsError(diagnose(kind, client_secrets))
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), scopes)
        register_browser()
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message=authorize_prompt(),
            success_message="gfunk is signed in. Close this tab.",
        )

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    token_path.chmod(0o600)
    return creds
