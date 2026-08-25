#!/usr/bin/env python3
"""Interactive release script with checkpoints."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], *, check: bool = True, capture: bool = False) -> str:
    result = subprocess.run(cmd, check=check, capture_output=capture, text=True)  # noqa: S603
    return result.stdout.strip() if capture else ""


def confirm(prompt: str) -> bool:
    answer = input(f"\n{prompt} [y/N] ").strip().lower()
    return answer in ("y", "yes")


def abort(msg: str = "Aborted.") -> None:
    print(f"\n{msg}")
    sys.exit(1)


def edit_changelog(root: Path, new_version: str) -> None:
    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        return
    editor = (
        run(
            ["git", "config", "--get", "core.editor"],
            capture=True,
            check=False,
        )
        or "vi"
    )
    print(f"\n── Opening {changelog.name} in {editor} ──")
    print("Edit release notes, save, and close.")
    run([editor, str(changelog)])

    diff = run(["git", "diff", "--name-only"], capture=True)
    if "CHANGELOG.md" in diff:
        print("Changelog edited — amending bump commit.")
        run(["git", "add", str(changelog)])
        run(["git", "commit", "--amend", "--no-edit"])
        run(["git", "tag", "-f", f"v{new_version}"])


def main() -> None:
    root = Path(__file__).resolve().parent.parent

    print("── Checking working tree ──")
    status = run(["git", "status", "--porcelain"], capture=True)
    if status:
        print(status)
        abort("Working tree is dirty. Commit or stash first.")

    print("\n── Version preview ──")
    current = run(["uv", "run", "cz", "version"], capture=True)
    print(f"Current version: {current}")
    bump_preview = run(
        ["uv", "run", "cz", "bump", "--dry-run"],
        capture=True,
        check=False,
    )
    print(bump_preview)

    if not confirm("Proceed with this bump?"):
        abort()

    print("\n── Running tests ──")
    run(["uv", "run", "pytest", "tests/", "-q"])

    print("\n── Running pre-commit ──")
    run(["uv", "run", "pre-commit", "run", "--all-files"], check=False)

    if not confirm("Pre-commit done. Continue?"):
        abort()

    print("\n── Building package ──")
    run(["uv", "build"])
    print("Build artifacts:")
    for f in sorted((root / "dist").glob("*")):
        print(f"  {f.name}")

    print("\n── Bumping version ──")
    run(["uv", "run", "cz", "bump", "--yes"])

    new_version = run(["uv", "run", "cz", "version"], capture=True)
    print(f"New version: {new_version}")

    edit_changelog(root, new_version)

    # 8. Final confirmation before push
    print("\n── Summary ──")
    print(f"Version: {new_version}")
    print(f"Tag:     v{new_version}")
    print("\nRecent commits:")
    run(["git", "log", "--oneline", "-5"])

    if not confirm("Push commit + tag to origin? (triggers PyPI publish)"):
        print("\nTag and commit are local. Push when ready:")
        print("  git push && git push --tags")
        sys.exit(0)

    # 9. Push
    run(["git", "push"])
    run(["git", "push", "--tags"])
    print(f"\n✓ v{new_version} pushed. PyPI publish will start shortly.")


if __name__ == "__main__":
    main()
