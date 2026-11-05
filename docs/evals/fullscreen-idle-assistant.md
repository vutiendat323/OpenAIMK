# Fullscreen idle assistant — 2026-10-27

The kiosk shows only its centered assistant while voice is enabled, armed and no
customer session is active. The assistant keeps its avatar, conversation bubbles,
waveform and microphone controls. Its container fills the viewport edge to edge with a muted sage background and no
card border. `object-fit: contain` preserves the avatar at portrait and landscape sizes.
Starting a guest through existing presence detection or “Bắt đầu nói” restores the
header, menu and cart. Turning the microphone off retains touch ordering.

## Implementation

`frontend/src/App.tsx` derives idle from the voice session state, without matching
localized status text. An active guest waiting for native voice or speaker ownership
still sees the complete ordering layout. The header is unmounted while idle so an
open portalled settings dialog cannot remain over the assistant. Menu/cart use
`hidden` and scoped CSS; their children are excluded from keyboard/accessibility
navigation. No audio, presence, native connection or merchant behavior changed.

The existing assistant remains mounted across session end and background token
refresh, preserving farewell playback, bubbles and waveform. Loading/error screens
remain available outside the armed idle state. The fullscreen scene has no outer
padding, border or rounded card corners. CSS overrides existing compact breakpoint
layouts only under `.assistant-idle`.

## Verification

- Witnessed the new browser regression fail because the menu remained visible.
- Five disposable fixture browser cases at 1440×1000, 1080×1920, 768×1000,
  375×812 and 667×375:
  initial auto-armed idle, centered/bounded avatar, controls/wave within viewport,
  manual start, active-but-waiting native state, cart mutation, end with an open
  settings popup, farewell, same mounted avatar, next-guest isolation and mic-off
  touch fallback. Screenshots: `output/assistant-idle-{width}x{height}.png`.
- Six existing boundary playback/camera cases also assert that presence-driven
  start restores ordering and departure hides it. Native is deliberately blocked
  or unavailable; speech and camera ownership assertions remain intact.
- Existing product cards had already moved from direct quick-add to opening a
  product panel before this task. Updated affected browser test selectors to use
  “Xem” → panel “Thêm”, retaining all quantity/note/checkout assertions. The first
  full run demonstrated the stale selectors in two settings cases and was stopped
  to update them; the original log is preserved in
  `output/assistant-idle-pytest-before-selector-update.txt`.
- All 19 affected customer/merchant/settings/category/table/cart journeys passed.
  Voice smoke passed: shared cart, waveform playback, conversation, guest isolation,
  reconnect, no browser errors and no axe violations at 1440/768/375 px.
- Frontend: 21 tests passed, production build/types, lint and format passed.
  Python lint and format passed. Final full suite: **290 passed in 105.05 s**
  (`output/assistant-idle-pytest.txt`), after the proportional-width correction.
- Independent review found no material lifecycle, visibility, portal or accessibility
  issue; a separate reviewer independently passed the landscape case.
- Before the final visual-only refinement, the running kiosk served the new CSS and
  `/health` returned `ok`. The borderless sage background and edge-to-edge layout
  were applied afterward; the production build passed. Visual/API process IDs were
  unchanged (475384/475424). Existing browser tabs require reload.

## Self-evaluation

| Axis | Score | Evidence / remaining limit |
|---|---:|---|
| Accuracy | 4 | Browser fixture validates real UI/session transitions; physical kiosk presence was not retested. |
| Completeness | 4 | Initial/end/manual/presence flows covered; viewport checks use five representative sizes. |
| Clarity | 4 | Behavior is tied to session state; existing compact CSS requires explicit overrides. |
| Actionability | 4 | Built assets already served; open tabs still need reload. |
| Conciseness | 4 | One predicate and scoped overrides; several existing tests needed selector maintenance. |

Overall: 4.0/5. Improvement: a physical kiosk pass can confirm the final visual size
on its installed display. The user should agree that the requested visibility and
return-to-ordering behavior is directly exercised; fixtures do not establish
physical acoustic or camera performance.
