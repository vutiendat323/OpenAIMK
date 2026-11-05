# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the service (local webcam optional); the GUI is http://localhost:9876/
python main.py

# Run all tests
python -m pytest tests/

# Run one layer's tests, one file, one test
python -m pytest tests/domain/
python -m pytest tests/domain/test_scene.py
python -m pytest tests/test_config.py::TestFromYaml::test_explicit_path_applies_overrides

# Real models on a still image, no camera (production wiring, CPU, spare port)
python tools/smoke_run.py photo.jpg --cpu --port 9877

# Camera intrinsic calibration (chessboard-based)
python tools/chessboard/calibrate.py
```

## Architecture

A **real-time face distance + anti-spoofing service** for a kiosk. The camera loop publishes frames; three worker threads each run their models at their own cadence and report to one `Scene`; the WS server reads the Scene. Nothing opens a window: the operator GUI is the web console the server serves.

Local camera open/read failures do not stop the service: `main.py` retries local capture every 2 seconds while the WS thread continues accepting remote frames. The Kiosk Remote Camera button can start video before a voice session, without a `?camera=remote` URL parameter.

### Layers and the dependency rule

Layered, with dependency inversion (ADR 0003 in the workspace `docs/adr/`):

```
presentation ──► application ──► domain ◄── infrastructure
```

| Layer | Holds | May import |
|---|---|---|
| `domain/` | `scene.py` (Scene, smoothing, the kiosk event), `geometry.py` (face/body distance, box maths), `faces.py` (`FaceDetection`) | stdlib, numpy, OpenCV **as maths only** (solvePnP, projectPoints) |
| `application/` | `ports.py` (one Protocol per model role), `state.py` (frame hand-off), `track_faces.py`, `check_liveness.py`, `measure_presence.py` | domain, `config` |
| `infrastructure/` | `faces/{scrfd,embedder,bytetrack}.py`, `spoof/minifasnet.py`, `depth/metric3d.py`, `person/yolo.py`, `camera.py` | domain, third-party — never application, presentation or `config` |
| `presentation/` | `ws_server.py`, `console.html` | application, domain, `config` — never infrastructure |

`main.py` is the composition root: it reads `config.py`, builds the infrastructure (`build_models`), hands it to the application loops (`start_workers`) and starts the presentation. It is the only module that imports every layer; `config.py` imports nothing from the service; `tools/` sit outside the layers.

**Ports are satisfied structurally.** The loops depend on `application/ports.py`; SCRFD, ByteTrack, Metric3D etc. match those Protocols without importing or inheriting them, and so do the test stand-ins. `tests/application/test_ports.py` keeps each adapter to its port. Values that cross layers (`FaceDetection`) live in the domain.

**The rule is a test.** `tests/test_architecture.py` parses every module's imports and fails on one that crosses the table above. The "OpenCV only as maths" part of the domain rule is a review convention — an import check cannot tell `solvePnP` from `VideoCapture`.

Naming: application modules say what they do, ports say the role, infrastructure is named after the technology, the domain after the business concept. `tests/` mirrors the layers; `test_imports.py` (every module imports) and `test_default_paths.py` (every configured file exists) sit at the top.

### Thread model

```
Camera loop (main.py)  ── put_frame ──►  SharedState.latest_frame
                                              │ read by
  ├── track_faces:      SCRFD → ByteTrack → PnP distance   15 Hz ─┐
  ├── check_liveness:   MiniFASNetV2 + V1SE ensemble      0.5 s ──┼──► Scene ──► presentation/ws_server.py
  └── measure_presence: YOLO11n person boxes + Metric3D    1 s  ──┘   (domain/scene.py)
```

**The loops never build models**, so the whole pipeline runs in a test with stand-ins (`tests/application/test_pipeline.py`: real loops, tracker, Scene and server; no camera, GPU or weights).

`SharedState` (`application/state.py`) is only the hand-off: the latest frame (its own lock, because a frame write is a ~0.9 MB copy), the `scene`, per-worker timings and the running flag. `put_frame()` copies (OpenCV reuses the `cap.read()` buffer); `get_latest_frame()` does **not** copy — consumers treat the frame as read-only model input.

### Scene: who is in front of the kiosk (`domain/scene.py`)

The one place that knows it. Workers push raw observations (`observe_faces`, `observe_bodies`, `observe_spoof`); readers take an immutable `SceneSnapshot` (`people`, `nearest`, `body_m`, `facing`, `event(ts)`). Choosing the nearest face, smoothing its distance, attaching a body to a face, the gate convention and the kiosk event all live here — the server only serialises, and the console is sent `nearest_id` rather than guessing. (They used to be re-derived in three places and drifted: the presence event paired the nearest distance with the id of the first-listed track.)

### Distance pipeline (face geometry → Scene)

1. **track_faces** — for every track a detection confirmed this frame, `face_distance()` (`domain/geometry.py`) solves PnP (`SOLVEPNP_SQPNP`) on the 5 SCRFD landmarks against a generic face scaled to `cfg.face_ipd_m`. Landmarks no rigid face fits (profile, occlusion: reprojection > 15% of the eye spacing) are gated out; coasting tracks get no measurement.
2. **Scene** smooths each track: a **median-of-3** drops single bad samples outright (an EMA at α=0.25 let one decay through the output for 5-7 s), then a **position-only Kalman** holds between measurements instead of extrapolating velocity (a constant-velocity model overshot a walk-then-stop by 0.14 m). Process noise accrues **per second** (0.9/s, the old 0.03 per call at 30 fps), so smoothing no longer depends on how often anything polls. Smoothers are dropped when their track disappears.

**Why not Metric3D for faces.** At a fixed 0.58 m on the kiosk's own frames it read 0.465 / 0.560 (PnP 0.569 / 0.584, IPD 0.582 / 0.588), refreshed at 1 Hz, and every per-face sample needed ROI-to-map frame pairing. PnP is exact in the pinhole model (simulated within 1% at 0-40° yaw, ±1.8 cm noise at 1 m); its one systematic error is the person's IPD against `face_ipd_m` (adult 63 ± 3.5 mm, ~5.5%).

### Body presence (YOLO + Metric3D)

Tracks come from faces, so a customer who turns away vanishes and the kiosk's
leave timer starts. `PersonDetector` (`infrastructure/person/yolo.py`, YOLO11n
filtered to the person class) runs **inside measure_presence, on the same frame
Metric3D reads**, so a box and the depth under it can never come from different
frames -- the pairing bug that made a sideways walk read 1.7-2.0 m instead of 1.0 m.

`body_distance()` (`domain/geometry.py`) keeps the middle `person_shrink` of the
box and takes the `person_depth_percentile` percentile of it: a body box holds
far more background than a face box, and a median lets that background in.

Faces keep the identity. A person box is a per-tick measurement, attached to a
track when the face box's centre sits inside it (`box_contains_center`). Every
presence event carries `body_m` (nearest person, -1.0 when none) and `facing`,
so the kiosk can tell "looked away" from "walked off"; `nearest_m` still means
the nearest face, so greeting behaviour is unchanged.

### Console (web GUI)

`presentation/console.html` is the operator GUI, served by `VisionWSServer` on the same port as the presence stream (`http://localhost:9876/`). The page sends `{"cmd": "monitor"}` and then gets an `info` event once, telemetry JSON (`_monitor_event`: per-track box, filtered and raw distance, landmarks, gate, spoof) and the camera frame as a binary JPEG at 15 Hz. It may send `{"cmd": "set"}` for the keys in `LIVE_KEYS` (`face_ipd_m`, `distance_threshold`), which are range-checked and written into the live Config. Clients that never send a command (the kiosk agent) get the presence stream, which also carries `body_m` and `facing`. It is the only GUI: nothing opens a window.

### Metric3D integration quirks (`infrastructure/depth/`)

- Metric3D code lives in a **sibling directory** `../Metric3D` (not vendored). `metric3d.py` adds it to `sys.path` at import time.
- `infrastructure/depth/_shim/mmcv/` provides a minimal `mmcv.utils` stub because Metric3D imports from it but only uses it in a commented-out function.
- The vendored Metric3D decoder modules hardcode `device="cuda"` — `DepthEstimator._patch_decoder_device()` monkey-patches `get_bins()` and `create_mesh_grid()` at init to derive the device from model parameters instead.
- The canonical-to-real depth conversion is `camera_fx * resize_scale / 1000.0`, where `resize_scale` is the keep-ratio factor that fit the frame into `metric3d_input_size` (`cfg.canonical_to_real_scale` supplies `fx / 1000`; `DepthEstimator.estimate()` multiplies in `meta["scale"]`, as Metric3D's own `hubconf.py` does). Dropping the resize factor inflated every reading by 1.56x at 308x532. The resize, pad and de-canonicalise steps are in `transforms.py`.

### Config system

`Config` is a **frozen dataclass** (`config.py`), outside the four layers; only `main.py` reads it and passes values in. Despite being frozen, calibration loading in `__post_init__` uses `object.__setattr__` to overwrite intrinsics from `tools/chessboard/calibration.npz`. YAML config discovery order: explicit path → `JARVIS_CONFIG` env var → `--config` CLI flag → `config.yml` walking up from cwd. Model weights live in `models/` (SCRFD, embedder, YOLO); the MiniFASNet weights sit beside their module in `infrastructure/spoof/pad_weights/`.

### Spoof detection

`SpoofDetector` (`infrastructure/spoof/minifasnet.py`) receives face bboxes from the tracking thread — it does **no internal face detection**. It runs a MiniFASNetV2 + MiniFASNetV1SE ensemble, summing softmax probabilities. Missing weights auto-download from GitHub. The models expect BGR input in `[0, 255]` range (no division by 255 — the original repo's custom ToTensor skips normalization).

### ByteTrack with optional ReID

`ByteTrack` (`infrastructure/faces/bytetrack.py`) implements the standard two-stage IoU association. When `FaceEmbedder` (`infrastructure/faces/embedder.py`) is available, the association cost fuses IoU with cosine similarity against a rolling gallery of stored embeddings per track (controlled by `reid_weight`).

### No distance calibration

Guided multi-point calibration and the `scale * raw + offset` correction were
removed (ADR 0001). The persisted correction was always identity, and a
correction factor hides measurement bugs instead of exposing them. The knob for
the one systematic error PnP has is `face_ipd_m`, editable live from the console.
