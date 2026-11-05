"""
Camera calibration using chessboard images + OpenCV.

Usage:
    python3 tools/chessboard/calibrate.py

Input:  tools/chessboard/captures/frame_*.jpg
Output: tools/chessboard/calibration.npz  (camera matrix + distortion coefficients)
"""

import glob
import os

import cv2
import numpy as np


def calibrate(
    image_dir: str | None = None,
    pattern_size: tuple[int, int] = (6, 9),  # (cols, rows) inner corners
    square_size_mm: float = 10.0,
    output_path: str | None = None,
):
    """
    Calibrate camera from chessboard images.

    Args:
        image_dir:     Directory containing captured chessboard images.
        pattern_size:  Number of inner corners (columns, rows).
        square_size_mm: Physical size of each square in mm.
        output_path:   Where to save calibration results (.npz).
    """
    if image_dir is None:
        image_dir = os.path.join(os.path.dirname(__file__), "captures")
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "calibration.npz")

    # --- 1. Prepare object points (3D) ---
    #    We treat the chessboard as lying on the z=0 plane.
    #    (0,0,0), (1,0,0), ..., (6,9,0) scaled by square_size_mm.
    objp = np.zeros((pattern_size[1] * pattern_size[0], 3), np.float32)
    # mgrid ensures X (col) in column 0, Y (row) in column 1
    objp[:, :2] = np.mgrid[0 : pattern_size[0], 0 : pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size_mm

    obj_points: list[np.ndarray] = []   # 3D points in real world
    img_points: list[np.ndarray] = []   # 2D points in image plane

    # --- 2. Find chessboard corners in each image ---
    images = sorted(glob.glob(os.path.join(image_dir, "*.jpg")))
    if not images:
        images = sorted(glob.glob(os.path.join(image_dir, "*.png")))

    print(f"Found {len(images)} images in {image_dir}")
    print(f"Chessboard pattern: {pattern_size[0]}x{pattern_size[1]} inner corners")
    print(f"Square size: {square_size_mm} mm\n")

    found_count = 0
    h, w = 0, 0

    for fname in images:
        img = cv2.imread(fname)
        if img is None:
            print(f"  ⚠️  Cannot read {fname}, skipping")
            continue

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Find chessboard corners
        ret, corners = cv2.findChessboardCorners(
            gray,
            pattern_size,
            flags=cv2.CALIB_CB_ADAPTIVE_THRESH
                  | cv2.CALIB_CB_FAST_CHECK
                  | cv2.CALIB_CB_NORMALIZE_IMAGE,
        )

        if not ret:
            print(f"  ⚠️  No chessboard found in {os.path.basename(fname)}")
            continue

        # Refine corner locations to sub-pixel accuracy
        criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
            30,
            0.001,
        )
        corners_sub = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

        obj_points.append(objp)
        img_points.append(corners_sub)
        found_count += 1
        print(f"  ✅ {os.path.basename(fname)} -> {len(corners_sub)} corners")

    if found_count < 5:
        print(f"\n❌ Only {found_count} images with chessboard found (need ≥ 5).")
        print("   Tips: make sure the entire chessboard is visible and in focus.")
        print(f"   Pattern size is {pattern_size[0]}x{pattern_size[1]} inner corners —")
        print("   check that the printed board matches!")
        return None

    # --- 3. Run calibration ---
    print(f"\n--- Calibrating with {found_count} views ({w}x{h}) ---")
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, (w, h), None, None
    )

    print(f"\nRMS reprojection error: {ret:.4f} px")
    print(f"\nCamera matrix:\n{mtx}")
    print(f"\nDistortion coefficients: {dist.ravel()}")

    # --- 4. Per-image reprojection error ---
    mean_error = 0.0
    for i in range(len(obj_points)):
        proj, _ = cv2.projectPoints(obj_points[i], rvecs[i], tvecs[i], mtx, dist)
        error = cv2.norm(img_points[i], proj, cv2.NORM_L2) / len(proj)
        mean_error += error
    mean_error /= len(obj_points)
    print(f"\nMean reprojection error: {mean_error:.4f} px")

    # --- 5. Quality assessment ---
    if ret < 0.5:
        print("\n✅ Excellent calibration (RMS < 0.5 px)")
    elif ret < 1.0:
        print("\n✔️  Good calibration (RMS < 1.0 px)")
    else:
        print("\n⚠️  Calibration quality is marginal — consider capturing more images")

    # --- 6. Save results ---
    np.savez(
        output_path,
        camera_matrix=mtx,
        distortion=dist,
        rms_error=ret,
        image_size=np.array([w, h]),
        pattern_size=np.array(pattern_size),
        square_size_mm=square_size_mm,
    )
    print(f"\n💾 Saved calibration to: {output_path}")

    return mtx, dist


def load_calibration(path: str | None = None):
    """Load saved calibration."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "calibration.npz")
    data = np.load(path)
    return data["camera_matrix"], data["distortion"]


def undistort_example(image_path: str, mtx: np.ndarray, dist: np.ndarray):
    """Show before/after comparison for one image."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"Cannot read {image_path}")
        return

    h, w = img.shape[:2]
    new_mtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))

    # Undistort
    dst = cv2.undistort(img, mtx, dist, None, new_mtx)

    # Crop the valid region
    x, y, rw, rh = roi
    dst = dst[y : y + rh, x : x + rw]

    # Resize back for side-by-side comparison
    dst = cv2.resize(dst, (w, h))

    comparison = np.hstack((img, dst))
    cv2.putText(img, "Original", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(dst, "Undistorted", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    out_path = os.path.join(os.path.dirname(__file__), "undistort_comparison.jpg")
    cv2.imwrite(out_path, comparison)
    print(f"\n📸 Saved before/after comparison to: {out_path}")


if __name__ == "__main__":
    result = calibrate()

    if result is not None:
        mtx, dist = result

        # Show undistort example on the first image
        image_dir = os.path.join(os.path.dirname(__file__), "captures")
        images = sorted(glob.glob(os.path.join(image_dir, "*.jpg")))
        if images:
            undistort_example(images[0], mtx, dist)
