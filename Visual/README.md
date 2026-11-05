# Vision: Face Distance & Anti-Spoofing Monitor

Real-time computer vision system that monitors a live camera stream and answers two key questions:
> **"How far is each face from the camera?"**
> **"Is that face REAL or a presentation attack (spoof)?"**

This module is designed as an asynchronous, multi-threaded pipeline to ensure a smooth camera feed even when heavy AI models are running in the background.

## 🏗 Pipeline Architecture

A camera loop and three worker threads; every worker reports to one `Scene`, which the WebSocket server reads:

```text
Camera loop ──► latest frame
  ├──> Track loop    (SCRFD + ByteTrack + PnP)   ──┐
  ├──> Spoof loop    (MiniFASNet ensemble)        ──┼──> Scene ──> WS server ──> kiosk events
  └──> Presence loop (YOLO11n + Metric3Dv2)      ──┘                        └──> web console (http://localhost:9876/)
```

- **SCRFD** detects faces with high accuracy.
- **ByteTrack** assigns a unique tracking ID to each face across frames.
- **Metric3Dv2** (ViT-Small) produces a full-frame metric depth map.
- **MiniFASNet Ensemble** (V2 + V1SE) classifies each face as a live human or a spoof (printed photo, screen replay).
- **Face distance**: `face_distance()` solves PnP on the 5 SCRFD landmarks against a generic face scaled to `face_ipd_m` (63 mm), at tracker rate. Metric3D, paired with YOLO11n person boxes in the depth thread, measures **bodies** instead, so a customer who turns away is still seen (`body_m`).
- **Scene** (`domain/scene.py`): smooths those distances (median-of-3, position-only Kalman), picks the nearest face, attaches bodies, and builds the kiosk event — one place, read by the server and console.

## 📂 Project Structure

Four layers, one dependency rule — `presentation → application → domain ← infrastructure` —
enforced by `tests/test_architecture.py`:

```text
Visual/
├── main.py                    # Composition root: builds models, starts workers, camera loop
├── config.py                  # Configuration (frozen dataclass), outside the layers
│
├── domain/                    # What the kiosk believes — imports only stdlib, numpy, OpenCV maths
│   ├── scene.py               # Scene: people, smoothing, the kiosk event
│   ├── geometry.py            # Face distance (PnP), body distance, box maths
│   └── faces.py               # FaceDetection
│
├── application/               # The three jobs, and the ports the models satisfy
│   ├── ports.py               # One Protocol per model role
│   ├── state.py               # SharedState (frame hand-off, timings)
│   ├── track_faces.py         # SCRFD → ByteTrack → PnP distance
│   ├── check_liveness.py      # MiniFASNet spoof tags
│   └── measure_presence.py    # YOLO person boxes + Metric3D depth
│
├── infrastructure/            # The technologies, one package each
│   ├── faces/                 # scrfd.py, embedder.py (ReID), bytetrack.py
│   ├── spoof/                 # minifasnet.py + model definitions + weights
│   ├── depth/                 # metric3d.py, transforms.py, mmcv shim
│   ├── person/                # yolo.py
│   └── camera.py              # Opening the camera, undistortion
│
├── presentation/              # ws_server.py (kiosk events, console) + console.html
│
├── models/                    # SCRFD, embedder and YOLO weights
├── tests/                     # domain/ application/ infrastructure/ presentation/ + architecture, imports, default paths
└── tools/                     # evaluate_all.py, smoke_run.py, chessboard/ calibration
```

## ⚙️ Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Download SCRFD model

```bash
mkdir -p models
python3 -c "
import urllib.request
url = 'https://github.com/deepinsight/insightface/releases/download/v0.7/scrfd_2.5g.onnx'
urllib.request.urlretrieve(url, 'models/scrfd_2.5g.onnx')
print('Done')
"
```

### 3. Metric3D code

The Metric3D repository must be alongside this project:

```text
jarvis/
├── Visual/       ← this project
└── Metric3D/     ← Metric3D code
```

### 4. Weights

Weights are downloaded automatically on the first run from HuggingFace (Metric3D) and GitHub (MiniFASNet PAD).

## 🚀 Usage

```bash
cd Visual/
python main.py
```

Nothing opens a window: the operator console is http://localhost:9876/. `Ctrl+C` stops the service.

Without a camera, `python tools/smoke_run.py photo.jpg --cpu` runs the real models on a still image
and serves the console on port 9877.

## 🛠 Configuration

All settings are centralized in `config.py`. Key parameters include:

| Parameter | Default | Description |
|---|---|---|
| `camera_id` | `0` | Webcam device index |
| `camera_fx` | `500.0` | Focal length (px) — calibrate for accuracy |
| `scrfd_model` | `models/scrfd_2.5g.onnx` | Path to SCRFD ONNX model |
| `depth_interval_sec` | `1.0` | Seconds between depth maps |
| `async_detect/depth` | `True` | Run detection/depth in background threads |
| `distance_threshold` | `1.0` | Red/Green threshold (meters) |
| `spoof_enabled` | `True` | Enable spoof detection |
| `spoof_interval_sec` | `2.0` | Spoof check interval per face |

## 💻 Visualisation Legend
- 🟢 **GREEN box** = Real face, distance ≥ threshold (e.g., 1m)
- 🔴 **RED box** = Real face, distance < threshold
- 🟠 **ORANGE box + "SPOOF!"** = Presentation attack detected

## 📊 Evaluation

The `tools/evaluate_all.py` script evaluates the AI models using your test data.

### Supported Evaluations
1. **Face Detection** — SCRFD 2.5G ONNX (Precision, Recall, F1)
2. **Spoof Detection** — MiniFASNet Ensemble (APCER, BPCER, HTER, AUC)
3. **Depth Estimation** — Metric3D (MAE, RMSE, AbsRel)

### Run Commands
```bash
python3 tools/evaluate_all.py                    # run all evals that have data
python3 tools/evaluate_all.py --face             # only face detection
python3 tools/evaluate_all.py --spoof            # only spoof
python3 tools/evaluate_all.py --depth            # only depth
python3 tools/evaluate_all.py --capture-spoof    # spoof test set capture tool
python3 tools/evaluate_all.py --capture-depth    # depth test set capture tool
```

### Test Data Directory Structure
Create an `eval_data/` directory in the `Visual/` folder:
```text
eval_data/
├── face_detection/
│   ├── images/         # any .jpg/.png images
│   └── labels/         # .txt file with the same name, each line: x1 y1 x2 y2 (pixel)
│
├── spoof/
│   ├── real/           # REAL face images (crop or full frame)
│   ├── fake_print/     # printed face images
│   └── fake_replay/    # face images on phone/computer screen
│
└── depth/
    ├── images/         # images taken at known distances
    └── ground_truth.json  # {"img.jpg": {"bbox": [x1,y1,x2,y2], "distance_m": 1.50}}
```

## 📋 Requirements
- Python ≥ 3.10
- CUDA-capable GPU highly recommended
- Webcam
