"""The camera: opening it, and undistorting its frames."""

import glob
import os
from typing import List, Tuple, Union

import cv2
import numpy as np


def init_undistort_maps(
    camera_matrix: np.ndarray,
    distortion: np.ndarray,
    image_size: Tuple[int, int],
    alpha: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Pre-compute remap matrices for fast undistortion.

    Args:
        camera_matrix: 3×3 camera intrinsics.
        distortion: Distortion coefficients (k1, k2, p1, p2, k3).
        image_size: (width, height) of the captured frames.
        alpha: 0.0 = crop to valid region; 1.0 = keep all pixels (black borders).

    Returns:
        (map_x, map_y) for use with cv2.remap().
    """
    w, h = image_size
    new_mtx, _ = cv2.getOptimalNewCameraMatrix(
        camera_matrix, distortion, (w, h), alpha, (w, h)
    )
    map_x, map_y = cv2.initUndistortRectifyMap(
        camera_matrix, distortion, None, new_mtx, (w, h), cv2.CV_32FC1
    )
    return map_x, map_y


def undistort_frame(
    frame: np.ndarray,
    map_x: np.ndarray,
    map_y: np.ndarray,
) -> np.ndarray:
    """
    Undistort a single frame using pre-computed remap matrices.

    Args:
        frame: Input BGR frame, shape (H, W, 3).
        map_x, map_y: Pre-computed from init_undistort_maps().

    Returns:
        Undistorted frame, same shape and dtype.
    """
    return cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR)


PREFERRED_CAMERA = "*C920*"   # Logitech C920, moved between laptop and workstation
BY_ID_DIR = "/dev/v4l/by-id"


def camera_candidates(camera_id: int, by_id_dir: str = BY_ID_DIR) -> List[Union[str, int]]:
    """Cameras to try, in order.

    VISION_CAMERA_PATH / VISION_CAMERA_INDEX pin one camera and disable the
    search. Otherwise: the C920 by its stable by-id path (its /dev/videoN
    changes with plug order), then the configured index, then any other
    camera. Only ``-video-index0`` nodes: index1 is the metadata node.
    """
    if os.environ.get("VISION_CAMERA_PATH"):
        return [os.environ["VISION_CAMERA_PATH"]]
    if os.environ.get("VISION_CAMERA_INDEX"):
        return [int(os.environ["VISION_CAMERA_INDEX"])]
    preferred = sorted(glob.glob(os.path.join(by_id_dir, PREFERRED_CAMERA + "-video-index0")))
    others = sorted(glob.glob(os.path.join(by_id_dir, "*-video-index0")))
    ordered = preferred + [camera_id] + [p for p in others if p not in preferred]
    seen, result = set(), []
    for cam in ordered:
        key = os.path.realpath(cam) if isinstance(cam, str) else f"/dev/video{cam}"
        if key not in seen:
            seen.add(key)
            result.append(cam)
    return result


def open_camera(camera_id: int, width: int, height: int) -> cv2.VideoCapture:
    tried = []
    for cam in camera_candidates(camera_id):
        cap = cv2.VideoCapture(cam, cv2.CAP_V4L2)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            # isOpened() alone accepts busy or non-capture nodes.
            if cap.read()[0]:
                print(f"Camera: {cam} {width}x{height}", flush=True)
                return cap
        cap.release()
        tried.append(str(cam))
    raise RuntimeError(f"Cannot open any camera (tried: {', '.join(tried)})")
