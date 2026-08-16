from pathlib import Path
from unittest.mock import patch

import pytest

from gfunk import browser


@pytest.mark.parametrize(
    ("version_text", "expected"),
    [
        ("Linux version 6.18.33.2-microsoft-standard-WSL2", True),
        ("Linux version 6.9.0-1-amd64 (Debian 6.9.7-1)", False),
    ],
)
def test_under_wsl_reads_proc_version(
    tmp_path: Path, version_text: str, *, expected: bool
) -> None:
    proc_version = tmp_path / "version"
    proc_version.write_text(version_text)
    assert browser.under_wsl(proc_version) is expected


def test_wsl_browser_hands_the_url_to_windows() -> None:
    url = "https://accounts.google.com/o/oauth2/auth?a=1&b=2"

    with patch("subprocess.run") as run:
        run.return_value.returncode = 0
        assert browser.WindowsBrowser().open(url) is True

    argv = run.call_args.args[0]
    assert argv[0].endswith("rundll32.exe")
    assert url in argv, "the URL is passed as one argv entry, never shell-interpolated"


def test_wsl_browser_falls_back_to_powershell_with_the_url_quoted() -> None:
    url = "https://accounts.google.com/o/oauth2/auth?a=1&b=2"

    with patch("subprocess.run") as run:
        run.side_effect = [FileNotFoundError, type("R", (), {"returncode": 0})()]
        assert browser.WindowsBrowser().open(url) is True

    command = run.call_args.args[0][-1]
    assert command == f"Start-Process '{url}'", (
        "PowerShell -Command re-parses; an unquoted & is a parse error"
    )


def test_wsl_browser_reports_failure_so_the_caller_can_print_the_url() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert browser.WindowsBrowser().open("https://example.com") is False


def test_register_is_a_no_op_off_wsl() -> None:
    with (
        patch("gfunk.browser.under_wsl", return_value=False),
        patch("webbrowser.register") as register,
    ):
        browser.register()

    register.assert_not_called()


def test_register_prefers_the_windows_browser_under_wsl() -> None:
    with (
        patch("gfunk.browser.under_wsl", return_value=True),
        patch("webbrowser.register") as register,
    ):
        browser.register()

    assert isinstance(register.call_args.args[2], browser.WindowsBrowser)
    assert register.call_args.kwargs["preferred"] is True


def test_hyperlink_survives_terminal_wrapping() -> None:
    url = "https://example.com/very/long?a=1"
    linked = browser.hyperlink("Authorize gfunk", url, supported=True)

    assert linked.startswith("\x1b]8;;" + url)
    assert linked.endswith("\x1b]8;;\x1b\\")
    assert "\n" not in linked, "an OSC 8 link is one unbroken sequence"


def test_hyperlink_falls_back_to_the_bare_url_when_unsupported() -> None:
    url = "https://example.com/very/long?a=1"
    assert browser.hyperlink("Authorize gfunk", url, supported=False) == url
