"""Interactive TUI for `grind` — weekly calendar at a glance.

Events grouped by day with time bars. Select an event and press Enter
to expand/collapse full details (location, duration). Press `O` (shift)
to open in Google Calendar.
"""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Footer, Header, ListItem, ListView, Static

from gfunk.cli import GrindDay, grind_days, grind_time_bar

if TYPE_CHECKING:
    from datetime import date

    from gfunk.workspace import Workspace

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_LOAD_LIGHT_HOURS = 2
_LOAD_HEAVY_HOURS = 5


def _format_time(dt_str: str) -> str:
    from datetime import datetime

    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%-I:%M%p").lower()


_LOC_MAX_LEN = 30


def _short_location(loc: str) -> str:
    if not loc:
        return ""
    short = loc.split(",", maxsplit=1)[0]
    if len(short) > _LOC_MAX_LEN:
        return short[: _LOC_MAX_LEN - 1] + "…"
    return short


def _load_label(hours: float) -> str:
    if hours < _LOAD_LIGHT_HOURS:
        return "[green]light[/]"
    if hours < _LOAD_HEAVY_HOURS:
        return "[yellow]moderate[/]"
    return "[red]heavy[/]"


class DayHeader(ListItem):
    def __init__(self, day: GrindDay) -> None:
        self.day = day
        day_name = _DAY_NAMES[day.date.weekday()]
        has_events = bool(day.events or day.all_day)
        if has_events:
            bar = grind_time_bar(day.time_spans)
            count = len(day.events)
            mtg = f"{count} meeting{'s' if count != 1 else ''}"
            load = _load_label(day.total_hours)
            label = (
                f"[bold]{day_name} {day.date.strftime('%b %d')}[/]  "
                f"{mtg}, {day.total_hours:.1f}h  {load}\n"
                f"  8am {bar} 8pm"
            )
            for ad in day.all_day:
                label += f"\n  ▸ ALL DAY  {ad}"
            if day.conflicts:
                label += (
                    f"\n  ⚠ {day.conflicts} conflict{'s' if day.conflicts != 1 else ''}"
                )
        else:
            label = (
                f"[dim]{day_name} {day.date.strftime('%b %d')}[/]  "
                f"[dim italic]no meetings[/]"
            )
        super().__init__(Static(label, markup=True))
        self.id = f"day-{day.date.isoformat()}"


class EventItem(ListItem):
    def __init__(self, event: dict[str, Any]) -> None:
        self.event = event
        self.expanded = False
        start_str = _format_time(event["start"]["dateTime"])
        end_raw = event.get("end", {}).get("dateTime", "")
        end_str = _format_time(end_raw) if end_raw else ""
        summary = event.get("summary", "(no title)")
        loc = _short_location(event.get("location", ""))
        self._compact = f"  {start_str}-{end_str}  {summary}"
        if loc:
            self._compact += f"  📍 {loc}"
        self._detail = self.render_detail()
        super().__init__(Static(self._compact))

    def render_detail(self) -> str:
        lines = [self._compact if hasattr(self, "_compact") else ""]
        loc = self.event.get("location", "")
        if loc:
            lines.append(f"    Location: {loc}")
        desc = self.event.get("description", "")
        if desc:
            short = desc[:200].replace("\n", " ")
            lines.append(f"    Notes: {short}")
        start_raw = self.event["start"]["dateTime"]
        end_raw = self.event.get("end", {}).get("dateTime", "")
        if end_raw:
            from datetime import datetime

            dur = datetime.fromisoformat(end_raw) - datetime.fromisoformat(start_raw)
            mins = int(dur.total_seconds() // 60)
            lines.append(f"    Duration: {mins}min")
        attendees = [
            a for a in self.event.get("attendees", []) if not a.get("self", False)
        ]
        if attendees:
            lines.append("    Attendees:")
            for a in attendees:
                name = a.get("displayName", a["email"])
                status = a.get("responseStatus", "unknown")
                lines.append(f"      • {name} ({status})")
        return "\n".join(lines)

    def toggle_expand(self) -> None:
        self.expanded = not self.expanded
        from textual.css.query import NoMatches

        try:
            static = self.query_one(Static)
        except NoMatches:
            return
        static.update(self._detail if self.expanded else self._compact)


class GrindApp(App[None]):
    TITLE = "gfunk grind"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "↓"),
        Binding("k", "cursor_up", "↑"),
        Binding("E", "toggle_detail", "Expand"),
        Binding("O", "open_in_calendar", "open in browser"),
        Binding("q", "quit", "quit"),
    ]

    def __init__(
        self,
        events: list[dict[str, Any]],
        *,
        workspace: Workspace | None = None,
        start_date: date | None = None,
        num_days: int = 7,
    ) -> None:
        super().__init__()
        self._events = events
        self._workspace = workspace
        self._start_date = start_date
        self._num_days = num_days

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView()
        yield Footer()

    def on_mount(self) -> None:
        days = grind_days(
            self._events,
            start_date=self._start_date,
            num_days=self._num_days,
        )
        lv = self.query_one(ListView)
        for day in days:
            lv.append(DayHeader(day))
            for ev in day.events:
                lv.append(EventItem(ev))

    def action_toggle_detail(self) -> None:
        lv = self.query_one(ListView)
        if lv.index is None:
            return
        item = lv.children[lv.index]
        if isinstance(item, EventItem):
            item.toggle_expand()

    def action_open_in_calendar(self) -> None:
        lv = self.query_one(ListView)
        if lv.index is None:
            return
        item = lv.children[lv.index]
        if isinstance(item, EventItem):
            eid = item.event.get("htmlLink", "")
            if eid:
                from gfunk.browser import register

                register()
                webbrowser.open(eid)

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()
