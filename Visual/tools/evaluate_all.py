#!/usr/bin/env python3
"""
Evaluate the entire pipeline with specific metrics.
See README.md for instructions on directory structure and usage.
"""

from __future__ import annotations

import argparse
import json
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ── Ensure import from root ──────────────────────────────────

from Visual.config import Config
from Visual.infrastructure.faces.scrfd import SCRFDFaceDetector
from Visual.domain.faces import FaceDetection
from Visual.infrastructure.spoof.minifasnet import SpoofDetector
from Visual.infrastructure.depth.transforms import sample_depth_at_bbox


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _compute_iou(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
    """IoU between 2 boxes (x1, y1, x2, y2)."""
    xa, ya = max(a[0], b[0]), max(a[1], b[1])
    xb, yb = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, xb - xa) * max(0.0, yb - ya)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 1e-8 else 0.0


def _load_face_labels(label_dir: Path, image_name: str) -> List[Tuple[float, float, float, float]]:
    """Load ground truth face boxes from .txt file."""
    label_path = label_dir / f"{Path(image_name).stem}.txt"
    if not label_path.exists():
        return []
    boxes = []
    with open(label_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            if len(parts) >= 4:
                boxes.append(tuple(float(p) for p in parts[:4]))
    return boxes


def _section(title: str) -> None:
    """Print section title."""
    w = 60
    print(f"\n{'='*w}")
    print(f"  {title}")
    print(f"{'='*w}")


def _metric_line(label: str, value: str, target: str = "") -> None:
    """Print a metric line with nice formatting."""
    if target:
        print(f"  {label:<22s} {value:<14s}  (target: {target})")
    else:
        print(f"  {label:<22s} {value}")


def _verdict(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


# ═══════════════════════════════════════════════════════════════════════════
# 1. FACE DETECTION EVALUATION
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_face_detection(cfg: Config, data_dir: Path) -> dict:
    """
    Evaluate SCRFD face detector.

    Requires: eval_data/face_detection/images/ + labels/

    Returns dict with precision, recall, f1, tp, fp, fn, avg_conf, num_images.
    """
    images_dir = data_dir / "face_detection" / "images"
    labels_dir = data_dir / "face_detection" / "labels"

    if not images_dir.exists() or not labels_dir.exists():
        return {"error": "missing_data",
                "msg": f"Missing {images_dir} or {labels_dir}"}

    image_files = sorted(
        list(images_dir.glob("*.jpg")) +
        list(images_dir.glob("*.png")) +
        list(images_dir.glob("*.jpeg"))
    )
    if not image_files:
        return {"error": "no_images", "msg": f"No images in {images_dir}"}

    print(f"\n  Loading SCRFD detector (320×320, {cfg.device}) …")
    detector = SCRFDFaceDetector(
        model_path=cfg.scrfd_model,
        conf_thresh=cfg.scrfd_conf,
        nms_thresh=cfg.scrfd_nms,
        input_size=cfg.scrfd_input_size,
        device=cfg.device,
    )
    detector.warmup()

    tp, fp, fn = 0, 0, 0
    total_gt = 0
    total_det = 0
    all_confidences = []
    per_image_results = []
    total_time_ms = 0.0

    print(f"  Evaluating {len(image_files)} images …")

    for img_path in image_files:
        frame = cv2.imread(str(img_path))
        if frame is None:
            continue

        # Load ground truth
        gt_boxes = _load_face_labels(labels_dir, img_path.name)
        total_gt += len(gt_boxes)

        # Detect
        t0 = time.perf_counter()
        detections = detector.detect(frame)
        dt = (time.perf_counter() - t0) * 1000.0
        total_time_ms += dt
        total_det += len(detections)

        # Match detections ↔ ground truth (greedy)
        matched_gt: set = set()
        for det in detections:
            best_iou, best_gt_idx = 0.0, -1
            for i, gt in enumerate(gt_boxes):
                if i in matched_gt:
                    continue
                iou_val = _compute_iou(det.bbox, gt)
                if iou_val > best_iou:
                    best_iou, best_gt_idx = iou_val, i
            if best_iou >= 0.5 and best_gt_idx not in matched_gt:
                tp += 1
                matched_gt.add(best_gt_idx)
                all_confidences.append(det.confidence)
            else:
                fp += 1

        fn += len(gt_boxes) - len(matched_gt)
        per_image_results.append({
            "file": img_path.name,
            "gt": len(gt_boxes),
            "det": len(detections),
            "matched": len(matched_gt),
        })

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    avg_conf = float(np.mean(all_confidences)) if all_confidences else 0.0
    avg_time_ms = total_time_ms / len(image_files) if image_files else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp, "fp": fp, "fn": fn,
        "total_gt": total_gt,
        "total_det": total_det,
        "num_images": len(image_files),
        "avg_confidence": avg_conf,
        "avg_time_ms": avg_time_ms,
        "per_image": per_image_results,
    }


def _print_face_results(r: dict) -> None:
    _section("FACE DETECTION — SCRFD 2.5G (320×320)")
    if "error" in r:
        print(f"\n  [WARN]  {r['msg']}")
        _print_face_data_instructions()
        return

    _metric_line("Images tested", str(r["num_images"]))
    _metric_line("Ground truth faces", str(r["total_gt"]))
    _metric_line("Detected faces", str(r["total_det"]))
    _metric_line("True positives (TP)", str(r["tp"]))
    _metric_line("False positives (FP)", str(r["fp"]))
    _metric_line("False negatives (FN)", str(r["fn"]))
    print(f"  {'─'*50}")
    _metric_line("Precision", f"{r['precision']:.3f}", "> 0.85")
    _metric_line("Recall", f"{r['recall']:.3f}", "> 0.80")
    _metric_line("F1 Score", f"{r['f1']:.3f}", "> 0.82")
    _metric_line("Avg confidence", f"{r['avg_confidence']:.3f}")
    _metric_line("Avg inference", f"{r['avg_time_ms']:.1f} ms", "< 10 ms")
    print(f"  {'─'*50}")
    print(f"  Verdict:")
    print(f"    Precision: {_verdict(r['precision'] >= 0.85)} "
          f"{'Good' if r['precision'] >= 0.85 else 'Needs improvement'}")
    print(f"    Recall:    {_verdict(r['recall'] >= 0.80)} "
          f"{'Good' if r['recall'] >= 0.80 else 'Needs improvement'}")
    print(f"    F1:        {_verdict(r['f1'] >= 0.82)} "
          f"{'Good' if r['f1'] >= 0.82 else 'Needs improvement'}")


def _print_face_data_instructions() -> None:
    """Print instructions to create face detection test data."""
    print(f"""
  HOW TO CREATE TEST DATA:

  1. Capture 50-100 images from webcam:
       python3 evaluate_all.py --capture-faces

  2. Label manually with labelImg:
       pip install labelImg
       labelImg eval_data/face_detection/images/ eval_data/face_detection/labels.txt
       # Choose YOLO format, draw boxes around each face
       # Each image → 1 .txt file in labels/

  3. Re-run evaluate:
       python3 evaluate_all.py --face
""")


# ═══════════════════════════════════════════════════════════════════════════
# 2. SPOOF DETECTION EVALUATION
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_spoof(cfg: Config, data_dir: Path) -> dict:
    """
    Evaluate MiniFASNet ensemble spoof detection.

    Supports 2 modes:
      A) Face crops: real/, fake_print/, fake_replay/ folders contain pre-cropped
         face images → evaluate MiniFASNet directly (independent of SCRFD)
      B) Full images: folder with images_full/ subfolder contains full images
         → use SCRFD to crop face before evaluating

    Returns dict with apcer, bpcer, hter, auc, eer, per_class_scores.
    """
    spoof_dir = data_dir / "spoof"

    if not spoof_dir.exists():
        return {"error": "missing_data",
                "msg": f"Missing {spoof_dir}"}

    # Detect mode: face crops or full images
    real_dir = spoof_dir / "real"
    fake_print_dir = spoof_dir / "fake_print"
    fake_replay_dir = spoof_dir / "fake_replay"

    use_full_images = (spoof_dir / "images_full").exists()

    # Check if directory exists
    real_images = _list_images(real_dir)
    fake_print_images = _list_images(fake_print_dir) if fake_print_dir.exists() else []
    fake_replay_images = _list_images(fake_replay_dir) if fake_replay_dir.exists() else []

    if not real_images and not use_full_images:
        return {"error": "no_real_images",
                "msg": f"No real images in {real_dir}/"}

    fake_print_images = _list_images(fake_print_dir) if fake_print_dir.exists() else []
    fake_replay_images = _list_images(fake_replay_dir) if fake_replay_dir.exists() else []
    all_fake = fake_print_images + fake_replay_images

    if not all_fake and not use_full_images:
        return {"error": "no_fake_images",
                "msg": f"No fake images in {fake_print_dir}/ or {fake_replay_dir}/"}

    n_real = len(real_images)
    n_fake = len(all_fake)
    n_print = len(fake_print_images)
    n_replay = len(fake_replay_images)

    print(f"\n  Mode: {'Full images (SCRFD crop)' if use_full_images else 'Face crops (direct)'}")
    print(f"  Real samples:  {n_real}")
    print(f"  Fake samples:  {n_fake}  (print: {n_print}, replay: {n_replay})")

    # Load spoof detector
    print(f"  Loading MiniFASNet ensemble ({cfg.device}) …")
    spoof = SpoofDetector(
        pad_live_threshold=cfg.spoof_live_threshold,
        device=cfg.device,
    )
    spoof.prepare()

    # Load face detector if using full images
    face_det = None
    if use_full_images:
        face_det = SCRFDFaceDetector(
            model_path=cfg.scrfd_model,
            conf_thresh=cfg.scrfd_conf,
            nms_thresh=cfg.scrfd_nms,
            input_size=cfg.scrfd_input_size,
            device=cfg.device,
        )
        face_det.warmup()

    # ── Evaluate REAL ──
    print(f"\n  Testing REAL faces ({n_real} images) …")
    real_scores = []
    real_timing = []
    for img_path in real_images:
        crop = _get_face_crop(img_path, face_det)
        if crop is None:
            continue
        t0 = time.perf_counter()
        _, score, _ = spoof.predict(crop)
        real_timing.append((time.perf_counter() - t0) * 1000.0)
        real_scores.append(score)

    # ── Evaluate FAKE ──
    print(f"  Testing FAKE faces ({n_fake} images) …")
    fake_scores = []
    fake_types = []  # "print" or "replay"
    fake_timing = []
    for img_path in fake_print_images:
        crop = _get_face_crop(img_path, face_det)
        if crop is None:
            continue
        t0 = time.perf_counter()
        _, score, _ = spoof.predict(crop)
        fake_timing.append((time.perf_counter() - t0) * 1000.0)
        fake_scores.append(score)
        fake_types.append("print")
    for img_path in fake_replay_images:
        crop = _get_face_crop(img_path, face_det)
        if crop is None:
            continue
        t0 = time.perf_counter()
        _, score, _ = spoof.predict(crop)
        fake_timing.append((time.perf_counter() - t0) * 1000.0)
        fake_scores.append(score)
        fake_types.append("replay")

    n_real_eval = len(real_scores)
    n_fake_eval = len(fake_scores)

    if n_real_eval == 0 or n_fake_eval == 0:
        return {"error": "no_faces_found",
                "msg": "No faces found to crop (check images or SCRFD)"}

    # ── Metrics ──
    real_arr = np.array(real_scores)
    fake_arr = np.array(fake_scores)

    # APCER / BPCER at default threshold (0.5)
    apcer_default = float(np.mean(fake_arr >= 0.5))  # fake accepted as real
    bpcer_default = float(np.mean(real_arr < 0.5))    # real rejected as fake
    hter_default = (apcer_default + bpcer_default) / 2.0

    # Find optimal threshold (min HTER)
    thresholds = np.arange(0.0, 1.01, 0.02)
    best_hter, best_thresh = 1.0, 0.5
    best_apcer, best_bpcer = 0.0, 0.0

    for t in thresholds:
        apcer = float(np.mean(fake_arr >= t))
        bpcer = float(np.mean(real_arr < t))
        hter = (apcer + bpcer) / 2.0
        if hter < best_hter:
            best_hter, best_thresh = hter, t
            best_apcer, best_bpcer = apcer, bpcer

    # AUC
    try:
        from sklearn.metrics import roc_auc_score
        y_true = [1] * n_real_eval + [0] * n_fake_eval
        y_scores = real_scores + fake_scores
        auc = float(roc_auc_score(y_true, y_scores))
    except ImportError:
        auc = -1.0

    # EER (point where APCER ≈ BPCER)
    diffs = []
    for t in thresholds:
        ap = float(np.mean(fake_arr >= t))
        bp = float(np.mean(real_arr < t))
        diffs.append(abs(ap - bp))
    eer_idx = int(np.argmin(diffs))
    eer = float((float(np.mean(fake_arr >= thresholds[eer_idx])) +
                 float(np.mean(real_arr < thresholds[eer_idx]))) / 2.0)

    # Per-attack-type breakdown
    per_type = {}
    if n_print > 0:
        print_scores = [s for s, t in zip(fake_scores, fake_types) if t == "print"]
        per_type["print_APCER"] = float(np.mean(np.array(print_scores) >= 0.5)) if print_scores else 0.0
    if n_replay > 0:
        replay_scores = [s for s, t in zip(fake_scores, fake_types) if t == "replay"]
        per_type["replay_APCER"] = float(np.mean(np.array(replay_scores) >= 0.5)) if replay_scores else 0.0

    avg_time = float(np.mean(real_timing + fake_timing)) if (real_timing or fake_timing) else 0.0

    return {
        "n_real": n_real_eval,
        "n_fake": n_fake_eval,
        "n_print": n_print,
        "n_replay": n_replay,
        "APCER@0.5": apcer_default,
        "BPCER@0.5": bpcer_default,
        "HTER@0.5": hter_default,
        "best_threshold": best_thresh,
        "best_APCER": best_apcer,
        "best_BPCER": best_bpcer,
        "best_HTER": best_hter,
        "AUC": auc,
        "EER": eer,
        "real_mean_score": float(np.mean(real_arr)),
        "fake_mean_score": float(np.mean(fake_arr)),
        "avg_time_ms": avg_time,
        "per_type": per_type,
    }


def _get_face_crop(img_path: Path, face_detector) -> Optional[np.ndarray]:
    """
    Get face crop from image.
    - If face_detector is None: image is already a crop → read directly
    - Otherwise: use SCRFD to detect and crop largest face
    """
    img = cv2.imread(str(img_path))
    if img is None:
        return None

    if face_detector is None:
        # Image is already a face crop — use directly
        return img

    # Full image — need to detect face
    faces = face_detector.detect(img)
    if not faces:
        return None

    # Get largest face (highest confidence)
    best = max(faces, key=lambda f: f.confidence)
    x1, y1, x2, y2 = [int(v) for v in best.bbox]
    h, w = img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 + 8 or y2 <= y1 + 8:
        return None
    return img[y1:y2, x1:x2]


def _list_images(directory: Path) -> List[Path]:
    """List all images in directory."""
    if not directory.exists():
        return []
    result = []
    for ext in ("*.jpg", "*.png", "*.jpeg", "*.bmp"):
        result.extend(sorted(directory.glob(ext)))
    return result


def _print_spoof_results(r: dict) -> None:
    _section("SPOOF DETECTION — MiniFASNet Ensemble (V2 + V1SE)")

    if "error" in r:
        print(f"\n  [WARN]  {r['msg']}")
        _print_spoof_data_instructions()
        return

    _metric_line("Real samples", str(r["n_real"]))
    _metric_line("Fake samples", str(r["n_fake"]),
                 f"(print: {r.get('n_print',0)}, replay: {r.get('n_replay',0)})")
    print()

    # ── Accuracy at default threshold (0.5) ──
    print("  ── Default threshold (0.50) ──")
    _metric_line("APCER (Fake→Real)", f"{r['APCER@0.5']:.4f}", "< 0.10")
    _metric_line("BPCER (Real→Fake)", f"{r['BPCER@0.5']:.4f}", "< 0.10")
    _metric_line("HTER", f"{r['HTER@0.5']:.4f}", "< 0.10")
    print()

    # ── Optimal threshold ──
    print(f"  ── Optimal threshold ({r['best_threshold']:.2f}) ──")
    _metric_line("APCER", f"{r['best_APCER']:.4f}")
    _metric_line("BPCER", f"{r['best_BPCER']:.4f}")
    _metric_line("HTER (min)", f"{r['best_HTER']:.4f}", "< 0.10")
    print()

    # ── AUC & EER ──
    if r["AUC"] >= 0:
        _metric_line("AUC", f"{r['AUC']:.4f}", "> 0.90")
    else:
        _metric_line("AUC", "N/A (requires sklearn)", "")
    _metric_line("EER", f"{r['EER']:.4f}", "< 0.10")
    print()

    # ── Score distribution ──
    _metric_line("Real mean score", f"{r['real_mean_score']:.4f}")
    _metric_line("Fake mean score", f"{r['fake_mean_score']:.4f}")
    print()

    # ── Per attack type ──
    if r.get("per_type"):
        print("  ── Per attack type ──")
        for k, v in r["per_type"].items():
            _metric_line(f"  {k}", f"{v:.4f}")

    _metric_line("Avg time/face", f"{r['avg_time_ms']:.1f} ms", "< 10 ms")
    print(f"  {'─'*50}")

    # ── Verdict ──
    print(f"  Verdict:")
    hter = r['best_HTER']
    auc = r['AUC']
    if hter < 0.10 and (auc < 0 or auc > 0.90):
        print(f"    [EXCELLENT] — HTER < 0.10, ready for production")
    elif hter < 0.15:
        print(f"    [GOOD] — HTER < 0.15, acceptable")
    elif hter < 0.25:
        print(f"    [WARN]  AVERAGE — HTER < 0.25, needs improvement")
    else:
        print(f"    [POOR] — HTER ≥ 0.25, model is not effective")

    # ── Recommendation ──
    if r["best_threshold"] < 0.35 or r["best_threshold"] > 0.65:
        print(f"\n  [TIP] Change spoof_live_threshold from 0.50 → {r['best_threshold']:.2f}")
        print(f"     in config.py to achieve HTER = {r['best_HTER']:.4f}")


def _print_spoof_data_instructions() -> None:
    """Print instructions to create spoof test data."""
    print(f"""
  HOW TO CREATE TEST DATA:

  Fastest way — use integrated tool:
       python3 evaluate_all.py --capture-spoof

  Or do it manually:
  1. Create folder eval_data/spoof/
  2. Capture 30 REAL face images → put into real/
  3. Print face images on paper, capture via webcam → fake_print/
  4. Display face image/video on phone, capture via webcam → fake_replay/

  Image format: .jpg or .png, cropped face or full frame are both fine
  (if full frame, script will auto-detect face using SCRFD)
""")


# ═══════════════════════════════════════════════════════════════════════════
# 3. DEPTH ESTIMATION EVALUATION
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_depth(cfg: Config, data_dir: Path) -> dict:
    """
    Evaluate Metric3D depth estimation.

    Requires: eval_data/depth/images/ + ground_truth.json

    ground_truth.json format:
    {
      "frame_1m.jpg": {"bbox": [200, 150, 300, 400], "distance_m": 1.0},
      "frame_2m.jpg": {"bbox": [180, 100, 250, 350], "distance_m": 2.0}
    }

    Returns dict with mae, rmse, absrel, delta1, per_sample errors.
    """
    depth_dir = data_dir / "depth"
    images_dir = depth_dir / "images"
    gt_file = depth_dir / "ground_truth.json"

    if not images_dir.exists() or not gt_file.exists():
        return {"error": "missing_data",
                "msg": f"Missing {images_dir} or {gt_file}"}

    with open(gt_file) as f:
        ground_truth = json.load(f)

    if not ground_truth:
        return {"error": "empty_gt", "msg": "ground_truth.json is empty"}

    print(f"\n  Test samples: {len(ground_truth)}")
    print(f"  Loading Metric3D ({cfg.metric3d_variant}, {cfg.device}) …")

    from Visual.infrastructure.depth.metric3d import DepthEstimator
    depth_est = DepthEstimator(
        cfg.metric3d_variant, cfg.device, use_half=cfg.metric3d_half,
    )

    errors_abs = []
    errors_rel = []
    details = []
    total_time_ms = 0.0

    print(f"  Estimating depth …")

    for img_name, info in ground_truth.items():
        img_path = images_dir / img_name
        if not img_path.exists():
            print(f"    [WARN]  Missing: {img_name}")
            continue

        true_dist = info["distance_m"]
        bbox = tuple(info["bbox"])  # (x1, y1, x2, y2)

        frame = cv2.imread(str(img_path))
        if frame is None:
            continue
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        t0 = time.perf_counter()
        depth_map = depth_est.estimate(
            frame_rgb, cfg.intrinsics, cfg.canonical_to_real_scale,
        )
        dt = (time.perf_counter() - t0) * 1000.0
        total_time_ms += dt

        pred = sample_depth_at_bbox(depth_map, bbox, method="center")
        # Apply calibration correction if configured
        abs_err = abs(pred - true_dist)
        rel_err = abs_err / true_dist if true_dist > 0 else 0.0

        errors_abs.append(abs_err)
        errors_rel.append(rel_err)
        details.append({
            "image": img_name,
            "true_m": true_dist,
            "pred_m": round(float(pred), 3),
            "abs_err_m": round(abs_err, 3),
            "rel_err": round(rel_err, 4),
            "bbox": list(bbox),
        })

    n = len(errors_abs)
    if n == 0:
        return {"error": "no_valid", "msg": "No valid images"}

    abs_arr = np.array(errors_abs)
    rel_arr = np.array(errors_rel)

    mae = float(np.mean(abs_arr))
    rmse = float(np.sqrt(np.mean(abs_arr ** 2)))
    absrel = float(np.mean(rel_arr))
    delta1 = float(np.mean((np.maximum(
        np.array([d["true_m"] for d in details]),
        np.array([d["pred_m"] for d in details]),
    ) / np.minimum(
        np.array([d["true_m"] for d in details]),
        np.array([d["pred_m"] for d in details]),
    )) < 1.25))

    avg_time = total_time_ms / n if n > 0 else 0.0

    return {
        "n_samples": n,
        "MAE_m": mae,
        "RMSE_m": rmse,
        "AbsRel": absrel,
        "delta_1_25": delta1,
        "avg_time_ms": avg_time,
        "details": details,
    }


def _print_depth_results(r: dict) -> None:
    _section("DEPTH ESTIMATION — Metric3D ViT-Small")

    if "error" in r:
        print(f"\n  [WARN]  {r['msg']}")
        _print_depth_data_instructions()
        return

    _metric_line("Samples", str(r["n_samples"]))
    print()
    _metric_line("MAE (Mean Abs Error)", f"{r['MAE_m']:.3f} m", "< 0.50 m")
    _metric_line("RMSE", f"{r['RMSE_m']:.3f} m", "< 1.00 m")
    _metric_line("AbsRel", f"{r['AbsRel']:.4f}", "< 0.15")
    _metric_line("δ < 1.25", f"{r['delta_1_25']:.3f}", "> 0.80")
    _metric_line("Avg inference", f"{r['avg_time_ms']:.0f} ms", "< 600 ms")
    print(f"  {'─'*50}")

    # Per-sample details
    print(f"\n  ── Per-sample breakdown ──")
    print(f"  {'Image':<25s} {'True':>8s} {'Pred':>8s} {'AbsErr':>8s} {'RelErr':>8s}")
    print(f"  {'─'*25} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
    for d in r.get("details", []):
        print(f"  {d['image']:<25s} {d['true_m']:>6.2f}m  {d['pred_m']:>6.2f}m  "
              f"{d['abs_err_m']:>6.3f}m  {d['rel_err']:>7.4f}")

    print(f"\n  Verdict:")
    ok_mae = r['MAE_m'] < 0.50
    ok_rmse = r['RMSE_m'] < 1.00
    ok_delta = r['delta_1_25'] > 0.80
    if ok_mae and ok_rmse and ok_delta:
        print(f"    [GOOD] — Meets all 3 criteria")
    else:
        print(f"    [WARN]  MAE: {'OK' if ok_mae else 'POOR'}, "
              f"RMSE: {'OK' if ok_rmse else 'POOR'}, "
              f"δ<1.25: {'OK' if ok_delta else 'POOR'}")
        print(f"    Possible causes:")
        if not ok_mae:
            print(f"      - Camera not calibrated → run tools/chessboard/calibrate.py")
        print(f"      - Metric3D is inaccurate at close/far distances")
        print(f"      - Should use depth method='median' instead of 'center'")


def _print_depth_data_instructions() -> None:
    """Print instructions to create depth test data."""
    print(f"""
  HOW TO CREATE TEST DATA:

  Use integrated tool:
       python3 evaluate_all.py --capture-depth

  Or manually:
  1. Fix the camera position, use a measuring tape/laser measure
  2. Stand at distances: 1m, 2m, 3m, 5m
  3. Capture images at each position (using cv2.imwrite or screenshot)
  4. Write face bbox coordinates + true distance into ground_truth.json
""")


# ═══════════════════════════════════════════════════════════════════════════
# 4. CAPTURE TOOLS — Support creating test data
# ═══════════════════════════════════════════════════════════════════════════

def capture_spoof_test_data(cfg: Config) -> None:
    """
    Interactive tool to capture images for spoof evaluation.

    Instructions:
      - Press R → capture REAL image (your face in front of webcam)
      - Press P → capture FAKE_PRINT image (printed on paper)
      - Press M → capture FAKE_REPLAY image (on screen)
      - Press Q → exit
    """
    import os
    data_dir = Path(_THIS_DIR) / "eval_data" / "spoof"
    for subdir in ["real", "fake_print", "fake_replay"]:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Count existing images to continue numbering
    counters = {
        "real": len(_list_images(data_dir / "real")),
        "fake_print": len(_list_images(data_dir / "fake_print")),
        "fake_replay": len(_list_images(data_dir / "fake_replay")),
    }

    cap = cv2.VideoCapture(cfg.camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera_height)

    current_mode = "real"

    print(f"\n  [CAM] SPOOF TEST DATA CAPTURE")
    print(f"  {'─'*50}")
    print(f"  Shortcuts:")
    print(f"    R = REAL mode (real face)")
    print(f"    P = FAKE_PRINT mode (printed image)")
    print(f"    M = FAKE_REPLAY mode (on screen)")
    print(f"    SPACE = Capture image")
    print(f"    Q/ESC = Exit")
    print(f"  {'─'*50}\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Display current mode
        mode_colors = {"real": (0, 255, 0), "fake_print": (0, 165, 255),
                       "fake_replay": (0, 0, 255)}
        color = mode_colors[current_mode]

        h, w = frame.shape[:2]
        # Draw ROI box in the center (suggested face position)
        roi_w, roi_h = 200, 250
        rx1, ry1 = (w - roi_w) // 2, (h - roi_h) // 2
        rx2, ry2 = rx1 + roi_w, ry1 + roi_h
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), color, 2)

        # Label
        label = f"MODE: {current_mode.upper()} | {counters[current_mode]} saved"
        cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, color, 2)
        cv2.putText(frame, "R=Real P=Print M=Replay SPACE=Capture Q=Quit",
                    (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        cv2.imshow("Spoof Data Capture", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("r"):
            current_mode = "real"
        elif key == ord("p"):
            current_mode = "fake_print"
            print(f"  [DEVICE] Switched to FAKE_PRINT — hold printed image up to camera")
        elif key == ord("m"):
            current_mode = "fake_replay"
            print(f"  [DEVICE] Switched to FAKE_REPLAY — hold phone/screen up to camera")
        elif key == ord(" "):
            # Capture and save
            filename = f"{current_mode}_{counters[current_mode]:04d}.jpg"
            filepath = data_dir / current_mode / filename
            cv2.imwrite(str(filepath), frame)
            counters[current_mode] += 1
            print(f"  [OK] [{current_mode.upper()}] {filename}  (total: {counters[current_mode]})")
        elif key in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n  [DONE] Total:")
    for mode, count in counters.items():
        print(f"    {mode}: {count} images")
    print(f"\n  Run evaluation: python3 evaluate_all.py --spoof")


def capture_depth_test_data(cfg: Config) -> None:
    """
    Tool to capture images for depth evaluation.

    Enter true distance (m), the tool will capture and save with face bbox.
    """
    data_dir = Path(_THIS_DIR) / "eval_data" / "depth"
    images_dir = data_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    gt_file = data_dir / "ground_truth.json"

    # Load old ground truth if available
    ground_truth = {}
    if gt_file.exists():
        with open(gt_file) as f:
            ground_truth = json.load(f)

    # Load face detector to auto-detect bbox
    print(f"  Loading SCRFD …")
    face_det = SCRFDFaceDetector(
        model_path=cfg.scrfd_model,
        conf_thresh=cfg.scrfd_conf,
        nms_thresh=cfg.scrfd_nms,
        input_size=cfg.scrfd_input_size,
        device=cfg.device,
    )
    face_det.warmup()

    cap = cv2.VideoCapture(cfg.camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera_height)

    print(f"\n  [CAM] DEPTH TEST DATA CAPTURE")
    print(f"  {'─'*50}")
    print(f"  Instructions: Stand at a fixed distance (use measuring tape)")
    print(f"  Enter distance (m) → Enter → auto capture")
    print(f"  Type 'q' to exit")
    print(f"  {'─'*50}\n")

    distance_str = "1.0"  # default
    distance = 1.0
    face_bbox = None
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]

        # Detect face
        detections = face_det.detect(frame)
        if detections:
            best = max(detections, key=lambda d: d.confidence)
            face_bbox = best.bbox
            x1, y1, x2, y2 = [int(v) for v in face_bbox]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # Display depth sample point (center)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.circle(frame, (cx, cy), 5, (0, 255, 255), -1)
        else:
            face_bbox = None

        # Overlay info
        cv2.putText(frame, f"Distance: {distance:.2f}m (type + Enter, q=quit)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
        cv2.putText(frame, f"Saved: {len(ground_truth)} images",
                    (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        cv2.imshow("Depth Data Capture", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:
            break
        elif key == 13:  # Enter
            if face_bbox is None:
                print(f"  [WARN]  No face found! Adjust position and try again")
                continue

            filename = f"depth_{distance:.1f}m_{frame_count:03d}.jpg"
            filepath = images_dir / filename
            cv2.imwrite(str(filepath), frame)

            ground_truth[filename] = {
                "bbox": [float(v) for v in face_bbox],
                "distance_m": distance,
            }

            # Save immediately after each capture
            with open(gt_file, "w") as f:
                json.dump(ground_truth, f, indent=2)

            frame_count += 1
            print(f"  [OK] {filename} | bbox={face_bbox} | dist={distance:.2f}m "
                  f"(total: {len(ground_truth)})")

    cap.release()
    cv2.destroyAllWindows()

    print(f"\n  [DONE] Total: {len(ground_truth)} images")
    print(f"  Ground truth: {gt_file}")
    print(f"\n  Run evaluation: python3 evaluate_all.py --depth")


def capture_faces_test_data(cfg: Config) -> None:
    """
    Tool to capture images for face detection evaluation.
    Just capture many images, label later using labelImg.
    """
    data_dir = Path(_THIS_DIR) / "eval_data" / "face_detection"
    images_dir = data_dir / "images"
    labels_dir = data_dir / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    existing = len(_list_images(images_dir))

    cap = cv2.VideoCapture(cfg.camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera_height)

    print(f"\n  [CAM] FACE DETECTION TEST DATA CAPTURE")
    print(f"  {'─'*50}")
    print(f"  SPACE = Capture image | Q = Quit")
    print(f"  After capturing, use labelImg to draw ground truth boxes")
    print(f"  {'─'*50}\n")

    count = existing
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        cv2.putText(frame, f"Saved: {count} | SPACE=Capture Q=Quit",
                    (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow("Face Detection Data Capture", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(" "):
            filename = f"face_{count:04d}.jpg"
            filepath = images_dir / filename
            cv2.imwrite(str(filepath), frame)
            count += 1
            print(f"  [OK] {filename} (total: {count})")
        elif key in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n  [DONE] {count} images in {images_dir}")
    print(f"\n  Next steps:")
    print(f"    pip install labelImg")
    print(f"    labelImg {images_dir} {labels_dir / 'classes.txt'}")
    print(f"  After labeling: python3 evaluate_all.py --face")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate the entire pipeline with specific metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python3 evaluate_all.py                     # Run all evaluations with data
  python3 evaluate_all.py --face              # Only face detection
  python3 evaluate_all.py --spoof             # Only spoof detection
  python3 evaluate_all.py --depth             # Only depth estimation
  python3 evaluate_all.py --capture-spoof     # Capture tool for spoof test set
  python3 evaluate_all.py --capture-depth     # Capture tool for depth test set
  python3 evaluate_all.py --capture-faces     # Capture tool for face detection test set
""",
    )
    parser.add_argument("--face", action="store_true",
                        help="Only evaluate face detection")
    parser.add_argument("--spoof", action="store_true",
                        help="Only evaluate spoof detection")
    parser.add_argument("--depth", action="store_true",
                        help="Only evaluate depth estimation")
    parser.add_argument("--capture-spoof", action="store_true",
                        help="Open capture tool for spoof test data")
    parser.add_argument("--capture-depth", action="store_true",
                        help="Open capture tool for depth test data")
    parser.add_argument("--capture-faces", action="store_true",
                        help="Open capture tool for face detection test data")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Path to eval_data directory (default: AI/eval_data/)")
    args = parser.parse_args()

    # ── Capture mode ──
    cfg = Config()
    if args.capture_spoof:
        capture_spoof_test_data(cfg)
        return
    if args.capture_depth:
        capture_depth_test_data(cfg)
        return
    if args.capture_faces:
        capture_faces_test_data(cfg)
        return

    # ── Evaluation mode ──
    data_dir = Path(args.data_dir) if args.data_dir else Path(_THIS_DIR) / "eval_data"

    # Determine what to run
    run_face = args.face or (not args.spoof and not args.depth)
    run_spoof = args.spoof or (not args.face and not args.depth)
    run_depth = args.depth or (not args.face and not args.spoof)

    print("=" * 60)
    print("  EVALUATE ALL — Pipeline Performance Report")
    print("=" * 60)
    print(f"  Device: {cfg.device}")
    print(f"  Data dir: {data_dir}")
    print(f"  Camera calibration: {'[OK] Loaded' if cfg.distortion != (0.0,)*5 else '[WARN]  Not calibrated'}")

    results = {}

    if run_face:
        r = evaluate_face_detection(cfg, data_dir)
        results["face"] = r
        _print_face_results(r)

    if run_spoof:
        r = evaluate_spoof(cfg, data_dir)
        results["spoof"] = r
        _print_spoof_results(r)

    if run_depth:
        r = evaluate_depth(cfg, data_dir)
        results["depth"] = r
        _print_depth_results(r)

    # ── Overall summary ──
    _section("OVERALL SUMMARY")
    errors = [k for k, v in results.items() if "error" in v]
    success = [k for k, v in results.items() if "error" not in v]

    if errors:
        print(f"\n  [WARN]  Cannot evaluate: {', '.join(errors)}")
        print(f"  Run with --capture-* flag to create test data")
    if success:
        print(f"\n  [OK] Evaluated: {', '.join(success)}")
        print(f"\n  ┌{'─'*22}┬{'─'*10}┬{'─'*10}┬{'─'*20}┐")
        print(f"  │ {'Component':<20s} │ {'Metric':>8s} │ {'Value':>8s} │ {'Verdict':>18s} │")
        print(f"  ├{'─'*22}┼{'─'*10}┼{'─'*10}┼{'─'*20}┤")

        if "face" in success:
            r = results["face"]
            f1_str = f"{r['f1']:.3f}"
            ok = "[OK] Good" if r['f1'] >= 0.82 else "[WARN] Needs work"
            print(f"  │ {'Face Detection':<20s} │ {'F1':>8s} │ {f1_str:>8s} │ {ok:<18s} │")

        if "spoof" in success:
            r = results["spoof"]
            hter_str = f"{r['best_HTER']:.4f}"
            if r['best_HTER'] < 0.10:
                ok = "[OK] Excellent"
            elif r['best_HTER'] < 0.15:
                ok = "[OK] Good"
            elif r['best_HTER'] < 0.25:
                ok = "[WARN] Fair"
            else:
                ok = "[FAIL] Poor"
            print(f"  │ {'Spoof Detection':<20s} │ {'HTER':>8s} │ {hter_str:>8s} │ {ok:<18s} │")

        if "depth" in success:
            r = results["depth"]
            mae_str = f"{r['MAE_m']:.3f}m"
            ok = "[OK] Good" if r['MAE_m'] < 0.50 else "[WARN] Needs work"
            print(f"  │ {'Depth Estimation':<20s} │ {'MAE':>8s} │ {mae_str:>8s} │ {ok:<18s} │")

        print(f"  └{'─'*22}┴{'─'*10}┴{'─'*10}┴{'─'*20}┘")

    if not success and not errors:
        print("\n  No data to evaluate.")
        print("  Run: python3 evaluate_all.py --help")

    print()


if __name__ == "__main__":
    main()
