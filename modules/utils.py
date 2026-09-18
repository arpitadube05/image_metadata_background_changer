"""
utils.py
--------
Small shared helper functions used across the application:
- human-friendly file size formatting
- safe wrappers that turn exceptions into friendly messages instead of crashes
- temporary file handling for uploaded images
- basic file validation

Keeping these here avoids duplicating "boilerplate" logic in every module.
"""

import io
import os
import tempfile
import functools
from typing import Callable, Any, Tuple

from PIL import Image, UnidentifiedImageError

# Formats we advertise support for in the UI.
SUPPORTED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP", "BMP", "TIFF", "GIF"}

# Anything above this (in megapixels) gets downsized for *processing* only.
# The original file is always kept untouched for the final export step.
MAX_PROCESSING_MEGAPIXELS = 12  # ~ e.g. 4000x3000


def human_readable_size(num_bytes: float) -> str:
    """Convert a byte count into a human-friendly string (KB/MB/GB)."""
    if num_bytes is None:
        return "Unknown"
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < step:
            return f"{num_bytes:.2f} {unit}" if unit != "B" else f"{int(num_bytes)} {unit}"
        num_bytes /= step
    return f"{num_bytes:.2f} PB"


def safe_call(default: Any = None):
    """
    Decorator that catches any exception raised inside the wrapped function
    and returns `default` instead, so a single missing metadata field or a
    corrupted image never crashes the whole app.

    Usage:
        @safe_call(default={})
        def extract_something(...):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                return default
        return wrapper
    return decorator


def validate_image_file(file_bytes: bytes) -> Tuple[bool, str]:
    """
    Confirm the uploaded bytes are actually a readable image before we do
    anything else with them.

    Returns (is_valid, message). message is empty on success, otherwise a
    user-friendly explanation of what went wrong.
    """
    if not file_bytes:
        return False, "The uploaded file is empty."

    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # cheap structural check
        return True, ""
    except UnidentifiedImageError:
        return False, "This file doesn't look like a supported image format."
    except Exception as exc:
        return False, f"The image appears to be corrupted or unreadable ({exc.__class__.__name__})."


def load_image_safely(file_bytes: bytes):
    """
    Re-open the image for actual use (Image.verify() leaves the file object
    unusable for further operations, so we open it fresh here).
    Returns (PIL.Image or None, error_message or "").
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.load()  # force full decode now, so later errors surface here
        return img, ""
    except Exception as exc:
        return None, f"Could not open this image: {exc.__class__.__name__}"


def save_to_temp_file(file_bytes: bytes, suffix: str = ".png") -> str:
    """
    Persist uploaded bytes to a temporary file on disk. Some libraries
    (EXIF readers, some CV routines) work more reliably from a file path
    than from an in-memory buffer.

    Returns the path to the temp file. Caller is responsible for cleanup
    via cleanup_temp_file().
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(file_bytes)
    tmp.flush()
    tmp.close()
    return tmp.name


def cleanup_temp_file(path: str) -> None:
    """Best-effort removal of a temp file. Never raises."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def downscale_for_processing(image: Image.Image, max_megapixels: float = MAX_PROCESSING_MEGAPIXELS):
    """
    If an image is very large, return a smaller copy for heavy processing
    (background removal, histograms, etc.) so the app stays responsive on
    normal laptop hardware. The original, full-resolution image is left
    untouched and should be used for the final export.

    Returns (processing_image, was_downscaled: bool, scale_factor: float)
    """
    width, height = image.size
    megapixels = (width * height) / 1_000_000

    if megapixels <= max_megapixels:
        return image, False, 1.0

    scale_factor = (max_megapixels / megapixels) ** 0.5
    new_size = (max(1, int(width * scale_factor)), max(1, int(height * scale_factor)))
    resized = image.resize(new_size, Image.LANCZOS)
    return resized, True, scale_factor


def get_mime_type(fmt: str) -> str:
    """Map a PIL format string to a MIME type for display purposes."""
    mapping = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "BMP": "image/bmp",
        "TIFF": "image/tiff",
        "GIF": "image/gif",
    }
    return mapping.get(fmt.upper() if fmt else "", "application/octet-stream")
