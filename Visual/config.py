"""
Global configuration for the real-time face detection and distance estimation system.

All tunable parameters live here. No hardcoded values elsewhere.
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Tuple

import numpy as np
import torch
import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: locate the calibration file relative to this config file
# ---------------------------------------------------------------------------
def _default_calibration_path() -> str:
    return os.path.join(os.path.dirname(__file__), "tools", "chessboard", "calibration.npz")


# ---------------------------------------------------------------------------
# YAML config file resolution
# ---------------------------------------------------------------------------
def _resolve_yaml_path(
    explicit_path: str | None = None,
    *,
    search_project_root: bool = True,
) -> str | None:
    """Discover the YAML config file path.

    Resolution order:
    1. *explicit_path* — returned as-is if the file exists (raises if not).
    2. ``JARVIS_CONFIG`` environment variable.
    3. ``--config <path>`` in ``sys.argv``.
    4. ``config.yml`` in the project root (walk up from the current working
       directory until the filesystem root is found).

    Args:
        explicit_path: A user-supplied path; validated for existence.
        search_project_root: When false, skip the project-root fallback
            (used in tests where there is no real project root).

    Returns:
        Absolute path to the YAML file, or ``None`` if no file was found
        through auto-discovery.
    """
    if explicit_path is not None:
        if not os.path.isfile(explicit_path):
            raise FileNotFoundError(
                f"YAML config file not found: {explicit_path}"
            )
        return os.path.abspath(explicit_path)

    # 2. JARVIS_CONFIG environment variable
    env_path = os.environ.get("JARVIS_CONFIG")
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)

    # 3. --config <path> in sys.argv
    try:
        idx = sys.argv.index("--config")
        cli_path = sys.argv[idx + 1]
        if os.path.isfile(cli_path):
            return os.path.abspath(cli_path)
    except (ValueError, IndexError):
        pass

    # 4. Walk up from the current working directory looking for config.yml
    if search_project_root:
        current = os.getcwd()
        while True:
            candidate = os.path.join(current, "config.yml")
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(current)
            if parent == current:  # reached filesystem root
                break
            current = parent

    return None


def _coerce_yaml_value(value, field_type):
    """Coerce a YAML value to the expected *field_type*.

    Handles tuple fields (YAML list to tuple) and passes through values
    that already match the expected type.
    """
    origin = getattr(field_type, "__origin__", None)

    # Tuple[int, ...] or Tuple[float, ...]
    if origin is tuple:
        return tuple(value)

    # Optional[T] — extract inner type from Union / Optional
    if origin is not None:
        args = getattr(field_type, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            field_type = non_none[0]

    # If the value is already the right type, pass through
    if isinstance(value, field_type):
        return value

    # Let the target type's constructor handle final coercion
    return field_type(value)


@dataclass(frozen=True)
class Config:
    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------
    camera_id: int = 0                # Webcam device index
    camera_width: int = 640           # Capture resolution width
    camera_height: int = 480          # Capture resolution height
    # Remote WebRTC camera (a phone or laptop a voice session explicitly
    # selects).  Its frames are cropped and resized to the capture size above;
    # with no calibration, its intrinsics are estimated from this horizontal
    # field of view, so its distances are approximate.  Its frames stopping for
    # remote_camera_stale_secs hands the image back to the local camera.
    remote_camera_hfov_deg: float = 70.0
    remote_camera_stale_secs: float = 0.5
    # Frames in a row, each in time, before the remote takes the camera (again).
    remote_camera_steady_frames: int = 5

    # ------------------------------------------------------------------
    # Camera Calibration
    #
    # If calibration_path points to a valid .npz file (from
    # tools/chessboard/calibrate.py), the intrinsics and distortion coefficients
    # are loaded automatically, overriding the approximate defaults below.
    # Set use_undistort=True to undistort every frame before processing.
    # ------------------------------------------------------------------
    calibration_path: str = field(default_factory=_default_calibration_path)
    use_calibration: bool = True
    use_undistort: bool = True

    # These are FALLBACK values used when no calibration file is found.
    # They are overwritten at init time when calibration_path exists.
    camera_fx: float = 500.0
    camera_fy: float = 500.0
    camera_cx: float = 320.0          # principal point x (width/2)
    camera_cy: float = 240.0          # principal point y (height/2)
    distortion: Tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0)

    # ------------------------------------------------------------------
    # SCRFD – Face Detection (ONNX)
    # ------------------------------------------------------------------
    scrfd_model: str = field(default_factory=lambda: os.path.join(os.path.dirname(__file__), "models", "scrfd_2.5g_face.onnx"))  # Path to ONNX model file
    scrfd_conf: float = 0.5            # Minimum confidence for a face detection
    scrfd_nms: float = 0.4             # NMS IoU threshold
    scrfd_input_size: Tuple[int, int] = (320, 320)  # Model input (W, H) — smaller=faster

    # ------------------------------------------------------------------
    # ByteTrack – Multi-Face Tracking
    # ------------------------------------------------------------------
    track_buffer: int = 15            # Frames to keep a lost track alive (reduced for face tracking)
    track_thresh: float = 0.5         # High-confidence detection threshold
    match_thresh: float = 0.3         # IoU threshold for first association (lower = more tolerant to fast motion)
    match_thresh_second: float = 0.5  # IoU threshold for second association
    track_init_thresh: float = 0.7    # Min confidence to initialise a new track
    # Cap the track loop.  Uncapped it re-detects as fast as SCRFD returns
    # (~150 fps measured), which pins a full core and starves the TTS worker
    # sharing the box.  A kiosk only needs enough rate to keep a walking
    # person's box smooth; 15 fps measured 98.7% -> ~10% of one core.
    # 0 disables the cap.
    track_max_fps: float = 15.0

    # ------------------------------------------------------------------
    # Face Embedder — ReID for appearance-based tracking
    # ------------------------------------------------------------------
    embedder_model_path: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(__file__), "models", "face_embedder.onnx"
    ))  # Path to ONNX embedder model
    embedder_device: str = "cuda"           # "cpu" or "cuda"
    reid_weight: float = 0.6               # Weight for appearance in fused cost (0=IoU only, 1=appearance only)
    gallery_size: int = 10                 # Max embeddings stored per track

    # ------------------------------------------------------------------
    # Lip reader — mouth activity for the voice speaker gate
    # ------------------------------------------------------------------
    lip_model_path: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(__file__), "models", "face_landmarks.onnx"
    ))  # MediaPipe face landmarks, ONNX (Apache-2.0)
    mouth_scale: float = 0.06              # Lip-opening std over 0.5 s that counts as full mouth activity

    # ------------------------------------------------------------------
    # Active speaker (Light-ASD) — scores the nearest face against session audio
    # ------------------------------------------------------------------
    asd_provider: str = "none"             # none | light_asd
    asd_model_path: str = field(default_factory=lambda: os.path.expanduser(
        "~/.cache/openjarvis/light_asd/light_asd.onnx"
    ))  # weights stay outside Git; the <path>.json manifest sits beside them
    asd_audio_offset_secs: float = 0.0     # video time = audio time + offset; -1.0..+1.0

    # ------------------------------------------------------------------
    # YOLO – Person Detection (presence when no face is visible)
    # ------------------------------------------------------------------
    person_model: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(__file__), "models", "yolo11n.pt"
    ))                                  # missing file → person detection is skipped
    person_conf: float = 0.4            # minimum confidence for a person box
    person_shrink: float = 0.5          # fraction of the box kept when sampling depth
    person_depth_percentile: float = 20.0  # low percentile leans on the nearest pixels

    # ------------------------------------------------------------------
    # Metric3Dv2 – Monocular Metric Depth Estimation
    # ------------------------------------------------------------------
    metric3d_variant: str = "vit_small"  # "vit_small" | "vit_large" | "vit_giant2"
    metric3d_input_size: Tuple[int, int] = (616, 1064)  # (H, W) for ViT models
    metric3d_canonical_focal: float = 1000.0  # Canonical focal length
    metric3d_depth_range: Tuple[float, float] = (0.1, 200.0)  # Clamp range (m)
    metric3d_half: bool = True         # FP16 saves 30% VRAM, 1.5-2x faster on RTX 30xx+
    # Depth refresh interval, in seconds.  Metric3D takes ~600 ms per map, so
    # asking for much below 1 s just queues work.  Named in seconds because
    # the loop is time-driven: the old `depth_every_n_frames = 20` never
    # counted frames, it counted 20 polls of a 0.05 s sleep -- always 1.0 s
    # regardless of capture rate.
    depth_interval_sec: float = 1.0

    # ------------------------------------------------------------------
    # Spoof Detection — MiniFASNet Ensemble (PAD only)
    # ------------------------------------------------------------------
    spoof_enabled: bool = True           # Enable spoof detection
    spoof_interval_sec: float = 0.5      # Run spoof check every N seconds
    spoof_live_threshold: float = 0.60   # Live score ≥ this → REAL person

    # ------------------------------------------------------------------
    # Distance threshold
    # ------------------------------------------------------------------
    distance_threshold: float = 1.0   # metres – face closer than this → RED

    # ------------------------------------------------------------------
    # Face-geometry distance (faces; Metric3D measures bodies)
    # ------------------------------------------------------------------
    # Interpupillary distance the PnP face model is scaled to.  Adult mean
    # 63 mm (+/- 3.5 mm).  Distance scales linearly with it, so this is the
    # calibration knob -- set your own IPD for a single-operator kiosk.
    face_ipd_m: float = 0.063

    # ------------------------------------------------------------------
    # Async pipeline
    # ------------------------------------------------------------------
    async_depth: bool = True          # Run depth estimation in background thread
    async_detect: bool = True         # Run detection in background thread

    # ------------------------------------------------------------------
    # Device
    # ------------------------------------------------------------------
    device: str = field(default_factory=lambda: "cuda" if torch.cuda.is_available() else "cpu")

    # ------------------------------------------------------------------
    # WebSocket server
    # ------------------------------------------------------------------
    ws_enabled: bool = False           # Deprecated — WS is always-on now
    ws_port: int = 9876                # Port for the WS server

    # ------------------------------------------------------------------
    # YAML-based config creation
    # ------------------------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str | None = None) -> "Config":
        """Create a Config from a YAML file.

        Resolution order (via ``_resolve_yaml_path``):
        1. ``path`` (explicit path)
        2. ``JARVIS_CONFIG`` environment variable
        3. ``--config <path>`` in ``sys.argv``
        4. ``config.yml`` in the project root

        Args:
            path: An explicit YAML path, or ``None`` for auto-discovery.

        Returns:
            A Config instance with YAML values applied on top of defaults.
        """
        yaml_path = _resolve_yaml_path(path)
        if yaml_path is None:
            return cls()

        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file: {e}") from e

        # Empty file or all-comments YAML
        if data is None:
            return cls()

        # Build keyword arguments from the YAML data, skipping unknown keys
        kwargs = {}
        for key, value in data.items():
            if key not in cls.__dataclass_fields__:
                logger.debug("Unknown config key: %s", key)
                continue

            field_type = cls.__dataclass_fields__[key].type
            try:
                kwargs[key] = _coerce_yaml_value(value, field_type)
            except (TypeError, ValueError):
                print(
                    f"[config] Cannot coerce value {value!r} for field "
                    f"{key}, using default",
                    file=sys.stderr,
                )

        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Post-init: load calibration if available
    # ------------------------------------------------------------------
    def __post_init__(self):
        # Reject nonsense intervals loudly.  These used to be clamped in the
        # worker loop (`max(1.0, spoof_interval_sec)`), which silently ignored
        # whatever the config asked for -- a setting that looks tunable but
        # is not is worse than one that refuses.
        for name in ("spoof_interval_sec", "depth_interval_sec"):
            value = getattr(self, name)
            if value <= 0:
                raise ValueError(f"{name} must be > 0, got {value!r}")
        if any(v % 14 for v in self.metric3d_input_size):
            raise ValueError(
                f"metric3d_input_size must be multiples of 14 (ViT patch "
                f"size), got {self.metric3d_input_size!r}"
            )
        if self.track_max_fps < 0:
            raise ValueError(
                f"track_max_fps must be >= 0 (0 disables the cap), "
                f"got {self.track_max_fps!r}"
            )

        if self.asd_provider not in ("none", "light_asd"):
            raise ValueError(
                f"asd_provider must be 'none' or 'light_asd', got {self.asd_provider!r}"
            )
        if not -1.0 <= self.asd_audio_offset_secs <= 1.0:  # also rejects NaN
            raise ValueError(
                f"asd_audio_offset_secs must be finite and within [-1, 1], "
                f"got {self.asd_audio_offset_secs!r}"
            )

        if self.use_calibration:
            if self.calibration_path and os.path.exists(self.calibration_path):
                data = np.load(self.calibration_path)
                mtx = data["camera_matrix"]
                dist = data["distortion"]

                # Override the frozen fields with calibrated values
                object.__setattr__(self, "camera_fx", float(mtx[0, 0]))
                object.__setattr__(self, "camera_fy", float(mtx[1, 1]))
                object.__setattr__(self, "camera_cx", float(mtx[0, 2]))
                object.__setattr__(self, "camera_cy", float(mtx[1, 2]))
                object.__setattr__(self, "distortion",
                                   tuple(float(v) for v in dist.ravel()))

                rms = data.get("rms_error", -1.0)
                print(f"[config] Loaded calibration from {self.calibration_path}")
                print(f"         fx={self.camera_fx:.1f} fy={self.camera_fy:.1f} "
                      f"cx={self.camera_cx:.1f} cy={self.camera_cy:.1f}")
                print(f"         distortion={[f'{v:.4f}' for v in self.distortion]}")
                print(f"         RMS reprojection error: {float(rms):.4f} px")
            else:
                print(f"[config] No calibration file found at {self.calibration_path}")
                print(f"         Using approximate intrinsics (fx={self.camera_fx:.0f}, "
                      f"fy={self.camera_fy:.0f})")
                print(f"         Run: python3 tools/chessboard/calibrate.py")

    # ------------------------------------------------------------------
    # Derived / convenience
    # ------------------------------------------------------------------
    @property
    def intrinsics(self) -> Tuple[float, float, float, float]:
        """Return (fx, fy, cx, cy)."""
        return (self.camera_fx, self.camera_fy, self.camera_cx, self.camera_cy)

    @property
    def canonical_to_real_scale(self) -> float:
        """Factor to convert canonical depth to real metric depth."""
        return self.camera_fx / self.metric3d_canonical_focal
