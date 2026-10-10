# -*- coding: utf-8 -*-
"""
Carrusel P30 — Cuando alguien sabe quedarse.
Slide 1: imagen original con watermark.
Slides 2-4: texto narrativo sobre el tema.
Slide 5: CTA.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess, imageio_ffmpeg

BASE = Path(__file__).parent.parent
FONT_PATH = BASE / "tools/reel_template/fonts/PlayfairDisplay.ttf"
OUT_DIR = BASE / "09_Usados_video/meta/piezas/30-dualidad-lectora"
ORIG_IMAGE = BASE / "nuevo_flujo/Imagenes david/1000106606_v3.png"

W, H = 1080, 1350
BG = (252, 252, 250)
DARK = (28, 24, 20)
ACCENT = (80, 100, 130)
DIVIDER = (200, 200, 195)
FF = imageio_ffmpeg.get_ffmpeg_exe()


def font(size):
    return ImageFont.truetype(str(FONT_PATH), size)


def draw_watermark_topright(draw, text="davidportodiaz.com"):
    f = font(22)
    bb = draw.textbbox((0, 0), text, font=f)
    tw = bb[2] - bb[0]
    draw.text((W - tw - 24, 24), text, font=f, fill=(120, 100, 80, 180))


def wrap_text(draw, text, font_obj, max_width):
    words = text.split()
    lines, current = [], []
    for w in words:
        test = " ".join(current + [w])
        bb = draw.textbbox((0, 0), test, font=font_obj)
        if bb[2] - bb[0] > max_width and current:
            lines.append(" ".join(current))
            current = [w]
        else:
            current.append(w)
    if current:
        lines.append(" ".join(current))
    return lines


def make_slide1_image(out_path):
    font_file = str(FONT_PATH).replace("\\", "/").replace(":", "\\:")
    filt = (
        "scale={W}:{H}:force_original_aspect_ratio=decrease,"
        "pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=fafafa,"
        "drawtext=fontfile='{f}'"
        ":text='davidportodiaz.com'"
        ":fontcolor=white@0.85:fontsize=26:x=W-tw-24:y=24"
        ":shadowcolor=black@0.5:shadowx=2:shadowy=2"
    ).format(W=W, H=H, f=font_file)
    r = subprocess.run(
        [FF, "-y", "-i", str(ORIG_IMAGE), "-vf", filt, "-frames:v", "1", str(out_path)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    print("  " + out_path.name + " OK")


def make_text_slide(text_blocks, out_path):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    y = H // 6
    for text, style in text_blocks:
        if style == "large":
            f = font(72)
            color = DARK
        elif style == "accent":
            f = font(60)
            color = ACCENT
        elif style == "body":
            f = font(44)
            color = DARK
        else:
            f = font(32)
            color = (140, 130, 120)
        lines = wrap_text(draw, text, f, W - 100)
        for line in lines:
            bb = draw.textbbox((0, 0), line, font=f)
            lw = bb[2] - bb[0]
            lh = bb[3] - bb[1]
            draw.text(((W - lw) // 2, y), line, font=f, fill=color)
            y += lh + 14
        y += 28
    draw_watermark_topright(draw)
    img.save(str(out_path), quality=95)
    print("  " + out_path.name + " OK")


def make_cta_slide(out_path):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    x0 = (W - 300) // 2
    draw.line([(x0, H // 3 - 20), (x0 + 300, H // 3 - 20)], fill=DIVIDER, width=2)
    f_big = font(70)
    q = "¿Tienes a alguien así?"
    bb = draw.textbbox((0, 0), q, font=f_big)
    y = H // 3 + 10
    draw.text(((W - (bb[2] - bb[0])) // 2, y), q, font=f_big, fill=DARK)
    y += (bb[3] - bb[1]) + 36
    f_cta = font(42)
    cta = "Cuéntamelo en comentarios."
    bb2 = draw.textbbox((0, 0), cta, font=f_cta)
    draw.text(((W - (bb2[2] - bb2[0])) // 2, y), cta, font=f_cta, fill=ACCENT)
    y += (bb2[3] - bb2[1]) + 60
    draw.line([(x0, y), (x0 + 300, y)], fill=DIVIDER, width=2)
    f_web = font(28)
    web = "davidportodiaz.com"
    bb3 = draw.textbbox((0, 0), web, font=f_web)
    draw.text(((W - (bb3[2] - bb3[0])) // 2, H - 80), web, font=f_web, fill=(160, 140, 110))
    draw_watermark_topright(draw)
    img.save(str(out_path), quality=95)
    print("  " + out_path.name + " OK")


if __name__ == "__main__":
    print("=== Build P30 Carrusel Dualidad ===")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    make_slide1_image(OUT_DIR / "slide_00_imagen.png")

    make_text_slide([
        ("Hay personas", "large"),
        ("que no buscan soluciones.", "body"),
    ], OUT_DIR / "slide_01_hay.png")

    make_text_slide([
        ("No arreglan nada.", "large"),
        ("Tampoco dicen que todo irá bien.", "body"),
        ("Solo se quedan.", "accent"),
    ], OUT_DIR / "slide_02_quedan.png")

    make_text_slide([
        ("Y eso es", "large"),
        ("lo más difícil", "accent"),
        ("de encontrar.", "body"),
    ], OUT_DIR / "slide_03_dificil.png")

    make_cta_slide(OUT_DIR / "slide_04_cta.png")

    print("\nP30 listo.")
