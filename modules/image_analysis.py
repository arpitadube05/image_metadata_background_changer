"""
image_analysis.py
------------------
Technical / visual analysis of the image itself (as opposed to metadata.py,
which reads information *about* the file): brightness, average color,
dominant colors, resolution stats, and RGB histograms.
"""

from typing import Dict, Any, List, Tuple

import numpy as np
from PIL import Image

from .utils import safe_call


@safe_call(default={})
def calculate_dimensions(image: Image.Image) -> Dict[str, Any]:
    width, height = image.size
    megapixels = round((width * height) / 1_000_000, 2)
    return {
        "Width (px)": width,
        "Height (px)": height,
        "Megapixels": f"{megapixels} MP",
        "Total Pixels": width * height,
    }


@safe_call(default="N/A")
def calculate_aspect_ratio(image: Image.Image) -> str:
    width, height = image.size
    if height == 0:
        return "N/A"

    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a

    g = gcd(width, height)
    if g == 0:
        return f"{width}:{height}"
    return f"{width // g}:{height // g}"


@safe_call(default={"R": 0, "G": 0, "B": 0})
def calculate_average_color(image: Image.Image) -> Dict[str, int]:
    """Average R, G, B value across the whole image."""
    rgb_image = image.convert("RGB")
    arr = np.asarray(rgb_image).reshape(-1, 3)
    avg = arr.mean(axis=0)
    return {"R": int(avg[0]), "G": int(avg[1]), "B": int(avg[2])}


@safe_call(default=0.0)
def calculate_brightness(image: Image.Image) -> float:
    """
    Perceived brightness (0-255 scale) using the standard luminance
    formula: 0.299R + 0.587G + 0.114B, averaged over all pixels.
    """
    rgb_image = image.convert("RGB")
    arr = np.asarray(rgb_image).astype(np.float32)
    luminance = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    return round(float(luminance.mean()), 2)


def brightness_label(brightness: float) -> str:
    """Turn a raw brightness number into a friendly label for the UI."""
    if brightness < 60:
        return "Very Dark"
    elif brightness < 110:
        return "Dark"
    elif brightness < 170:
        return "Medium"
    elif brightness < 220:
        return "Bright"
    return "Very Bright"


@safe_call(default=[])
def get_dominant_colors(image: Image.Image, num_colors: int = 5) -> List[Tuple[Tuple[int, int, int], float]]:
    """
    Find the most common colors in the image using simple color quantization
    (via PIL's built-in palette reduction, which is fast and dependency-free).

    Returns a list of ((R, G, B), percentage) tuples, sorted by dominance.
    """
    rgb_image = image.convert("RGB")

    # Downscale for speed - color distribution doesn't need full resolution.
    thumb = rgb_image.copy()
    thumb.thumbnail((150, 150))

    # Quantize to a limited palette, then count pixel frequency per palette color.
    quantized = thumb.quantize(colors=max(num_colors, 8), method=Image.MEDIANCUT)
    palette = quantized.getpalette()
    color_counts = quantized.getcolors()  # list of (count, palette_index)

    if not color_counts:
        return []

    color_counts.sort(reverse=True, key=lambda x: x[0])
    total_pixels = sum(c for c, _ in color_counts)

    results = []
    for count, idx in color_counts[:num_colors]:
        r = palette[idx * 3]
        g = palette[idx * 3 + 1]
        b = palette[idx * 3 + 2]
        percentage = round((count / total_pixels) * 100, 1)
        results.append(((r, g, b), percentage))

    return results


@safe_call(default={"R": [], "G": [], "B": []})
def calculate_histogram(image: Image.Image) -> Dict[str, List[int]]:
    """
    Compute the RGB histogram (256 bins per channel). The UI layer can plot
    this directly with matplotlib or Streamlit's native chart widgets.
    """
    rgb_image = image.convert("RGB")
    histogram = rgb_image.histogram()  # 768 values: R(256) + G(256) + B(256)
    return {
        "R": histogram[0:256],
        "G": histogram[256:512],
        "B": histogram[512:768],
    }


@safe_call(default="Unknown")
def estimate_quality_label(image: Image.Image, file_size_bytes: int) -> str:
    """
    Rough, heuristic-only "quality" estimate based on bytes-per-pixel.
    This is NOT a rigorous quality metric — just a friendly indicator,
    clearly framed as an estimate in the UI.
    """
    width, height = image.size
    pixels = max(width * height, 1)
    bytes_per_pixel = file_size_bytes / pixels

    if bytes_per_pixel > 3:
        return "High (large file relative to resolution — likely lossless or high quality)"
    elif bytes_per_pixel > 1:
        return "Medium (typical compressed photo quality)"
    elif bytes_per_pixel > 0.2:
        return "Compressed (noticeable compression likely)"
    return "Heavily Compressed (small file relative to resolution)"


def get_full_analysis(image: Image.Image, file_size_bytes: int) -> Dict[str, Any]:
    """Convenience aggregator used by the UI layer."""
    brightness = calculate_brightness(image)
    return {
        "dimensions": calculate_dimensions(image),
        "aspect_ratio": calculate_aspect_ratio(image),
        "average_color": calculate_average_color(image),
        "brightness": brightness,
        "brightness_label": brightness_label(brightness),
        "dominant_colors": get_dominant_colors(image),
        "histogram": calculate_histogram(image),
        "quality_estimate": estimate_quality_label(image, file_size_bytes),
    }
