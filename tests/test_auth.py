import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gfunk.auth import SCOPES, MissingClientSecretsError, get_down


@pytest.fixture
def client_secrets(tmp_path: Path) -> Path:
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({"installed": {"client_id": "x", "client_secret": "y"}}))
    return path


def fake_creds(*, valid: bool = True, expired: bool = False) -> MagicMock:
    creds = MagicMock()
    creds.valid = valid
    creds.expired = expired
    creds.refresh_token = "refresh"
    creds.to_json.return_value = json.dumps({"token": "cached"})
    return creds


def test_missing_client_secrets_names_the_expected_path(tmp_path: Path) -> None:
    missing = tmp_path / "credentials.json"
    with pytest.raises(MissingClientSecretsError) as exc:
        get_down(client_secrets=missing, token_path=tmp_path / "token.json")
    assert str(missing) in str(exc.value)


def test_first_run_completes_flow_and_caches_token(
    client_secrets: Path, tmp_path: Path
) -> None:
    token_path = tmp_path / "token.json"
    flow = MagicMock()
    flow.run_local_server.return_value = fake_creds()

    with patch(
        "gfunk.auth.InstalledAppFlow.from_client_secrets_file", return_value=flow
    ) as from_file:
        get_down(client_secrets=client_secrets, token_path=token_path)

    from_file.assert_called_once_with(str(client_secrets), SCOPES)
    assert json.loads(token_path.read_text()) == {"token": "cached"}


def test_scopes_are_sheets_and_drive_read_only() -> None:
    assert SCOPES == [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]


def test_cached_valid_token_skips_the_browser(
    client_secrets: Path, tmp_path: Path
) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"token": "cached"}))

    with (
        patch(
            "gfunk.auth.Credentials.from_authorized_user_file",
            return_value=fake_creds(),
        ),
        patch("gfunk.auth.InstalledAppFlow.from_client_secrets_file") as from_file,
    ):
        get_down(client_secrets=client_secrets, token_path=token_path)

    from_file.assert_not_called()


def test_expired_token_refreshes_instead_of_reauthorizing(
    client_secrets: Path, tmp_path: Path
) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"token": "stale"}))
    creds = fake_creds(valid=False, expired=True)

    with (
        patch("gfunk.auth.Credentials.from_authorized_user_file", return_value=creds),
        patch("gfunk.auth.InstalledAppFlow.from_client_secrets_file") as from_file,
    ):
        get_down(client_secrets=client_secrets, token_path=token_path)

    creds.refresh.assert_called_once()
    from_file.assert_not_called()
    assert json.loads(token_path.read_text()) == {"token": "cached"}
