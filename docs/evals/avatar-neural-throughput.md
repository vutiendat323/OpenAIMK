# Neural mouth rendering and relaxed rest — 2026-10-31

The selected profile reaches **15.6 generated mouth frames/s** in the measured
RTX 3060 WebRTC speech window, compared with the previous 8.6. Source presentation
remains 24 FPS. After speech, the avatar uses the original relaxed source smile.
This is not a claim that generated speaking lips reproduce the source anatomy.

## Selected implementation

- Same Ditto weights, full 512px coordinate system and five motion sampling steps.
- Torch grid sampling around a prepared TensorRT dense-motion CNN and decoder.
  Convolutions use FP16; normalization computation uses FP32. No model download,
  source-video replacement or cloud avatar service was added.
- The partial decoder retains full-frame normalization statistics and only skips
  unused work in its final stage. It supplies `[128,272,384,464]` to the existing
  source-mouth compositor. Original source pixels supply the rest of the image.
- A dedicated CUDA stream avoids TensorRT default-stream synchronization.
  Audio conditioning is reused within each motion call, with unchanged sampling
  noise/RNG and equations. Motion windows advance every 160 ms.
- Rest uses original source pixels after 280 ms without voiced assistant PCM;
  silent packets perform no neutral-mouth inference. Cached final mouth textures
  are cleared so resumed speech waits for a fresh texture.

The manifest selects `tensorrt-mouth`, a neural target ceiling of 24, motion
stride 160 ms, presentation 24 FPS and GPU-path wall-time budget **1.0**. The old
profile used budget 0.8. The speed increase therefore includes renderer changes
and a different work budget; it is not an equal-budget A/B claim. Native voice
and microphone processing are unchanged.

## Accuracy contract and rejected candidates

Full TensorRT rendering passed comparisons against current PyTorch weights on
five changing captured inputs: worst mouth MAE 0.09346, p99.9 0.62256 and maximum
1.36963, measured in RGB255 units. Nonfinite output is rejected.

The partial decoder **failed** the original *unmasked rectangular* comparison
(worst MAE 0.10173 versus limit <0.1). That failed report remains
`neural-fps/tensorrt-hybrid-roi.json`; no full-face equivalence is claimed for it.

Its separate, narrower runtime contract is the actual source-composited mouth.
Preparation compares current full PyTorch output with partial output, applying
the compositor's alpha on its nonzero support **before final uint8 rounding**.
It excludes pixels that the product never displays. The same numerical limits
remain: MAE <0.1, p99.9 <1 and max <2 RGB255. All **383 source/gesture regions**
were checked for each of five inputs (1,915 comparisons). Worst displayed-mouth
MAE **0.083493**, p99.9 **0.684815**, max **1.182861**; all finite.

Every source and gesture frame must fit the decoder rectangle, including a
four-pixel transition/interpolation margin. Prepared metadata binds source-video
hashes, weight hashes, engine hashes, TensorRT version and GPU capability.
Changed source identity or uncovered geometry rejects startup. The partial
canvas is never used as a complete face.

Other experiments are not selected: Conv3d folding and batching were slower;
batched motion guidance took 28.73 ms versus 20.19 ms; capturing the full motion
sampler saved only 0.93 ms. FP16 normalization outputs did not materially improve
renderer time. Their diagnostic results remain separate.

## Actual decoded WebRTC measurement

Exclusive port 8011, prerecorded local `output/native-speech-48k.wav`, two speech
repetitions, 1.3 s gap, resumed speech, waving with speech and epoch reset.
476 frames recorded, zero recorder drops, cleared PCM after reset, no engine
error. Values below are actual received video; neural rates are rolling five
second health windows at the end of each phase.

| Phase | Received FPS | Interval p95 | Generated mouth FPS | Changed-pose FPS |
| --- | ---: | ---: | ---: | ---: |
| Speech | 23.993 | 43.42 ms | **15.6** | 8.8 |
| Gap | 24.027 | 43.19 ms | 12.4* | 7.0* |
| Resumed | 23.994 | 43.98 ms | 13.6* | 10.2* |
| Wave + speech | 23.982 | 44.60 ms | **16.0** | **15.4** |

*Rolling windows include preceding speech/gap. Gap checkpoint reports
`mouth_mode: source`; it does not keep inferring at 12.4 FPS during silence.

Generated frames can reuse a pose. The first speech expression counter is 8.8,
while the wave window reaches 15.4. This does **not** establish 15–20 distinct
expressions/s for every utterance. Geometry transitions remain bounded at 41.7 ms.

Mean stage times in the speech checkpoint: feature extraction 12.95 ms, motion
21.81 ms, renderer 47.06 ms. Raw partial-renderer benchmarks exclude audio/motion
and must not be reported as achieved conversation FPS.

GPU samples for this isolated test: mean 69.90%, max 91%, peak 4,098 MiB. These
samples include pauses and do not include live Fusion/microphone processing.
They cannot be directly compared to the user's earlier full-kiosk GPU screenshot.

- [Received conversation preview](../../output/avatar-quality-review/neural-fps/conversation-optimized/conversation-preview.mp4)
- [Received relaxed smile](../../output/avatar-quality-review/neural-fps/conversation-optimized/relaxed-source-smile.jpg)
- `cadence.json`, `received-frame-times.json`, `gpu-samples.json` in that directory.
- [Current-weight visible-mouth validation](../../output/avatar-quality-review/neural-fps/presented-mouth-validation.json)

Preview audio is prerecorded reference PCM at feed time +160 ms. It is not a
physical speaker/microphone recording. Acoustic sync, microphone word retention
and subjective speaking-tooth anatomy are not established by this test.

## Verification and operation

110 focused Python tests pass, including original rest pixels, silent PCM,
resumption without a stale mouth, epoch/action isolation, decoder mathematics,
source coverage/identity and transport. 26 frontend voice/avatar tests pass.
Actual GPU/browser greeting, interruption, wave, smile, reconnect and next guest
regression passes in **34.76 s**. Touched Python lint/format checks pass.

Normal start uses the already prepared caches:

```sh
.venv/bin/python scripts/kiosk.py start
.venv/bin/python scripts/kiosk.py status
```

Rebuild only when needed, with the kiosk and test avatar stopped:

```sh
.venv/bin/python scripts/kiosk.py stop
PYTHONPATH=. .runtime/livetalking-venv/bin/python scripts/prepare_ditto_acceleration.py --rebuild
PYTHONPATH=. .runtime/livetalking-venv/bin/python scripts/prepare_ditto_mouth.py --rebuild
.venv/bin/python scripts/kiosk.py start
```

Preparation refuses active kiosk/test-avatar ports or a live voice session.
The second command requires local Ditto source/checkpoints and captured input
fixtures; it is not a fresh-machine environment installer.

Final activation: managed ports 9877/8010/8080 listen; avatar and API report
ready, `tensorrt-mouth`, video-only, no engine error, and original-source mouth
while resting. No active guest at the check. Test port 8011 is closed. Cache
preparation was also verified to reject the running kiosk before GPU imports.
Snapshot: `output/avatar-quality-review/neural-fps/deployment-health.json`.

Before-profile backup: `.runtime/trend-avatar.before-neural-optimization.json`.
Selecting `renderer_backend: tensorrt` uses the validated full decoder; selecting
`pytorch` uses the original fused Torch path. Rest/source fixes stay in either.

## Self-evaluation

Accuracy 4/5: actual decoded rates, distinct pose counts and validation scope are
explicit; acoustic quality is unmeasured. Completeness 4/5: requested source smile
and ~15 generated FPS are verified; distinct-pose smoothness and speaking anatomy
still need perceptual review. Clarity 4/5: raw, generated, changed-pose and received
rates are separate. Actionability 4/5: prepared profile, review video, startup and
rebuild/rollback options exist; cold installation is outside this change.
Conciseness 4/5: detailed evidence stays here. Average 4.0/5. Next improvements:
measure real acoustic timing and inspect pose holds with the user's utterances.
Would the user agree? The source smile is visible; acceptance of speaking lips
has not been reported for this revision.
