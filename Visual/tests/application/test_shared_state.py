"""SharedState: the frame hand-off between the camera loop and the workers."""

import time

import numpy as np

from Visual.application.state import SharedState


class TestFrameSharing:
    """put_frame owns the copy; get_latest_frame must not copy again.

    cap.read() reuses its buffer, so put_frame has to snapshot. Consumers
    only read, so handing them the same array is safe and saves ~0.9 MB
    per call at ~150 calls/s.
    """

    def test_put_frame_isolates_caller_buffer(self):
        state = SharedState()
        buf = np.zeros((4, 4, 3), dtype=np.uint8)
        state.put_frame(buf)
        buf[0, 0, 0] = 255  # simulate cap.read() reusing the buffer
        assert state.get_latest_frame()[0, 0, 0] == 0

    def test_get_latest_frame_does_not_copy(self):
        state = SharedState()
        state.put_frame(np.zeros((4, 4, 3), dtype=np.uint8))
        assert state.get_latest_frame() is state.get_latest_frame()

    def test_get_latest_frame_none_before_first_put(self):
        assert SharedState().get_latest_frame() is None

    def test_frame_seq_counts_published_frames(self):
        state = SharedState()
        for _ in range(3):
            state.put_frame(np.zeros((2, 2, 3), dtype=np.uint8))
        assert state.frame_seq == 3


class TestFrameSnapshot:
    """get_frame_snapshot hands the tracker a (frame, seq, ts) triple that
    can never straddle a concurrent put_frame."""

    def test_none_before_first_put(self):
        assert SharedState().get_frame_snapshot() is None

    def test_snapshot_matches_put_frame_fields(self):
        state = SharedState()
        state.put_frame(np.zeros((2, 2, 3), dtype=np.uint8), timestamp=123.0)
        frame, seq, ts = state.get_frame_snapshot()
        assert seq == 1 and ts == 123.0
        assert frame is state.get_latest_frame()  # same array, no extra copy

    def test_default_timestamp_is_time_time(self):
        state = SharedState()
        before = time.time()
        state.put_frame(np.zeros((2, 2, 3), dtype=np.uint8))
        after = time.time()
        _, _, ts = state.get_frame_snapshot()
        assert before <= ts <= after

    def test_seq_and_ts_advance_together(self):
        state = SharedState()
        state.put_frame(np.zeros((2, 2, 3), dtype=np.uint8), timestamp=1.0)
        state.put_frame(np.zeros((2, 2, 3), dtype=np.uint8), timestamp=2.0)
        _, seq, ts = state.get_frame_snapshot()
        assert (seq, ts) == (2, 2.0)


class TestAsdBuffer:
    def test_shared_state_exposes_an_avbuffer(self):
        from Visual.domain.active_speaker import AVBuffer
        assert isinstance(SharedState().asd, AVBuffer)


class TestLockSplit:
    """A 0.9 MB frame write must not stall readers of the scene or timings."""

    def test_scene_and_timings_readable_while_frame_lock_held(self):
        state = SharedState()
        with state._frame_lock:          # would deadlock on a single shared lock
            state.set_timing("track", 5.0)
            assert state.timings()["track"] == 5.0
            assert state.scene.snapshot().people == ()
