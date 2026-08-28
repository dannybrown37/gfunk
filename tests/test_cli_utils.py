"""Tests for pure utility functions in cli.py that don't need Google auth."""

from __future__ import annotations

from datetime import datetime, UTC

import pytest

from gfunk.cli import (
    _default_format,
    _fmt_size,
    _grind_render,
    _sheet_label,
    _short_location,
    _snoop_actions,
    GrindDay,
    grind_time_bar,
    snoop_entries,
)


# --- _fmt_size ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, "  —"),
        ("0", "  —"),
        ("", "  —"),
        (512, "512 B"),
        ("1024", "1.0 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.0 GB"),
        (1099511627776, "1.0 TB"),
        (1125899906842624, "1.0 PB"),
    ],
)
def test_fmt_size(raw: str | int, expected: str) -> None:
    assert _fmt_size(raw) == expected


# --- snoop_entries ---


def test_snoop_entries_home_sorts_naturally() -> None:
    items = [
        {"name": "Z file", "id": "1", "createdTime": "", "modifiedTime": ""},
        {"name": "A file", "id": "2", "createdTime": "", "modifiedTime": ""},
    ]
    result = snoop_entries(items, up=False, mode="home")
    names = list(result.keys())
    assert names[0].startswith("A file")
    assert names[1].startswith("Z file")


def test_snoop_entries_recent_sorts_by_modified() -> None:
    items = [
        {"name": "Old", "id": "1", "modifiedTime": "2024-01-01T00:00:00Z"},
        {"name": "New", "id": "2", "modifiedTime": "2026-01-01T00:00:00Z"},
    ]
    result = snoop_entries(items, up=False, mode="recent")
    names = list(result.keys())
    assert names[0].startswith("New")


def test_snoop_entries_largest_sorts_by_size() -> None:
    items = [
        {"name": "Small", "id": "1", "quotaBytesUsed": "100", "modifiedTime": ""},
        {"name": "Big", "id": "2", "quotaBytesUsed": "9999", "modifiedTime": ""},
    ]
    result = snoop_entries(items, up=False, mode="largest")
    names = list(result.keys())
    assert names[0].startswith("Big")


def test_snoop_entries_up_adds_parent_entry() -> None:
    result = snoop_entries([], up=True)
    assert "../" in result


def test_snoop_entries_folder_gets_slash() -> None:
    items = [
        {
            "name": "Docs",
            "id": "1",
            "mimeType": "application/vnd.google-apps.folder",
            "createdTime": "",
            "modifiedTime": "",
        },
    ]
    result = snoop_entries(items, up=False)
    assert any("Docs/" in k for k in result)


def test_snoop_entries_empty_returns_empty() -> None:
    assert snoop_entries([], up=False) == {}


# --- _snoop_actions ---


def test_snoop_actions_sheet_has_vibe() -> None:
    item = {"mimeType": "application/vnd.google-apps.spreadsheet"}
    actions = _snoop_actions(item)
    assert actions[0] == "View (Vibe TUI)"
    assert "Open in browser" in actions


def test_snoop_actions_doc_has_view() -> None:
    item = {"mimeType": "application/vnd.google-apps.document"}
    actions = _snoop_actions(item)
    assert actions[0] == "View"


def test_snoop_actions_other_has_base_only() -> None:
    item = {"mimeType": "application/pdf"}
    actions = _snoop_actions(item)
    assert actions[0] == "Open in browser"


# --- _default_format ---


def test_default_format_sheet() -> None:
    assert _default_format("application/vnd.google-apps.spreadsheet") == "csv"


def test_default_format_doc() -> None:
    assert _default_format("application/vnd.google-apps.document") == "txt"


def test_default_format_unknown_falls_back_to_csv() -> None:
    assert _default_format("application/pdf") == "csv"


# --- _sheet_label ---


def test_sheet_label_recent_shows_hours_ago() -> None:
    now = datetime.now(UTC)
    mod = now.isoformat().replace("+00:00", "Z")
    label = _sheet_label({"name": "Budget", "modifiedTime": mod})
    assert "Budget" in label
    assert "ago" in label or "just now" in label


def test_sheet_label_days_ago() -> None:
    label = _sheet_label({"name": "Old", "modifiedTime": "2020-01-01T00:00:00Z"})
    assert "Old" in label
    assert "2020-01-01" in label


def test_sheet_label_no_modified() -> None:
    assert _sheet_label({"name": "Plain"}) == "Plain"


# --- _short_location ---


def test_short_location_trims_after_comma() -> None:
    assert _short_location("Zoom, https://zoom.us/j/123") == "Zoom"


def test_short_location_empty() -> None:
    assert _short_location("") == ""


# --- grind_time_bar ---


def test_grind_time_bar_empty() -> None:
    bar = grind_time_bar([])
    assert "█" not in bar
    assert len(bar) == 24  # 12 hours * 2 half-hour slots


def test_grind_time_bar_fills_slots() -> None:
    spans = [
        (datetime(2026, 1, 1, 9, 0), datetime(2026, 1, 1, 10, 0)),
    ]
    bar = grind_time_bar(spans)
    assert "█" in bar
    assert bar[2:4] == "██"  # 9:00-10:00 = slots 2,3


# --- _grind_render ---


def test_grind_render_basic_event() -> None:
    day = GrindDay(
        date=datetime(2026, 8, 25).date(),
        events=[
            {
                "summary": "Standup",
                "start": {"dateTime": "2026-08-25T09:00:00-05:00"},
                "end": {"dateTime": "2026-08-25T09:30:00-05:00"},
            },
        ],
        total_hours=0.5,
        time_spans=[
            (datetime(2026, 8, 25, 9, 0), datetime(2026, 8, 25, 9, 30)),
        ],
    )
    out = _grind_render([day])
    assert "Standup" in out
    assert "Aug 25" in out
    assert "0.5h" in out


def test_grind_render_all_day_event() -> None:
    day = GrindDay(
        date=datetime(2026, 8, 25).date(),
        all_day=["Company Offsite"],
    )
    out = _grind_render([day])
    assert "ALL DAY" in out
    assert "Company Offsite" in out


def test_grind_render_conflict() -> None:
    day = GrindDay(
        date=datetime(2026, 8, 25).date(),
        conflicts=2,
    )
    out = _grind_render([day])
    assert "2 conflicts" in out


def test_grind_render_single_conflict() -> None:
    day = GrindDay(
        date=datetime(2026, 8, 25).date(),
        conflicts=1,
    )
    out = _grind_render([day])
    assert "1 conflict" in out
    assert "conflicts" not in out


def test_grind_render_location() -> None:
    day = GrindDay(
        date=datetime(2026, 8, 25).date(),
        events=[
            {
                "summary": "Lunch",
                "start": {"dateTime": "2026-08-25T12:00:00-05:00"},
                "end": {"dateTime": "2026-08-25T13:00:00-05:00"},
                "location": "Cafe, 123 Main St",
            },
        ],
        total_hours=1.0,
        time_spans=[
            (datetime(2026, 8, 25, 12, 0), datetime(2026, 8, 25, 13, 0)),
        ],
    )
    out = _grind_render([day])
    assert "Cafe" in out


def test_grind_render_light_moderate_heavy() -> None:
    light = GrindDay(date=datetime(2026, 8, 25).date(), total_hours=1.0)
    mod = GrindDay(date=datetime(2026, 8, 26).date(), total_hours=3.0)
    heavy = GrindDay(date=datetime(2026, 8, 27).date(), total_hours=6.0)
    out = _grind_render([light, mod, heavy])
    assert "light" in out
    assert "moderate" in out
    assert "heavy" in out
