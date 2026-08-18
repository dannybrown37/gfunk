import json
from pathlib import Path

from gfunk.mothership_config import MothershipConfig, load, save


def test_defaults_enable_drive_and_sheets_but_not_gmail(tmp_path: Path) -> None:
    cfg = load(tmp_path / "mothership.json")
    assert cfg.features["drive"] is True
    assert cfg.features["sheets"] is True
    assert cfg.features["gmail"] is False
    assert cfg.excluded_folders == []


def test_save_then_load_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "mothership.json"
    cfg = MothershipConfig(
        features={"drive": True, "sheets": False, "gmail": True},
        excluded_folders=["folder123"],
    )
    save(cfg, path)
    loaded = load(path)
    assert loaded == cfg


def test_missing_file_returns_defaults_without_creating_it(tmp_path: Path) -> None:
    path = tmp_path / "nope" / "mothership.json"
    load(path)
    assert not path.exists()


def test_corrupt_file_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "mothership.json"
    path.write_text("not json")
    cfg = load(path)
    assert cfg.features["gmail"] is False


def test_enable_disable_feature_persists(tmp_path: Path) -> None:
    from gfunk.mothership_config import disable_feature, enable_feature

    path = tmp_path / "mothership.json"
    enable_feature(path, "gmail")
    assert load(path).features["gmail"] is True
    disable_feature(path, "gmail")
    assert load(path).features["gmail"] is False


def test_exclude_include_folder_persists(tmp_path: Path) -> None:
    from gfunk.mothership_config import exclude_folder, include_folder

    path = tmp_path / "mothership.json"
    exclude_folder(path, "abc123")
    assert load(path).excluded_folders == ["abc123"]
    exclude_folder(path, "abc123")
    assert load(path).excluded_folders == ["abc123"]
    include_folder(path, "abc123")
    assert load(path).excluded_folders == []


def test_saved_file_is_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "mothership.json"
    save(
        MothershipConfig(
            features={"drive": False, "sheets": True, "gmail": True},
            excluded_folders=[],
        ),
        path,
    )
    raw = json.loads(path.read_text())
    assert raw["features"]["drive"] is False
