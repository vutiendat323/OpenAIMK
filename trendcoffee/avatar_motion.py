"""Thread-safe source-frame selection, independent of GPU/audio implementation."""

from threading import RLock


class MotionController:
    @classmethod
    def from_manifest(cls, manifest, *, talking_count, wave_count):
        source = manifest.get("idle_source", "wave")
        if source not in ("talking", "wave"):
            raise ValueError("invalid_idle_source")
        idle_count = talking_count if source == "talking" else wave_count
        idle_offset = 0 if source == "talking" else talking_count
        idle = manifest["idle_range"]
        smile = manifest["smile_range"]
        if not (0 <= idle[0] < idle[1] <= idle_count and 0 <= smile[0] < smile[1] <= wave_count):
            raise ValueError("invalid_motion_range")
        return cls(
            talking=(0, talking_count),
            wave=(talking_count, talking_count + wave_count),
            idle=tuple(idle_offset + n for n in idle),
            smile=tuple(talking_count + n for n in smile),
        )

    def __init__(self, *, talking, wave, idle, smile):
        self.ranges = dict(talking=talking, wave=wave, idle=idle, smile=smile)
        if any(start < 0 or end <= start for start, end in self.ranges.values()):
            raise ValueError("invalid_motion_range")
        self.lock = RLock()
        self.epoch = 0
        self.mode = "idle"
        self.position = 0
        self.oneshot = None

    def action(self, name):
        with self.lock:
            if name not in ("idle", "wave", "smile"):
                return False
            self.oneshot = name if name != "idle" else None
            self.mode, self.position = name, 0
            return True

    def reset(self, epoch):
        with self.lock:
            self.epoch = epoch
            self.oneshot = None
            self.mode, self.position = "idle", 0

    def frames(self, count, *, speaking):
        with self.lock:
            result = []
            for _ in range(count):
                mode = self.oneshot or ("talking" if speaking else "idle")
                if mode != self.mode:
                    # A neutral clip can supply both modes. Keep its head/body
                    # motion continuous when PCM starts or stops between batches.
                    if self.ranges[mode] != self.ranges[self.mode]:
                        self.position = 0
                    self.mode = mode
                start, end = self.ranges[mode]
                size = end - start
                if self.oneshot:
                    index = self.position
                else:
                    cycle = self.position % (size * 2)
                    index = cycle if cycle < size else size * 2 - cycle - 1
                result.append(start + index)
                self.position += 1
                if self.oneshot and self.position >= size:
                    self.oneshot = None
            return result
