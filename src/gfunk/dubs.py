"""Find duplicate files in Drive.

Pure functions over what Drive already returns: no I/O here, so the grouping
is testable on its own, same shape as regulate.py.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Hashable
from typing import Any

NATIVE_PREFIX = "application/vnd.google-apps."
BYTES_PER_UNIT = 1024


def is_native(file: dict[str, Any]) -> bool:
    """Google-native files (Docs/Sheets/Slides) have no md5Checksum to compare."""
    return str(file.get("mimeType", "")).startswith(NATIVE_PREFIX)


def _group(
    files: list[dict[str, Any]], key: Callable[[dict[str, Any]], Hashable | None]
) -> list[list[dict[str, Any]]]:
    groups: dict[Hashable, list[dict[str, Any]]] = defaultdict(list)
    for f in files:
        k = key(f)
        if k is None:
            continue
        groups[k].append(f)
    return [group for group in groups.values() if len(group) > 1]


def find_exact_duplicates(files: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group binary files sharing an md5Checksum — byte-identical copies."""
    binaries = [f for f in files if not is_native(f) and f.get("md5Checksum")]
    return _group(binaries, key=lambda f: f["md5Checksum"])


def find_possible_duplicates(
    files: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Group Google-native files by (name, mimeType) — no checksum to trust."""
    natives = [f for f in files if is_native(f)]
    return _group(natives, key=lambda f: (f.get("name"), f.get("mimeType")))


def wasted_bytes(group: list[dict[str, Any]]) -> int:
    """Space reclaimed by keeping one copy and trashing the rest."""
    sizes = [int(f.get("size", 0) or 0) for f in group]
    if not sizes:
        return 0
    return sum(sizes) - max(sizes)


def sort_by_waste(
    groups: list[list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    """Biggest reclaimable groups first."""
    return sorted(groups, key=wasted_bytes, reverse=True)


def human_bytes(n: int) -> str:
    """Render a byte count the way a person reads it, not the way a computer does."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < BYTES_PER_UNIT:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= BYTES_PER_UNIT
    return f"{size:.1f}TB"


GroupKey = tuple[str, int]


def flatten_groups(
    exact: list[list[dict[str, Any]]], possible: list[list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """One flat row list, each tagged with which group it came from — a picker's diet."""
    rows: list[dict[str, Any]] = []
    for kind, groups in (("exact", exact), ("possible", possible)):
        for index, group in enumerate(groups):
            rows.extend({**f, "group_key": (kind, index)} for f in group)
    return rows


def group_rows(
    rows: list[dict[str, Any]],
) -> list[tuple[GroupKey, list[dict[str, Any]]]]:
    """Bucket flattened rows back by group, preserving first-seen order."""
    order: list[GroupKey] = []
    groups: dict[GroupKey, list[dict[str, Any]]] = {}
    for row in rows:
        key: GroupKey = row["group_key"]
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(row)
    return [(key, groups[key]) for key in order]


def group_label(key: GroupKey, members: list[dict[str, Any]]) -> str:
    """Describe a group the way a person would, waste recomputed for whatever remains."""
    kind, _ = key
    if kind == "exact":
        waste = human_bytes(wasted_bytes(members))
        return f"Exact duplicates — {waste} reclaimable ({len(members)} copies)"
    return f"Possible duplicates — check by hand ({len(members)} copies)"
