"""
background_removal.py
----------------------
Removes the background from an uploaded image, producing an RGBA image
where the background is transparent.

Two strategies are used:

1. AI-based removal via `rembg` (if the package and its model are
   available). This gives the best quality results and is tried first.

2. A classical computer-vision fallback using OpenCV's GrabCut algorithm.
   This requires no external model download and works fully offline, so
   the application still works even if `rembg`/`onnxruntime` are not
   installed or a model can't be downloaded (e.g. no internet access).

The public entry point is `remove_background()`, which tries method 1
and transparently falls back to method 2, reporting which method was
actually used so the UI can inform the user.
"""

from typing import Tuple, Optional

import numpy as np
import cv2
from PIL import Image

# rembg is an optional dependency. The app must keep working without it.
try:
    from rembg import remove as _rembg_remove, new_session as _rembg_new_session
    _REMBG_AVAILABLE = True
except Exception:
    _REMBG_AVAILABLE = False


class BackgroundRemovalError(Exception):
    """Raised when neither the AI method nor the fallback method could produce a result."""
    pass


def is_ai_removal_available() -> bool:
    """Whether the rembg package is importable in this environment."""
    return _REMBG_AVAILABLE


def _remove_background_ai(image: Image.Image, model_name: str = "u2netp") -> Image.Image:
    """
    AI-based background removal via rembg.
    `u2netp` is the smallest/fastest bundled model - a good default for a
    responsive desktop/laptop experience. Raises on any failure so the
    caller can fall back to the classical method.
    """
    session = _rembg_new_session(model_name)
    result = _rembg_remove(image.convert("RGB"), session=session)#Remove background using the AI model
    return result.convert("RGBA")


def _remove_background_grabcut(image: Image.Image, iterations: int = 5) -> Image.Image:
    """
    Classical fallback using OpenCV's GrabCut algorithm.

    GrabCut needs an initial rectangle that roughly contains the foreground
    subject. Since we don't have a subject detector here, we assume the
    subject is roughly centered (a very common case for portraits/product
    photos) and seed the rectangle accordingly. This is naturally less
    accurate than an AI model but requires zero external downloads.
    """
    rgb_image = image.convert("RGB")
    img_array = np.array(rgb_image)
    height, width = img_array.shape[:2]

    if height < 10 or width < 10:
        raise BackgroundRemovalError("Image is too small for background removal.")

    # Seed rectangle: a margin around the image, assuming the subject
    # occupies the central region (a reasonable default heuristic).
    margin_x = int(width * 0.08)
    margin_y = int(height * 0.05)
    rect = (margin_x, margin_y, width - 2 * margin_x, height - 2 * margin_y)

    mask = np.zeros((height, width), np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    bgr_image = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    cv2.grabCut(bgr_image, mask, rect, bgd_model, fgd_model, iterations, cv2.GC_INIT_WITH_RECT)

    # Pixels marked as probable/definite foreground become opaque.
    binary_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    # Smooth the mask edges slightly for a less jagged cutout.
    binary_mask = cv2.GaussianBlur(binary_mask, (5, 5), 0)

    rgba = np.dstack((img_array, binary_mask))
    return Image.fromarray(rgba, mode="RGBA")


def remove_background(image: Image.Image, prefer_ai: bool = True) -> Tuple[Optional[Image.Image], str, str]:
    """
    Main entry point for background removal.

    Returns a tuple: (result_image_or_None, method_used, message)
      - result_image_or_None: an RGBA PIL Image, or None if everything failed
      - method_used: "ai", "classical", or "none"
      - message: friendly status/error text for the UI
    """
    if image is None:
        return None, "none", "No image was provided."

    if prefer_ai and _REMBG_AVAILABLE:
        try:
            result = _remove_background_ai(image)
            return result, "ai", "Background removed successfully using the AI model (u2netp)."
        except Exception as exc:
            # Fall through to the classical method; don't crash the app.
            ai_error = str(exc)
        else:
            ai_error = None
    else:
        ai_error = "AI model not available in this environment." if prefer_ai else None

    try:
        result = _remove_background_grabcut(image)
        note = " (AI method unavailable, used a classical CV fallback instead — results may be less precise for complex scenes.)"
        return result, "classical", "Background removed using a classical computer-vision method." + note
    except Exception as exc:
        error_detail = f" Details: {ai_error}" if ai_error else ""
        return None, "none", (
            "Background removal failed for this image. It may be too complex, too small, "
            "or in an unsupported color mode." + error_detail
        )
