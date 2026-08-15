from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "gfunk"
DEFAULT_CLIENT_SECRETS = DEFAULT_CONFIG_DIR / "credentials.json"
DEFAULT_TOKEN_PATH = DEFAULT_CONFIG_DIR / "token.json"


class MissingClientSecretsError(Exception):
    """gfunk ships no credentials; the user registers their own GCP OAuth client."""


def mount_up(
    client_secrets: Path = DEFAULT_CLIENT_SECRETS,
    token_path: Path = DEFAULT_TOKEN_PATH,
    scopes: list[str] | None = None,
) -> Credentials:
    """Complete first-run OAuth and cache the resulting token."""
    scopes = scopes if scopes is not None else SCOPES
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not client_secrets.exists():
            message = (
                f"No OAuth client secrets at {client_secrets}. Create a Desktop-app "
                "OAuth client in your own Google Cloud project, download its JSON, and "
                "save it there (or pass --client-secrets)."
            )
            raise MissingClientSecretsError(message)
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), scopes)
        creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    token_path.chmod(0o600)
    return creds
