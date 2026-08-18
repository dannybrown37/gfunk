"""Per-feature MCP opt-in and Drive folder exclusion for the mothership server."""

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "gfunk" / "mothership.json"

DEFAULT_FEATURES = {"drive": True, "sheets": True, "gmail": False}


@dataclass
class MothershipConfig:
    features: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_FEATURES))
    excluded_folders: list[str] = field(default_factory=list)


def load(path: Path = DEFAULT_CONFIG_PATH) -> MothershipConfig:
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return MothershipConfig()
    features = dict(DEFAULT_FEATURES)
    features.update(raw.get("features", {}))
    return MothershipConfig(
        features=features,
        excluded_folders=list(raw.get("excluded_folders", [])),
    )


def save(cfg: MothershipConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"features": cfg.features, "excluded_folders": cfg.excluded_folders},
            indent=2,
        )
    )


def enable_feature(path: Path, feature: str) -> None:
    cfg = load(path)
    cfg.features[feature] = True
    save(cfg, path)


def disable_feature(path: Path, feature: str) -> None:
    cfg = load(path)
    cfg.features[feature] = False
    save(cfg, path)


def exclude_folder(path: Path, folder_id: str) -> None:
    cfg = load(path)
    if folder_id not in cfg.excluded_folders:
        cfg.excluded_folders.append(folder_id)
    save(cfg, path)


def include_folder(path: Path, folder_id: str) -> None:
    cfg = load(path)
    if folder_id in cfg.excluded_folders:
        cfg.excluded_folders.remove(folder_id)
    save(cfg, path)
