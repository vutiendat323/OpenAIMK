"""AVBuffer: bounded, thread-safe audio/video window assembly."""

import numpy as np
import pytest

from Visual.domain.active_speaker import AsdResult, AsdWindow, AVBuffer

PACKET_SECS = 0.080
PACKET_SAMPLES = 1280


def feed_window(buffer, stream_id, track_id, audio_t0, video_shift):
    """13 consecutive 80 ms audio packets ending at audio_t0 + 1.0 s, 25
    timestamped 112x112 crops centered on the same window at *video_shift*,
    and select *track_id*. Enough for one full ``next_window`` at
    ``offset_secs=video_shift``.
    """
    first_t0 = audio_t0 - 0.04  # 1s is 12.5 packets: the window starts mid-packet
    results = []
    for i in range(13):
        pcm = np.full(PACKET_SAMPLES, i % 100, dtype=np.int16)
        results.append(buffer.push_audio(stream_id, i, first_t0 + i * PACKET_SECS, pcm))
    buffer.select_track(track_id)
    for k in range(25):
        ts = audio_t0 + video_shift + 0.02 + 0.04 * k
        crop = np.full((112, 112), k, dtype=np.uint8)
        buffer.push_crop(track_id, ts, crop)
    return results


class TestOffsetAndShapes:
    def test_offset_sign_and_window_shapes(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        feed_window(buffer, "s1", 17, audio_t0=100.0, video_shift=0.2)
        window = buffer.next_window(offset_secs=0.2, now=101.3)
        assert window is not None and window.track_id == 17
        assert window.stream_id == "s1"
        assert window.audio_t0 == pytest.approx(100.0)
        assert window.pcm16.shape == (16000,)
        assert window.pcm16.dtype == np.int16
        assert window.crops.shape == (25, 112, 112)
        assert window.crops.dtype == np.uint8

    def test_wrong_offset_finds_no_matching_crops(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        feed_window(buffer, "s1", 17, audio_t0=100.0, video_shift=0.2)
        # Crops were only laid down for a 0.2s shift; a wildly different
        # offset can't find a bin partner within the 80ms tolerance.
        assert buffer.next_window(offset_secs=-0.4, now=101.3) is None

    def test_no_repeated_window_at_unchanged_audio_end(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        feed_window(buffer, "s1", 17, audio_t0=100.0, video_shift=0.0)
        first = buffer.next_window(offset_secs=0.0, now=101.3)
        assert first is not None
        assert buffer.next_window(offset_secs=0.0, now=101.3) is None

    def test_new_window_after_more_audio_arrives(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        feed_window(buffer, "s1", 17, audio_t0=100.0, video_shift=0.0)
        assert buffer.next_window(offset_secs=0.0, now=101.3) is not None
        # One more contiguous packet advances the window end.
        buffer.push_audio("s1", 13, 100.0 + 1.0, np.zeros(PACKET_SAMPLES, np.int16))
        for k in range(25):
            buffer.push_crop(17, 100.08 + 0.02 + 0.04 * k, np.full((112, 112), k, np.uint8))
        second = buffer.next_window(offset_secs=0.0, now=102.0)
        assert second is not None
        assert second.audio_t0 > 100.0

    def test_model_never_needs_the_lock_held_windows_are_copies(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        feed_window(buffer, "s1", 17, audio_t0=100.0, video_shift=0.0)
        window = buffer.next_window(offset_secs=0.0, now=101.3)
        window.pcm16[0] = 12345
        window.crops[0, 0, 0] = 255
        # Mutating the returned copy must not corrupt buffer-internal state.
        buffer.select_track(None)
        buffer.select_track(17)
        feed_window(buffer, "s1", 17, audio_t0=200.0, video_shift=0.0)
        again = buffer.next_window(offset_secs=0.0, now=201.3)
        assert again.pcm16[0] != 12345


class TestPushAudio:
    def test_first_packet_after_start_is_a_reset_not_contiguous(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        assert buffer.push_audio("s1", 0, 100.0, np.zeros(PACKET_SAMPLES, np.int16)) is False

    def test_contiguous_packets_accepted(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.push_audio("s1", 0, 100.0, np.zeros(PACKET_SAMPLES, np.int16))
        assert buffer.push_audio("s1", 1, 100.08, np.zeros(PACKET_SAMPLES, np.int16)) is True

    def test_wrong_stream_rejected(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        assert buffer.push_audio("other", 0, 100.0, np.zeros(PACKET_SAMPLES, np.int16)) is False

    def test_wrong_sample_count_rejected(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        assert buffer.push_audio("s1", 0, 100.0, np.zeros(999, np.int16)) is False

    def test_non_int16_dtype_rejected_not_cast(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        pcm = np.zeros(PACKET_SAMPLES, dtype=np.float32)
        assert buffer.push_audio("s1", 0, 100.0, pcm) is False
        assert buffer._audio == []

    def test_sequence_gap_clears_and_resets(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=100.0, video_shift=0.0)
        window = buffer.next_window(offset_secs=0.0, now=101.3)
        assert window is not None
        buffer.publish(AsdResult("s1", 1, window.audio_t0, np.zeros(25, np.float32)))
        assert buffer.latest_result(100.5) is not None
        # Skip a sequence number: a gap.
        ok = buffer.push_audio("s1", 99, 101.0, np.zeros(PACKET_SAMPLES, np.int16))
        assert ok is False
        assert buffer.latest_result(100.5) is None  # current result cleared
        # Accumulation restarted: not enough audio yet for a window.
        assert buffer.next_window(offset_secs=0.0, now=101.1) is None

    def test_timestamp_discontinuity_clears_and_resets(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.push_audio("s1", 0, 100.0, np.zeros(PACKET_SAMPLES, np.int16))
        # seq is contiguous but t0 jumped by more than 20ms.
        ok = buffer.push_audio("s1", 1, 100.5, np.zeros(PACKET_SAMPLES, np.int16))
        assert ok is False

    def test_a_late_in_flight_result_from_before_a_gap_cannot_publish(self):
        # Reviewer probe: a window computed just before a gap must not be
        # accepted once the gap has reset _result (which would otherwise be
        # the only thing stopping it, and _result is exactly what a gap
        # clears).
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(17)
        feed_window(buffer, "s1", 17, audio_t0=100.0, video_shift=0.0)
        window = buffer.next_window(offset_secs=0.0, now=101.3)
        assert window is not None
        stale = AsdResult("s1", 17, window.audio_t0, np.full(25, 0.9, np.float32))
        # A gap: seq 50 instead of 13, well past the window's own audio.
        buffer.push_audio("s1", 50, 102.0, np.zeros(PACKET_SAMPLES, np.int16))
        assert buffer.publish(stale) is False
        assert buffer.latest_result(102.5) is None

    def test_a_late_in_flight_result_across_a_track_flip_cannot_publish(self):
        # A -> B -> A: an in-flight result computed for A before the flip
        # must not be accepted once A is reselected, even though _result was
        # cleared twice in between (matching neither track_id nor "None" the
        # way a stream mismatch would).
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=100.0, video_shift=0.0)
        window = buffer.next_window(offset_secs=0.0, now=101.3)
        assert window is not None
        stale = AsdResult("s1", 1, window.audio_t0, np.full(25, 0.9, np.float32))

        buffer.select_track(2)          # A -> B
        buffer.select_track(1)          # B -> A: track_id matches again

        assert buffer.publish(stale) is False
        assert buffer.latest_result(102.5) is None

    def test_within_tolerance_timestamp_jitter_still_contiguous(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.push_audio("s1", 0, 100.0, np.zeros(PACKET_SAMPLES, np.int16))
        assert buffer.push_audio("s1", 1, 100.08 + 0.019, np.zeros(PACKET_SAMPLES, np.int16)) is True

    def test_backward_clock_jump_resets_last_window_end(self):
        # Without clearing _last_window_end on a reset, a clock that jumps
        # backward would never produce another window: every future end
        # would still be <= the old (now meaningless) high-water mark.
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=200.0, video_shift=0.0)
        assert buffer.next_window(offset_secs=0.0, now=201.3) is not None  # end ~= 201.0

        # A backward jump: same seq continuation but a much earlier t0.
        buffer.push_audio("s1", 100, 50.0, np.zeros(PACKET_SAMPLES, np.int16))
        for i in range(1, 13):
            buffer.push_audio("s1", 100 + i, 50.0 + i * PACKET_SECS,
                              np.zeros(PACKET_SAMPLES, np.int16))
        for k in range(25):
            buffer.push_crop(1, 50.0 + 0.02 + 0.04 * k, np.full((112, 112), k, np.uint8))
        second = buffer.next_window(offset_secs=0.0, now=51.5)
        assert second is not None
        assert second.audio_t0 < 60.0  # nowhere near the old, much later window

    def test_history_pruned_to_three_seconds(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        n = int(6.0 / PACKET_SECS)
        t0 = 100.0
        buffer.push_audio("s1", 0, t0, np.zeros(PACKET_SAMPLES, np.int16))
        for i in range(1, n):
            buffer.push_audio("s1", i, t0 + i * PACKET_SECS, np.zeros(PACKET_SAMPLES, np.int16))
        oldest_t0 = buffer._audio[0][1]
        newest_end = buffer._audio[-1][1] + PACKET_SECS
        assert newest_end - oldest_t0 <= 3.0 + PACKET_SECS


class TestPushCrop:
    def test_crop_for_non_selected_track_ignored(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        buffer.push_crop(2, 100.0, np.zeros((112, 112), np.uint8))
        assert buffer._crops == []

    def test_backward_camera_clock_clears_crop_history(self):
        # A camera clock step backward would otherwise leave the list
        # unsorted, and front-only pruning would never bound it again.
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        for i in range(5):
            buffer.push_crop(1, 100.0 + i * 0.04, np.full((112, 112), i, np.uint8))
        assert len(buffer._crops) == 5
        buffer.push_crop(1, 99.0, np.full((112, 112), 99, np.uint8))  # backward
        assert len(buffer._crops) == 1
        assert buffer._crops[0][0] == 99.0

    def test_crop_history_pruned_to_three_seconds(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        for i in range(200):
            buffer.push_crop(1, i * 0.04, np.zeros((112, 112), np.uint8))
        oldest_ts = buffer._crops[0][0]
        newest_ts = buffer._crops[-1][0]
        assert newest_ts - oldest_ts <= 3.0 + 0.04


class TestTrackSelection:
    def test_select_same_track_is_a_no_op(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        buffer.push_crop(1, 100.0, np.full((112, 112), 7, np.uint8))
        buffer.select_track(1)
        assert len(buffer._crops) == 1

    def test_select_other_track_clears_crops_and_result(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=100.0, video_shift=0.0)
        window = buffer.next_window(offset_secs=0.0, now=101.3)
        buffer.publish(AsdResult("s1", 1, window.audio_t0, np.zeros(25, np.float32)))
        assert buffer.latest_result(100.5) is not None  # published, before the switch
        buffer.select_track(2)
        assert buffer._crops == []
        assert buffer.latest_result(100.5) is None

    def test_select_none_clears_crops_and_result(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        buffer.push_crop(1, 100.0, np.zeros((112, 112), np.uint8))
        buffer.select_track(None)
        assert buffer._crops == []


class TestStreamLifecycle:
    def test_active_false_until_started(self):
        assert AVBuffer().active is False

    def test_active_true_between_start_and_stop(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        assert buffer.active is True
        buffer.stop_stream("s1")
        assert buffer.active is False

    def test_stop_with_wrong_id_is_a_no_op(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.stop_stream("other")
        assert buffer.active is True

    def test_start_stream_replaces_and_clears_everything(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=100.0, video_shift=0.0)
        window = buffer.next_window(offset_secs=0.0, now=101.3)
        buffer.publish(AsdResult("s1", 1, window.audio_t0, np.zeros(25, np.float32)))
        assert buffer.latest_result(100.5) is not None  # published, before the restart
        buffer.start_stream("s2")
        assert buffer._audio == [] and buffer._crops == []
        assert buffer.latest_result(100.5) is None
        assert buffer.next_window(offset_secs=0.0, now=101.0) is None

    def test_old_stream_cannot_publish_after_reset(self):
        buffer = AVBuffer()
        buffer.start_stream("s2")
        old = AsdResult("s1", 17, 100.0, np.full(25, 0.9, np.float32))
        assert not buffer.publish(old)
        assert buffer.latest_result(101.0) is None


class TestPublishAndLatestResult:
    def test_publish_requires_current_stream_and_selected_track(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=100.0, video_shift=0.0)
        window = buffer.next_window(offset_secs=0.0, now=101.3)
        assert window is not None
        assert buffer.publish(AsdResult("s1", 2, window.audio_t0, np.zeros(25, np.float32))) is False
        assert buffer.publish(AsdResult("other", 1, window.audio_t0, np.zeros(25, np.float32))) is False
        assert buffer.publish(AsdResult("s1", 1, window.audio_t0, np.zeros(25, np.float32))) is True

    def test_publish_accepts_only_the_exact_issued_window(self):
        # publish() no longer compares against the last published result's
        # audio_t0 (a monotonic floor); it must match the one window
        # next_window() actually handed out, exactly -- neither older nor a
        # fabricated "newer" value is accepted.
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=100.0, video_shift=0.0)
        window = buffer.next_window(offset_secs=0.0, now=101.3)
        assert window is not None
        assert buffer.publish(AsdResult("s1", 1, window.audio_t0 - 1.0, np.zeros(25, np.float32))) is False
        assert buffer.publish(AsdResult("s1", 1, window.audio_t0 + 1.0, np.zeros(25, np.float32))) is False
        assert buffer.publish(AsdResult("s1", 1, window.audio_t0, np.zeros(25, np.float32))) is True

    def test_a_newer_next_window_call_supersedes_an_older_in_flight_one(self):
        # Single-worker contract: calling next_window a second time (a newer
        # "take") moves the token, so the earlier window's result -- even
        # though it was genuinely issued and never reset -- can no longer
        # land once a newer one has been taken.
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=100.0, video_shift=0.0)
        first = buffer.next_window(offset_secs=0.0, now=101.3)
        assert first is not None
        buffer.push_audio("s1", 13, 100.0 + 1.0, np.zeros(PACKET_SAMPLES, np.int16))
        for k in range(25):
            buffer.push_crop(1, 100.08 + 0.02 + 0.04 * k, np.full((112, 112), k, np.uint8))
        second = buffer.next_window(offset_secs=0.0, now=102.0)
        assert second is not None and second.audio_t0 != first.audio_t0

        assert buffer.publish(AsdResult("s1", 1, first.audio_t0, np.zeros(25, np.float32))) is False
        assert buffer.publish(AsdResult("s1", 1, second.audio_t0, np.zeros(25, np.float32))) is True

    def test_latest_result_none_when_absent(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        assert buffer.latest_result(100.0) is None

    def test_latest_result_expires_after_support_end_plus_one_second(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=100.0, video_shift=0.0)
        window = buffer.next_window(offset_secs=0.0, now=101.3)
        assert window is not None
        buffer.publish(AsdResult("s1", 1, window.audio_t0, np.zeros(25, np.float32)))
        assert buffer.latest_result(window.audio_t0 + 2.0) is not None
        assert buffer.latest_result(window.audio_t0 + 2.01) is None

    def test_backward_clock_jump_discards_the_stale_in_flight_result(self):
        # Reviewer probe: a window taken just before a backward clock jump
        # (audio_t0=200.04) must not publish once the jump has reset the
        # issued-window token, even though its own audio_t0 is *larger* than
        # the fresh post-jump window's -- a floor on audio_t0 alone cannot
        # tell "stale" from "smaller", but an exact token match can.
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.select_track(1)
        feed_window(buffer, "s1", 1, audio_t0=200.0, video_shift=0.0)
        stale = buffer.next_window(offset_secs=0.0, now=201.3)
        assert stale is not None and stale.audio_t0 == pytest.approx(200.0)

        # The backward jump: seq continues, but the timestamp lands far in
        # the past -- a discontinuity, not a contiguous packet.
        buffer.push_audio("s1", 13, 50.0, np.zeros(PACKET_SAMPLES, np.int16))
        assert buffer.publish(AsdResult("s1", 1, stale.audio_t0, np.zeros(25, np.float32))) is False
        assert buffer.latest_result(50.1) is None

        # Enough contiguous post-jump audio and matching crops produce a
        # fresh window, and *its* result is accepted and served.
        for i in range(1, 13):
            buffer.push_audio("s1", 13 + i, 50.0 + i * PACKET_SECS, np.zeros(PACKET_SAMPLES, np.int16))
        for k in range(25):
            buffer.push_crop(1, 50.0 + 0.02 + 0.04 * k, np.full((112, 112), k, np.uint8))
        fresh = buffer.next_window(offset_secs=0.0, now=51.5)
        assert fresh is not None and fresh.audio_t0 == pytest.approx(50.04)

        assert buffer.publish(AsdResult("s1", 1, fresh.audio_t0, np.full(25, 0.7, np.float32))) is True
        served = buffer.latest_result(51.5)
        assert served is not None and served.audio_t0 == pytest.approx(50.04)


# ---------------------------------------------------------------------------
# Protocol v2: pinned track, input signal, publish listener.
# ---------------------------------------------------------------------------

import threading
import time


def _issued(buffer, stream_id="s1", track_id=7):
    buffer.start_stream(stream_id)
    feed_window(buffer, stream_id, track_id, 100.0, 0.0)
    return buffer.next_window(offset_secs=0.0, now=101.0)


class TestPinnedTrack:
    def test_pin_selects_the_track_and_is_reported(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.pin_track(5)
        assert buffer.pinned_track == 5
        assert buffer._track_id == 5

    def test_unpin_keeps_the_current_selection(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.pin_track(5)
        buffer.pin_track(None)
        assert buffer.pinned_track is None
        assert buffer._track_id == 5

    def test_the_pin_belongs_to_the_stream(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        buffer.pin_track(5)
        buffer.start_stream("s2")
        assert buffer.pinned_track is None
        buffer.pin_track(6)
        buffer.stop_stream("s2")
        assert buffer.pinned_track is None


class TestPublishListener:
    def test_listener_gets_each_published_result(self):
        buffer = AVBuffer()
        window = _issued(buffer)
        seen = []
        buffer.set_publish_listener(seen.append)
        result = AsdResult("s1", 7, window.audio_t0, np.full(25, 0.9, np.float32))
        assert buffer.publish(result)
        assert seen == [result]

    def test_a_refused_result_never_reaches_the_listener(self):
        buffer = AVBuffer()
        window = _issued(buffer)
        seen = []
        buffer.set_publish_listener(seen.append)
        stale = AsdResult("s1", 7, window.audio_t0 - 0.08, np.full(25, 0.9, np.float32))
        assert not buffer.publish(stale)
        assert seen == []

    def test_a_failing_listener_never_breaks_publish(self):
        buffer = AVBuffer()
        window = _issued(buffer)

        def boom(_result):
            raise RuntimeError("socket gone")

        buffer.set_publish_listener(boom)
        result = AsdResult("s1", 7, window.audio_t0, np.full(25, 0.9, np.float32))
        assert buffer.publish(result)
        assert buffer.latest_result(101.0) is result


class TestInputSignal:
    def test_wait_returns_as_soon_as_audio_arrives(self):
        buffer = AVBuffer()
        buffer.start_stream("s1")
        done = threading.Event()

        def waiter():
            buffer.wait_for_input(2.0)
            done.set()

        thread = threading.Thread(target=waiter)
        thread.start()
        time.sleep(0.05)
        started = time.monotonic()
        buffer.push_audio("s1", 0, 10.0, np.zeros(PACKET_SAMPLES, np.int16))
        assert done.wait(1.0)
        assert time.monotonic() - started < 0.5
        thread.join()

    def test_wait_times_out_without_input(self):
        buffer = AVBuffer()
        started = time.monotonic()
        buffer.wait_for_input(0.05)
        assert 0.04 <= time.monotonic() - started < 0.5
