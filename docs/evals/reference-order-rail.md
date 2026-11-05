# Reference order rail — 2026-10-27

Requested reference: Cuberto's
[McDonald's Touch Interface Concept](https://dribbble.com/shots/7049291-McDonald-s-Touch-Interface-Concept).
Downloaded and inspected the original 3200×2400 PNG. The targeted structure is a
narrow, pale right rail with a two-line heading, fulfillment caption, centered
product image/name/unit price, compact quantity controls, and subtotal plus a
rounded yellow checkout action at the bottom.

## Implementation

- Right rail widths: 160 px desktop, 144 px tablet, 112 px phone. The mobile
  floating cart bar is replaced by the persistent rail. Standard-height screens
  scroll items independently while subtotal/checkout stay in place.
- Cart typography uses an Arial/Helvetica stack, a black two-line heading,
  small centered names/prices, and 40 px product thumbnails. Measured reference
  pixels give yellow `#ffca40` and rail background `#fbfbf9`.
- Product summaries expand the existing note editor. Per the user's follow-up,
  the remove icon is always visible beside the quantity stepper, outside the
  disclosure; narrow-phone controls retain usable hit areas without overflow. Whole-order
  notes are collapsed below the fulfillment caption; requested item notes remain
  visible as previews. Existing note input synchronization is unchanged.
- Rows display unit price, matching the reference; totals still multiply by
  quantities. Minus at one removes the row; quantity limits and submitting locks
  remain. No pricing, checkout API, voice, guest or payment authority changed.
- Checkout/QR expands the rail to 320 px or a full row on small screens. Merchant
  QR images remain inline and ≥200 px in browser regressions. After submission,
  the empty cart is hidden; adding another product restores it.
- Review reproduced clipped content at 667×375/812×375. A witnessed failing
  regression preceded the short-height fallback: the rail can scroll and products
  retain at least 144 px of space. This keeps checkout reachable on short screens.

## Fidelity limits

The source contains raster artwork, not the original font/design file. Its exact
font is unidentified; the cart font is a visual approximation, not a verified
100% font match. Actual Trend Coffee product photography, Vietnamese labels and
VND amounts are retained. Muted text is slightly darker than the reference to
pass contrast checks. Notes and responsive/QR states extend beyond the source's
three-product static example. No literal pixel-perfect claim is made.

## Evidence and verification

Witnessed the initial rail-width regression fail (300 px instead of 160 px), then
verified six viewport cases: 1440×1000, 768×1000, 375×1000, 667×375, 812×375 and
320×568. Assertions cover centered images, widths, actual colors, unit prices,
quantity totals, removal, both notes, long-list scrolling and reachable checkout.
Customer/merchant browser journeys cover lost-response idempotency, notes,
checkout locking, QR display/expiry/payment, and guest reset. Independent review
passed after the short-height fix.

`tests/browser_voice_smoke.py` passed: no browser errors or axe violations at
1440/768/375, real shared-cart/PCM fixture playback, delayed note echo, checkout
while a note has focus, next-guest clearing and reconnect. It uses fake devices,
native substitutes and a disposable DB; no real merchant order/payment/print.

Artifacts:

- `output/reference-cart-{width}.png` and `reference-cart-rail-{width}.png`.
- `output/reference-cart-pytest.txt` — complete backend/browser run.
- `output/reference-cart-voice-smoke.txt` — voice UI, notes, isolation and axe.
- `output/reference-cart-runtime.json` — deployed-asset verification.

Frontend: 21 tests, production build, lint and formatting passed. Python
lint/format and patch whitespace checks passed. This frontend-only update needs
existing tabs reloaded; services require no restart.

Final full suite after the always-visible removal follow-up: **285 passed in
92.52 s**. The final nine responsive/customer/merchant checks also passed, including
removal visible before opening notes, placement within `quantity-row`, narrow-rail
fit, actual deletion, minus-at-one deletion, and submitting locks. Deployed
1440/375 px checks passed without errors/overflow; screenshots are
`output/reference-cart-deployed-rail-{1440,375}.png`. Validation created no real
merchant orders/payments/print jobs and did not restart services.

## Self-evaluation

| Axis | Score | Evidence / improvement |
| --- | --- | --- |
| Accuracy | 4 | Real source colors and functional regressions verified; exact source font is unidentified. |
| Completeness | 3 | Requested rail structure and responsive checkout implemented; a literal 100% font match requires the source font/design asset. |
| Clarity | 4 | Actual fulfillment, unit prices and subtotal stay visible; notes are discoverable by opening the product summary. |
| Actionability | 4 | Built, tested and served with screenshots; the original font is the remaining fidelity input. |
| Conciseness | 4 | Three application files, native disclosures and existing controls; CSS handles narrow and short viewports without new JS layout machinery. |

Overall 3.8/5. Highest-impact fidelity improvement is identifying/providing the
original font and comparing against the original design at an agreed viewport.
Self-check: the implementation is reviewable and working; the requested 100%
font equivalence is explicitly unverified.
