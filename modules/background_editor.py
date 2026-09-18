"""
background_editor.py
---------------------
Everything needed to build a *new* background and composite the
extracted (transparent) foreground onto it:

- solid color backgrounds
- gradient backgrounds (built-in presets + custom two-color gradients)
- blurred version of the original background
- compositing foreground + background, with resize/position/rotation/opacity
- loading predefined (built-in) background images from disk
"""

from typing import Tuple, Optional

import numpy as np
from PIL import Image, ImageFilter

# Named color presets offered in the UI's quick-pick swatches.
SOLID_COLOR_PRESETS = {
    "White": (255, 255, 255),
    "Black": (0, 0, 0),
    "Red": (220, 40, 40),
    "Blue": (40, 90, 220),
    "Green": (40, 170, 90),
    "Yellow": (240, 210, 40),
    "Gray": (128, 128, 128),
}

# Named gradient presets: (top-left color, bottom-right color)
GRADIENT_PRESETS = {
    "Blue → Purple": ((60, 90, 220), (150, 60, 200)),
    "Pink → Orange": ((240, 110, 170), (250, 170, 60)),
    "Green → Blue": ((50, 190, 130), (50, 130, 220)),
    "Black → Gray": ((20, 20, 20), (140, 140, 140)),
}


def create_solid_background(size: Tuple[int, int], color: Tuple[int, int, int]) -> Image.Image:
    """Create a flat solid-color background of the given size."""
    return Image.new("RGB", size, color)


def create_gradient_background(
    size: Tuple[int, int],
    color_start: Tuple[int, int, int],
    color_end: Tuple[int, int, int],
    direction: str = "diagonal",
) -> Image.Image:
    """
    Create a smooth linear gradient background between two colors.
    direction: "horizontal", "vertical", or "diagonal".
    """
    width, height = size
    color_start = np.array(color_start, dtype=np.float32)
    color_end = np.array(color_end, dtype=np.float32)

    if direction == "horizontal":
        t = np.linspace(0, 1, width).reshape(1, width, 1)
        t = np.repeat(t, height, axis=0)
    elif direction == "vertical":
        t = np.linspace(0, 1, height).reshape(height, 1, 1)
        t = np.repeat(t, width, axis=1)
    else:  # diagonal
        x = np.linspace(0, 1, width).reshape(1, width)
        y = np.linspace(0, 1, height).reshape(height, 1)
        t = ((x + y) / 2)
        t = t.reshape(height, width, 1)

    gradient = color_start.reshape(1, 1, 3) * (1 - t) + color_end.reshape(1, 1, 3) * t
    gradient = np.clip(gradient, 0, 255).astype(np.uint8)
    return Image.fromarray(gradient, mode="RGB")


def blur_background(original_image: Image.Image, blur_radius: int = 20) -> Image.Image:
    """
    Blur the ORIGINAL image (before background removal) so it can be used
    as its own softly-blurred backdrop behind the extracted foreground.
    """ 
    rgb_image = original_image.convert("RGB")
    return rgb_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))


def load_predefined_background(path: str, target_size: Tuple[int, int]) -> Image.Image:
    """Load a built-in background image from disk and resize/crop it to fit target_size."""
    bg = Image.open(path).convert("RGB")
    return _resize_and_crop_to_fill(bg, target_size)


def _resize_and_crop_to_fill(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """Scale an image up/down and center-crop so it exactly fills target_size (like CSS 'cover')."""
    target_w, target_h = target_size
    src_w, src_h = image.size

    if src_w == 0 or src_h == 0:
        return Image.new("RGB", target_size, (200, 200, 200))

    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale) + 1, int(src_h * scale) + 1
    resized = image.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def resize_foreground(foreground: Image.Image, scale_percent: float) -> Image.Image:
    """
    Resize the (transparent) foreground image by a percentage of its
    original size (100 = unchanged). Keeps aspect ratio.
    """
    scale_percent = max(1, min(scale_percent, 400))  # sane bounds
    width, height = foreground.size
    new_size = (max(1, int(width * scale_percent / 100)), max(1, int(height * scale_percent / 100)))
    return foreground.resize(new_size, Image.LANCZOS)


def rotate_foreground(foreground: Image.Image, degrees: float) -> Image.Image:
    """Rotate the foreground around its center, expanding the canvas so nothing is clipped."""
    return foreground.rotate(degrees, expand=True, resample=Image.BICUBIC)


def apply_opacity(foreground: Image.Image, opacity_percent: float) -> Image.Image:
    """Scale the alpha channel of an RGBA image by opacity_percent (0-100)."""
    opacity_percent = max(0, min(opacity_percent, 100))
    foreground = foreground.convert("RGBA")
    r, g, b, a = foreground.split()
    a = a.point(lambda px: int(px * (opacity_percent / 100)))
    return Image.merge("RGBA", (r, g, b, a))


def combine_foreground_background(
    foreground: Image.Image,
    background: Image.Image,
    x_offset_percent: float = 50.0,
    y_offset_percent: float = 50.0,
) -> Image.Image:
    """
    Composite the (RGBA) foreground onto the (RGB) background canvas.

    x_offset_percent / y_offset_percent (0-100) position the CENTER of the
    foreground within the background canvas: 50/50 is dead-center.
    """
    background = background.convert("RGBA")
    foreground = foreground.convert("RGBA")

    bg_w, bg_h = background.size
    fg_w, fg_h = foreground.size

    center_x = int(bg_w * (x_offset_percent / 100))
    center_y = int(bg_h * (y_offset_percent / 100))

    paste_x = center_x - fg_w // 2
    paste_y = center_y - fg_h // 2

    canvas = background.copy()
    canvas.alpha_composite(foreground, dest=(paste_x, paste_y))
    return canvas.convert("RGB")


def build_background_for_option(
    option: str,
    canvas_size: Tuple[int, int],
    original_image: Optional[Image.Image] = None,
    solid_color: Optional[Tuple[int, int, int]] = None,
    gradient_preset: Optional[str] = None,
    custom_gradient: Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = None,
    uploaded_background: Optional[Image.Image] = None,
    predefined_path: Optional[str] = None,
    blur_radius: int = 20,
) -> Optional[Image.Image]:
    """
    Single dispatch function the UI calls to build the chosen background
    type, keeping app.py free of branching logic.

    Returns None for "Transparent" (caller should skip compositing and
    just show the foreground as-is).
    """
    if option == "Transparent":
        return None

    if option == "Solid Color":
        color = solid_color or SOLID_COLOR_PRESETS["White"]
        return create_solid_background(canvas_size, color)

    if option == "Gradient":
        if custom_gradient:
            start, end = custom_gradient
        else:
            start, end = GRADIENT_PRESETS.get(gradient_preset, GRADIENT_PRESETS["Blue → Purple"])
        return create_gradient_background(canvas_size, start, end)

    if option == "Blur":
        if original_image is None:
            return create_solid_background(canvas_size, (200, 200, 200))
        blurred = blur_background(original_image, blur_radius)
        return _resize_and_crop_to_fill(blurred, canvas_size)

    if option == "Upload Background":
        if uploaded_background is None:
            return create_solid_background(canvas_size, (200, 200, 200))
        return _resize_and_crop_to_fill(uploaded_background.convert("RGB"), canvas_size)

    if option == "Predefined":
        if predefined_path is None:
            return create_solid_background(canvas_size, (200, 200, 200))
        return load_predefined_background(predefined_path, canvas_size)

    # Unknown option -> safe default
    return create_solid_background(canvas_size, (255, 255, 255))
