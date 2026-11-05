"""
chessboard.py
Generate a standard chessboard image to print for camera calibration.
Size: 9x6 inner corners (10x7 squares), 25mm per square.
"""

import logging
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def generate_chessboard(
    rows: int = 9,
    cols: int = 6,
    square_size_mm: int = 25,
    dpi: int = 300,
    output_path: str | Path = "chessboard.png",
) -> np.ndarray:
    """
    Generate a chessboard image for printing.
    Result: 1 PNG file ready to print.

    Args:
        rows: Number of inner corners vertically (9).
        cols: Number of inner corners horizontally (6).
        square_size_mm: Size of each square (mm).
        dpi: Print resolution (300 DPI is standard).
        output_path: Path to save the image file.

    Returns:
        np.ndarray: Chessboard image (with border) as a numpy array.
    """
    output_path = Path(output_path)

    # Calculate the number of squares in each dimension (e.g. 9x6 corners -> 10x7 squares)
    squares_x = cols + 1
    squares_y = rows + 1

    # Convert mm to pixels based on DPI (1 inch = 25.4 mm)
    pixel_per_square = int(square_size_mm * dpi / 25.4)
    img_width = squares_x * pixel_per_square
    img_height = squares_y * pixel_per_square

    # Create the base pattern image using numpy vectorization (high performance, clean)
    y, x = np.indices((squares_y, squares_x))
    grid = np.zeros((squares_y, squares_x), dtype=np.uint8)
    grid[(x + y) % 2 == 0] = 255

    # Scale up the pattern to the final pixel size
    chessboard = cv2.resize(
        grid, (img_width, img_height), interpolation=cv2.INTER_NEAREST
    )

    # Add a white border around for easy cutting/pasting when printing
    border = 50
    chessboard_with_border = cv2.copyMakeBorder(
        chessboard, border, border, border, border, cv2.BORDER_CONSTANT, value=255
    )

    # Save the file
    cv2.imwrite(str(output_path), chessboard_with_border)

    logger.info(f"[OK] Successfully generated chessboard: {output_path}")
    logger.info(f"   - Inner Corners: {cols}x{rows}")
    logger.info(f"   - Square size: {square_size_mm}mm")
    logger.info(f"   - Print resolution: {dpi} DPI")
    logger.info(f"   - Image size: {img_width}x{img_height} pixels")
    logger.info("\n[PRINTING INSTRUCTIONS]:")
    logger.info("   1. Open the file with an image viewer.")
    logger.info("   2. Print at 100% scale (Actual Size / Do not scale / Fit to page -> OFF).")
    logger.info("   3. Paste the printed paper onto a flat/hard cardboard, avoid wrinkles.")
    logger.info("   4. Measure a square with a ruler to ensure it is exactly 25mm.")

    return chessboard_with_border


if __name__ == "__main__":
    generate_chessboard()