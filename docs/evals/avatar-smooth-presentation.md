# Smooth conversation presentation — 2026-10-31

User goal: motion smooth enough for conversation. Treat 20–24 actual presented
frames/s as the engineering target; subjective acceptance is separate.

## Reproduced causes

- Generated output was approximately 8–9 FPS while RTP was capped at 12 FPS.
  Repeating a frame at the transport rate did not provide continuous motion.
- The worker deliberately held the **whole** neutral image after a 750 ms PCM
  gap. A minimized CPU replay produced only one distinct published image across
  twelve presentation ticks. This explained the reported full-avatar pause.
- Actual renderer/transfer throughput was 14.68 FPS / 68.12 ms before feature,
  motion and budget overhead. Removing an FP32 boundary did not improve it.
  Freezing and padding kernels reached only 15.05–15.14 FPS; these experimental
  changes are not deployed. Merely raising the neural FPS setting was insufficient.

## Implemented

`DittoEngine` now has an independent 24 FPS CPU source presenter and a bounded
latest-mouth slot. The GPU continues producing mouth textures at its existing
budget. Source movement, including the body/head during speech and pauses,
continues without waiting for a neural frame. Each mouth texture follows the
current source landmarks; original pixels outside the mouth remain untouched.

The CPU presenter can make a short geometric transition between mouth updates.
It estimates a conservative positive affine motion from consistent lip features,
then warps **one current texture**. Low-confidence or excessive transforms fall
back to the newest image. Transition duration is capped at one presentation
interval (41.7 ms); no playback queue or audio delay is introduced.

An earlier dense-flow, two-texture experiment produced floating tooth fragments
in actual received frames and was rejected. The final interpolation uses one
texture and rejects folds/invalid scales. A regression with equal-luminance but
different-color mouth features verifies that previous texture cannot leak into
the new mouth. Diagnostic rejected output is retained separately.

Epoch reset clears the latest-mouth slot and rejects in-flight GPU/CPU results.
Action changes never reuse a previous action's mouth. A long PCM gap renders one
neutral mouth; the source body keeps moving. RTP pacing and 90 kHz timestamps now
match actual 24 FPS presentation. Native speaker/microphone code is not modified.

## Actual RTX 3060 / decoded WebRTC result

Exclusive server on 8011, standing source at 720×1280 / 24 FPS, five motion steps,
160 ms pose-clock lead, GPU-path work budget 0.8. Prerecorded greeting PCM;
speaking, a 1.3 s PCM gap, resumed speech, wave while speaking, then epoch reset.
No live customer session, cloud voice, merchant/payment or printer action is used.

| Phase | Received FPS | Interval p95 | Maximum interval | Frames / unique RGB hashes |
| --- | ---: | ---: | ---: | ---: |
| Speaking | 23.995 | 43.81 ms | 45.50 ms | 127 / 127 |
| PCM gap | 24.007 | 43.86 ms | 44.19 ms | 31 / 31 |
| Resumed | 23.995 | 44.63 ms | 46.60 ms | 63 / 63 |
| Wave + speaking | 24.026 | 43.74 ms | 45.93 ms | 64 / 64 |

All cadence gates passed: at least 20 received FPS, p95 below 65 ms, zero recorder
drops, cleared PCM after interruption and no engine error. Recorded 305 frames.
Decoded hashes include codec variation; median consecutive grayscale differences
were 0.60–1.37/255, alongside the source-clock regression proving actual source
advancement. These metrics do not grade perceptual lip synchronization.

**Neural rendering remains 8.6 FPS**, with changed expressions at 7.2 FPS in the
last speech window. Presentation is 24 FPS; twenty mouth transitions were used by
the first speech checkpoint. This is not 24 neural mouth inferences per second.
Mean CPU presentation cost was 7.25 ms in that window. GPU-path wall-time fraction
was 0.774, which is not a device-utilization measurement.

Artifacts:

- [Actual received conversation preview](../../output/avatar-quality-review/smooth-presentation-affine/conversation-preview.mp4)
- [Consecutive received mouth frames](../../output/avatar-quality-review/smooth-presentation-affine/mouth-cadence-24frames.jpg)
- `cadence.json` / `received-frame-times.json` in the same directory.

Preview audio is the prerecorded feed placed at feed time +160 ms to approximate
native startup buffering. It is not a microphone recording, actual speaker capture
or a measurement of physical A/V skew. Original tooth anatomy remains unproven.

Reproduce against an exclusive warmed instance:

```sh
PYTHONPATH=. .runtime/livetalking-venv/bin/python scripts/ditto_cadence.py \
  --url http://127.0.0.1:8011 --output output/avatar-smoothness
TREND_TEST_AVATAR_URL=http://127.0.0.1:8011 TREND_TEST_GESTURES=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_avatar_browser.py
```

## Verification / activation

79 focused Python tests pass. Regressions cover continuous body frames while
mouth/PCM pauses, original-source preservation, tracked geometry, bounded
single-texture transitions, epoch reset during CPU composition, guest/action
isolation and correct 24 FPS RTP timestamps. Changed Python files pass Ruff lint
and format. The actual GPU/browser speech, interrupt, wave, reconnect and next
guest test passes in **34.66 seconds** against the final isolated instance.

The launcher profile retains Ditto and budget 0.8; manifest FPS metadata is 24.
Previous manifest: `.runtime/trend-avatar.before-smooth-presentation.json`.
The final code is used on each managed avatar start. See progress for final live
port/readiness checks. No new weights or lower face/video resolution is used.

Final activation checked all owned ports listening: visual 9877, avatar 8010,
API 8080. Avatar API reports Ditto, ready and video-only. Engine reports no error,
24 FPS presentation/publishing and budget 0.8. No active guest at that check.
The isolated 8011 test server is stopped.

## Self-evaluation

Accuracy 4/5: decoded cadence, distinct neural/presentation rates and rejected
artifact are explicit; physical A/V timing is unmeasured. Completeness 4/5:
cadence and no-freeze targets pass; subjective conversational smoothness still
needs user review. Clarity 4/5: presented source frames and neural mouth frames
are distinguished. Actionability 4/5: runnable exclusive test, actual MP4 and
rollback manifest; cold environment preparation is outside this patch.
Conciseness 4/5: detailed measurements stay here. Average 4.0/5. Next priorities:
review the actual clip for mouth motion, then test acoustic A/V timing with the
real device. Would the user agree? The measured target is achieved; perceptual
acceptance has not yet been reported for this version.
