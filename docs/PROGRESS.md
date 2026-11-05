# Implementation progress

Plan: docs/superpowers/plans/2026-10-16-trend-agent.md

- Design: shared service, SQLite/FTS, local request queue, scoped memory; recorded.
- Discovery: completed read-only public branch/catalog/menu inspection and sanitized import; source boundaries recorded in research notes.
- Ruling: existing AGENTS.md remains untouched. No Git metadata exists, so worktree/commit automation is inapplicable; implement directly in the explicitly selected workspace.
- Ruling: local execution authorized by the user's build request following the service proposal; no repeated design-approval prompts. No deployment or production writes.
- Ruling: use current official MCP SDK 2.x; keep its API version pinned in the lockfile.
- Task 1: complete. Shared SQLite service, FTS retrieval, session capabilities, memory consent, integer pricing and idempotent local submission.
- Task 2: complete. Strict HTTP validation, scoped progress, staff authority, local agent routing and optional bounded semantic evidence selection.
- Task 3: complete. Official MCP SDK 2.3.0; ten tools, workflow resource, actual stdio list/call/error test. Project-scoped Codex configuration provided.
- Task 4: complete. Public branch/day menu imported: 51 variants and 13 knowledge records. Skill validator passed; independent behavior retest passed four scenarios, simulated without merchant mutations.
- Task 5: complete. Customer/staff browser flow, 375/768/1440 screenshots, automatic axe scan, package build and concurrent latency measurement.
- Regression suite: 49 tests passed; ruff and JavaScript syntax checks passed. Wheel layout smoke imported all 51 items from packaged data outside the source directory.
- Independent review: five Important findings fixed and rechecked; no Critical findings. Additional numeric-ambiguity tests prevent decimal/negative/unsupported compound quantities from becoming wrong quotes.
- Runtime semantics: memory preference30d, working draft15m, quote5m, menu evidence24h, other knowledge max30d. Unsupported customization/fulfillment is clarified, never silently dropped.
- Latency: see docs/evals/latency.json for final300-request/eight-session in-process measurement; this excludes model/network/POS latency.
- Browser: zero captured page errors/network failures or axe violations. Visual regression INCONCLUSIVE without approved baseline; no production CWV or full manual accessibility claim.
- Remaining integration boundary: merchant POS/bank adapters and production deployment are not connected. Operator token is intentionally unset by default. No actual merchant order or customer message was sent.

- Final preview: http://127.0.0.1:8080/; health/customer/staff/favicon HTTP200. Project-config MCP command exercised directly: 10 tools and 51 catalog variants. Current Codex CLI did not auto-load project MCP (`mcp get` not found); configuration is supplied, and host trust/reload remains host-controlled.

## React kiosk — 2026-10-16

Plan: [React kiosk implementation](superpowers/plans/2026-10-16-react-kiosk.md).

- Implemented the approved React/TypeScript/Vite/Tailwind/shadcn (Radix) frontend. Forest green/ivory/terracotta, left categories, product grid, sticky cart and touch layouts. All 51 published variants retained; 49 public product photos optimized to about 0.59 MB. Two missing photos use neutral placeholders. Behance preview informed layout; full reference was not accessible.
- Product details expose published options only. Explicit at-table/takeaway, required table, authoritative server quote and separate confirmation remain intact. No merchant/POS/payment integration added.
- Assistant, sourced answers, support messages, consented preferences/deletion and progress are available in sheets. Staff console preserved.
- Guest token remains in memory. Next guest/reload starts a new session; idle warning at 90 seconds, reset at 120 seconds without interaction. Submitted requests are retained. Late quotes validate both cart revision and guest generation. Submission is guarded against concurrent clicks and remains server-idempotent.
- Radix scroll-lock CSS uses a per-request nonce under the existing CSP. No unsafe-inline permission added. Frontend build cleans only kiosk-assets; source archives explicitly exclude node_modules/runtime.
- Final verification: 50 pytest tests, 7 Vitest tests, TypeScript/Vite build, oxlint, Prettier, ruff check/format and npm audit (zero reported vulnerabilities) passed. Deterministic browser regressions cover late manual/chat quotes, boot retry, old-guest replies, mobile reset and idle reset. Fixture timestamps are refreshed only in the disposable test database.
- Browser checks: 375/768/1080/1440 widths without horizontal overflow; zero captured console/network errors and zero axe violations across menu, detail, review, progress, assistant, mobile review and staff views. Screenshots inspected. Visual regression remains INCONCLUSIVE without an approved baseline; manual screen-reader coverage and field INP are not established.
- Local synthetic performance: five fresh Chromium contexts, menu-ready about 208–319 ms; maximum sampled LCP 292 ms, CLS 0.00023. No network/CPU throttling; not a customer-network SLA. Evidence: [kiosk latency](evals/kiosk-latency.json), [browser QA](evals/browser-qa.json).
- Independent reviewer identified three issues (late assistant quote, hidden mobile reset, boot retry epoch mismatch); all corrected and re-review passed. Additional regression fixes assistant-quoted duplicate line merging.
- Wheel built and smoke-tested outside the source tree: root nonce HTML, JS/CSS, photo manifest/all49 photos, staff page and51 catalog variants. README and frontend guide include development/build commands.
- Preview remains http://127.0.0.1:8080/. Existing AGENTS.md unchanged. No publication, merchant mutation or outbound customer message.

## OpenJarvis / Audio / Visual discovery — 2026-10-17

- [State and timing research](research/openjarvis-kiosk-state.md) maps interaction/voice/speaker/business ownership, selected preset versus defaults, turn/STT/Responder deadlines, cancellation, queues and copied-environment paths.
- OpenJarvis already selects the Audio adapter in its ordering preset; its environment imports the original jarvis/Audio source. OpenAIMK's copied directories do not yet provide a connected Audio/Visual workflow.
- Source-only gap reproduced: one stale near-person observation can enter active and retain a session without fresh events. Frozen-frame emission, timer ownership and session-generation alignment are integration priorities.
- Focused OpenJarvis tests: 48 passed in 13.64s, with two existing dependency warnings. Pure evaluator probe only; no live camera/microphone/model or merchant call. Upstream OpenJarvis application/configuration unchanged; pre-existing dirty files preserved. AGENTS.md unchanged.

## AV Fusion → native Codex voice — 2026-10-17

- Connected copied Audio/Visual and sibling Metric3D within OpenAIMK only. Root AGENTS.md and original jarvis source remain untouched. Current-source imports are validated; model caches/checkpoints stay in `.runtime`.
- Operator arms browser devices once. Visual processed-frame sequence/timestamp and expiring PAD evidence create a fresh guest/thread after continuous presence. Shared server authority controls touch/voice cart, fulfillment, quote, confirmation, payment status and progress.
- Audio uses Sortformer/TitaNet/TSE + VisionAudioBridge and the full requested Visual model stack. Unlocked/stale/rejected/unseparated audio is silenced before native voice. Browser camera is about15fps to support Light-ASD crop windows.
- Native CLI0.163.0 WebRTC works with the current ChatGPT login. Backend owns the media track and only feeds filtered PCM; raw browser RTC is never used. Native WebSocket rejected ChatGPT auth. Code Mode host must remain available for dynamic tools; shell/apps/plugins/web/foreign MCP remain disabled, sandbox read-only, approval never.
- Packet capture and playback are generation-bound; reset discards partial mic/delayed/TSE/playback state. Native process exit disables voice. Complete affirmative customer turn must have a recorded ID/start after the quote; fragments, refusals, unknown IDs and pre-quote speech never authorize submission.
- Independent review findings fixed and rechecked: stale queued touch command, negation/ambiguous confirmation, stale perception provenance and missing-turn fallback. No remaining Important/Critical finding from focused re-review.
- Final checks:79 backend tests,100 copied-Visual tests,9 frontend tests; build/typecheck/oxlint/Prettier/ruff passed. Browser fake-device/fixture flow verifies shared cart, new guest and disarm at375/768/1440, zero captured console/page errors and zero axe violations. No approved visual regression baseline.
- Live native smoke: synthesized speech invoked `kiosk_menu` against a fixture and returned audio. Real warmed Fusion rejected synthesized speech without a live face: no speaker lock and zero user transcripts. Warm controller→listening one sample2,947ms; excludes presence/enrollment and is not p95/SLA.
- Launcher manages only owned workspace processes, API/UI8080 + Visual9877. Remote browser needs one SSH forward to8080. [Workflow](workflows/kiosk-voice.md), [evidence](evals/voice-integration.json).
- At-counter real camera/microphone/PAD/lip-sync/overlap/calibration acceptance remains unverified. Payment/POS remain disconnected; requests stay local pending and payment unverified. No merchant write or outbound customer message performed.
# Merchant QR and multi-item ordering — 2026-10-17

- Fixed whole-utterance menu matching: independent names/queries, accent-insensitive and `cafe` support, per-query unmatched results; actual MCP stdio regression covers three drinks and a single multi-line quote.
- Added atomic native cart `lines` additions and corresponding instructions, preserving quantities/options and preventing partial writes.
- Managed kiosk/project MCP now enable merchant guest checkout after exact quote confirmation. Merchant-generated QR is displayed with amount/expiry; scoped reads refresh payment, including late settlement after QR expiry. Persisted creation claims prevent blind duplicate POSTs; malformed/mismatched responses suppress payment and retain merchant references.
- Validation: 104 backend tests, 11 frontend tests, real isolated-browser checkout; build/lint/format passed. Independent review findings resolved. See [verification](evals/merchant-checkout.md) and [workflow](workflows/merchant-checkout.md).
- Stack kept stopped. No live merchant order or payment was created during verification; actual QR scan/settlement remains field acceptance.

# Avatar assistant layout — 2026-10-17

- Replaced the top voice strip with a fictional Trend barista portrait, actual voice transcript log, PCM-driven waveform and camera/microphone controls. Desktop uses assistant/menu/cart columns; tablet/mobile put the assistant above the menu.
- Optimized the generated portrait to a self-hosted WebP of approximately 138 KB. Asset prompt and interaction details: [design](design/avatar-assistant.md). Portrait is static; no lip-sync renderer is claimed.
- Validation: 14 frontend tests, 104 backend tests, build/lint/format; dedicated browser smoke verified playback waveform, both speakers, shared cart and next-guest clearing. Screenshots/axe at 1440/768/375 had no errors/violations or horizontal overflow. Independent review found no Important/Critical issue. [Verification](evals/avatar-ui.md).
- Managed stack kept stopped; operator starts it when ready. No real device capture or merchant write during checks.

# Spoken menu candidates and automatic invoices — 2026-10-20

- Menu lookup now resolves clear spelling/speech errors and offers up to three real catalog candidates for uncertain names. Reported “trà bắp miền Bắc/Nam” variants surface Trà Bắc; generic beverage words do not invent flavors. Browser displays backend candidate IDs and resets them on manual filtering or guest change.
- Added `print_invoice` / `get_invoice_status` MCP tools, scoped HTTP invoice routes and a durable worker independent of customer page/voice lifetime. Official merchant-completed payment and invoice PDF are required. Unique order/invoice records, held CUPS jobs and persisted transitions prevent duplicate submissions after concurrent calls or restart.
- Launcher/project MCP use GP-C180I on next start; direct serve/MCP can disable via empty `TREND_PRINT_QUEUE`. Existing orders are not automatically enrolled. Stack remained stopped; no merchant order/payment or physical test print was created.
- Final verification: 175 Python tests, 15 frontend tests, build/lint/format; independent invoice review passed. Actual project MCP registered 14 tools. Synthetic PDF raster conversion and isolated browser candidates passed. [Evidence and limits](evals/invoice-and-menu-matching.md), [printer operation](workflows/invoice-printing.md).

# Whole-menu recommendation reasoning — 2026-10-20

- Native sessions now receive all current catalog records and reason about preferences without name/keyword overlap. Selected real IDs control display; unclear name lookup includes the full catalog for agent review. MCP reads the whole menu for recommendation requests. No additional model round trip/provider or fruit-keyword mapping was added.
- Actual Luna medium turns handled `trái cây` and fruit/no-coffee/below-50k preferences using one display call each, valid current IDs/prices, short replies and no order mutation. Browser semantic-ID display passed. 179 Python tests and Ruff passed; stack remained stopped. [Evidence and limits](evals/menu-intent-reasoning.md).

# Order notes and voice output — 2026-10-20

- Added compact per-item/whole-order notes to touch, native voice, HTTP and MCP checkout. Different notes preserve separate cups; typing survives slow server echoes, edits preserve row identity, retries bind normalized notes, and notes clear with the cart/guest. Merchant payload carries both scopes while exact kiosk echo validation remains intact.
- Reproduced packet-boundary distortion from 24→48 kHz browser resampling. Native assistant output and browser playback clock now both use 48 kHz. Real native speech rendered continuously without the prior boundary error; physical speaker listening remains unverified.
- 188 backend/browser tests and 17 frontend tests passed; build/lint/format passed. Actual Luna processed distinct per-cup notes and an order note in one fixture order. Stack remained stopped; no real merchant order/payment/print. [Evidence](evals/order-notes-and-voice.md).

# Streaming speech continuity — 2026-10-21

- Reproduced output loss under backpressure (100 packets → 64), quiet onset clipping and loss of approved microphone audio after a 300 ms scheduler stall. Native media now uses awaited delivery rather than the lossy shared control queue. Input scheduler re-anchors without clearing the approved bounded buffer.
- Native assistant turn boundaries lower the speech threshold for quiet phonemes; idle codec comfort noise remains suppressed so it cannot continually duck customer input.
- Browser playback now uses a continuous AudioWorklet queue, an 80 ms startup target, continuous rate conversion for boundary recordings, and 3 ms ramps at starvation edges. It no longer creates one AudioBufferSource per network packet. Guest reset clears the queue and ignores retired events.
- Chromium tests cover real-time delivery with 45 ms UI stalls, full sample continuity away from edge ramps, and the existing native packet rendering regression. Built UI smoke covers mic, greetings/goodbye, shared cart, notes and guest isolation. Native/model transport jitter and physical speaker listening remain explicit limitations; production stack remains stopped. See [streaming voice evidence](evals/voice-streaming-continuity.md).

# Voice startup and transcript latency — 2026-10-21

- Prefer the default-route ICE candidate; keep the original candidates when no matching route exists. Increased the premature outer 10-second timeout to 30 seconds after observing a valid handshake take 16.737 seconds. Explicitly cancel/await outstanding STUN checks during teardown so retries cannot target closed UDP sockets.
- Prepare one silent, unused voice connection before a guest arrives; reject tools until adoption, expire unused calls, validate catalog and transport, and never reuse a prior guest thread. Arrival joins preparation rather than opening a competing second connection.
- Display incremental transcript in one stable bubble. Keep full menu on backing Luna/medium, short realtime instructions, and no acknowledgment filler. Model/effort and AV Fusion checks remain unchanged.
- Browser playback now adapts its bounded startup buffer to device render batches; the previously failing timed Chromium sample-continuity test passes even with 45 ms UI stalls. Separate 240 ms short-tail deadline preserves tiny utterances without prematurely starting a partial opening.
- Final verification: **200 backend/browser tests**, **20 frontend tests**, production build, Ruff, oxlint, Prettier and responsive browser smoke passed. Test work issued no real order/payment/print.
- Deployed API 8080 and Visual 9877. Stopped only the previously authorized Jarvis Visual process; Trend owns C920 and reports current local frames. Native connection probes improve but do not prove reliability: first improved batch 6/6 within 10 seconds, repeat with kiosk running 5/6. Useful response remains **8.004 seconds** in the latest fixture; requested 1–2 seconds is **not achieved**. Physical microphone/speaker latency remains unverified. [Evidence and remaining limits](evals/voice-connection-latency.md).

- Final live probe under the actual 30-second outer budget: **1/3 connected**, two timed out after ICE completed but before DTLS/data channel readiness. Startup reliability remains unresolved; do not interpret passing local tests or an earlier 6/6 batch as completion. Evidence: `output/connection-cycles-final-30s.json`.

# Persistent voice recovery — 2026-10-21

- Idle voice preparation now renews expired/closed calls and retries failures with bounded backoff. During a guest session, startup/recovery keeps retrying instead of stopping after two failures; each transport attempt is bounded to eight seconds and ownership/cart state remains with that guest. Guest departure/idle expiry stops retries.
- Own/cancel aiortc connect tasks before transport teardown, closing the distinct late-connect/closed-ICE race. Browser reconnect handles server restarts and reset generation counters; explicit mic-off/unmount cancels retry and retired sockets cannot mutate current state.
- Requested Fast/priority for the unchanged Luna/medium backing model, supported by installed model metadata. Useful speech measured 6.260 seconds in one native fixture; 1–2 seconds remains unmet. Maintained native handoff: 6/6, 0.038–0.120 ms, but preparation itself still took 4.120–57.525 seconds including retries. Deployed API/Fusion/native test: `listening` in 0.016 seconds from a prepared call, no audio/order/payment/print sent.
- Verified 203 backend/browser tests; 15 latest focused prepared/socket/AV checks; 20 frontend tests, production build, lint/format and built-browser restart/reconnect/mic-off/guest-isolation smoke. API 8080 and Visual/C920 9877 running. [Evidence and remaining limits](evals/voice-connection-latency.md#recovery-follow-up--2026-10-21).

# Voice speaks before tools — 2026-10-21

- User clarified the desired flow: brief immediate acknowledgment → tool call → actual result. Enabled native delegation acknowledgment and instructed one 4–8-word acknowledgment, no confirmation gate, no success claim before tool results, at most 30 combined words.
- Native fixture: first spoken acknowledgment at **1.624 s**, menu tool starts **5.527 s**, returns **8.528 s** (deliberate three-second fixture delay), then actual menu result is spoken. 17 focused tests and Ruff passed. `output/ack-before-tools.json`.
- Apply the API update after the active customer finishes; retain the current cart during that wait.

- Applied acknowledgment update after the active guest ended; API restarted as owned pid 378120, C920 Visual remained running. Native fixture confirms first speech precedes the tool call.

# Explicit laptop/phone camera selection — 2026-10-21

- User accesses from a home laptop through SSH local forwarding. local_camera_available=true describes the server camera; previously it prevented browser capture and the Visual router also rejected remote frames while local frames were fresh.
- Added Camera tại kiosk / Camera thiết bị này selection before arming. Device mode requests camera and microphone together, keeps browser video despite healthy local telemetry, and forwards a validated preference through the authenticated controller to the owned Visual stream. Default C920 priority, stale/disconnect fallback and Fusion speaker verification remain.
- Witnessed failing regressions before implementation, then 212 root tests, 29 Visual camera/router tests and 20 frontend tests passed. Production build, Ruff, oxlint and Prettier passed. Browser regressions use fake capture and merchant/native fixtures; actual remote-laptop/phone camera quality remains unverified. No real order/payment/printer job was sent.
- Runtime status before deployment: API 8080 and Visual 9877 both not managed/not ready. Source and built frontend updated; subsequent runtime checks determine deployment status.

- Final review also reproduced and fixed video-only loss closing the microphone/session and frozen JPEGs preventing fallback. Final verification: 212 root tests in 52.42s; 20 frontend tests; responsive browser smoke without console/axe errors. Started owned API 8080 / Visual 9877, verified both listening, HTTP health and new served camera selector; passive Visual local availability: true. [Evidence](evals/remote-camera-selection.md). Physical remote-device capture still needs browser permission/testing.

# Audio upstream update deployed — 2026-10-21

- Fast-forwarded Audio main from f0f168eb to latest upstream 7538d785: duplicate diarizer slots belonging to the same customer count as one voice. Visual already matches latest feat/mouth-activity a2289d5; existing kiosk camera/freshness patches preserved.
- Added a host-boundary regression using actual FusionGate and accepted_pcm. Observed failure before update and success afterward; other-speaker overlap and stale-evidence silence remain enforced. Full Audio: 279 passed, 3 skipped; kiosk: 213 passed; selected current Visual: 48 passed. Ruff and diff checks passed; review found no material findings.
- Services were found stopped during validation; their exit cause was not established. Started owned Visual 146382 and API 146421 with new Audio worker 146428. Both ports listen, HTTP health ok, voice_prepared=true. No real customer audio/order/payment/print was sent. Physical acoustic quality and native useful-result latency remain unverified. [Update and deployment evidence](evals/audio-upstream-update.md).

# Website Codex voice settings — 2026-10-23

- Added Giọng nói selector, populated from installed Codex 0.163.0 thread/realtime/listVoices v3 list: 25 voices plus the default option. IDs are validated by the backend; no guessed gender labels or v2/TTS voice mixing. Browser remembers the choice for the current origin.
- Active guest voice/cart remain intact when changing preference; next session uses the new voice. Both PCM/WebRTC carry the per-thread choice; incompatible prepared calls are retired. Browser regressions cover persistence, delayed socket open and guest-boundary-before-settings-ack races. Review found both races, witnessed failures before fixes, and passed the final changes.
- Final verification: 223 root tests, 20 frontend tests, production build/lint/format and responsive browser smoke passed at 1440/768/375 px without browser/axe errors. Isolated real native Maple session connected; no customer audio or business action sent. Prerecorded greeting/goodbye retain their current voice; no all-voice acoustic comparison was performed.
- Started owned Visual 32786 / API 32832 after verification; both ports listen, health ok, voice_prepared=true. Live endpoint returns 25 voices, and deployed browser DOM shows 26 options including default with no page errors. [Evidence and limits](evals/codex-voice-settings.md).
# Consistent selected voice — 2026-10-24

- Greeting, conversation and farewell now share the guest-captured native v3
  voice. Mid-guest selection changes apply from the next guest, including the
  current guest's farewell remaining in their original voice.
- Prepared 48 transcript-verified 48 kHz WAV clips for 23 accessible named voices
  plus native default. Porto/Selva return upstream `forbidden` and are excluded
  from selection; the CLI still advertises both. An offline preparation command
  and manifest preserve the source assets and verification evidence.
- Final backend/browser suite: 234 passed; frontend: 20 passed; production build,
  targeted lint/format and deployed catalog/asset/browser checks passed. Restarted
  only the owned API while idle; Visual stayed running. Existing tabs need reload.
  [Evidence and limits](evals/consistent-kiosk-voice.md).


# Immediate microphone feedback — 2026-10-24

- Reproduced the ready-session display waiting on Fusion speaker lock. Removed
  that lock from local listening/waveform presentation while preserving native
  PCM approval and all business authority.
- Chromium measured 70.8 ms local mic feedback before speaker lock; verified
  silence, backend capture, partial-text updates and disarm cleanup. Full backend/
  browser: 235 passed; frontend: 21 passed; production build/lint/format passed.
- Physical Fusion/native transcript latency remains unresolved by this display
  fix. Owned API/Visual both not managed/not ready; built static files updated,
  no service started/restarted. [Evidence](evals/immediate-microphone-feedback.md).

# Actual native input latency — 2026-10-24

- User clarified that real transcript/spoken-response latency must improve;
  the preceding UI microphone feedback work did not fulfill that request.
- Reproduced and fixed redundant startup silence queued by FilteredTrack before
  approved speech. Actual media replay removes 400 ms; subsequent spoken samples
  and pauses remain intact. Full suite: 236 passed; Ruff lint/format passed;
  independent review passed. Audio/Fusion policy experiments were reverted.
- User authorized other configuration/model trials. Luna low and gpt-live-1 did
  not establish a clear reliable improvement; native V1/V2 were unavailable via
  the tested CLI routes. Production retains its original model/voice settings.
- Owned Visual/API were started and pass health/preparation checks. The broader
  immediate transcript/reply target remains unmet. Realtime API trial needs local
  API credentials; no OPENAI_API_KEY or provisioning tool is currently available.
  [Measured evidence, reproduction and remaining work](evals/native-input-latency.md).

# Native-only latency constraint — 2026-10-24

- User explicitly declined a separate Realtime API path. Continue actual audio/
  transcript/answer latency investigation using ChatGPT/Codex native login only.
  Configuration/model trials remain authorized within that constraint; no API key
  setup is requested. The existing native queue correction stays deployed.

# Native-only follow-up probes — 2026-10-24

- Retained ChatGPT/Codex native login; no separate Realtime API or credential setup.
- Restored-onset, social-prompt, native PCM sideband, smaller Sortformer chunks,
  older Luna/low and speakable final-answer routing were tested in isolation.
  None established a reliable overall latency improvement without another
  regression; no experimental route/model/buffering policy was deployed.
- Short-utterance tests expose real initial-word loss during identity acquisition.
  Post-lock replay restores recognition but can add paced catch-up delay, and a
  complete fast reply is not established. Existing six-row verification remains.
- Current deployed improvement remains the 400 ms startup-silence queue fix.
  Immediate native transcript/reply target remains unmet; the investigation and
  measured tradeoffs are recorded in [native input latency](evals/native-input-latency.md).

# Live merchant tables and automatic at-table selection — 2026-10-26

- Added HTTP `/api/tables`, MCP `get_tables` and native `kiosk_tables`. Each reads
  current merchant table status; questions no longer rely on saved knowledge or
  a claim that the assistant cannot view tables. Unknown status is not free.
- At-table without a specified table picks the first `available` row in merchant
  order. Touch auto-fills an editable input; voice shares the selected table;
  HTTP/MCP checkout handles omitted labels. Explicit choices and idempotent
  retry selections remain intact. Selection is not reservation; full/offline
  states are reported honestly. Local-only mode retains manual entry.
- Updated the service skill and native instructions. Independent review found
  controlled-input and polite-suffix bugs; failing regressions preceded fixes.
  Real Codex native text turns passed five live-tool scenarios using isolated
  merchant fixtures; a separate public merchant GET succeeded. No live order,
  payment or new print request was created by tests/probes.
- Final verification: 267 backend/browser and 21 frontend tests passed; production
  build, lint/format and skill validation passed. Earlier runs exposed an
  intermittent unchanged playback sample-comparison failure, documented rather
  than attributed to table code. [Evidence](evals/live-merchant-tables.md).
- Started the previously stopped owned Visual/API services. Both ports listen;
  deployed health is `ok`, merchant table reads succeed and native voice is
  prepared, with no active guest. Existing tabs need reload; existing MCP
  connections need reconnecting for the newly registered tool.

# Real merchant categories — 2026-10-27

- Replaced the hardcoded category rail and invented display aliases with the
  merchant `/catalogs` IDs, names and order. Kept all eight real groups, including
  empty ones; “Tất cả”, “Bán chạy” and “Món mới” match the merchant customer UI.
  The latter two use actual `isTopSell`/`isNew` product flags, not guessed labels.
- `sync-public` fetches categories plus the approved public menu and persists
  both atomically. Category responses stay complete during product searches;
  filtering uses stable IDs. Existing seed/legacy imports remain supported.
- Witnessed six backend and three responsive-browser regressions fail first.
  Final verification: 276 backend/browser and 21 frontend tests passed, with
  build/lint/format and independent review. Public read verification found
  51 variants, 4 best sellers and 1 new item. No real order/payment/new print
  request was created by validation.
- Refreshed the local production snapshot. Services were found stopped during
  work; started the owned Visual/API and verified health, native preparation,
  all 11 deployed category choices and per-category counts at 1440/768/375 px.
  Existing tabs need reload. [Evidence](evals/merchant-categories.md).

# Simple assistant settings popup — 2026-10-27

- User simplified the separate settings page to a popup and invoked
  `karpathy-guidelines`. Moved the existing voice and camera dropdowns into the
  existing dialog; microphone controls stay on the assistant. No route, new
  dependency, backend or voice/camera hook change.
- Retained selection handlers, busy/armed guards and next-guest voice behavior.
  Three responsive popup cases and six existing voice/camera boundary cases pass.
  Independent review found no material findings.
- Final verification: 279 backend/browser and 21 frontend tests passed, plus
  build/lint/format. Built assets update the running site without restarting
  services; existing tabs need reload. [Evidence](evals/assistant-settings-popup.md).

# Reference order rail and visible removal — 2026-10-27

- Reworked the cart toward the supplied Cuberto/Dribbble reference: narrow right
  rail, stacked centered product photo/name/unit price, compact quantity controls,
  source-measured yellow actions and bottom subtotal/checkout. Removed the
  redundant floating mobile cart bar. Actual merchant photos, VND and Vietnamese
  labels remain. Source font is unavailable; Arial/Helvetica approximates it.
- Product summaries expand their note editors; the whole-order note is a
  disclosure below fulfillment. The user's follow-up moved the remove icon
  outside the disclosure, always visible beside quantity controls, including on
  narrow phones. Submitting locks it with the other cart mutations.
- QR/results expand the rail/full row to retain a readable merchant QR. Standard
  screens keep the footer while products scroll; review found and tests reproduced
  clipping on short landscape screens before adding the scrolling fallback.
- Six responsive cases, customer/merchant journeys and voice smoke cover real
  quantity math/unit prices, notes, removal, retry identity, QR/status, guest
  isolation and reconnect. Frontend 21 tests/build/lint/format and independent
  review passed; runtime read-only browser verification passed without restarting
  services or creating real orders/payments/print requests. Full-suite output and
  measured limitations are in [the evaluation](evals/reference-order-rail.md).
- Final follow-up verification: 285 backend/browser tests passed in 92.52 s,
  21 frontend tests passed, and deployed removal/rail checks passed at 1440/375 px.
  The remove button is visibly accessible without expanding an item.

# Fullscreen idle assistant — 2026-10-27

- Armed kiosk with no active guest now shows only a centered assistant fitted to
  the viewport: avatar, bubbles, waveform and controls. Presence/manual session
  start restores header/menu/cart; ending the guest restores fullscreen waiting.
  Active guests waiting for native voice or speaker ownership retain ordering.
- Kept the assistant mounted through ended/token refresh and closed header settings
  portals on idle. Touch ordering remains available when the microphone is off.
  Proportional width handles tall 1080×1920 kiosks as well as short landscape.
- Five responsive idle cases and six existing presence/speech/camera boundary
  cases pass. Updated stale quick-add test selectors for the existing product-panel
  flow, retaining cart/note/checkout assertions. Final full suite: 290 passed in
  105.05 s; frontend 21 tests/build/lint/format, Python lint/format and voice smoke
  passed. Independent review found no material issue.
- New assets are served by the existing Visual/API processes without a restart.
  No real merchant order/payment/new print action occurred. Reload existing kiosk
  tabs. [Evidence and screenshots](evals/fullscreen-idle-assistant.md).

- Visual follow-up from user screenshot: remove the idle card border/radius and
  outer padding; fill the screen with a muted sage background. Production build
  passed; existing kiosk tabs need reload.

# General settings and styled select menus — 2026-10-27

- Rebuilt Settings around the supplied neutral reference: 760×500 dialog, left
  navigation, three theme tiles and compact right-side controls. General is active
  on open; Profile, Data and About have blank selectable panels. Phones use a
  compact navigation row and contained scrolling.
- Light/Dark/System and VI/EN apply immediately. System tracks live OS changes;
  explicit themes override OS color mode. Theme/language persist only explicit
  browser choices; customer UI labels translate while merchant/user content stays
  intact. Existing voice/camera handlers and capture/next-guest guards remain.
- Follow-up screenshot request replaced platform select menus with installed Radix
  Select for Language/Voice/Camera: floating rounded lists, hover rows, selected
  checkmarks, scrolling, viewport collision handling and CSP nonce. Empty default
  voice decodes back to the existing empty-string API value.
- Five General cases cover preference persistence, locale, menu bounds, selected
  marker, keyboard selection/Escape, unchanged cart and focus. Five idle cases also
  close nested menus at guest end; six speech/camera boundary cases retain their
  original assertions. Independent review verified long-list/default selection and
  zero accessibility violations after two Dark contrast fixes.
- Production build, frontend 21 tests/lint/format and Python lint/format pass. Built
  popup/select styles are served by the existing healthy API without a restart.
  Reload existing tabs. [Evidence and screenshots](evals/general-settings.md).
- Final full-suite verification after the Select update: 292 passed in 119.29 s.

## Product detail popup — 2026-10-28

- Changed the inline product panel to a centered Radix popup following the KFC reference: image, real category/title/price/description/options, quantity row and full width red add button. User confirmed retaining the synchronized public catalog to keep prices consistent with checkout. Removed the staff customization note and synthetic description fallback.
- Back/close/Escape, focus return, viewport scrolling, light/dark themes, add-and-close and guest/idle clearing are supported. Built assets updated; existing services need no restart.
- Validation: 19 affected browser tests passed; final customer/staff journey passed again after CSS cleanup, including four popup viewports and light/dark accessibility checks. Frontend 21 tests, build, lint, format and changed Python lint passed. All ordering checks used isolated fixtures. [Evidence](evals/product-popup.md).
- Popup follow-up: hid the category label, changed the quantity prompt to localized `Số lượng` / `Quantity`, then removed the back button per user request. The close control remains.

## On-demand voice — 2026-10-28

- Removed idle native voice preparation at startup, candidate presence and guest teardown. Local Fusion warmup remains. Greeting is sent once after native voice and Fusion are ready, with generation checks; no early greeting on connection failure or guest exit. Native connection attempt timeout is 20 seconds with retries while a guest remains active.
- API restarted when status showed no active guest; initial new status showed no active or prepared voice call. Both API and Visual were later observed stopped for an undetermined reason. Start the kiosk and reload the frontend. Isolated unit/browser and frontend checks, limits and quota measurement caveat: [evidence](evals/idle-voice-on-demand.md).

## Camera source and departure — 2026-10-28

- Pinned the explicit kiosk/device source, removed browser fallback to an unselected camera, and rejected stale results from the previous camera. Manual guests now end on departure/sensor-loss like automatic guests; ending starts native teardown and clears the active guest state.
- Root suite 300 passed; focused Visual 39 passed; browser subset 11 passed. Wider Visual environment limitations and runtime activation state: [evidence](evals/camera-source-and-departure.md).
- After an active-customer check deferred restart, the user explicitly authorized interrupting the test session. Both owned services were restarted and checked listening; final status was idle with no active/prepared voice. Reload the browser to receive the camera capture changes.

## Kiosk media continuity — 2026-10-30

- Deployed short-gap AudioWorklet recovery, video-only Ditto negotiation, complete timestamped pose trajectories, overlap fusion, packet-gap handling and upstream mutation isolation. The native voice path remains independent; legacy engines retain their media negotiation.
- Persisted a 0.8 GPU-path work-time budget in the avatar manifest/launcher. Avatar-only tests sampled GPU utilization 85.54% → 68.62%; generated frames 10.2 → 8.4/s; changed-expression frames 7.0 → 7.4/s. RTP remains 12 FPS including repeats. These are short synthetic runs, not live Fusion/acoustic acceptance.
- 58 focused Python tests, 37 frontend tests, frontend build/lint and touched-file Python/TypeScript checks passed. Actual GPU/browser speech, wave, interruption and reconnect regression passed. Cold-start capability refresh has its own regression test. Managed visual/avatar/API ports 9877/8010/8080 are ready; final state has no active guest.
- Original lip/tooth appearance is still unaccepted. A controlled 5/10/20/50-step comparison did not restore source anatomy; no higher-step runtime is deployed. Measurements, artifacts, remaining limits and the unrelated existing frontend format failure: [evidence](evals/kiosk-media-continuity-2026-10-30.md).

## Avatar state appearance — 2026-10-30

- Reproduced the state mismatch: sharp poster/idle were from the standing clip; speech used differently lit `123_…`. Selected the existing standing clip as the common non-gesture source, preserving the preferred poster. Poster/source RGB MAE 20.17 → 0.009/255.
- Replaced broad neural face putback with landmark-aligned mouth/lower-jaw composition. Original eyes, hair, skin, clothing and background remain unchanged outside that region. Registration reuses its existing landmark pass. Idle and speech share one source/frame clock.
- 69 focused tests passed, including red/green pixel-preservation and frame-clock regressions; changed Python files pass Ruff. Actual-model comparison across nine cases: measured upper-face RGB difference 4.06 → 0/255 before encoding.
- Managed services are running with the new source/compositor. Browser smoke failed during overlapping runtime use and is not claimed passing; real voice was subsequently confirmed active, so further GPU/peer tests were deferred. Generated lip/tooth anatomy remains a separate limitation. [Evidence and comparisons](evals/avatar-state-appearance.md).

## Continuous avatar presentation — 2026-10-31

- Separated 24 FPS source presentation from the GPU mouth worker, removing the whole-body hold during PCM gaps. Mouth textures follow current source landmarks. Short positive-affine transitions use one texture; an earlier dense-flow crossfade that produced tooth fragments was rejected.
- Actual decoded RTC cadence is 23.995–24.026 FPS across speech, gap, resumed speech and waving. Interval p95 43.74–44.63 ms; maximum 46.60 ms; 305 recorded frames with zero recording drops. Neural rendering remains 8.6 FPS, distinct from source presentation and geometric transitions.
- 79 focused tests and changed-file Ruff checks pass. Final isolated GPU/browser speech, wave, interrupt and reconnect regression passes in 34.66 s. The native audio path is unchanged. Ditto/budget 0.8 are retained; manifest FPS metadata is 24.
- [Measured evidence and actual preview](evals/avatar-smooth-presentation.md). Subjective mouth naturalness, original tooth anatomy and physical acoustic synchronization remain separate acceptance items.
- Final activation: owned ports 9877/8010/8080 listening; Ditto ready, video-only, no engine error, 24 FPS presentation/publishing, budget 0.8 and no active guest. Exclusive test server 8011 stopped.

## Neural throughput and original resting smile — 2026-10-31

- Restore the actual source smile after 280 ms without voiced assistant PCM. Silent packets skip neutral inference; resumed speech cannot flash the old final mouth. The source presenter continues at 24 FPS.
- Prepared `tensorrt-mouth` keeps original weights, full 512px coordinates and full-frame normalization statistics, with a dedicated GPU stream and per-call conditioning reuse. The partial final decoder supplies only pixels actually used by the compositor. Every one of 383 source/gesture regions and source identity is validated before use.
- Actual RTX 3060/decoded RTC: 15.6 generated mouth FPS in speech, 16.0 while waving, received video 23.982–24.027 FPS, p95 intervals at most 44.60 ms; 476 frames recorded without drops. Changed-pose rates differ (8.8 speech, 15.4 wave); these are not 24 neural FPS or guaranteed 15 distinct expressions for every phrase.
- Current-weight displayed-mouth checks pass unchanged RGB255 error limits across five inputs and all 383 source regions. The original unmasked-rectangle comparison remains failed and is not called full-face equivalence. The selected backend has a narrower source-compositor contract and rejects changed/uncovered source clips.
- 110 focused Python tests, 26 frontend tests, touched-file Ruff and actual GPU/browser regression pass (34.76 s). Profile budget changes from 0.8 to 1.0; isolated GPU samples averaged 69.90%, max 91%, peak 4,098 MiB. Live Fusion/acoustic quality is outside this measurement. [Evidence, preview, cache preparation and rollback](evals/avatar-neural-throughput.md).
- Activated the validated profile: managed Visual 9877, avatar 8010 and API 8080 listen; avatar/API ready, video-only, no engine error, source mouth while resting and no active guest. Test port 8011 is closed. Verified the preparation guard rejects running services before GPU imports.

## Bounded mouth opening — 2026-10-31

The user clarified: preserve the standing avatar’s warm face/color; correct excessive opening. Source-switch and original-pixel retrieval prototypes were rejected and never deployed. A smooth vertical lip-displacement limit is now enabled at 0.035, preserving small motion and lateral smile movement. Controlled maximum aperture decreased 24.3%; upper-face pixels unchanged. 72 focused tests and Ruff pass. Actual WebRTC receives ~24 FPS without recorder drops, but two runs generated only 14.2–14.6 neural FPS and failed the 15 FPS gate. Naturalness acceptance is pending; do not call the overall avatar quality/FPS objective complete. Evidence and rollback: [opening-limit evaluation](evals/avatar-opening-limit.md).

## Browser 2D avatar option — 2026-10-31

- Added saved Settings 3D/2D choice with microphone-off switching; 3D remains default.
- Browser rig uses the exact supplied art, output-driven mouth, blinking and small head movement.
  2D skips Ditto transport/inference and preserves native voice/Fusion.
- RTX3060 hardware run: ~60.1 draw FPS, p95 intervals18.4–18.5ms; preview recorded separately.
  Seven GPU browser cases and42 frontend tests pass. Full Python verification has missing
  dependencies and one reproduced audio-gap failure; naturalness/acoustic sync remain unaccepted.
- No managed processes started. [Evidence, preview, commands and limits](evals/browser-2d-avatar.md).

## 2D body and mouth correction — 2026-10-31

- User feedback: V1 mouth too subtle and hands/head lacked reference motion. Updated2D to
  the new screenshot/clip character, silent source body loop and frame-aligned live mouth atlas.
- Body24 FPS, browser drawing ~60 FPS on RTX3060; stronger quiet-speech articulation.
  Source feet are outside the frame; this is a video-body/live-mouth hybrid.
- Fixed a bright mouth-skin halo and invalid-metadata fallback; actual pixel tests check
  arm/head motion and conceal the prerecorded mouth during silence.13 GPU browser cases
  and44 frontend tests pass; build/lint/format pass. No managed processes started.
- [Before/after, final preview, measurements and remaining limits](evals/browser-2d-motion.md).

## 2D lip-sync shape correction — 2026-10-31

- User rejected the mouth. Timing/saturation were measured and excluded; causes were a
  crossfaded three-frame loudness mouth and scale tied to the hidden source mouth.
- Now eight whole source mouth shapes selected by loudness and vowel tone, 90 ms hold,
  eye-based scale and a nose-anchored center, so a closed mouth stops following the
  hidden prerecorded speech. Not phoneme recognition. Human acceptance pending; no managed
  processes started. [Evidence](evals/browser-2d-motion.md).

## Layered 2D rig face trial — 2026-10-31

- User rejected the pasted mouth and approved a one-mesh rig. Design and plan:
  `docs/superpowers/specs/2026-10-31-layered-2d-rig-design.md`,
  `docs/superpowers/plans/2026-10-31-layered-2d-rig.md`.
- Standalone trial in `output/avatar-quality-review/rig-trial/`, built by
  `scripts/prepare_2d_rig.py`: one head mesh with mouth targets measured from clip frames.
- First review rejected the static body, joined hair and blended eyes. Added breathing, hair
  springs, open-hands frames 162–180 and the clip's whole blink drawings (124, 125, 127).
- RTX3060 Chromium, Maple fixture: 60.1 FPS, interval p95 16.7 ms, mouth closed 67 ms after
  interruption. Correction round 1 of 2 awaits review; kiosk code and services are unchanged.
- User rejected the hand-driven rig as robotic and required the sample clip's look. New standalone
  trial `output/avatar-quality-review/clip-trial/`, built by `scripts/prepare_2d_clip.py`: the clip
  plays unchanged except a soft lower-face region from closed-mouth frame 212, carried by each
  frame's head pose and warped from assistant output. Landmarks understate the drawn open mouth, so
  squeezing the source lips shut failed. Source motion is 24 FPS inside a 60 FPS canvas. Awaits review.

## Ready-made VRM staff character trial — 2026-10-31

- User rejected the clip hybrid and declined paid art. Trial in
  `output/avatar-quality-review/vrm-trial/`: CC0-labelled VRoid sample Vivi with three-vrm, outfit
  repainted by `scripts/prepare_vrm_outfit.py`, skeletal clasped/open hands and audio mouth shapes.
- Vivi's file metadata states CC0/commercial Allow, but it came from a GitHub mirror; the official
  VRoid conditions page was unreachable. 60.1 FPS on RTX3060. Awaits review; kiosk is unchanged.


## Kiosk sidebar navigation — 2026-10-31

- Added overlay drawer at every viewport, initially closed, with hamburger/close/Escape/backdrop and Menu, Cart, Payment/QR, Placed orders destinations. Progress moved into the sidebar; touch and existing agent view events share navigation state.
- Current-QR viewing stays read-only. Empty QR leaves checkout disabled; errors remain visible in the drawer; menu restores focus and new guest state clears previous results. Table selector stays above the overlay.
- 53 frontend tests, 39 focused Python/browser tests, production build, frontend lint and touched-file format/Ruff checks pass. Full frontend formatting still flags unrelated VirtualKeyboard.tsx.
- API reloaded only after idle/no-microphone check, with existing environment preserved. Visual/avatar stayed running; API health ok and no guest active. Reload browser tabs. No real orders/payments/printing during tests; live spoken intent selection remains unmeasured.
- [Evidence and screenshots](evals/kiosk-navigation.md).

- Sidebar layout follow-up: moved hamburger into the right header action group after Settings/Order status. Drawer/backdrop and checkout dock now share a safe-area-aware height variable so their bottom boundary meets on desktop and mobile. Frontend rebuilt.

## 2D character work stopped — 2026-10-31

- User rejected the clip hybrid, the Vivi VRM trial and a TalkingHead trial, and work stopped by
  agreement. None is accepted. The TalkingHead trial was deleted at the user's request. Remaining
  trials stay under `output/avatar-quality-review/` (`rig-trial`, `clip-trial`, `vrm-trial`).
- Kiosk 2D still holds the unaccepted eight-shape mouth from earlier today, and the output analyser
  remains 1024 samples for both modes. Default remains 3D. Services were not started.


## Empty-screen guest reset loop — 2026-10-31

- Reproduced repeated POST /api/sessions from an untouched screen every 120 seconds. This is a guest bootstrap/reset loop; no application location.reload call was found.
- Start the touch idle countdown only after user interaction. Reset clears the interaction marker, so an expired guest is replaced once and the untouched screen stays stable. Existing 90-second warning and 120-second expiry remain for an interacted guest.
- Browser regression failed before the fix (two sessions on untouched screen), then passed. Five focused navigation/idle tests pass; production build and frontend lint pass. Actual full-document reload reported by the user remains distinct from this reproduced reset behavior.

## Ditto talking head on the sample clip — 2026-11-01

- User asked for a talking head instead of lip-sync, with hands and body from the sample clip, and
  freed the GPU. Offline Ditto with the clip as source video and Maple audio produced
  `output/avatar-quality-review/ditto-head/first.mp4`: first run on this anime art, 81 frames.
- Face, including mouth, comes from one generated image; hands and body stay the clip's. Awaits
  review. Offline only: streaming speed, silence and interruption are not yet tested.
- Streaming trial with `stream_pipeline_online.py`, PyTorch and 5 steps at full 1080×1920: 180 of
  237 frames in 31.7 s, about 5.7 FPS, so not live-capable. Mouth still open inside the silent gap,
  though the missing frames leave alignment unproven. Next candidate is the existing live path
  with `renderer_backend: tensorrt` and a closed-mouth idle range; not yet tried on this clip.

## 2D cancelled, 3D only — 2026-11-01

- User cancelled the anime 2D character and chose to keep the running 3D avatar at 24 FPS.
- Removed the 2D setting, `Avatar2D`, renderer, assets, browser test and preparation scripts from the
  kiosk; they are preserved in `output/avatar-quality-review/cancelled-2d/`. The shared output
  analyser is back to 256 samples. Frontend 43 tests, lint and build pass; `format:check` was not rerun.
- The 3D profile and Ditto path were not changed. Services are stopped and the rebuilt UI is not
  yet served. Microphone error seen by the user is not diagnosed: the message is a catch-all.

## 3D lip shape versus sample clip — 2026-11-01

- User reported lips too large and long against `Tạo_video_chân_thực_cô_0e3fdbe0_1080p.mp4`. Live 3D
  on isolated port 8011: at small openings its lip width stays near 0.62–0.65 eye widths while the
  sample narrows to 0.47–0.56, and it opens to about 0.15 versus 0.24.
- Tried and reverted: a lateral widening limit and a speech smile relax of 12–25%. Width barely
  moved and the upper lip thickened. No 3D code or profile changed. Captures: `output/avatar-quality-review/lip-width/`.

## 3D source switch trial (sample clip) — 2026-11-01

- User accepted the face and color of `Tạo_video_chân_thực_cô_0e3fdbe0_1080p.mp4` as the 3D source.
  Isolated port 8011, `tensorrt-mouth`, clip as source: ready, no engine error. Mouth cache prepared and
  passed its accuracy checks. At small openings lip width is 0.55 (sample 0.56, old source 0.65).
- The live kiosk was not changed. `.runtime/ditto-trt-roi.json` was restored byte-for-byte from
  `.runtime/backup-source-switch-2026-11-01/`; the new manifest is kept in
  `output/avatar-quality-review/source-switch-sample/`. Switching the real kiosk also needs the 3D
  asset rebuild, a new poster and a decision about the wave clip, which still shows the old person.
  Awaiting user review of `new-source-3d.mp4`.
- User rejected the trial video: lips, chin and mouth look distorted. Landmark jaw and cheek widths
  match the sample, so the fault is local to the generated mouth. Absolute expression mode and no
  opening limit did not help. 20 sampling steps reduced pouting but lips stay softer and heavier
  than the sample. The live kiosk and `.runtime/ditto-trt-roi.json` remain on the old source.
- 20 steps on TensorRT dropped generation from 137 to 79 frames over the same speech. Offline whole-face
  Ditto (`full-face.mp4`, 50 steps) looks sharper with no mouth seam but opens wider than the sample;
  it is not real-time. Awaiting the user's choice; nothing deployed.
- User confirmed whole-face output has no distortion but opens too wide. Closed source lips alone did
  nothing; vertical lip compression 0.6 helped; both with 0.5 gave aperture p95 0.237 and max 0.284
  against 0.279/0.348 before and sample 0.196/0.24. Offline `full-face-both0.5.mp4` awaits review.

## 3D source switched to the sample clip — 2026-11-01

- User approved the whole-face result and asked to apply it. `.runtime/trend-avatar.json` now uses
  `Tạo_video_chân_thực_cô_0e3fdbe0_1080p.mp4`, `renderer_backend: tensorrt`, `composite: lower-face`.
  Previous profile: `.runtime/trend-avatar.before-source-switch.json`; earlier poster and manifests:
  `.runtime/backup-source-switch-2026-11-01/`. Poster replaced and frontend rebuilt.
- `--composite full-face` replaced an earlier lower-face composite that the user rejected as still
  distorted. Each generated face is pasted by Ditto's own putback on the exact source frame it was
  made from, with no interpolation. A closed mouth per source frame is rendered at startup, about 12 s.
- Isolated and launcher runs: 23.9 presented FPS, about 13 generated FPS during speech, render about
  52 ms, 4.1 GB GPU, ready in 47 s, no engine error. RTP epoch check passed. The waving clip stays the
  previous person by user decision. Live Fusion, acoustic sync and Vietnamese accuracy are unmeasured.
- Pursed lips: two causes confirmed by measurement and rendered comparison. Each frame's own lips
  were the anchor, and 12 of 50 "closed" clip frames are pursed, so silent lips moved (width 0.47-0.61,
  now 0.54-0.61); full-face now uses one shared closed shape. Each motion window also restarted from
  clip frame 0; it now continues from the previous window as upstream does, cast to the source dtype so
  compiled sampling does not recompile. Motion 22 ms, render 52 ms, 85 faces over the fixture.
- Not accepted yet: some frames of the first phrase after start-up still purse; the cause is not
  established. Speech shows about 13 new source-paired frames per second.
- Resting mouth: lips moved in silence because each rest face inherited its source frame's mouth
  (width correlation 0.67). Taking the whole face from a calm frame fixed that but put that frame's
  hair and collar on the current frame, which the user caught. Rest now uses the current frame's own
  face with only a feathered mouth area from the nearest calm closed frame (`blend_rest_mouth`).
  Correlation 0.01; collar and hair visually clean across eight checked frames.
- The source clip is someone speaking, so her body kept gesturing through silence. In full-face mode
  the clip clock now runs at 0.3 speed in silence, integrated so it never jumps, and resting resumes
  from the frame on screen. This departs from the clip's own timing; set `SILENT_CLIP_RATE` to 1 to
  undo it. Slow playback steps at about 7 source frames per second. Acceptance pending.
- Stable baseline, chosen after the user asked to stop chasing bugs: `.runtime/trend-avatar.json` now uses
  `.runtime/trend-closed-source.mp4`, a closed-mouth rebuild of the clip, with `tensorrt-mouth`, `composite:
  mouth` and `closed_source: true`. Body stays at the 24 FPS clock during speech; silence shows the
  closed clip at 0.5 speed. The launcher run used speed 0.3; 0.5 passed tests but was not rerun live.
- Launcher: ready in 36 s, no engine error, 141 faces, render 47 ms, motion 22 ms. Opening p95 0.131.
  RTP epoch check passed. Previous profile: `.runtime/trend-avatar.before-closed-source.json`; earlier
  mouth manifest in `.runtime/backup-source-switch-2026-11-01/`. Full kiosk, acoustic sync and Vietnamese
  accuracy are unmeasured. User acceptance is pending; other defects are deferred by the user.

## 3D returned to the original source — 2026-11-02

- User rejected every switched source as distorted and skewed, including the closed-mouth baseline.
  Restored the original profile, poster and cache manifests from `.runtime/backup-source-switch-2026-11-01/`:
  `Female_staff_member_standing_3128c196.mp4`, `tensorrt-mouth`, opening limit 0.035.
- Launcher: ready in 36 s, no engine error, RTP epoch check passed. The large-lip complaint is open again.
  Engine options `full-face` and `closed_source` remain in code but are off in this profile. Trials are kept
  as `.runtime/trend-avatar.closed-source-trial.json`, `.runtime/ditto-trt-roi.closed-source-trial.json`
  and `output/avatar-quality-review/source-switch-sample/`.
- Correction the same day: the user requires the `Tạo_video…` clip and a real Ditto talking head, not the
  standing clip. Profile now: `.runtime/trend-closed-source.mp4` (closed-mouth rebuild of that clip),
  `tensorrt`, `composite: full-face`, `closed_source`, opening limit 0.06. The clip advances at a steady
  0.55 speed in speech and silence so generated faces do not skip frames. Launcher: ready in 47 s, no
  engine error, opening p95 0.187 (sample 0.196), RTP epoch check passed. User acceptance is pending.
- Jerk diagnosis: only 38 of 85 generated faces had a new pose. Poses arrive every 160 ms and carry 80 ms
  of audio context, but were requested only 160 ms behind received audio, so the mouth held and jumped.
  `presentation_lead_ms: 360` in the profile keeps requests inside available poses, at the cost of a
  larger mouth delay behind audio. 80 ms stride reached 100% but dropped output to 64 faces.
- Launcher with lead 360: 81 of 83 faces have a new pose, no engine error, RTP epoch check passed. Earlier
  previews kept every second received frame, so they looked jerkier than the 24 FPS stream; use
  `talking-head-24fps.mp4`. Mouth delay behind audio grew by 200 ms and is unmeasured on real speakers.
  The 24 FPS recording run measured 59 of 85 new poses, against 81 of 83 in the half-frame run. Saving every
  frame may have delayed the test client's audio, but the cause is unverified.



## Catalog-only scrolling — 2026-11-02

- Customer request: scrolling changes the catalog while banner, topbar, assistant and checkout dock keep their positions. The kiosk shell now fits the viewport; menu and category rail have bounded independent scroll regions. Portrait layouts retain the assistant above the menu; short landscape layouts place it beside the menu. Fullscreen idle presentation stays unchanged.
- Scroll-to-top now targets the catalog region and respects reduced motion. Removed the old whole-page checkout scroll.
- Reproduced the missing independent scroll region before the fix. Three new browser regressions pass (1440×900, 375×812, 667×375), including stable shell positions and catalog scroll-to-top. Five navigation/idle-reset tests and five assistant lifecycle tests pass. The lifecycle tests were updated from obsolete always-visible-cart and old add-button expectations.
- Frontend 43 tests, lint, production build and changed-file formatting checks pass. Screenshots: output/kiosk-navigation/fixed-scroll-*.png. No managed services restarted.

## Talking head verdict on `talking-head-24fps.mp4` — 2026-11-02

- User verdict: still jerky; pursed lips; head and body do not match; distorted (méo). Not accepted. The six
  user screenshots were located in the clip (match 0.96-0.997): frames 246, 80, 38, 30, 28, 28. Pursed frame
  246 is at 10.29 s, the end of the clip. No code, profile or service changed; no GPU used.
- Jerk: about 14 new pictures/s in the 24 FPS stream (147 of 247 frame steps changed); the rest repeat. The
  body is tied to the face's source frame, so the whole person steps. GPU limit, as agreed: render alone is
  52 ms (about 19/s) against Ditto's 25. Stop tuning this.
- Head versus body is not a wrong-frame fault: head and body match the same source frame (mean difference
  0.37 frames) and neck geometry is unchanged. Sharpness is what differs. Laplacian variance, face/collar:
  original 0.82, accepted offline 0.57, closed source 0.63, live 0.45; neck/collar 0.74, 0.42, 0.52, 0.37.
  Measured on captured video, so compression contributes. The live face passes through Ditto twice: once in
  the closed rebuild, once live. Whether a single pass fixes the complaint is untested.
- `full-face-steps5.mp4` matches the accepted offline sharpness (face 180 vs 182), so 5 sampling steps are not
  the cause. Accepted offline clip used the 1080p original and one pass; live uses the 720p rebuild.
- Méo frames 28-30 show half-closed eyes that also exist in the original clip, plus a generated open mouth.
  Cause not established.
- One-pass trial, port 8011, profile unchanged. Only the source differs: `Tạo_video…` versus the closed rebuild.
  Same tool, lossless capture, frames held in memory. Both: 24.0 FPS, no engine error, 83 faces, 81 new poses,
  render 52 ms. Face/collar 0.47 closed, 0.62 original; neck/collar 0.50, 0.62; face detail +36%. The bare mouth
  stays closed in the checked silence frames. Pursed shapes remain in both, and the clip's blinks stay visible.
- Three in-memory runs all gave 81/83 new poses, so the earlier 59/85 fits capture I/O. Corrects "about 14 new
  pictures/s" above: that used a threshold on compressed video; source-frame steps and health give about 13/s.
- Awaiting review: `original-one-pass.mp4`, `closed-vs-original.mp4` (left closed, right original). Audio muxed
  afterwards, so do not judge sync. Services stopped.
- User review of `closed-vs-original.mp4`: less méo; head and body still mismatch; new complaint, lips tilted
  unlike the sample. Screenshot pixels match the left (closed) side better (0.97-0.99 vs 0.91-0.97), so these
  complaints may not apply to the right side. Left and right are not on the same source frame at a given time.
- Against the same sample frame, chosen by matching the body: chin lateral shift about 0.005 eye widths in both,
  so no geometric head-body offset was found. Lip width ratio in speech 0.856 closed, 1.029 original. Lip tilt
  +0.83° closed, +0.34° original. Chin-to-neck lightness difference 5.7 closed, 13.9 original, 12.0 sample.
  The head-body complaint is not explained by these measures. Live profile unchanged, still closed source.
- Caveat: the two runs covered different clip ranges (closed 158-238, original 10-140) because the clip clock
  runs from server start. All closed-versus-original figures above, sharpness included, therefore also compare
  different clip segments; a same-range rerun is needed for a clean result. Speech frames with lip width under
  0.85 of the sample: 85/158 closed, 12/158 original; lip tilt over 1.5° off: 51 and 19.
- User rejected the result strongly: neck looks broken, heavy méo, asked whether Ditto is really used. Live is
  Ditto, but not the accepted offline form: exp only, `relative_d=False`, own `calibrate_expression`, shared
  closed anchor and opening limit on top. Suspect, unproven: the shared closed anchor removes the clip's smile.


## Checkout dock cart preview — 2026-11-02

- Reworked the full-width dock using the requested KFC reference: cart icon at left, horizontal cart item preview and subtotal above, rounded cancel and red checkout actions below. The existing cart and checkout flows remain connected.
- Built frontend; 43 frontend tests and lint passed. Eight navigation/menu-scroll tests passed; product name, quantity and subtotal were then checked in the browser at all three navigation widths. Mobile preview: output/kiosk-navigation/dock-cart-375.png. Checks use fixture orders; no live merchant order or payment.

## Plain Ditto trial — 2026-11-02

- Added `plain_ditto` / `--plain-ditto`, default off, trial only: upstream relative drive, source keypoint smoothing
  (13 frames), no `calibrate_expression`, no shared closed anchor, no opening limit. Still 5 steps, clip rate 0.55
  and no driving smoothing. `.runtime/trend-avatar.json` unchanged. Pre-change copies:
  `.runtime/ditto_realtime.before-plain-ditto.py`, `.runtime/ditto_server.before-plain-ditto.py`. 64 focused tests
  pass, Ruff clean; full suite not rerun.
- Port 8011, original clip, aligned start (clip 10-139, same range as the earlier original run). 24 FPS, no engine
  error, 82 faces, 81 new poses. Opening p95 0.346 against sample 0.192 and layered 0.187, so about twice too wide.
  Lip tilt worsened: +1.12°, 73/158 frames over 1.5° (layered +0.34°, 19). Narrow-lip frames 8/158 (layered 12).
  Tilt therefore comes with Ditto's own motion and grows with opening, not from the kiosk layers. Sharpness about
  equal. Visually fewer pursed shapes and a clearer mouth; the two offline complaints about wide opening apply.
- Review: `plain-ditto.mp4`, `sample-original-plain.png` (sample, layered, plain). Candidate next: plain plus only
  the 0.5 lip compression of the accepted offline clip. Not tried. Services stopped.
- User: opening too wide, and a talking head must not be mouth only. Added trial flags, default off, `--lip-factor`
  (accepted offline recipe: `closed_lip_shape` on all source frames, `compress_lips`) and `--drive-head` (audio pose
  added to the clip's). Pre-change copies `.runtime/*.before-drive-head.py`. 76 focused tests pass, Ruff clean.
- Trial A lip 0.5: opening p95 0.255 (sample 0.192, accepted offline 0.237), width ratio 0.994, lip tilt +1.24°, 65/158
  over 1.5°. Trial B adds head: p95 0.274, tilt +0.77°, 39/158, head movement sd about 1.6-2.5 times A. Both 24 FPS, no
  engine error, about 82 faces. Rest mouth stays closed in the checked frames. Neck not assessed. Clips
  `trial-A-mouth.mp4`, `trial-B-head.mp4`, still `sample-A-B.png`. Port 8011 fixture only; profile unchanged.
- User objected to patching without a definition of done. Acceptance criteria proposed; no further tuning until agreed.
- User asked that Ditto keep running through silence. Added `--ditto-silence`, default off: pads the audio clock, keeps
  generating until guest reset, fades lips with upstream `vad_alpha` timed to the displayed pose. 86 focused tests pass.
  Trial D, no packets in silence: 24 FPS, no engine error, 148 faces in 10 s (about 15/s), GPU work fraction near 0.98.
  Voice level reached 0 in silence, but the mouth still moved: open 0.113 against 0.006 for prepared rest faces.
- Root cause, measured: in silence the face reproduces the clip's own mouth pixels (open mean 0.113 vs clip 0.113,
  correlation 0.99). Ditto warps source pixels and the clip's person is speaking; replacing lip keypoints in `x_s` does
  not change pixels. Speech mouth also correlates 0.88 with the clip's own mouth in this trial, so one-pass results
  largely show the clip's speech rather than the audio. Earlier "closer to the sample" readings of original-source
  trials are explained by this and do not show sync. The closed rebuild exists for this reason; its cost is softness.
- Proposed, not tried: rebuild the closed source at higher quality, keeping original pixels outside a feathered mouth
  area, then run Ditto whole-face live on it. Clips `trial-D-silence-fade.mp4`, `silence-vs-clip.png`. Profile unchanged.

## Mouth-only closed source trial — 2026-11-02

- `.runtime/trend-closed-source-v2.mp4`, 1080p: original clip pixels with only a feathered lip-and-chin area from the closed
  rebuild, colour-matched to the surrounding ring. Mask about 0.65% of the frame. Mouth closed on all 239 frames
  (open mean 0.004, original 0.093). Eyes/collar sharpness 0.81, equal to the original (old rebuild 0.54); neck/collar
  0.61 (original 0.78, old rebuild 0.39). No seam seen in four checked frames. Builder is scratch only, not in the repo.
- Live on it, port 8011, `--plain-ditto --drive-head --ditto-silence`, no packets in silence. Lip factor 0.5: opening
  p95 0.121, too small. Lip factor 0.8: p95 0.165, max 0.210 (sample 0.192, 0.238). Both about 15 faces/s, 24 FPS, no engine
  error. Silence open 0.003. Correlation with the clip's mouth 0.20 at 0.8 (0.88 before); with voice energy 0.52 at about
  625 ms lag (0.15 before). The lag is a coarse estimate, and points to a mouth well behind audio; not measured on
  speakers. Output eyes/collar 0.49, neck/collar 0.35, so the live pass still softens head and neck.
- Review: `trial-V2-0.8.mp4`, `trial-V2-0.8.png`. `.runtime/trend-avatar.json` unchanged; services stopped.

## V2 rejected: distortion, neck seam and pursed lips — 2026-11-02

- User rejects V2 throughout the clip: méo, gãy cổ, môi chu, poor quality despite near-full GPU use.
  V2 is not accepted and was never promoted. No further GPU render or runtime code change in this review.
- Located all eight supplied crops in the existing output (NCC 0.966–0.986; localization scores, not
  quality/confidence percentages). Frames 242, 37, 129, 10, 129, 37, 22, 37; clothing-matched source frames
  141, 27, 78, 13, 78, 27, 19, 27. Three-stage images show lower-face changes already in V2 source,
  followed by additional softness and a neck blend discontinuity in the live pass. The closure mask included
  the chin, so claiming untouched original pixels outside the mouth was too broad.
- Code audit: head drive is added to the video's moving pose while putback keeps the original frame's affine
  transform/mask and body. This is a structural mismatch needing isolation; this review does not prove that
  head drive alone causes all distortion. CPU evidence cannot separate pose, neural renderer and compositing.
- Withdraw prior claims of synced/first-correct speech based on audio-energy correlation. Aperture thresholds
  do not establish face quality. GPU throughput does not explain away neck seams or distortion. No accepted
  real-time visual baseline exists. Do not continue V2 by merely changing opening factors.
- Evidence and reproduction: [V2 rejection report](evals/ditto-v2-rejection.md),
  `output/avatar-quality-review/v2-rejection/`. Managed services and port 8011 remain stopped; profile still uses
  `.runtime/trend-closed-source.mp4`. The original chosen identity and accepted offline reference are preserved.

## Original-identity whole-face repair — 2026-11-02

- User requested an actual fix. Replaced the V2 rebuild with one real closed frame (frame 0) of the approved
  original clip as the fixed identity. `avatar_whole_face.py` retargets full expressions to the current head
  pose, aligns the facial contour and blends the whole face inside the original outline. Neck, hair and
  collar remain original pixels before stream encoding. This is full-face synthesis, including eyes and cheeks.
- Added `reference_frame` / `--reference-frame`; the mode keeps source head/body pose rather than adding
  independent head rotation, continues generating during silence and starts each motion window from the
  same identity condition. Same-input diagnostics showed predicted-condition feedback changed the smile
  across repeated utterances. The old chaining path remains unchanged for other profiles.
- Corrected a performance regression in the initial implementation: alignment now runs on the presenter,
  once per new face, in parallel with GPU rendering. Sparse remapping/ROI blending replace repeated full-frame
  warps. The final fixture captures 238 frames at about 24 encoded FPS, ~146 generated faces in 9.9 s, no engine
  error. This still means about 15 actual neural faces/s, not 24. Physical speaker sync remains unverified.
- Selected profile now uses the original clip, `reference_frame: 0`, `lip_factor: 0.5`, `closed_source: false`;
  original-frame posters updated in public and served static directories. Prior profile/posters/existing code
  backed up in `.runtime/backup-face-neck-fix/`. Services and trial server stopped after recording.
- Focused regression suite passes; full mixed-environment run: 567 passed, 29 failed, 4 skipped. Two MCP failures
  pass under the backend interpreter. Remaining UI/paused-avatar-audio browser failures are recorded, not
  claimed fixed or proven pre-existing. See [repair report](evals/ditto-face-neck-fix.md) and evidence in
  `output/avatar-quality-review/face-neck-fix/`. Human visual acceptance is still pending; no claim that all
  distorted/pursed shapes have been eliminated.
- Final focused count: 126 passing tests. Selected preset verified through the real launcher; both posters
  match original frame 0. Final live: 238 frames at 24 FPS encoded, 146 generated faces (~14.8/s), no engine
  error. Neck RGB difference against matched original drops 8.20→1.95 (includes encoding). Speech opening
  p95/max 0.139/0.161, quiet mean 0.006. Mouth tilt remains unresolved (absolute p95 4.38°, rejected V2 2.46°);
  pursed frames remain. This is a face/neck repair baseline, not a claim all visual defects are fixed.

## Fixed-frame appearance rejected; restore per-frame source identity — 2026-11-02

- User rejects the fixed-frame repair throughout the clip: changed face shape and viewing angle, asks whether
  output was reviewed. Contact sheets had been viewed, but the assessment was wrong; tests/neck metrics were
  allowed to substitute for appearance acceptance. That result is rejected, not a stable accepted base.
- Same-frame/same-drive controls showed filtering full-expression displacement alone did not correct the
  fixed appearance/pose transfer. Removed frame-zero appearance-feature reuse, the all-expression bypass,
  and custom face-outline/lip warping. The rejected implementation/tests/profile are preserved under
  `.runtime/backup-rejected-reference/`.
- Prepare only source lip pixels using a real closed mouth at source frame 0; leave eyes/nose/chin/neck
  untouched at source preparation. Extract both geometry and features from that same prepared crop.
  Render the current frame's own pair through Ditto's normal stitch, with protected non-lip anatomy.
  The decoder still produces the complete face. No source mouth pixels are overlaid in live output.
- Source video assets were concurrently moved into `output/`. Updated the selected source path to the
  relocated approved original (1080p, 239 frames, 24 FPS), and added the relocated wave lookup; no identity
  change. Profile's `reference_frame: 0` now denotes only the mouth donor during source registration.
- Actual server trial: 238 received/encoded frames, ~24 FPS, 148 generated faces (~15/s), no engine error.
  Viewed all 238 decoded frames in six numbered sheets, plus matched original/rejected/current comparisons.
  The conspicuously different fixed-frame viewing angle is absent in that inspection. Some pursed shapes
  remain (e.g. 52–55, 176–179); visual acceptance remains the user's. No acoustic sync claim.
- 129 focused tests pass, including source-pixel scope, encoder restoration and current-frame feature/geometry
  pairing. Ruff passes. Prior full-suite browser/audio failures remain unclaimed. Evidence and rollback:
  [per-frame source report](evals/ditto-own-frame-repair.md), `output/avatar-quality-review/own-frame-repair/`.
  Services and GPU trial server are stopped.

## No GPU inference in silence — 2026-11-02

- User: silence must stay off the GPU (prepared rest faces, no Ditto inference); Ditto-in-silence is not wanted.
  `reference_frame` had forced `ditto_silence` on, so the live profile generated through silence. It now sets only
  `plain_ditto`; `--ditto-silence` remains an explicit option. Tests first: 2 red, then 132 passing across the avatar set,
  Ruff clean. Pre-change copies: `.runtime/ditto_realtime.before-no-silence-gpu.py`, `.runtime/test_ditto_realtime.before-no-silence-gpu.py`.
- Isolated run on 8011 with the profile's flags: 250 frames, 24.0 FPS, no engine error. Generated-face counter stayed at 41
  through the 2.5 s no-packet gap and after the last utterance; whole run 81 generated faces (148 before). Mouth mode
  `source`, rest opening mean 0.006, speech p95 0.139. The 5 s window metrics (`rendered_fps`, `gpu_work_wall_fraction`)
  decay slowly and are not evidence of idle GPU. Startup still renders the rest faces once. Services stopped.
- Visual state is not accepted. User reports every reviewed frame wrong, mismatch between body and head, and asks whether
  Ditto can handle the body. Source: `_paste_face` calls Ditto's `putback`, which warps one 512px face onto the original
  frame; the driven keys are only exp, pitch, yaw, roll, t, scale. Body and hands therefore always come from the clip.
  Three reported frames were located (rest-no-gpu 134 and 178, own-frame 106); against matched source frames the
  difference is confined to lips and jaw edge, none in the body (`rest-no-gpu/user-frames/compare.png`).
- The `/trend/close` 404 after a capture is the known pre-existing exit error. Tools kept in
  `output/avatar-quality-review/rest-no-gpu/` (`run.sh`, `capture.py`, `review_transition.py`, `compare_user_frames.py`).

## Standing rest clip and audio-driven head — 2026-11-02

- User confirmed: silence plays `output/Female_staff_member_standing_3128c196.mp4` (no GPU); speech is whole-face Ditto on
  the `Tạo_video…` clip. The standing clip is therefore allowed as the rest clip only, never as a Ditto source.
  Profile gained `rest_source`, `drive_head: true`, `head_gain: 0.4` (before: `.runtime/backup-rest-clip-head-drive/`).
  New code: `trendcoffee/avatar_rest.py` (ping-pong clip clock, loader, `CrossFade`), `pose_degrees` and `head_drive` in
  `avatar_whole_face.py`, engine/server/launcher options `rest_source`, `drive_head` (now valid with `reference_frame`),
  `head_gain`. 165 focused tests pass (tests written first and seen red). Startup no longer renders rest faces.
  One old test set `_rest_frames` from a removed mechanism; those two lines were dropped, its assertion is unchanged.
- Isolated runs on 8011, 310 frames at 24.0 FPS, no engine error: generated-face counter stays flat in every rest period
  (+0), rest frames equal the standing clip (correlation 1.000), 82 faces over two utterances (148 before).
- Dissolve between the two clips (0.25 s) was rejected after viewing: it shows two heads and two mouths at once
  (frames 46-50, 111-113). Transitions are now a clean cut (`FADE_SECONDS = 0.0`); the dissolve class remains.
- What Ditto's audio model drives (measured on the greeting): head pitch/yaw/roll std 1.7/1.6/0.8 degrees (about ±5),
  small translation and scale; expression mostly lips, with eyes at about a third of the lip amplitude. Blinks,
  winks and smile therefore stay the clip's. Hands and body are the clip's and cannot be driven by Ditto.
- Head drive on the clip's own pose, same source frames, drive off versus on: at gain 1.0 a dark hair wedge at the left
  forehead and face seams appear in every compared frame; at gain 0.4 none in the compared frames or in both full speech
  sheets. At 0.4 the head differs from the clip-only head by only about 0.35 degrees roll and 2-3 px yaw (p95 about 6 px):
  real but faint. A vertical seam across the upper lip is present with drive off too.
- Not done: real guest, microphone, speakers, Fusion; the launcher itself was not started (its command for the profile was
  generated and read). Poster is still the `Tạo_video…` frame, while idle now shows the standing clip.
  Review: `output/avatar-quality-review/rest-no-gpu/review-rest-clip-head04.mp4` (audio muxed afterwards), sheets in
  `head-gain04/`, `forehead-aligned-gain04*.png`. Tools in the same folder. Services stopped.

## Seam and doubled lips: cause found, source changed — 2026-11-02

- User: all ~100 speaking frames show distortion, a double image and no real talking head. Screenshots enlarged: a vertical
  seam from nose to lips and a doubled upper-lip outline. My earlier review missed them (small sheets, and I had called the
  frames clean). The user's earlier guess, "caused by lip/chin", was right.
- Stage dump (source crop, crop after donor lips, Ditto face, composite): the seam is already in the crop after
  `prepare_closed_mouth` pastes frame zero's lips; the original crop has none; the decoder copies it. Same source frames,
  donor-lip preparation versus the pre-closed source: seam and doubled lip contour in the first, absent in the second.
- Change: `closed_source` now skips the donor-lip preparation (`_prepares_source_mouth`); the profile uses
  `.runtime/trend-closed-source-v2.mp4` (original pixels, closed mouth from a feathered lip-and-chin area of the Ditto
  closed rebuild) with `closed_source: true`. Builder kept as `output/avatar-quality-review/rest-no-gpu/build_closed_source_v2.py`;
  a rebuild matches the existing asset pixel for pixel. Previous profile: `.runtime/trend-avatar.before-closed-source-v2.json`.
- Viewed all speaking frames of the final configuration (two sheets) and eight same-frame A/B pairs: no seam, no wedge,
  single lip contour. Rounded "o" lips are frequent (frames 86-90, 215-231); the pursed-lip defect is not fixed.
- Head: 0.7 and 1.0 gain bring back a dark hair wedge at the left brow in the second utterance (source frames about
  130-154, where a bang strand crosses the face oval). Tested and refuted: keeping the clip's forehead and pasting only from
  the brows down did not remove it; that code was reverted. Gain 0.4 is clean, with head motion of only about 2-3 px, so
  this is not yet a visibly moving head. Larger motion needs a paste that follows hair; not built.
- 195 avatar-group tests pass (run under bash; zsh does not word-split a variable of paths). Isolated runs on 8011:
  310 frames, 24 FPS, no engine error, no generation in rest. Launcher not started. Services stopped.
  Review: `output/avatar-quality-review/rest-no-gpu/review-v2-candidate-NOT-selected.mp4` (V2 candidate, not the selected profile), `lower-v2-closed-*.png`, `pair-v2head04-*.png`.
- Correction, same day: I put the V2 source into the profile before reading `docs/evals/ditto-v2-rejection.md`, where the user had
  rejected V2 for a neck/tonal discontinuity and distortion. Checked at the same source frames: with V2 the chin is lighter
  and the neck darker than the original, and the neck band differs from the original by 3.3-3.9 grey levels against 2.1-2.9
  with donor lips (`neck-check.png`). V2 removes the lip seam but brings back the rejected neck defect. The profile is back to
  the donor-lip version (with rest clip and head gain 0.4); V2 is kept as `.runtime/trend-avatar.v2-candidate.json`, not selected.
  No accepted visual baseline exists. The `closed_source` skip in the engine stays (tested); the V2 profile is not in use.
- Fixes tried on the seam, on saved inputs of `prepare_closed_mouth` (CPU, 9 frames, `talking-head-drive/prep_variants.py`):
  Poisson clone with the union mask keeps the seam and reddens the lips; mixed clone keeps the open mouth; Poisson on a
  donor-lips-only mask removes the seam but makes the lips dark red (a new look defect), and a hybrid is still dark; a union of
  two hulls instead of one hull keeps the seam. A V3 source (V2 with a Poisson-joined patch) matched V2 and was deleted.
  Conclusion: the seam is the donor's skin around the lips pasted with one global tone shift (left half lighter than right).
  Not built: remove the old mouth by inpainting skin, then paste only the donor lips. The selected profile is still the
  donor-lip version (rest clip, head gain 0.4) and still shows the seam; the open default stays `closed_source: false`.
- Final state of the work tree: rest clip, head gain, `closed_source` skip, trial tools; 195 avatar-group tests pass; services stopped.

## Seam and doubled lips fixed in the selected profile: inpaint the old mouth, paste only the donor lips (2026-11-02)

- `prepare_closed_mouth` no longer pastes the donor's skin. It fills the old mouth and the new lip area from the frame's own
  surrounding skin (Telea inpaint, edge-feathered), then pastes only the donor lips (tight lip hull, a skin-tone shift measured
  on the repaired skin). Backup of the previous version: `.runtime/backup-rest-clip-head-drive/avatar_whole_face.before-inpaint.py`.
- Test first: `test_donor_skin_around_the_lips_is_not_pasted_only_the_lips_are` failed on the old code (pale donor halo 130
  pasted over skin 80), passes now; the "source unchanged outside the mouth" and lip-width tests still pass.
- Nine saved crops, old vs new (`talking-head-drive/prep-new-a.png`, `prep-new-b.png`): vertical nose-to-lip seam and pale halo
  gone, no new tone patch. Neck and chin stay original (no V2 asset).
- Two isolated GPU runs on 8011 with the selected profile (rest clip, head gain 0.4; `rest-no-gpu/inpaint-prep`, `inpaint-prep2`),
  each 310 frames at 24 FPS, 81 generated faces in two utterances (none in rest). Viewed every speaking frame of both runs in
  close-up sheets (`close-all-*.png`, 155 and 156 frames): single mouth, no seam, no halo, no doubled lip contour.
- Run 1 had one glitch: capture frames 237-238 (source frames about 152-155) show blocky red squares at the lips. The prepared
  crops of those source frames are clean and run 2 did not repeat it, so it is a one-off in generation, cause not found.
- Still open: rounded "o" lips (run 1 frames 88-90, 100-103, 224-226), head motion faint at gain 0.4, blinks/winks are the clip's,
  mouth/audio delay unmeasured on real speakers, no real guest test. No visual acceptance by the user yet.

## Pursed lips: `lip_width`, head gain re-checked (2026-11-02)

- Ditto's audio lip motion is almost all vertical on points 19/20 (std 0.018/0.009); sideways (x) and forward (z) motion on
  points 17/19/20 is what rounded the mouth into "o" shapes (`talking-head-drive/lip_axes.py`, `lip_delta_series.npy`).
- New `lip_width` (engine arg, `--lip-width`, profile key): share of sideways/forward lip motion kept; opening untouched.
  Test first (`test_lip_width_factor_tames_sideways_and_forward_lip_motion_not_opening`, kiosk flag test). 169 avatar-group tests pass.
- Same-frame comparison of 1.0 / 0.5 / 0.0 (`rest-no-gpu/lipw-compare.png`): 0.0 gives wider, flatter lips, still opens fully.
  Profile now has `lip_width: 0.0` (backup `.runtime/backup-rest-clip-head-drive/trend-avatar.before-lip-width.json`).
- Viewed every speaking frame of the selected configuration (`rest-no-gpu/lipw00/close-all-1..4.png`, 156 frames): single
  mouth, no seam, no halo, no doubled contour, no rounded "o". The block glitch of one earlier run did not occur.
- Head gain 0.6 tried with the new source preparation: a hair step shows at the left forehead (capture frames ~195, 205, 225);
  0.4 stays (`head04-vs-06.png`). Head motion remains faint; a hair-aware paste is not built.
- Review video with audio: `rest-no-gpu/review-final-lipw00.mp4` (H.264; the first export used MPEG-4 and would not play in a browser).
- Still open: faint head motion, blinks/winks are the clip's, mouth/audio delay unmeasured on real speakers, no real guest test,
  one unexplained single-frame block glitch in one run. No visual acceptance by the user yet.

## Sleepy eyes: blinks were stretched by the slow clip rate (2026-11-02)

- User saw eyes closed for a long time while speaking ("mắt ngủ"). Cause: the clip is played at `STEADY_CLIP_RATE` 0.55, so a
  blink of 6-7 source frames lasted about half a second. Source blinks (`talking-head-drive/source-eyes.png`): frames 12-26, 59-65,
  90-93, 110-113, 132-137, 178-182.
- `trendcoffee/avatar_blink.py` flags closed-eye frames from the registration landmarks (`blink_flags`); the engine plays flagged
  frames at `BLINK_CLIP_RATE` 2.2. Tests: `tests/test_avatar_blink.py`, engine blink-rate test. 172 avatar-group tests pass.
- Trial `rest-no-gpu/final-blink` (selected profile): the closed phase is about 3-4 frames instead of 8; the clip's own wink at
  the start of speech and the asymmetric closing of one eye stay (they are the source's, not generated).
- Head gain 1.0 (Ditto's full predicted displacement, `blink-head10`, `face-big.png`) shows a dark hair spike on the forehead in
  the second utterance; 0.6 already shows a step. Profile stays at 0.4. Hair-aware paste is still not built.
- Review video with audio: `rest-no-gpu/review-final-blink.mp4`. Not accepted by the user; mouth complaint ("miệng lỗi") received
  without a frame number, not yet located.

## Ditto source switched to the standing clip (2026-11-02)

- User: "bỏ cái nguồn này" after frame 86 (left eye drooping, torn lips) and asked whether the idea was understood; chose the
  standing clip as Ditto source. Root problem found on the way: rest played the standing clip (full body) while speech used the
  `Tạo_video…` bust crop, so every rest/speech change also changed the framing. Source and rest are now the same clip.
- Profile (`.runtime/trend-avatar.json`, backup `.runtime/backup-rest-clip-head-drive/trend-avatar.before-standing-source.json`):
  `source` and `rest_source` = standing clip, `reference_frame 0`, `lip_factor 0.5`, `lip_width 0.0`, `drive_head true`,
  `head_gain 1.0` (Ditto's own predicted head motion, as asked), `talking_frames 240`. Poster `frontend/public/avatars/trend-live.png`
  and its static copy are now standing-clip frame 0 (old poster: `.runtime/backup-rest-clip-head-drive/trend-live.before-standing.png`).
  `CLAUDE.md` binding line updated.
- Code: `composite_whole_face` keeps the clip's forehead above the brows (`BROWS`, test first) because a turned head made the
  decoder draw a dark hair wedge on the forehead (frames 190-204 of `stand-g10`, absent in the source). Also this session:
  `lip_width`, blink fast-pass (`avatar_blink.py`), inpaint lip preparation. 173 avatar-group tests pass, Ruff clean.
- Trials on 8011 (`rest-no-gpu/stand-g10`, `stand-brow`): 310 frames, 24 FPS, rest/speech cuts are continuous
  (`stand-brow/transitions.png`). Viewed all 156 speaking frames of `stand-brow` in close-up: no wedge, no seam, symmetric eyes,
  one lip contour, natural head tilt (the clip's own tilt at source frames ~84-107 plus Ditto's). Blinks last 2-3 frames.
- Review video with audio: `rest-no-gpu/review-standing-source.mp4`. Not accepted by the user yet. Launcher not started;
  no guest/microphone/speaker test; mouth/audio delay unmeasured; the face is smaller in a full-body frame than in the old bust crop.

## Whole head generated, not a face pasted into the clip's head (2026-11-02)

- User: "sao cứ cắt cắt dán dán ... làm cả cái đầu luôn, chứ đắp mặt này vào mặt khác làm gì". Cause: with head motion on
  (`head_gain` 1.0) only the face oval was pasted back, so the generated face turned while hair, ears and neck stayed the clip's.
- New `whole_head` (engine arg, `--whole-head`, profile key, now true): paste the whole generated 512 crop with upstream's own head
  mask (`PutBack`, 90% soft mask) instead of `composite_whole_face`. Test first (paste goes through `putback` only when set);
  174 avatar-group tests pass. The forehead keep from the previous entry is not used with this paste (hair now moves with the head).
- Trial `rest-no-gpu/whole-head` (standing source, gain 1.0, lip_width 0): viewed all 156 speaking frames in five sheets: head,
  hair and ears turn together, no wedge, no seam, one mouth, symmetric eyes. Contrast-stretched background
  (`whole-head/neck-bg.png`): no pasted rectangle or halo; neck/collar continuous at the large tilt (frames ~84-107).
- Video with audio: `rest-no-gpu/review-whole-head.mp4`. Not accepted by the user yet. Same open items: no guest/speaker test,
  mouth/audio delay unmeasured, launcher not started; the earlier neck-tone complaint was about the V2 source, not rechecked live.

## New near-still source clip (2026-11-02)

- The user generated a new clip from the prompt I wrote (`Female_staff_member_standing_smi…_f1513f72.mp4`, repo root; copy
  `output/avatar-quality-review/new-source/candidate.mp4`). Ditto-registration measurements, old standing clip vs new
  (`new-source/check_source.py`): face width 156 -> 200 px; yaw range 6.5 -> 2.9 deg, pitch 5.5 -> 5.5, roll 0.8 -> 0.6; frame-to-frame
  pose p95 0.63 -> 0.42 deg; mouth closed all clip (max aperture 0.009); blinks 6 -> 4 (user asked for 2); no hands or gestures.
  Not met: face 300 px (only 200), exactly two blinks, loop end matches start (pose differs by 1.5 deg yaw).
- Defects of the file itself: the first 8 frames are a zoom-out settle (black border, rounded corners, exposure drifting); a
  generator star mark sits on the right forearm for the whole clip (x 572-617, y 1133-1178). Built
  `output/Female_staff_member_clean_v2.mp4` (232 frames, 720x1280, 24 fps) by dropping the first 8 frames
  (`new-source/build_clean_source.py`). Star removal was tried five ways (inpaint, row and column blends, overlay inversion with
  fitted shape); every one left a visible patch that looked worse than the faint mark, so the mark is kept; it is on the arm, not the head.
- Profile (`.runtime/trend-avatar.json`, backup `.runtime/backup-rest-clip-head-drive/trend-avatar.before-clean-v2.json`):
  `source` and `rest_source` = clean_v2, whole_head, head_gain 1.0, lip_width 0.0; poster = clip frame 0 (old poster backed up).
  `CLAUDE.md` binding line points at the new file.
- Trial `rest-no-gpu/new-source`: 310 frames, 24 FPS; viewed face sheets of the 155 speaking frames (`face-all-*.png`): face large,
  eyes symmetric, one mouth, natural opening, hardly any pursing, no seam. The head barely moves because the source is nearly still,
  so visible talking-head motion now comes only from Ditto's predicted pose. Not accepted by the user.
- Video with audio: `rest-no-gpu/review-new-source.mp4`. Still open: no guest/speaker test, mouth/audio delay unmeasured,
  launcher not started.

## "Looks in another direction" check (2026-11-02)

- User sent a crop of the new-source output saying the gaze goes elsewhere. Measured with Ditto's iris landmarks
  (`new-source/gaze.py`, `yawproxy.py`; `gaze-view.png`): iris position inside the eye is centred in every frame of the source
  (right eye 0.494 +- 0.013, left eye 0.537 +- 0.019, 0.5 = centred) and the generated frames differ from their source frame by
  0.003 mean (p95 0.024). Worst frame 0.074 of eye width, about 1 degree. Head yaw proxy (nose vs eye midline) is within +-0.03 of
  the eye distance. So no generated gaze error was found; any offset is already in the source clip's eyes (left eye slightly outward).
- Added an optional `turn_gain` (engine, `--turn-gain`, profile key; test first, 175 avatar-group tests pass) that scales yaw/pitch
  separately from roll, in case head turning is ever shown to pull the gaze off the camera. Not enabled: `turn03` trial
  (`rest-no-gpu/turn03`) shows the yaw spread falls from 0.013 to 0.005 but no gaze problem existed to fix. Profile unchanged.
- The frame the user pictured was matched only loosely (capture frames ~214-217, correlation 0.86, flat across similar frames).

## Launcher run and speaker-path check (2026-11-02 14:53-15:16)

- Started api/visual/avatar with `TREND_MERCHANT_ENABLED=0 scripts/kiosk.py start`: all three ready (avatar ~45 s), clip_v2 profile
  active (`whole_head`, rest clip). About 19 minutes up with a user session: avatar 24 FPS, no engine error, 3 stale-frame drops,
  3 audio-clock re-anchors over 51 sessions; RAM steady (avatar 8.2 GB, visual 3.0 GB). At 15:12:47-49 all three stopped; no stop
  command came from this session (the tests I ran use their own ports); cause unknown. Not restarted.
- Live audio metrics before the stop: microphone max gap 210.8 ms, native input 347.8 ms, Fusion output 367.2 ms; native input
  transport underflow frames 0; Fusion silenced 105 of 878 packets as `visual_stale` (no fresh face in the last 1.0 s, by design).
  Visual log: 4 websocket `1011` handler errors since this start, and "Local camera stopped; retrying with browser fallback"
  (the same 1011 message appears 295 times in the older log, so it predates this work; client not identified).
- Speaker tests (browser, built UI): 36 passed, 1 failed, 1 skipped. Failing:
  `test_avatar_audio_browser.py::test_native_sized_packets_render_continuously_and_status_does_not_flicker[paused]` (3/3 runs):
  16 silent 20 ms frames where 25 +-2 are expected, output span 10.4 s versus 10.5. A 500 ms packet pause minus the player's 160-200 ms
  prefilled buffer is about 16 frames, so the test most likely predates the buffer change (voice-playback.js, 2026-10-30) rather than
  showing a new defect; not verified. No frontend or audio file was changed in this work.
- Not established: that playback has no audible glitch. Needs a real listening test on the physical speaker with a guest.

## Head turned left at second 7: `turn_gain` 0.0 (2026-11-02)

- User: at 7 s the head turns left, while 2-5 s looks straight; wants it straight throughout. Source clip pose is steady
  (yaw 2.0-2.5 deg over the whole clip, `new-source/pose.npy`), so the turn is Ditto's predicted yaw added at head_gain 1.0.
  Nose-vs-eye-midline proxy, mean 2-5 s / 7-10 s: gain 1.0: -0.022 / +0.001 (a +0.023 shift); `turn_gain` 0.3: -0.019 / -0.019;
  0.0: -0.018 / -0.029 (landmark noise about 0.01). Same-time crops: `rest-no-gpu/turn-compare.png` (top row turns at 7.9-9.2 s,
  the other two do not).
- Profile now `turn_gain: 0.0` (yaw and pitch stay the clip's; roll, position and scale still follow the voice at head_gain 1.0).
  Backup `.runtime/backup-rest-clip-head-drive/trend-avatar.before-turn-gain.json`. Test added for the zero case (176 avatar-group
  tests pass). Tested only on the Maple greeting; other utterances may pull the head differently but yaw/pitch are no longer applied.
- The previous entry's conclusion ("no gaze problem, turn_gain not needed") was too early: the user's frames showed the turn.

## "Customer audio not received": microphone level measured (2026-11-02)

- Symptom: UI shows no accepted audio. `/api/kiosk/status` during live use: 2261 of 2276 Fusion packets silenced as
  `speaker_unlocked`, 15 as `visual_stale`, `accepted_audio_receiving` false, gate never locked. Native underflow 0.
- The browser is not on the kiosk machine: client sockets arrive through the Tailscale SSH forward, no process on this host holds a
  capture stream, all PipeWire sources are SUSPENDED, and Visual switched camera `local -> remote`. So the microphone in use is the
  remote device's, not the USB mic of the kiosk.
- Added `microphone_level` to the status metrics (`InteractionHost.audio_level`, `SPEECH_RMS` 300, numbers only, no audio stored; test
  first; `tests/test_kiosk_runtime.py` 28 pass). API restarted alone with `TREND_MERCHANT_ENABLED=0`.
- Measured over 2.5 minutes and four sessions: peak RMS 1033 / 375 / 46 on a 32768 scale, last RMS mostly exactly 0, speech-level
  packets (RMS >= 300) 3 of 398, 0 of 41x, 2 of 492, 0 of 132. Fusion still produced ACCEPT verdicts (8, 4) and REJECT, yet never
  locked: `TargetLock` needs Light-ASD to confirm a face and a diarizer slot together. Monitor ASD probability stayed mostly below
  0.05 (best 0.95 once) while the camera saw mouth activity up to 1.0.
- Conclusion: the input level is far too low. Cause on the remote device not determined (wrong input, input gain, or a gate: exact
  zeros suggest a gate or AEC). Link from quiet audio to weak ASD/no lock is a hypothesis. Browser AGC is off by the 2026-10-29
  decision (measured on the kiosk USB mic); not changed. Services left running.


## Balanced assistant and shared catalog scroll — 2026-11-02

- Moved conversation out of the avatar scene into its own bounded area, so long replies cannot cover the face. Portrait/mobile layout puts transcript beside the image and reserves more assistant height; short landscapes use compact controls. Audio/native/Fusion behavior was not edited.
- Category rail and menu now share the workspace scroll container; removed the category scrollbar and moved scroll-top/reset handling to that container. Header/banner/assistant/dock stay fixed. Product cards are capped at 240px, with denser responsive columns.
- Browser coverage includes long transcript/image non-overlap, category/menu moving together, scroll-to-top, idle transitions and sidebar ordering. Thirteen focused tests passed; after the final mobile height adjustment, eight scroll/assistant tests passed again. Frontend 43 tests, lint, build and touched formatting passed. No managed service restart. Fixture screenshot: output/kiosk-navigation/avatar-clear-1440x1000.png.

- Avatar fit correction: browser measurement found the poster's intrinsic grid height was 444px inside a 284px stage, clipping the source despite object-fit contain. Poster/video now use a bounded absolute element with zero intrinsic minimums and contain sizing; removed edge masking. Regression failed before the correction and passed after it. Eight scroll/assistant browser tests pass, including full poster bounds and long-reply non-overlap. Build passed; no runtime model/profile change.

- Unified white avatar background: the outside was white but the source poster/video retained a pale-green background. Added a source-color matte filter in the browser for both poster and video, composited on white. Poster pixel probe: 18,061 near-background pixels whitened (100%); mean RGB change for pixels with a channel below 140 was 0. Canvas-stream video fixture confirmed white background and visible character. Eight focused layout/lifecycle browser tests, lint, build and formatting passed. A physical live voice/video run was not performed. Evidence: output/kiosk-navigation/avatar-filtered.png and avatar-video-white.png.

## Waving clip removed from the kiosk (2026-11-02)

- User: remove the hands-together/waving segment and keep the new model only. It is `Café_assistant_waving_hand_a1410f2d_1080p.mp4`,
  the only clip the engine loaded besides the source; the browser fires it at every session start (`useKioskVoice.ts`, on `session`).
- New `wave` engine arg (`--no-wave`, profile `"wave": false`, now set): the clip is not loaded, `action("wave")` is refused, `actions`
  no longer lists it, so the browser and Settings do not offer it. This replaces the earlier binding "keep the accepted wave".
  Test first; 177 avatar-group tests pass. Video file left on disk. Backup: `.runtime/backup-rest-clip-head-drive/trend-avatar.before-no-wave.json`.
- Avatar service restarted alone; screenshots were not matched to exact clip frames (correlation 0.78 at best, crops differ).

- Dine-in selector correction: local_queue_only previously rendered an autofocus table text input, triggering the virtual keyboard. Dine in now always uses the same Radix table selector. Local mode shows an honest disconnected-table-list message; it neither invents tables nor enables merchant checkout. Connected mode retains live table selection. Eight navigation tests (both connection states, three widths, tool/idle checks), 43 frontend tests, lint and build passed.


## Merchant connection restored — 2026-11-02

- User reported local-only confirmation without QR and no live tables. Health confirmed local_queue_only; active API inherited TREND_MERCHANT_ENABLED=0 from audio debugging. Merchant GET tables succeeded: 100 tables, 93 available at 09:19 UTC; menu was a fresh 51-item snapshot from today.
- After a fresh idle/no-microphone check, restarted API only with existing process environment preserved and TREND_MERCHANT_ENABLED=1. Health now merchant_api/live_pos_connected, menu merchant_connected=true, /api/tables live=true. Visual/avatar left running.
- Browser opened Dine in and showed merchant table options. No live checkout, payment initiation or printing was tested. Existing local-only orders were not submitted or migrated; QR for a new real order still requires the normal verified merchant checkout. Screenshot: output/kiosk-navigation/live-merchant-tables.png.

- Fixed chat anchor: reserved a constant 80px transcript slot on desktop (bounded fixed grid slot on compact layouts), including when empty. Status heading and control row now keep constant heights; Stop playback shares the microphone row. Avatar area no longer changes height when a long reply arrives. Regression reproduced a 132px shrink before the fix and verifies stable image position/height afterward.

- Chat anchor strengthened after further user feedback: assistant uses explicit grid tracks, with avatar and transcript assigned independent cells and size containment on the avatar scene. Latest two messages scroll inside the fixed transcript cell. Browser regression now delivers four successive short/long customer/assistant turns and asserts identical avatar stage position/height after each update.


## OpenJarvis Pet as a selectable kiosk character — 2026-11-03

- User requested the white/blue OpenJarvis Pet alongside the current Avatar 3D. Settings → Nhân vật now selects Pet / Avatar 3D and persists `trendcoffee.character`; default remains Avatar 3D. Selection is disabled while the microphone is armed/connecting, with an explanation to turn it off first.
- Adapted the source procedural Three.js robot, with Apache-2.0 attribution under `frontend/public/licenses/`. Pet is lazy loaded, fits the existing avatar stage and preserves the fixed transcript/control slots. Expressions use existing assistant phases: waiting/off → idle, connecting → thinking, listening, actual PCM playback → speaking, unavailable → error. Thinking does not claim a new backend tool-processing signal.
- Pet creates `VoicePlayer` directly and never calls `/api/avatar`; native voice, microphone capture, camera/Fusion and guest generations remain shared. Avatar 3D keeps the existing transport. Renderer failure/context loss shows an SVG robot. Resize, reduced motion and resource cleanup are handled.
- Verification: 43 frontend tests; typecheck and lint; formatting for all touched frontend files; Ruff check/format for the new browser test; 19 browser tests (3 Pet + 16 existing assistant/menu/navigation regressions) passed. New coverage includes persistence, actual PCM speaking/interruption, zero talking-head requests in Pet, WebGL unavailable/context loss, and switching back to Avatar 3D. Independent review found one minor blink/reduced-motion issue, now fixed.
- Built with `npm run typecheck` and `npm exec -- vite build`, preserving existing hashed assets by bypassing the known destructive prebuild cleanup. Vite warns that the lazy Pet chunk is 554 kB (141 kB gzip). This does not load for the default Avatar 3D. No managed services were started/restarted; port 8080 refused the pre-build status request. No physical microphone/speaker session or user visual acceptance was performed. Screenshots and review notes: `output/pet/`.

## Short customer speech diagnosis and native response policy — 2026-11-03

- User clarified that “yes/chào/hello/open menu” under two seconds must receive a response. Two seconds is voiceprint enrollment, not a minimum turn length; after identity lock, real Fusion gate/preroll checks preserve 160–320 ms owner PCM without a ready voiceprint. Cold two/four-row words still cannot establish the unchanged six-row owner lock, and speech during startup before greeting is not sent to native.
- Reproduced native ASR accepting a 0.737-second synthesized “Xin chào bạn” with no reply. Prompt-only change failed; aligning the stale role-bearing startup item with the short-turn voice policy produced a reply. Both PCM/WebRTC now receive the same developer policy. Customer greetings get a brief answer, yes/no uses context or clarification, and short display requests explicitly require actual Codex delegation rather than an acknowledgement alone. No invented checkout/order authority.
- Synthetic native checks: greeting 0.737 s and Yes 0.321 s transcribed/replied; Open menu 0.716 s invoked kiosk_menu using a read-only fixture. First output audio was 1.88–2.19 s after speech ended; the menu tool came at 7.81 s. These are individual synthetic observations, not physical A/V acceptance or an immediate-action SLA.
- 55 focused tests and changed-file Ruff lint/format pass; independent review found no important issue. No Audio thresholds, models, capture settings or owner gate changed. After an idle/no-mic check, restarted API only (449722 → 471893), preserving environment/merchant_api. Visual/avatar unchanged; health ok/live_pos_connected. Evidence and remaining startup/initial-lock/camera limitations: docs/evals/customer-short-speech.md and output/audio-diagnosis/.


## Fast disabled; Luna medium retained — 2026-11-03

- User explicitly disabled Fast. Removed `serviceTier: priority` from kiosk `thread/start`; model remains `gpt-6-luna`, reasoning effort `medium`, model fallback disabled. User/project configuration was read for inheritance: neither sets service_tier or fast_mode. No global configuration was changed.
- New regression failed while priority was present, then passed. An actual isolated app-server thread/start resolved model=gpt-6-luna, reasoningEffort=medium, serviceTier=null; no audio session or business action was started. 55 focused tests plus changed-file Ruff checks pass.
- After an idle/no-microphone check, restarted API 471893 → 477443 with the existing environment preserved. Visual/avatar unchanged. Previous short-speech timing probes ran with the earlier Fast setting and are historical; no normal-tier latency measurement is claimed.

## Direct order/payment QR flow — 2026-11-03

- User rejected long sales dialogue and repeated confirmations. Explicit delegated choice plus known fulfillment now means choose an actual catalog item, add/update the real cart and checkout in one turn. Advice and view-only QR remain read-only; missing genuine details still require a brief question. Exact catalog products need not be searched again. Lookup alone never adds the newly requested Latte.
- Fixed `kiosk_payment` no-order contract: configured merchant no longer incorrectly reports disconnected just because no payment record exists, and the scoped pending cart is returned so the agent can place it instead of requesting the same drinks again. Reading payment still never submits an order.
- QR-ready final speech is exactly “Bạn quét QR trên màn hình để thanh toán nhé.” Merchant-verified paid gets the concise paid answer instead. Payment-status questions refresh merchant evidence rather than relying on cached progress. Native voice stays within coffee service and delegates original uncertain drink wording instead of unrelated property advice.
- Actual Luna medium/non-Fast evaluations with disposable merchant fixtures: delegated choice/order, existing-cart payment, Latte addition/dine-in auto-table, advice-only, view-only and verified-paid all passed. 93 focused backend tests and 2 desktop/mobile QR browser tests pass, plus changed-file Ruff checks. Browser tests needed existing-sidebar/dock selector updates; frontend product source unchanged. No real merchant order/payment/printing was performed.
- Current merchant read confirmed 100 tables/92 available at 07:31 UTC. After a fresh idle/no-mic check, API 477443 → 496852 restarted with environment preserved; merchant health ok. Visual/avatar unchanged. Evidence, historical local-queue explanation and limitations: docs/evals/qr-checkout-flow.md, output/checkout-flow/.

## Native output packet loss: arrival audio buffer — 2026-11-03

- User reported crackly, noisy and stuttering assistant speech in Pet mode; recorded greeting/farewell clips sounded clean (user not certain). User chose to replace the audio jitter buffer; WebSocket microphone transport is unchanged.
- Root cause in aiortc 1.15.0: the audio `JitterBuffer(capacity=16, prefetch=4)` holds every packet behind one lost RTP packet until 16 later packets arrive, then discards good packets. Real in-process aiortc loopback (Opus, 2% induced loss) logged a 321 ms decode stall at the first loss, ~100 ms stalls afterwards, and 1.18 s of 9.88 s audio removed. Earlier native fixture probes recorded 7/493 lost packets and a 333 ms gap. Live kiosk loss rate is still unmeasured.
- `native_peer.ArrivalAudioBuffer` replaces the receiver's audio buffer: each packet decodes on arrival in sequence order; late/duplicate packets are dropped; no reordering hold. `receive_audio` replaces a lost span of up to 120 ms with silence of equal length (5 ms ramp out, 5 ms fade-in of the next packet), so the browser playback buffer does not drain per loss; longer jumps are treated as pauses.
- Same loopback after the change: 9.98 s audio over 9.96 s, maximum delivery gap 41 ms, no gap >100 ms, 10 losses → 200 ms filled, no waveform jumps. Name-mangled aiortc attribute is covered by a test (upgrade guard).
- New status telemetry `audio_metrics.native_output_transport` (packets, lost, late, concealed_ms).
- Tests: 3 new red→green tests in `tests/test_native_peer.py`; 82 focused voice tests pass; Ruff check passes. Full suite: 25 browser-test failures and 13 avatar collection errors (`cv2` missing in root venv) are pre-existing — the voice-related browser failures reproduce identically with the change reverted. Pre-existing Ruff format drift in `test_live_tables_browser.py` and `test_reference_cart_browser.py` was not touched.
- After an idle/no-microphone check (`session_active=false`), restarted API only (512035 → 574720) with the launcher's environment preserved (merchant mode); `/health` reports merchant_api/live_pos_connected and `/api/tables` is live (100 tables). Visual (511975) and avatar (512014) were untouched. No live Pet session or telemetry sample has been taken yet; physical speaker listening is not verified.
- Live Pet session after the restart (user: still crackly/stuttering, "worse"): `native_output_transport` showed 7977 RTP packets, 60 lost (0.75%), 0 late, 1200 ms filled. Packet loss is therefore not the main cause of the reported sound. The new buffer releases each frame at its arrival, never later than the old buffer did; the "worse" report is not explained by measured data yet.
- Offline probe of the real `voice-playback.js` (Node): 160 ms start buffer absorbs 0–100 ms jitter with no underrun; after a >160 ms stall, the 40 ms post-underrun refill causes cascaded underruns under 0–60 ms jitter (250 ms stall every 2 s + jitter: 17 underruns, 11% of speech silent). A full 160 ms refill copy reduced interruptions (17 → 8) but not silent time (11.5%). Not deployed.
- Added numbers-only diagnostics (test-first, 84 focused tests pass): `native_output_transport.arrival_gaps_over_100ms`, `max_arrival_gap_ms` (frames from native while Trend speaks), `max_send_ms` (time to hand a frame to the kiosk socket), and `browser_playback` (starts, stops, restarts_within_500ms = browser buffer underruns, from existing playback messages). Requires an API restart to take effect.
- After a fresh idle/no-microphone check, restarted API only (574720 → 580912) so the new diagnostics run; environment unchanged (`/health` merchant_api/live_pos_connected), Visual 511975 and avatar 512014 untouched. Awaiting a live Pet session to read `native_output_transport` and `browser_playback`.

## Trend's speech over WebRTC to the browser (Pet) — 2026-11-03

- User asked why the speech path is complex and chose option B: send Trend's speech to the browser over WebRTC instead of PCM16 JSON/base64 on the kiosk WebSocket plus a hand-written AudioWorklet buffer. User said "làm luôn" (skip design questions). Microphone transport stays WebSocket (user decision).
- My calls: applies to the Pet character only; Avatar 3D keeps its existing path (talking-head sync depends on the browser PCM clock and GPU trials are out of scope). Fallback: while the speaker connection is not established or drops, the backend sends PCM on the socket as before, and `RtcSpeaker` plays it through its internal `VoicePlayer`.
- Backend `trendcoffee/speaker.py`: `SpeakerTrack` sends 48 kHz mono on a steady 20 ms clock with a 100 ms start buffer that grows 40 ms after each underrun inside a reply (max 300 ms), 5 ms fade in/out, interrupt/resume/clear; `SpeakerPeer` answers a browser recvonly offer. `InteractionHost` adds the connection-level `speaker_offer` command; routes native audio, greeting and goodbye clips to the speaker; interrupts on the guest's turn and resumes on Trend's turn; clears on guest change; reports playback to Fusion and to the screen (`speaking` event) with a 150 ms stop delay for the browser buffer and echo tail; closes the speaker on detach. Metrics: `audio_metrics.speaker_transport` (underruns, target_ms, max_buffer_ms, overflow).
- Frontend `frontend/src/speakerRtc.ts` (`RtcSpeaker`): recvonly RTCPeerConnection negotiated over the kiosk socket after auth, plays through an `<audio>` element (browser NetEQ, outside the page's JS thread), level meter tap for the wave; autoplay retried on pointer/key. `useKioskVoice.ts` uses it for Pet, handles `speaking` events, keeps socket PCM playback reporting for the fallback.
- Verification: 12 backend speaker tests (incl. real aiortc loopback), 5 frontend unit tests, new real-Chromium Pet test (WebRTC connected, received level > 10 px on the wave, no socket PCM, 0 underruns, speaking → listening, speaker closed when the mic turns off); 4/4 Pet browser tests pass. Full suite: 375 passed, 22 failed and 13 collection errors, all in the pre-existing set (no new failures). Frontend: 48 tests, typecheck, oxlint, Prettier. Built with `npm run typecheck` + `vite build` (served hashed assets kept).
- Not yet deployed: the running API (580912) has the old code; the kiosk page needs a reload after an API restart. No physical speaker listening or live latency measurement yet.
- Last session on the old socket-PCM path (read just before this restart, Pet): native delivery was healthy — 3026 packets, 15 lost (0.5%), 0 arrival gaps >100 ms (max 98 ms), max socket send 16 ms — but the browser worklet restarted 30 of 35 stops within 500 ms (`browser_playback`). The stutter was in browser playback, not network/native; this confirms the WebRTC change targets the right stage.
- After an idle/no-microphone check, restarted API only (580912 → 614024) with the WebRTC speaker code; `/health` merchant_api/live_pos_connected; Visual and avatar untouched. Browser page needs a reload.
- Live Pet session on WebRTC (user: still crackly/stuttering): `speaker_transport` 12–16 underruns with the start buffer pushed to 300 ms; native 0.35–0.65% loss, ≤3 arrival gaps >100 ms. Simulation showed my underrun rule treated natural ~250 ms pauses between phrases as underruns (stop, fade, rebuffer, grow the buffer).
- Fix (test-first): silence inside a reply is now sent as silence (pause keeps its length); after running dry the track fades out, then resumes with a fade-in once 60 ms is buffered or 60 ms has passed; the reply ends for Fusion/screen only after 400 ms of silence; no growing start buffer. Metric renamed to `speaker_transport.starvations`.
- Diagnostics: opt-in `TREND_SPEECH_CAPTURE_DIR` writes WAVs of Trend's own speech only (never guest audio): `native-*.wav` right after decoding native RTP, `speaker-*.wav` exactly as sent to the browser (300 s cap each). Browser posts NetEQ inbound-rtp numbers every 2 s (`speaker_stats` → `audio_metrics.browser_speaker`, numbers only).
- Verification: 17 speaker tests, 121 focused backend tests, 49 frontend tests, typecheck/oxlint, 4/4 Pet browser tests; Ruff clean. Rebuilt with `vite build` (assets kept).
- After an idle/no-microphone check, restarted API only (614024 → 621199) with `TREND_SPEECH_CAPTURE_DIR=.runtime/speech-capture` added; `/health` merchant_api/live_pos_connected; Visual/avatar untouched. Captures are diagnostic and should be deleted after analysis; restart without the variable to stop capturing.
- Live Pet session with captures: browser leg clean (`browser_speaker`: 1 packet lost, ~63 ms concealed in total, jitter 1 ms, NetEQ delay ≈44 ms). Capture analysis (frames RMS > 300, short gaps ≤300 ms inside speech): `native-*.wav` 14.4 s speech, 28 gaps, no clipping or steps >6000; `speaker-*.wav` 14.3 s speech, 49 gaps. The API's speaker stage added ~21 cuts (17 starvations): `receive_audio` dropped native's quiet frames outside its own turn heuristic, so the speaker buffer emptied in pauses.
- Fix (test-first): in speaker mode the native peer forwards every frame (`NativePeer.continuous`, set per audio event via `CodexVoice.set_output_continuous` while the speaker is connected); native's steady 20 ms delivery is the playout clock. `SpeakerTrack` reports playback from audible frames (>64) with a 400 ms hangover, so idle comfort noise does not duck the guest's microphone; start buffer 160 ms, rebuffer 100 ms. Replay of the captured native speech through the new track: 28 gaps (same as native) with in-order arrival jitter up to 150 ms and a 300 ms stall; previous logic produced 49 live. 123 focused tests pass; Ruff clean. No frontend change. Needs API restart.
- After an idle/no-microphone check, restarted API only (621199 → 627339) with the continuous native feed; capture still enabled (earlier WAVs moved to `.runtime/speech-capture/before-fix/`). `/health` merchant_api/live_pos_connected; Visual/avatar untouched.
- Live Pet session after the continuous-feed fix (user: still stops, still bad): native nearly perfect (1 lost, max arrival gap 101 ms), browser clean (0 lost), but `speaker_transport` 35 starvations and 16 exact-zero runs inside speech in `speaker-*.wav`. Totals disagree with a steady native clock: about 99 s of native frames over about 116 s of native lifetime, with about 27 s of exact zeros sent. So native does not send continuously (possibly Opus DTX in silence or variable delivery); my "steady native clock" assumption was wrong.
- Added per-frame timing logs next to the opt-in captures (test-first; 125 focused tests pass): `native-*.csv` = arrival time, pts, RMS; `speaker-*.csv` = time, buffered ms, speaking. Needs an API restart and one more Pet session to locate the cuts exactly. Not deployed yet.
- User asked why the API inserts, cuts or filters at all. Answer: the old-path filter only served socket PCM (idle noise would duck the microphone); the inserted zeros came from my own 20 ms send clock in `SpeakerTrack`, a design error (two clocks). User approved "chuyển thẳng" (pass-through).
- Pass-through `SpeakerTrack` (test-first): forwards native's decoded frames as they arrive and never invents silence; a late frame keeps its timeline position (browser NetEQ stretches it); after >300 ms with no frames the timeline jumps to the wall clock (as a WebRTC sender after a pause); queued clips leave at most 100 ms ahead of play time; a clip's short last frame is padded. Playback for Fusion/screen: audible frames (>64) with a 400 ms quiet timer. Metrics: `speaker_transport.frames/resyncs/max_queue_ms/overflow`; capture CSV = time, queued ms, pts. 18 speaker tests, 127 focused + Pet browser tests pass; Ruff clean. Not deployed yet.
- After an idle/no-microphone check, restarted API only (627339 → 636793) with the pass-through speaker; capture + timing CSV enabled; earlier captures moved to `.runtime/speech-capture/before-passthrough/`. Visual/avatar untouched.

## Warmer, slightly longer spoken replies — 2026-11-03

- User asked why Trend answers so briefly and wanted longer, natural replies with some emotion; chose to proceed ("làm ngay") after a proposed scope. This relaxes the 2026-11-03 "short replies" direction for conversation only.
- Cause: prompt limits in `trendcoffee/codex_voice.py` — `INSTRUCTIONS` (≤20 words, ≤2 sentences) and `VOICE_INSTRUCTIONS` (4–8-word acknowledgement, combined 30 words, one short result sentence).
- Change (test-first, `tests/test_voice_tone.py`, 6 tests): warm friendly-barista tone with light emotion and varied wording in both prompts; conversation/greeting/suggestions 2–3 short sentences (~40 words max); result after a tool 1–2 friendly sentences (~25 words); acknowledgement still 4–8 words but friendly; greeting example warmer. Unchanged and test-locked: exact QR sentence, exact paid sentence, no order confirmation questions, no claim of success before the tool result, at most two drink names, never read the whole menu.
- Not measured: the model's real wording and the added speech time (about 1.5–2 s per extra 10 words). Needs an API restart to take effect; `CLAUDE.md` still says "Keep speech concise" and should be updated to match if the user keeps this.
- User still hears crackle/distortion ("rè, nhiễu, méo") on the pass-through speaker. Evidence from the 17:04 session captures: native audio has no clipping or large steps; `speaker-*.wav` matches native's spectrum (the API does not alter content); live native speech has almost no energy above 6 kHz versus the stored greeting clips (source bandwidth, not our processing). Native delivery runs at ≈96.5% of real time with sender stalls that never catch up (no bursts after stalls, pts advance 20 ms across them), including while Trend is silent — a sender-side pacing property of codex app-server/native, not the API or network.
- Chromium replay (real aiortc → Chromium NetEQ, recorded arrival times): `jitterBufferTarget` 300/400 ms made no difference; a native-pts timeline prototype was mixed versus the current numbering (in speech: 0.00–0.14 s concealed and 0.29–0.92 s stretched versus 0.00–0.18 s and 0.15–0.27 s). Both leave only ≈0.2–1 s of concealed/stretched audio per ~20 s of speech, too little to explain the reported severe distortion. The native-pts change was reverted (never deployed).
- After five transport fixes without a resolved symptom, transport changes are paused. Next: listening A/B on the kiosk speaker of an excerpt of native's raw output versus a stored greeting clip, to separate source voice quality, speaker/OS volume and Chrome output.
- User asked to run the full stack (services were all stopped). Started visual 679024, avatar 679063, API 679083 via `scripts/kiosk.py start` (merchant mode default; speech capture off). `/health` merchant_api/live_pos_connected. Contains the pass-through speaker and the warmer voice prompts.
- Correction of the listening test: the user's browser runs on a remote Linux laptop (`fedora-2`) through SSH forwarding over Tailscale ("This device's camera" mode); Trend's voice plays on the laptop, while the `pw-play` A/B played on the kiosk PC's speaker (both clips reported fine there), so it does not test the user's listening path. Tailscale path to the laptop is direct (not DERP), ping median 8 ms, max 101 ms over 20 pings. A local Chromium replay reproduced most of the session's NetEQ concealment, so the network leg is not the main cause. Remaining suspects are on the laptop: audio output underruns under load (mic + camera JPEG upload + Pet WebGL in Chrome) or the laptop's own output path. Next: play the clips on the laptop outside Chrome, and watch the laptop's PipeWire xrun counter (`pw-top`) while Trend speaks.
- User A/B on the laptop: both clips clean via `pw-play`, and clean when played in another Chrome tab during an active kiosk session; only Trend's WebRTC voice is bad. So the fault is in the WebRTC speaker playout, not the laptop, its speaker or Chrome's output.
- Chromium replay with the decoded playout recorded and aligned sample-accurately to the source (30 s from the 17:04 session): codec opus/48000/2; steady windows SNR 12–15 dB; 9 of 35 speech windows (≈25%) at 1–5 dB, each coinciding with NetEQ delay changes (756→878→782 ms drift = time-stretching; +514 ms step at 16.5 s = my timeline resync concealed by NetEQ). Root cause: native delivers at ≈96.5% of real time with stalls; both the current numbering and native-pts pass the lateness to NetEQ, which, tuned for low-latency calls, stretches and conceals inside speech.
- Proposed (awaiting user approval because of latency): server playout buffer for each reply (~500 ms), sent to Chrome on a steady real-time clock with contiguous timestamps (NetEQ sees no jitter); the buffer is corrected only inside native's silence (drop or add quiet frames), never inside speech. Success measure: same replay, all speech windows near the steady SNR, constant NetEQ delay, ~0 concealment/stretch.
- User approved ~0.5 s added wait at the start of each reply for smooth sound. Implemented (test-first, 20 speaker tests) a steady-clock playout buffer in `SpeakerTrack`: contiguous 20 ms timestamps to Chrome; a reply starts after >500 ms is buffered (or 500 ms after its first word); idle native silence is trimmed to a 100 ms preroll; the buffer is corrected only inside pauses of ≥60 ms by dropping or adding quiet frames (±100 ms band); speech frames are never changed, skipped or split; a native stall inside speech gives silence and a 200 ms rebuffer (counted as an underrun only if speech returns). Metrics: `speaker_transport.underruns/dropped_quiet/added_quiet/max_queue_ms/overflow`.
- Chromium replay of the real 17:04 native timing, Chrome's decoded playout recorded: NetEQ concealment and stretching inside speech 0.00 s in all three windows (previously 0.29–0.69 s concealed, up to 10 events); NetEQ average delay 30 ms (was ≈245 ms). Alignment-based SNR, same 30 s window: windows <8 dB 9/35 → 0/35 (0.5 s windows), 17/81 → 5/81 (0.2 s windows; short windows misalign and are noisy). Focused suites incl. Pet browser tests pass (one earlier Pet failure was a page-load timeout; 2/2 reruns passed). Needs API restart; not yet heard by the user.
- User tested the steady-clock playout buffer and the warmer voice after restarting the stack (all three services restarted 20:28, newer than the code): reported okay, voice warmer. No numeric telemetry was read from that session; the 0.5 s wait at the start of each reply was accepted in advance.


## Wobnimo Volt replaces the previous Pet renderer — 2026-11-03

- User selected Wobnimo Volt after comparing ready-made robot designs and state/audio animation options. Pinned npm dependency `wobnimo@0.2.0`; only the Volt character is imported. Pet now uses Wobnimo's WebGL2 renderer and original LED expressions/acting; white/cyan palette uses the package's supported colour overrides.
- `PetAssistant.tsx` forwards idle/listening/thinking/speaking/error through the public `Mascot.setState` API. Speaking still comes from the kiosk's real playback state. Volt's individual mouth movements are synthetic state animation, not audio/phoneme lip sync. No voice transport, Fusion, merchant or Avatar 3D changes.
- Generated five matching static WebP fallbacks using the upstream snapshot API; unsupported WebGL/startup timeout shows the appropriate Volt state. Upstream MIT licence retained at `frontend/public/licenses/wobnimo-MIT.txt`. Previous Three.js renderer and Fluent SVG source archived under `output/pet/previous-pet-source/`.
- Verified 49 frontend tests, TypeScript, oxlint, touched-file Prettier/Ruff and 4 Chromium Pet tests. Browser checks include public Volt state labels, desktop/mobile persistence, real shared-context loss/restoration, loaded no-WebGL fallback, Avatar 3D switch-back and WebRTC speaker continuity. Browser test was first seen failing against the previous renderer. No physical-device audio/performance claim.
- Built with `vite build`, retaining old hashed assets for active pages. New Pet chunk: 80.56 kB / 28.16 kB gzip (previous 564.41 kB / 144.37 kB gzip). API/Visual/avatar services were not restarted. Preview: `output/pet/volt/states.png`, kiosk screenshots `output/pet-soft-green-{1440,375}.png`. Reload kiosk to select/use Volt via the existing Pet option.

## Volt interaction boundary — 2026-11-03

- User reported Volt looking toward the cursor even over distant menu items. Wobnimo 0.2.0 listens for `pointermove` on the window and accepts a radius of 3.3 times canvas width; no public radius option exists in this installed version.
- Added `components/pet/pointerBoundary.ts` after Mascot construction: tracking stays within the Pet canvas plus 24 CSS px on each edge. Far movement or window blur sends the existing document `pointerleave` signal so the original engine resumes autonomous animation. Page pointer events keep propagating; cleanup removes the adapter. Upstream package, character geometry, expressions and animation are unchanged.
- Existing interactions: native single click uses Wobnimo's happy `poke`; double click sets built-in `celebrating` for four seconds, then returns to the current assistant state. A new assistant state cancels celebration immediately.
- Verification: new Chromium boundary test failed against the prior build and passed after the change; unit checks cover all four edges, the margin, reentry, blur, cleanup and unaffected menu listeners. 50 frontend tests, TypeScript, oxlint, touched-file Prettier/Ruff and Vite build pass. Pet browser run: 4 passed, 1 desktop voice/menu-start failure; that failed test passed alone on rerun (19.21 s). Desktop/mobile celebration, voice states, WebRTC, fallback and context restore remain covered. Boundary browser test observes the engine's leave-event contract; it does not measure head rotation angles.
- Built assets are served after reloading the kiosk; old hashes retained. No service restart. Pet chunk 81.22 kB / 28.35 kB gzip.

## Short first answer released with 3 confirmed rows — 2026-11-03

- User: after the greeting, a very short first answer ("dạ", "có", "chào") got no reply and the guest had to repeat a longer sentence. Usually only the guest stands at the kiosk, sometimes a companion; Trend must listen only to the person in front of the kiosk.
- Cause: before the initial lock (6 ASD-confirmed rows, ~480 ms) `FusionPreroll` holds confirmed rows up to 2 s and drops them when no lock arrives.
- User decision (explicitly relaxing the earlier review that required the full lock): for the FIRST answer only, release it when it ends (320 ms without confirmed speech) if it has ≥3 rows (240 ms) with verdict ACCEPT from the guest's face (presence owner track; with no owner, a single face) and no other face had confirmed speech in that utterance. No lock is created; later turns still need the normal 6-row lock; the allowance resets for the next guest. Change is host-side in `trendcoffee/av_transport.py` (`SHORT_FIRST_ROWS = 3`); `Audio/` is untouched (OpenJarvis parity preserved).
- Tests (test-first): 8 new in `tests/test_fusion_preroll.py` (release at 3 rows, 2 rows blocked, waits for the end, companion blocks, companion alone blocked, first-only + reset per guest, single face without owner, stale camera does not spend the allowance); 112 focused voice/Fusion tests pass; Ruff clean. Real `FusionGate` probe with synthetic ASD rows: 160 ms blocked, 240/320 ms released as `kept_short_first`, 480 ms locks normally, other face 320 ms blocked. Synthetic rows do not prove physical camera/mic recognition. Needs API restart (Fusion worker is its child).
- After an idle/no-microphone check, restarted API only (881252 → 884871) so the short-first-answer release is active (Fusion worker is the API's child). `/health` merchant_api/live_pos_connected; Visual/avatar untouched.
- Live test of the short first answer (user: "dạ" still gets no reply): `kept_short_first` never appeared in `fusion_reasons`, so the new path did not fire. API log had no Fusion errors since the 22:39 restart; the session eventually locked (`locked: true`, source asd, native received audio). Cumulative counters cannot show the rows of one utterance, so the cause is not yet known; leading hypothesis: a one-syllable word does not reach ASD ACCEPT (≥0.7 probability) on 3 rows, which the release still requires. Not verified.
- Added a 60-row diagnostic ring `audio_metrics.fusion_recent` (test-first): per decision `{t, v (verdict), lock, p (ASD probability), mouth}` and per output row `{t, out (reason), heard}`; numbers and categories only. Needs an API restart and one repeated test ("dạ" once, right after the greeting, then stop) to read the exact rows.
- Test with the user's laptop (low-resolution laptop camera): the API had NOT been restarted, so `fusion_recent` was absent (old code). Cumulative numbers of that session: 1346 output rows all `speaker_unlocked`, only 8 ACCEPT verdicts, gate `locked: false` with source `mar`, last accept `asd_probability: None`, `asd_late: 4`, `asd_wait_timed_out: true`. So ASD scores did not arrive in time, Fusion fell back to mouth activity and could not form the lock (the lock needs ASD accept) — the whole session was unresponsive, not only the one-syllable answer. Visual was using ≈4 CPU cores; its log shows camera route flapping (16 local→remote, 14 remote→local) and 30 client closes with 1011 over the last 6000 lines (normal page reloads and camera restarts are possible causes; not established). Cause of the missing ASD scores is not yet known (candidates: Visual/diarizer overload, ASD stream-id mismatch after a camera stream change, low camera frame rate/resolution). No code changed in this step.
- After an idle/no-microphone check, restarted API only (884871 → 899857) so `audio_metrics.fusion_recent` is live; Visual/avatar untouched. Awaiting one repeated test ('dạ' once after the greeting, then silence).
- First "dạ" test with the live ring: the 60-entry ring was entirely plain silence rows by the time it was read (the session kept running), so the word's rows were gone. Session totals: gate `locked: true`, source `asd`; reasons `speaker_unlocked` 216, `kept` 15, `kept_onset` 4, `kept_tail` 6; verdicts ACCEPT 38, REJECT 10; no `kept_short_first`. Not enough to say where the one-word answer was lost.
- Fixed the diagnostic (test-first, 86 focused tests pass): `audio_metrics.fusion_recent` now skips plain `silenced_no_voice` rows and keeps 200 entries, so a word stays visible for the rest of a session. Needs one more API restart and one more test.
- After an idle/no-microphone check (the user's mic-off reached the API about a minute late over the SSH tunnel), restarted API only (899857 → 904090) with the filtered 200-entry `fusion_recent`. Visual/avatar untouched.
- Live "dạ" test with `fusion_recent` (laptop camera, Pet): the word lasted ≈0.56 s and produced 7 consecutive ACCEPT verdicts with ASD probabilities 0.40, 0.44, 0.60, 0.63, 0.67, 0.72, 0.96 (mouth ≈1.0); every output row was `speaker_unlocked`, `heard: false`. Root cause of the miss: `FusionGate._pre_lock_frame` sets `row_asd_track` only when the ASD probability ≥ 0.7 (`confirmed`), so only the last 2 of the 7 rows carry the guest's face id; the others are ACCEPT through the mouth-activity fallback (`asd_middle`) with `track_id=None`, whose audio `FusionPreroll` zeroes. The 3-row release therefore never sees 3 confirmed rows in one short word, because ASD confidence ramps up over the word. The 6-row lock fails for the same reason. The change needs a decision on how to count rows (asked of the user).
- User: "speaking longer is still not accepted". Next session's ring (laptop device camera): a ~0.7 s utterance had 4 onset rows REJECT (ASD 0.06–0.29, mouth 1.0), then 6 rows ACCEPT (ASD 0.95–0.97) which formed the lock; 6 `kept` + 3 `kept_tail` rows reached native, the first ≈0.3 s was dropped. Same ramp as the one-word test (0.40 → 0.96). Hypothesis (not measured): video arrives later than audio in device-camera mode (laptop JPEG frames over the SSH/Tailscale tunnel), and Fusion waits at most `asd_wait_secs` 0.12 s (Audio library limit), so the first rows of each utterance are judged on stale, mouth-closed frames; earlier sessions also showed `asd_late` and `asd_wait_timed_out`. The kiosk's local C920 should have far less video delay. Neither the short-answer relaxation nor the lock helps while onsets are rejected; awaiting the user's choice of target camera before changing Fusion timing.
- User chose the counting rule: a short first answer is released when it has ≥3 ACCEPT rows of which ≥2 are ASD-confirmed (≥0.7) on the guest's own face; still blocked if another face has confirmed speech or voices overlap. Their earlier remark "speaking longer is still not accepted" was traced to the same ASD ramp; my video-delay hypothesis was withdrawn because the rejected onset rows had mouth activity 1.0 from the same frames (video was current), so this also happens on the C920.
- Implemented test-first in `FusionPreroll` (`SHORT_FIRST_ROWS = 3`, `SHORT_FIRST_ASD_ROWS = 2`): ACCEPT rows without a face id keep their audio aside ("loose") and are used only by the short first answer; the normal lock replay still uses only face-id rows. 15 preroll tests; focused voice/Fusion suites pass; Ruff clean. Real `FusionGate` probe with the measured "dạ" ramp (25-frame ASD window): 7/7 rows released as `kept_short_first` (5 without face id + 2 with), a single confident row blocked, the same word from another face blocked. Not yet deployed (needs API restart). Known remaining limit: on a longer first sentence, onset rows the gate REJECTs (ASD < 0.3 at speech start) are already silenced inside `Audio/` and cannot be recovered host-side.
- After an idle/no-microphone check, restarted API only (904090 → 918049) with the ramp-aware short first answer (≥3 ACCEPT rows, ≥2 ASD-confirmed). Visual/avatar untouched.
- User: the guest's own transcript bubble ("Bạn: …") appears slower than usual. Not yet measured. Candidate seen in counters: the native input queue (`FilteredTrack`) has reached 480/960/2180 ms backlog, which happens when Fusion releases held rows in one burst (lock replay, short-first release) and the track drains them at real-time pace. Added (test-first, 99 focused tests pass) to `fusion_recent`: `q` = current native-input backlog in ms on each heard row (`FilteredTrack.metrics.buffer_ms`), and `{tr: user|assistant, final}` when the first and final transcript of a turn arrive (time only, never text). Needs an API restart and one test to measure speech-end → transcript.
- User: the first sentence of Trend's reply is cut. Hypothesis (not measured): Trend's own voice from the laptop speaker re-enters the laptop microphone and passes Fusion after the lock (the previous session forwarded 18 rows while the user says they were silent); native treats it as the guest talking over Trend, `userTurn/started` interrupts the speaker, and `SpeakerTrack.interrupt()` discards the queued reply — with the 0.5 s playout buffer, that is the opening sentence. This may also explain "no reply to 'dạ'". Added (test-first, 107 tests incl. Pet browser) `fusion_recent` entries `{turn: user, dropped_ms}` / `{turn: assistant}` so a session shows whether interruptions happen while Trend speaks and how much reply audio each one discards. Needs an API restart and one session; no behavior change yet.
- After an idle/no-microphone check, restarted API only (918049 → 932164) with turn/interruption and transcript timing in `fusion_recent`. Visual/avatar untouched.

## Stack restart observed at 23:58 and `av_fusion` failures stop — 2026-11-03/04

- Found while onboarding from `/tmp/openaimk-audio-handoff-2.md`: all four processes were restarted at 23:58:15–16 by someone other than this agent (not recorded before). Old → new: visual 881192 → 939008, avatar 881232 → 939054, API 932164 → 939074, `av_worker` → 939126. The agent did not restart anything.
- Before the restart `kiosk-api.log` had 647 `Voice connection failed at av_fusion` lines (last at line 110806; the new API starts at line 110902) and the UI waited for A‑V. After the restart: no new failures, `voice_ready: true`, gate `locked: true`, source `asd`, with a live session at 00:01.
- Root cause of the failures and of Visual's `1011 (internal error)` handler errors is still unknown. The last `1011` line (137096) sits just before the new Visual's startup, so it most likely comes from the old process (not proven). Visual (pid 939008) used ≈713% CPU at 3.5 min with an active session; the handoff recorded ≈4.4 cores after 77 min. Not interpreted. Watch Visual CPU and `1011` after 30–60 min; the earlier failure appeared after ≈77 min.

## Voice stuck at "Đang kết nối giọng nói… AV": no face reaches Fusion — 2026-11-04

- Stack restarted at 08:03 by someone else (visual 174879, avatar 174899, API 174939, `av_worker` 174989). The kiosk showed "Đang kết nối giọng nói… AV" again: 9 `Voice connection failed at av_fusion` since that start. Each one is `asyncio.wait_for(ready, 12)` in `av_transport._session_command`: the worker's `begin` waits up to 10 s for `media_ready()` and never replied in time. `av-worker.log` had no line after 08:03 (no worker exception, no ASD disconnect).
- Read-only Visual probe at 09:10: ping 0 ms, faces stream fresh (age 0.01–0.10 s), but 60/60 face events had no track and 31 `no_person` events; monitor frames 29.6 fps (C920 rate; the device path sends at most 15). The Visual log shows, at each attempt, `source local -> remote (stream …)` immediately followed by `remote -> local (… released)`. The `1011` handler errors line up with those teardowns (cancelled clients); they look like a consequence, not the cause. Cause of the release is still unmeasured: a probe waiting for a live session timed out because no session started.
- Found `.venv/bin/python` re-pointed at 08:13 (not by this agent) to system Python 3.15 (`/usr/bin/python3`), where `aiortc` cannot import (`_cffi_backend` only built for 3.12); tests and the next API start would fail. With user approval, restored the symlink to `~/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12` (matches `pyvenv.cfg` and `Visual/.venv`). `.venv/lib/python3.15/` left untouched. Running processes were unaffected (they started on 3.12.14).

## Device camera over WebRTC — 2026-11-04

- User chose to send "Camera thiết bị này" over WebRTC instead of JPEG packets on the kiosk socket ("làm luôn", design questions skipped). My calls: Visual's interface is unchanged; the API decodes the video and hands Visual the same 640x480 JPEG + wall-clock header as before. Socket JPEGs remain the fallback while WebRTC is not delivering. Microphone transport unchanged.
- Backend `trendcoffee/camera_rtc.py` (`CameraPeer`): answers a browser send-only video offer (aiortc), keeps at most 15 fps, encodes 640x480 JPEG with PyAV mjpeg (fixed qscale 5, ~0.7–1.4 ms/frame, in a worker thread; root venv has no numpy/cv2), skips frames >256 kB, a failing Visual send does not stop the reader. Metrics `audio_metrics.camera_transport` = frames, forwarded, send_errors, oversize, max_gap_ms (kept across guests). `InteractionHost`: `camera_offer` command (device mode only, else `invalid_camera_offer`), closed on renegotiation and disconnect; `camera()` (socket JPEG) is ignored while WebRTC frames arrived within 1 s; both paths go through `camera_frame()` to Visual.
- Frontend `frontend/src/cameraRtc.ts` (`RtcCamera`): send-only video transceiver, `maxFramerate` 15, `maxBitrate` 1.5 Mbps, negotiated over the kiosk socket after auth (and after a late camera start); `useKioskVoice.ts` stops socket JPEGs while it is connected; closed on shutdown / camera source change.
- Tests (backend first seen failing with the module missing): 7 in `tests/test_camera_rtc.py` (real aiortc loopback → decodable 640x480 JPEG, offer without video refused, 15 fps cap on a 30 fps fake-clock camera, send errors survive, host offer/refusal/close, socket fallback gating); 4 in `cameraRtc.test.ts`. `tests/test_device_camera_browser.py` now runs real Chromium twice: WebRTC (peer connected, ≥10 frames forwarded, 0 socket JPEGs in the following second; 2 socket JPEGs before it connected; 25 frames/2.5 s, 9.9 fps with connection setup included) and socket fallback with WebRTC refused (29 frames, 11.2 fps). The mic-off stop check now waits 300 ms instead of 200 ms before counting. I did not see the browser test fail against the old build.
- Verification: 110 focused backend tests (camera, speaker, kiosk runtime/socket, local camera, worker queue, preroll, tone, native peer), 54 frontend tests, typecheck, oxlint, Prettier, Ruff check, Ruff format on touched files. Built with `npm run build` (`emptyOutDir: false`, old hashed assets kept). Not deployed: needs an API restart and a kiosk page reload. Not measured on the laptop/Tailscale path; this does not by itself explain or fix the `av_fusion` timeout above.
- Toward the `av_fusion` timeout: API log since 08:03 shows many `/api/kiosk` socket accepts without page loads between them (e.g. three within a few lines), i.e. the kiosk socket reconnects; each reconnect detaches the controller, cancels the API→Visual camera link and releases the device camera in Visual (matching `local -> remote` then `released` per stream). Uvicorn does not log socket closes and `_vision_loop` swallowed its exceptions, so the trigger was invisible. Added (test-first, `tests/test_vision_link.py` red then green) WARNING lines with wall time: `Visual camera link open/lost` (exception type, and `video_status` value when Visual refuses), `Kiosk controller attached/detached`, `Kiosk socket ended: <reason>` in `api.py`. WARNING because the API configures no logging (INFO is dropped). 113 focused tests incl. the two Chromium camera tests pass; Ruff clean. Needs API restart, then one live attempt, to read the cause.
- Whole stack restarted at 09:28:06 by someone other than this agent (visual 238312, avatar 238352, API 238372, `av_worker` 238429), after the venv fix and with the WebRTC camera code in `kiosk.py`/`camera_rtc.py` and the new build. The logging edits to `kiosk.py` (WARNING, 09:29) and `api.py` (09:30) came after it and are not active yet.
- Live session after that restart (laptop, device camera): `voice_ready: true` at 09:30, 0 `Voice connection failed` since the start, Fusion verdicts ACCEPT 20 / REJECT 7. `camera_transport`: 2327 frames received, 2115 forwarded to Visual, 0 send errors, 0 oversize, max gap 171.8 ms. Visual switched to the device stream once and released it once (session end), instead of a release after every first frame. Cause of the earlier failures is still not proven: Visual was restarted at the same time (as at 23:58, when a restart also cleared it), so this session does not separate "WebRTC camera" from "fresh Visual".
- After an idle/no-microphone check (3 reads, `session_active=false`), restarted API only (238372 → 277757) at 09:36 with the camera-link / kiosk-socket WARNING logs (`Visual camera link open/lost`, `Kiosk controller attached/detached`, `Kiosk socket ended`). `/health` merchant_api/live_pos_connected. Visual 238312 and avatar 238352 untouched. Awaiting a live session; if "Đang kết nối giọng nói… AV" returns, read those lines in `.runtime/kiosk-api.log` plus `Voice connection failed` and Visual `camera_router`.
- Live session after the 09:36 API restart (laptop, device camera, page reloaded, mic on): at 09:41 `voice_ready: true`, gate `locked` source `asd`, 0 `Voice connection failed`; `camera_transport` 1477 frames, 1354 forwarded, 0 errors, max gap 111.7 ms; verdicts ACCEPT 12 / REJECT 33, reasons `kept` 12, `kept_onset` 4, `kept_tail` 3. The new logs show every kiosk socket end in this window as `closed by browser` (09:37:09, 09:39:42, 09:39:48), each followed at once by a controller detach; the camera link to Visual opens with each attach (`local` for the page's first 1–4 s, then `device`). So the Visual `remote -> local (released)` lines in this window follow browser-side socket closes (page load / source change / mic off), not API-side failures. Not shown: whether the earlier `av_fusion` failures had abnormal closes, because the logs did not exist then. The original failure has not reproduced since the 09:28 stack restart; cause remains unproven. Visual `1011` handler errors still appear around each release (sender not traced).

## Pet fits its panel: tall narrow panel no longer clips the robot — 2026-11-04

- User (screenshot of the kiosk's Pet panel, about 358 px wide and tall): the Pet looks too large and its ears touch the panel sides; asked to scale it down a little to fit. Reproduced with real Chromium (`tests/test_pet_fit_browser.py`, new): the robot's distance from the picture edge was 3 px at 1440×900 (panel 358×653) and 0 px (cut) at 1440×1080 (panel 358×833); 34–59 px in shorter panels (1280×720, 1100×800) and 79 px in the wide stacked layout (820×900). Cause: the Pet picture fills the whole panel; the robot is about 0.775 times as wide as tall, so a tall narrow picture is limited by width and the robot touches both sides.
- Change (CSS only, `frontend/src/components/pet/pet.css`): `.pet-floating-body` is a size container; the Pet picture (and the fallback image) keeps its full width and its height is at most 125% of its width (`height: min(100cqh, 125cqw)`), centred. Short or wide panels are unchanged. At 1440×900 the picture is now 320×400 and the robot is 34 px from each side (was 3 px); at 1440×1080 also 34 px (was 0). Test asserts at least 8% of the picture width at each side at 1440×900, 1440×1080, 1280×720, 1100×800, 820×900: 5 pass (2 failed before, with the old CSS). Screenshots `output/pet/fit-*.png`. No logic, voice or Fusion change.
- Not covered: phone-width layouts (390–420 px), where the microphone button overlaps the lower part of the stage and hides the robot's feet; that is a separate layout issue and was not changed. The dev server was not used; changes served after `npm run build` (old hashed assets kept; reload the kiosk page).
- Existing `test_pet_selection_persists_and_voice_never_connects_talking_head[1440]` and `[375]` fail (`dblclick` waits for the canvas to become "stable" and never does, because of the floating animation). They fail identically with the previous `pet.css` restored byte for byte and rebuilt (2 runs), so they are not caused by this change. `src/index.css` was modified at 10:05 by someone other than this agent after these tests last passed earlier today; cause not investigated. The other 8 Pet browser tests pass.
- Cause of the two red Pet tests found (corrects the entry above, which suspected `index.css`): `PetAssistant.tsx` was edited at 08:24 on 2026-11-04 by someone other than this agent (floating body with `pet-hover-float` plus drag), after `test_pet_browser.py` was last green. The canvas now moves 12 px up and down all the time (measured y 193.5–205.5 per frame), so Playwright's "element is stable" wait before `dblclick` never ends. A/B in the same browser: with the animation stopped through CSSOM the double click passes; with it running it fails with "element is not stable" (a style tag cannot be injected, the page CSP blocks it). The `index.css` suspicion was wrong; it has no part in it.
- Fix is test-only: `dblclick(force=True)` with a comment in `tests/test_pet_browser.py`; the test still asserts the `celebrating` state follows and returns to `idle`. No product code changed. `tests/test_pet_browser.py` + `tests/test_pet_fit_browser.py`: 10 passed; Ruff clean. The float/drag change is not described anywhere else in this file.

## Invoice: AI ORDER notice and printing right after payment — 2026-11-04

- User: the printed bill/invoice must carry a fixed "AI Order … đợi 15 phút … nhận tại quầy" line, and asked why printing waits for the customer to request it (reference: OpenJarvis kiosk auto-print / AI order note).
- Read-only findings: printing already starts without a request. `_save_order` enrolls every created merchant order in `print_jobs`; the worker (`TREND_PRINT_QUEUE=GP-C180I`, merchant mode on) printed today's two paid orders automatically: placed 10:26:00 → job completed 10:27:45 (GP-C180I-13), placed 10:36:49 → 10:38:44 (GP-C180I-14); 0 `POST /api/orders/*/invoice` requests in the API log. The delay came from the queue: 185 `waiting` rows (174 with `merchant_rejected`, plus expired/pending QR orders) were re-polled at the merchant forever (every 10 s each, 8 rows per 2 s pass), ahead of a newly paid order.
- User decisions: put the notice in the merchant order description (like OpenJarvis's "AI order"), wording "AI ORDER / Quý khách vui lòng đợi khoảng 15 phút và nhận món tại quầy thanh toán. Cảm ơn quý khách!", and do both queue fixes.
- `merchant.py`: `AI_ORDER_NOTICE` + `order_description(order)` = notice, `Kiosk <order id>`, then the guest's order note. Validation of a guest order without branch accepts the new or the legacy (`Kiosk <id>[\n<note>]`) description, so orders placed before the change keep their payment/invoice checks.
- `invoices.py`: `wake(order_id)` sets the row to `waiting` with `next_check=0` (also from `abandoned`); `service.payment` calls it when the merchant reports `paid` (the QR panel polls every 3 s; the voice `kiosk_payment` tool uses the same path), so the next 2 s worker pass prints it. Unpaid orders older than 45 min (15 min QR + 30 min grace) become `abandoned` (error `payment_expired`/`payment_pending`/merchant code) and are not polled again; a paid order waiting for its invoice is never abandoned. No reprint path, no change to at-most-once spooling.
- Tests (red first): description exact text; legacy description still validates (regression guard); paid order seen by the kiosk prints on the next non-forced pass; expired and merchant-rejected old orders stop polling; late payment revives an abandoned order and prints once; paid order without invoice stays waiting; recent unpaid order stays waiting. 128 related backend tests pass (service, voice checkout, kiosk runtime/checkout, invoice printing, merchant, printer, categories); Ruff check/format clean.
- Not verified: whether TREND's invoice PDF actually prints the order description, and whether TREND limits description length (new description is 136 characters plus the guest note; order notes up to 1000 characters were already sent). Both need the first real paid order after deployment; tests use fixtures only. Needs an API restart; on the first pass after it, the existing stale rows become `abandoned` after one more merchant request each.

## Trend claims actions that never ran — root cause traced — 2026-11-04

- User: Trend says an item was added, an order created, a QR shown or payment done, but the screen shows nothing; happens at add-to-cart, order, checkout and payment.
- Evidence (read-only, today's 22 kiosk rollouts in `~/.codex/sessions/2026/11/04`, which hold transcript segments, `<realtime_delegation>` messages, Codex `custom_tool_call`s and outputs): of 66 Trend sentences that claim an action or screen state, 15 had no delegation to Codex and no kiosk tool call since the guest's turn (e.g. 10:53:19 "thanh toán giúp mình luôn" → "Bạn quét QR…" with an empty cart; 10:53:52 "Tạo lại đơn" → "Đơn … đã tạo xong"; 09:42 "Đã vào giỏ rồi đó"; 10:59/11:00 "Mình đã thêm … vào đơn rồi"), 2 followed a delegation with no tool call in the window (not yet inspected), 0 followed a tool error, 49 followed a tool call. When Codex is delegated, the tools work (10:54:34 add → checkout → QR).
- Root cause: the realtime voice layer (V3, `VOICE_INSTRUCTIONS`) decides on its own whether to delegate; when it does not, it composes the result itself, often copying the success sentences that appear in its prompt and earlier turns. Nothing on the host checks that a kiosk tool ran before such a sentence is spoken. Not a recent regression: Codex CLI 0.166.0 since 2026-10-30; skipped delegations also on 11-02 and 11-03. `thread/realtime/start` (v3) offers no "always delegate" option (checked the experimental protocol schema: delegationAckFiller, codexResponseHandoffMode, clientManagedHandoffs, initialItems, prompt, …).
- No change made yet; awaiting the user's choice of fix.
- User chose both fixes (host check + prompt), measured.
- Host check, test-first (`tests/test_claim_guard.py`, 23 tests; module `trendcoffee/claim_guard.py`): a Trend sentence with completed-result wording (QR/created/sent/paid/added/in cart/updated/on screen) is backed only if a kiosk tool ran after the guest's latest request began (2.5 s allowance; guest utterances under 3 words continue the current request). Offline replay of 2026-11-03/04 rollouts: 23 unbacked results caught; the two true restatements that a plain rule flagged (09:49:00 after "nhé", 10:54:53 "Chắc chưa") are no longer flagged; one arguable explanation (09:04:48) remains flagged. In `_open_voice`: on an unbacked result the speaker queue is interrupted, the rest of that reply's audio is dropped until the next assistant turn, the browser gets the existing `voice_turn` user interruption, `audio_metrics.unbacked_claims` and `fusion_recent {claim: unbacked}` count it, a WARNING is logged, and `CodexVoice.append_text` sends a developer note (`thread/realtime/appendText`) asking the voice layer to delegate the latest request now. The note is sent from a task because transcript events arrive from Codex's reader loop. Checked on transcript deltas and again on the final transcript.
- Prompt, test-first (`test_the_voice_layer_states_results_only_by_relaying_codex`): `VOICE_INSTRUCTIONS` now starts with the rule that the voice never knows kiosk state, states results only when relaying Codex's result for the latest request, delegates otherwise and never repeats an earlier result as new. Exact QR/paid sentences unchanged (locked test still passes); both realtime start paths use the same text for `prompt` and `initialItems`.
- Verification: 126 voice/kiosk/speaker/camera/native tests, 33 prompt/checkout tests, 89 of 90 Pet browser/socket/invoice/merchant/service tests (the failing Pet `[375]` test passed 2/2 when rerun alone; known flaky page load); Ruff check clean; Ruff format clean on touched files (pre-existing drift in `test_live_tables_browser.py`, `test_reference_cart_browser.py` untouched).
- Not measured: how much of an unbacked sentence is already heard before the stop (depends on transcript vs audio timing; Pet has a ~0.5 s playout buffer, Avatar 3D uses socket PCM), whether the realtime model acts on the developer note, and the prompt's effect on the rate. Plan: after an API restart, compare `unbacked_claims` and the rollout replay (`claims.py`-style) on new sessions against the 2026-11-04 baseline (15 unbacked of 66 result sentences, 22 sessions). Needs an API restart (also activates the invoice changes above).

## Voice A‑V wait again; camera choice persisted; API restart — 2026-11-04

- 11:20 user: "Đang kết nối giọng nói… / Đang chờ camera thấy rõ khuôn mặt và kết nối A‑V… / Đang chờ micro". New logs: every attach since 10:22 used `camera local`; 40 `Voice connection failed at av_fusion` since the 09:36 API start. The user then said they were working at the kiosk's C920, so my first reading ("nobody in front of the C920") was wrong for that moment and is withdrawn.
- Read-only probes: 11:23:25 (mic just turned off) Visual saw no person (61/61 empty face events) with changing C920 frames (mean abs diff ≈1.6 per frame, 31.5 fps, not frozen); 11:24:31 (session active) 44/60 face events had tracks, 39 live tracks, 22 `person_near`. The worker's `media_ready()` also needs a live face within 0.8 m in the nearest faces event (`FaceTrackBuffer.anchor(now, 0.8)`) and the ASD bridge ready; which condition failed is not yet measured. A background probe now records per second: face events, live faces, live faces ≤0.8 m, nearest distance, and the API's failure lines for the next session.
- Camera source choice is now kept per browser (user decision), test-first: `tests/test_device_camera_browser.py::test_the_chosen_camera_source_survives_a_page_reload` failed before (reload reverted to "Camera tại kiosk"), passes after; a browser that never chose still starts on the kiosk camera. `useKioskVoice.ts` stores `trendcoffee.cameraSource` (try/catch like the voice preference). 54 frontend tests, typecheck, oxlint, Prettier; 3 device-camera Chromium tests pass. Built (old assets kept).
- After waiting for one minute of idle (`session_active` and `microphone_receiving` false; a first idle window at 11:23:53 was skipped because a guest reconnected), restarted API only (277757 → 662208) at 11:25 with: AI ORDER description + paid-first/abandoned print queue, claim guard + voice prompt rule, camera choice persistence (page reload needed). `/health` merchant_api/live_pos_connected. Visual 238312 and avatar 238352 untouched.

## Invoices failed after the AI ORDER change: stale MCP invoice worker — 2026-11-04

- User at 11:31: "bây giờ không in hóa đơn". Orders created after the 11:25 API restart had print jobs `failed` with `merchant_order_mismatch` (terminal), including paid order 7a0305c952 (11:29:37 +07). The running API's validation passed for all of them (read-only re-check: slug, description, type, subtotal, items).
- Cause (introduced by the description change): a second invoice worker. `trendcoffee mcp` (pid 173344), started 08:01 by the Codex app-server daemon from `.codex/config.toml`, runs `invoice_worker` on the same database with code loaded at 08:01; its `validate` accepted only the legacy `Kiosk <id>` description and marked the new orders failed. Restarting the API does not restart this process.
- With user approval: stopped 173344 (no other `trendcoffee mcp/serve` left except API 662208), then requeued the four never-spooled jobs (`failed`, `merchant_order_mismatch`, `job_id` NULL, orders after 04:25 UTC) to `waiting`, next_check 0. The paid order printed through the API worker: CUPS job GP-C180I-15 at 11:33:34; the three unpaid orders keep waiting.
- Lesson: merchant/invoice code changes need both the API and the MCP server (Codex daemon child) restarted; otherwise two code versions process the same print queue. Not automated yet.

## av_worker names the failing media condition — 2026-11-04

- Pattern so far: the `av_fusion` timeout ("Đang chờ camera thấy rõ khuôn mặt và kết nối A‑V…") appeared about 1–2 h after each API start (08:03 → 09:10; 09:36 → by 11:20, 40 failures) and cleared after each API restart (the worker is the API's child). At 11:24:31 Visual reported 39 live faces while the voice still failed; at 11:27:56 after the restart a live face at 0.25–0.32 m and voice ready. Root cause unknown because the worker logged nothing.
- Test-first (`tests/test_av_worker_queue.py::test_a_media_wait_names_every_condition_that_is_missing`, red then green): `Worker.media_missing(now)` lists `no_stream`, `asd_bridge_not_ready`, `no_faces`/`faces_stale`/`no_live_face_within_0.8m`, `fusion_tasks_stopped`; `media_ready()` is now `not media_missing()` (same conditions as before). `media_report()` writes one stderr line to `.runtime/av-worker.log` with the time, stage (`begin` 10 s timeout or failed `check_ready`), the missing conditions, face count/live count/nearest distance and the ASD bridge state (ready/terminal/closed/version). Numbers and states only. 87 worker/Fusion/kiosk tests pass; Ruff clean.
- Needs an API restart to take effect. Next occurrence: read `grep 'media not ready' .runtime/av-worker.log`.
- After one minute of idle (user turned the mic off; background idle check), restarted API only (662208 → 679206) at 11:51:10 with the av_worker media diagnostics; new av_worker 679215. `/health` merchant_api/live_pos_connected. Visual 238312 and avatar 238352 untouched. MCP server (`trendcoffee mcp`) is not running; the Codex daemon starts it on demand with current code.

## Pet floats higher inside its stage — 2026-11-04

- User: `pet-floating-body` should float higher; scope = up to the top of the panel (screenshot of the panel's top with the "Mic off" line). My reading: the float may rise as far as the top of the Pet's stage and no higher; the stage (`.avatar-stage`, overflow hidden) starts below the "Mic off" line and clips anything above it, so the Pet never covers that line. Changeable: the cap below.
- Measured before: the float rose only 14 px (keyframes −10/−4/−12 px) although the robot's highest point rests 90 px (1440×900), 180 px (1440×1080), 32 px (1280×720) and 40 px (1100×800) below the stage top.
- Change (CSS only, `frontend/src/components/pet/pet.css`): the container query box moves to `.assistant-pet` (the stage-sized parent) so `.pet-floating-body` can size its float from it. `--pet-room` = space above the picture + 9% of the picture height (the robot's own top margin, measured 10%); `--pet-rise` = clamp(12 px, room − 4 px, 44 px); the keyframes scale the old −10/−4/−12 px shape by the rise. The picture sizing from the earlier fit change (`min(100cqh, 125cqw)`) is unchanged, now through `--pet-picture`.
- Test-first (`tests/test_pet_fit_browser.py::test_the_pet_floats_higher_but_never_above_its_stage`, 4 sizes; red first: 14–15 px rise): animation paused at its rest and highest phase in real Chromium, robot's highest pixel measured inside the stage image. After: rise 47 / 47 / 26 / 34 px, highest point still 43 / 133 / 6 / 6 px inside the stage (test requires ≥2 px and a rise of at least min(40, room − 10)). Screenshots `output/pet/float-rest-1440x900.png`, `float-peak-1440x900.png`.
- Verification: 14 Pet browser tests pass (the 2 earlier failures were fixed by the `dblclick(force=True)` change); 54 frontend tests, typecheck, oxlint, Prettier, Ruff. Built with `npm run build` (old assets kept); reload the kiosk page. Not changed: the drag range (±65/±45 px) can still push the Pet out of the stage on a short panel; the Wobnimo mouth/eye animation; no logic or voice code.
- User asked for a higher float ("cao hơn"). Cap raised from 44 px to 90 px in `pet.css` (`--pet-rise: clamp(12px, room − 4px, 90px)`); test-first: the float test now requires a rise of at least min(80, room − 10) and failed first at 1440×900 and 1440×1080 (47 px). After: rise 84 / 93 / 27 / 34 px at 1440×900 / 1440×1080 / 1280×720 / 1100×800, the robot's highest point 6 / 87 / 5 / 6 px inside the stage at the top of the float (the Pet nearly touches the stage top at 1440×900 and still stays under the "Mic off" line). Screenshot `output/pet/float-peak-1440x900.png`.
- Fix to the test from this change: the side-margin test (`test_the_pet_fits_inside_its_panel_with_room_at_the_sides`) was phase-dependent: at 1440×900 it failed once because, with the higher float, part of the canvas box reached over the "Mic off" line and that text counted as robot pixels. It now measures with the float paused at rest; 3 consecutive runs 9/9 pass. 14 Pet browser tests, 54 frontend tests, typecheck, oxlint, Prettier, Ruff pass; built (old assets kept), reload the kiosk page.

## Kiosk Codex threads: readable names and archive at session end — 2026-11-04

- User (screenshot of Codex's session picker, Filter Cwd / Active / Sort Updated, full of `<realtime_delegation> <input>…` rows): asked how to handle voice/Codex sessions; chose naming and archiving at session end; retention/deletion declined ("no need"), so nothing is ever deleted by the kiosk.
- Before: each guest session starts a Codex thread; Codex stores a rollout per thread (1434 kiosk rollouts, 70 MB, 53 on 2026-11-04, among 151 `codex-tui` operator sessions); the picker title is the first message, i.e. the XML. Nothing named, archived or removed them. Rollouts hold the guest's spoken text (local only).
- Change (test-first, `tests/test_codex_threads.py`, 4 red then 5 green): `CodexVoice.stop_voice` now also sends `thread/archive` after `thread/realtime/stop` and `thread/unsubscribe` (failures ignored); new `CodexVoice.name_thread` (`thread/name/set`, cosmetic, never raises). `InteractionHost`: when a guest's thread is bound it is titled `Kiosk HH:MM — đang phục vụ` from a background task (a hung request cannot delay the greeting, tested); at session end or a voice reconnect `_retire_voice` titles it `Kiosk HH:MM–HH:MM` and then stops (= archives) it. Unused warm-up threads are archived by `stop_voice` too. `session_wall` stores the guest session's start.
- Live check with the real Codex app-server and one empty throwaway thread (no turn, no tool, no merchant; deleted afterwards): the title is stored; after `stop_voice` the thread is absent from `thread/list` (archived=false) and present with its title under archived=true; its rollout moved to `~/.codex/archived_sessions/rollout-…jsonl`. An empty thread has no rollout until its first message.
- Effect on tooling: new kiosk threads now end up in `~/.codex/archived_sessions/` instead of `~/.codex/sessions/YYYY/MM/DD/` once the call stops. Analysis scripts (the claim/transcript replays) must read both locations. Existing 1434 threads were not touched (still listed as active); archiving them in bulk is possible on request.
- Verification: 126 related backend tests pass (kiosk runtime/socket/checkout, speaker, claim guard, voice prompt/start, native peer, camera, vision link); Ruff clean. Needs an API restart; the first new guest session after it shows the new titles.
- After three idle reads (`session_active` and `microphone_receiving` false), restarted API only (50494 → 117400) at 14:36:08 with thread naming/archiving, the claim guard, the AI ORDER/print-queue changes and the av_worker media diagnostics; new av_worker 117406. `/health` merchant_api/live_pos_connected. The user allowed a full-stack restart, but only the API carries these changes, so Visual 50434 and avatar 50454 were left alone. Found on the way: Visual/avatar/API had been restarted at 13:25:22 by someone other than this agent.
- Three `trendcoffee mcp` processes exist (49004 from 13:23:53, 106758 from 14:23:09, 108779 from 14:23:59, all children of the Codex app-server daemon); each runs an invoice worker on the same database. All started after `merchant.py`/`invoices.py` were last edited (10:52), so none has the stale validation behind the 11:30 incident; double printing is prevented by the database compare-and-set (`tests/test_invoice_printing.py`). No print job failed since then (last `failed` row is from 2026-10-28).

## Guest identity principle confirmed — 2026-11-04

- User decision: a kiosk session and its Codex conversation serve whoever is the current guest at that moment. No names or guest profiles; the same person returning later is a new guest; no face or voice data is kept between sessions (confirmed as intended). Attribution stays: face `track_id` → session token/generation → Codex thread → tools scoped to that token; the per-session speaker lock in Fusion. Linking a thread to its orders (proposed) was not requested and is not implemented.

## One guest, one Codex thread across voice reconnects — 2026-11-04

- User: a voice drop and reconnect mid-session must not split the conversation into several rows. Before: every `_connect_voice` attempt ran `_disconnect_voice` (stop + archive the thread) and `_open_voice` created a new thread; failed attempts (e.g. the `av_fusion` timeouts) also made a new, empty thread each time.
- Live check first (real Codex app-server, one throwaway thread, two silent calls, no guest/tool/merchant, thread deleted): a second realtime call on the same thread after `thread/realtime/stop` started in 2.2 s (first call 2.8 s).
- Change, test-first (`tests/test_codex_threads.py`, 6 new: 4 red then green, 2 guards): `CodexVoice.end_call` stops only the realtime call (peer closed, `thread/realtime/stop`); `CodexVoice.resume_thread` rebinds the new call's handlers to a thread this app-server process created and still holds (else `voice_thread_not_resumable`; `_thread_process` maps thread → process). `InteractionHost`: `_drop_call` ends the call and keeps `thread_id`; `_open_voice` resumes the guest's thread when it can (else retires it and creates a new one, titled as before); `_connect_voice` keeps the thread after camera/microphone/A‑V failures and replaces it only when the failure was at `codex_thread`/`codex_voice` (the thread could not carry a call). Fakes without `end_call` keep the old behaviour. The thread is stopped, titled `Kiosk HH:MM–HH:MM` and archived once, at session end.
- Mid-session drops are now logged: `Voice call dropped at HH:MM:SS (closed|error, reason …); reconnecting on the same thread` (WARNING, `kiosk-api.log`), so the cause and rate of drops can be measured next.
- Verification: 160 voice/kiosk/Fusion/worker tests, 8 Pet and device-camera Chromium tests, Ruff clean. Not verified live: a real mid-session drop and reconnect on the same thread (only the protocol step was checked). Needs an API restart.

## Reverted: Pet float height change — 2026-11-04

- User (angry): never asked to make the Pet float or to change its pose; keep Volt at its default. My reading of "pet-floating-body expected pet floating height more … scope top panel" as "float higher" was wrong.
- Reverted `pet.css` to the state before the float change (the 12 px `pet-hover-float` keyframes −10/−4/−12 px that existed since the undocumented 08:24 `PetAssistant.tsx`/`pet.css` change; container on `.pet-floating-body`); removed `test_the_pet_floats_higher_but_never_above_its_stage`. Kept the earlier user-requested fit sizing (`height: min(100cqh, 125cqw)`) and the side-margin test measured at rest. Built (old assets kept); 10 Pet browser tests pass. Reload the kiosk page.
- Open question to the user: the remaining 12 px float and the drag-to-move were not added by this agent (08:24 change, not in this file); whether to remove them for a fully default Volt, and what "pose" change they saw, is pending.
- User decision: remove the hover float, Volt stands still (keep drag-to-move). `pet.css`: `pet-hover-float` animation, its keyframes and the paused-while-dragging rule removed; `.pet-floating-body` stays as the sizing container. Test-first: `test_volt_stands_still_without_a_page_float` (no animation on `.pet-floating-body`, canvas y unchanged over 1.5 s) failed before, passes after. The persistence test's `dblclick` is back to a plain `dblclick()` (the float was the only reason for `force=True`); the side-margin test no longer needs to pause an animation. 11 Pet browser tests pass; Prettier/Ruff clean; built (old assets kept). Volt's own Wobnimo animation, click = poke, double click = celebrating and drag are unchanged.

## "Đang chờ camera… A‑V" again: the worker's reply reader dies silently — 2026-11-04

- 15:11 report (bug back, 40 min after the 14:36 API restart). Evidence (read-only): 20 `Voice connection failed at av_fusion` since 14:36, all `TimeoutError` from the 12 s wait for the worker's `session_ready` in `FusionProcess._session_command`; `av-worker.log` has 0 `media not ready` lines (the new diagnostic never fired, so the worker never reached its own 10 s face wait) and nothing after 14:36:28; the worker (pid 117406) is alive, 1.5% CPU, 59 threads all idle (stdin reader thread waiting in `anon_pipe_read`, event loop in `ep_poll`); both IPC pipes have 0 unread OS bytes (not conclusive: asyncio buffers data in memory). So the worker is idle and its replies are not reaching the `begin` waiter.
- Defect found in `FusionProcess._read` (the API's one task that reads the worker's JSON lines): any exception ended it silently (`except (Exception, CancelledError): pass`) — a non-JSON line on the pipe (a C library writing to fd 1), a line over the 2 MB stream limit, a non-dict JSON value, or any exception from the kiosk's `fused` event handler (unguarded `b64decode` and `await codex.append_audio(...)`, which can fail when the native call closes). Nothing restarted the reader and `start()` returns at once for a live process, so every later `begin` waits 12 s and times out until the API is restarted — matching "after 1–2 h, only a restart fixes it". Not proven to be the trigger in this incident (no log existed); proven to be a real way to reach exactly this state (tests below fail before the fix).
- Test-first (`tests/test_fusion_reader.py`, 6 tests, 5 red then green): a non-JSON line, a non-event JSON value and an over-long line are skipped and logged and later replies still arrive; a failing event handler does not end the reader and later events are delivered; a `fatal` event still ends the reader and fails the wait (kept); a reader that ended while the worker lives makes `start()` stop and respawn the worker (safety net, logged `reader had ended…`); the reader logs `av_worker reader ended (worker returncode …)` when it ends. 150 related tests pass; Ruff clean.
- Needs an API restart. If the symptom returns afterwards, `kiosk-api.log` will name the cause (`not a JSON event`, `over-long line`, `event handler failed …` with traceback, `reader ended`) and `av-worker.log` the media condition (`media not ready …`).
- Follow-up the same afternoon (user: "fix, stop explaining"): the first guest session after the 14:36 API restart (15:00) already failed — not a decay after 1–2 h. A real standalone av_worker (same code and models, fake Visual URL so the live Visual was untouched; GPU had room) answers `begin` correctly: error after 10.0 s when no face is available, no non-JSON line on its stdout, 20 s to load. So the worker side works; the silence is between the API and the worker. Root cause of the silence in the live incident is not proven (no log existed).
- Fixes (test-first, 9 tests in `tests/test_fusion_reader.py` incl. 3 for this, 154 related tests pass): the worker now logs the traceback and duration of a failed or successful `begin` (`[av_worker] begin failed after …`, `begin ready after …`; it used to swallow the exception); the API waits 15 s (was 12) for any worker answer; two consecutive silent commands stop the worker and the next session starts a fresh one (`av_worker did not answer … / is not answering; stopping it…` in `kiosk-api.log`) — an `error` answer (no face yet) never counts as silence; plus the reader fixes above (survives a bad line or a failing handler, restarts the worker if the reader ended). Net effect: the kiosk recovers by itself within about two attempts instead of staying stuck until the API is restarted.
- Needs an API restart (the stuck one at 15:11 is cleared by it too).
- After three idle reads, restarted API only (117400 → 158232) at 15:23 with the worker self-heal, the reader fixes, `begin` logging in the worker, one Codex thread per guest across reconnects, the stand-still Volt build and the earlier changes; new av_worker 158241. `/health` merchant_api/live_pos_connected. Visual 50434 and avatar 50454 untouched. If "Đang chờ camera… A‑V" returns: `grep -E 'did not answer|not answering|reader|event handler|not a JSON' .runtime/kiosk-api.log` and `grep -E 'begin (failed|ready)|media not ready' .runtime/av-worker.log`.

## New sessions read: slow replies and results spoken but not shown — 2026-11-04

- User: Trend is slow and sometimes only reads search results without showing them. Read 41 kiosk sessions of 2026-11-04 (199 guest turns; active and archived rollouts).
- Speed, measured: guest → first speech (acknowledgement) median 2.4 s (p90 5.7); guest → spoken result median 12.5 s (p90 18.7, max 39.9). Kiosk tools themselves are fast (median 0.2 s per turn, max 4.7 s). Per delegated request: delegation → first tool call 2.1 s; each extra sequential tool call adds a model round trip of 1.8 s median; last tool result → Codex final answer 1.7 s; Codex final answer → Trend speaks it 5.3 s median (p90 10.2) — the largest single part, in the realtime voice layer. Requests with 1 / 2 / 3 sequential tool calls reach Codex's final answer in 4.3 / 8.4 / 10.9 s (76 / 58 / 9 requests); the model calls one tool per script. Nothing changed for speed yet: the remaining levers are the user's baseline (gpt-6-luna medium, Fast off) or prompt/tool-flow changes; awaiting the user's choice.
- Not shown, measured: 20 of 90 replies that named menu items or prices had no display tool behind them (advice/search answers from the catalog in the prompt, and replies the voice layer composed without delegating). Fix, test-first (`tests/test_spoken_items.py`, 8 tests, red then green): `claim_guard.spoken_items(text, catalog)` finds catalog drinks named in a reply (spoken order, names under 6 characters ignored, a name inside a longer matched name dropped, at most 6). At the end of a Trend reply that names drinks while no kiosk tool has answered the guest's latest request, the host waits `show_delay` (4 s) and, if still no tool ran and the session is unchanged, shows those drinks with the same `view: menu` event `kiosk_menu` uses; counted in `audio_metrics.shown_for_speech`. Replay of today's transcripts: 20 replies would now show their drinks; 3 acknowledgements are left to the tool that followed within 4 s (no flicker). Related suites pass; Ruff clean. Needs an API restart.
- API restarted only after one minute of idle (background check) at 15:40:02: 158232 → 168161, with show-what-is-said. Visual/avatar untouched.
- User chose two speed directions: merge cart + checkout, and find the 5.3 s answer-to-speech part.
- Merge, test-first (3 new tests in `tests/test_voice_checkout.py`, red then green): `kiosk_checkout` accepts `lines` (same schema as `kiosk_cart` add, shared `LINES`), adds them to the cart and places the order in the same call; `INSTRUCTIONS` now asks for one `kiosk_checkout` call with `lines` and verification of the returned order lines (kiosk_cart only to change the cart without ordering; "never checkout an older cart" kept). Real-model evaluation (`output/checkout-flow/evaluate.py` copy with a `two` case; GPT-6-Luna medium, temporary database, mocked merchant, no real order): every after-run used 1 tool call instead of 2, correct lines, QR shown. Codex time to its final answer: `two` 10.8 / 10.0 / 14.0 s before → 9.3 / 8.7 / 8.1 s after (median −2.1 s); `latte` 9.9 / 7.4 / 15.1 s before → 8 runs after, median ≈ 8.7 s (5.7–10.7 s, one 28.9 s outlier). Small samples; model variance is large.
- That outlier run (after) replied "Đơn đã được thanh toán." for a pending QR order; one before-run (latte 3) gave an empty reply. Whether the merge changes the error rate is not established (7/8 vs 2/3 correct). Added a host check regardless, test-first (3 tests in `tests/test_claim_guard.py`): the paid sentence is stopped unless a kiosk tool result in this call reported paid (`says_paid`: `payment_status`/`status`/`payment.status` = paid), with a developer note telling the voice to relay `kiosk_payment`'s real status or the QR sentence; counted in `unbacked_claims`.
- The "Codex final answer → Trend speaks it 5.3 s" figure was measured to the END of the spoken sentence (rollout transcript segments are logged when a segment finishes), so it includes the 2.5–3 s it takes to say the QR sentence; the real wait before speech is about 2–3 s, including the 0.5 s playout buffer the user accepted for clean audio. The earlier "guest → spoken result 12.5 s" is also measured to the end of the sentence. No realtime option was changed; no evidence that one would help.
- 197 related tests pass; Ruff clean. Needs an API restart (one-call checkout, prompt, paid guard).
- After three idle reads, restarted API only (168161 → 175733) at about 15:48 with one-call `kiosk_checkout` + prompt, the unverified-paid guard and the earlier changes; new av_worker 175739. `/health` merchant_api/live_pos_connected. Visual 50434 and avatar 50454 untouched. Check next: `audio_metrics.unbacked_claims` and `shown_for_speech` in `/api/kiosk/status`; Codex rollouts (now in `~/.codex/archived_sessions/` after a session ends) for guest → first tool call and calls per request (baseline 1.9 s; 1 / 2 / 3 calls = 76 / 58 / 9 requests).

## Search found the dishes but the screen stayed empty until the guest asked again — 2026-11-04

- User: a search needs two attempts; the first time Trend finds the dishes but only reads them out, the second time it shows them. Reproduced in the 15:20–15:53 conversations: 15:26:46 "Tìm cho mình những món có hoa" → `kiosk_menu({queries:["món có hoa"]})` → Trend said "trà nhài hoa cúc" → guest: "Hiển thị đi, hiển thị đi" → second call with `item_ids` showed it; 15:52:28 "tìm cho tôi món trà" → `kiosk_menu({queries:["món trà"]})` → "Mình đã mở thực đơn trà rồi" → guest: "Có cái gì đâu" → second call.
- Root causes (measured): (1) `menu_search` compared the whole phrase, so descriptive wording found nothing: "món có hoa", "món trà", "món có kem" returned 0 items (the words "món", "những", "các", "cái", "loại", "nào", "gì" were not ignored). (2) With 0 items the kiosk still sent `view: menu` with `item_ids: []` and the guest's wording as the search text; the screen treats `[]` as "show nothing", so the grid was blank, while Trend answered from the catalog snapshot in its prompt (the tool result carries the full catalog when nothing matches).
- Fixes, test-first (`tests/test_menu_descriptive.py` 5 tests, 3 red; `tests/test_spoken_items.py` +5, 1 red): those words are now filler in `menu_matching._FILLER` (named drinks still resolve exactly; a phrase with no matching dish still matches nothing); a search with no result now shows the whole menu (`item_ids: null`, `query: ""`) instead of an empty screen; the host remembers what the last display tool put on screen (`self.screen`) and, after a reply that names drinks, adds those drinks to a menu view that lacks them (keeps what was shown, menu order), after `show_delay` and only for a menu view made for the guest's latest request — cart, payment and other screens are never replaced, and the whole menu counts as showing everything.
- Replay on the 47 distinct text searches Trend ran on 11-03/04: "món có hoa" and "món trà" went from 0 items to 1 and 3; "món latte" now also adds Latte; 9 searches still match nothing (e.g. "kem tươi", "chè vải": not in the menu) and now show the whole menu instead of a blank screen. 204 related tests pass; Ruff clean. Frontend unchanged. Needs an API restart.

## Trend ordered nothing: the voice never delegated, then claimed a QR — kiosk now runs the request itself — 2026-11-04

- User screenshot/transcript (session 15:59:50, 16:00): guest "một latte mang đi" → Trend "để mình lên đơn ngay cho bạn đây" → 19 s later "Bạn quét QR trên màn hình để thanh toán nhé…" while the cart was empty. Rollout read: no `realtime_delegation`, no Codex turn, no tool call at all for that request — the realtime voice acknowledged and never delegated (the 15/66 pattern again, 2026-11-04 baseline). The claim guard worked (`unbacked_claims` 1, reply stopped; the first words were already audible) but the voice then only apologised and still did not delegate, so the guest got no order.
- Live check (real Codex, fixtures only: temporary database, mocked merchant, silent realtime call, no guest): a host-started `turn/start` on the guest's thread ran `kiosk_checkout` with `lines` 3.6 s later, posted one fixture order, and the realtime voice itself spoke "Bạn quét QR trên màn hình để thanh toán nhé." (184 audio chunks) — Codex answers of host-started turns reach the voice automatically.
- Change, test-first (`tests/test_claim_guard.py` +7: 5 red, 2 guards; 32 pass): when the guard stops a result claim, the kiosk starts a Codex turn itself with the guest's own words, the last 6 finished turns as context and the instruction to run the request with the kiosk tools and report only the real result (`CodexVoice.start_turn`, `claim_guard.recovery_turn`); it then tells the voice `TAKEOVER_NOTE` (do not delegate again, do not state a result, relay the result) instead of "delegate now". Once per guest request (and once per payment check); if Codex refuses the turn the old "delegate now" note is sent. An unverified "đã thanh toán" claim starts a turn that calls `kiosk_payment`. Not covered: a voice that acknowledges but never claims a result (e.g. says only "để mình xem") — nothing is run for that; measure first. Not run end to end: the full path (guard → turn → tools → spoken result) was unit-tested with fakes and its Codex step checked live; a risk to watch is a duplicate when the voice also delegates late (checkout repeats return the same order only if the cart is unchanged).
- 192 related tests pass; Ruff clean. A background job restarts only the API after one minute of kiosk idle and will load this code together with the menu-search fix; the API was last started 15:48.
- API restarted only (background job after one minute of kiosk idle) at 16:05:28: 175733 → 188841 (the job's own "new 182966" is a shell it matched by mistake; `kiosk.py status` and `ps` give 188841), after the last code edit (16:03:47), so it carries the descriptive-search fix, the never-empty menu view, the spoken-drinks-on-screen rule and the kiosk recovery turn. `/health` merchant_api/live_pos_connected. Visual 50434 and avatar 50454 untouched. Next check: `audio_metrics.unbacked_claims`, `shown_for_speech`; rollouts for a `turn/start` the kiosk ran itself (a Codex turn without a `realtime_delegation` message) and whether the guest then got an order.

## Paid notice: a verified payment reaches the guest and Trend's context — 2026-11-05

- User request: when payment completes, the agent should know the order context and the customer should be told. Before: the screen's QR poll (`PaymentQr`, every 3 s) or the invoice worker could record a merchant-verified paid status, but Trend learned of it only if the voice itself called `kiosk_payment`, so it stayed silent and had no paid-order context for follow-up questions.
- Change, test-first (`tests/test_paid_notice.py`, 10 tests; 6 red before the change, the 4 others guard against extra notices): `Service._save_order` (the one place every merchant-verified paid status is written: QR poll, invoice worker, kiosk tools, checkout) calls `Service.paid_listeners` once per order when it first becomes paid, after the commit; a failing listener is logged and never fails the save. `InteractionHost` listens (thread-safe via its loop) and, for an order of the current guest only, shows the payment screen (`view: payment`) and starts a Codex turn (`claim_guard.paid_turn`) carrying the order context (lines, options, notes, total, takeaway/table, merchant order id) that asks Codex to confirm with `kiosk_payment` and say only 'Đơn đã được thanh toán.'. The confirming tool call is what backs the locked paid sentence, so the paid/unbacked-result guards are unchanged. If Codex refuses the turn, the voice gets a developer note with the same context that does not state paid. No notice when a voice `kiosk_payment`/`kiosk_checkout` result already reported that order as paid (the notice waits up to 20 s for such a call to finish), for another guest's order, after the session ended, or twice for one order. Counted in `audio_metrics.paid_notices`.
- Not run: real merchant settlement, live Codex/realtime speech of the host-started turn, or the browser. Fixtures only; no merchant order, payment action or printer job. Frontend unchanged (it already handles `view: payment`; `PaymentQr` shows the paid state). Needs an API restart to take effect.

## Paid reply worded naturally, not a fixed sentence — 2026-11-05

- User decision: "no hardcode 'Đơn đã được thanh toán.'". Both prompts (`INSTRUCTIONS`, `VOICE_INSTRUCTIONS`) and the paid-notice Codex turn (`claim_guard.paid_turn`) now ask Trend to tell the guest warmly, in its own words and one or two short sentences, that the payment went through, optionally mentioning the order (at most two drink names, takeaway or table), without another order/QR. The QR sentence stays exact. CLAUDE.md, the handoff and `docs/evals/qr-checkout-flow.md` are updated.
- Because the wording is free, the unverified-paid guard (`claim_guard.PAID`) now also recognises "đã thanh toán thành công/rồi", "thanh toán xong/thành công rồi", "thanh toán thành công", "đã nhận (được) tiền/thanh toán"; QR instructions and payment questions are not matched (tests in `tests/test_claim_guard.py`). The rule is unchanged: a paid claim is stopped unless a kiosk tool result reported paid.
- Tests: `tests/test_voice_tone.py` now asserts the fixed paid sentence is absent from both prompts and the natural paid result is described; 87 related tests pass; Ruff clean. Not run with the real model or voice: whether real replies stay within the 1–2 sentence budget is not measured. Needs an API restart.

## Shortcut to hide/show the Settings button — 2026-11-05

- User request: a shortcut to hide/show the header Settings (gear) button. `Ctrl+Alt+S` (`⌘+⌥+S` on macOS) toggles it; matched by physical key (`KeyS`) so the Vietnamese IME or any layout works; held keys and AltGr typing are ignored. The choice is kept per browser in `localStorage` (`trendcoffee.settingsButton`, guarded when storage is unavailable); default is shown, so nothing changes until staff press it. Hidden means the button is not rendered (no tab stop).
- `frontend/src/settingsShortcut.ts` + `settingsShortcut.test.ts` (4 tests); `App.tsx` wiring. Frontend tests 58 pass, lint/format/typecheck clean; built into `trendcoffee/static`. Checked in Chromium against a fixture server: shown → hidden after the shortcut → still hidden after reload → shown again; Ctrl+S alone does nothing; the dialog still opens. Not checked on the physical kiosk keyboard.

## Settings → Kiosk: staff-tuned session start/end boundaries — 2026-11-05

- User request: tune kiosk boundary times from the Settings dialog. User chose the session-start and session-end groups, protected by the staff code and saved on the server.
- Before, fixed in code: presence 0.6 m and 2 s to open a session (`PresencePolicy`), 3 s away to end it, 120 s idle, 600 s maximum with a warning at 540 s (`InteractionHost._ticks`), and the screen's own 120 s idle reset / 90 s notice (`App.tsx`).
- Change: `trendcoffee/kiosk_timing.py` keeps `presence_distance_m` (0.3–2 m), `enter_seconds` (0.5–10), `leave_seconds` (1–30), `idle_seconds` (30–600), `session_limit_seconds` (120–3600) and `warning_seconds` (0–300, below the limit; 0 = no warning) in `kiosk-timing.json` next to the database (`.runtime/` by default), written atomically; an unreadable or out-of-range file falls back to the defaults (same as the old fixed values). `GET /api/kiosk/timing` is public (values, defaults, limits); `PUT /api/kiosk/timing` needs `Authorization: Bearer $TREND_STAFF_TOKEN` (503 `staff_disabled` without one, 403 `staff_forbidden`, 400 `invalid_kiosk_timing`). The host takes a guest's session limits when the session opens (`session_timing`) and applies presence limits only between guests (`apply_timing`, also after `end`), so a guest in a session keeps their limits. The warning text stays "Phiên trò chuyện còn một phút." at 60 s and states the seconds otherwise. The screen reads `idle_seconds` for each new guest and shows its notice at three quarters of it (90 of 120 s as before).
- Settings dialog: new **Kiosk** section (`KioskTimingSettings.tsx`) with the two groups, range/default hints, inline validation (decimal comma accepted), staff code field (kept only while the dialog is open), Restore defaults and Save. The virtual keyboard now also opens for password fields so the staff code can be typed on the touch screen.
- Tests: `tests/test_kiosk_timing.py` (18), `frontend/src/kioskTiming.test.ts` (5); 449 backend tests pass (same 60 environment-only failures), frontend 63 pass, lint/format/typecheck clean, built. Chromium against a fixture server: Save disabled until a change and a code; out-of-range value flagged; wrong code → "Mã nhân viên không đúng."; correct code saved 1.5 s / 90 s to the server; light, dark and 390 px layouts checked. Not checked with the real camera/Visual presence or a physical guest. Needs an API restart (and `TREND_STAFF_TOKEN` set) to use it.

## Shortcut to turn the on-screen keyboard off/on — 2026-11-05

- User request: a shortcut for the virtual keyboard (it opens on every text field and covers the screen when testing with a physical keyboard). `Ctrl+Alt+K` (`⌘+⌥+K`) turns the on-screen keyboard off or on; turning it off also closes an open one; physical typing is unaffected. Kept per browser (`trendcoffee.virtualKeyboard`); default on, so the touch kiosk is unchanged until staff press it. `Esc` still closes an open keyboard once.
- `settingsShortcut.ts` became `kioskShortcuts.ts` (Ctrl+Alt+S Settings button, Ctrl+Alt+K keyboard; same modifier, AltGr and key-repeat rules; the saved Settings choice keeps its storage key). Frontend tests 64 pass, lint/format/typecheck clean, built. Chromium against a fixture server: keyboard opens on focus → closes on Ctrl+Alt+K → stays off on focus and after reload while typing still works → opens again after a second Ctrl+Alt+K; Settings button unaffected. Not checked on the physical kiosk.

## Session warnings spoken by Trend instead of shown on screen — 2026-11-05

- User request: remove the on-screen "Phiên sẽ kết thúc sau 30 giây không tương tác. / Tiếp tục chọn món" notice and have the agent (Codex voice) say the warning instead, including the warning before the session limit.
- Before: the screen showed that notice at 90 of 120 s only for guests without a voice session; in a voice session the server ended an idle guest with no warning, and the time-limit warning was a status text line ("Phiên trò chuyện còn một phút.").
- Change, test-first where possible (`tests/test_spoken_warnings.py`, 6 tests; `tests/test_kiosk_timing.py` updated): in a voice session the host starts a Codex turn (`trendcoffee/session_notices.py`) a quarter of `idle_seconds` before an idle end (30 of 120 s) and `warning_seconds` before the time limit; the turn asks Trend for one short, warm sentence in its own words and forbids tools/cart/order changes. Trend's own speech still counts as kiosk activity, so the host now tracks the guest's own activity separately (`guest_activity_at`: speech transcript, accepted audio, screen touch, cart change): after an idle warning the session ends at the promised time unless the guest acts, and a returning guest clears the warning (a new idle stretch warns again). The screen shows the warning text only if Trend cannot say it (no conversation thread, or Codex refuses the turn). Counted in `audio_metrics.spoken_warnings`. The per-tick logic moved to `InteractionHost._session_step`.
- Screen: the idle notice, its state, CSS and translations are removed; a guest without a voice session is still reset after `idle_seconds`, now without a countdown (nothing can speak for them). `tests/test_browser.py` updated accordingly (cannot run here: needs `data/trendcoffee-public.json`); the same flow was checked in Chromium against a fixture server: no notice at 91 s, cart kept, reset at 121 s.
- 455 backend tests pass (same 60 environment-only failures), frontend 63 pass, lint/format/typecheck clean, built. Not run with the real model/voice: whether Trend speaks the warning promptly (a Codex turn takes seconds) and how it words it are not measured. Needs an API restart.

## Trend's reply cut after a few words — 2026-11-05

- User: Trend's speech sometimes stops after the first few words although the transcript is complete, e.g. "Bạn quét Q.." (Bạn quét QR trên màn hình để thanh toán nhé.) and "Dạ, k…" (Dạ, kem tươi mang đi, để mình đặt luôn … Bạn chờ mình chút nha.). The kiosk machine was not reachable from this session, so no live log was read.
- Only two places stop a reply that is already playing: the claim guard (`stop_unbacked_result` → `speaker.interrupt()`, logged "Trend stated a result with no kiosk tool behind it") and a native guest turn (`userTurn/started` → `speaker.interrupt()`, `fusion_recent` `{turn: user, dropped_ms}`).
- "Bạn quét Q..": reproduced a false positive of the claim guard. A guest remark of three or more words while Codex was still working ("Ừ nhanh nha bạn ơi") moved `request_at` past the tool, so the real QR relay matched "quét QR" without backing and was cut at those words (end-to-end test logged the warning and interrupted the speaker). Fix, test-first (`tests/test_claim_guard.py` +5, 4 red): a tool result not yet read out still backs a result reply for `RELAY_WINDOW` = 15 s after the tool, until a reply with result wording has finished after it (`ClaimGuard.done`, called on Trend's finished transcript). Repeating an already read-out result for a new request is still caught; an old unread tool result does not cover a claim 31 s later; all earlier guard tests pass.
- "Dạ, k…" contains no result wording, so it was not the guard; the only other cause is a guest turn interrupting Trend: the guest continuing to speak after a pause, or Trend's own voice coming back through the microphone (the unmeasured hypothesis of 2026-11-03). Added, test-first: such a cut is logged ("A guest turn cut Trend off at HH:MM:SS; N ms of the reply dropped", numbers only) and counted in `audio_metrics.reply_cuts` (`count`, `dropped_ms`). Next step: after a cut, read `fusion_recent` around that time — heard rows (`heard: true`) while the guest was silent point to echo.
- 461 backend tests pass (same 60 environment-only failures); focused voice suites stable over 5 runs; Ruff clean. Not checked with the real voice. Needs an API restart.
- Follow-up (review): the cut log first relied on the server speaker's buffer, which exists only for Pet; in Avatar 3D (browser player, the default character) every cut went unlogged. A cut is now any guest turn that starts while `playing` is true (server speaker or browser playback report) or the server speaker still holds audio. `reply_cuts` = `{count, dropped_ms, unmeasured}`; `unmeasured` counts cuts whose lost duration is unknown (browser player). Test: `test_a_cut_while_the_browser_plays_trend_is_counted_without_a_duration` (red before).

## A quiet guest is asked, not sent away — 2026-11-05

- User decision: "Không tương tác" must not end the session ("kiosk kết thúc phiên và chờ khách tiếp theo" is unwanted); Trend should only ask the guest, depending on the session (e.g. what to buy, whether to pay, add to the cart).
- Change: `idle_seconds` (default 120 s) now triggers one spoken question per quiet stretch (`idle_nudge`), never an end and no "session will end" warning. The host describes where the guest is (`InteractionHost.guest_situation` → `session_notices.guest_situation`): nothing chosen / cart not ordered (lines, takeaway or table) / order awaiting payment / paid, and the Codex turn (`idle_nudge_turn`) asks for one short question in Trend's own words that fits it: what they would like (may show the menu), pay now or add more (may show the cart with `kiosk_cart` view before naming it), refresh with `kiosk_payment` then the exact QR sentence or a paid answer, or anything else. It must never add, change, remove or order anything unless the guest asks. The guest's own activity (speech, touch, cart) starts a new quiet stretch; Trend's own speech does not, so a guest who stays quiet is asked once. Sessions still end when the guest leaves the camera (`leave_seconds`) or at `session_limit_seconds` (warning still spoken). The screen shows "Bạn cần Trend giúp gì thêm không?" only if Trend cannot speak. Counted in `audio_metrics.idle_nudges`.
- Settings → Kiosk: the field moved to a new group "Nhắc khách", renamed "Hỏi khách sau khi im lặng", with a one-line explanation. A guest without a voice session is still reset by the screen after `idle_seconds` (nobody can ask them).
- Tests: `tests/test_spoken_warnings.py` rewritten (7), `tests/test_kiosk_timing.py` updated; related suites stable over 3 runs; frontend 67 pass, lint/format/typecheck clean, built; Settings checked in Chromium. Not run with the real voice: the wording and timing of Trend's question are not measured. Needs an API restart.

## A guest who stays after a session ended is welcomed again — 2026-11-05

- Report: after a session ended for idleness, the guest still standing at the kiosk got no new session. Cause: an idle/time-limit/next-guest end blocks the guest's track until a camera frame shows nobody near; a guest who stays is blocked indefinitely. Evidence: after an API restart (which clears the block) a session opened at once for the same guest at 0.35 m.
- User decision: a guest who stays is a new customer, with no pause (a first 10 s pause was rejected by the user). `BLOCK_SECONDS` is 0: after the end, the usual `enter_seconds` near opens a new session. A positive value would hold the same track back for that long. Watch for the new greeting overlapping the farewell clip; not measured.
- `/api/kiosk/status` now has `presence`: the last camera decision (`stale` with age, `far`/`near` with distance and track, `blocked_same_guest` with seconds left, `enter`), counts per reason, and the blocked track. Tests: `tests/test_presence_diagnostics.py` (3). Not run with a real guest yet.

## Spoken warnings wait for Trend to finish — 2026-11-05

- Evidence (rollout 11:12:43, kiosk log): with `session_limit_seconds` set to 120 by staff, the time warning fired at 11:13:43 while Trend was saying "Dạ, hiểu rồi, mình sẽ bật nhanh ngay đầu câu."; the warning turn replaced it ("Dạ, kiosk sắp hết giờ rồi…") and the guest heard only "Dạ, hiểu rồi, mình sẽ…". No guest-turn cut was logged at that moment.
- The other reported loss ("Ừm, có lần một bạn ghé…", cut 11:13:26, 440 ms dropped) was a guest turn: Fusion ACCEPT with the guest's face locked and mouth moving, then the guest's own sentence ("Câu sau bạn trả lời cho tôi phải có một chữ ừm…"). Not echo; unchanged by design (the guest may interrupt Trend).
- Change, test-first (`tests/test_spoken_warnings.py` +2, red before): `_warn` waits, at most `WARNING_WAIT` (12 s), until `playing` is false before starting the warning turn, and drops it if the session ended meanwhile. Not run with the real voice.

## Visual console: device camera 12–16 fps; no target lock or audio monitor — 2026-11-05

- User screenshots of the Visual console (`Visual/presentation/console`, port 9876) in device-camera (remote) mode: frame rate 12–16 against 29–30 with the kiosk's C920; "TARGET LOCKED" never shown; "Giám sát âm thanh" flat.
- Target lock / audio monitor, root cause: the console's voice half is fed by `voice_monitor_start` + `voice_telemetry` from `Audio`'s `SpeakerConsole`, which `SpeakerStream` creates only when it is given `speaker_settings`; `av_worker.begin` passed none, so no session ever published (no publisher of those commands exists elsewhere in OpenAIMK). Fix, test-first (`tests/test_av_worker_ready.py`, red then green, Audio modules faked because this environment has no numpy/torch): the worker passes the same `settings` the `FusionGate` uses. The console now receives lock state, target face, verdicts, ASD use and audio levels/waveform (128 level values, never PCM), at most 10 Hz, over the existing loopback Visual socket. Its live tuning of fusion thresholds applies to the current session only; "Save" reports "No settings store configured" (no store passed); the target-audio listen switch stays unavailable.
- FPS: the console's "Tốc độ khung hình" counts frames entering Visual. Device mode was capped at 15 fps in four places (getUserMedia ideal 15 / max 20, WebRTC `maxFramerate` 15, `camera_rtc.MAX_FPS` 15, socket JPEG pump 15), so jitter showed as 12–16; face tracking/ASD analyse at most 15 Hz (`track_max_fps`) for both sources. Change: the device camera's WebRTC path now asks for and forwards up to 30 fps (getUserMedia ideal/max 30, `maxFramerate` 30 with 2 Mbit/s, `MAX_FPS` 30), like the C920, so the 15 Hz analysis always has a fresh frame. The socket JPEG fallback (used until WebRTC connects) stays at 15 fps. Tests: `tests/test_camera_rtc.py` (+1: a 30 fps camera keeps every frame; the cap test now 60 → 30 fps), `cameraRtc.test.ts`; `tests/test_device_camera_browser.py` 3 pass in local Chromium (fake camera).
- 470 backend tests pass (same 60 environment-only failures), frontend 67, lint/format/typecheck clean, rebuilt from current main. Not measured on the user's device or a live Visual console. Needs an API restart (av_worker restarts with it) and a browser reload.

## Device camera that stops sending is reconnected — 2026-11-05

- Evidence (kiosk status, 14:15–14:25): after the kiosk page reconnected at 14:15:26 the API's device-camera WebRTC peer received 34 frames, then none for over ten minutes, while the kiosk socket stayed open (`send_errors` 0, Visual alive). Presence went `stale`, so no guest could start a session; the Visual console showed 0 fps with the last frame frozen. The same pattern (camera and microphone stopped, socket open) happened at 13:44 at 15 fps, so it predates the 30 fps change. The page sends socket JPEGs only while the WebRTC camera is not `connected`, so a connected-but-silent camera was never replaced. Where the video stopped (browser sender or aiortc receiver) is not yet known.
- Change, test-first (`tests/test_camera_rtc.py` +5, red before): `CameraPeer.stalled(now)` is true when the connection's video gave no frame for `STALL_SECONDS` (2 s), including a track that ended. After the first restart the track ended again after 34 frames (no hang), so ended tracks are replaced too; `CameraPeer` now logs `Device camera track ended … (connection <state>)` and every connection state change to failed/closed/disconnected, with `camera_transport.state` and `track_ended`. The host checks it every tick (`_watch_camera`): it logs `Device camera stalled at HH:MM:SS after N frames (browser sent M); reconnecting it`, counts `audio_metrics.camera_stalls`, closes the peer and emits `camera_reset`. The page closes its camera connection (socket JPEGs carry the camera meanwhile) and offers a new one after 1 s.
- Diagnosis: the page sends the browser's own sender numbers every 2 s (`camera_stats`, outbound-rtp video: `framesSent`, `framesEncoded`, `framesPerSecond`, NACK/PLI counts, `qualityLimitationReason`), kept as `audio_metrics.browser_camera`; the stall log includes `framesSent`, so the next stall shows whether the browser kept sending.
- Not yet observed on the user's device.
