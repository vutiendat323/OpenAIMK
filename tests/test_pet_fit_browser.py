"""The Pet must sit inside its panel with room at the sides, however tall the panel is.

Phone-width layouts (where the microphone button overlaps the stage) are not covered here.
"""

import base64

import pytest
from playwright.sync_api import expect
from test_pet_browser import choose_character, pet_kiosk

# Reads the canvas picture and reports how far the robot is from each canvas edge.
MEASURE = """
async (png) => {
  const bytes = Uint8Array.from(atob(png), (c) => c.charCodeAt(0)) // fetch(data:) is blocked
  const blob = new Blob([bytes], { type: 'image/png' })
  const image = await createImageBitmap(blob)
  const surface = document.createElement('canvas')
  surface.width = image.width
  surface.height = image.height
  const context = surface.getContext('2d')
  context.drawImage(image, 0, 0)
  const { data, width, height } = context.getImageData(0, 0, image.width, image.height)
  const [r, g, b] = [226, 242, 231] // the Pet panel's soft green
  let left = width, right = -1, top = height, bottom = -1
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4
      const delta = Math.abs(data[i] - r) + Math.abs(data[i + 1] - g) + Math.abs(data[i + 2] - b)
      if (delta < 30) continue
      left = Math.min(left, x); right = Math.max(right, x)
      top = Math.min(top, y); bottom = Math.max(bottom, y)
    }
  return { width, height, left, right: width - 1 - right, top, bottom: height - 1 - bottom }
}
"""


def robot_margins(page):
    canvas = page.locator(".pet-webgl")
    page.wait_for_timeout(1200)  # first frames settle
    box = canvas.bounding_box()  # a clip: the floating Pet never "settles" for locator.screenshot
    png = base64.b64encode(page.screenshot(clip=box)).decode()
    return page.evaluate(MEASURE, png)


@pytest.mark.parametrize(
    "width,height",
    [(1440, 900), (1440, 1080), (1280, 720), (1100, 800), (820, 900)],
)
def test_the_pet_fits_inside_its_panel_with_room_at_the_sides(svc, width, height):
    with pet_kiosk(svc, width) as (page, _host):
        page.set_viewport_size({"width": width, "height": height})
        choose_character(page, "Pet")
        expect(page.locator(".assistant-pet")).to_have_attribute("data-renderer", "webgl")
        panel = page.locator(".avatar-assistant").bounding_box()
        margins = robot_margins(page)
        page.screenshot(path=f"output/pet/fit-{width}x{height}.png")
        print(
            f"\nviewport {width}x{height} panel {panel['width']:.0f}x{panel['height']:.0f}", margins
        )
        # Ears and arms must not touch the canvas edge: at least 8% of its width each side.
        room = margins["width"] * 0.08
        assert margins["left"] >= room and margins["right"] >= room, margins
        assert margins["top"] >= 4, margins


def test_volt_stands_still_without_a_page_float(svc):
    """User decision 2026-11-04: no host-added hover float; Volt keeps its own animation."""
    with pet_kiosk(svc, 1440) as (page, _host):
        choose_character(page, "Pet")
        expect(page.locator(".assistant-pet")).to_have_attribute("data-renderer", "webgl")
        running = "() => document.querySelector('.pet-floating-body').getAnimations().length"
        assert page.evaluate(running) == 0
        canvas = page.locator(".pet-webgl")
        first = canvas.bounding_box()["y"]
        page.wait_for_timeout(1500)
        assert canvas.bounding_box()["y"] == first, "the picture does not move up and down"
