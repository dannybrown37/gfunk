import json
import os
import stat
from pathlib import Path

import pytest

from gfunk.bootstrap import (
    PROJECT_PLACEHOLDER,
    Kind,
    classify,
    console_urls,
    diagnose,
    find_candidates,
    install,
    walkthrough,
)


def write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload))
    return path


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"installed": {"client_id": "x"}}, "installed"),
        ({"web": {"client_id": "x"}}, "web"),
        ({"type": "service_account", "client_email": "a@b.com"}, "service_account"),
        ({"nothing": "useful"}, "unknown"),
    ],
)
def test_classify_names_the_credential_family(
    tmp_path: Path, payload: object, expected: Kind
) -> None:
    assert classify(write(tmp_path / "c.json", payload)) == expected


def test_classify_missing_file(tmp_path: Path) -> None:
    assert classify(tmp_path / "absent.json") == "missing"


def test_classify_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text("{not json")
    assert classify(path) == "malformed"


@pytest.mark.parametrize(
    ("kind", "must_mention"),
    [
        ("web", "Desktop app"),
        ("service_account", "service account"),
        ("malformed", "not valid JSON"),
        ("unknown", "OAuth client"),
        ("missing", "gfunk mount-up"),
    ],
)
def test_diagnose_explains_every_wrong_kind(
    tmp_path: Path, kind: Kind, must_mention: str
) -> None:
    path = tmp_path / "c.json"
    message = diagnose(kind, path)
    assert must_mention in message
    assert str(path) in message


def test_diagnose_rejects_the_one_kind_that_is_fine(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nothing to diagnose"):
        diagnose("installed", tmp_path / "c.json")


def test_console_urls_target_the_named_project() -> None:
    urls = console_urls("white-set-462000-b7")
    assert all(url.endswith("project=white-set-462000-b7") for url in urls.values())
    assert set(urls) == {"sheets_api", "drive_api", "consent", "clients"}


def test_console_urls_without_a_project_stay_usable() -> None:
    urls = console_urls(None)
    assert all(PROJECT_PLACEHOLDER not in url for url in urls.values())
    assert all("project=" not in url for url in urls.values())


def test_walkthrough_is_numbered_and_carries_every_url() -> None:
    steps = walkthrough("proj-1")
    assert [step.number for step in steps] == list(range(1, len(steps) + 1))
    linked = {step.url for step in steps if step.url}
    assert set(console_urls("proj-1").values()) <= linked


def test_walkthrough_warns_about_the_test_user_trap() -> None:
    blob = " ".join(line for step in walkthrough(None) for line in step.lines)
    assert "test user" in blob.lower()


def test_find_candidates_returns_newest_first(tmp_path: Path) -> None:
    older = write(tmp_path / "client_secret_old.json", {})
    newer = write(tmp_path / "client_secret_new.json", {})
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    assert find_candidates([tmp_path]) == [newer, older]


def test_find_candidates_ignores_unrelated_files_and_absent_dirs(
    tmp_path: Path,
) -> None:
    write(tmp_path / "taxes.json", {})
    write(tmp_path / "client_secret_1.json", {})
    found = find_candidates([tmp_path, tmp_path / "nope"])
    assert [path.name for path in found] == ["client_secret_1.json"]


def test_install_copies_with_locked_down_permissions(tmp_path: Path) -> None:
    source = write(tmp_path / "client_secret_1.json", {"installed": {"client_id": "x"}})
    dest = tmp_path / "config" / "credentials.json"

    install(source, dest)

    assert json.loads(dest.read_text()) == {"installed": {"client_id": "x"}}
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    assert stat.S_IMODE(dest.parent.stat().st_mode) == 0o700
    assert source.exists(), "the download is copied, not moved"


def test_install_refuses_a_credential_that_is_not_an_installed_client(
    tmp_path: Path,
) -> None:
    source = write(tmp_path / "sa.json", {"type": "service_account"})
    dest = tmp_path / "config" / "credentials.json"

    with pytest.raises(ValueError, match="service account"):
        install(source, dest)
    assert not dest.exists()
