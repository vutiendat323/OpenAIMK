# Immediate microphone feedback — 2026-10-24

## Diagnosis and change

The reported sequence showed an active conversation remaining visually idle until
1–3 seconds of customer speech. Two presentation conditions waited for Fusion's
speaker lock: `assistantPhase` required `active && locked`, and `audioLevels`
returned zero until that lock. The browser already captures and sends 80 ms PCM
packets during an active session, so the display hid ongoing microphone activity.

`assistantState.ts` now reports listening when an active native session is ready
(`state === listening`). `useKioskVoice.ts` reads the local microphone analyser
throughout an active session. Playback still uses the output analyser; connecting,
unavailable, disarmed and ended presentation retains its existing behavior.
Fusion approval, speaker ownership, native audio routing, models and business
authority are unchanged. Local amplitude never creates a transcript or an order.

## Verification

- Before the fix, the new state regression and actual built-browser regression
  both failed: expected listening, received waiting while unlocked.
- After the fix, the Chromium fixture measured microphone waveform feedback in
  **70.8 ms**, below its 250 ms budget, while Fusion remained unlocked.
- The same test verifies quiet input remains flat, 80 ms PCM reaches the backend,
  no user text/order is invented, native partial transcript deltas update one
  bubble before turn completion, and disarming clears text and wave activity.
- Full backend/browser suite: **235 passed in 61.33 seconds**. Frontend: **21 passed**.
  TypeScript/Vite production build, oxlint, Prettier, root Ruff lint and format passed.
- Screenshot: [microphone before speaker lock](../../output/microphone-feedback-before-lock.png).
  Measurement XML: `/tmp/openai-microphone-suite.xml` (temporary local artifact).

Reproduce from the root after building the frontend:

```bash
.venv/bin/python -B -m pytest tests/test_microphone_feedback_browser.py -q -p no:cacheprovider
npm --prefix frontend test
```

## Limits and runtime

This corrects delayed **visual microphone feedback**. It does not establish that
physical speech recognition or model responses are now immediate. Real Vietnamese
microphone → Fusion → native transcript timing still needs an end-to-end trace;
Fusion's identity/evidence checks and upstream recognition latency still apply.
The browser test uses an oscillator, an isolated database and fixture native events,
with no real microphone, external order, payment or printer action.

The built static frontend is updated. The owned launcher status, checked outside
the sandbox, reported API 8080 and Visual 9877 not managed / not ready. No services
were started or restarted; deployed behavior has not been verified. When the kiosk
is next started, reload the page to load the new bundle.

## Self-evaluation

| Axis | Score | Evidence / remaining improvement |
| --- | --- | --- |
| Accuracy | 4/5 | Red/green state and browser regressions; measured local feedback, not physical recognition. |
| Completeness | 3/5 | Visual delay corrected; physical transcript/answer delay is still unmeasured and unresolved. |
| Clarity | 4/5 | Distinguishes microphone capture from speaker approval and native transcription. |
| Actionability | 4/5 | Built artifact, reproduction and screenshot supplied; runtime is stopped. |
| Conciseness | 4/5 | Two production conditions changed; focused regressions cover the visible behavior. |

Overall **3.8/5**. Next improvements, by impact: trace physical onset through
Fusion/native transcript; verify the rebuilt page in the intended running kiosk.
Self-check: this addresses the visible idle period without claiming the separate
physical recognition/answer latency is fixed.
