# Streaming voice continuity — 2026-10-21

The previous rate correction addressed packet resampling, but did not test timed delivery. This change addresses additional independently reproduced word loss and discontinuities.

## Red/green evidence

- `tests/test_native_peer.py`: an actual NativePeer receiving 100 PCM packets while its event sink is slow delivered only 64 with the previous queue. The corrected path awaits media delivery and retains all 100 packets, including a quiet opening during the native assistant turn.
- A FilteredTrack whose scheduler clock was 300 ms behind discarded approved speech and returned silence. It now re-anchors its clock without clearing the bounded pending/tail data.
- A separate regression rejects idle codec comfort noise. Merely accepting every nonzero sample would keep playback/echo suppression active during idle periods; the correction uses assistant turn state to preserve quiet phonemes while suppressing idle noise.
- `frontend/src/voiceAudio.test.ts` executes the actual playback processor: 80 ms buffering, ordered samples, starvation ramp, short tails, guest reset/old packet rejection, and a six-second maximum queue.
- `tests/test_voice_audio_browser.py` renders actual NativePeer packets through Chromium and compares split/continuous playback. Its additional live AudioContext test delivers timed packets, blocks the UI thread twice for 45 ms and compares the captured samples against a changing reference signal. No middle samples may be lost/reordered; only 3 ms start/end ramps differ.
- The UI initially exposed an initialization race while adding the playback worklet: the WebSocket could open before its auth handler was installed. Worklet setup now completes before constructing the socket. All greeting/camera boundary cases pass again.

## Implementation

Native output stays mono PCM16 at 48 kHz. Browser decoding transfers mono Float32 packets to a continuous AudioWorklet queue instead of scheduling a new AudioBufferSource per packet. The processor uses continuous interpolation for recordings at other rates and ramps at exhausted-buffer edges. It reports actual playback activity for the existing Fusion echo control. Session epochs discard late playback messages and pending old-guest samples. Microphone capture and speaker verification remain unchanged.

Native output audio no longer competes with transcript/control events in a lossy queue. Control overload now reports a connection error rather than silently dropping a transcript. The input clock correction preserves the existing eight-packet bound.

## Measured limits

Repeated native fixture probes, with synthesized customer speech and fixture-only menu tools, observed roughly **1.0–2.0 seconds** from input end to initial audio and **3.3–4.5 seconds** to the menu tool call. These are individual observations, not a percentile or an end-to-end camera/Fusion measurement. Some first speech was still filler despite the existing prompt. A shorter realtime prompt did not demonstrate improvement and was reverted.

Native decoded audio also showed variable delivery gaps, including hundreds of milliseconds, and occasional RTP timestamp gaps. The final fixture probe reported 493 received RTP packets and 7 lost packets, with a 333 ms maximum decoded-frame delivery gap; these observations confirm that loss also occurs upstream of browser playback. The playback processor can avoid an abrupt full-amplitude cut at starvation; it cannot reconstruct speech absent upstream or guarantee continuous output through arbitrary network stalls. The real-time browser regression deliberately covers a bounded, measured UI stall rather than claiming arbitrary jitter is solved.

The production API/Visual stack remains stopped. Built assets are ready for the next start. Physical speaker listening and real microphone → Fusion → native latency remain unverified. No real merchant order, payment or printer job was created.

## Final verification

- Backend/browser suite: **192 passed** (47.25 seconds).
- Frontend: **18 passed**; production build, TypeScript, oxlint and Prettier passed.
- Ruff check and format passed.
- Separate built-app smoke: zero browser errors and axe violations at 1440/768/375; mic, avatar/playback waveform, voice/touch cart, notes, checkout and guest isolation passed.
- Runtime status: API 8080 and Visual 9877 remain stopped.

## Self-evaluation

| Axis | Score | Evidence / improvement |
|---|---:|---|
| Accuracy | 4 | Independent red/green packet-loss and scheduler regressions, plus live Chromium capture; acoustic output remains unmeasured. |
| Completeness | 3 | Local clipping/loss and playback scheduling are corrected; native tool latency and upstream jitter remain. Measure the live kiosk before claiming the entire symptom is resolved. |
| Clarity | 4 | Reproduction, implementation and remaining timing limits are separated; numerical observations are not presented as an SLA. |
| Actionability | 4 | Built assets and regression commands are ready; the intentionally stopped kiosk has not loaded the new code. |
| Conciseness | 4 | One playback worklet replaces per-packet source scheduling; no new dependencies or customer UI controls. |

Overall: **3.8/5**. Highest-impact remaining check is the physical kiosk's full microphone/Fusion/native/speaker path. The user's reported latency is only partially addressed; claiming it fully fixed would exceed the evidence.
