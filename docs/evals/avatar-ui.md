# Avatar assistant UI verification — 2026-10-17

Delivered: a branded virtual barista portrait, combined voice conversation/waveform/controls, horizontal menu categories and responsive assistant/menu/cart layout. Existing chat shortcut opens the chat tab, including after the customer previously viewed another support tab.

## Evidence

- Frontend: 14 tests passed. Phase regression covers connecting/listening/speaking/unavailable; conversation keeps both speakers and a six-turn bound; waveform responds to samples and stays quiet for silence. TypeScript/Vite build, oxlint and Prettier passed.
- Backend suite: 104 tests passed, including existing customer/staff browser workflows and merchant QR checks. Backend code was outside this UI change.
- Dedicated browser smoke: self-hosted WebP loaded, real Web Audio PCM playback drove speaking state and waveform, both speakers appeared in the log, touch/native-tool fixture shared cart, and the next guest received no old transcript. Fake devices and fixture events were used; this does not establish physical AV recognition.
- Screenshot/axe at 1440×1000, 768×1024, 375×812: zero console/page errors, zero axe violations, no horizontal overflow. Images under `.runtime/voice-browser/`. No approved screenshot baseline or field accessibility audit is claimed.
- Independent review: no Important/Critical issues. End/disarm controls reachable at additional 600px-height layouts; voice-disabled fallback checked separately.
- Runtime image: approximately 138 KB with transparency, served locally. Waveform updates only its own component every 80 ms while listening/speaking. No field p95 latency measurement is inferred.
- The managed production stack remains stopped. No live merchant order, payment or customer device capture occurred.

## Self-evaluation

| Axis | Score | Evidence / next improvement |
|---|---:|---|
| Accuracy | 4 | PCM-driven speaking/waveform and fixture guest reset verified; portrait is explicitly static without lip-sync. |
| Completeness | 4 | Avatar, conversation, waveform, controls and layout delivered; true facial animation would require a separate renderer/model. |
| Clarity | 4 | “TRỢ LÝ AI”, real status labels and device state distinguish the virtual assistant and active capture. |
| Actionability | 4 | Production assets built; preview screenshots and start command available. Hardware acceptance still needed at the kiosk. |
| Conciseness | 4 | One assistant component and small audio/transcript helpers; existing chat and checkout flows reused. |

Overall: 4.0/5. Highest-impact follow-up: review touch readability and real acoustics at the intended physical kiosk size. Self-check: the user can inspect the shipped layout and see exactly which behavior was tested.
