import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from gfunk import auth
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
    creds.to_json.return_value = json.dumps({"token": "cached", "scopes": SCOPES})
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
    assert json.loads(token_path.read_text()) == {"token": "cached", "scopes": SCOPES}


def test_scopes_include_sheets_drive_and_script_processes() -> None:
    assert SCOPES == [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/script.processes",
    ]


def test_cached_valid_token_skips_the_browser(
    client_secrets: Path, tmp_path: Path
) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"token": "cached", "scopes": SCOPES}))

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
    token_path.write_text(json.dumps({"token": "stale", "scopes": SCOPES}))
    creds = fake_creds(valid=False, expired=True)

    with (
        patch("gfunk.auth.Credentials.from_authorized_user_file", return_value=creds),
        patch("gfunk.auth.InstalledAppFlow.from_client_secrets_file") as from_file,
    ):
        get_down(client_secrets=client_secrets, token_path=token_path)

    creds.refresh.assert_called_once()
    from_file.assert_not_called()
    assert json.loads(token_path.read_text()) == {"token": "cached", "scopes": SCOPES}


@pytest.mark.parametrize(
    ("expected", "refresh_token", "valid", "expired"),
    [
        ("signed-in", "r", True, False),
        ("refreshable", "r", False, True),
        ("stale", None, False, True),
    ],
)
def test_token_state_names_what_the_cached_token_can_still_do(
    tmp_path: Path,
    expected: str,
    refresh_token: str | None,
    *,
    valid: bool,
    expired: bool,
) -> None:
    token = tmp_path / "token.json"
    token.write_text(json.dumps({"scopes": SCOPES}))
    creds = SimpleNamespace(valid=valid, expired=expired, refresh_token=refresh_token)

    with patch("gfunk.auth.Credentials.from_authorized_user_file", return_value=creds):
        assert auth.token_state(token) == expected


def test_token_state_is_stale_when_scopes_narrower_than_required(
    tmp_path: Path,
) -> None:
    token = tmp_path / "token.json"
    token.write_text(
        json.dumps(
            {
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            }
        )
    )

    assert auth.token_state(token) == "stale"


def test_scope_mismatch_forces_reauth(
    client_secrets: Path,
    tmp_path: Path,
) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text(
        json.dumps(
            {
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            }
        )
    )

    flow = MagicMock()
    flow.run_local_server.return_value = fake_creds()

    with patch(
        "gfunk.auth.InstalledAppFlow.from_client_secrets_file", return_value=flow
    ) as from_file:
        get_down(client_secrets=client_secrets, token_path=token_path)

    from_file.assert_called_once()
    assert not token_path.read_text().startswith(
        '{"scopes": ["https://www.googleapis.com/auth/drive.readonly"]'
    )


def test_token_state_is_none_without_a_token_file(tmp_path: Path) -> None:
    assert auth.token_state(tmp_path / "missing.json") == "none"


def test_token_state_treats_an_unreadable_token_as_stale(tmp_path: Path) -> None:
    token = tmp_path / "token.json"
    token.write_text("not json")
    assert auth.token_state(token) == "stale"
