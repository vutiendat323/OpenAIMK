"""The pulsing status dot of the assistant keeps its whole glow (2026-11-07: left side cut off).

`.assistant-heading` clips overflow to keep its slot height fixed, and the dot sits at its
left edge; the dot's pulse spreads up to 8 px (ring 3.5 px, glow 7 px + 1 px), so the
heading's own box must reach that far past the dot on every side.
"""

import os
import re
import shutil
from pathlib import Path

import pytest

GLOW = 8  # px: the largest spread in `status-dot-pulse` (index.css)
STATIC = Path(
    os.environ.get("TREND_STATIC_DIR") or Path(__file__).parent.parent / "trendcoffee/static"
)


def built_css():
    index = (STATIC / "index.html").read_text()
    href = re.search(r'href="/(kiosk-assets/index-[^"]+\.css)"', index).group(1)
    return (STATIC / href).read_text()


@pytest.mark.parametrize("width,height", [(1440, 1000), (800, 1000), (375, 812)])
@pytest.mark.parametrize("phase", ["connecting", "listening", "error"])
def test_the_status_dot_glow_is_not_clipped(width, height, phase):
    from playwright.sync_api import sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium required")
    html = f"""<!doctype html><meta charset="utf-8"><style>{built_css()}</style>
    <div class="simple-kiosk avatar-kiosk"><div class="kiosk-layout"><aside class="assistant-panel">
    <section class="avatar-assistant" data-phase="{phase}" data-engine="livetalking">
    <header class="assistant-heading"><span class="assistant-phase" role="status"><i></i>Connecting…
    </span></header><div class="assistant-scene"></div></section></aside></div></div>"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html)
            box = page.evaluate(
                """() => {
                  const dot = document.querySelector('.assistant-phase i').getBoundingClientRect();
                  const head = document.querySelector('.assistant-heading');
                  const pad = getComputedStyle(head);
                  const r = head.getBoundingClientRect();
                  // the clip edge is the padding box: inside the border
                  const border = parseFloat(pad.borderLeftWidth) || 0;
                  return {room: {left: dot.left - (r.left + border), right: r.right - dot.right,
                                 top: dot.top - r.top, bottom: r.bottom - dot.bottom},
                          clips: pad.overflowX !== 'visible'};
                }"""
            )
        finally:
            browser.close()
    if box["clips"]:
        assert all(space >= GLOW for space in box["room"].values()), box
