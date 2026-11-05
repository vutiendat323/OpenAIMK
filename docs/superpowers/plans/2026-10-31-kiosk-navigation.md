# Kiosk navigation implementation plan

Goal: customer and agent navigation share an overlay drawer on every viewport, initially closed.
User delegated the layout choice and implementation. Retain existing kiosk, native voice, guest ownership and checkout idempotency.

- [x] Add navigation state tests: menu closes sidebar; cart/payment/progress reopen it; reset closes the sidebar and selects cart.
- [x] Add shared navigation reducer and wire existing agent view events, header, dock and checkout result to it.
- [x] Move ProgressPanel into sidebar; add section navigation, close/Escape and mobile backdrop.
- [x] Clarify native instructions for read-only display requests, including current QR without checkout.
- [x] Run frontend tests/lint/build and isolated browser tests for desktop/mobile navigation, reset and order display.

Files: frontend/src/navigation.ts and navigation.test.ts; App.tsx; index.css; translations.ts; ProgressPanel.tsx; trendcoffee/codex_voice.py; tests/test_navigation_browser.py.
Review focus: stale guest content, checkout triggered by navigation, focus after close, hidden columns consuming space, narrow QR/order layouts.
No root Git repository is available; no commit or worktree can be created here.
