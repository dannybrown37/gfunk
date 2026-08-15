import subprocess
import sys
from importlib.metadata import version

import pytest

from gfunk.cli import main


def run_cli(*args: str, cwd) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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


def test_version_works_with_no_config_and_no_credentials(tmp_path) -> None:
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


@pytest.mark.parametrize("verb", ["mount-up", "mothership"])
def test_known_verbs_are_registered(verb: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([])
    assert verb in capsys.readouterr().out
