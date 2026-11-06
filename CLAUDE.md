# Trend Coffee project instructions

## Read first

- Read `handoff_trendcoffee_kiosk.md` and `docs/ONBOARDING.md` for the architecture, system state, and task-to-file map.
  Dated operational details may be stale; check recent progress and source.
- Before resuming work, read the latest entries in `docs/PROGRESS.md`; later entries
  supersede earlier status and behavior. Root `AGENTS.md`'s empty-scaffold description
  is historical; application source, tests and manifests now exist.
- For voice selection or boundary playback, start with
  `docs/evals/consistent-kiosk-voice.md`; for latency, read
  `docs/evals/voice-connection-latency.md`, including its final acknowledgment section.
  Use source/evidence for implemented behavior and fresh status checks for availability.
- For camera and microphone readiness, read `docs/evals/device-camera-av-readiness.md`
  and `docs/workflows/kiosk-voice.md`; synthetic checks do not prove device performance.
- Use CodeGraph before code search only when a root `.codegraph/` exists.

## Stack and structure

- Python ≥3.12, uv/Hatchling, FastAPI, SQLite WAL/FTS5; `trendcoffee/` owns business logic.
- React 19/TypeScript/Vite/Tailwind in `frontend/`; build output is `trendcoffee/static/`.
- HTTP (`api.py`), MCP (`mcp_server.py`) and voice (`kiosk.py`) share `Service`/`Store`.
- `codex_voice.py` and `native_peer.py` implement native voice; `av_transport.py` and
  workers integrate local `Audio/`, `Visual/` and `Metric3D/` environments.
- `merchant.py`, `invoices.py`, `printer.py` handle merchant checkout and official invoices.
- `scripts/kiosk.py` manages recorded owned processes; `.runtime/` holds local state.
- Avatar: `avatarPlayer.ts` → `/api/avatar` proxy → `ditto_server.py` →
  `ditto_realtime.py`; mouth generation and video presentation run separately.
  Read `docs/evals/avatar-opening-limit.md` for current evidence and rollback.
  Talking head: on 2026-11-02 the user dropped the `Tạo_video…` clip as the Ditto source (its winks and head
  gestures showed as droopy eyes, torn lips and a bust/full-body framing jump at rest) and chose
  `output/Female_staff_member_clean_v2.mp4` (new AI-generated near-still clip; the older standing clip is superseded) as both Ditto source and silent rest clip (`source`,
  `rest_source`, no GPU in silence). Whole-face Ditto only; never paste a mouth over video. See latest `docs/PROGRESS.md`.
  Use `GLOSSARY.md` terms; make no success claim without measurement; stop before GPU trials.
- 2D character mode was cancelled by the user on 2026-11-01; do not restore its model path. Its code, assets,
  tests and scripts are preserved in `output/avatar-quality-review/cancelled-2d/`.
  On 2026-11-03 the user added a separate code-driven Pet from OpenJarvis. Settings →
  Nhân vật selects Pet / Avatar 3D (default); turn off the microphone before changing.
  Pet uses browser Three.js, bypasses AvatarPlayer and `/api/avatar`, and keeps native voice/Fusion.
  It does not restore the cancelled 2D model path.

## Behavior to preserve

- Voice tone (updated 2026-11-03): warm, friendly-barista tone with light emotion in Vietnamese;
  2–3 short sentences (~40 words max) for conversation/suggestions; 1–2 friendly sentences (~25 words)
  after tool results; acknowledgment remains 4–8 words. Locked rules remain: exact QR payment sentence
  ('Bạn quét QR trên màn hình để thanh toán nhé, thẻ của bạn là số N.' with the order's pickup
  card, from the tool's `qr_reply`; user decision 2026-11-06; orders without a card keep
  'Bạn quét QR trên màn hình để thanh toán nhé.'). The paid result is NOT a fixed sentence (user decision
  2026-11-05): Trend words it naturally (1–2 friendly sentences, may mention the order) only after a
  tool reports paid; `claim_guard.PAID` recognises free wording;
  no order confirmation questions before placing; at most two drink names spoken; never claim checkout/payment success before tool verification.
- Speaker playout (added 2026-11-03): Pet character uses browser WebRTC audio via `SpeakerTrack`
  (`trendcoffee/speaker.py`) with a steady 20ms clock and ~500ms startup playout buffer to prevent
  NetEQ time-stretching and concealment inside words. Buffer is corrected only during ≥60ms pauses;
  speech frames are never skipped or altered. WebSocket PCM fallback is retained. Avatar 3D continues using
  its existing Ditto WebSocket PCM transport.
- First short answer (user decision 2026-11-03): released after it ends when it has ≥3 ACCEPT rows,
  ≥2 of them ASD-confirmed on the guest's face, no other face speaking; once per guest (`FusionPreroll`).
  Later turns keep the 6-row lock.
- Short completed customer turns (hello/yes/menu) must not require two seconds of speech.
  Keep native prompt and role-bearing startup instructions aligned; see
  `docs/evals/customer-short-speech.md` for verified behavior and cold-start limitations.
- Keep one captured voice for greeting, conversation and farewell; changes during a
  guest apply to the next guest. Maple defaults only when no browser preference exists.
- Voice assets: `frontend/public/voice/` → build → `trendcoffee/static/voice/`.
  Read the consistency evaluation before preparing clips; context recovery needs no render.
- Baseline: `gpt-6-luna`, medium reasoning, Fast/priority disabled (user decision 2026-11-03). The user authorized model/
  configuration trials for latency on 2026-10-24; see `docs/evals/native-input-latency.md`.
  Preserve AV Fusion speaker ownership and validate a replacement before deploying it.
- Greeting requires a fresh microphone packet, visual worker readiness and a ready
  native connection. Preserve the A/V acceptance gate and guest-generation checks.
- Voice latency work must stay on ChatGPT/Codex native login. The user declined
  a separate Realtime API/key path on 2026-10-24; do not request API credentials.
- Keep the complete menu available for reasoning; only real tool results authorize
  business success. Enforce freshness, backend pricing and guest capability boundaries.
- Submit a specified order with known fulfillment once; ask only for missing information.
  Explicit “chọn giúp/chọn cho mình ... mang đi” authorizes selecting a fitting real item
  and placing it without a second confirmation. Advice-only/view-only stays read-only.
  When the requested order has a pending QR, final speech is only the tool's `qr_reply`
  (“Bạn quét QR trên màn hình để thanh toán nhé, thẻ của bạn là số N.”). Verified paid status
  gets a paid answer. Pickup cards: every new order gets card 1–16, rotating, advancing only past a paid order (an unpaid order, even with a live QR, leaves the number for the next order); it is in the merchant
  order description (no card header on the printed invoice, user decision 2026-11-06); see `docs/superpowers/specs/2026-11-06-vibrating-card-design.md`.
  See `docs/evals/qr-checkout-flow.md` for the payment contract and fixture evidence.
  Keep QR inline and stable checkout IDs on retries; preserve per-cup and whole-order notes.
- QR presence does not prove payment. Tests/probes use fixtures without real merchant
  orders, payment actions or printer jobs.
- Separate early speech, useful-result latency, prepared-call handoff and cold startup
  measurements. Passing fixtures do not establish physical acoustic performance.
- Preserve the warm source appearance; the bounded mouth opening is not yet
  visually accepted. Distinguish displayed FPS, generated mouth FPS and changed-pose
  rate; latest RTC trials did not reach the 15–20 generated FPS target.
- Kiosk UI & popup: Fullscreen idle assistant when inactive; General settings uses Radix Select.
  Product details open in a viewport-fitted popup (KFC style) sourced from synchronized public
  catalog; show real description/options, uppercase pill chips, localized quantity (VI: Số lượng,
  EN: Quantity), and close X only (no back button, no category badge, no synthetic notes).
- Keep requested UI changes in the existing kiosk. The checkout dock stays full width;
  cart and checkout results remain in the sidebar. Build frontend changes before viewing them.

## Style and verification

- Python snake_case; Ruff format/lint, 100-column lines. Domain failures use
  `ServiceError(code, status)`; adapters handle transport presentation.
- React components PascalCase, hooks camelCase; Prettier single quotes, no semicolons,
  100 columns. Follow existing async cleanup and guest-generation checks.
- Root tests: `.venv/bin/pytest -q`; focused tests live in `tests/test_*.py`.
- Root lint: `.venv/bin/ruff check trendcoffee tests`.
- Root format: `.venv/bin/ruff format --check trendcoffee tests`.
- In `frontend/`: `npm test`, `npm run lint`, `npm run format:check`, `npm run build`.
  Build first removes `trendcoffee/static/kiosk-assets`; protect active clients.
- Build before `PYTHONPATH=tests:. .venv/bin/python tests/browser_voice_smoke.py`.
  Keep timing-sensitive browser audio tests separate from native network probes.
- No root Git history, CI workflow or coverage threshold was detected during onboarding.

## Setup and operations

- Setup: `uv sync --locked`; HTTP: `uv run trendcoffee serve`; MCP: `uv run trendcoffee mcp`.
- Frontend: Node ≥22.12, `npm ci` then `npm run dev` in `frontend/`.
- Check runtime with `.venv/bin/python scripts/kiosk.py status` before deployment work.
  Start/stop services only within the requested operational task and protect active guests.
- Direct serve defaults to local queue. Launcher start enables merchant mode by default;
  use `TREND_MERCHANT_ENABLED=0` for local-only kiosk development.
- Default to C920 local camera priority; explicit device-camera selection overrides it
  only for the owned video stream. Preserve fallback on stream loss and unrelated Jarvis processes.
- `.env.example` is not auto-loaded. Keep credentials, guest tokens and local values private.
- Keep user-facing progress updates concise in Vietnamese.
