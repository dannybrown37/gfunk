from datetime import date, datetime, UTC
from typing import Any

import pytest

from gfunk.cli import _short_location, grind_days, grind_time_bar


def _event(
    summary: str,
    start: str,
    end: str,
    *,
    all_day: bool = False,
    location: str = "",
) -> dict[str, Any]:
    if all_day:
        return {
            "summary": summary,
            "start": {"date": start},
            "end": {"date": end},
        }
    base: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    if location:
        base["location"] = location
    return base


class TestGrindDays:
    def test_groups_events_by_date(self) -> None:
        events = [
            _event("Standup", "2026-08-24T09:00:00-05:00", "2026-08-24T09:30:00-05:00"),
            _event("Lunch", "2026-08-24T12:00:00-05:00", "2026-08-24T13:00:00-05:00"),
            _event("Review", "2026-08-25T10:00:00-05:00", "2026-08-25T11:00:00-05:00"),
        ]
        days = grind_days(events)
        assert len(days) == 2
        assert days[0].date == date(2026, 8, 24)
        assert len(days[0].events) == 2
        assert days[1].date == date(2026, 8, 25)
        assert len(days[1].events) == 1

    def test_computes_meeting_hours(self) -> None:
        events = [
            _event("Standup", "2026-08-24T09:00:00-05:00", "2026-08-24T09:30:00-05:00"),
            _event(
                "Deep dive", "2026-08-24T14:00:00-05:00", "2026-08-24T16:00:00-05:00"
            ),
        ]
        days = grind_days(events)
        assert days[0].total_hours == pytest.approx(2.5)

    def test_all_day_events_tracked_separately(self) -> None:
        events = [
            _event("PTO", "2026-08-24", "2026-08-25", all_day=True),
            _event("Standup", "2026-08-24T09:00:00-05:00", "2026-08-24T09:30:00-05:00"),
        ]
        days = grind_days(events)
        assert len(days) == 1
        assert days[0].all_day == ["PTO"]
        assert len(days[0].events) == 1

    def test_detects_conflicts(self) -> None:
        events = [
            _event("A", "2026-08-24T09:00:00-05:00", "2026-08-24T10:00:00-05:00"),
            _event("B", "2026-08-24T09:30:00-05:00", "2026-08-24T10:30:00-05:00"),
        ]
        days = grind_days(events)
        assert days[0].conflicts == 1

    def test_no_conflicts_when_back_to_back(self) -> None:
        events = [
            _event("A", "2026-08-24T09:00:00-05:00", "2026-08-24T10:00:00-05:00"),
            _event("B", "2026-08-24T10:00:00-05:00", "2026-08-24T11:00:00-05:00"),
        ]
        days = grind_days(events)
        assert days[0].conflicts == 0

    def test_empty_events_returns_empty(self) -> None:
        assert grind_days([]) == []

    def test_fills_empty_days_when_start_date_given(self) -> None:
        events = [
            _event("Standup", "2026-08-24T09:00:00-05:00", "2026-08-24T09:30:00-05:00"),
            _event("Review", "2026-08-27T10:00:00-05:00", "2026-08-27T11:00:00-05:00"),
        ]
        days = grind_days(events, start_date=date(2026, 8, 24), num_days=7)
        assert len(days) == 7
        assert days[0].date == date(2026, 8, 24)
        assert len(days[0].events) == 1
        assert days[1].date == date(2026, 8, 25)
        assert len(days[1].events) == 0
        assert days[2].date == date(2026, 8, 26)
        assert len(days[2].events) == 0
        assert days[3].date == date(2026, 8, 27)
        assert len(days[3].events) == 1

    def test_fills_all_empty_when_no_events(self) -> None:
        days = grind_days([], start_date=date(2026, 8, 24), num_days=7)
        assert len(days) == 7
        assert all(len(d.events) == 0 for d in days)
        assert all(d.total_hours == 0.0 for d in days)

    def test_sorts_days_chronologically(self) -> None:
        events = [
            _event("B", "2026-08-25T10:00:00-05:00", "2026-08-25T11:00:00-05:00"),
            _event("A", "2026-08-24T09:00:00-05:00", "2026-08-24T10:00:00-05:00"),
        ]
        days = grind_days(events)
        assert days[0].date < days[1].date


class TestGrindTimeBar:
    def test_empty_day_shows_all_dots(self) -> None:
        bar = grind_time_bar([])
        assert "░" in bar or "·" in bar
        assert "█" not in bar

    def test_full_slot_filled(self) -> None:
        events = [
            (
                datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
                datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
            ),
        ]
        bar = grind_time_bar(events)
        assert "█" in bar

    def test_bar_length_is_consistent(self) -> None:
        bar_empty = grind_time_bar([])
        events = [
            (
                datetime(2026, 8, 24, 12, 0, tzinfo=UTC),
                datetime(2026, 8, 24, 13, 0, tzinfo=UTC),
            ),
        ]
        bar_some = grind_time_bar(events)
        assert len(bar_empty) == len(bar_some)


class TestShortLocation:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("", ""),
            ("Zoom", "Zoom"),
            (
                "Making Light Productions, Inc., 2720 S Blair Stone Rd",
                "Making Light Productions",
            ),
            ("123 Main St, Springfield, IL", "123 Main St"),
        ],
    )
    def test_truncates_after_first_comma(self, raw: str, expected: str) -> None:
        assert _short_location(raw) == expected
