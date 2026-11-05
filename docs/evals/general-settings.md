# General settings — 2026-10-27

The settings popup now follows the supplied reference: a neutral 760×500 dialog,
24 px corners, compact left navigation, three theme tiles and pill-shaped selectors
on the right. Its reference layout uses Arial/Helvetica at 14 px and a 16 px title.
On phones the navigation becomes a row and the settings body scrolls inside the
viewport. Profile, Data and About have selectable, empty content areas.

## Working preferences

- Light, Dark and System apply to the kiosk and its popup. System follows live
  `prefers-color-scheme` updates; explicit Light/Dark override OS changes. Tailwind
  dark variants follow the same resolved `.dark` class as the custom dark palette.
- Vietnamese remains the initial UI language, with English selectable immediately.
  Customer labels, cart, product details, progress, payment labels and known errors
  use the selected language; `html.lang` changes accordingly. Merchant catalog names,
  product descriptions, customer notes and actual voice conversation text remain
  their original content. This preference does not change the model's spoken-language
  policy or native voice configuration.
- Theme/language use validated browser preferences, stored only when explicitly
  selected. They survive reload and guest changes. Voice selection retains its
  existing persistence and next-guest behavior; camera source retains its existing
  selection semantics and cannot change while capture is armed.
- Language, Voice and Camera now use the installed Radix Select rather than the
  platform menu: 200 px floating list, rounded hover rows, selected checkmark,
  constrained scroll area, themed palette and viewport collision handling. The
  viewport's injected style receives the existing CSP nonce. The empty default
  voice value is encoded internally and decoded before calling the unchanged handler.
- Uses the existing Radix dialog: focus trapping, Escape, close button and restored
  trigger focus. No new dependencies, routes or profile/data/about functionality.

## Implementation

`SettingsDialog.tsx` owns navigation and controls. `preferences.tsx` applies and stores
preferences; `usePreferences.ts` shares the context and `translations.ts` holds English
UI labels. Existing customer components translate labels at render time, preserving
cart state and merchant values. `DialogContent` accepts an optional overlay class;
other dialog defaults are retained. New CSS scopes the reference design and dark
palette, including legacy surfaces with literal light colors.

## Verification

- Five fixture browser cases: 1440×1000, 851×605, 768×1000, 375×812 and 667×375.
  They exercise Light/Dark/System, live OS changes, explicit-theme override, VI/EN,
  reload persistence, actual translated menu/cart labels, saved voice, camera choices,
  empty placeholder sections, popup/menu bounds, preserved cart and keyboard focus.
  Select tests use actual options, verify checkmarks, Home/Enter selection and Escape;
  idle tests close both open Settings and its nested menu when a guest ends.
- Reference images: `output/general-settings-light-{width}.png` and
  `output/general-settings-dark-{width}.png`; menu snapshots use
  `output/settings-camera-menu-{width}.png`. Screenshots finish finite transitions
  before capture. The supplied image is the visual reference; no source design file
  or exact reference font was available, so literal pixel identity is not claimed.
- Independent Select review used 43 voice choices on a 667×375 fixture: the 200 px
  menu stayed inside the viewport, the list scrolled, End/Home plus Enter worked,
  default voice persisted the exact empty string, and Escape restored trigger focus.
  It found zero WCAG A/AA violations. Keyboard tests wait for focus movement before
  Enter; selecting an already-selected item does not produce a value-change event.
- Independent review found and verified fixes for two inherited Dark contrast issues:
  cart muted labels and the product-detail quantity stepper. Its disposable-browser
  axe probe found zero WCAG A/AA violations on ordering/details/notes and in Settings.
- Frontend: 21 unit tests, production build/types, lint and formatting passed.
  Python lint and formatting passed. Final full suite: **292 passed in 119.29 s**,
  including the custom menus (`output/general-settings-pytest.txt`).
- All browser activity uses temporary services/FakeCodex. No real customer order,
  payment, print request or native voice session was created. Running Visual/API
  process IDs remain 475384/475424; built assets require existing kiosk tabs to reload.

## Self-evaluation

| Axis | Score | Evidence / remaining limit |
|---|---:|---|
| Accuracy | 4 | Preference and UI behavior exercised; reference font is approximated. |
| Completeness | 4 | Requested General controls work; dynamic merchant and conversation content keeps its source language. |
| Clarity | 4 | Preferences have one shared context; literal legacy colors require scoped Dark overrides. |
| Actionability | 4 | Built assets are ready; already-open tabs require reload. |
| Conciseness | 4 | No dependency or route; UI language support necessarily touches customer labels. |

Overall: 4.0/5. Highest-impact improvement is access to the original design/font for
closer visual matching. The user can review the supplied-size screenshot and actual
controls; the assessment distinguishes that from an exact source-design reproduction.
