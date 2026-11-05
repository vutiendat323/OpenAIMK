# Continuous avatar presentation

Implemented inline in the existing workspace; no root Git history/worktree exists.

Goal: enough smoothness for conversation on the RTX 3060 while retaining original
source detail, immediate interruption and native voice independence. User requests
implementation and has explicitly asked to proceed without more design questions.

## Diagnosis / design

Current generated output is about 8–9 FPS; renderer alone measured 68 ms. RTP is
capped at 12 FPS and repeats generated frames. After a long PCM gap the worker
holds the entire neutral frame indefinitely, freezing the body. Source video is
24 FPS and can be presented without neural inference.

Separate 24 FPS CPU presentation from bounded GPU mouth generation. Present the
actual source frame at each tick and reproject the newest epoch/action-matched
mouth patch onto its source landmarks. A short, bounded, motion-compensated mouth
transition may fill a presentation step; it must not create a queued playback
timeline, mix old guest/action frames or change pixels outside the mouth.

The displayed-source rate, neural-generation rate and interpolated-mouth rate must
remain distinct metrics. 24 presented frames does not mean 24 neural inferences.
No network audio, STUN, microphone routing or additional model is introduced.

## Execution

1. Write failing CPU regressions for continued body motion during GPU waits/PCM
   gaps, epoch interruption, source/action matching and tracked mouth placement.
2. Add a bounded latest-mouth slot and independent source presenter. Continue
   recording neural costs and budget; close/reset must invalidate both workers.
3. Add bounded mouth interpolation only if synthetic-edge and actual-mouth
   comparisons avoid ghosting; otherwise retain direct newest-patch presentation.
4. Set RTP pacing/timestamps to the actual presentation rate. Test video-only,
   epoch/interrupt and monotonic timestamps with the local transport.
5. Benchmark captured renderer inputs for safe kernel improvements, requiring
   unchanged weights/resolution and existing pixel-error limits. Reject changes
   that provide no measured speed benefit.
6. Run exclusive local GPU/WebRTC acceptance on 8011 before deployment, recording
   received cadence, actual image changes, longest repeat, neural FPS, frame age
   and short/long PCM gap behavior. Produce a prerecorded-PCM comparison clip.
   Protect any active real kiosk voice session. Deploy the measured configuration
   and document actual rates and perceptual limits.

## Acceptance

- Aim for 20–24 actual presented source frames/s during speech and source idle,
  not repeated whole frames; report received interval p95 and longest repeat.
- Source continues moving through a pause; no indefinite whole-frame freeze.
- Mouth compositing preserves original upper-face/background pixels.
- Reset rejects all retired neural/interpolation results and clears latest mouth.
- Visual smoothing must not delay or interrupt native speaker playback; bound its
  additional visual transition to one presentation interval.
- Do not claim original tooth anatomy, acoustic alignment or subjective acceptance
  from counters alone. Present an actual review artifact.

## Execution outcome — 2026-10-31

- [x] Reproduced whole-frame hold and low renderer throughput.
- [x] Independent source presenter, bounded latest-mouth slot, source tracking and epoch fences.
- [x] Rejected dense-flow two-texture output after actual ghost artifacts; single-texture affine transitions pass texture-isolation regression and inspected frame sequence.
- [x] 24 FPS RTP clock/timestamps and decoded cadence measured on the RTX 3060.
- [x] Kernel probes completed; negligible improvements left experimental.
- [x] 79 focused tests and changed-file Ruff lint/format pass.
- [x] Exclusive GPU/browser speech/gesture/interrupt/reconnect regression passes.
- [x] Managed kiosk activated and checked ready with 24 FPS presentation; staging stopped.

Actual cadence 23.995–24.026 FPS, neural rendering 8.6 FPS. Details and received
review clip: [evaluation](../../evals/avatar-smooth-presentation.md). Perceptual mouth
quality and physical acoustic A/V alignment are not established by FPS counters.
