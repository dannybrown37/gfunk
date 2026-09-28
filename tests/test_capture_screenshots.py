import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "capture_screenshots.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capture_screenshots", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capture = _load()


@pytest.mark.parametrize(
    ("svg", "expected"),
    [
        ("<svg>  \n</svg>\t", "<svg>\n</svg>\n"),
        ("<svg/>", "<svg/>\n"),
        ("a \r\nb ", "a\nb\n"),
    ],
)
def test_save_strips_trailing_whitespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, svg: str, expected: str
) -> None:
    monkeypatch.setattr(capture, "SCREENSHOT_DIR", tmp_path)
    capture._save("x.svg", svg)
    assert (tmp_path / "x.svg").read_text() == expected
