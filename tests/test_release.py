import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _load()


@pytest.mark.parametrize("answer", ["y", "yes", " YES "])
def test_confirm_accepts_yes(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: answer)
    assert release.confirm("Go?") is True


@pytest.mark.parametrize("answer", ["n", "", "maybe"])
def test_confirm_rejects_other(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: answer)
    assert release.confirm("Go?") is False


def test_confirm_without_tty_declines(monkeypatch: pytest.MonkeyPatch) -> None:
    def eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert release.confirm("Go?") is False


def test_abort_exits_nonzero() -> None:
    with pytest.raises(SystemExit) as exc:
        release.abort()
    assert exc.value.code == 1


def test_edit_changelog_skips_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kw: object) -> str:
        calls.append(cmd)
        return ""

    monkeypatch.setattr(release, "run", fake_run)
    release.edit_changelog(tmp_path, "1.0.0")
    assert calls == []
