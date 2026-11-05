# Customer short speech: diagnosis and fix — 2026-11-03

The customer must not speak for two seconds to obtain a transcript or response.
The suggested two-second pause was only a diagnostic way to distinguish speech
capture from end-of-turn handling. It is not an application requirement.

## Confirmed failure and change

The repeatable native probe is
`PYTHONPATH=. .venv/bin/python output/audio-diagnosis/replay-short-native.py before`.
Its original saved result is `output/audio-diagnosis/short-native-before.json`:
a synthesized Vietnamese greeting lasting 0.737 seconds reached native ASR as
“Xin chào bạn”, but no assistant audio followed in the observation window.
Changing only the native prompt still produced the same failure
(`short-native-after.json`).

Two instruction surfaces disagreed: `VOICE_INSTRUCTIONS` handled only actionable
requests, while the role-bearing WebRTC startup item told the voice to listen
and not greet again. The fix defines behavior for every intelligible completed
turn, including a greeting, yes/no and a short display command. A customer greeting
gets a short response; yes/no uses context or asks clarification; neither authorizes
an invented order. An actionable command must invoke the Codex delegation tool;
a spoken promise alone does not perform the action. Both native transports now
initialize their developer item with the same policy as their effective prompt.

| Synthetic input | Spoken duration | Result | End of speech → first output audio |
| --- | ---: | --- | ---: |
| Xin chào bạn | 0.737 s | Transcript and “Dạ, Trend đang nghe bạn.” | 2.191 s |
| Yes | 0.321 s | Transcript and context clarification; no business tool | 1.882 s |
| Open menu | 0.716 s | Transcript, acknowledgement, actual `kiosk_menu` call | 2.111 s |

The menu tool was called 7.813 seconds after speech ended. This is not an immediate
screen-action result or a 1–2-second completion SLA. The earlier candidate only
acknowledged the command and never called the tool in 25 seconds
(`short-native-open-menu-ack-only.json`); the final prompt explicitly requires
same-turn delegation. The probe verifies the actual call, not the timing of a
final useful spoken result. Final artifacts are `short-native-final-greeting.json`,
`short-native-yes.json`, and `short-native-open-menu.json`.

These are isolated calls with synthetic input, a disposable tool response and no
merchant order, payment or printer action. The greeting replays an existing
synthetic Fusion-approved trace; Yes/Open menu test the native leg after Fusion,
not physical A/V ownership. No customer microphone recording was made.

The timing probes above used the prior Fast/priority setting. The user then
disabled Fast; those timings must not be treated as measurements of normal-tier
Luna. A real thread-start check now resolves `gpt-6-luna`, `reasoningEffort=medium`,
`serviceTier=null`, with no priority field requested. See the latest PROGRESS entry.

## Audio/Fusion boundaries and remaining limits

Path: browser PCM16/16 kHz/80 ms → `InteractionHost.microphone` → worker IPC →
`Audio.SpeakerStream` (Sortformer, active-speaker evidence and owner lock) →
`FusionPreroll`/approved PCM → native WebRTC → transcript/assistant PCM → browser.

- `voiceprint_min_secs = 2.0` is voiceprint enrollment/readiness. It is not a
  minimum customer-turn length. The existing owner can speak before that
  voiceprint is ready.
- `lock_asd_frames = 6` requires six same-face/solo-speaker ASD-confirmed rows for
  the initial owner lock. Each row is 80 ms; this is model evidence, not a
  guaranteed 480-ms utterance threshold. The ASD input window and classifier
  confidence also matter. Once locked, no new six-row lock is required per turn.
- A deterministic test of the real Fusion gate and preroll preserves all
  160/320/480/720 ms confirmed-owner PCM even with `voiceprint_ready=false`.
  With a cold lock and only two/four qualifying rows, 160/320 ms remains blocked;
  six/nine qualifying rows lock and replay the approved prefix. See
  `output/audio-diagnosis/short-gate-check.json`. This evidence uses synthetic
  face/ASD rows, not a physical recognition score. The initial-lock policy was
  deliberately not weakened. Very short/uncertain first words are still a limit.
- Before connection/readiness and the greeting, current host code does not send
  customer PCM to native. A turn spoken entirely during cold connection can be
  lost. The prompt fix does not change that startup boundary.
- Streaming microphone capture is continuous. Sortformer runs 240-ms chunks;
  the 700-ms mask setting is a missing-evidence deadline, with early release for
  covered evidence. Native controls turn ending. There is no fixed two-second
  application sleep before every turn. Observed response latency remains separate.

## Other observed evidence

- API, Visual and avatar were running. The local Audio models were already loaded,
  so the reproduced no-reply case was not a model-download/loading failure.
- The earlier live session had 359 microphone packets, normal RMS, 27 kept Fusion
  packets and 427 native output packets. This proves that some speech/output
  passed, not that every customer phrase was recognized.
- The current API log contained one `av_check` failure:
  `RuntimeError: fusion_session_unavailable`. During a later 180-second read-only
  watch there was no active guest; 70 samples showed a live face without a valid
  distance. A live in-range anchor is required for readiness. These observations
  were not simultaneous with that failure, so they do not establish its exact
  camera cause. Numeric-only samples: `output/audio-diagnosis/live-status.jsonl`.
- A separate real-IPC probe with a 2.5-second temporary readiness miss sent all
  38 microphone packets without error. A suspected IPC-backpressure explanation
  was not reproduced and no IPC/worker change was shipped.

## Verification and activation

- 55 focused tests passed: voice startup policy, AV transport, kiosk lifecycle,
  transcript streaming, native peer, preroll and Fusion identity. The startup
  regression failed before adding the aligned PCM startup item, then passed.
- Ruff lint/format passed for changed Python files.
- Independent read-only review found no important regression. Configuration
  alignment tests are not evidence of model semantics; the live probes supply
  that narrower evidence.
- Restarted owned API only after checking both `session_active=false` and
  `microphone_receiving=false`, preserving the original environment including
  `TREND_MERCHANT_ENABLED=1`. API 449722 → 471893. Visual 449662 and avatar 449682
  remained running. `/health`: ok, merchant_api, live_pos_connected=true.
- No physical customer mic/camera/speaker acceptance is claimed. No Audio
  thresholds, native model/voice defaults or Fusion ownership checks were changed.

## Self-evaluation

Applied `agent-self-evaluation`: accuracy 4/5 (reproduced no-reply before and
verified short replies after; synthetic versus physical scope is explicit),
completeness 3/5 (short-response policy fixed, but cold first-word ownership,
startup-word loss and precise historical A/V failure remain open), clarity 4/5
(separates turn length, enrollment and response latency), actionability 4/5
(repeatable probes and active API), conciseness 4/5 (one production file and one
regression file). Overall 3.8/5. The completeness gap requires real cold-start
short-utterance A/V measurement before changing initial-lock or startup buffering;
it cannot be fixed responsibly by merely lowering a threshold. Would the user
agree: the reported short-reply failure is fixed, while universal first-word
recognition and immediate response are not established.
