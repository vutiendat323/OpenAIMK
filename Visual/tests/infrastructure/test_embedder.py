"""Unit tests for FaceEmbedder — ONNX face embedding wrapper."""

import numpy as np
import pytest


class TestFaceEmbedder:
    """Tests for FaceEmbedder. These use a real model when available,
    and verify the interface contract even without one."""

    def test_import_succeeds(self):
        from Visual.infrastructure.faces.embedder import FaceEmbedder
        assert FaceEmbedder is not None

    def test_init_raises_file_not_found_for_missing_model(self):
        from Visual.infrastructure.faces.embedder import FaceEmbedder
        with pytest.raises(FileNotFoundError, match="(?i)face embedder"):
            FaceEmbedder(model_path="/nonexistent/model.onnx", device="cpu")

    def test_init_succeeds_with_valid_model(self):
        """Skip if no model available — tests the constructor contract."""
        import os
        from Visual.infrastructure.faces.embedder import FaceEmbedder
        model_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "models", "face_embedder.onnx"
        )
        if not os.path.isfile(model_path):
            pytest.skip("No embedder model available")
        embedder = FaceEmbedder(model_path, device="cpu")
        assert embedder._session is not None
