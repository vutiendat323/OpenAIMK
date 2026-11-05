"""Original PCM on a continuous audio clock; video releases each turn's onset."""

from collections import deque
from threading import RLock


class AvatarPlayout:
    def __init__(self):
        self.lock = RLock()
        self.epoch = 0
        self.pending = deque()
        self.active = False

    def reset(self, epoch):
        with self.lock:
            self.epoch = epoch
            self.pending.clear()
            self.active = False

    def push(self, epoch, sequence, pcm):
        with self.lock:
            if epoch != self.epoch:
                return
            if len(pcm) != 1920:
                raise ValueError("invalid_playout_frame")
            if len(self.pending) >= 75:
                raise BufferError("avatar_playout_backlog")
            self.pending.append((sequence, pcm))

    def activate(self, epoch, sequence):
        with self.lock:
            if epoch == self.epoch and self.pending and self.pending[0][0] <= sequence:
                self.active = True

    def read(self):
        with self.lock:
            if self.active and self.pending:
                return self.pending.popleft()[1]
            # Once a turn starts, a packet gap must not re-gate the speaker on
            # GPU output. Explicit interruption/reset is the turn boundary.
            return bytes(1920)
