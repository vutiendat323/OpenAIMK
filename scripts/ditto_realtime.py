"""Bounded, causal Ditto kiosk engine (experimental five-step motion sampler).

The 80-frame model sees only past features. Hubert uses 80 ms of already received
right context; no complete utterance or upstream 70-frame batch is required.
Five DDIM steps differ from the official 50: visual equivalence is NOT asserted.
"""

import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

from trendcoffee.avatar_appearance import (
    blend_rest_mouth,
    calm_source_frames,
    composite_mouth,
    register_source,
)
from trendcoffee.avatar_blink import blink_flags
from trendcoffee.avatar_expression import (
    LIP_POINTS,
    calibrate_expression,
    closed_lip_shape,
    compress_lips,
)
from trendcoffee.avatar_pose import PoseTimeline
from trendcoffee.avatar_presentation import MouthFrame, MouthTransition
from trendcoffee.avatar_rest import CrossFade, load_rest_clip, rest_frame_index
from trendcoffee.avatar_whole_face import composite_whole_face, head_drive, speech_expression


class DittoEngine:
    TARGET_FPS = 12
    PRESENTATION_FPS = 24
    AUDIO_CAPACITY = 64000
    SAMPLING_STEPS = 5
    MOTION_SAMPLES = 3200
    GAP_GRACE_SECONDS = 0.75
    MOUTH_REST_SECONDS = 0.28
    STEADY_CLIP_RATE = 0.55
    # A blink played at the slow rate lasts half a second and reads as sleepy eyes.
    BLINK_CLIP_RATE = 2.2
    # Two different clips dissolved into each other show both faces at once, so cut.
    FADE_SECONDS = 0.0
    VOICE_FADE_SECONDS = 0.18
    VOICE_WINDOW_SAMPLES = 1600
    REST_CATCHUP_FRAMES = 12
    METRIC_WINDOW_SECONDS = 5.0

    def __init__(
        self,
        source_path: Path,
        root: Path,
        *,
        gpu_budget=None,
        presentation_lead_ms=None,
        render_fps=None,
        motion_stride_ms=None,
        renderer_backend="pytorch",
        expression_mode="source-relative",
        lip_opening_limit=0.0,
        composite="mouth",
        closed_source=False,
        plain_ditto=False,
        lip_factor=None,
        lip_width=None,
        whole_head=False,
        wave=True,
        drive_head=False,
        ditto_silence=False,
        reference_frame=None,
        rest_source=None,
        head_gain=None,
        turn_gain=None,
    ):
        self.TARGET_FPS = float(
            os.environ.get("DITTO_RENDER_FPS", str(self.TARGET_FPS))
            if render_fps is None
            else render_fps
        )
        if not np.isfinite(self.TARGET_FPS) or not 6 <= self.TARGET_FPS <= 24:
            raise ValueError("Render FPS must be between six and twenty-four")
        if motion_stride_ms is not None:
            if motion_stride_ms not in (80, 120, 160, 200):
                raise ValueError("Motion stride must be 80, 120, 160 or 200ms")
            self.MOTION_SAMPLES = int(motion_stride_ms * 16)
        if renderer_backend not in ("pytorch", "tensorrt", "tensorrt-mouth"):
            raise ValueError("Renderer backend must be pytorch, tensorrt or tensorrt-mouth")
        self._renderer_backend = renderer_backend
        if expression_mode not in ("absolute", "source-relative"):
            raise ValueError("Expression mode must be absolute or source-relative")
        if reference_frame is not None:
            if composite != "full-face":
                raise ValueError("Reference rendering requires the whole face")
            if reference_frame != 0:
                raise ValueError("Source preparation currently requires real closed frame zero")
            # Silence stays off the GPU: the prepared rest faces cover it unless asked otherwise.
            plain_ditto = True
            lip_factor = 0.5 if lip_factor is None else lip_factor
        self._reference_frame = reference_frame
        if plain_ditto:
            if composite != "full-face":
                raise ValueError("Plain Ditto is only defined for the whole face")
            # Upstream's own relative drive replaces the kiosk's calibration layers.
            expression_mode, lip_opening_limit = "absolute", 0.0
        elif lip_factor is not None or lip_width is not None or drive_head or ditto_silence:
            raise ValueError("These options need the plain Ditto path")
        if lip_factor is not None and not 0 < lip_factor <= 1:
            raise ValueError("Lip factor must be above zero and at most one")
        if lip_width is not None and not 0 <= lip_width <= 1:
            raise ValueError("Lip width must be between zero and one")
        if head_gain is not None:
            if not drive_head:
                raise ValueError("Head gain needs head drive")
            if not np.isfinite(head_gain) or head_gain <= 0:
                raise ValueError("Head gain must be a positive finite number")
        if turn_gain is not None and (
            not drive_head or not np.isfinite(turn_gain) or turn_gain < 0
        ):
            raise ValueError("Turn gain needs head drive and must be zero or more")
        self._head_gain = 1.0 if head_gain is None else float(head_gain)
        self._turn_gain = None if turn_gain is None else float(turn_gain)
        self._plain_ditto = bool(plain_ditto)
        self._lip_factor = lip_factor
        self._whole_head = bool(whole_head)
        self._wave_enabled = bool(wave)
        self._lip_width = 1.0 if lip_width is None else float(lip_width)
        self._drive_head = bool(drive_head)
        self._ditto_silence = bool(ditto_silence)
        self._voice_level = 0.0
        self._voice_at = None
        self._expression_mode = expression_mode
        if composite not in ("mouth", "full-face"):
            raise ValueError(f"Unsupported composite: {composite}")
        if composite == "full-face" and renderer_backend == "tensorrt-mouth":
            raise ValueError("Full-face composite needs a full-face renderer")
        self._composite = composite
        # A clip rebuilt with a closed mouth needs the same motion handling as full-face.
        self._steady_motion = composite == "full-face" or bool(closed_source)
        self._closed_source = bool(closed_source)
        self._rest_faces = []
        self._rest_source = rest_source
        self._rest_frames = []
        self._rest_fps, self._rest_origin = 24.0, time.monotonic()
        self._fade = CrossFade(self.FADE_SECONDS)
        self._chained_pose = None
        self._latest_prediction = None
        self._clip_position = 0.0
        self._clip_at = None
        self._blink_frames = []
        self._shown_index = None
        self._lip_opening_limit = float(lip_opening_limit)
        if not np.isfinite(self._lip_opening_limit) or self._lip_opening_limit < 0:
            raise ValueError("Lip opening limit must be finite and nonnegative")
        self._gpu_budget = float(
            os.environ.get("TREND_DITTO_GPU_BUDGET", "1") if gpu_budget is None else gpu_budget
        )
        self._presentation_lead_ms = float(
            os.environ.get("TREND_DITTO_PRESENTATION_LEAD_MS", "160")
            if presentation_lead_ms is None
            else presentation_lead_ms
        )
        if not np.isfinite(self._gpu_budget) or not 0 < self._gpu_budget <= 1:
            raise ValueError("GPU budget must be greater than zero and at most one")
        if not np.isfinite(self._presentation_lead_ms) or self._presentation_lead_ms < 0:
            raise ValueError("Presentation lead must be finite and nonnegative")
        self.source_path, self.root = Path(source_path).resolve(), Path(root).resolve()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._presenter = None
        self._mouth = None
        self._mouth_transition = MouthTransition(1 / self.PRESENTATION_FPS)
        self._presentation_epoch = None
        self._mouth_mode = "source"
        self._presented_source_index = None
        self._ready = False
        self._epoch = -1
        self._audio = np.empty(0, np.float32)
        self._audio_end = 0
        self._audio_started_at = None
        self._last_push = 0.0
        self._last_voiced_at = None
        self._poses = PoseTimeline()
        self._drive = None
        self._neutral_drive = None
        self._selected_pose_sample = None
        self._pose_target_sample = None
        self._last_rendered_exp = None
        self._idle_frames = []
        self._wave_frames = []
        self._wave_info = None
        self._wave_started = None
        self._smile_started = None
        self._published_at = 0.0
        self._origin = time.monotonic()
        self._source_fps = 25.0
        self._wave_fps = 25.0
        self._latest = None
        self._sequence = 0
        self._next_render = 0.0
        self._error = None
        self._stats = {
            "generated_frames": 0,
            "motion_updates": 0,
            "dropped_stale_frames": 0,
            "dropped_stale_motion": 0,
            "unique_pose_frames": 0,
            "audio_clock_reanchors": 0,
            "interpolated_mouth_frames": 0,
        }
        self._timings = {
            key: deque(maxlen=120)
            for key in ("feature_ms", "motion_ms", "render_ms", "presentation_ms")
        }
        if self._reference_frame is not None:
            for key in ("retarget_ms", "decoder_ms"):
                self._timings[key] = deque(maxlen=120)
        self._rates = {key: deque(maxlen=120) for key in ("published", "rendered", "unique_pose")}
        self._work = deque(maxlen=120)
        self._metrics_started = time.monotonic()

    def reset(self, epoch):
        with self._lock:
            if epoch < self._epoch:
                return False
            self._epoch = epoch
            self._chained_pose = None
            self._audio = np.empty(0, np.float32)
            self._audio_end = 0
            self._audio_started_at = None
            self._last_push = 0.0
            self._last_voiced_at = None
            self._poses.clear()
            self._mouth = None
            self._mouth_mode = "source"
            self._presented_source_index = None
            self._drive = None
            self._selected_pose_sample = self._pose_target_sample = None
            self._last_rendered_exp = None
            for history in self._rates.values():
                history.clear()
            self._work.clear()
            self._metrics_started = time.monotonic()
            self._wave_started = None
            self._smile_started = None
            self._origin = self._rest_origin = time.monotonic()
            self._fade.clear()
            first = self._rest_frames[0] if self._rest_frames else None
            if first is None and self._idle_frames:
                first = self._idle_frames[0]
            if first is not None:
                self._sequence += 1
                self._latest = (epoch, first, self._sequence)
                self._published_at = time.monotonic()
            return True

    def push(self, epoch, pcm):
        pcm = np.asarray(pcm, dtype=np.float32)
        if pcm.ndim != 1 or len(pcm) != 320 or not np.isfinite(pcm).all():
            raise ValueError("Expected 320 finite mono float32 samples at 16 kHz")
        with self._lock:
            if epoch != self._epoch or self._stop.is_set():
                return False
            now = time.monotonic()
            self._audio = np.concatenate((self._audio, pcm))[-self.AUDIO_CAPACITY :]
            self._audio_end += len(pcm)
            if self._audio_started_at is None:
                self._audio_started_at = now - len(pcm) / 16000
            elif now - self._last_push > self.GAP_GRACE_SECONDS:
                # A packet gap does not add samples. Resume this bounded local
                # clock at received PCM instead of skipping resumed speech forever.
                self._audio_started_at = now - self._audio_end / 16000
                self._stats["audio_clock_reanchors"] += 1
            self._last_push = now
            if float(np.mean(pcm * pcm)) > 1e-6:
                self._last_voiced_at = now
        return True

    def _pad_silence(self, now):
        """Keep the audio clock running between utterances so Ditto never stops."""
        if not self._ditto_silence:
            return
        with self._lock:
            if self._audio_end <= 0 or self._audio_started_at is None:
                return
            missing = int((now - self._audio_started_at) * 16000) - self._audio_end
            if missing < 320:
                return
            quiet = np.zeros(min(missing, self.AUDIO_CAPACITY), np.float32)
            self._audio = np.concatenate((self._audio, quiet))[-self.AUDIO_CAPACITY :]
            self._audio_end += missing
            self._last_push = now

    def _voice_alpha(self, audio, end, sample, now):
        """Upstream's lip fade, timed to the audio of the pose on screen."""
        position = int(sample) - (end - len(audio))
        lo = max(0, position - self.VOICE_WINDOW_SAMPLES)
        hi = max(0, position + self.VOICE_WINDOW_SAMPLES // 2)
        window = audio[lo:hi]
        target = float(window.size > 0 and np.mean(window * window) > 1e-6)
        last = self._voice_at if self._voice_at is not None else now
        reach = max(0.0, now - last) / self.VOICE_FADE_SECONDS
        change = np.clip(target - self._voice_level, -reach, reach)
        self._voice_level, self._voice_at = float(self._voice_level + change), now
        return self._voice_level

    def _motion_active(self, now, end, last_push, last_voiced):
        if end <= 0 or now - last_push > self.GAP_GRACE_SECONDS:
            return False
        if self._ditto_silence:
            return True
        return last_voiced is not None and now - last_voiced <= self.MOUTH_REST_SECONDS

    def _audio_snapshot(self):
        with self._lock:
            return self._audio.copy(), self._audio_end

    def _publish(self, epoch, frame):
        with self._lock:
            if epoch != self._epoch or self._stop.is_set():
                self._stats["dropped_stale_frames"] += 1
                return False
            self._sequence += 1
            self._latest = (epoch, frame, self._sequence)
            self._published_at = time.monotonic()
            self._rates["published"].append(self._published_at)
            return True

    def _accept_motion(self, epoch, drives, end_sample):
        with self._lock:
            if epoch != self._epoch or self._stop.is_set():
                self._stats["dropped_stale_motion"] += 1
                return False
            self._poses.append(drives, end_sample=end_sample)
            self._stats["motion_updates"] += 1
            return True

    def _pose_at(self, epoch, now):
        with self._lock:
            if epoch != self._epoch or self._audio_started_at is None:
                return None
            target = max(
                0, (now - self._audio_started_at) * 16000 - self._presentation_lead_ms * 16
            )
            selected = self._poses.at(target)
            self._pose_target_sample = target
            self._selected_pose_sample = selected.sample if selected else None
            self._drive = selected.drive if selected else None
            return selected

    def _speech_active(self, now):
        with self._lock:
            return self._audio_end > 0 and now - self._last_push <= self.GAP_GRACE_SECONDS

    def _record_render(self, epoch, drive, started, finished):
        with self._lock:
            if epoch != self._epoch:
                return
            self._timings["render_ms"].append((finished - started) * 1000)
            self._rates["rendered"].append(finished)
            self._stats["generated_frames"] += 1
            expression = drive["exp"]
            if self._last_rendered_exp is None or not np.array_equal(
                expression, self._last_rendered_exp
            ):
                self._stats["unique_pose_frames"] += 1
                self._rates["unique_pose"].append(finished)
            self._last_rendered_exp = expression.copy()

    def latest_frame(self):
        with self._lock:
            return self._latest

    def _store_mouth(self, epoch, rgb, kind, region, index=None):
        with self._lock:
            if epoch != self._epoch or self._stop.is_set():
                self._stats["dropped_stale_frames"] += 1
                return False
            self._mouth = MouthFrame(epoch, kind, rgb, region, time.monotonic(), index)
            return True

    def _present_at(self, now):
        started = time.monotonic()
        with self._lock:
            epoch, mouth = self._epoch, self._mouth
            resting = (
                not self._ditto_silence
                and self._audio_end > 0
                and (
                    self._last_voiced_at is None
                    or now - self._last_voiced_at > self.MOUTH_REST_SECONDS
                )
            )
            if resting:
                self._mouth = None
        if resting:
            # Silence is the original relaxed smile, not the model's zero-audio pose.
            mouth = None
        if self._presentation_epoch != epoch:
            self._mouth_transition.clear()
            self._presentation_epoch = epoch
        index, kind = self._source_frame(now)
        frames = self._wave_frames if kind == "wave" else self._idle_frames
        if not frames:
            return False
        frame, blended, showing_rest = frames[index], False, False
        if mouth is not None and mouth.epoch == epoch and mouth.kind == kind:
            info = self._wave_info if kind == "wave" else self._info
            if self._composite == "full-face":
                # A generated face fits only the source frame it was made from, so that
                # frame is shown with it, exactly as upstream Ditto writes its video.
                index = self._shown_index = mouth.index
                frame = self._paste_face(frames[index], mouth.rgb, info, index)
            else:
                rgb, blended = self._mouth_transition.at(mouth, now)
                frame = composite_mouth(
                    frame,
                    rgb,
                    info["M_c2o_lst"][index],
                    info["mouth_regions"][index],
                    render_region=mouth.region,
                )
        else:
            self._mouth_transition.clear()
            if self._shown_index is not None and kind != "wave":
                # Faces lag the clip clock; continue from the frame on screen, not ahead of it.
                gap = abs(index - self._shown_index)
                if gap <= self.REST_CATCHUP_FRAMES:
                    with self._lock:
                        self._clip_position = max(0.0, self._clip_position - gap)
                    index = self._shown_index
                    frame = frames[index]
                self._shown_index = None
            if self._rest_frames and kind != "wave":
                position = rest_frame_index(
                    now - self._rest_origin, self._rest_fps, len(self._rest_frames)
                )
                frame, showing_rest = self._rest_frames[position], True
            elif self._rest_faces and kind != "wave":
                # This source speaks on its own, so silence uses its prepared closed mouth.
                frame = self._paste_face(frame, self._rest_faces[index], self._info, index)
        frame = self._fade.apply(frame, "rest" if showing_rest else "face", now)
        accepted = self._publish(epoch, frame)
        if accepted:
            with self._lock:
                self._stats["interpolated_mouth_frames"] += int(blended)
                self._mouth_mode = (
                    "generated"
                    if mouth is not None and mouth.epoch == epoch and mouth.kind == kind
                    else "source"
                )
                self._presented_source_index = index
                self._timings["presentation_ms"].append((time.monotonic() - started) * 1000)
        return accepted

    def _rest_face(self, index, source):
        """This frame's own face, with its mouth taken from a calm closed source frame."""
        if self._reference_frame is not None:
            return self._render(index, self._neutral_drive, vad_alpha=0.0)
        info, sdk = self._info, self._sdk
        own_face = self._render(index, self._neutral_drive)
        if source == index:
            return own_face
        own = info["x_s_info_lst"][index]
        drive = {key: value.copy() for key, value in self._neutral_drive.items()}
        for key in ("pitch", "yaw", "roll", "t", "scale"):
            drive[key] = own[key].copy()
        if self._expression_mode == "source-relative":
            drive["exp"] = calibrate_expression(
                drive["exp"],
                self._neutral_drive["exp"],
                info["mouth_expression_anchors"][source],
                opening_limit=self._lip_opening_limit,
            )
        stitch = sdk.motion_stitch
        keep = stitch.use_d_keys
        stitch.use_d_keys = ("exp", "pitch", "yaw", "roll", "t", "scale")
        if self._plain_ditto:
            # This drive is already absolute, so the relative offset must not apply.
            drive["exp"] = info["x_s_info_lst"][source]["exp"].copy()
            first_drive, stitch.d0, stitch.relative_d = stitch.d0, None, False
        try:
            source_kp, driving = stitch(info["x_s_info_lst"][source], drive)
        finally:
            stitch.use_d_keys = keep
            if self._plain_ditto:
                stitch.d0, stitch.relative_d = first_drive, True
        face = self._renderer(info["f_s_lst"][source], source_kp, driving)
        self._renderer.frame_ms.clear()
        calm_face = np.ascontiguousarray(face, dtype=np.float32)
        return blend_rest_mouth(own_face, calm_face, info["mouth_regions"][index])

    def _smooth_source(self, info):
        if not self._plain_ditto or self._reference_frame is not None:
            return
        from core.atomic_components.avatar_registrar import smooth_x_s_info_lst

        info["x_s_info_lst"] = smooth_x_s_info_lst(info["x_s_info_lst"], smo_k=13)
        if self._lip_factor is None:
            return
        # As the accepted offline clip: every source frame shares one closed lip pose.
        lips = closed_lip_shape([item["exp"] for item in info["x_s_info_lst"]])
        for item in info["x_s_info_lst"]:
            points = item["exp"].reshape(21, 3).copy()
            points[LIP_POINTS] = lips
            item["exp"] = points.reshape(item["exp"].shape)
        info["lip_rest_y"] = lips[:, 1] - lips[:, 1].mean()

    def _driven_keys(self):
        if not self._drive_head:
            return ("exp",)
        keys = ("exp", "pitch", "yaw", "roll", "t")
        return keys + ("scale",) if self._reference_frame is not None else keys

    def _prepares_source_mouth(self):
        # Donor lips are pasted into every frame unless the clip was closed in advance;
        # pasting them again leaves a seam that Ditto's decoder then copies.
        return self._reference_frame is not None and not self._closed_source

    def _needs_rest_faces(self):
        # Silence is covered by the standing clip when there is one.
        return self._composite == "full-face" and not self._rest_frames

    def _calm_sources(self):
        from core.atomic_components.motion_stitch import bin66_to_degree

        infos = self._info["x_s_info_lst"]
        poses = [
            [bin66_to_degree(i[key]).item() for key in ("pitch", "yaw", "roll")] for i in infos
        ]
        widths = [region[2] for region in self._info["mouth_regions"]]
        return calm_source_frames(self._info["mouth_apertures"], widths, poses)

    def _wave_source(self):
        if not self._wave_enabled:
            return None
        name = "Café_assistant_waving_hand_a1410f2d_1080p.mp4"
        for path in (self.root / name, self.root / "output" / name):
            if path.exists():
                return path
        return None

    def _paste_face(self, frame, face, info, index):
        if self._reference_frame is not None and not self._whole_head:
            return composite_whole_face(
                frame, face, info["M_c2o_lst"][index], info["face_landmarks"][index]
            )
        rgb = np.clip(face, 0, 255).astype(np.float32)  # Upstream blends float32 RGB.
        return self._sdk.putback(frame, rgb, info["M_c2o_lst"][index])

    def _presentation_worker(self):
        deadline = time.monotonic()
        try:
            while not self._stop.is_set():
                self._present_at(time.monotonic())
                deadline = max(deadline + 1 / self.PRESENTATION_FPS, time.monotonic())
                self._stop.wait(max(0, deadline - time.monotonic()))
        except Exception as exc:
            import traceback

            traceback.print_exc()
            with self._lock:
                self._error, self._ready = f"presentation: {type(exc).__name__}: {exc}", False
            self._stop.set()

    def action(self, name):
        with self._lock:
            if name == "wave" and self._wave_frames:
                self._wave_started = time.monotonic()
                self._smile_started = None
                return True
            if name == "smile":
                self._smile_started = time.monotonic()
                self._wave_started = None
                return True
            if name == "idle":
                self._wave_started = None
                self._smile_started = None
                return True
            return False

    def _source_frame(self, now):
        with self._lock:
            if self._wave_started is not None:
                index = int((now - self._wave_started) * self._wave_fps)
                if index < len(self._wave_frames):
                    return max(0, index), "wave"
                self._wave_started = None
            if self._smile_started is not None:
                if now - self._smile_started < 2.5:
                    return 0, "smile"
                self._smile_started = None
            count = max(1, len(self._idle_frames))
            index = self._clip_index(now)
            turn, offset = divmod(index, count)
            return (count - 1 - offset if turn % 2 else offset), "idle"

    def _in_blink(self, position):
        count = len(self._idle_frames)
        if not self._blink_frames or len(self._blink_frames) != count:
            return False
        turn, offset = divmod(int(position), count)
        return self._blink_frames[count - 1 - offset if turn % 2 else offset]

    def _clip_index(self, now):
        if not self._steady_motion:
            return int((now - self._origin) * self._source_fps)
        # Each face fits one source frame. Advancing at the rate faces are generated
        # shows every clip frame in order instead of skipping, in speech and silence alike.
        last = self._clip_at if self._clip_at is not None else now
        self._clip_at = now
        rate = (
            self.BLINK_CLIP_RATE if self._in_blink(self._clip_position) else self.STEADY_CLIP_RATE
        )
        self._clip_position += max(0.0, now - last) * self._source_fps * rate
        return int(self._clip_position)

    def _advance_render_clock(self, now, *, work_seconds=0):
        # This is a GPU-path wall-time budget, not measured device utilization.
        # Include feature and motion work, not just the face renderer, in the cost.
        budget_wait = work_seconds * (1 / self._gpu_budget - 1)
        self._next_render = max(self._next_render + 1 / self.TARGET_FPS, now + budget_wait)
        return self._next_render

    def status(self):
        with self._lock:
            now = time.monotonic()
            window = min(self.METRIC_WINDOW_SECONDS, max(1.0, now - self._metrics_started))
            result = dict(
                self._stats,
                ready=self._ready,
                epoch=self._epoch,
                audio_buffer_samples=len(self._audio),
                frame_backlog=int(self._latest is not None),
                error=self._error,
                target_fps=self.TARGET_FPS,
                presentation_fps=self.PRESENTATION_FPS,
                mouth_frame_age_ms=(now - self._mouth.at) * 1000 if self._mouth else None,
                sampling_steps=self.SAMPLING_STEPS,
                motion_stride_ms=self.MOTION_SAMPLES / 16,
                presentation_lead_ms=self._presentation_lead_ms,
                gap_grace_ms=self.GAP_GRACE_SECONDS * 1000,
                mouth_rest_ms=self.MOUTH_REST_SECONDS * 1000,
                mouth_mode=self._mouth_mode,
                source_frame_index=self._presented_source_index,
                gpu_budget=self._gpu_budget,
                renderer_backend=self._renderer_backend,
                expression_mode=self._expression_mode,
                lip_opening_limit=self._lip_opening_limit,
                composite=self._composite,
                reference_frame=self._reference_frame,
                steady_motion=self._steady_motion,
                plain_ditto=self._plain_ditto,
                lip_factor=self._lip_factor,
                lip_width=self._lip_width,
                whole_head=self._whole_head,
                drive_head=self._drive_head,
                head_gain=self._head_gain,
                turn_gain=self._turn_gain,
                rest_clip=bool(self._rest_frames),
                source_mouth_prepared=self._prepares_source_mouth(),
                ditto_silence=self._ditto_silence,
                renderer_region=getattr(getattr(self, "_renderer", None), "decoder_roi", None),
                gpu_budget_basis="feature_motion_render_wall_time",
                pose_buffer_frames=len(self._poses),
                dropped_pose_samples=self._poses.dropped,
                pose_audio_sample=self._selected_pose_sample,
                pose_target_sample=self._pose_target_sample,
                pose_staleness_ms=max(0, self._pose_target_sample - self._selected_pose_sample) / 16
                if self._pose_target_sample is not None and self._selected_pose_sample is not None
                else None,
                speech_active=self._audio_end > 0
                and now - self._last_push <= self.GAP_GRACE_SECONDS,
                metric_window_seconds=window,
                gpu_work_wall_fraction=sum(
                    min(duration, max(0, finished - (now - window)))
                    for finished, duration in self._work
                    if finished > now - window
                )
                / window,
                official_sampling_steps=50,
                quality_equivalence_verified=False,
                streaming=True,
                actions=["idle", "smile", *(["wave"] if self._wave_frames else [])],
                animation="wave"
                if self._wave_started
                else "smile"
                if self._smile_started
                else "idle",
                frame_age_ms=(now - self._published_at) * 1000 if self._published_at else None,
            )
            result.update(
                {
                    f"{key}_fps": sum(timestamp > now - window for timestamp in history) / window
                    for key, history in self._rates.items()
                }
            )
            result.update({k: float(np.mean(v)) if v else None for k, v in self._timings.items()})
            return result

    def start(self):
        if self._thread is not None:
            raise RuntimeError("Engine already started")
        self._initialized = threading.Event()
        self._thread = threading.Thread(target=self._worker, name="ditto-gpu", daemon=True)
        self._thread.start()
        self._initialized.wait()
        if self._error:
            raise RuntimeError(self._error)
        self._presenter = threading.Thread(
            target=self._presentation_worker, name="avatar-presenter", daemon=True
        )
        self._presenter.start()

    def _load(self):
        checkout = self.root / ".runtime/Ditto"
        sys.path[:0] = [str(self.root / ".runtime/ditto-packages"), str(checkout)]
        import cv2
        import onnxruntime as ort
        import torch
        from stream_pipeline_online import StreamSDK

        from scripts.ditto_torch import install_fused_renderer

        # TensorRT enqueue on CUDA's default stream introduces synchronization.
        # This worker owns all model calls and one dedicated Torch/TRT stream.
        self._cuda_stream = torch.cuda.Stream()
        torch.cuda.set_stream(self._cuda_stream)
        torch.set_num_threads(4)
        torch.set_grad_enabled(False)
        original_session = ort.InferenceSession

        def limited_session(*args, **kwargs):
            opts = ort.SessionOptions()
            opts.intra_op_num_threads, opts.inter_op_num_threads = 2, 1
            opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
            kwargs.setdefault("sess_options", opts)
            return original_session(*args, **kwargs)

        ort.InferenceSession = limited_session
        try:
            sdk = StreamSDK(
                str(checkout / "checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl"),
                str(checkout / "checkpoints/ditto_pytorch"),
            )
        finally:
            ort.InferenceSession = original_session
        self._sdk = sdk
        if self._renderer_backend.startswith("tensorrt"):
            from scripts.ditto_trt import HybridTensorRTRenderer

            models = checkout / "checkpoints/ditto_pytorch/models"
            self._renderer = HybridTensorRTRenderer(
                sdk.warp_f3d.warp_net.model,
                head_engine_path=self.root / ".runtime/ditto-warp-head.engine",
                decoder_engine_path=self.root / ".runtime/ditto-decoder-512.engine",
                manifest_path=self.root / ".runtime/ditto-trt.json",
                weight_paths={
                    "warp_head": models / "warp_network.pth",
                    "decoder": models / "decoder.pth",
                },
            )
            # The optimized renderer returns final RGB directly.
            sdk.warp_f3d = self._renderer
            sdk.decode_f3d = lambda frame: frame
        else:
            self._renderer = install_fused_renderer(sdk)
        shared_anchor = self._steady_motion
        info = register_source(
            sdk.avatar_registrar,
            str(self.source_path),
            max_dim=1280,
            shared_anchor=shared_anchor,
            close_mouth=self._prepares_source_mouth(),
        )
        self._smooth_source(info)
        self._info = info
        self._idle_frames = info["img_rgb_lst"]
        self._blink_frames = blink_flags(info.get("face_landmarks", []))
        if self._rest_source is not None:
            self._rest_frames, self._rest_fps = load_rest_clip(
                self._rest_source, self._idle_frames[0].shape[:2]
            )
            self._rest_origin = time.monotonic()
        capture = cv2.VideoCapture(str(self.source_path))
        self._source_fps = capture.get(cv2.CAP_PROP_FPS) or 25
        capture.release()
        # Precompute action features once so waving can also lip-sync incoming PCM.
        wave_path = self._wave_source()
        if wave_path is not None:
            self._wave_info = register_source(
                sdk.avatar_registrar, str(wave_path), max_dim=1280, shared_anchor=shared_anchor
            )
            self._smooth_source(self._wave_info)
            self._wave_frames = self._wave_info["img_rgb_lst"]
            capture = cv2.VideoCapture(str(wave_path))
            self._wave_fps = capture.get(cv2.CAP_PROP_FPS) or 24
            capture.release()
        if self._renderer_backend == "tensorrt-mouth":
            from scripts.ditto_trt import install_mouth_decoder

            infos = [info, *([self._wave_info] if self._wave_info else [])]
            sources = {self.source_path.name: self.source_path}
            if self._wave_info:
                sources[wave_path.name] = wave_path
            install_mouth_decoder(self._renderer, self.root, infos, sources)
        condition_info = info
        if self._reference_frame is not None:
            if self._reference_frame >= len(info["x_s_info_lst"]):
                raise ValueError("Reference frame lies outside the source clip")
            identity = info["x_s_info_lst"][self._reference_frame]
            condition_info = {
                **info,
                "x_s_info_lst": [identity],
                "sc": identity["kp"].flatten(),
                "eye_open_lst": [info["eye_open_lst"][self._reference_frame]],
                "eye_ball_lst": [info["eye_ball_lst"][self._reference_frame]],
            }
        sdk.condition_handler.setup(condition_info, 3, eye_f0_mode=True, ch_info=None)
        sdk.audio2motion.setup(
            condition_info["x_s_info_lst"][0],
            sampling_timesteps=self.SAMPLING_STEPS,
            online_mode=True,
        )
        sdk.motion_stitch.setup(
            N_d=-1,
            use_d_keys=self._driven_keys(),
            relative_d=self._plain_ditto and self._reference_frame is None,
            drive_eye=False,
            is_image_flag=info["is_image_flag"],
            x_s_info=info["x_s_info_lst"][0],
        )
        self._silence_feature = sdk.wav2feat(np.zeros(6480, np.float32))
        self._features = np.tile(self._silence_feature, (16, 1))
        self._neutral_drive = self._motion(self._features)[-1]
        # The motion decoder otherwise launches many small eager CUDA kernels
        # for every diffusion step. Compile the fixed-shape guidance function.
        from scripts.ditto_motion import install_motion_optimization

        install_motion_optimization(sdk.audio2motion.lmdm.model)
        motion_model = sdk.audio2motion.lmdm.model.model
        motion_model.prepare_conditioning = torch.compile(
            motion_model.prepare_conditioning,
            fullgraph=True,
            options={"triton.cudagraphs": False},
        )
        motion_model.guided_forward = torch.compile(
            motion_model.guided_forward, mode="reduce-overhead", fullgraph=True
        )
        self._neutral_drive = self._motion(self._features)[-1]
        for _ in range(12):
            self._render(0, self._neutral_drive)
        # Instrumentation is bounded even though the benchmark helper retains timings.
        self._renderer.frame_ms.clear()
        if self._needs_rest_faces():
            # Prepared once at startup; silence then needs no GPU work at all.
            calm = self._calm_sources()
            self._rest_faces = [
                np.rint(self._rest_face(index, calm[index])).clip(0, 255).astype(np.uint8)
                for index in range(len(self._idle_frames))
            ]
            self._renderer.frame_ms.clear()
        with self._lock:
            self._ready = True
        self.reset(max(0, self._epoch))

    def _motion(self, features):
        self._latest_prediction = self._predict_motion(features)
        return self._sdk.audio2motion.cvt_fmt(self._latest_prediction)

    def _motion_start(self):
        if self._reference_frame is not None:
            # A real closed identity is fixed; feeding predicted history back into
            # it drifts the resting expression across repeated utterances.
            return self._sdk.audio2motion.s_kp_cond
        pose = self._chained_pose
        return self._sdk.audio2motion.s_kp_cond if pose is None else pose

    def _chain_motion(self, frames):
        # A speaking source often starts away from its resting lips. Restarting each
        # window there purses the mouth, so continue from the last window as upstream does.
        if not self._steady_motion or self._reference_frame is not None:
            return
        source = self._sdk.audio2motion.s_kp_cond
        self._chained_pose = self._latest_prediction[:, frames - 1].astype(source.dtype)

    def _clear_motion_chain(self):
        self._chained_pose = None

    def _predict_motion(self, features):
        import torch

        sdk = self._sdk
        cond = sdk.condition_handler(features, 0)[None]
        # Reuse sampling noise across overlapping windows to avoid random facial
        # changes when the audio is unchanged. Restore the process RNG afterward.
        with torch.random.fork_rng(devices=[torch.cuda.current_device()]):
            torch.manual_seed(17)
            with torch.autocast("cuda", dtype=torch.float16):
                predicted = sdk.audio2motion.lmdm(self._motion_start(), cond, self.SAMPLING_STEPS)
        return predicted

    def _render(self, index, drive, info=None, vad_alpha=None):
        info, sdk = info if info is not None else self._info, self._sdk
        if self._reference_frame is not None:
            started = time.monotonic()
            own = info["x_s_info_lst"][index]
            render_drive = {key: value.copy() for key, value in drive.items()}
            strength = 1.0 if vad_alpha is None else vad_alpha
            render_drive["exp"] = speech_expression(
                own["exp"],
                drive["exp"],
                self._neutral_drive["exp"],
                self._lip_factor,
                strength,
                self._lip_width,
            )
            if self._drive_head:
                render_drive.update(
                    head_drive(
                        own, drive, self._neutral_drive, strength, self._head_gain, self._turn_gain
                    )
                )
            source, driving = sdk.motion_stitch(own, render_drive)
            stitched_at = time.monotonic()
            face = self._renderer(info["f_s_lst"][index], source, driving)
            decoded_at = time.monotonic()
            with self._lock:
                self._timings["retarget_ms"].append((stitched_at - started) * 1000)
                self._timings["decoder_ms"].append((decoded_at - stitched_at) * 1000)
            self._renderer.frame_ms.clear()
            return np.ascontiguousarray(face, dtype=np.float32)
        # Upstream stitching inserts source keys into the supplied dictionary.
        # Own this boundary so a rendered pose cannot corrupt the next overlap.
        render_drive = {key: value.copy() for key, value in drive.items()}
        if self._expression_mode == "source-relative" and self._neutral_drive is not None:
            anchors = info.get("mouth_expression_anchors")
            anchor = anchors[index] if anchors is not None else info["x_s_info_lst"][index]["exp"]
            render_drive["exp"] = calibrate_expression(
                render_drive["exp"],
                self._neutral_drive["exp"],
                anchor,
                opening_limit=self._lip_opening_limit,
            )
        if self._lip_factor is not None:
            render_drive["exp"] = compress_lips(
                render_drive["exp"], info["lip_rest_y"], self._lip_factor
            )
        controls = {} if vad_alpha is None else {"vad_alpha": vad_alpha}
        source, driving = sdk.motion_stitch(info["x_s_info_lst"][index], render_drive, **controls)
        face = self._renderer(info["f_s_lst"][index], source, driving)
        self._renderer.frame_ms.clear()
        return np.ascontiguousarray(face, dtype=np.float32)

    def _worker(self):
        try:
            self._load()
            self._initialized.set()
            seen_epoch, processed = None, 0
            while not self._stop.is_set():
                now = time.monotonic()
                if now < self._next_render:
                    self._stop.wait(self._next_render - now)
                    continue
                self._pad_silence(now)
                with self._lock:
                    epoch, audio, end, last_push, last_voiced = (
                        self._epoch,
                        self._audio.copy(),
                        self._audio_end,
                        self._last_push,
                        self._last_voiced_at,
                    )
                if epoch != seen_epoch:
                    self._features = np.tile(self._silence_feature, (16, 1))
                    seen_epoch, processed = epoch, 0
                    self._voice_level, self._voice_at = 0.0, None
                aligned = end // self.MOTION_SAMPLES * self.MOTION_SAMPLES
                active = self._motion_active(now, end, last_push, last_voiced)
                work_seconds = 0.0
                if active and aligned > processed:
                    started = time.monotonic()
                    # Catch up at most four chunks. Older missed context is replaced by
                    # silence rather than accumulating an unbounded feature work queue.
                    first = max(processed + self.MOTION_SAMPLES, aligned - 3 * self.MOTION_SAMPLES)
                    if first > processed + self.MOTION_SAMPLES:
                        self._features = np.tile(self._silence_feature, (16, 1))
                        self._clear_motion_chain()
                    for endpoint in range(first, aligned + 1, self.MOTION_SAMPLES):
                        chunk = np.zeros(6480, np.float32)
                        start = endpoint - 6480
                        lo, hi = max(start, end - len(audio), 0), min(endpoint, end)
                        chunk[lo - start : hi - start] = audio[
                            lo - (end - len(audio)) : hi - (end - len(audio))
                        ]
                        feature = self._sdk.wav2feat(chunk)
                        advance = self.MOTION_SAMPLES // 640
                        self._features = np.concatenate(
                            (self._features[advance:], feature[-advance:])
                        )
                    feature_ms = (time.monotonic() - started) * 1000
                    work_seconds += feature_ms / 1000
                    started = time.monotonic()
                    drives = self._motion(self._features)
                    motion_ms = (time.monotonic() - started) * 1000
                    work_seconds += motion_ms / 1000
                    if not self._accept_motion(epoch, drives, aligned):
                        self._advance_render_clock(time.monotonic(), work_seconds=work_seconds)
                        continue
                    self._chain_motion(
                        (aligned - max(processed, first - self.MOTION_SAMPLES)) // 640
                    )
                    with self._lock:
                        self._timings["feature_ms"].append(feature_ms)
                        self._timings["motion_ms"].append(motion_ms)
                    processed = aligned
                index, kind = self._source_frame(time.monotonic())
                if not active:
                    # The presenter uses the original source smile during rest.
                    # Silent packets must not trigger neutral-mouth inference.
                    self._clear_motion_chain()
                    self._advance_render_clock(time.monotonic())
                    continue
                if active:
                    selected = self._pose_at(epoch, time.monotonic()) if active else None
                    drive = selected.drive if selected is not None else self._neutral_drive
                    started = time.monotonic()
                    info = self._wave_info if kind == "wave" else self._info
                    alpha = None
                    if self._ditto_silence:
                        sample = selected.sample if selected is not None else end
                        alpha = self._voice_alpha(audio, end, sample, started)
                    face = self._render(index, drive, info, vad_alpha=alpha)
                    finished = time.monotonic()
                    work_seconds += finished - started
                    self._record_render(epoch, drive, started, finished)
                else:
                    self._advance_render_clock(time.monotonic())
                    continue
                published = self._store_mouth(
                    epoch, face, kind, info["mouth_regions"][index], index
                )
                finished = time.monotonic()
                if published:
                    if work_seconds:
                        with self._lock:
                            self._work.append((finished, work_seconds))
                self._advance_render_clock(finished, work_seconds=work_seconds)
        except Exception as exc:
            import traceback

            traceback.print_exc()
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"
                self._ready = False
        finally:
            self._initialized.set()
            if hasattr(self, "_sdk"):
                self._sdk.avatar_registrar.source2info.landmark478.model.detector.close()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        if self._presenter is not None:
            self._presenter.join(timeout=2)
        with self._lock:
            self._ready = False
