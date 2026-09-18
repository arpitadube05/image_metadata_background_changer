"""
generate_backgrounds.py
------------------------
One-time setup script that procedurally generates the built-in
"predefined background" images used by the app, so the project works
completely offline (no stock-photo downloads required).

Run once with:
    python generate_backgrounds.py

This creates several stylized .jpg backgrounds inside backgrounds/.
Feel free to replace any of these with your own real photos later —
the app just looks for files in the backgrounds/ folder.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "backgrounds")
SIZE = (1600, 1000)


def _gradient(size, top_color, bottom_color):
    w, h = size
    top = np.array(top_color, dtype=np.float32)
    bottom = np.array(bottom_color, dtype=np.float32)
    t = np.linspace(0, 1, h).reshape(h, 1, 1)
    grad = top.reshape(1, 1, 3) * (1 - t) + bottom.reshape(1, 1, 3) * t
    grad = np.repeat(grad, w, axis=1)
    return Image.fromarray(np.clip(grad, 0, 255).astype(np.uint8), mode="RGB")


def make_studio():
    img = _gradient(SIZE, (235, 235, 238), (170, 170, 178))
    draw = ImageDraw.Draw(img)
    w, h = SIZE
    # Soft studio "floor line"
    draw.rectangle([0, int(h * 0.72), w, h], fill=(190, 190, 196))
    img = img.filter(ImageFilter.GaussianBlur(radius=6))
    return img


def make_office():
    img = _gradient(SIZE, (223, 231, 235), (150, 168, 176))
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = SIZE
    # Simple window mullions to suggest an office setting
    for x in range(0, w, 220):
        draw.rectangle([x, 0, x + 6, int(h * 0.65)], fill=(255, 255, 255, 60))
    draw.rectangle([0, int(h * 0.65), w, h], fill=(120, 110, 100, 255))
    img = img.filter(ImageFilter.GaussianBlur(radius=3))
    return img


def make_nature():
    img = _gradient(SIZE, (150, 205, 235), (170, 220, 150))
    draw = ImageDraw.Draw(img)
    w, h = SIZE
    draw.rectangle([0, int(h * 0.6), w, h], fill=(90, 160, 90))
    img = img.filter(ImageFilter.GaussianBlur(radius=8))
    return img


def make_beach():
    img = _gradient(SIZE, (150, 210, 235), (245, 225, 180))
    draw = ImageDraw.Draw(img)
    w, h = SIZE
    draw.rectangle([0, int(h * 0.55), w, h], fill=(235, 210, 160))
    img = img.filter(ImageFilter.GaussianBlur(radius=10))
    return img


def make_mountain():
    img = _gradient(SIZE, (200, 220, 235), (120, 130, 150))
    draw = ImageDraw.Draw(img)
    w, h = SIZE
    draw.polygon([(0, h * 0.75), (w * 0.3, h * 0.4), (w * 0.55, h * 0.7), (w, h * 0.5), (w, h), (0, h)],
                 fill=(90, 100, 120))
    img = img.filter(ImageFilter.GaussianBlur(radius=5))
    return img


def make_city():
    img = _gradient(SIZE, (60, 70, 100), (200, 150, 130))
    draw = ImageDraw.Draw(img)
    w, h = SIZE
    rng = np.random.default_rng(42)
    x = 0
    while x < w:
        bw = int(rng.uniform(60, 140))
        bh = int(rng.uniform(h * 0.25, h * 0.6))
        draw.rectangle([x, h - bh, x + bw, h], fill=(35, 35, 50))
        x += bw + 10
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    return img


def make_classroom():
    img = _gradient(SIZE, (230, 225, 210), (190, 180, 160))
    draw = ImageDraw.Draw(img)
    w, h = SIZE
    draw.rectangle([int(w * 0.1), int(h * 0.15), int(w * 0.6), int(h * 0.55)], fill=(60, 90, 70))
    img = img.filter(ImageFilter.GaussianBlur(radius=6))
    return img


def make_corporate():
    img = _gradient(SIZE, (210, 215, 225), (110, 125, 145))
    img = img.filter(ImageFilter.GaussianBlur(radius=4))
    return img


def make_gradient_sample():
    return _gradient(SIZE, (90, 110, 230), (200, 90, 190))


def make_abstract():
    rng = np.random.default_rng(7)
    base = _gradient(SIZE, (30, 30, 40), (90, 40, 110))
    draw = ImageDraw.Draw(base, "RGBA")
    w, h = SIZE
    for _ in range(18):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(60, 220)
        color = tuple(int(c) for c in rng.uniform(60, 255, size=3)) + (70,)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    return base.filter(ImageFilter.GaussianBlur(radius=25))


BACKGROUNDS = {
    "studio.jpg": make_studio,
    "office.jpg": make_office,
    "nature.jpg": make_nature,
    "beach.jpg": make_beach,
    "mountain.jpg": make_mountain,
    "city.jpg": make_city,
    "classroom.jpg": make_classroom,
    "corporate.jpg": make_corporate,
    "gradient.jpg": make_gradient_sample,
    "abstract.jpg": make_abstract,
}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for filename, builder in BACKGROUNDS.items():
        img = builder()
        path = os.path.join(OUTPUT_DIR, filename)
        img.save(path, format="JPEG", quality=90)
        print(f"Created {path}")


if __name__ == "__main__":
    main()
