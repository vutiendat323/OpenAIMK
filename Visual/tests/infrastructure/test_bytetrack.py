"""Unit tests for ByteTrack tracker and STrack embedding gallery."""

import numpy as np
import pytest
from Visual.infrastructure.faces.bytetrack import STrack, ByteTrack


class TestSTrackGallery:
    """Tests for STrack embedding gallery."""

    def test_gallery_centroid_empty_returns_none(self):
        track = STrack(np.array([10.0, 10.0, 50.0, 50.0]), 0.9)
        assert track.gallery_centroid is None

    def test_add_embedding_and_centroid(self):
        track = STrack(np.array([10.0, 10.0, 50.0, 50.0]), 0.9)
        emb = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        emb = emb / np.linalg.norm(emb)  # L2-normalized
        track.add_embedding(emb)
        centroid = track.gallery_centroid
        assert centroid is not None
        # Single embedding → centroid == embedding
        np.testing.assert_array_almost_equal(centroid, emb)

    def test_gallery_evicts_oldest(self):
        track = STrack(np.array([10.0, 10.0, 50.0, 50.0]), 0.9)
        track._max_gallery = 3

        e1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        e2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        e3 = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        e4 = np.array([0.5, 0.5, 0.0], dtype=np.float32)
        e4 = e4 / np.linalg.norm(e4)

        track.add_embedding(e1)
        track.add_embedding(e2)
        track.add_embedding(e3)
        track.add_embedding(e4)  # should evict e1

        assert len(track._embeddings) == 3
        # e1 should be gone, e2, e3, e4 remain
        assert not any(np.allclose(emb, e1) for emb in track._embeddings)

    def test_centroid_is_l2_normalized(self):
        track = STrack(np.array([10.0, 10.0, 50.0, 50.0]), 0.9)
        e1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        e2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        track.add_embedding(e1)
        track.add_embedding(e2)
        centroid = track.gallery_centroid
        assert centroid is not None
        norm = float(np.linalg.norm(centroid))
        assert abs(norm - 1.0) < 1e-5

    def test_centroid_mean_of_two(self):
        track = STrack(np.array([10.0, 10.0, 50.0, 50.0]), 0.9)
        e1 = np.array([1.0, 0.0], dtype=np.float32)
        e2 = np.array([0.0, 1.0], dtype=np.float32)
        track.add_embedding(e1)
        track.add_embedding(e2)
        centroid = track.gallery_centroid
        assert centroid is not None
        # Mean of [1,0] and [0,1] = [0.5, 0.5], L2-normalized = [0.707, 0.707]
        expected = np.array([0.70710678, 0.70710678], dtype=np.float32)
        np.testing.assert_array_almost_equal(np.abs(centroid), np.abs(expected), decimal=5)


class TestByteTrackWithEmbeddings:
    """Integration tests for ByteTrack with appearance embeddings."""

    @pytest.fixture
    def tracker(self):
        """Create a tracker with low init threshold so tests can easily
        create tracks."""
        bt = ByteTrack(
            track_buffer=30,
            track_thresh=0.5,
            match_thresh=0.3,
            match_thresh_second=0.3,
            track_init_thresh=0.5,
        )
        yield bt
        bt.reset()

    def test_update_without_embeddings_is_backward_compatible(self, tracker):
        """Calling update() without embeddings should work identically to before."""
        dets = [(10.0, 10.0, 50.0, 50.0, 0.9)]
        result = tracker.update(dets, embeddings=None)
        assert len(result) == 1
        assert result[0][4] >= 1  # some track ID

    def test_embeddings_none_vs_empty_list_same_behavior(self, tracker):
        """None and [] embeddings should both result in IoU-only matching."""
        dets = [(10.0, 10.0, 50.0, 50.0, 0.9)]
        r1 = tracker.update(dets, embeddings=None)
        tracker.reset()
        r2 = tracker.update(dets, embeddings=[])
        # Both should create one track
        assert len(r1) == 1
        assert len(r2) == 1

    def test_same_appearance_keeps_id_across_non_overlapping_frames(self, tracker):
        """Fast motion: bboxes don't overlap but embeddings match → same ID."""
        # Frame 1: bbox on the left
        dets_frame1 = [(10.0, 10.0, 50.0, 50.0, 0.9)]
        emb1 = np.array([1.0, 0.0], dtype=np.float32)
        emb1 = emb1 / np.linalg.norm(emb1)
        r1 = tracker.update(dets_frame1, embeddings=[emb1])
        id1 = r1[0][4]

        # Frame 2: bbox on the far right — zero IoU with frame 1
        dets_frame2 = [(200.0, 10.0, 240.0, 50.0, 0.9)]
        emb2 = np.array([1.0, 0.0], dtype=np.float32)  # same embedding
        emb2 = emb2 / np.linalg.norm(emb2)
        r2 = tracker.update(dets_frame2, embeddings=[emb2])
        id2 = r2[0][4]

        assert id1 == id2, (
            f"ID changed from {id1} to {id2} despite same appearance"
        )

    def test_different_appearance_creates_new_id(self):
        """Overlapping bboxes but different appearance → different IDs."""
        tracker = ByteTrack(
            track_buffer=30, track_thresh=0.5,
            match_thresh=0.3, match_thresh_second=0.3,
            track_init_thresh=0.5,
        )

        # Frame 1
        r1 = tracker.update(
            [(10.0, 10.0, 50.0, 50.0, 0.9)],
            embeddings=[np.array([1.0, 0.0], dtype=np.float32)],
        )
        id1 = r1[0][4]

        # Frame 2: same location but different embedding
        r2 = tracker.update(
            [(10.0, 10.0, 50.0, 50.0, 0.9)],
            embeddings=[np.array([-1.0, 0.0], dtype=np.float32)],
        )
        r2_ids = {r[4] for r in r2}

        # The old track should still be active (not pruned yet)
        assert id1 in r2_ids, (
            f"Old track {id1} should still be active, got IDs: {r2_ids}"
        )
        # A new track should have been created with a different ID
        assert any(i != id1 for i in r2_ids), (
            f"Expected a new ID different from {id1}, got IDs: {r2_ids}"
        )

    def test_fast_motion_sequence_stable_id(self, tracker):
        """10-frame sequence: person moves across frame, no overlap between
        consecutive frames with same appearance → stable single ID."""
        emb = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        emb = emb / np.linalg.norm(emb)

        ids = set()
        for i in range(10):
            # Bbox jumps 100px right each frame — zero overlap
            x = 10.0 + i * 100.0
            dets = [(x, 10.0, x + 40.0, 50.0, 0.9)]
            result = tracker.update(dets, embeddings=[emb.copy()])
            for r in result:
                ids.add(r[4])

        # Without embeddings this would create 10 different IDs.
        # With embeddings, should be 1 (maybe 2 at most if threshold edge cases)
        assert len(ids) <= 2, (
            f"Expected ≤2 IDs across 10 frames, got {len(ids)}: {ids}"
        )

    def test_empty_gallery_falls_back_to_iou(self, tracker):
        """New track has empty gallery → first match uses IoU only."""
        # Frame 1: create track
        emb1 = np.array([1.0, 0.0], dtype=np.float32)
        emb1 = emb1 / np.linalg.norm(emb1)
        r1 = tracker.update(
            [(10.0, 10.0, 50.0, 50.0, 0.9)],
            embeddings=[emb1],
        )
        assert len(r1) == 1
        # Frame 2: overlapping, different appearance
        # The track now has 1 embedding (from frame 1), so it should match
        emb2 = np.array([0.0, 1.0], dtype=np.float32)
        emb2 = emb2 / np.linalg.norm(emb2)
        r2 = tracker.update(
            [(12.0, 12.0, 52.0, 52.0, 0.9)],  # high IoU, different emb
            embeddings=[emb2],
        )
        assert len(r2) == 1


class TestBackwardCompatibility:
    """Ensure existing IoU-only behavior is preserved."""

    def test_default_constructor_works_without_embeddings(self):
        """Original construction pattern still works."""
        tracker = ByteTrack(
            track_buffer=30,
            track_thresh=0.5,
            match_thresh=0.3,
            match_thresh_second=0.5,
            track_init_thresh=0.7,
        )
        # Simulate a few frames of normal tracking
        for i in range(5):
            dets = [(float(10 + i * 2), 10.0, float(50 + i * 2), 50.0, 0.9)]
            result = tracker.update(dets)  # no embeddings arg
            assert len(result) == 1
            assert result[0][4] >= 1
        tracker.reset()

    def test_old_constructor_args_still_work(self):
        """Passing only the original 5 positional args should work."""
        tracker = ByteTrack(30, 0.5, 0.3, 0.5, 0.7)
        result = tracker.update([(10.0, 10.0, 50.0, 50.0, 0.9)])
        assert len(result) == 1
        tracker.reset()
