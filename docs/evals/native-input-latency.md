# Native transcript and spoken-response latency — 2026-10-24

## Outcome

Corrected a real input-media queue defect, independently reviewed and deployed.
The broader request for immediate native transcription/replies is **not yet met**.
The prior UI-only feedback change does not establish native latency improvement.

`FilteredTrack.recv()` already generates silence while no approved audio is queued.
Fusion releases initial masked packets in batches as evidence becomes available.
Queuing those zero packets made native wait through silence it had already heard
before receiving the first approved words. `push()` now ignores zero packets only
until the first nonzero approved packet. All later speech and pauses retain their
samples and duration. Fusion's six-row lock, freshness checks, speaker ownership,
selected voice and the backing model remain unchanged.

## Measurements

The input was synthetic Vietnamese: “Xin chào bạn. Cho mình xem thực đơn cà phê.”
Real Sortformer processed it; face/ASD evidence was a timed fixture, not a physical
camera. The same resulting PCM packet timeline was replayed through actual
FilteredTrack media frames and real native Juniper/Luna medium priority sessions.
The before comparison used the original push behavior in an isolated probe only.

Deterministic media-clock replay: first approved nonzero PCM sent at **1.200 s →
0.800 s** from input onset: **400 ms** removed. The real native runs independently
observed about **1.165 s → 0.762 s** to the first outgoing voiced media frame.
This measurement concerns actual PCM transmission, not waveform presentation.

| Measurement | Original queue | Fixed queue |
| --- | --- | --- |
| First native transcript after speech onset, first pair | 2.825 s | 2.580 s |
| First native audio after speech end, first pair | 2.224 s | 2.294 s |
| First useful result audio after speech end, first pair | 8.803 s | 6.224 s |
| Repeat: first transcript after speech onset | 3.955 s | 2.596 s |
| Repeat: first audio after speech end | 3.205 s | 2.490 s |

These small live samples are variable, not a percentile or causal proof of faster
model replies. The repeat-after run overlapped startup of the deployed kiosk's
silent preparation. Only the deterministic 400 ms queue correction is isolated.
A direct native probe without Fusion already needed about **1.35 s** to its first
transcript and **2.20 s** from speech end to first audio. The observed native processing
delay is separate from the fixed transport delay; physical acoustics are untested.

Evidence: `output/native-media-replay.json`, `output/fusion-latency-packets.json`,
`output/pipeline-before.json`, `output/pipeline-after.json`, and repeat files.
Summary: `output/voice-latency-trials-20261024.json`. Synthetic source WAV:
`output/native-latency-synthetic-input.wav`. Local reproduction probes are in
`.runtime/fusion-input-latency-probe.py`, `.runtime/native-input-latency-probe.py`
and `.runtime/native-input-media-replay.py`.

## Authorized configuration/model trials

The user explicitly authorized trying other configurations/models after seeing
the measured remaining delay. Trials were isolated; no alternative is deployed.

- Luna `low`: first transcript 2.606 s; first audio 2.518 s after speech end;
  useful result 6.196 s. No clear advantage over the current medium samples.
- Voice model override `gpt-live-1`: first transcript 2.596 s; first audio 2.021 s
  after speech end in one run. Insufficient evidence for a reliable improvement.
- A voice-prompt variant following the current GPT-Live delegation structure had
  an unfavorable outlier: first transcript 18.046 s, first audio 16.584 s after
  input end. The cause of that outlier was not established; it was not shipped.
- Native V2 was rejected: `AVAS realtime calls require realtime v1 or v3`.
- Native V1 was rejected by the server: `AVAS requires OpenAI-Alpha: quicksilver=v2`.
  An isolated correction of that header still received an unsupported-architecture
  rejection. No proxy, header workaround or protocol downgrade was shipped.
- Installed CLI is 0.163.0; official 0.164.0 does not change the relevant core
  realtime implementation. No global CLI upgrade was performed.
- `OPENAI_API_KEY` is absent in this environment. No connected key-provisioning
  tool is available. A separate API trial was considered, but the user explicitly declined that route.
  Continue with ChatGPT/Codex native login; no API credential setup is pending.

References: [official model selection](https://learn.chatgpt.com/docs/model-selection),
[GPT-Live prompting](https://developers.openai.com/api/docs/guides/live-prompting),
and the [installed-version native implementation](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/core/src/realtime_conversation.rs).
These describe configuration/protocol behavior, not measured latency guarantees.

## Verification and deployment

The new regression failed on the original queue, then passed. It checks first-word
media immediately after a startup silence batch and exact preservation of the
subsequent 80 ms pause. Full root suite: **236 passed in 61.48 seconds**; root Ruff
lint and format passed. Independent final review found no material issue and ran
all 10 native-peer tests successfully. Experimental early-ASD routing was rejected
by review and reverted; Audio has no remaining diff.

The owned launcher started Visual PID 525059 and API PID 525098 from a stopped
state. Both ports 9877/8080 listen; health is `ok`, native preparation is ready.
`output/native-input-latency-runtime.json` records the passive check. No active
guest was interrupted and no probe issued a real merchant order/payment/print.
Actual customer microphone-to-speaker performance still needs field verification.

## Self-evaluation

| Axis | Score | Evidence / gap |
| --- | --- | --- |
| Accuracy | 4/5 | Sample-level media correction verified; cloud and physical limits distinguished. |
| Completeness | 2/5 | Real queue defect fixed, but immediate native transcript/reply target remains unmet. |
| Clarity | 4/5 | Media, transcript, acknowledgment and useful-result timings are separate. |
| Actionability | 4/5 | Queue fix is deployed; remaining work is constrained to native login. |
| Conciseness | 4/5 | Seven production lines; meaningful media regression and recorded experiments. |

Overall **3.6/5**. Next: investigate preserved input onset and supported native configuration under
the user's native-only constraint, then verify the actual microphone/speaker chain.
Self-check: the user should see this as a verified transport correction and an
unfinished broader latency request, not a claim that moving a UI indicator solved it.

## Native-only follow-up

The user ruled out a separate Realtime API route. No API key setup is pending;
all following probes used the existing Codex/ChatGPT login in isolated sessions.
No additional runtime configuration or Audio policy was deployed.

- A 737 ms synthetic “Xin chào bạn” utterance crossed the full six-row lock only
  near its end; native produced no transcript/reply in the 24-second observation.
  A known-fixture prototype restoring five initial packets **after** lock recovered
  “Xin chào bạn” partial text, but still no completed turn or reply. This establishes
  initial-word loss, not a complete latency fix.
- A social-response prompt with restored onset did elicit a spoken response, but
  first audio was 3.627 s after speech end; it did not meet the latency goal.
- Restoring onset in the longer menu request advanced first transcript from
  2.580 s to 1.998 s from onset in individual runs, but first audio moved from
  2.294 s to 2.753 s after speech end. Paced replay creates catch-up delay. No
  post-lock replay implementation was shipped as a faster-answer claim.
- Native appendAudio over the existing authenticated WebRTC sideband was rejected
  by the live session: `input_audio.append` is unsupported there. Successful local
  RPC acknowledgment alone did not establish delivery to the voice model.
- An 80 ms Sortformer chunk trial retained six-row locking but worsened the
  reference diarization error from 0.1378 to 0.1506 and dropped a realtime chunk.
  Its modest confirmation improvement was not adopted.
- gpt-5.6-luna/low: first audio 1.999 s and useful-result audio 8.632 s after
  speech end, with tool start 5.827 s after end. No clear overall improvement.
- Native `bemTags` final-answer routing: first audio 2.413 s, useful-result audio
  6.088 s after end; first transcript 2.614 s from onset. No clear improvement
  over the existing commentary routing in these variable live samples.

Independent review required any future onset preservation to retain the full
same-face/same-slot lock, complete sample provenance, stream/epoch freshness,
contiguous timing and bounded queues. An early one-row ASD route remains rejected.
The deployed behavior continues to be the verified 400 ms transport correction;
immediate transcript/reply behavior remains unresolved under the native-only
constraint. Further native changes require evidence of actual improvement.
