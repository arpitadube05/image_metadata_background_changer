"""
image_export.py
----------------
Final export/download logic:
- optionally strip EXIF/metadata before saving
- export to PNG (with transparency), JPEG (flattened onto a chosen
  background color), or WEBP (with optional transparency and quality)
"""

import io
from typing import Tuple

from PIL import Image


def remove_metadata(image: Image.Image) -> Image.Image:
    """
    Return a copy of the image with all EXIF/metadata stripped.
    This is done by rebuilding a fresh image from the pixel data only,
    which naturally drops any embedded EXIF/ICC/XMP blocks.
    """
    data = list(image.getdata())
    clean_image = Image.new(image.mode, image.size)
    clean_image.putdata(data)
    return clean_image


def _flatten_transparency(image: Image.Image, background_color: Tuple[int, int, int]) -> Image.Image:
    """Flatten an RGBA image onto a solid background color, producing RGB output."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        flattened = Image.new("RGB", rgba.size, background_color)
        flattened.paste(rgba, mask=rgba.split()[-1])
        return flattened
    return image.convert("RGB")


def export_png(image: Image.Image, strip_metadata: bool = False) -> bytes:
    """Export as PNG, preserving transparency if present."""
    if strip_metadata:
        image = remove_metadata(image)
    buffer = io.BytesIO()
    # PNG mode must be one PIL supports for saving; RGBA/RGB/L/P are all fine.
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def export_jpeg(
    image: Image.Image,
    quality: int = 90,
    strip_metadata: bool = False,
    background_color: Tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    """
    Export as JPEG. JPEG has no alpha channel, so any transparent areas
    are flattened onto `background_color` first.
    """
    flattened = _flatten_transparency(image, background_color)
    if strip_metadata:
        flattened = remove_metadata(flattened)
    buffer = io.BytesIO()
    quality = max(1, min(int(quality), 100))
    flattened.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def export_webp(
    image: Image.Image,
    quality: int = 90,
    strip_metadata: bool = False,
    preserve_transparency: bool = True,
    background_color: Tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    """Export as WEBP. Supports transparency; can optionally flatten it instead."""
    if preserve_transparency and image.mode in ("RGBA", "LA"):
        export_image = image
    else:
        export_image = _flatten_transparency(image, background_color)

    if strip_metadata:
        export_image = remove_metadata(export_image)

    buffer = io.BytesIO()
    quality = max(1, min(int(quality), 100))
    export_image.save(buffer, format="WEBP", quality=quality)
    return buffer.getvalue()


def get_export_bytes(
    image: Image.Image,
    output_format: str,
    quality: int = 90,
    strip_metadata: bool = False,
    background_color: Tuple[int, int, int] = (255, 255, 255),
) -> Tuple[bytes, str, str]:
    """
    Single dispatch function for the UI's export step.
    Returns (file_bytes, mime_type, suggested_filename_extension).
    """
    output_format = output_format.upper()
    if output_format == "PNG":
        return export_png(image, strip_metadata), "image/png", "png"
    elif output_format in ("JPEG", "JPG"):
        return export_jpeg(image, quality, strip_metadata, background_color), "image/jpeg", "jpg"
    elif output_format == "WEBP":
        return export_webp(image, quality, strip_metadata, True, background_color), "image/webp", "webp"
    else:
        raise ValueError(f"Unsupported export format: {output_format}")
