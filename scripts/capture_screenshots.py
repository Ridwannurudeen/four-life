"""Capture README screenshots from the live site.

Writes PNGs into docs/screenshots/ at 1440×900 viewport. Each page is given
extra settle time so live-fetch components (radar, activity, /dgrid) are
populated before the shot is taken. Uses the playwright chromium binary the
MCP server installed so we don't need a separate download.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

BASE = os.environ.get("FOUR_LIFE_BASE_URL", "https://four-life.gudman.xyz")

# Reuse whichever chromium the host has already installed. Playwright installs
# to %LOCALAPPDATA%/ms-playwright/<name>/... on Windows. The headless shell
# lands in chromium_headless_shell-*; the full browser in chromium-*.
def _find_chromium() -> str | None:
    if env := os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"):
        return env
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    if not base.exists():
        return None
    candidates = []
    for d in sorted(base.iterdir(), reverse=True):
        name = d.name.lower()
        if name.startswith("chromium_headless_shell-"):
            candidates.append(d / "chrome-headless-shell-win64" / "chrome-headless-shell.exe")
        elif name.startswith("chromium-"):
            candidates.append(d / "chrome-win64" / "chrome.exe")
            candidates.append(d / "chrome-win" / "chrome.exe")
    for c in candidates:
        if c.exists():
            return str(c)
    return None


EXECUTABLE = _find_chromium()

SHOTS = [
    # (path, filename, settle_seconds, full_page)
    ("/",        "hero.png",      3, False),
    ("/radar",   "radar.png",     5, False),
    ("/dgrid",   "dgrid.png",     5, False),
    ("/alerts",  "alerts.png",    4, False),
    ("/activity","activity.png",  4, False),
    ("/evidence","evidence.png",  5, False),
    ("/metrics", "metrics.png",   3, False),
    (f"/launch/0xd8c1c7b065ec8548093fe237157088b984dc4444", "launch.png", 5, False),
]


def main() -> None:
    exec_path = EXECUTABLE if EXECUTABLE and Path(EXECUTABLE).exists() else None
    if not exec_path:
        print("no local chromium found; relying on playwright default", file=sys.stderr)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exec_path, headless=True)
        try:
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
                color_scheme="dark",
            )
            page = context.new_page()
            for path, filename, settle, full_page in SHOTS:
                url = f"{BASE}{path}"
                print(f"capturing {url}")
                page.goto(url, wait_until="networkidle", timeout=30_000)
                page.wait_for_timeout(settle * 1000)
                out_path = OUT / filename
                page.screenshot(path=str(out_path), full_page=full_page)
                size = out_path.stat().st_size
                print(f"  wrote {out_path.relative_to(ROOT)} ({size/1024:.0f} KB)")
            context.close()
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"screenshot capture failed: {e}", file=sys.stderr)
        sys.exit(1)
