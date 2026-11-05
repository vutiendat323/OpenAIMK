# Ditto V2: rejected visual result — 2026-11-02

The user rejected `trial-V2-0.8.mp4`: distortion throughout the clip, broken-looking
neck, pursed lips and poor quality despite near-full GPU use. This is a failed
candidate, not an accepted base for deployment or further parameter tuning.

## Reproduced evidence

CPU-only extraction found all eight supplied screenshot crops in the rejected
video. Normalized image-matching scores are 0.966–0.986; these are localization
scores, not probabilities, quality ratings or percentages of acceptable frames.
Several screenshots repeat the same video frame.

| Screenshot | Video frame (zero-based) | Time | Original/source frame |
|---|---:|---:|---:|
| 1 | 242 | 10.083 s | 141 |
| 2, 6, 8 | 37 | 1.542 s | 27 |
| 3, 5 | 129 | 5.375 s | 78 |
| 4 (neck) | 10 | 0.417 s | 13 |
| 7 (lips) | 22 | 0.917 s | 19 |

The original frame is selected by matching untouched clothing, excluding the
generated head and neck. The closed V2 source has the original's frame order.
The image comparisons retain the actual decoded pixels, with only resizing,
cropping and labels; no restoration or retouching is applied.

- [Original / closed V2 source / rejected live output](../../output/avatar-quality-review/v2-rejection/failure-stages.png)
- [Neck case](../../output/avatar-quality-review/v2-rejection/screenshot-4-stages.png)
- [Matching records](../../output/avatar-quality-review/v2-rejection/matches.json)
- [CPU extraction script](../../output/avatar-quality-review/v2-rejection/audit.py)

## What is established

The closed source changes the mouth and chin shape before live inference. It is
not an untouched original face with only the inner mouth closed. The previous
builder used both lip and chin landmarks for its mask and pixels from the
earlier generated closed-face video. Calling it a mouth-only, original-pixel
source overstated what was preserved.

The live output introduces additional visible softness and a neck blend/tonal
discontinuity in the reported neck case. The source-to-output comparisons localize
this additional degradation to the live rendering/compositing stage; they do not
separate the neural renderer, pose drive and putback into independent causes.

Code inspection identifies a structural mismatch to investigate, not an isolated
causal proof: `--drive-head` drives pitch/yaw/roll/translation on top of the video's
own moving pose, while `_paste_face` uses the video's original `M_c2o_lst[index]`
and Ditto's fixed crop mask. The surrounding body is not driven by that added
motion. Increasing head movement without resolving this attachment is not a
verified fix for the requested talking head.

## Corrections to earlier claims

- GPU time and encoded FPS are performance measures. They do not establish image
  quality. The known throughput limit does not explain away distortion or a neck
  seam, and no claim that a faster GPU would repair these defects is supported.
- Aperture p95 and lip tilt do not grade identity, anatomy, teeth, smoothness or
  the neck junction. Reaching an aperture threshold did not mean this result passed.
- Correlation between mouth opening and audio energy is not phoneme alignment or
  a lipsync test. The earlier assertion that V2 was the first genuinely synced
  result, and categorical claims that other variants could not sync based only on
  those correlations, are withdrawn. The roughly 600 ms estimate is unvalidated,
  especially with audio muxed after capture.
- `full-face-both0.5.mp4` remains the historical offline appearance reference. Its
  acceptance does not establish a real-time implementation, silence behaviour or
  speaker sync. The running profile still has no accepted real-time visual result.

## Disposition

No new GPU generation was performed in this review. All managed services and the
isolated port 8011 were stopped when inspected. The active profile still points
to `.runtime/trend-closed-source.mp4`; V2 was never promoted. No renderer code or
profile was changed. Retain rejected artifacts for diagnosis, not as deployable
presets. Further work needs a validated face/neck rendering baseline, not another
opening-factor change or another request that the user accept 13–15 FPS.

## Self-evaluation

Accuracy 4/5: exact reported frames and code paths are documented; renderer versus
pose versus blend causality remains unresolved. Completeness 2/5: rejection is
contained and earlier claims corrected, but the requested visual quality is not
delivered. Clarity 4/5: stage images separate source and live degradation; visual
judgment remains partly subjective. Actionability 4/5: durable reproduction and
failure locations exist; no verified replacement is available. Conciseness 4/5:
technical detail stays in this report. Average 3.6/5. The user would agree that
V2 fails; no acceptance is assumed. Highest priority: isolate the neck junction
and restore the accepted face appearance before another full clip trial.
