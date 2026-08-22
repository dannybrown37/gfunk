from __future__ import annotations

from typing import Any

import pytest

from gfunk.grind_tui import DayHeader, EventItem, _load_label
from gfunk.cli import grind_days


def _event(
    summary: str,
    start: str,
    end: str,
    *,
    location: str = "",
    all_day: bool = False,
) -> dict[str, Any]:
    if all_day:
        return {"summary": summary, "start": {"date": start}, "end": {"date": end}}
    base: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    if location:
        base["location"] = location
    return base


FAKE_EVENTS = [
    _event(
        "Snoop Dogg Meetup",
        "2026-08-24T09:00:00-05:00",
        "2026-08-24T09:45:00-05:00",
        location="213 Main St, Los Angeles, CA",
    ),
    _event("Team Standup", "2026-08-24T10:00:00-05:00", "2026-08-24T10:30:00-05:00"),
    _event("PTO", "2026-08-25", "2026-08-26", all_day=True),
    _event("1:1 with Boss", "2026-08-25T14:00:00-05:00", "2026-08-25T14:30:00-05:00"),
]


class TestEventItem:
    def test_compact_label_has_time_and_summary(self) -> None:
        item = EventItem(FAKE_EVENTS[0])
        assert "Snoop Dogg Meetup" in item._compact
        assert "9:00am" in item._compact

    def test_compact_shows_short_location(self) -> None:
        item = EventItem(FAKE_EVENTS[0])
        assert "📍 213 Main St" in item._compact
        assert "1425" not in item._compact

    def test_long_location_truncated_in_compact(self) -> None:
        long_name = "A" * 40
        ev = _event(
            "Mtg", "2025-06-02T10:00:00", "2025-06-02T11:00:00", location=long_name
        )
        item = EventItem(ev)
        assert "…" in item._compact
        loc_part = item._compact.split("📍")[1].strip()
        assert len(loc_part) == 30

    def test_expand_shows_full_location(self) -> None:
        item = EventItem(FAKE_EVENTS[0])
        detail = item.render_detail()
        assert "213 Main St" in detail

    def test_expand_shows_duration(self) -> None:
        item = EventItem(FAKE_EVENTS[0])
        detail = item.render_detail()
        assert "45min" in detail

    def test_toggle_sets_expanded(self) -> None:
        item = EventItem(FAKE_EVENTS[1])
        assert not item.expanded
        item.toggle_expand()
        assert item.expanded

    def test_toggle_twice_unsets_expanded(self) -> None:
        item = EventItem(FAKE_EVENTS[1])
        item.toggle_expand()
        item.toggle_expand()
        assert not item.expanded

    def test_expand_shows_attendees(self) -> None:
        ev = _event(
            "Standup",
            "2026-08-24T10:00:00-05:00",
            "2026-08-24T10:30:00-05:00",
        )
        ev["attendees"] = [
            {
                "email": "alice@example.com",
                "displayName": "Alice A",
                "responseStatus": "accepted",
            },
            {"email": "bob@example.com", "responseStatus": "needsAction"},
            {"email": "self@example.com", "self": True, "responseStatus": "accepted"},
        ]
        item = EventItem(ev)
        detail = item.render_detail()
        assert "Alice A" in detail
        assert "bob@example.com" in detail
        assert "self@example.com" not in detail
        assert "accepted" in detail

    def test_no_location_omits_pin(self) -> None:
        item = EventItem(FAKE_EVENTS[1])
        assert "📍" not in item._compact


class TestDayHeader:
    def test_header_contains_day_name(self) -> None:
        days = grind_days(FAKE_EVENTS)
        header = DayHeader(days[0])
        assert header.id == "day-2026-08-24"

    def test_header_shows_meeting_count(self) -> None:
        days = grind_days(FAKE_EVENTS)
        day = days[0]
        assert len(day.events) == 2

    def test_all_day_events_in_header(self) -> None:
        days = grind_days(FAKE_EVENTS)
        day = days[1]
        assert "PTO" in day.all_day


class TestLoadLabel:
    @pytest.mark.parametrize(
        ("hours", "expected"),
        [
            (0.5, "light"),
            (3.0, "moderate"),
            (6.0, "heavy"),
        ],
    )
    def test_load_thresholds(self, hours: float, expected: str) -> None:
        label = _load_label(hours)
        assert expected in label
