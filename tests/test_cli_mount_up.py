import json
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from gfunk.cli import main


def client_json(tmp_path: Path, name: str = "client_secret_1.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps({"installed": {"client_id": "x", "client_secret": "y"}}))
    return path


def test_mount_up_prints_the_walkthrough_without_a_tty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    with patch("sys.stdin.isatty", return_value=False):
        code = main_code(["mount-up", "--project", "proj-1", "--dest", str(dest)])

    out = capsys.readouterr().out
    assert code == 0
    assert "project=proj-1" in out
    assert "Desktop app" in out
    assert "--client-secrets" in out, "non-interactive users need the scriptable form"


def test_mount_up_installs_a_named_file_without_prompting(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = client_json(tmp_path)
    dest = tmp_path / "config" / "credentials.json"

    with patch("sys.stdin.isatty", return_value=False):
        code = main_code(
            [
                "setup",
                "--client-secrets",
                str(source),
                "--dest",
                str(dest),
                "--token",
                str(tmp_path / "token.json"),
            ]
        )

    assert code == 0
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    assert "gfunk mount-up" in capsys.readouterr().out


def test_mount_up_rejects_a_service_account_key_with_a_useful_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "sa.json"
    source.write_text(json.dumps({"type": "service_account"}))
    dest = tmp_path / "config" / "credentials.json"

    with patch("sys.stdin.isatty", return_value=False):
        code = main_code(
            [
                "setup",
                "--client-secrets",
                str(source),
                "--dest",
                str(dest),
                "--token",
                str(tmp_path / "token.json"),
            ]
        )

    assert code == 1
    assert "service account" in capsys.readouterr().err
    assert not dest.exists()


def test_mount_up_picks_the_newest_download_when_confirmed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = client_json(tmp_path)
    dest = tmp_path / "config" / "credentials.json"

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", side_effect=["", "1", "n"], create=True),
        patch("gfunk.bootstrap.default_download_dirs", return_value=[tmp_path]),
        patch("gfunk.cli.fzf_pick", return_value=None),
    ):
        code = main_code(
            ["mount-up", "--dest", str(dest), "--token", str(tmp_path / "token.json")]
        )

    assert code == 0
    assert dest.exists()
    replay = capsys.readouterr().out
    assert f"--client-secrets {source}" in replay, (
        "an interactive run must echo a replayable one"
    )


def test_mount_up_offers_to_sign_in_and_runs_it(tmp_path: Path) -> None:
    source = client_json(tmp_path)
    dest = tmp_path / "config" / "credentials.json"

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", return_value="", create=True),
        patch("gfunk.cli.sign_in", return_value=0) as signed_in,
    ):
        code = main_code(
            [
                "mount-up",
                "--client-secrets",
                str(source),
                "--dest",
                str(dest),
                "--token",
                str(tmp_path / "token.json"),
            ]
        )

    assert code == 0
    signed_in.assert_called_once()


def test_mount_up_with_calendar_flag_requests_calendar_scope(tmp_path: Path) -> None:
    source = client_json(tmp_path)
    dest = tmp_path / "config" / "credentials.json"

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", return_value="", create=True),
        patch("gfunk.auth.get_down", return_value=None) as get_down,
    ):
        code = main_code(
            [
                "mount-up",
                "--with-calendar",
                "--client-secrets",
                str(source),
                "--dest",
                str(dest),
                "--token",
                str(tmp_path / "token.json"),
            ]
        )

    assert code == 0
    _client_secrets, kwargs = get_down.call_args
    from gfunk.auth import CALENDAR_SCOPE, SCOPES

    assert kwargs["scopes"] == [*SCOPES, CALENDAR_SCOPE]


def test_mount_up_without_with_calendar_requests_default_scopes(
    tmp_path: Path,
) -> None:
    source = client_json(tmp_path)
    dest = tmp_path / "config" / "credentials.json"

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", return_value="", create=True),
        patch("gfunk.auth.get_down", return_value=None) as get_down,
    ):
        code = main_code(
            [
                "mount-up",
                "--client-secrets",
                str(source),
                "--dest",
                str(dest),
                "--token",
                str(tmp_path / "token.json"),
            ]
        )

    assert code == 0
    _args, kwargs = get_down.call_args
    assert kwargs["scopes"] is None


def test_mount_up_declining_sign_in_leaves_the_next_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = client_json(tmp_path)
    dest = tmp_path / "config" / "credentials.json"

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", return_value="n", create=True),
        patch("gfunk.cli.sign_in") as signed_in,
    ):
        code = main_code(
            [
                "mount-up",
                "--client-secrets",
                str(source),
                "--dest",
                str(dest),
                "--token",
                str(tmp_path / "token.json"),
            ]
        )

    signed_in.assert_not_called()
    assert code == 0
    assert "gfunk mount-up" in capsys.readouterr().out


def test_setup_is_an_alias_for_mount_up(tmp_path: Path) -> None:
    source = client_json(tmp_path)
    dest = tmp_path / "config" / "credentials.json"

    with patch("sys.stdin.isatty", return_value=False):
        code = main_code(
            [
                "setup",
                "--client-secrets",
                str(source),
                "--dest",
                str(dest),
                "--token",
                str(tmp_path / "token.json"),
            ]
        )

    assert code == 0
    assert dest.exists()


def test_mount_up_reports_an_already_installed_client_instead_of_the_walkthrough(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    dest.parent.mkdir()
    dest.write_text(client_json(tmp_path).read_text())

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", return_value="n", create=True),
    ):
        code = main_code(
            ["mount-up", "--dest", str(dest), "--token", str(tmp_path / "token.json")]
        )

    out = capsys.readouterr().out
    assert code == 0
    assert str(dest) in out
    assert "Desktop app" not in out, "already set up; don't re-run the walkthrough"


def test_mount_up_says_nothing_to_do_when_already_signed_in(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    dest.parent.mkdir()
    dest.write_text(client_json(tmp_path).read_text())
    token = tmp_path / "config" / "token.json"

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", create=True) as asked,
        patch("gfunk.auth.token_state", return_value="signed-in"),
    ):
        code = main_code(["mount-up", "--dest", str(dest), "--token", str(token)])

    out = capsys.readouterr().out
    assert code == 0
    asked.assert_not_called(), "already signed in; there is nothing to ask"
    assert "Already signed in" in out
    assert "gfunk snoop" in out, "point at the next useful command instead"


def test_mount_up_with_calendar_reauths_a_token_missing_the_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    dest.parent.mkdir()
    dest.write_text(client_json(tmp_path).read_text())
    token = tmp_path / "config" / "token.json"
    token.write_text(json.dumps({"scopes": ["https://www.googleapis.com/auth/drive"]}))

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", return_value="", create=True),
        patch("gfunk.auth.token_state", return_value="signed-in"),
        patch("gfunk.cli.sign_in", return_value=0) as signed_in,
    ):
        code = main_code(
            ["mount-up", "--with-calendar", "--dest", str(dest), "--token", str(token)]
        )

    assert code == 0
    signed_in.assert_called_once_with(
        client_secrets=dest, token_path=token, with_calendar=True
    )
    assert "Already signed in" not in capsys.readouterr().out


def test_mount_up_with_calendar_skips_reauth_when_scope_already_granted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    dest.parent.mkdir()
    dest.write_text(client_json(tmp_path).read_text())
    token = tmp_path / "config" / "token.json"
    token.write_text(
        json.dumps(
            {
                "scopes": [
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/calendar.readonly",
                ]
            }
        )
    )

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", create=True) as asked,
        patch("gfunk.auth.token_state", return_value="signed-in"),
    ):
        code = main_code(
            ["mount-up", "--with-calendar", "--dest", str(dest), "--token", str(token)]
        )

    assert code == 0
    asked.assert_not_called()
    assert "Already signed in" in capsys.readouterr().out


def test_mount_up_still_offers_sign_in_when_the_token_is_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    dest.parent.mkdir()
    dest.write_text(client_json(tmp_path).read_text())

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", return_value="n", create=True) as asked,
        patch("gfunk.auth.token_state", return_value="stale"),
    ):
        code = main_code(["mount-up", "--dest", str(dest)])

    assert code == 0
    asked.assert_called_once()
    assert "gfunk mount-up" in capsys.readouterr().out


def test_mount_up_reinstall_forces_the_walkthrough(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    dest.parent.mkdir()
    dest.write_text(client_json(tmp_path).read_text())

    with patch("sys.stdin.isatty", return_value=False):
        code = main_code(["mount-up", "--dest", str(dest), "--reinstall"])

    assert code == 0
    assert "Desktop app" in capsys.readouterr().out


def test_mount_up_walks_through_when_the_installed_file_is_the_wrong_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    dest.parent.mkdir()
    dest.write_text(json.dumps({"type": "service_account"}))

    with patch("sys.stdin.isatty", return_value=False):
        code = main_code(["mount-up", "--dest", str(dest)])

    out = capsys.readouterr()
    assert code == 0
    assert "service account" in out.err
    assert "Desktop app" in out.out


def test_ctrl_c_exits_cleanly_without_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("gfunk.cli.build_parser", side_effect=KeyboardInterrupt):
        code = main_code([])

    assert code == 130
    assert "Traceback" not in capsys.readouterr().err


def test_download_selection_uses_fzf_when_available(tmp_path: Path) -> None:
    source = client_json(tmp_path)
    dest = tmp_path / "config" / "credentials.json"

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", side_effect=["", "n"], create=True),
        patch("gfunk.bootstrap.default_download_dirs", return_value=[tmp_path]),
        patch("gfunk.cli.fzf_pick", return_value=source) as picker,
    ):
        code = main_code(["mount-up", "--dest", str(dest)])

    assert code == 0
    assert picker.call_args.args[0] == [source]
    assert dest.exists()


def main_code(argv: list[str]) -> int:
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert isinstance(exc.value.code, int)
    return exc.value.code


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [("setup", "mount-up"), ("browse", "snoop")],
)
def test_the_word_a_new_user_types_blind_reaches_the_real_command(
    alias: str, canonical: str
) -> None:
    from gfunk.cli import COMMANDS, build_parser

    assert COMMANDS[alias] is COMMANDS[canonical]
    assert build_parser().parse_args([alias]).command == alias


def test_steps_prints_the_walkthrough_even_when_already_set_up(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    dest.parent.mkdir()
    dest.write_text(json.dumps({"installed": {"project_id": "gfunk-505623"}}))

    code = main_code(["mount-up", "--steps", "--dest", str(dest)])

    out = capsys.readouterr().out
    assert code == 0
    assert "Drive API" in out
    assert "project=gfunk-505623" in out, "the client JSON names its own project"


def test_already_installed_points_at_the_steps_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "config" / "credentials.json"
    dest.parent.mkdir()
    dest.write_text(client_json(tmp_path).read_text())

    with patch("sys.stdin.isatty", return_value=False):
        code = main_code(
            ["mount-up", "--dest", str(dest), "--token", str(tmp_path / "t.json")]
        )

    assert code == 0
    assert "gfunk mount-up --steps" in capsys.readouterr().out
