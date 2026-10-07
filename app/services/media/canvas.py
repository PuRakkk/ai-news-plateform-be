import re
import textwrap
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.core.log import logger


def _get_font(name: str, size: int) -> ImageFont.ImageFont:
    """Attempt to load requested truetype font, with graceful fallbacks."""
    candidates = [
        f"{name.lower()}.ttf",
        f"{name}.ttf",
        "arialbd.ttf" if "bold" in name.lower() else "arial.ttf",
        "segoeui.ttf",
        "calibri.ttf",
    ]
    for cand in candidates:
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _extract_metric(text: str) -> str | None:
    """Detect key numbers, percentages, or dollar amounts to display as a prominent stat badge."""
    pattern = r"(\$\d+(?:\.\d+)?(?:[BMK]| billion| million)?|\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?x\b|\b\d+x\b)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _build_avatar_frame(
    avatar_path: Path,
    width: int,
    height: int,
    primary_color: str,
    accent_color: str,
    badge_label: str = "AI PRESENTER // ON AIR",
    font_family: str = "Arial",
) -> Image.Image:
    """Frame the presenter portrait with rounded corners, glowing double-border, and live status badge."""
    orig = Image.open(avatar_path).convert("RGB")
    fit_img = ImageOps.fit(orig, (width, height), Image.Resampling.LANCZOS)

    mask = Image.new("L", (width, height), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.rounded_rectangle([0, 0, width, height], radius=36, fill=255)

    pad = 12
    fw, fh = width + (pad * 2), height + (pad * 2)
    frame = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    f_draw = ImageDraw.Draw(frame)

    # Outer primary glow
    f_draw.rounded_rectangle([0, 0, fw, fh], radius=40, fill="#131D31", outline=primary_color, width=3)
    # Inner accent highlight ring
    f_draw.rounded_rectangle([4, 4, fw - 4, fh - 4], radius=36, outline=accent_color, width=2)
    # Paste masked avatar
    frame.paste(fit_img, (pad, pad), mask=mask)

    # Live Broadcast Status Badge at bottom of frame
    font_badge = _get_font(font_family, 20)
    badge_text = f"  ● {badge_label}  "
    bbox = f_draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox[2] - bbox[0]
    bx = (fw - bw) // 2
    by = fh - 28
    f_draw.rounded_rectangle(
        [bx - 6, by - 4, bx + bw + 6, by + 24],
        radius=10,
        fill="#090D16",
        outline=accent_color,
        width=2,
    )
    f_draw.text((bx, by), badge_text, font=font_badge, fill=accent_color)

    return frame


def render_beat_card(
    beat_index: int,
    beat_type: str,
    headline: str,
    content_text: str,
    client_name: str = "AI News Daily",
    persona_role: str = "AI Chief of Staff",
    source_feed: str = "Verified Source",
    brand_colors: dict[str, str] | None = None,
    font_family: str = "Arial",
    watermark_logo_path: str | Path | None = None,
    avatar_image_path: str | Path | None = None,
    visual_directive: str | None = None,
) -> Image.Image:
    """Render a modern, minimalist 1080x1920 vertical broadcast card without text clutter."""
    colors = brand_colors or {}
    bg_color = colors.get("background_hex", "#090D16")
    primary_color = colors.get("primary_hex", "#2563EB")
    accent_color = colors.get("accent_hex", "#F59E0B")
    card_bg = "#131D31"
    text_white = "#FFFFFF"

    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # 1. Subtle top glowing border
    draw.rectangle([0, 0, width, 6], fill=primary_color)

    # 2. Sleek Minimalist Top Bar (Y: 55 to 110)
    font_top = _get_font(font_family, 22)

    # Clean Brand Pill on Top-Left
    clean_client = client_name.strip()
    brand_label = f"  ● {clean_client.upper()}  "
    brand_bbox = draw.textbbox((70, 60), brand_label, font=font_top)
    draw.rounded_rectangle(
        [brand_bbox[0] - 6, brand_bbox[1] - 4, brand_bbox[2] + 6, brand_bbox[3] + 4],
        radius=12,
        fill="#1E293B",
        outline=primary_color,
        width=1,
    )
    draw.text((70, 60), brand_label, font=font_top, fill=text_white)

    # Sleek Micro Progress Indicator on Top-Right (5 discrete segment pills)
    seg_w = 40
    seg_h = 6
    seg_gap = 8
    total_prog_w = (seg_w * 5) + (seg_gap * 4)
    prog_start_x = width - 70 - total_prog_w
    prog_y = 70

    for i in range(1, 6):
        sx1 = prog_start_x + (i - 1) * (seg_w + seg_gap)
        sx2 = sx1 + seg_w
        is_active = (i <= beat_index)
        seg_fill = accent_color if i == beat_index else (primary_color if is_active else "#2A374A")
        draw.rounded_rectangle([sx1, prog_y, sx2, prog_y + seg_h], radius=3, fill=seg_fill)

    # 3. Clean Headline Card (Y: 130 to 450)
    # Eliminates multiline body text dump to avoid visual clutter with spoken audio & subtitles
    draw.rounded_rectangle([70, 130, width - 70, 450], radius=24, fill=card_bg, outline="#1E293B", width=2)

    # Category Pill
    font_tag = _get_font(font_family, 18)
    cat_text = f"  ● EXECUTIVE BRIEF  //  {persona_role.upper()}  "
    cat_bbox = draw.textbbox((95, 155), cat_text, font=font_tag)
    draw.rounded_rectangle(
        [cat_bbox[0] - 4, cat_bbox[1] - 4, cat_bbox[2] + 4, cat_bbox[3] + 4],
        radius=8,
        fill="#1E293B",
        outline=accent_color,
        width=1,
    )
    draw.text((95, 155), cat_text, font=font_tag, fill=accent_color)

    # Bold Headline (Max 2-3 clean lines, readable at speed)
    font_head = _get_font(font_family, 42)
    wrapped_headline = textwrap.fill(headline, width=28)
    draw.text((95, 210), wrapped_headline, font=font_head, fill=text_white, spacing=8)

    # Key Metric Pill (If present, prominent highlight)
    metric = _extract_metric(content_text)
    if metric:
        font_metric = _get_font(font_family, 36)
        m_label = f"  KEY STAT: {metric}  "
        mbox = draw.textbbox((95, 360), m_label, font=font_metric)
        draw.rounded_rectangle(
            [mbox[0] - 6, mbox[1] - 4, mbox[2] + 6, mbox[3] + 4],
            radius=10,
            fill="#090D16",
            outline=accent_color,
            width=2,
        )
        draw.text((95, 360), m_label, font=font_metric, fill=accent_color)

    # 4. Presenter Avatar Frame (Y: 480 to 1280)
    has_avatar = avatar_image_path and Path(avatar_image_path).exists()
    if has_avatar:
        av_path = Path(avatar_image_path)
        av_size = 540
        av_frame = _build_avatar_frame(
            avatar_path=av_path,
            width=av_size,
            height=av_size,
            primary_color=primary_color,
            accent_color=accent_color,
            badge_label=f"{persona_role.upper()} // ON AIR",
            font_family=font_family,
        )
        av_x = (width - av_frame.width) // 2
        av_y = 480
        img.paste(av_frame, (av_x, av_y), mask=av_frame)

    # Optional Watermark logo (Top Right, above headline card)
    if watermark_logo_path and Path(watermark_logo_path).exists():
        try:
            logo = Image.open(watermark_logo_path).convert("RGBA")
            logo.thumbnail((160, 60), Image.Resampling.LANCZOS)
            img.paste(logo, (width - 160 - 70, 55), mask=logo)
        except Exception as exc:
            logger.warning(f"Failed to paste watermark into canvas: {exc}")

    # 5. Clean Safe-Area Footer (Y: 1720 to 1820)
    # The lower-third (Y: 1350 to 1700) is reserved for kinetic ASS subtitles
    font_footer = _get_font(font_family, 22)
    source_label = f"SOURCE: {source_feed.upper()}  •  VERIFIED INTELLIGENCE"
    draw.text((70, 1750), source_label, font=font_footer, fill="#64748B")

    return img
