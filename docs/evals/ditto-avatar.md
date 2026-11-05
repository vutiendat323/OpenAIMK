# Direct-source Ditto evaluation — 2026-10-30

The acceptance criterion is the original character's lip and tooth anatomy while
speaking new audio. Sharpening a different mouth synthesized by MuseTalk does not
meet this criterion. No MuseTalk outputs, latents, model or restoration pass are
inputs to this evaluation.

## Reproducible experiment

- Original: `123_Tạo_video_chân_thực_cô_48e0af4f.mp4`, 720×1280, 24 FPS.
- SHA-256: `e792cc32e6b3d557d64d3b77fafb657015683b522547ec9296b2ff8bff115335`.
- [Ditto upstream](https://github.com/antgroup/ditto-talkinghead), commit
  `c3e47eee2e626500017a0556b470d6d4182f85e8` in `.runtime/Ditto`.
- Weights: `digital-avatar/ditto-talkinghead`, revision
  `e4a2f60328ee7c32af585ac4b3cce299e4c8e254`, `ditto_pytorch/*` and
  `ditto_cfg/v0.4_hubert_cfg_pytorch.pkl` under `.runtime/Ditto/checkpoints`.
- Interpreter: `.runtime/livetalking-venv/bin/python`, Python 3.12, torch 2.9.1
  CUDA 12.8. Optional packages isolated in `.runtime/ditto-packages`.
- GPU: RTX 3060 12 GB. No production voice connection or microphone is opened.

```sh
HF_HUB_OFFLINE=1 .runtime/livetalking-venv/bin/python scripts/review_ditto_source.py \
  '123_Tạo_video_chân_thực_cô_48e0af4f.mp4' \
  --output output/avatar-quality-review/ditto-smile-123 \
  --emotion 3 --silence-control

.venv/bin/python -m unittest discover -s tests -p test_ditto_review.py
```

The runner resamples the original video to 25 FPS without spatial resizing and
extracts its audio to 16 kHz mono. It also drives the same source with the existing
`frontend/public/voice/default/greeting.wav` and a four-second silence control.
The upstream demo actor's `ch_info`, expression/eye arrays and pose controls are
explicitly removed. Source pose and eye motion are retained. The model's expression
driver controls mouth movement. Rendering and muxing are local.

## Findings

1. **Relative motion is unsuitable for a talking source video here.** Upstream
   adds the generated motion delta to each source frame's expression. This keeps
   the original mouth movement and can look deceptively close to the original
   even when another utterance is playing. Kept as a diagnostic only in
   `output/avatar-quality-review/ditto-original-123`.
2. **Absolute motion avoids that additive source-mouth dependency.** With
   `relative_d=False`, source and greeting audio produce different mouth movement;
   the silence control closes the mouth in inspected frames. The neutral emotion
   setting (4) produces visibly pursed lips and loses the source smile. Results in
   `output/avatar-quality-review/ditto-absolute-123`.
3. **The happy emotion setting (3) improves the smile in inspected frames.** It
   still uses the original source features with Ditto's own neural renderer.
   This is a candidate for perceptual review, not a claim of identical anatomy or
   proven phoneme alignment. Results in `output/avatar-quality-review/ditto-smile-123`.

Review artifacts (left: original appearance; right: Ditto):

- [Original audio comparison](../../output/avatar-quality-review/ditto-smile-123/source-comparison.mp4)
- [New greeting comparison](../../output/avatar-quality-review/ditto-smile-123/greeting-comparison.mp4)
- [Full-body new greeting](../../output/avatar-quality-review/ditto-smile-123/greeting-ditto.mp4)
- [Source/greeting/silence sampled frames](../../output/avatar-quality-review/ditto-smile-123/audio-control-contact.jpg)

The happy run passed all three actual output validations, with 202/67/100 frames.
Its source, greeting and silence runs took 48.82/22.75/29.55 seconds respectively.
The side-by-side greeting uses the new audio for both panels; the left panel is
only the original appearance reference and is not claimed to synchronize to it.

The full-face renderer can alter details. Source likeness in selected frames is
not sufficient evidence of stable teeth throughout speech. The new-audio clip and
the silence control are necessary alongside the same-audio comparison.

## Performance and validation

The current eager PyTorch renderer (FP32 stored weights, FP16 autocast in the
warper and decoder) sustains approximately **6 FPS** during its
steady output stage, using approximately 11.3 GB total GPU memory including the
desktop. This is not a realtime kiosk implementation. In the neutral run, the
8.04-second audio took 48.79 seconds including source registration and rendering;
the 2.68-second greeting took 22.86 seconds. Per-run times, source hash, settings
and decoded stream lengths are recorded in each `render.json`.

Four unit tests cover complete output, missing audio, truncated video and truncated
audio. Actual neutral renders passed stream validation: 202 frames for 8.043 s,
67 frames for 2.68 s and 100 frames for 4 s. These checks do not prove visual
naturalness, Vietnamese lip synchronization or browser playback performance.

The upstream documentation reports an A100/TensorRT tested environment; its
realtime claims cannot be applied to this RTX 3060 PyTorch run. TensorRT work is
only warranted after the character's mouth appearance is accepted.

The active avatar manifest and poster remain byte-identical to the saved baseline.
No voice pipeline code is changed by this evaluation.

### Measured stage profile

The actual 67-frame greeting was profiled using `.runtime/profile_ditto.py`.
Results: `output/avatar-quality-review/ditto-profile/stages.json`. Median wall
time after the first ten frames: warper 166.35 ms, decoder 70.71 ms, compositing
4.36 ms, writer 1.05 ms. Parallel stages share the GPU: do not add these times
or treat them as isolated kernel costs. The warper service interval agrees with
the observed 6 FPS. Audio features cost 185 ms and motion generation 1,118 ms for
the whole 2.68-second greeting. Source registration costs 9.84 s before rendering.

Correction: upstream warper and decoder already enable FP16 autocast with FP32
stored weights. Merely enabling FP16 is not a new optimization. Their boundaries
also materialize CPU NumPy arrays and upload them again at the next GPU stage;
that independent overhead has not yet been isolated. Next performance experiments
should target warping/rendering and transfers while preserving output resolution
and checking mouth detail. No optimized FPS has been measured yet.

## PyTorch optimization measured on this RTX 3060

Implemented in `scripts/ditto_torch.py`, enabled only by `--torch-optimized` in
the offline review runner. The original path remains available for comparison.
Model weights, face resolution (512×512), video resolution (720×1280), audio,
frame rate and motion-generation settings are unchanged.

Changes:

- Channels-last storage for 2D and 3D convolutions. The hourglass output is made
  contiguous where upstream uses `view` to flatten channel/depth dimensions.
- Spectral normalization's fixed evaluation weights are materialized once.
- Warper and decoder features stay on GPU between these stages.
- Warper and decoder are compiled separately. Warper compilation disables
  Inductor layout optimization to retain the measured 3D convolution layout;
  decoder uses `reduce-overhead`. A single compiled graph with default layout
  selection was slower and is not enabled.

Initial experiments on five real captured frames gave these render-only rates:
6.22 FPS baseline; 6.38 with cuDNN algorithm search; 8.65 with memory layout;
7.98 compiling the entire function; 13.29 compiling only the decoder; 15.07
compiling the models separately with the warper layout preserved. These isolated
measurements reused GPU inputs and exclude transfers; they are not kiosk FPS.

The final reproducible benchmark exercises actual CPU input/output interfaces,
including transfers, against the upstream NumPy/GPU wrappers. Results are in
`output/avatar-quality-review/ditto-torch-benchmark/verified-renderer.json`:

| Renderer, after warmup | Mean/frame | P95/frame | Throughput |
| --- | ---: | ---: | ---: |
| Upstream | 164.94 ms | 166.43 ms | 6.06 FPS |
| Optimized PyTorch | 69.52 ms | 69.96 ms | 14.38 FPS |

50 measured frames per path, cycling five captured source/audio conditions.
Measured speedup: **2.37×**. Optimization warmup took **16.47 seconds**, versus
1.65 seconds for baseline, in that process; cold compilation/cache conditions
can change startup time. Compilation must finish before serving interactive audio.

Raw-face equivalence against upstream: mean absolute RGB difference **0.0178/255**,
99.9th percentile **0.1245/255**, maximum **0.2491/255**. All values were finite.
`tests/test_ditto_torch_gpu.py` passed with real checkpoint inference and checks
that changing source/motion inputs still changes the output. Four review-output
validation tests also passed; modified Python files pass Ruff.

```sh
TORCHINDUCTOR_COMPILE_THREADS=4 HF_HUB_OFFLINE=1 \
  .runtime/livetalking-venv/bin/python scripts/benchmark_ditto_torch.py \
  output/avatar-quality-review/ditto-torch-benchmark \
  --output output/avatar-quality-review/ditto-torch-benchmark/verified-renderer.json

TORCHINDUCTOR_COMPILE_THREADS=4 HF_HUB_OFFLINE=1 \
  .runtime/livetalking-venv/bin/python scripts/review_ditto_source.py \
  '123_Tạo_video_chân_thực_cô_48e0af4f.mp4' \
  --output output/avatar-quality-review/ditto-torch-optimized-123 \
  --emotion 3 --silence-control --torch-optimized

TORCHINDUCTOR_COMPILE_THREADS=4 RUN_AVATAR_GPU_TESTS=1 HF_HUB_OFFLINE=1 \
  .runtime/livetalking-venv/bin/python -m unittest discover -s tests \
  -p test_ditto_torch_gpu.py
```

This proves a faster renderer on the actual GPU, **not 25 FPS**, realtime WebRTC
performance, microphone quality or subjective acceptance of Ditto's mouth anatomy.
The optimization is independent of the native voice pipeline.

Full offline pipeline verification is recorded in
`output/avatar-quality-review/ditto-torch-optimized-123/render.json`:

| Audio case | Validated frames | Steady renderer FPS | Entire job, including preparation |
| --- | ---: | ---: | ---: |
| Original 8.043 s | 202 | 14.04 | 45.37 s, including first compilation/autotune |
| Greeting 2.68 s | 67 | 13.98 | 16.39 s |
| Silence 4 s | 100 | 13.95 | 19.77 s |

The review runner registers all 200 source frames again for each case. Thus total
offline job time is not `frames / steady FPS` and is not realtime latency. The
steady values measure the completed CPU face output per call, excluding the first
ten calls. Actual videos retain all frames and validated audio duration.

[Inspected before/after face samples](../../output/avatar-quality-review/ditto-torch-optimized-123/before-after.jpg)
show similar lips/teeth at the sampled instants. Across every decoded output frame,
face-region MAE versus the earlier unoptimized run was 1.40/255 (source), 1.40/255
(greeting), and 1.45/255 (silence). These comparisons include the entire upstream
preparation/motion/compositing/encoding pipeline, whereas the much smaller raw-face
error above isolates the renderer with fixed identical inputs. Neither metric is
a substitute for subjective character-quality acceptance.

An additional isolated experiment disabled cuDNN algorithm search: 14.16 FPS,
versus 15.07 FPS with it on GPU-resident inputs. The faster setting is retained;
its startup cost is explicitly reported. No frame interpolation, frame skipping,
lower resolution or changed model weights were used to reach the reported FPS.

Optimization follow-up self-evaluation: accuracy 4/5 (actual GPU benchmarks and
full clips; no browser latency measurement); completeness 4/5 (implemented and
tested PyTorch path, not production integration); clarity 4/5 (cold/warm and
renderer/pipeline scopes separated); actionability 4/5 (commands and artifacts,
captured inputs required for isolated replay); conciseness 4/5 (detailed evidence
kept in this report). Average 4.0/5. Next independent validation would be live
streaming latency; 25 FPS remains unproven and is not claimed.

## Self-evaluation

Accuracy 4/5: original-source provenance, actual videos and measured timing;
perceptual quality and phoneme synchronization remain unvalidated.
Completeness 3/5: a working replacement-engine experiment exists, but it is not
an accepted realtime replacement. Clarity 4/5: relative-motion leakage and smile
control are separated from anatomical fidelity. Actionability 4/5: reproducible
runner and comparison artifacts; optional environment setup still needs packaging.
Conciseness 4/5: technical limitations are retained here instead of obscuring the
visual review. Average 3.8/5. Priority: inspect full-sequence mouth stability with
the user before spending GPU time optimizing this candidate. User acceptance must
not be inferred from a previous MuseTalk restoration review.
