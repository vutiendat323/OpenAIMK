# Whole-face reference correction — 2026-10-31

Status: rejected visual diagnosis and offline prototypes; not deployed.

**Subsequent user clarification supersedes the source-switch interpretation:**
“Giữ diện mạo, màu ấm bên trái; sửa biểu cảm.” Preserve the currently deployed
standing face and warm coloration. Use the other clip as an expression reference,
not as replacement identity/appearance. The user rejected the source-pixel video
for disharmonious expression and changed coloration, then explicitly identified
excessive mouth opening in the warm/current avatar. The next probes preserve the
standing source. The historical source-switch analysis below is not the target.
The user explicitly rejected the previous source-relative expression comparison
as still thick/unnatural and approximately 80% satisfactory. Geometry statistics
from that comparison must not be treated as perceptual acceptance.

## Correct reference

The latest requested sample is visually consistent with
`123_Tạo_video_chân_thực_cô_48e0af4f.mp4`, rather than
`Tạo_video_chân_thực_cô_0e3fdbe0_1080p.mp4`, which earlier geometry comparisons
used. Both files exist and have visibly different face, lip, tooth and color
appearances. The deployed standing source is yet another clip,
`Female_staff_member_standing_3128c196.mp4`.

Evidence: [source contact sheet](../../output/avatar-quality-review/whole-face/sources.jpg)
and [preferred source timeline](../../output/avatar-quality-review/whole-face/reference-timeline.jpg).
`scripts/review_avatar_mouth.py` now requires an explicit `--reference` and records
both input paths in its JSON report. It cannot silently use the previous clip.

## Controlled probes

The same prerecorded native speech fixture, `output/native-speech-48k.wav`, was
used throughout. No microphone capture, replacement TTS or merchant action was
used. The preferred source was registered with the existing Ditto weights and
full TensorRT decoder. Within one instance, identical predicted motion was
rendered at expression displacement strengths 1.0 and 0.75. These are experimental
strengths, not production settings. Both retain unnatural mouth/jaw shapes in
some frames; reducing amplitude alone was not accepted as a fix.

[Three-way contact sheet](../../output/avatar-quality-review/whole-face/whole-face-candidates.jpg).
The standing/current column comes from the previous run using the same audio;
it is not a same-noise, same-source control. Only the two preferred-source columns
share all predicted motion and differ solely in displacement strength.

A second CPU-only diagnostic matches real mouth images from the 192-frame
preferred clip to predicted aperture, relative width and head orientation.
It aligns eyes/nose with a similarity transform, composites the real mouth
pixels and applies a skin-ring color offset. There is no generated tooth
interior or vertical mouth compression in this probe. The unchanged source
upper-face region (canonical rows 0–259) has exactly zero maximum RGB difference
before encoding across all 112 output frames.

- [Current / preferred appearance with original mouth pixels](../../output/avatar-quality-review/whole-face/before-after-source-pixels.mp4)
- [Same preferred source: generated / original mouth pixels](../../output/avatar-quality-review/whole-face/same-source-mouth.mp4)
- [Static same-source detail](../../output/avatar-quality-review/whole-face/source-pixels-comparison.jpg)
- [Diagnostic measurements](../../output/avatar-quality-review/whole-face/source-pixel-review.json)

Both videos contain 112 frames, 4.48 seconds, 25 FPS encoded video and the same
audio fixture, verified with ffprobe. Encoding at 25 FPS does not establish
real-time rendering speed or acoustic synchronization.

## Why the prototype is not deployed

The retrieval diagnostic uses whole-utterance Viterbi selection and landmarks
measured from previously rendered output. Neither is a causal, efficient live
selector. It changes selected mouth images 52 times in 4.48 seconds, approximately
11.61 changes/second, below the user's requested 15–20 FPS motion target. The
largest source index jump is 100 frames. A small aperture error (p95 0.0328 in
mouth-width units) does not establish phoneme accuracy, seamless texture changes
or natural motion. The offline upper-face preservation check is also not a
naturalness score.

The preferred original clip includes speech. Simply changing the installed
source would make its mouth move during silence. Its rest loop and greeting
appearance also need a consistent source strategy before a live switch.
The production manifest, source, posterior image, audio path and renderer were
not changed during these probes. Managed avatar was temporarily stopped only
after the API reported no active session, and restarted after GPU rendering.
A subsequent read-only check found all managed services stopped; the managed
launcher was used to restore them with the existing profile.

Human feedback on the new whole-face prototype was requested. Outstanding:
appearance acceptance, a causal selector, temporal continuity, state consistency,
and measured live performance. This report does not mark the user objective done.

## Verification scope

Ruff lint/format and CLI help pass for the changed geometry-review script.
There are no new production inference changes to validate in this follow-up.
Earlier source-relative work had 40 focused passing tests and real WebRTC
measurements, but the full mixed-interpreter suite was not wholly green:
528 passed, 3 failed, 4 skipped. Two MCP failures passed using the main project
interpreter; the paused-audio browser fixture still observed 17 rather than 25
silent frames. That failure is not represented as fixed by these appearance probes.

## Self-evaluation

Accuracy 4/5: the corrected reference, inspected failures and prototype limits
are explicit; subjective naturalness remains unconfirmed. Completeness 2/5:
the desired live face/motion result is not delivered, and the retrieval prototype
does not yet satisfy causal operation or motion-rate requirements. Clarity 4/5:
source changes and mouth-generation changes have separate comparison artifacts.
Actionability 4/5: two playable comparisons and reproducible diagnostic artifacts
are available, with experiments kept under `.runtime/review_reference_face.py`,
`.runtime/review_source_pixels.py` and `.runtime/build_whole_face_review.py`.
Conciseness 4/5: detailed limitations stay here. Average 3.6/5.

Next improvements by impact: establish the user's acceptance of the corrected
whole-face target; replace whole-utterance image selection with a causal motion
selector; validate rest/greeting continuity and actual motion rate before rollout.
Would the user agree? The previous result was rejected; no acceptance is assumed.
