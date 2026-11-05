"""Compare visible lip geometry at matched openings, without running the avatar GPU.

This is a geometry diagnostic, not a perceptual naturalness or lipsync score.
The contact sheet must also be reviewed for teeth and texture artifacts.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".runtime/ditto-packages"))


def measure_video(path, *, limit=180):
    import cv2
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks.python import BaseOptions, vision

    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=str(
                ROOT / ".runtime/Ditto/checkpoints/ditto_pytorch/aux_models/face_landmarker.task"
            )
        ),
        num_faces=1,
    )
    rows = []
    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS)
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    stride = max(1, count // limit)
    with vision.FaceLandmarker.create_from_options(options) as detector:
        index = -1
        while True:
            ok, bgr = capture.read()
            if not ok:
                break
            index += 1
            if index % stride:
                continue
            height, width = bgr.shape[:2]
            # Original assets are full-body portraits. Keep the head at a useful
            # resolution for the CPU landmarker; output is still measured in px.
            left, right, bottom = int(width * 0.20), int(width * 0.80), int(height * 0.48)
            rgb = cv2.cvtColor(bgr[:bottom, left:right], cv2.COLOR_BGR2RGB)
            result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            if not result.face_landmarks:
                continue
            points = np.array(
                [(p.x * rgb.shape[1], p.y * rgb.shape[0]) for p in result.face_landmarks[0]]
            )
            lip_width = np.linalg.norm(points[291] - points[61])
            if lip_width < 5:
                continue
            aperture = np.linalg.norm(points[14] - points[13]) / lip_width
            upper = np.linalg.norm(points[0] - points[13]) / lip_width
            lower = np.linalg.norm(points[17] - points[14]) / lip_width
            mouth = points[[61, 291, 0, 17]]
            lo = np.floor(mouth.min(0) - lip_width * 0.15).astype(int)
            hi = np.ceil(mouth.max(0) + lip_width * 0.15).astype(int)
            lo = np.maximum(lo, 0)
            hi = np.minimum(hi, [rgb.shape[1], rgb.shape[0]])
            patch = rgb[lo[1] : hi[1], lo[0] : hi[0]].copy()
            rows.append(
                {
                    "frame": index,
                    "seconds": index / fps,
                    "aperture": float(aperture),
                    "upper": float(upper),
                    "lower": float(lower),
                    "thickness": float(upper + lower),
                    "patch": patch,
                }
            )
    capture.release()
    return rows


def compare(reference, actual, output, *, max_ratio=1.2, max_tail_ratio=1.25):
    import numpy as np
    from PIL import Image, ImageDraw, ImageOps

    selected = [row for row in actual if row["aperture"] >= 0.20]
    pairs = []
    for row in selected:
        match = min(reference, key=lambda other: abs(other["aperture"] - row["aperture"]))
        if abs(match["aperture"] - row["aperture"]) <= 0.04:
            pairs.append((match, row))
    if len(pairs) < 5:
        raise ValueError(
            "Not enough matched large-open mouths; inspect sources instead of declaring a pass"
        )
    ratios = [b["thickness"] / a["thickness"] for a, b in pairs]
    ratio = float(np.median(ratios))
    tail = float(np.percentile(ratios, 90))
    report = {
        "reference_frames": len(reference),
        "actual_frames": len(actual),
        "matched_large_open_frames": len(pairs),
        "median_matched_thickness_ratio": ratio,
        "geometry_limit": max_ratio,
        "p90_matched_thickness_ratio": tail,
        "tail_geometry_limit": max_tail_ratio,
        "reference_aperture_p95": float(np.percentile([r["aperture"] for r in reference], 95)),
        "actual_aperture_p95": float(np.percentile([r["aperture"] for r in actual], 95)),
        "geometry_passed": ratio <= max_ratio and tail <= max_tail_ratio,
        "note": "Normalized center-lip landmark thickness at matched aperture. Not a tooth-anatomy, texture or lipsync acceptance score.",
    }
    output.mkdir(parents=True, exist_ok=True)
    chosen = sorted(
        pairs, key=lambda pair: pair[1]["thickness"] / pair[0]["thickness"], reverse=True
    )[:10]
    sheet = Image.new("RGB", (640, 130 * len(chosen)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (a, b) in enumerate(chosen):
        for col, (label, row) in enumerate((("Original", a), ("Actual", b))):
            patch = ImageOps.contain(Image.fromarray(row["patch"]), (300, 95))
            sheet.paste(patch, (col * 320 + 8, index * 130 + 30))
            draw.text(
                (col * 320 + 8, index * 130 + 5),
                f"{label} {row['seconds']:.2f}s open={row['aperture']:.2f} lip={row['thickness']:.2f}",
                fill="black",
            )
    sheet.save(output / "matched-open-mouths.jpg")
    (output / "geometry.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        required=True,
        help="Explicit user-selected source; different clips have different face/lip appearances.",
    )
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-ratio", type=float, default=1.2)
    args = parser.parse_args()
    report = compare(
        measure_video(args.reference),
        measure_video(args.actual),
        args.output,
        max_ratio=args.max_ratio,
    )
    report["reference_video"] = str(args.reference.resolve())
    report["actual_video"] = str(args.actual.resolve())
    (args.output / "geometry.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)
    raise SystemExit(0 if report["geometry_passed"] else 2)


if __name__ == "__main__":
    main()
