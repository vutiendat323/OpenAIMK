"""
Face embedding extractor for ReID-assisted tracking.

Wraps an ONNX face-embedding model (mobilefacenet, ArcFace variant, etc.).
Follows the same patterns as SCRFDFaceDetector — ONNX Runtime session,
CUDA/CPU provider selection, batched inference.
"""

from typing import List, Tuple

import cv2
import numpy as np
import onnxruntime as ort


class FaceEmbedder:
    """Extract L2-normalized face embeddings for appearance-based tracking."""

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        input_size: Tuple[int, int] = (112, 112),
    ):
        """
        Args:
            model_path: Path to ONNX face embedding model.
            device: "cpu" or "cuda".
            input_size: Model input (width, height). Default (112, 112).

        Raises:
            FileNotFoundError: If model_path does not exist.
        """
        import os

        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"Face embedder model not found: {model_path}"
            )

        self._input_size = input_size  # (W, H)

        if device == "cuda":
            self._providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        else:
            self._providers = ["CPUExecutionProvider"]

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 2

        self._session = ort.InferenceSession(
            model_path,
            sess_options=opts,
            providers=self._providers,
        )
        self._input_name = self._session.get_inputs()[0].name
        self._output_name = self._session.get_outputs()[0].name

        # Validate we got the expected provider
        actual_provider = self._session.get_providers()[0]
        if device == "cuda" and "CUDA" not in actual_provider:
            import logging
            logging.getLogger(__name__).warning(
                "CUDA requested but not available for embedder, "
                "using %s", actual_provider
            )

    def warmup(self) -> None:
        """Run dummy inference to warm CUDA kernels and allocate memory."""
        target_w, target_h = self._input_size
        dummy = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        self.extract(dummy, [(0, 0, target_w, target_h)])

    def extract(
        self,
        frame_bgr: np.ndarray,
        bboxes: List[Tuple[float, float, float, float]],
    ) -> List[np.ndarray]:
        """
        Extract L2-normalized embeddings for each bbox.

        Args:
            frame_bgr: BGR image (H, W, 3), uint8.
            bboxes: List of (x1, y1, x2, y2) in pixel coordinates.

        Returns:
            List of 1-D numpy arrays, one per bbox (same order),
            L2-normalized so cosine similarity is a dot product.
            Returns empty list when bboxes is empty.
        """
        if len(bboxes) == 0:
            return []

        target_w, target_h = self._input_size
        h, w = frame_bgr.shape[:2]

        crops = []
        for x1, y1, x2, y2 in bboxes:
            # Clamp to frame bounds
            x1_c = max(0, int(x1))
            y1_c = max(0, int(y1))
            x2_c = min(w, int(x2))
            y2_c = min(h, int(y2))

            if x2_c <= x1_c or y2_c <= y1_c:
                # Degenerate bbox — use a 1-pixel fallback
                x1_c, y1_c = 0, 0
                x2_c, y2_c = max(1, w), max(1, h)

            crop = frame_bgr[y1_c:y2_c, x1_c:x2_c]
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            crop_resized = cv2.resize(
                crop_rgb, (target_w, target_h), interpolation=cv2.INTER_LINEAR
            )
            # Normalize to [-1, 1] (InsightFace convention)
            crop_f = crop_resized.astype(np.float32)
            crop_f = (crop_f - 127.5) / 128.0
            crops.append(crop_f)

        # Batch: (N, H, W, 3) → (N, 3, H, W)
        batch = np.stack(crops, axis=0)
        batch = np.transpose(batch, (0, 3, 1, 2))  # NHWC → NCHW

        # Inference
        outputs = self._session.run(
            [self._output_name],
            {self._input_name: batch},
        )
        embeddings = outputs[0]  # (N, D)

        # L2-normalize each embedding
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)  # avoid div-by-zero
        embeddings = embeddings / norms

        return [embeddings[i].copy() for i in range(len(bboxes))]
