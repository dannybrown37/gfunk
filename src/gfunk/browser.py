"""Open the OAuth consent page where the human is: a Windows browser, from WSL."""

import subprocess
import sys
import webbrowser
from pathlib import Path

PROC_VERSION = Path("/proc/version")
RUNDLL32 = "/mnt/c/Windows/System32/rundll32.exe"
POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"


def _powershell_literal(url: str) -> str:
    """Single-quoted, because -Command re-parses and OAuth URLs are full of '&'."""
    escaped = url.replace("'", "''")
    return f"Start-Process '{escaped}'"


def under_wsl(proc_version: Path = PROC_VERSION) -> bool:
    try:
        return "microsoft" in proc_version.read_text().lower()
    except OSError:
        return False


class WindowsBrowser(webbrowser.BaseBrowser):
    """WSL has no browser; Windows does, and Start-Process reaches it."""

    def open(self, url: str, new: int = 0, autoraise: bool = True) -> bool:  # noqa: ARG002, FBT001, FBT002
        for argv in self.commands(url):
            try:
                done = subprocess.run(argv, capture_output=True, check=False)  # noqa: S603
            except OSError:
                continue
            if done.returncode == 0:
                return True
        return False

    def commands(self, url: str) -> list[list[str]]:
        """rundll32 first: it hands the URL to Windows with no shell to re-parse it."""
        powershell = POWERSHELL if Path(POWERSHELL).exists() else "powershell.exe"
        return [
            [RUNDLL32, "url.dll,FileProtocolHandler", url],
            [powershell, "-NoProfile", "-Command", _powershell_literal(url)],
        ]


def register() -> None:
    """Make webbrowser.open (and anything built on it) reach the Windows side."""
    if not under_wsl():
        return
    webbrowser.register("gfunk-windows", None, WindowsBrowser(), preferred=True)


def hyperlink(text: str, url: str, *, supported: bool | None = None) -> str:
    """OSC 8: one clickable link, immune to however the terminal wraps the URL."""
    if supported is None:
        supported = sys.stdout.isatty()
    if not supported:
        return url
    return f"\x1b]8;;{url}\x1b\\{text}\x1b]8;;\x1b\\"
