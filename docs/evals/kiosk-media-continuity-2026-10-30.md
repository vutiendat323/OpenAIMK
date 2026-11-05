# Kiosk media continuity — 2026-10-30

User report: saturated RTX 3060, jerky mouth motion, changed lips/teeth and
interrupted speaker output. These are separate acceptance criteria. The changes
below improve scheduling and buffering; they do not establish anatomical fidelity.

## Implemented

- `voice-playback.js`: after an underrun within a 500 ms recovery window, refill
  up to 40 ms instead of repeating the initial 160–200 ms buffer / 240 ms tail
  deadline. Initial startup protection and explicit interruption epochs remain.
  Long silence restores the initial buffer. The test reproduces the extra wait
  before the fix and resumes a short PCM fragment within 50 ms after the fix.
- Ditto advertises video-only WebRTC. The browser negotiates no RTP audio for
  this engine; native PCM still goes straight to its existing AudioWorklet.
  Cold starts refresh capabilities when reconnecting after model warmup, rather
  than retaining stale audio negotiation. Other engines retain their previous
  negotiation. The server also supports
  legacy audio/video offers, and skips 48 kHz conversion and audio queues for
  video-only clients. A slow or disconnected avatar does not stop the speaker.
- Keep all 80 predicted poses, timestamp them using the 16 kHz sample count and
  Hubert's 80 ms right context, fuse overlapping windows and interpolate existing
  poses. Previously only the last pose survived each 200 ms update. No future
  speech is predicted. This is an arrival-based clock with a 160 ms presentation
  lead, not a measured common browser/GPU playback clock.
- A gap up to 750 ms retains the speech source. A longer gap renders one neutral
  frame from that source and holds it. Explicit reset cancels immediately, rejects
  retired motion/frame results and clears history. Source clip jumps are not used
  to fill packet gaps.
- The GPU-path wall-time budget includes features, motion and rendering. Selected
  budget `0.8` persists in `.runtime/trend-avatar.json`; `scripts/kiosk.py` passes
  it as `--gpu-budget` on every start. This reserves processing time rather than
  promising a hard device-utilization cap. Target render rate remains at most 12.
- Real GPU acceptance caught upstream `motion_stitch` inserting keys into a
  buffered pose dictionary. Rendering now owns a copy, including its arrays.
  A regression test demonstrates the previous mutation failure.

## Actual RTX 3060 / WebRTC measurements

Same 720×1280 source, five motion steps, 200 ms feature stride, 160 ms presentation
lead, prerecorded greeting PCM. One local receiver, no STUN/cloud/avatar audio.
These are **avatar-only** runs; live AV Fusion and microphone recognition are
outside this benchmark. Both runs include speech, speaking while waving, smile,
reset and empty-audio-buffer checks.

| Metric | Work budget 1.0 | Selected budget 0.8 |
| --- | ---: | ---: |
| Mean sampled GPU utilization during established speech | 85.54% | 68.62% |
| Neural frames generated per second, last speech window | 10.2 | 8.4 |
| Numerically changed expression frames per second | 7.0 | 7.4 |
| Video RTP frames per second | 12.003 | 12.000 |
| Face render mean | 74.45 ms | 74.17 ms |
| Motion prediction mean | 23.18 ms | 23.15 ms |
| Feature extraction mean | 12.59 ms | 12.52 ms |
| PCM HTTP acknowledgment p95 | 2.50 ms | 2.36 ms |
| Reset HTTP duration | 1.28 ms | 1.32 ms |
| Received RTP audio frames | 0 | 0 |

The budget trades generated-frame rate for headroom. The expression-change counter
does not measure phoneme accuracy or visual quality; 7.4 versus 7.0 is a scheduling
observation from these short runs, not a statistically established quality gain.
RTP FPS includes repeats. Reset HTTP duration is not acoustic interruption latency.

Evidence: `output/avatar-quality-review/continuity-budget-{100,80}/acceptance.json`,
`telemetry.json`, `received-mouth-frames.jpg` and `wave-speaking.jpg`. Telemetry
samples `nvidia-smi` every 500 ms; the utilization means use active speech samples
after a metric window of at least four seconds (13 samples per run).

Reproduce against a warmed local server:

```sh
PYTHONPATH=. .runtime/livetalking-venv/bin/python scripts/ditto_acceptance.py \
  --url http://127.0.0.1:8010 --output output/ditto-webrtc
# Optional compatibility test: add --legacy-audio.
```

## Lips and teeth: controlled check

Same source features, audio contexts at 0.8 / 1.4 / 2.0 seconds, fixed noise seed 17,
sampler steps 5 / 10 / 20 / 50. Increasing steps did not restore the original
lip/tooth appearance in the inspected samples. Warm motion prediction rose from
about 22 ms (5 steps) to 44 / 87 / 216 ms. The first five-step timing includes
compilation and is excluded from this comparison.

[Sample comparison](../../output/avatar-quality-review/streaming-mouth-ab/sampler-comparison.jpg)
and `timings.json` retain the evidence. The left column is an appearance reference,
not a phoneme-matched image. More FPS or more diffusion steps does not prove
preservation of the original anatomy. No face restoration, replacement mouth
texture, lower face resolution or new model weights are deployed by this change.

## Verification and limits

Fresh checks: 58 focused Python tests, 37 frontend tests, TypeScript build and
Oxlint passed. Ruff lint/format passed for all 13 Python files touched by this
change. Modified TypeScript and AudioWorklet files pass Prettier. The wider frontend format check
reports an existing issue in untouched `VirtualKeyboard.tsx`; it is not reformatted
as part of the media patch.

The actual GPU browser regression passed in 34.74 s against the managed avatar:
greeting, native PCM events, interruption, next turn/guest, wave while speaking,
smile, transport reconnection, microphone rearm and 375/768/1440 layouts. Voice
events are mocked against an isolated guest database; the WebRTC avatar is real.
Screenshots: `output/avatar-browser/`. This is transport/UI acceptance, not physical
microphone/speaker acceptance.

Built frontend and started managed visual/avatar/API services at 9877/8010/8080.
Final checks: all ports listening; API advertises Ditto `video_only=true`; engine
ready with no error and budget 0.8; no active guest and zero audio buffered. At rest,
the three-service configuration sampled 2% GPU and 7,398 MiB. Live voice/Fusion
load must not be inferred from this idle sample. The staging server at 8011 is
stopped. `.runtime/trend-avatar.before-continuity.json` retains the prior manifest.

No live voice service, customer recording, merchant order, payment or printer job
is used by the tests. Actual speaker distortion, word loss and subjective mouth
naturalness still need physical acceptance; synthetic PCM cannot establish them.

The remaining architectural limitation is the generic neural face renderer's
reconstruction of teeth/lips. A character-specific model is a separate quality
experiment with its own source-data and RTX 3060 validation, not an improvement
established by this patch.

## Self-evaluation

Accuracy 4/5: real GPU measurements, observed failures, explicit acoustic and
anatomical limits. Completeness 3/5: buffering/transport/motion fixes are deployed;
the original-mouth requirement remains unmet. Clarity 4/5: generated, changed-pose
and RTP frame rates are separate. Actionability 4/5: persistent launcher settings,
reproducible acceptance command, tests and review artifacts. Conciseness 4/5:
detailed evidence stays here. Average 3.8/5. The unresolved item is appearance,
not a reason to repeat sampler/FPS tuning without a new quality hypothesis.
