# Layered 2D Rig Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the pasted-mouth 2D hybrid with one continuous rig of Nhân vật Trend, proven first by a face-only trial the user can watch.

**Architecture:** An offline script cuts one clip frame into a body layer, a head layer and mouth interior, and measures mouth shape targets as landmark offsets from real clip frames. A WebGL2 renderer deforms one head mesh from those targets, so lips, cheeks and chin stay one image. The trial is a standalone page; the kiosk changes only after the user accepts it.

**Tech Stack:** Python with OpenCV and MediaPipe in `.runtime/livetalking-venv`; WebGL2; Playwright with Chromium for real browser recording.

**Spec:** `docs/superpowers/specs/2026-10-31-layered-2d-rig-design.md`

## Global Constraints

- Identity `image.png_3ae5f671.jpg`; motion and source pixels from `Woman_greeting_customers_at_counter_b58d415e_1080p.mp4`.
- At least 30 display FPS, aiming for 60. No GPU upgrade.
- Output audio only. No microphone, transcript, paid service or generated art.
- Hidden areas use colour fill and neighbouring pixels only.
- Small head turns only. Silence means a closed, still mouth.
- Maximum two correction rounds on the face after the first trial.
- Fixtures only: no merchant orders, payments or printer jobs. Managed services stay stopped.
- No root Git repository: skip commit steps.
- The existing kiosk 2D, 3D mode and native voice stay unchanged until stage 4.

## Review Focus

- Mouth during a pause inside speech: closes within about 150 ms, then stays still.
- Mouth opening to its maximum: no stretched skin, torn lips or visible mesh edges.
- Head at its turn limit: no doubled hair edge or wall gap around the neck.
- Blink during speech: eyes and mouth stay independent, with no ghost eyes.
- Different voice loudness: quiet speech still articulates and loud speech does not saturate.

---

## Stage 1: Face trial

### Task 1: Cut layers and measure mouth targets

**Files:**
- Create: `scripts/prepare_2d_rig.py`
- Output: `output/avatar-quality-review/rig-trial/assets/`

**Interfaces:**
- Produces: `body.png`, `head.png` (RGBA), `blink.png`, `mouth.png`, and `rig.json` with `width`, `height`, `points` (rest vertices), `triangles`, `interior` (inner-lip indices), `targets` (`open`, `round`, `spread` offset arrays), `pivot`.

- [ ] **Step 1:** Choose a closed-mouth, frontal, hands-clasped frame after the camera settles, and a closed-eye frame.
- [ ] **Step 2:** Implement `prepare(source, output)`: wall-colour matte, head mask above the collar, body layer with the head removed and the neck extended by inpainting.
- [ ] **Step 3:** Align target frames to the rest frame from eyes and nose. Keep offsets for lip and chin landmarks only, averaged over nearby frames to reduce landmark noise.
- [ ] **Step 4:** Triangulate the landmarks plus an outer head grid, leaving the inner-lip polygon empty.
- [ ] **Step 5:** Run it and inspect a debug overlay. Expected: mesh follows the lips, with no jagged lip offsets.

### Task 2: Render and drive the trial

**Files:**
- Create: `output/avatar-quality-review/rig-trial/index.html`, `rig.js`, `record.py`

**Interfaces:**
- Consumes: Task 1 assets.
- Produces: `canvas.dataset.fps`, `window.rigState` with `open`, `round`, `spread`, `blink`, and `preview.mp4`.

- [ ] **Step 1:** Draw body, mouth interior, then the head mesh in WebGL2.
- [ ] **Step 2:** Drive target weights from a real AnalyserNode on Maple audio: level for opening, spectral centroid for round or spread. Add head nod on phrase onset, small idle sway and blinking.
- [ ] **Step 3:** Record in GPU Chromium with speech, an interruption and rest.
- [ ] **Step 4:** Check: FPS at least 30, mouth still and closed in silence, and close-ups at maximum opening, head limit and blink.

### Task 3: First gate

- [ ] **Step 1:** Encode the preview and show the user. Stop for their verdict. Up to two correction rounds follow; after that, stop and discuss hiring an artist and Live2D rigger.

## Later stages, only after acceptance

- **Stage 2, body:** breathing, shoulders, rest motion, hair lag, long sessions and interruption.
- **Stage 3, hands:** clasped and open poses, clip frames for the transition, a trigger after about 1–2 seconds of sustained speech, and a smooth return on interruption.
- **Stage 4, kiosk:** move the renderer into `Avatar2D`/`avatar2d.ts`, keep the `read()` contract, remove the hybrid, add browser tests for poster fallback, reduced motion and context loss, and update evidence.

These stages get detailed tasks after the face gate, because the renderer may change.
