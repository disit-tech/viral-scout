"""Two-panel "Don't / Do" still (1080×1350, 4:5) from two film frames, for Threads, Facebook and Instagram.

  python -m viral_scout video <profile> still --top a.png --bottom b.png --top-text "DON'T ..." --bottom-text "DO ..." \
      [--source "Source: CDC"] --out still.png [--top-y 0.4] [--bottom-y 0.5]

Frames: any size (usually 1080×1920 film frames, e.g. `ffmpeg -ss 21.5 -i film.mp4 -frames:v 1 a.png`); each is
cropped to 1080×675 around --top-y / --bottom-y (0 = top of the frame, 1 = bottom). Colors, fonts and the brand label
come from the profile (video.colors, video.fonts.still_bold / still_regular). Needs Pillow in the CLI's Python.
"""
from pathlib import Path

from .settings import hex_rgb

W, H = 1080, 1350
PANEL = H // 2
RED, GREEN = (255, 90, 79), (61, 220, 132)
SYSTEM_BOLD = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf"]
SYSTEM_REGULAR = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf"]


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        from .deps import MissingDependency
        raise MissingDependency("Pillow", "pip install pillow (in the Python that runs viral_scout)")
    return Image, ImageDraw, ImageFont


def font_path(v: dict, bold: bool) -> str | None:
    p = v["fonts"].get("still_bold" if bold else "still_regular")
    if p and Path(p).exists():
        return str(p)
    return next((f for f in (SYSTEM_BOLD if bold else SYSTEM_REGULAR) if Path(f).exists()), None)


def _font(path, size):
    _, _, ImageFont = _pil()
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size)


def crop(path: str, focus: float):
    Image, _, _ = _pil()
    im = Image.open(path).convert("RGB")
    im = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
    if im.height < PANEL:
        im = im.resize((round(im.width * PANEL / im.height), PANEL), Image.LANCZOS)
        x = (im.width - W) // 2
        return im.crop((x, 0, x + W, PANEL))
    y = round((im.height - PANEL) * min(1, max(0, focus)))
    return im.crop((0, y, W, y + PANEL))


def fit(draw, text, size, max_w, path):
    while size > 40:
        f = _font(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(path, size)


def badge(draw, cx, cy, r, ok, ink):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GREEN if ok else RED, outline=ink, width=5)
    w = max(8, r // 4)
    if ok:
        draw.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)],
                  fill=ink, width=w, joint="curve")
    else:
        d = r * 0.42
        draw.line([(cx - d, cy - d), (cx + d, cy + d)], fill=ink, width=w)
        draw.line([(cx - d, cy + d), (cx + d, cy - d)], fill=ink, width=w)


def label(img, y0, text, ok, ink, night, bold):
    Image, ImageDraw, _ = _pil()
    shade = Image.new("L", (1, 220))
    for i in range(220):  # dark gradient at the top of the panel so the text reads on any frame
        shade.putpixel((0, i), int(170 * (1 - i / 220)))
    img.paste(Image.new("RGB", (W, 220), night), (0, y0), shade.resize((W, 220)))
    d = ImageDraw.Draw(img)
    r = 46
    badge(d, 40 + r, y0 + 40 + r, r, ok, ink)
    f = fit(d, text, 92, W - (40 + 2 * r + 28) - 40, bold)
    d.text((40 + 2 * r + 28, y0 + 40 + r), text, font=f, fill=ink, anchor="lm", stroke_width=6, stroke_fill=night)


def make(v: dict, top, bottom, top_text, bottom_text, out, source="", brand=None, top_y=0.45, bottom_y=0.45) -> Path:
    Image, ImageDraw, _ = _pil()
    for f in (top, bottom):
        if not Path(f).exists():
            raise SystemExit(f"error: frame not found: {f}")
    c = v["colors"]
    ink, night, accent = hex_rgb(c["text"]), hex_rgb(c["bg"]), hex_rgb(c["accent"])
    bold, regular = font_path(v, True), font_path(v, False)
    brand = v["brand"] if brand is None else brand
    img = Image.new("RGB", (W, H), night)
    img.paste(crop(top, top_y), (0, 0))
    img.paste(crop(bottom, bottom_y), (0, PANEL))
    label(img, 0, top_text.upper(), False, ink, night, bold)
    label(img, PANEL, bottom_text.upper(), True, ink, night, bold)
    d = ImageDraw.Draw(img)
    d.rectangle((0, PANEL - 4, W, PANEL + 4), fill=accent)
    small = _font(regular, 30)
    if source:
        tw = d.textlength(source, font=small)
        d.rounded_rectangle((32, H - 84, 32 + tw + 44, H - 32), radius=26, fill=night)
        d.text((54, H - 58), source, font=small, fill=ink, anchor="lm")
    if brand:
        bw = d.textlength(brand, font=small)
        d.rounded_rectangle((W - 32 - bw - 44, H - 84, W - 32, H - 32), radius=26, fill=night)
        d.text((W - 54, H - 58), brand, font=small, fill=accent, anchor="rm")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92)
    return out
