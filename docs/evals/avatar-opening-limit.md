# Excessive mouth opening — 2026-10-31

The user clarified the visual target: keep the warm standing face and coloration,
and correct its expression. They rejected replacing the face with the greenish
reference clip and rejected the original-pixel mouth retrieval prototype. Their
latest marked frames show excessive vertical opening and a stretched lower lip.
See [rejected source experiment](avatar-whole-face-reference.md) for that boundary.

## Change

`calibrate_expression` now optionally bounds the centered vertical displacement
of the six SDK lip keypoints relative to the predicted silent pose. It preserves
horizontal/depth displacement and their common vertical translation. Small
movements below half the configured limit are unchanged; a smooth tanh knee
compresses larger movements. It does not clamp output images, recolor skin,
replace teeth, change the source face, or introduce temporal buffering.

The configured limit is 0.035 in model-coordinate displacement units, not a
pixel distance, normalized aperture, or universal anatomical threshold. Default
zero disables the correction. The installed manifest explicitly enables it;
`kiosk.py` forwards it to `ditto_server.py`, and engine health reports it.
Rollback profile: `.runtime/trend-avatar.before-opening-limit.json`, including
an explicit zero limit. The existing source-relative calibration remains active.

## Same-input visual comparison

Same SDK instance, source frames, 5-step predicted motion, seed and recorded
native audio; only the opening limit changes between the two outputs.

- [Before / after video](../../output/avatar-quality-review/warm-expression/bounded-before-after.mp4)
- [Largest sampled opening detail](../../output/avatar-quality-review/warm-expression/bounded-before-after.jpg)
- [Geometry report](../../output/avatar-quality-review/warm-expression/bounded-geometry.json)

| Inner aperture divided by mouth width | Before | After |
| --- | ---: | ---: |
| Median | 0.2262 | 0.1915 |
| 95th percentile | 0.2913 | 0.2259 |
| Maximum | 0.3174 | 0.2404 |

The maximum measured opening fell approximately 24.3%. The canonical upper-face
region (rows 0–259) is exactly unchanged before encoding across all 112 frames.
These measurements support smaller openings and preserved appearance, not a
claim that tooth anatomy or overall naturalness is fully solved. The review
video is an offline 25 FPS encode; it is not a throughput benchmark. User visual
feedback on this specific bounded version is pending.

## Alternatives checked

On the warm source, increasing motion sampling from 5 to 20/50 steps reduced
opening, but motion time rose from about 21.7 ms/window to 79.8/197.6 ms/window.
Ten steps cost about 42.2 ms/window and still had a maximum aperture of 0.3017.
These timings cover motion only and are not end-to-end FPS. Changing sampler
step count changes its diffusion schedule; this is not an identical-noise
trajectory comparison. None of these step-count changes was deployed.

A 0.55 constant vertical multiplier reduced maximum aperture to 0.2139 but also
compressed small articulation. The selected soft limit preserves small motion.
A 0.65 multiplier on all expression displacement narrowed more than vertical
opening. Using another warm clip's open-mouth appearance features still left
excessive opening, and was not deployed. No retrieval bank is used in production.

## Validation

New tests were observed failing before implementation: five expression tests
and the real `_render` boundary test. After implementation, 51 expression,
runtime, appearance and launcher tests passed; another 21 server, pose and
presentation tests passed. They cover large-motion bounding, unchanged small
articulation/rest, preserved lateral/depth motion and vertical center, input
immutability, invalid limits, forwarding into the actual warp path, and launch
configuration. Ruff lint and format passed for the seven changed Python files.

Live verification is recorded in
`output/avatar-quality-review/warm-expression/webrtc/` and `webrtc-warm/`.
Both runs received approximately 24 FPS with zero recorder drops and correctly
returned to source-smile pixels during the PCM gap. Both **failed** the 15 neural
FPS threshold: initial speech/wave 14.2/14.6 FPS; warm repeat 14.4/14.4 FPS.
The initial run's changed raw-pose rates were 8.6/13.8 FPS respectively. Displayed
frame cadence, generated frames and changed poses remain different metrics.
The current 15–20 neural FPS goal is not met; no threshold was lowered to claim
a pass. Limiter CPU overhead measured about 0.019 ms/render over 20,000 calls,
while the observed total renderer path was approximately 50 ms/frame. This is
not a complete explanation of the throughput difference from prior runs.

The decoded RTC video was also inspected: 476 frames measured, aperture p95
0.1979, maximum 0.2182. See the [maximum opening capture](../../output/avatar-quality-review/warm-expression/webrtc/maximum-opening.jpg).
This is a different sampler instance from the offline controlled comparison,
so it is not a matched before/after measurement. Native source color remained
visually consistent. The engine was ready without inference errors, using the
explicit 0.035 limit after deployment.

Only the existing native
speech fixture is fed; no live microphone, merchant, order, payment or printer
actions are used. Source, wave source, poster, 5-step sampler, renderer, work-time
budget, native audio path and presentation clock remain unchanged.

## Self-evaluation

Accuracy 4/5: controlled images and measurements substantiate the narrower
opening, but naturalness requires user assessment. Completeness 3/5: excessive
opening is addressed; all lip/tooth realism concerns are not proven resolved.
Clarity 4/5: model-coordinate limits and aperture measurements are distinguished.
Actionability 4/5: explicit installed setting, rollback and comparison video.
Conciseness 4/5: detailed rejected probes and evidence remain in this report.
Average 3.8/5. Improvements: confirm the user's preferred opening range; recover
the unmet 15–20 neural FPS target; extend perceptual review to additional phonemes and wave
poses. Earlier source/pixel experiments were rejected, so acceptance is not
inferred from geometry or passing tests.
