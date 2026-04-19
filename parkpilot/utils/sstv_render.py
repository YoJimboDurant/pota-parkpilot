from __future__ import annotations

from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


def load_font_x(size_x: int):
    """
    Try a good bold font on Linux first, then Windows Arial,
    then fall back to Pillow default.
    """
    dejavu_path_x = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

    if dejavu_path_x.exists():
        return ImageFont.truetype(str(dejavu_path_x), size_x)

    try:
        return ImageFont.truetype("arial.ttf", size_x)
    except Exception:
        return ImageFont.load_default()


def render_sstv_image_x(
    input_path_x: Path,
    output_path_x: Path,
    template_type_x: str,
    my_call_x: str,
    park_id_x: str,
    their_call_x: str = "",
    rsv_x: str = "",
    caption_x: str = "",
) -> Path:
    # ---------- LOAD IMAGE ----------
    img_x = Image.open(input_path_x).convert("RGB")

    # ---------- CROP TO 4:3 ----------
    width_x, height_x = img_x.size
    target_ratio_x = 4 / 3
    current_ratio_x = width_x / height_x

    if current_ratio_x > target_ratio_x:
        # too wide -> crop sides
        new_width_x = int(height_x * target_ratio_x)
        left_x = (width_x - new_width_x) // 2
        img_x = img_x.crop((left_x, 0, left_x + new_width_x, height_x))
    else:
        # too tall -> crop top/bottom
        new_height_x = int(width_x / target_ratio_x)
        top_x = (height_x - new_height_x) // 2
        img_x = img_x.crop((0, top_x, width_x, top_x + new_height_x))

    # ---------- RESIZE TO SSTV ----------
    img_x = img_x.resize((320, 256), Image.LANCZOS)

    width_x, height_x = img_x.size
    draw_x = ImageDraw.Draw(img_x)

    # ---------- FONTS ----------
    font_big_x = load_font_x(int(height_x * 0.15))
    font_med_x = load_font_x(int(height_x * 0.07))
    font_small_x = load_font_x(int(height_x * 0.05))

    # ---------- OVERLAY BARS ----------
    top_bar_h_x = int(height_x * 0.18)
    bottom_bar_h_x = int(height_x * 0.25)

    top_overlay_x = Image.new("RGBA", (width_x, top_bar_h_x), (0, 0, 0, 150))
    bottom_overlay_x = Image.new("RGBA", (width_x, bottom_bar_h_x), (0, 0, 0, 160))

    img_x.paste(top_overlay_x, (0, 0), top_overlay_x)
    img_x.paste(bottom_overlay_x, (0, height_x - bottom_bar_h_x), bottom_overlay_x)

    timestamp_x = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    template_clean_x = str(template_type_x).strip().lower()

    # ---------- CQ ----------
    if template_clean_x == "cq":
        draw_x.text((10, 5), "CQ SSTV", fill="yellow", font=font_big_x)

        y_x = height_x - bottom_bar_h_x + 5
        draw_x.text((10, y_x), my_call_x, fill="yellow", font=font_big_x)

        time_w_x = draw_x.textlength(timestamp_x, font=font_small_x)
        draw_x.text((width_x - time_w_x - 5, y_x + 10), timestamp_x, fill="yellow", font=font_small_x)

        if caption_x:
            draw_x.text((10, y_x + 35), caption_x, fill="yellow", font=font_small_x)

    # ---------- CQ POTA ----------
    elif template_clean_x == "cq_pota":
        draw_x.text((10, 5), "CQ SSTV POTA", fill="yellow", font=font_big_x)

        y_x = height_x - bottom_bar_h_x + 5
        draw_x.text((10, y_x), my_call_x, fill="yellow", font=font_big_x)

        park_w_x = draw_x.textlength(park_id_x, font=font_med_x)
        draw_x.text(((width_x - park_w_x) / 2, y_x + 5), park_id_x, fill="yellow", font=font_med_x)

        time_w_x = draw_x.textlength(timestamp_x, font=font_small_x)
        draw_x.text((width_x - time_w_x - 5, y_x + 10), timestamp_x, fill="yellow", font=font_small_x)

        if caption_x:
            draw_x.text((10, y_x + 35), caption_x, fill="yellow", font=font_small_x)

    # ---------- REPLY ----------
    elif template_clean_x == "reply":
        to_line_x = f"TO: {their_call_x}" if their_call_x else "TO:"
        de_line_x = f"DE: {my_call_x}"
        park_line_x = f"POTA {park_id_x}" if park_id_x else ""
        rsv_line_x = f"RSV {rsv_x}" if rsv_x else ""

        draw_x.text((10, 5), to_line_x, fill="yellow", font=font_big_x)

        de_w_x = draw_x.textlength(de_line_x, font=font_med_x)
        draw_x.text((width_x - de_w_x - 5, 8), de_line_x, fill="yellow", font=font_med_x)

        y_x = height_x - bottom_bar_h_x + 5

        if park_line_x:
            draw_x.text((10, y_x), park_line_x, fill="yellow", font=font_med_x)

        if rsv_line_x:
            rsv_w_x = draw_x.textlength(rsv_line_x, font=font_med_x)
            draw_x.text((width_x - rsv_w_x - 5, y_x), rsv_line_x, fill="yellow", font=font_med_x)

        lower_line_x = caption_x if caption_x else timestamp_x
        draw_x.text((10, y_x + 30), lower_line_x, fill="yellow", font=font_small_x)

    # ---------- 73 ----------
    elif template_clean_x == "73":
        headline_x = f"73 {their_call_x}" if their_call_x else "73"
        de_line_x = f"DE: {my_call_x}"
        park_line_x = f"POTA {park_id_x}" if park_id_x else ""

        draw_x.text((10, 5), headline_x, fill="yellow", font=font_big_x)

        de_w_x = draw_x.textlength(de_line_x, font=font_med_x)
        draw_x.text((width_x - de_w_x - 5, 8), de_line_x, fill="yellow", font=font_med_x)

        y_x = height_x - bottom_bar_h_x + 5

        if park_line_x:
            draw_x.text((10, y_x), park_line_x, fill="yellow", font=font_med_x)

        lower_line_x = caption_x if caption_x else timestamp_x
        draw_x.text((10, y_x + 30), lower_line_x, fill="yellow", font=font_small_x)

    # ---------- FREE FORM ----------
    elif template_clean_x == "free":
        y_top_x = 5

        if their_call_x:
            to_line_x = f"TO: {their_call_x}"
            draw_x.text((10, y_top_x), to_line_x, fill="yellow", font=font_med_x)
            y_top_x += int(height_x * 0.10)

        call_w_x = draw_x.textlength(my_call_x, font=font_big_x)
        draw_x.text(
            ((width_x - call_w_x) / 2, y_top_x),
            my_call_x,
            fill="yellow",
            font=font_big_x,
        )

        if caption_x:
            msg_y_x = height_x - bottom_bar_h_x + 5
            draw_x.text((10, msg_y_x), caption_x, fill="yellow", font=font_med_x)

        time_w_x = draw_x.textlength(timestamp_x, font=font_small_x)
        draw_x.text(
            (width_x - time_w_x - 5, height_x - 20),
            timestamp_x,
            fill="yellow",
            font=font_small_x,
        )

    # ---------- FALLBACK ----------
    else:
        draw_x.text((10, 5), my_call_x, fill="yellow", font=font_big_x)
        draw_x.text(
            (10, height_x - 40),
            f"{park_id_x} | {timestamp_x}" if park_id_x else timestamp_x,
            fill="yellow",
            font=font_small_x,
        )

        if caption_x:
            draw_x.text((10, height_x - 20), caption_x, fill="yellow", font=font_small_x)

    img_x.save(output_path_x, "JPEG", quality=90)
    return output_path_x