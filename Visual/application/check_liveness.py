"""Check liveness: tag each face the Scene knows about as live or spoof.

Handed the spoof checker it runs -- it never builds it.
"""

import time

from Visual.application.ports import SpoofChecker
from Visual.application.state import SharedState
from Visual.config import Config


def _spoof_loop(state: SharedState, cfg: Config, spoof_detector: SpoofChecker) -> None:
    """Every ``cfg.spoof_interval_sec``, tag each face live or spoof.

    *spoof_detector* has ``check_faces(frame, boxes) -> {index: (is_spoof, score)}``.
    """
    while state.running:
        time.sleep(cfg.spoof_interval_sec)

        people = state.scene.snapshot().people
        generation = state.scene.generation
        snapshot = state.get_frame_snapshot()
        if snapshot is None or not people:
            continue

        frame, _, captured_at = snapshot
        t0 = time.perf_counter()
        try:
            results = spoof_detector.check_faces(frame, [p.box for p in people])
            tags = {p.id: results.get(i, (True, 0.0)) for i, p in enumerate(people)}
        except Exception as e:
            print(f"[spoof] error: {e}")
            tags = {}  # unavailable PAD never becomes a live-person result

        state.scene.observe_spoof(tags, captured_at=captured_at, generation=generation)
        state.set_timing("spoof", (time.perf_counter() - t0) * 1000.0)
