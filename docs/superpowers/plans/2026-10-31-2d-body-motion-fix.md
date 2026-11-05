# 2D body motion correction

User feedback: mouth barely articulates, head/hands/body do not move like the supplied greeting clip; new image is a small screenshot of the clip's hands-down pose.

Evidence: v1 has no arm/body rig, head displacement below 1 degree, mouth drive scales ordinary RMS0.05 to0.246. User's video has real head/arm/torso motion; feet are outside its frame. MediaPipe detects anime face landmarks in13/13 sampled frames using existing local CPU model.

Implementation choice: use the user-supplied video as a silent body-motion texture, prepared as a forward/reverse loop to avoid a cut. Track face/mouth offline. Replace the source mouth using closed/medium/open sprites extracted from the same character, anchored to the displayed video frame and driven by current assistant output. No live inference or new TTS. Report body24 FPS separately from mouth/render FPS. 3D and mode selection stay as already approved.

- [x] RED: quiet speech articulation and actual hand/head movement.
- [x] Prepare/validate all frame anchors and same-source mouth atlas, high-resolution poster.
- [x] Render moving body with frame-aligned live mouth and stronger ordinary speech response.
- [x] Check silence, speech, interruption, loop, visibility/reduced-motion and fallback.
- [x] Capture a real browser comparison and measure cadence; run focused regressions/build/lint.

This is a correction to the authorized avatar implementation; do not restart design approvals. Do not claim a skeletal full-body rig, generated body60 FPS, visible feet, accurate phonemes or human acceptance.

Verified:44 frontend tests,13 GPU browser cases, decoded final preview. Metadata and skin-ring failures reproduced RED then fixed. Existing full-Python limits remain in the evaluation; human acceptance not inferred.
