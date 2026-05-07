"""
Royal Now-Playing Image Card Generator
Golden royal aesthetic — the viral feature
"""
import io
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CARD_W, CARD_H = 900, 320

# Colors
GOLD        = (255, 200, 50)
GOLD_DARK   = (180, 130, 10)
WHITE       = (245, 240, 225)
GRAY        = (160, 150, 130)
BG_DARK     = (8, 6, 18)
BG_MID      = (20, 15, 35)
ACCENT      = (255, 170, 0)
PREMIUM_COL = (255, 215, 0)

def _load_font(size: int, bold: bool = False) -> ImageFont:
    paths = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{'-Bold' if bold else ''}.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _fetch_thumb(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        pass
    return None

def _rounded_rect_mask(size: tuple, radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0]-1, size[1]-1], radius=radius, fill=255)
    return mask

def make_card(track: dict, requester_name: str, elapsed: int = 0, is_premium: bool = False) -> bytes:
    # ── Canvas ───────────────────────────────
    card = Image.new("RGBA", (CARD_W, CARD_H), BG_DARK)
    draw = ImageDraw.Draw(card)

    # Gradient background
    for i in range(CARD_H):
        t    = i / CARD_H
        r    = int(BG_DARK[0] + (BG_MID[0] - BG_DARK[0]) * t)
        g    = int(BG_DARK[1] + (BG_MID[1] - BG_DARK[1]) * t)
        b    = int(BG_DARK[2] + (BG_MID[2] - BG_DARK[2]) * t)
        draw.line([(0, i), (CARD_W, i)], fill=(r, g, b, 255))

    # Subtle gold vignette on right
    for x in range(CARD_W // 2, CARD_W):
        alpha = int(15 * (x - CARD_W // 2) / (CARD_W // 2))
        draw.line([(x, 0), (x, CARD_H)], fill=(180, 130, 10, alpha))

    # ── Thumbnail ────────────────────────────
    THUMB_SZ = 260
    THUMB_X, THUMB_Y = 25, 30

    thumb_img = _fetch_thumb(track.get("thumb", ""))
    if thumb_img:
        thumb_img = thumb_img.resize((THUMB_SZ, THUMB_SZ), Image.LANCZOS)
        mask = _rounded_rect_mask((THUMB_SZ, THUMB_SZ), 20)
        # Glow effect behind thumb
        glow = Image.new("RGBA", (THUMB_SZ + 20, THUMB_SZ + 20), (0, 0, 0, 0))
        glow_d = ImageDraw.Draw(glow)
        glow_d.rounded_rectangle([5, 5, THUMB_SZ + 14, THUMB_SZ + 14], radius=22, fill=(*GOLD, 60))
        glow = glow.filter(ImageFilter.GaussianBlur(8))
        card.paste(glow, (THUMB_X - 10, THUMB_Y - 10), glow)
        card.paste(thumb_img, (THUMB_X, THUMB_Y), mask)
    else:
        # Placeholder
        ph = Image.new("RGBA", (THUMB_SZ, THUMB_SZ), (30, 20, 5, 255))
        mask = _rounded_rect_mask((THUMB_SZ, THUMB_SZ), 20)
        ImageDraw.Draw(ph).text((THUMB_SZ//2 - 20, THUMB_SZ//2 - 20), "🎵", font=_load_font(48))
        card.paste(ph, (THUMB_X, THUMB_Y), mask)

    # ── Text area ────────────────────────────
    TX = THUMB_X + THUMB_SZ + 30
    TW = CARD_W - TX - 25  # available width

    font_label  = _load_font(13)
    font_title  = _load_font(26, bold=True)
    font_body   = _load_font(18)
    font_small  = _load_font(14)

    draw = ImageDraw.Draw(card)

    # "NOW PLAYING" label
    label_text = "♛  NOW PLAYING" + ("  💎 PREMIUM" if is_premium else "")
    draw.text((TX, 32), label_text, font=font_label, fill=GOLD)

    # Gold underline
    label_w = draw.textlength(label_text, font=font_label)
    draw.line([(TX, 50), (TX + label_w, 50)], fill=GOLD_DARK, width=1)

    # Song title — truncate
    title = track.get("title", "Unknown")
    while draw.textlength(title, font=font_title) > TW and len(title) > 5:
        title = title[:-4] + "..."
    draw.text((TX, 58), title, font=font_title, fill=WHITE)

    # Artist / source badge
    source  = track.get("source", "YouTube")
    artist  = track.get("artist", "")
    sub_txt = f"{artist}  ·  {source}" if artist else source
    draw.text((TX, 95), sub_txt, font=font_small, fill=GRAY)

    # Duration
    from player import duration_str
    total_s   = track.get("duration", 0)
    dur_text  = f"⏱  {duration_str(elapsed)} / {duration_str(total_s)}"
    draw.text((TX, 118), dur_text, font=font_body, fill=GRAY)

    # Progress bar
    BAR_Y   = 150
    BAR_H   = 10
    BAR_X2  = TX + TW
    # Track
    draw.rounded_rectangle([TX, BAR_Y, BAR_X2, BAR_Y + BAR_H], radius=5, fill=(40, 30, 10))
    # Fill
    if total_s and elapsed:
        pct    = min(elapsed / total_s, 1.0)
        filled = int(TW * pct)
        if filled > 0:
            draw.rounded_rectangle([TX, BAR_Y, TX + filled, BAR_Y + BAR_H], radius=5, fill=ACCENT)
        # Thumb dot
        dot_x = TX + filled
        draw.ellipse([dot_x - 7, BAR_Y - 4, dot_x + 7, BAR_Y + BAR_H + 4], fill=GOLD)

    # Requester
    req_text = f"🎤  Requested by {requester_name}"
    draw.text((TX, BAR_Y + 20), req_text, font=font_body, fill=GRAY)

    # Source icon row
    icons_y = BAR_Y + 48
    draw.text((TX, icons_y), "🔊 320kbps" if is_premium else "🔊 128kbps", font=font_small, fill=GOLD_DARK)

    # Sponsor text (if applicable)
    if is_premium:
        sp_text = "💎 PREMIUM QUALITY"
        draw.text((TX, icons_y + 20), sp_text, font=font_small, fill=(*GOLD, 180))

    # ── Corner Ornaments ─────────────────────
    sz = 45
    for pts, fill in [
        ([(0,0),(sz,0)], GOLD), ([(0,0),(0,sz)], GOLD),
        ([(CARD_W,0),(CARD_W-sz,0)], GOLD), ([(CARD_W,0),(CARD_W,sz)], GOLD),
        ([(0,CARD_H),(sz,CARD_H)], GOLD), ([(0,CARD_H),(0,CARD_H-sz)], GOLD),
        ([(CARD_W,CARD_H),(CARD_W-sz,CARD_H)], GOLD), ([(CARD_W,CARD_H),(CARD_W,CARD_H-sz)], GOLD),
    ]:
        draw.line(pts, fill=fill, width=2)

    # Bottom gold bar
    draw.rectangle([(0, CARD_H - 4), (CARD_W, CARD_H)], fill=(*GOLD, 180))

    # ── Export ───────────────────────────────
    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="JPEG", quality=93)
    buf.seek(0)
    return buf.read()
