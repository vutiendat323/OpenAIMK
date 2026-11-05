# Consistent kiosk voice — 2026-10-24

## Behavior

The selected native Codex v3 voice now supplies the greeting, conversation and
farewell. The host captures `session_voice` at guest start. A preference change
during an active guest preserves that guest's conversation and farewell, and the
next guest receives the new voice beginning with their greeting.

Boundary recordings are loaded by `(kind, voice)` from the built static directory.
Only native voices with both recordings are selectable. The default has separate
clips rendered without a voice override. Cached playback remains independent of
native connection readiness and cleanup.

## Native preparation

`scripts/prepare_voice_clips.py` uses isolated native threads with no business
tools. The two fixed source WAVs are the synthetic input to an exact-repeat voice
prompt. It never opens a real microphone. A Maple probe returned the intended
Vietnamese greeting with 48 kHz mono PCM (`output/boundary-native-probe.json`).
Native text append requests produced no speech on this installed WebRTC path;
the supported synthetic-audio path was used instead.

Prepared WAVs live in `frontend/public/voice/<voice>/`, then Vite copies them into
`trendcoffee/static/voice/`. The manifest records the native CLI version, voice ID,
protocol version, expected and actual transcript, PCM SHA-256 and duration.
Rendering rejects missing, incomplete or extra speech, silent audio, inconsistent
formats and audio exceeding the browser's 600,000-character base64 chunk limit.
Writes use temporary files followed by atomic replacement.

Preparation command:

```bash
PYTHONPATH=. .venv/bin/python scripts/prepare_voice_clips.py
npm --prefix frontend run build
```

## Verification record

- Three new routing regressions failed before implementation, then passed:
  distinct per-voice PCM; captured farewell after a preference change; incomplete
  voice assets excluded from selection. Full voice settings module: 12 passed.
- Six built-browser boundary cases passed. They verify the actual announcement
  voice IDs and PCM bytes for Maple greeting, Maple farewell after choosing Rio,
  and Rio greeting for the next guest, alongside audible playback waveform and
  slow/failed native connection handling.
- Initial backend/browser run: 231 passed, with asset completeness deselected
  while the recordings were being prepared. Frontend: 20 passed.
- Independent review found a generation/playback size mismatch. Two regressions
  reproduced it before the fix; new and reusable recordings now share the actual
  browser limit. Seven capture/reuse validation tests passed after the fix.
- Final full backend/browser suite: **234 passed in 56.38 seconds**; frontend:
  **20 passed**. TypeScript/Vite production build and targeted Ruff lint/format
  checks passed. Re-running preparation for the already verified Maple clips
  completed without regenerating them.
- **48 clips** were prepared: both sentences for **23 accessible native voices**
  and the unoverridden default. All source and built WAVs match byte-for-byte;
  longest recording is 3.32 seconds. The all-assets regression checks sentence,
  voice, format, duration, playback limit and PCM hash for every prepared clip.
- Porto and Selva are advertised by CLI 0.163.0 but three rendering attempts each
  failed. An isolated startup probe confirmed both return `forbidden` with
  `Voice session access denied.` (`output/boundary-voice-access.json`). They are
  listed under `unavailable` in the manifest and excluded from the web selector.
- The owned API was restarted only after confirming no active guest. API PID
  76236 and unchanged Visual PID 8089 were listening on 8080/9877 at verification;
  health was `ok`, native preparation was ready, and the live voice endpoint
  returned exactly 23 choices including Maple and excluding Porto/Selva.
- A fresh deployed browser confirmed Maple default and persistence of Maple,
  Miko and an explicit Codex default after reload. Both deployed Maple WAV URLs
  returned the exact manifest PCM hashes. No real microphone permission,
  merchant order, payment or printer operation was used for this verification.

## Limits

Voice identity is verified by the native request's voice ID and separate per-voice
recordings; Vietnamese sentence content is checked against the native transcript.
This does not measure physical speaker/microphone acoustics or guarantee identical
intonation between a cached sentence and live conversational speech. Some native
handshakes required retries during offline preparation; boundary playback itself
does not make those network requests. A new upstream voice needs both recordings
prepared and an API restart after the build before it appears in the selector.

## Execution record

The workspace is not an initialized Git checkout, so changes and evidence remain
in the shared workspace. The implementation preserves the existing native model,
Fusion checks, business tools and guest lifecycle. The renderer follows the
existing frontend-public-to-static build path; first-run generated files are
copied to the public source directory before the final build.

Ruling: prepare all accessible voices, and hide the two upstream-denied choices
rather than replacing them with a different voice. The user asked for consistency
for a selected voice; offering a choice that cannot connect would violate that.
This leaves 23 named choices until access to Porto/Selva becomes available and
their clips can be prepared.

## Self-evaluation

| Axis | Score | Evidence |
| --- | --- | --- |
| Accuracy | 4/5 | Native voice IDs, transcript and PCM integrity verified; physical acoustic comparison was not performed. |
| Completeness | 4/5 | All 23 accessible choices and default cover all speech stages; Porto/Selva are denied upstream and explicitly excluded. |
| Clarity | 5/5 | One selection controls all speech stages, with changes deferred consistently to the next guest. |
| Actionability | 5/5 | Built, deployed while idle, and verified on the running service; existing pages need a reload. |
| Conciseness | 4/5 | Runtime change is small; 48 assets and an offline preparation script are needed to retain immediate, consistent boundary playback. |

Overall **4.4/5**. Next improvements: compare the physical speaker output with
live conversation for the preferred voice, and retry the two denied voices only
after upstream access changes. Self-check: the user can verify all three speech
stages by reloading the kiosk and choosing a voice.
