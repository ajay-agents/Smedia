import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

# Preset background templates (FR5: 2-3 preset options). Generated procedurally
# with Pillow gradients so no external asset downloads are required.
TEMPLATES = {
    "midnight": {
        "top": (15, 23, 42),
        "bottom": (30, 64, 175),
        "text_color": (255, 255, 255),
        "accent": (56, 189, 248),
    },
    "sunset": {
        "top": (124, 58, 237),
        "bottom": (249, 115, 22),
        "text_color": (255, 255, 255),
        "accent": (255, 255, 255),
    },
    "forest": {
        "top": (6, 78, 59),
        "bottom": (132, 204, 22),
        "text_color": (255, 255, 255),
        "accent": (250, 204, 21),
    },
}

_FONT_CANDIDATES = [
    "arialbd.ttf",
    "Arial Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _gradient_background(size, top_color, bottom_color) -> Image.Image:
    width, height = size
    base = Image.new("RGB", size, top_color)
    overlay = Image.new("RGB", size, bottom_color)
    mask = Image.new("L", size)
    mask_row = [int(255 * (y / max(height - 1, 1))) for y in range(height)]
    mask.putdata([v for v in mask_row for _ in range(width)])
    base.paste(overlay, (0, 0), mask)
    return base


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_thumbnail(headline: str, template: str = "midnight", size=(1280, 720), output_path: str = None) -> str:
    """Compose a YouTube thumbnail: gradient background + bold centered text overlay.

    Returns the path to the saved PNG (FR5: downloadable PNG output).
    """
    if template not in TEMPLATES:
        template = "midnight"
    cfg = TEMPLATES[template]

    img = _gradient_background(size, cfg["top"], cfg["bottom"]).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")

    max_width = size[0] - 160
    max_height = size[1] - 220
    headline = headline.upper().strip()

    font_size = 110
    wrap_width = 16
    wrapped = textwrap.fill(headline, width=wrap_width)
    font = _load_font(font_size)

    while font_size > 28:
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=12, align="center")
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w <= max_width and h <= max_height:
            break
        font_size -= 6
        wrap_width = min(wrap_width + 1, 30)
        wrapped = textwrap.fill(headline, width=wrap_width)
        font = _load_font(font_size)

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=12, align="center")
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size[0] - w) / 2 - bbox[0]
    y = (size[1] - h) / 2 - bbox[1]

    pad = 36
    draw.rounded_rectangle(
        [x - pad, y - pad, x + w + pad, y + h + pad], radius=20, fill=(0, 0, 0, 130)
    )
    draw.multiline_text((x, y), wrapped, font=font, fill=cfg["text_color"], align="center", spacing=12)

    bar_height = 16
    draw.rectangle([0, size[1] - bar_height, size[0], size[1]], fill=cfg["accent"])

    img = img.convert("RGB")

    if output_path is None:
        os.makedirs("data/thumbnails", exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in headline)[:40] or "thumbnail"
        output_path = f"data/thumbnails/{safe_name}_{template}.png"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path, "PNG")
    return output_path
