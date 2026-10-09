#!/usr/bin/env python3
"""Render determinista de los carruseles IG-12. No genera ni altera las obras."""

from __future__ import annotations

import argparse
import json
import pathlib
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "output"

W, H = 1080, 1350
MARGIN = 54
IMAGE_TOP = 48
IMAGE_BOTTOM = 970
BAND_TOP = 990
BG = (247, 243, 235)
INK = (27, 24, 20)
MUTED = (91, 84, 76)
RULE = (201, 194, 184)


def font(size: int, bold: bool = False):
    # El kit autoriza explícitamente una sans neutra: DejaVu/Arial (Inter también
    # sería válida, pero no se selecciona dinámicamente aquí para evitar variar
    # entre máquinas). La prioridad es determinista y no cae a la fuente bitmap
    # por defecto de Pillow.
    names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    raise RuntimeError(
        "IG12_RENDER_BLOCKED: no se encontró DejaVu Sans ni Arial, las familias "
        "autorizadas por este renderer. Instala una de ellas y repite el gate; "
        "no usar la fuente bitmap por defecto de Pillow."
    )


def find_asset(item_id: str) -> pathlib.Path:
    matches = []
    for ext in ("jpg", "jpeg", "png"):
        p = ASSETS / f"{item_id}.{ext}"
        if p.exists():
            matches.append(p)
    if len(matches) != 1:
        raise FileNotFoundError(f"{item_id}: expected exactly one downloaded asset, got {len(matches)}")
    return matches[0]


def fit_art(path: pathlib.Path, box: tuple[int, int, int, int]) -> Image.Image:
    art = Image.open(path).convert("RGB")
    bw, bh = box[2] - box[0], box[3] - box[1]
    fitted = ImageOps.contain(art, (bw, bh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (bw, bh), BG)
    x = (bw - fitted.width) // 2
    y = (bh - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


def text_width(draw, s, f):
    b = draw.textbbox((0, 0), s, font=f)
    return b[2] - b[0]


def wrap_pixels(draw, text: str, f, max_width: int):
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = word if not line else f"{line} {word}"
        if text_width(draw, test, f) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_centered_lines(draw, lines, y, f, max_width, fill=INK, spacing=12):
    for raw in lines:
        wrapped = wrap_pixels(draw, raw, f, max_width)
        for line in wrapped:
            b = draw.textbbox((0, 0), line, font=f)
            tw, th = b[2] - b[0], b[3] - b[1]
            draw.text(((W - tw) // 2, y), line, font=f, fill=fill)
            y += th + spacing
        y += 4
    return y


def slide1(item, asset):
    im = Image.new("RGB", (W, H), BG)
    art_box = (MARGIN, IMAGE_TOP, W - MARGIN, IMAGE_BOTTOM)
    art = fit_art(asset, art_box)
    im.paste(art, art_box[:2])
    d = ImageDraw.Draw(im)
    d.line((MARGIN, BAND_TOP, W - MARGIN, BAND_TOP), fill=RULE, width=2)
    f = font(54, bold=True)
    draw_centered_lines(d, item["meme_lines"], BAND_TOP + 44, f, W - 2 * MARGIN - 24, spacing=10)
    return im


def slide2(item, asset):
    im = Image.new("RGB", (W, H), BG)
    art_box = (MARGIN, IMAGE_TOP, W - MARGIN, 900)
    art = fit_art(asset, art_box)
    im.paste(art, art_box[:2])
    d = ImageDraw.Draw(im)
    d.line((MARGIN, 922, W - MARGIN, 922), fill=RULE, width=2)
    title_f = font(38, bold=True)
    meta_f = font(30)
    small_f = font(25)
    y = 952
    for line in wrap_pixels(d, item["title"], title_f, W - 2 * MARGIN):
        d.text((MARGIN, y), line, font=title_f, fill=INK)
        y += 48
    artist_label = item["display_artist"] if "display_artist" in item else item["artist"]
    meta_parts = [part for part in (artist_label, item["date_label"]) if part]
    d.text((MARGIN, y + 6), " · ".join(meta_parts), font=meta_f, fill=MUTED)
    disclosure = (
        "La obra original no contiene el texto de la slide anterior. "
        "Imagen Open Access / Public Domain — The Metropolitan Museum of Art."
    )
    y += 62
    for line in wrap_pixels(d, disclosure, small_f, W - 2 * MARGIN):
        d.text((MARGIN, y), line, font=small_f, fill=MUTED)
        y += 35
    return im


def render_item(item):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    asset = find_asset(item["id"])
    s1 = slide1(item, asset)
    s2 = slide2(item, asset)
    s1.save(OUTPUT / f"{item['id']}_slide1.png", optimize=True)
    s2.save(OUTPUT / f"{item['id']}_slide2.png", optimize=True)
    print(f"RENDERED {item['id']}")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = data["items"]
    if args.all:
        selected = items
    else:
        selected = [x for x in items if x["id"] == args.item]
        if not selected:
            raise SystemExit(f"Unknown item: {args.item}")

    # Falla antes de tocar outputs si la máquina no tiene una sans autorizada.
    font(20, False)
    font(20, True)
    for item in selected:
        render_item(item)


if __name__ == "__main__":
    main()
