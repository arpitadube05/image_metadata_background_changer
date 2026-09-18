# 🖼️ Image Metadata Analyzer & Background Changer

A Python desktop-style web application (built with Streamlit) that lets you
upload an image, inspect everything about it — file properties, EXIF, GPS,
hashes, brightness, dominant colors — and then remove and replace its
background using several different styles, before exporting the result.

Built as a portfolio-quality project: modular code, defensive error
handling, and a clean step-by-step UI.

---

## 1. Project Overview

The app walks the user through a linear 7-step workflow:

1. **Upload** an image and see its basic properties.
2. **Analyze Metadata** — file info, EXIF, GPS, and file hashes.
3. **Remove Background** — AI-based (via `rembg`) with an automatic
   classical computer-vision fallback (OpenCV GrabCut) if the AI model
   isn't available.
4. **Choose a New Background** — transparent, solid color, gradient,
   blurred original, an uploaded image, or a built-in preset.
5. **Edit** — resize, reposition, rotate, and adjust opacity of the
   extracted subject.
6. **Preview** the original vs. the edited result side by side.
7. **Export** — choose PNG / JPEG / WEBP, a quality level, and whether to
   keep or strip metadata, then download.

Everything runs **locally** — no image is ever uploaded to an external
server unless you explicitly use the optional AI background-removal model
(which only downloads its *model weights* once, not your images).

---

## 2. Features

- Full metadata extraction: filename, format, dimensions, color mode,
  channels, bits-per-pixel, EXIF (camera, lens, exposure, ISO, aperture,
  flash, white balance, orientation, software, copyright), GPS
  (lat/long/altitude/timestamp, converted to decimal degrees), and MD5 /
  SHA-256 file hashes.
- Clear privacy warning whenever GPS location data is detected.
- Image analysis: brightness, average color, dominant color palette, and
  an RGB histogram.
- Background removal with a real AI model (`rembg`, using the lightweight
  `u2netp` network by default) **and** a fully offline classical fallback
  (OpenCV GrabCut) so the app never hard-depends on an internet connection
  or a large model download.
- Seven background-replacement styles: transparent, solid color (presets
  + custom color picker), gradient (presets + custom two-color gradient),
  blurred version of the original background, a background you upload
  yourself, or one of ten built-in stylized presets (studio, office,
  nature, beach, mountain, city, classroom, corporate, gradient, abstract).
- Interactive editing: resize / position / rotate / opacity sliders for
  the extracted subject.
- Export to PNG (with transparency), JPEG (transparent areas flattened
  onto a chosen color), or WEBP (with or without transparency), with a
  quality slider and an explicit "keep metadata" vs. "remove metadata"
  choice.
- Defensive error handling throughout: corrupted files, missing EXIF,
  missing GPS, background-removal failures, and oversized images are all
  handled with friendly messages instead of crashes or stack traces.

---

## 3. Technologies Used

| Purpose                        | Library                         |
|--------------------------------|----------------------------------|
| Web UI                         | Streamlit                       |
| Image I/O & basic processing   | Pillow (PIL)                    |
| Computer vision / GrabCut      | OpenCV (`opencv-python-headless`)|
| Numerical operations           | NumPy                           |
| EXIF reference tooling         | piexif, ExifRead                |
| Charts (optional)              | Matplotlib                      |
| AI background removal (opt.)   | rembg + onnxruntime             |
| File hashing                   | hashlib (standard library)      |
| File/path handling             | os, pathlib, tempfile (standard library) |

---

## 4. Python Version

Developed and tested with **Python 3.12**. Python 3.10+ should work fine.

---

## 5. Installation

Clone or copy the project folder, then move into it:

```bash
cd image_metadata_background_changer
```

## 6. Virtual Environment Setup

```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

## 7. Installing Dependencies

```bash
pip install -r requirements.txt
```

> **Note on `rembg` / `onnxruntime`:** these two packages are optional.
> The app detects at startup whether they're installed and available, and
> automatically falls back to a classical OpenCV-based background removal
> method if not. If you do install them, the very first background
> removal will download a small model file (a few MB) from the `rembg`
> GitHub releases — this requires an internet connection just that once.

## 8. Running the Application

Generate the built-in background images once (only needed the first time,
or if the `backgrounds/` folder is empty):

```bash
python generate_backgrounds.py
```

Then launch the app:

```bash
streamlit run app.py
```

Streamlit will print a local URL (typically `http://localhost:8501`) —
open it in your browser.

---

## 9. Project Structure

```
image_metadata_background_changer/
│
├── app.py                     # Streamlit UI - the 7-step workflow
├── generate_backgrounds.py    # One-time script that creates built-in backgrounds
├── requirements.txt
├── README.md
│
├── backgrounds/               # Built-in predefined background images
│   ├── studio.jpg
│   ├── office.jpg
│   ├── nature.jpg
│   ├── beach.jpg
│   ├── mountain.jpg
│   ├── city.jpg
│   ├── classroom.jpg
│   ├── corporate.jpg
│   ├── gradient.jpg
│   └── abstract.jpg
│
├── modules/
│   ├── __init__.py
│   ├── metadata.py            # Basic / EXIF / GPS metadata + hashing
│   ├── image_analysis.py      # Brightness, color, dominant colors, histogram
│   ├── background_removal.py  # AI (rembg) + classical (GrabCut) removal
│   ├── background_editor.py   # Solid/gradient/blur backgrounds + compositing
│   ├── image_export.py        # Metadata stripping + PNG/JPEG/WEBP export
│   └── utils.py                # Shared helpers, validation, safe-call decorator
│
└── outputs/                   # (optional) local scratch space for exports
```

---

## 10. How Metadata Extraction Works

- **Basic metadata** comes straight from Pillow (`Image.format`,
  `Image.size`, `Image.mode`) plus the raw uploaded bytes (for file size
  and MIME type).
- **EXIF metadata** is read via Pillow's built-in `Image.getexif()`, which
  is decoded using the standard EXIF tag tables (`PIL.ExifTags`). Only a
  curated set of the most useful/human-readable fields are shown (camera,
  lens, exposure settings, timestamps, etc.), with values formatted into
  friendly units (e.g. `f/2.8`, `1/200 sec`, `50.0 mm`).
- **GPS metadata** lives in a nested EXIF "IFD" block. The raw
  degrees/minutes/seconds values are converted into decimal latitude and
  longitude. If GPS data is found, the UI shows an explicit privacy
  warning **before** displaying the coordinates.
- **Hashes** (MD5, SHA-256) are computed directly from the raw file bytes
  using Python's built-in `hashlib`.

Every extractor is wrapped so that missing or malformed metadata never
crashes the app — it just results in an empty section with a friendly
"not found" message.

## 11. How Background Removal Works

1. The app first tries `rembg`, an AI segmentation library, using its
   lightweight `u2netp` model. This produces the highest-quality cutouts,
   especially for people and complex objects.
2. If `rembg`/`onnxruntime` aren't installed, or the model can't be
   loaded (e.g. no internet on first run), the app automatically falls
   back to a **classical** method: OpenCV's GrabCut algorithm, seeded
   with a rectangle that assumes the subject is roughly centered in the
   frame. This works fully offline but is less accurate for busy or
   off-center scenes.
3. Either way, the result is an RGBA image with a transparent background,
   which then feeds into the background-replacement step.

Very large images are automatically downsized *for this processing step
only* to keep the app responsive; your final export always composites at
your chosen resolution.

## 12. Privacy Considerations

- All processing happens locally in your own Python process — no image is
  sent to an external server by this app.
- If GPS metadata is found in an uploaded photo, the app clearly warns you
  before showing the coordinates, since this reveals where the photo was
  taken.
- You can explicitly choose "Remove Metadata" at export time to strip all
  EXIF/GPS/software metadata from the final downloaded file.
- Uploaded images are only held in memory / Streamlit's session state for
  the duration of your session; nothing is written permanently to disk by
  default.

## 13. Known Limitations

- The classical (GrabCut) background-removal fallback assumes the subject
  is roughly centered and works best on relatively simple scenes; it will
  be noticeably less accurate than the AI model on cluttered or
  off-center compositions.
- Dominant-color detection and the histogram are computed on a
  thumbnail-scale copy for speed, so extremely fine color detail won't be
  reflected.
- The "AI-Generated Background" (text-prompt) option described in the
  original spec is intentionally **not** included, since it requires an
  external paid API and the project is designed to work fully offline —
  the "Upload Background" and ten built-in presets cover the same use
  case without that dependency.
- EXIF field coverage focuses on the most commonly useful tags rather
  than the full EXIF specification (hundreds of possible tags).

## 14. Future Improvements

- Face/object detection to auto-seed the GrabCut rectangle more
  accurately, or to support multiple subjects.
- Batch processing of multiple images at once.
- An in-app metadata *editor* (not just remove/keep).
- Optional integration with a real text-to-image API for AI-generated
  backgrounds (kept as a pluggable, opt-in module).
- Image enhancement / super-resolution before or after background
  replacement.
- A proper interactive before/after slider (currently side-by-side).
- Watermarking and simple batch export to a ZIP file.

---

## License / Usage

This project was generated as a learning/portfolio exercise. Feel free to
adapt, extend, or repurpose any part of it.
