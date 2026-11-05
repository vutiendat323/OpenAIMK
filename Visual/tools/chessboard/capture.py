"""
Capture chessboard images for camera calibration.

Usage:
    python3 tools/chessboard/capture.py

Controls:
    SPACE   - Save current frame
    ESC/q   - Quit

Images are saved to tools/chessboard/captures/ as frame_0000.jpg, frame_0001.jpg, ...
"""

import logging
import sys
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class ChessboardCapturer:
    """Tool for capturing chessboard images for calibration."""

    def __init__(self, camera_id: int = 0, width: int = 640, height: int = 480):
        self.camera_id = camera_id
        self.width = width
        self.height = height

        # Save directory relative to this file
        self.save_dir = Path(__file__).parent / "captures"
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.count = 0
        self.cap = None

    def run(self) -> None:
        """Run the capture loop."""
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            logger.error("ERROR: Cannot open camera")
            sys.exit(1)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        self._print_instructions()

        try:
            self._capture_loop()
        finally:
            self._cleanup()

    def _print_instructions(self) -> None:
        """Print usage instructions to the console."""
        logger.info("=== Chessboard Capture Tool ===")
        logger.info("  SPACE - Save current frame")
        logger.info("  ESC/q - Quit")
        logger.info(f"  Save dir: {self.save_dir}")
        logger.info("===============================\n")

    def _capture_loop(self) -> None:
        """Main loop for reading and displaying frames."""
        while True:
            ret, frame = self.cap.read()
            if not ret:
                logger.error("ERROR: Failed to read frame")
                break

            # Create a copy for displaying text so we don't save text onto the calibration image
            display_frame = frame.copy()
            cv2.putText(
                display_frame,
                f"Saved: {self.count}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )
            cv2.imshow("Chessboard Capture", display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                self._save_frame(frame)
            elif key in (ord("q"), 27):
                break

    def _save_frame(self, frame: np.ndarray) -> None:
        """Save the current frame to disk."""
        fname = self.save_dir / f"frame_{self.count:04d}.jpg"
        cv2.imwrite(str(fname), frame)
        logger.info(f"  Saved: {fname}")
        self.count += 1

    def _cleanup(self) -> None:
        """Release resources."""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        logger.info(f"\nDone. {self.count} images saved to {self.save_dir}")


def main() -> None:
    """Entry point."""
    capturer = ChessboardCapturer()
    capturer.run()


if __name__ == "__main__":
    main()
