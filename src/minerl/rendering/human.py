from __future__ import annotations

import numpy as np


def show_rgb(frame: np.ndarray) -> None:
    """Show an RGB frame if OpenCV is installed."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Install minerl-modern[render] to use human rendering") from exc

    cv2.imshow("MineRL Render", frame[:, :, ::-1])
    cv2.waitKey(1)
