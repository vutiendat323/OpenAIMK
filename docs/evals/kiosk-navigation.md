# Kiosk navigation — 2026-10-31

User selected an overlay drawer at every viewport, initially closed. The existing kiosk remains the application; checkout dock remains full width.

## Behavior

- Header hamburger toggles the drawer; close button, Escape and backdrop dismiss it.
- Menu returns to the menu and closes the drawer. Cart, Payment / QR and Placed orders select their corresponding sidebar content.
- ProgressPanel now lives inside the sidebar. Existing agent view events use the same navigation reducer as touch controls.
- Native instructions map menu/cart/current QR/my orders requests to kiosk_menu, kiosk_cart(action=view), kiosk_payment and kiosk_progress. Viewing QR never invokes checkout.
- Viewing empty QR leaves checkout disabled and Cancel available. Checkout errors display inside the drawer. Guest reset closes the drawer and removes prior guest content.
- Table selector is explicitly above the drawer/backdrop; Escape respects an open dialog/listbox. Reduced-motion preferences disable drawer entry animation.

## Verification

- `npm test` in frontend: 53 passed.
- `npm run lint` and `npm run build` in frontend: passed.
- Prettier checks on all changed frontend files: passed. Full-project format check additionally flags existing `VirtualKeyboard.tsx`; that file was left untouched.
- `.venv/bin/python -m pytest tests/test_navigation_browser.py tests/test_kiosk_runtime.py tests/test_kiosk_socket.py -q --tb=short`: 39 passed in 10.36 seconds.
- Browser fixtures cover 1440/768/375px, empty payment/orders, preserved cart and local checkout, missing fulfillment errors, merchant-connected table picker with mocked tables, Escape/focus, backdrop, guest replacement and no page errors.
- Ruff lint/format on changed Python files: passed.
- Reviewer findings about empty-QR checkout presentation, hidden errors and menu focus were fixed. Merchant table picker coverage was added after review.

Screenshots: [desktop](../../output/kiosk-navigation/navigation-1440.png), [tablet](../../output/kiosk-navigation/navigation-768.png), [mobile](../../output/kiosk-navigation/navigation-375.png).

## Activation and limits

Frontend build is in trendcoffee/static. API alone was reloaded after a fresh idle/no-microphone check, preserving its prior process environment. Visual/avatar were left running; API health is ok, native voice enabled, and no guest was active after reload. Reload open browser tabs to receive the build.

Tests used disposable local databases and mock table responses; no real merchant order, payment or print was created. Actual spoken intent selection by the live native model was not exercised; the tool/event contract and frontend presentation were verified separately. Screenshots are new-feature evidence, without a prior visual baseline.

## Self-evaluation

Accuracy 4/5: source and fixtures verified, live spoken intents unmeasured. Completeness 4/5: all requested destinations implemented, physical voice smoke remains. Clarity 4/5: concise evidence, fixture/live boundaries explicit. Actionability 5/5: built assets and API activated; screenshots and repeatable commands provided. Conciseness 4/5: evidence retained here to keep the user summary short. Overall 4.2/5. Highest-impact follow-up: customer speech smoke for the four destination phrases. Would the user agree: likely, with visual and live voice acceptance still theirs.
