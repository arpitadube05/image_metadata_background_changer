"""
metadata.py
-----------
Everything related to reading information *about* an image file:
- basic file/image properties (size, format, dimensions, color mode...)
- EXIF metadata (camera, lens, exposure settings, timestamps...)
- GPS metadata (converted to readable latitude/longitude/altitude)
- file hashes (MD5, SHA-256) for integrity/identity checks

All functions are defensive: missing metadata never raises, it just
results in empty dictionaries or "not available" values, which the UI
layer turns into friendly messages.
"""

import os
import hashlib
from typing import Dict, Any, Optional

from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS

from .utils import human_readable_size, get_mime_type, safe_call

# Basic file / image metadata
@safe_call(default={})
def extract_basic_metadata(image: Image.Image, filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """
    Collect basic, always-available information about the file and image.
    Does not depend on EXIF being present at all.
    """
    width, height = image.size
    mode = image.mode
    fmt = image.format or os.path.splitext(filename)[1].replace(".", "").upper() or "UNKNOWN"

    # Channels / bits-per-pixel are derived from PIL mode
    mode_channel_map = {
        "1": (1, 1), "L": (1, 8), "P": (1, 8), "RGB": (3, 24),
        "RGBA": (4, 32), "CMYK": (4, 32), "YCbCr": (3, 24),
        "LAB": (3, 24), "HSV": (3, 24), "I": (1, 32), "F": (1, 32),
    }
    channels, bits_per_pixel = mode_channel_map.get(mode, (None, None))

    aspect_ratio = _simplify_ratio(width, height)

    return {
        "Filename": filename,
        "File Extension": os.path.splitext(filename)[1].lower() or "N/A",
        "File Size": human_readable_size(len(file_bytes)),
        "File Size (bytes)": len(file_bytes),
        "MIME Type": get_mime_type(fmt),
        "Format": fmt,
        "Width (px)": width,
        "Height (px)": height,
        "Aspect Ratio": aspect_ratio,
        "Color Mode": mode,
        "Number of Channels": channels if channels is not None else "N/A",
        "Bits per Pixel": bits_per_pixel if bits_per_pixel is not None else "N/A",
    }


def _simplify_ratio(width: int, height: int) -> str:
    """Reduce width:height to a simplified ratio like 16:9."""
    if width == 0 or height == 0:
        return "N/A"

    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a

    g = gcd(width, height)
    if g == 0:
        return f"{width}:{height}"
    return f"{width // g}:{height // g}"


# EXIF metadata
# Human-friendly labels for the EXIF tags we care most about.
_EXIF_FIELDS_OF_INTEREST = {
    "DateTimeOriginal": "Date/Time Taken",
    "DateTime": "Date/Time (File)",
    "Make": "Camera Manufacturer",
    "Model": "Camera Model",
    "LensModel": "Lens Information",
    "FocalLength": "Focal Length",
    "ISOSpeedRatings": "ISO",
    "PhotographicSensitivity": "ISO",
    "FNumber": "Aperture (f-number)",
    "ExposureTime": "Exposure Time",
    "Flash": "Flash",
    "WhiteBalance": "White Balance",
    "Orientation": "Orientation",
    "Software": "Software Used",
    "ImageDescription": "Image Description",
    "Copyright": "Copyright",
}


@safe_call(default={})
def extract_exif_metadata(image: Image.Image) -> Dict[str, Any]:
    """
    Extract human-readable EXIF fields of interest. Returns an empty dict
    if the image has no EXIF data at all (this is normal for screenshots,
    PNGs, web-downloaded images, etc.)
    """
    raw_exif = image.getexif()
    if not raw_exif or len(raw_exif) == 0:
        return {}

    decoded: Dict[str, Any] = {}
    for tag_id, value in raw_exif.items():
        tag_name = TAGS.get(tag_id, tag_id)
        if tag_name in _EXIF_FIELDS_OF_INTEREST:
            label = _EXIF_FIELDS_OF_INTEREST[tag_name]
            decoded[label] = _format_exif_value(tag_name, value)

    # Some cameras store lens/exposure info in the "Exif IFD" sub-block.
    try:
        exif_ifd = raw_exif.get_ifd(ExifTags.IFD.Exif)
        for tag_id, value in exif_ifd.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if tag_name in _EXIF_FIELDS_OF_INTEREST:
                label = _EXIF_FIELDS_OF_INTEREST[tag_name]
                decoded.setdefault(label, _format_exif_value(tag_name, value))
    except Exception:
        pass

    return decoded


def _format_exif_value(tag_name: str, value: Any) -> str:
    """Turn raw EXIF values into readable strings (fractions, flash codes, etc.)."""
    try:
        if tag_name == "ExposureTime":
            # Pillow returns an IFDRational (or occasionally a plain tuple);
            # normalize both to a float, then format as a 1/x fraction for
            # sub-second exposures, which is how exposure time is
            # conventionally displayed (e.g. "1/200 sec").
            if isinstance(value, tuple) and len(value) == 2:
                numerator, denominator = value
                exposure_seconds = numerator / denominator if denominator else 0.0
            else:
                exposure_seconds = float(value)

            if exposure_seconds <= 0:
                return "N/A"
            if exposure_seconds < 1:
                return f"1/{round(1 / exposure_seconds)} sec"
            return f"{exposure_seconds:.2f} sec"
        if tag_name == "FNumber":
            return f"f/{float(value):.1f}"
        if tag_name == "FocalLength":
            return f"{float(value):.1f} mm"
        if tag_name == "Flash":
            flash_map = {0: "No Flash", 1: "Flash Fired", 5: "Flash Fired, Return not detected",
                         7: "Flash Fired, Return detected", 9: "Flash Fired, Compulsory",
                         16: "No Flash, Compulsory", 24: "No Flash, Auto"}
            return flash_map.get(int(value), f"Code {value}")
        if tag_name == "WhiteBalance":
            return "Auto" if int(value) == 0 else "Manual"
        if tag_name == "Orientation":
            orientation_map = {1: "Normal", 2: "Mirrored horizontal", 3: "Rotated 180°",
                                4: "Mirrored vertical", 5: "Mirrored + rotated 270°",
                                6: "Rotated 90° CW", 7: "Mirrored + rotated 90°",
                                8: "Rotated 90° CCW"}
            return orientation_map.get(int(value), str(value))
        if isinstance(value, bytes):
            return value.decode(errors="ignore").strip("\x00").strip()
        return str(value).strip()
    except Exception:
        return str(value)


# GPS metadata

@safe_call(default={})
def extract_gps_metadata(image: Image.Image) -> Dict[str, Any]:
    """
    Extract and convert GPS EXIF info into readable latitude/longitude/
    altitude values. Returns an empty dict if there is no GPS data.

    NOTE: callers should always show a privacy warning when this returns
    non-empty data, since it reveals where the photo was taken.
    """
    raw_exif = image.getexif()
    if not raw_exif:
        return {}

    try:
        gps_ifd = raw_exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        gps_ifd = None

    if not gps_ifd:
        return {}

    gps_data = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
    if not gps_data:
        return {}

    result: Dict[str, Any] = {}

    lat = _convert_gps_coordinate(gps_data.get("GPSLatitude"), gps_data.get("GPSLatitudeRef"))
    lon = _convert_gps_coordinate(gps_data.get("GPSLongitude"), gps_data.get("GPSLongitudeRef"))
    if lat is not None:
        result["Latitude"] = f"{lat:.6f}"
    if lon is not None:
        result["Longitude"] = f"{lon:.6f}"

    altitude = gps_data.get("GPSAltitude")
    if altitude is not None:
        try:
            alt_value = float(altitude)
            ref = gps_data.get("GPSAltitudeRef", 0)
            if ref == 1:
                alt_value = -alt_value
            result["Altitude"] = f"{alt_value:.1f} m"
        except Exception:
            pass

    timestamp = gps_data.get("GPSTimeStamp")
    datestamp = gps_data.get("GPSDateStamp")
    if timestamp:
        try:
            h, m, s = [float(x) for x in timestamp]
            time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d} UTC"
            result["GPS Timestamp"] = f"{datestamp} {time_str}" if datestamp else time_str
        except Exception:
            pass

    return result


def _convert_gps_coordinate(dms, ref) -> Optional[float]:
    """Convert (degrees, minutes, seconds) EXIF tuples into decimal degrees."""
    if not dms or ref is None:
        return None
    try:
        degrees, minutes, seconds = [float(x) for x in dms]
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
    except Exception:
        return None


def has_gps_data(gps_metadata: Dict[str, Any]) -> bool:
    """Convenience check used by the UI to decide whether to show the privacy warning."""
    return bool(gps_metadata) and ("Latitude" in gps_metadata or "Longitude" in gps_metadata)


# ---------------------------------------------------------------------------
# File hashes
# ---------------------------------------------------------------------------

@safe_call(default={"MD5": "N/A", "SHA-256": "N/A"})
def calculate_file_hash(file_bytes: bytes) -> Dict[str, str]:
    """
    Compute MD5 and SHA-256 hashes of the raw uploaded file. These identify
    the *exact* file — any change to the bytes (including re-saving with the
    same visual content) will produce different hashes.
    """
    md5 = hashlib.md5(file_bytes).hexdigest()
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    return {"MD5": md5, "SHA-256": sha256}


def get_all_metadata(image: Image.Image, filename: str, file_bytes: bytes) -> Dict[str, Dict[str, Any]]:
    """
    Convenience aggregator used by the UI: runs every extractor and returns
    a single nested dictionary grouped by section.
    """
    basic = extract_basic_metadata(image, filename, file_bytes)
    exif = extract_exif_metadata(image)
    gps = extract_gps_metadata(image)
    hashes = calculate_file_hash(file_bytes)

    return {
        "basic": basic,
        "exif": exif,
        "gps": gps,
        "hashes": hashes,
    }
