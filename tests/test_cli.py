import argparse
import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gfunk.cli import main


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    # Fixed argv, no shell: the only variable part is this file's own literals.
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "gfunk", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env={"PATH": "/usr/bin:/bin", "HOME": str(cwd)},
        check=False,
    )


def test_version_matches_package_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == version("gfunk")


def test_version_works_with_no_config_and_no_credentials(tmp_path: Path) -> None:
    result = run_cli("--version", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == version("gfunk")


def test_no_arguments_prints_usage_not_a_bare_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main([])
    out = capsys.readouterr().out
    assert "usage:" in out
    assert "mount-up" in out


@pytest.mark.parametrize("verb", ["mount-up", "mothership", "snoop", "sample", "dj"])
def test_known_verbs_are_registered(
    verb: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main([])
    assert verb in capsys.readouterr().out


def test_prompting_off_a_tty_fails_loudly_instead_of_hanging(tmp_path: Path) -> None:
    # A prompt that blocks in CI burns the job's whole timeout with no log line.
    result = run_cli("sample", cwd=tmp_path)
    assert result.returncode != 0
    assert result.stderr, "must explain the failure, not hang silently"


def test_every_verb_has_a_handler() -> None:
    from gfunk.cli import COMMANDS, build_parser

    parser = build_parser()
    actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    assert set(actions[0].choices) == set(COMMANDS)


def test_snoop_browse_opens_the_chosen_files_web_link() -> None:
    from gfunk.cli import browse

    found = [
        {"id": "a", "name": "Budget 2026", "webViewLink": "https://docs.google.com/a"},
        {"id": "b", "name": "Other", "webViewLink": "https://docs.google.com/b"},
    ]

    with (
        patch("gfunk.cli.fzf_pick", return_value="Other\tb"),
        patch("webbrowser.open", return_value=True) as opened,
    ):
        browse(found)

    opened.assert_called_once_with("https://docs.google.com/b")


def test_snoop_browse_does_nothing_when_the_picker_is_escaped() -> None:
    from gfunk.cli import browse

    with (
        patch("gfunk.cli.fzf_pick", return_value=None),
        patch("webbrowser.open") as opened,
    ):
        browse([{"id": "a", "name": "Budget", "webViewLink": "https://x"}])

    opened.assert_not_called()


def test_snoop_browse_prints_the_link_when_no_browser_opens(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from gfunk.cli import browse

    with (
        patch("gfunk.cli.fzf_pick", return_value="Budget\ta"),
        patch("webbrowser.open", return_value=False),
    ):
        browse([{"id": "a", "name": "Budget", "webViewLink": "https://x"}])

    assert "https://x" in capsys.readouterr().err


def test_an_empty_answer_asks_again_instead_of_querying_for_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from gfunk.cli import prompt_required

    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("gfunk.cli.input", side_effect=["", "   ", "budget"], create=True),
    ):
        assert prompt_required("Search Drive for: ", "a search term") == "budget"

    assert capsys.readouterr().err.count("Nothing entered") == 2


@pytest.mark.parametrize("tty", [True, False])
def test_status_only_writes_to_a_terminal(
    *, tty: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    from gfunk.cli import status

    with (
        patch("sys.stderr.isatty", return_value=tty),
        status("Fetching your newest Drive files"),
    ):
        pass

    err = capsys.readouterr().err
    assert ("Fetching your newest Drive files" in err) is tty
    assert "\n" not in err, "the status line is transient, not scrollback"


def test_fzf_ui_is_not_captured_away_from_the_terminal() -> None:
    """fzf draws on stderr; capturing it leaves an invisible picker eating keys."""
    import subprocess

    from gfunk.cli import fzf_pick

    done = subprocess.CompletedProcess(args=[], returncode=0, stdout="alpha\n")
    with (
        patch("shutil.which", return_value="/usr/bin/fzf"),
        patch("sys.stdin.isatty", return_value=True),
        patch("subprocess.run", return_value=done) as ran,
    ):
        assert fzf_pick(["alpha", "beta"], "pick") == "alpha"

    kwargs = ran.call_args.kwargs
    assert kwargs.get("capture_output") is not True, "this hides the picker"
    assert kwargs.get("stderr") is None, "stderr is the picker's canvas"


def test_fzf_is_skipped_entirely_off_a_tty() -> None:
    """No terminal means no picker; blocking on one is the hang we are fixing."""
    from gfunk.cli import fzf_pick

    with (
        patch("shutil.which", return_value="/usr/bin/fzf"),
        patch("sys.stdin.isatty", return_value=False),
        patch("subprocess.run") as ran,
    ):
        assert fzf_pick(["alpha"], "pick") is None

    ran.assert_not_called()


def regulate_args(**overrides: object) -> argparse.Namespace:
    defaults = {"limit": 200, "all": False, "json": False}
    return argparse.Namespace(**{**defaults, **overrides})


def owned(name: str, permissions: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": name,
        "name": name,
        "webViewLink": f"https://x/{name}",
        "owners": [{"emailAddress": "danny@example.com"}],
        "permissions": [
            {"type": "user", "role": "owner", "emailAddress": "danny@example.com"},
            *permissions,
        ],
    }


def test_regulate_reports_the_worst_exposure_first(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from gfunk.cli import cmd_regulate

    workspace = MagicMock()
    workspace.sharing.return_value = [
        owned("quiet", [{"type": "user", "role": "reader", "emailAddress": "s@o.com"}]),
        owned("loud", [{"type": "anyone", "role": "reader"}]),
    ]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=False),
    ):
        code = cmd_regulate(regulate_args())

    out = capsys.readouterr().out
    assert code == 0
    assert out.index("loud") < out.index("quiet"), "public outranks external"
    assert "anyone with the link" in out, "say who is reached, not just how bad"


def test_regulate_hides_unshared_files_unless_asked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from gfunk.cli import cmd_regulate

    workspace = MagicMock()
    workspace.sharing.return_value = [
        owned("private-thing", []),
        owned("shared-thing", [{"type": "anyone", "role": "reader"}]),
    ]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=False),
    ):
        cmd_regulate(regulate_args())
        default = capsys.readouterr().out
        cmd_regulate(regulate_args(all=True))
        everything = capsys.readouterr().out

    assert "private-thing" not in default, "a clean file is noise in a risk report"
    assert "private-thing" in everything


def test_regulate_says_so_plainly_when_nothing_is_exposed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An empty table is ambiguous; 'nothing is shared' is an answer."""
    from gfunk.cli import cmd_regulate

    workspace = MagicMock()
    workspace.sharing.return_value = [owned("private-thing", [])]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=False),
    ):
        code = cmd_regulate(regulate_args())

    assert code == 0
    assert "Nothing" in capsys.readouterr().out


def test_regulate_emits_json_when_asked(capsys: pytest.CaptureFixture[str]) -> None:
    from gfunk.cli import cmd_regulate

    workspace = MagicMock()
    workspace.sharing.return_value = [owned("loud", [{"type": "anyone", "role": "r"}])]

    with (
        patch("gfunk.workspace.Workspace.connect", return_value=workspace),
        patch("gfunk.cli.can_browse", return_value=False),
    ):
        cmd_regulate(regulate_args(json=True))

    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["exposure"] == "public"


def test_regulate_is_a_registered_verb_with_a_handler() -> None:
    from gfunk.cli import COMMANDS

    assert "regulate" in COMMANDS
