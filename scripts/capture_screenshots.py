"""Capture SVG screenshots of every TUI view using demo data."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from gfunk.demo_data import (
    DEMO_DUBS_ROWS,
    DEMO_GRIND_EVENTS,
    DEMO_LABELS,
    DEMO_REGULATE_ROWS,
    DEMO_VIBE_ROWS,
    DemoWorkspace,
)
from gfunk.dubs_tui import DubsApp
from gfunk.grind_tui import GrindApp
from gfunk.holla_tui import HollaApp
from gfunk.regulate_tui import RegulateApp
from gfunk.snoop_tui import SnoopApp
from gfunk.vibe import VibeApp

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SIZE = (130, 45)


def _save(name: str, svg: str) -> None:
    clean = "\n".join(line.rstrip() for line in svg.splitlines()) + "\n"
    (SCREENSHOT_DIR / name).write_text(clean)
    print(f"  ✓ {name}")


async def capture_holla() -> None:
    ws = DemoWorkspace()

    app = HollaApp(list(DEMO_LABELS), workspace=ws)  # type: ignore[arg-type]
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(1)
        _save("holla_labels.svg", app.export_screenshot(title="gfunk holla — labels"))

        await pilot.press("enter")
        await pilot.pause(1)
        _save(
            "holla_messages.svg", app.export_screenshot(title="gfunk holla — messages")
        )

        await pilot.pause(1)
        _save("holla_preview.svg", app.export_screenshot(title="gfunk holla — preview"))

        await pilot.press("/")
        await pilot.press(*"warren")
        await pilot.pause(0.5)
        _save("holla_filter.svg", app.export_screenshot(title="gfunk holla — filter"))

        await pilot.press("escape")
        await pilot.pause(0.5)
        await pilot.press("s")
        await pilot.pause(0.5)
        _save(
            "holla_sorted.svg",
            app.export_screenshot(title="gfunk holla — sorted by size"),
        )


async def capture_grind() -> None:
    app = GrindApp(
        DEMO_GRIND_EVENTS,
        start_date=date(2024, 8, 26),
        num_days=7,
    )
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(1)
        _save("grind_week.svg", app.export_screenshot(title="gfunk grind — week view"))

        await pilot.press("j")
        await pilot.pause(0.3)
        await pilot.press("E")
        await pilot.pause(0.5)
        _save(
            "grind_expanded.svg",
            app.export_screenshot(title="gfunk grind — expanded event"),
        )


async def capture_snoop() -> None:
    ws = DemoWorkspace()

    app = SnoopApp(ws)  # type: ignore[arg-type]
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(1)
        _save(
            "snoop_browse.svg",
            app.export_screenshot(title="gfunk snoop — folder browser"),
        )

        for _ in range(3):
            await pilot.press("j")
            await pilot.pause(0.2)
        await pilot.pause(1)
        _save(
            "snoop_preview.svg",
            app.export_screenshot(title="gfunk snoop — preview pane"),
        )


async def capture_dubs() -> None:
    ws = DemoWorkspace()

    app = DubsApp(list(DEMO_DUBS_ROWS), workspace=ws)  # type: ignore[arg-type]
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(1)
        _save("dubs_groups.svg", app.export_screenshot(title="gfunk dubs — duplicates"))


async def capture_regulate() -> None:
    ws = DemoWorkspace()

    app = RegulateApp(list(DEMO_REGULATE_ROWS), workspace=ws)  # type: ignore[arg-type]
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(1)
        _save(
            "regulate_audit.svg", app.export_screenshot(title="gfunk regulate — audit")
        )


async def capture_vibe() -> None:
    app = VibeApp(list(DEMO_VIBE_ROWS), title="gfunk vibe — Studio Budget Q3")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(1)
        _save("vibe_table.svg", app.export_screenshot(title="gfunk vibe — spreadsheet"))

        await pilot.press("/")
        await pilot.press(*"quik")
        await pilot.pause(0.5)
        _save("vibe_search.svg", app.export_screenshot(title="gfunk vibe — search"))


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for name, coro in [
        ("holla", capture_holla),
        ("grind", capture_grind),
        ("snoop", capture_snoop),
        ("dubs", capture_dubs),
        ("regulate", capture_regulate),
        ("vibe", capture_vibe),
    ]:
        print(f"Capturing {name} screenshots...")
        asyncio.run(coro())
    print(f"\nDone. Screenshots in {SCREENSHOT_DIR}/")


if __name__ == "__main__":
    main()
