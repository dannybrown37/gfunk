import argparse
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

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


@pytest.mark.parametrize("verb", ["mount-up", "mothership", "snoop", "sample", "mix"])
def test_known_verbs_are_registered(
    verb: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main([])
    assert verb in capsys.readouterr().out


def test_prompting_off_a_tty_fails_loudly_instead_of_hanging(tmp_path: Path) -> None:
    # A prompt that blocks in CI burns the job's whole timeout with no log line.
    result = run_cli("snoop", cwd=tmp_path)
    assert result.returncode != 0
    assert "Not a TTY" in result.stderr


def test_every_verb_has_a_handler() -> None:
    from gfunk.cli import COMMANDS, build_parser

    parser = build_parser()
    actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    assert set(actions[0].choices) == set(COMMANDS)
