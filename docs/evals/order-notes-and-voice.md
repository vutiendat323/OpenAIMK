# Item/order notes and speech output — 2026-10-20

Implemented both requests: compact per-item and whole-order note fields, touch/voice/MCP support, merchant delivery, and a measured fix for distortion in streamed assistant speech. Production stack remains stopped; the built UI and service code load on next start.

## Notes

- `lines[].note` (300 characters) and `order_note` (1000) validate/normalize on the server and bind to idempotent checkout payloads. Legacy quotes without notes still submit. Client signatures also normalize whitespace, so a lost-response retry with trailing spaces returns the same order.
- Same SKU/options with different notes remain separate. Editing preserves row order and key; a unique item-ID target still works, while ambiguous rows require a specific line. Notes reset after checkout, cart clear and guest change.
- Inline local drafts keep fast typing intact while authority responses are delayed. Browser smoke simulated 60 ms state echoes, typed accented notes with spaces one character at a time, then checked the actual submitted order. Voice checkout cleared the whole-order field even while it retained focus. No popup or extra confirmation step was added.
- Merchant request tests inspect item `note` fields and order description, including exact description verification when branch data is absent. No actual merchant order or payment was created.
- Actual native Luna medium processed two coffees: one “ít đá”, one “không đá”, plus “gọi tên Linh khi xong”. It retained both distinct line notes, the whole-order note, total 80,000đ and one fixture-local order. [Captured model/tool result](../../output/native-notes-smoke.json).

## Speech

The native bridge previously sent separate 24 kHz buffers into a 48 kHz browser context, producing a discontinuity at every per-buffer resampling boundary. A regression rendering actual NativePeer output through the real VoicePlayer in Chromium measured 0.03706 full-scale error before the fix and passed afterward. Output and browser clock now both use 48 kHz; microphone processing remains 16 kHz. No new buffering or output gain reduction was added.

Actual native assistant output returned 88 mono 48 kHz packets, 1.76 seconds of speech. Browser rendering of these packets matched the continuous reference within 1.67e-16 with peak 0.299 full scale. [Detailed audio evidence](../../output/voice-output-48k-fix.md). Physical speaker listening is still unverified; this establishes the digital fix, not an all-device acoustic guarantee.

## Final checks

- Full backend/browser suite: **188 passed**, 38.29 seconds.
- Frontend: **17 passed**; TypeScript/production build, oxlint and Prettier passed.
- Ruff check/format passed. No new frontend dependencies.
- Separate browser smoke: zero console/page errors, axe violations or overflow at 1440/768/375, including shared voice/touch cart, semantic menu selection, note typing, order submission, note clearing and guest isolation. Screenshot: `.runtime/voice-browser/notes-voice-editing.png`.

## Self-evaluation

| Axis | Score | Evidence / improvement |
|---|---:|---|
| Accuracy | 4/5 | Real model, merchant mock payload and actual Chromium audio rendering verify behavior; listen at the physical kiosk to confirm the reported symptom is fully absent. |
| Completeness | 5/5 | Both requested features cover UI, voice, backend and tests; notes survive merchant submission without adding a confirmation step. |
| Clarity | 5/5 | API fields and audio root cause are documented; field-test limits are explicit. |
| Actionability | 4/5 | Built assets are ready, but the intentionally stopped stack needs starting and the browser/MCP needs reload. |
| Conciseness | 5/5 | Two compact note inputs; audio correction changes the existing rate rather than adding a playback subsystem. |

Overall: **4.6/5**. Highest-impact follow-up: listen to the next real kiosk reply and inspect notes on a genuine merchant order. Would the user agree? The requested controls and semantic note handling are verified; acoustic field confirmation remains separate.
