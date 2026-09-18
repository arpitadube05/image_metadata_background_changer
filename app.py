"""
app.py
------
Image Metadata Analyzer & Background Changer
A Streamlit application that lets a user upload an image, inspect its
metadata and technical properties, remove its background, replace it
with a new one, fine-tune the composition, and export the final result.

Run with:
    streamlit run app.py
"""

import os
import io

import streamlit as st
from PIL import Image

from modules import metadata, image_analysis, background_removal, background_editor, image_export
from modules.utils import (
    validate_image_file, load_image_safely, downscale_for_processing, human_readable_size
)

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Image Metadata Analyzer & Background Changer",
    page_icon="🖼️",
    layout="wide",
)

BACKGROUNDS_DIR = os.path.join(os.path.dirname(__file__), "backgrounds")

PREDEFINED_BACKGROUNDS = {
    "Studio": "studio.jpg",
    "Office": "office.jpg",
    "Nature": "nature.jpg",
    "Beach": "beach.jpg",
    "Mountain": "mountain.jpg",
    "City": "city.jpg",
    "Classroom": "classroom.jpg",
    "Professional / Corporate": "corporate.jpg",
    "Gradient": "gradient.jpg",
    "Abstract": "abstract.jpg",
}

MAX_UPLOAD_MB = 25


def _init_session_state():
    defaults = {
        "original_image": None,
        "original_bytes": None,
        "filename": None,
        "foreground": None,          # RGBA cutout result
        "removal_method": None,
        "removal_message": None,
        "final_image": None,         # last composited preview
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_session_state()

st.title("🖼️ Image Metadata Analyzer & Background Changer")
st.caption("Analyze your image metadata, remove its background, and create a new background — all processed locally.")

# ---------------------------------------------------------------------------
# STEP 1 - Upload
# ---------------------------------------------------------------------------

st.header("Step 1 — Upload Image")

uploaded_file = st.file_uploader(
    "Upload an image (JPG, PNG, WEBP, BMP, TIFF, GIF)",
    type=["jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "gif"],
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()

    if len(file_bytes) > MAX_UPLOAD_MB * 1024 * 1024:
        st.error(f"This file is larger than the {MAX_UPLOAD_MB} MB limit. Please upload a smaller image.")
    else:
        is_valid, error_msg = validate_image_file(file_bytes)
        if not is_valid:
            st.error(error_msg)
        else:
            img, load_error = load_image_safely(file_bytes)
            if img is None:
                st.error(load_error)
            else:
                # New upload detected -> reset downstream state
                if st.session_state["filename"] != uploaded_file.name or st.session_state["original_bytes"] != file_bytes:
                    st.session_state["original_image"] = img
                    st.session_state["original_bytes"] = file_bytes
                    st.session_state["filename"] = uploaded_file.name
                    st.session_state["foreground"] = None
                    st.session_state["removal_method"] = None
                    st.session_state["final_image"] = None

if st.session_state["original_image"] is not None:
    img = st.session_state["original_image"]
    file_bytes = st.session_state["original_bytes"]
    filename = st.session_state["filename"]

    col1, col2 = st.columns([2, 1])
    with col1:
        st.image(img, caption="Uploaded Image", use_container_width=True)
    with col2:
        st.subheader("Basic Information")
        basic_info = metadata.extract_basic_metadata(img, filename, file_bytes)
        st.write(f"**Filename:** {basic_info.get('Filename', 'N/A')}")
        st.write(f"**Format:** {basic_info.get('Format', 'N/A')}")
        st.write(f"**Width:** {basic_info.get('Width (px)', 'N/A')} px")
        st.write(f"**Height:** {basic_info.get('Height (px)', 'N/A')} px")
        st.write(f"**Aspect Ratio:** {basic_info.get('Aspect Ratio', 'N/A')}")
        st.write(f"**Color Mode:** {basic_info.get('Color Mode', 'N/A')}")
        st.write(f"**File Size:** {basic_info.get('File Size', 'N/A')}")

    # -----------------------------------------------------------------
    # STEP 2 - Metadata
    # -----------------------------------------------------------------
    st.header("Step 2 — Analyze Metadata")

    all_meta = metadata.get_all_metadata(img, filename, file_bytes)

    tabs = st.tabs(["File Information", "EXIF Information", "GPS Information", "Hash Information"])

    with tabs[0]:
        st.table({"Property": list(all_meta["basic"].keys()), "Value": [str(v) for v in all_meta["basic"].values()]})

    with tabs[1]:
        if all_meta["exif"]:
            st.table({"Property": list(all_meta["exif"].keys()), "Value": [str(v) for v in all_meta["exif"].values()]})
        else:
            st.info("No EXIF metadata was found in this image. This is common for screenshots, PNGs, or images that have been re-saved or shared through apps that strip metadata.")

    with tabs[2]:
        if metadata.has_gps_data(all_meta["gps"]):
            st.warning(
                "⚠️ This image contains GPS location metadata, which can reveal where the "
                "photo was taken. Be cautious about sharing the original file. This metadata "
                "is never sent anywhere automatically — it's shown here for your awareness only."
            )
            st.table({"Property": list(all_meta["gps"].keys()), "Value": [str(v) for v in all_meta["gps"].values()]})
        else:
            st.info("No GPS information was found in this image.")

    with tabs[3]:
        st.write("These hashes identify the *exact* file. Any change to the bytes — even re-saving with identical visual content — will produce different hashes.")
        st.code(f"MD5:     {all_meta['hashes'].get('MD5', 'N/A')}\nSHA-256: {all_meta['hashes'].get('SHA-256', 'N/A')}")

    # -----------------------------------------------------------------
    # STEP 2b - Image Analysis
    # -----------------------------------------------------------------
    st.header("Image Analysis")

    analysis = image_analysis.get_full_analysis(img, len(file_bytes))

    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        st.metric("Brightness", f"{analysis['brightness']:.1f} / 255", analysis["brightness_label"])
    with ac2:
        avg = analysis["average_color"]
        st.write("**Average Color**")
        st.color_picker("Average RGB", f"#{avg['R']:02x}{avg['G']:02x}{avg['B']:02x}", disabled=True, label_visibility="collapsed")
        st.caption(f"R={avg['R']}, G={avg['G']}, B={avg['B']}")
    with ac3:
        st.write("**Estimated Quality**")
        st.caption(analysis["quality_estimate"])

    st.write("**Dominant Colors**")
    dom_cols = st.columns(len(analysis["dominant_colors"]) or 1)
    for i, (rgb, pct) in enumerate(analysis["dominant_colors"]):
        with dom_cols[i]:
            hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            st.color_picker(f"{pct}%", hex_color, disabled=True, label_visibility="visible", key=f"dom_{i}")

    st.write("**RGB Histogram**")
    hist = analysis["histogram"]
    st.line_chart({"Red": hist["R"], "Green": hist["G"], "Blue": hist["B"]})

    # -----------------------------------------------------------------
    # STEP 3 - Background Removal
    # -----------------------------------------------------------------
    st.header("Step 3 — Background Removal")

    if not background_removal.is_ai_removal_available():
        st.caption("ℹ️ The optional AI model (`rembg`) isn't available in this environment — a classical computer-vision fallback will be used instead. Install `rembg` + `onnxruntime` for higher-quality cutouts.")

    if st.button("🪄 Remove Background", type="primary"):
        with st.spinner("Removing background..."):
            processing_image, was_downscaled, _ = downscale_for_processing(img)
            result, method, message = background_removal.remove_background(processing_image)

            if result is None:
                st.error(message)
                st.session_state["foreground"] = None
            else:
                st.session_state["foreground"] = result
                st.session_state["removal_method"] = method
                st.session_state["removal_message"] = message
                if was_downscaled:
                    st.session_state["removal_message"] += " (Note: a downsized copy was used for processing speed; export uses your chosen composite resolution.)"

    if st.session_state["foreground"] is not None:
        if st.session_state["removal_method"] == "ai":
            st.success(st.session_state["removal_message"])
        else:
            st.info(st.session_state["removal_message"])

        bcol1, bcol2 = st.columns(2)
        with bcol1:
            st.write("**Before**")
            st.image(img, use_container_width=True)
        with bcol2:
            st.write("**After (transparent)**")
            st.image(st.session_state["foreground"], use_container_width=True)

    # -----------------------------------------------------------------
    # STEP 4 & 5 - Choose + Edit Background
    # -----------------------------------------------------------------
    if st.session_state["foreground"] is not None:
        st.header("Step 4 — Choose New Background")

        bg_option = st.radio(
            "Background type",
            ["Transparent", "Solid Color", "Gradient", "Blur", "Upload Background", "Predefined"],
            horizontal=True,
        )

        solid_color = None
        gradient_preset = None
        custom_gradient = None
        uploaded_bg_image = None
        predefined_path = None
        blur_radius = 20

        if bg_option == "Solid Color":
            preset_name = st.selectbox("Quick colors", list(background_editor.SOLID_COLOR_PRESETS.keys()) + ["Custom"])
            if preset_name == "Custom":
                hex_color = st.color_picker("Pick a custom color", "#ffffff")
                solid_color = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
            else:
                solid_color = background_editor.SOLID_COLOR_PRESETS[preset_name]

        elif bg_option == "Gradient":
            gradient_choice = st.selectbox("Gradient preset", list(background_editor.GRADIENT_PRESETS.keys()) + ["Custom"])
            if gradient_choice == "Custom":
                c1, c2 = st.columns(2)
                with c1:
                    start_hex = st.color_picker("Start color", "#5a5ae6")
                with c2:
                    end_hex = st.color_picker("End color", "#9632c8")
                start = tuple(int(start_hex[i:i + 2], 16) for i in (1, 3, 5))
                end = tuple(int(end_hex[i:i + 2], 16) for i in (1, 3, 5))
                custom_gradient = (start, end)
            else:
                gradient_preset = gradient_choice

        elif bg_option == "Blur":
            blur_radius = st.slider("Blur strength", 5, 50, 20)

        elif bg_option == "Upload Background":
            bg_file = st.file_uploader("Upload a background image", type=["jpg", "jpeg", "png", "webp"], key="bg_upload")
            if bg_file is not None:
                bg_bytes = bg_file.getvalue()
                valid, err = validate_image_file(bg_bytes)
                if valid:
                    uploaded_bg_image, _ = load_image_safely(bg_bytes)
                else:
                    st.error(err)

        elif bg_option == "Predefined":
            predefined_choice = st.selectbox("Built-in backgrounds", list(PREDEFINED_BACKGROUNDS.keys()))
            predefined_path = os.path.join(BACKGROUNDS_DIR, PREDEFINED_BACKGROUNDS[predefined_choice])
            if os.path.exists(predefined_path):
                st.image(predefined_path, caption=predefined_choice, width=200)
            else:
                st.warning("This built-in background file is missing. Run generate_backgrounds.py to create it.")
                predefined_path = None

        st.header("Step 5 — Edit (Position, Size, Rotation)")
        e1, e2, e3, e4 = st.columns(4)
        with e1:
            fg_scale = st.slider("Foreground Size (%)", 10, 300, 100)
        with e2:
            x_pos = st.slider("X Position (%)", 0, 100, 50)
        with e3:
            y_pos = st.slider("Y Position (%)", 0, 100, 50)
        with e4:
            rotation = st.slider("Rotation (°)", -180, 180, 0)
        opacity = st.slider("Foreground Opacity (%)", 0, 100, 100)

        # Build the final composite live, so Step 6 always reflects current controls.
        foreground = st.session_state["foreground"]
        edited_fg = background_editor.resize_foreground(foreground, fg_scale)
        edited_fg = background_editor.rotate_foreground(edited_fg, rotation)
        edited_fg = background_editor.apply_opacity(edited_fg, opacity)

        canvas_size = img.size

        if bg_option == "Transparent":
            # Render the foreground alone, centered on a transparent canvas
            canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            cx = int(canvas_size[0] * (x_pos / 100)) - edited_fg.width // 2
            cy = int(canvas_size[1] * (y_pos / 100)) - edited_fg.height // 2
            canvas.alpha_composite(edited_fg, dest=(cx, cy))
            final_image = canvas
        else:
            new_background = background_editor.build_background_for_option(
                option=bg_option,
                canvas_size=canvas_size,
                original_image=img,
                solid_color=solid_color,
                gradient_preset=gradient_preset,
                custom_gradient=custom_gradient,
                uploaded_background=uploaded_bg_image,
                predefined_path=predefined_path,
                blur_radius=blur_radius,
            )
            final_image = background_editor.combine_foreground_background(
                edited_fg, new_background, x_pos, y_pos
            )

        st.session_state["final_image"] = final_image

        # -------------------------------------------------------------
        # STEP 6 - Preview
        # -------------------------------------------------------------
        st.header("Step 6 — Preview")
        pcol1, pcol2 = st.columns(2)
        with pcol1:
            st.write("**Original**")
            st.image(img, use_container_width=True)
        with pcol2:
            st.write("**Edited**")
            st.image(final_image, use_container_width=True)

        # -------------------------------------------------------------
        # STEP 7 - Export
        # -------------------------------------------------------------
        st.header("Step 7 — Export")

        x1, x2, x3 = st.columns(3)
        with x1:
            output_format = st.selectbox("Output Format", ["PNG", "JPEG", "WEBP"])
        with x2:
            quality = st.slider("Quality (JPEG/WEBP)", 10, 100, 90, disabled=(output_format == "PNG"))
        with x3:
            metadata_choice = st.radio("Metadata", ["Keep Metadata", "Remove Metadata"])

        jpeg_bg_color = (255, 255, 255)
        if output_format == "JPEG" and final_image.mode == "RGBA":
            jpeg_bg_hex = st.color_picker("Background color for transparent areas (JPEG has no transparency)", "#ffffff")
            jpeg_bg_color = tuple(int(jpeg_bg_hex[i:i + 2], 16) for i in (1, 3, 5))

        strip = metadata_choice == "Remove Metadata"

        try:
            export_bytes, mime_type, ext = image_export.get_export_bytes(
                final_image, output_format, quality=quality, strip_metadata=strip, background_color=jpeg_bg_color
            )
            st.success(f"Ready to download ({human_readable_size(len(export_bytes))}).")
            st.download_button(
                label="⬇️ Download Final Image",
                data=export_bytes,
                file_name=f"edited_{os.path.splitext(filename)[0]}.{ext}",
                mime=mime_type,
                type="primary",
            )
        except Exception as exc:
            st.error(f"Could not prepare the export: {exc.__class__.__name__}. Please try a different format.")

else:
    st.info("Upload an image above to get started.")

st.divider()
st.caption(
    "🔒 Privacy note: images are processed locally in this session and are not uploaded to any "
    "external service. GPS/location metadata, if present, is shown for your awareness only and "
    "is never transmitted automatically."
)
