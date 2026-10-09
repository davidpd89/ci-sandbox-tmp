#!/usr/bin/env python3
"""Render IG-11 archive puzzles from verified LOC images.

Dependencies:
  pip install pillow qrcode
  fontconfig + Inter installed locally

Usage:
  python tools/archive_impossible/render_archive_impossible.py \
    tools/archive_impossible/ig11_manifest.json \
    --assets assets/archive_impossible \
    --out build/ig11

Slides 1–3 are declared montages with one deterministic local anachronism.
Slide 4 places the untouched source image inside a reserved image region;
all labels and credits are outside that region.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode

W, H = 1080, 1350
BG = "#11100F"
TEXT = "#F7F1E8"
ACCENT = "#C27937"


@lru_cache(maxsize=2)
def font_path(kind: str) -> str:
    """Resolve the audited Inter family and reject silent substitutes."""
    if kind not in {"sans", "sans_bold"}:
        raise ValueError(f"Unknown font kind: {kind}")
    if not shutil.which("fc-match"):
        raise RuntimeError(
            "IG11_RENDER_BLOCKED: falta fc-match/fontconfig. "
            "Instala fontconfig e Inter antes del gate; no usar la fuente por defecto de Pillow."
        )
    query = "Inter:style=Bold" if kind == "sans_bold" else "Inter:style=Regular"
    try:
        raw = subprocess.check_output(
            ["fc-match", "-f", "%{family}\n%{style}\n%{file}", query],
            text=True,
        ).strip().splitlines()
    except Exception as exc:
        raise RuntimeError(f"IG11_RENDER_BLOCKED: no se pudo resolver {query!r}") from exc
    if len(raw) < 3:
        raise RuntimeError(f"IG11_RENDER_BLOCKED: fontconfig no devolvió familia/estilo/ruta para {query!r}")
    family, style, path = raw[0].strip(), raw[1].strip(), raw[2].strip()
    if "inter" not in family.casefold() or not Path(path).exists():
        raise RuntimeError(
            f"IG11_RENDER_BLOCKED: se pidió {query!r}, pero fontconfig resolvió "
            f"{family!r} ({style!r}). No se permite fallback tipográfico silencioso."
        )
    if kind == "sans_bold" and not any(x in style.casefold() for x in ("bold", "semibold", "demibold")):
        raise RuntimeError(
            f"IG11_RENDER_BLOCKED: Inter está instalada, pero {query!r} resolvió el estilo {style!r}. "
            "Instala Inter Bold/SemiBold y repite el gate."
        )
    return path


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(kind), size=size)


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def draw_multiline_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_w: int = 900,
    size: int = 58,
    padding: int = 28,
    fill: tuple[int, int, int, int] = (17, 16, 15, 205),
    fg: str = TEXT,
    bold: bool = True,
) -> int:
    f = font("sans_bold" if bold else "sans", size)
    words = text.replace("\n", " \n ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        if word == "\n":
            lines.append(current.rstrip())
            current = ""
            continue
        trial = (current + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=f)[2] > max_w - 2 * padding and current:
            lines.append(current)
            current = word
        else:
            current = trial
    if current or not lines:
        lines.append(current)
    line_h = int(size * 1.22)
    height = padding * 2 + line_h * len(lines)
    draw.rounded_rectangle((x, y, x + max_w, y + height), radius=24, fill=fill)
    ty = y + padding - 2
    for line in lines:
        draw.text((x + padding, ty), line, font=f, fill=rgb(fg))
        ty += line_h
    return height


def label(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    fg: str = TEXT,
    bg: tuple[int, int, int, int] = (17, 16, 15, 205),
    size: int = 26,
) -> None:
    f = font("sans_bold", size)
    bbox = draw.textbbox((0, 0), text, font=f)
    width = bbox[2] - bbox[0] + 32
    height = bbox[3] - bbox[1] + 22
    draw.rounded_rectangle((x, y, x + width, y + height), radius=12, fill=bg)
    draw.text((x + 16, y + 9), text, font=f, fill=rgb(fg))


def create_object(kind: str, base: int, target: str | None = None) -> Image.Image:
    """Create the single modern object with local deterministic geometry."""
    size = max(80, base)
    if kind == "smartphone":
        tile = Image.new("RGBA", (int(size * .62), int(size * 1.05)), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        d.rounded_rectangle(
            (6, 6, tile.width - 6, tile.height - 6),
            radius=max(10, int(size * .07)),
            fill=(30, 31, 32, 255),
            outline=(5, 5, 5, 255),
            width=max(4, int(size * .025)),
        )
        # Neutral camera detail: enough to read as a phone, no branded lens layout.
        r = max(4, int(size * .025))
        cx, cy = int(tile.width * .22), int(tile.height * .12)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(12, 12, 12, 255))
        return tile
    if kind == "ereader":
        tile = Image.new("RGBA", (int(size * .70), int(size * .95)), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        d.rounded_rectangle(
            (4, 4, tile.width - 4, tile.height - 4),
            radius=max(6, int(size * .035)),
            fill=(45, 46, 47, 255),
            outline=(8, 8, 8, 255),
            width=max(4, int(size * .02)),
        )
        d.rectangle(
            (int(tile.width * .10), int(tile.height * .08), int(tile.width * .90), int(tile.height * .88)),
            fill=(205, 205, 199, 255),
        )
        for i, frac in enumerate((.23, .34, .45, .56, .67)):
            x2 = .78 if i % 2 else .84
            d.line(
                (tile.width * .18, tile.height * frac, tile.width * x2, tile.height * frac),
                fill=(105, 105, 100, 210),
                width=max(2, int(size * .012)),
            )
        return tile
    if kind == "earbuds_case":
        tile = Image.new("RGBA", (int(size * .85), int(size * .55)), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        d.rounded_rectangle(
            (4, 4, tile.width - 4, tile.height - 4),
            radius=int(tile.height * .42),
            fill=(224, 224, 218, 255),
            outline=(115, 115, 110, 255),
            width=max(3, int(size * .018)),
        )
        d.line(
            (tile.width * .12, tile.height * .46, tile.width * .88, tile.height * .46),
            fill=(150, 150, 145, 255),
            width=max(2, int(size * .012)),
        )
        return tile
    if kind == "qr":
        if not target:
            raise ValueError("QR overlay requires target")
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(target)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        return ImageOps.contain(image, (size, size), Image.Resampling.NEAREST)
    raise ValueError(f"Unknown overlay type: {kind}")


def paste_object(
    source: Image.Image,
    spec: dict[str, Any],
    *,
    reveal: bool = False,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    out = source.convert("RGBA").copy()
    multiplier = float(spec.get("reveal_scale", 1.0)) if reveal else 1.0
    base = int(
        min(source.width, source.height)
        * .115
        * float(spec.get("scale", 1.0))
        * multiplier
    )
    obj = create_object(spec["type"], base, spec.get("target"))
    degrees = float(spec.get("rotate", 0))
    if degrees:
        obj = obj.rotate(degrees, expand=True, resample=Image.Resampling.BICUBIC)
    cx = int(source.width * float(spec["x"]))
    cy = int(source.height * float(spec["y"]))
    left = cx - obj.width // 2
    top = cy - obj.height // 2
    out.alpha_composite(obj, (left, top))
    return out, (left, top, left + obj.width, top + obj.height)


def contain_on_canvas(im: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", (W, H), rgb(BG))
    fitted = ImageOps.contain(im.convert("RGB"), (W, H), Image.Resampling.LANCZOS)
    canvas.paste(fitted, ((W - fitted.width) // 2, (H - fitted.height) // 2))
    return canvas


def contain_in_region(
    im: Image.Image,
    left: int = 55,
    top: int = 190,
    right: int = 1025,
    bottom: int = 1000,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Place an untouched image inside a reserved rectangle with no overlays."""
    if right <= left or bottom <= top:
        raise ValueError("Invalid image region")
    canvas = Image.new("RGB", (W, H), rgb(BG))
    fitted = ImageOps.contain(
        im.convert("RGB"),
        (right - left, bottom - top),
        Image.Resampling.LANCZOS,
    )
    x = left + (right - left - fitted.width) // 2
    y = top + (bottom - top - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas, (x, y, x + fitted.width, y + fitted.height)


def crop_focus(
    im: Image.Image,
    focus_x: float,
    focus_y: float,
    zoom: float,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    sw, sh = im.size
    target_ratio = W / H
    crop_h = sh / max(1.0, zoom)
    crop_w = crop_h * target_ratio
    if crop_w > sw:
        crop_w = sw / max(1.0, zoom)
        crop_h = crop_w / target_ratio
    cx, cy = sw * focus_x, sh * focus_y
    left = max(0, min(sw - crop_w, cx - crop_w / 2))
    top = max(0, min(sh - crop_h, cy - crop_h / 2))
    box = (int(left), int(top), int(left + crop_w), int(top + crop_h))
    cropped = im.crop(box).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    return cropped, box


def transform_bbox(
    bbox: tuple[int, int, int, int],
    crop: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    left, top, right, bottom = crop
    cw, ch = right - left, bottom - top
    return (
        int((bbox[0] - left) / cw * W),
        int((bbox[1] - top) / ch * H),
        int((bbox[2] - left) / cw * W),
        int((bbox[3] - top) / ch * H),
    )


def add_common_header(canvas: Image.Image, ep_index: int, montage: bool = True) -> ImageDraw.ImageDraw:
    d = ImageDraw.Draw(canvas, "RGBA")
    label(d, f"ARCHIVO IMPOSIBLE · {ep_index}/4", 55, 45, size=25)
    label(
        d,
        "MONTAJE · HAY UN ANACRONISMO" if montage else "ORIGINAL · LIBRARY OF CONGRESS",
        55,
        102,
        fg=ACCENT if montage else TEXT,
        size=22,
    )
    return d


def save_slide1(original: Image.Image, ep: dict[str, Any], ep_index: int, target: Path) -> None:
    modified, _ = paste_object(original, ep["overlay"], reveal=False)
    canvas = contain_on_canvas(modified)
    d = add_common_header(canvas, ep_index, True)
    draw_multiline_box(d, ep["slide1"], 65, 190, max_w=900, size=54)
    canvas.save(target, "PNG", optimize=True)


def save_hint(
    original: Image.Image,
    ep: dict[str, Any],
    ep_index: int,
    target: Path,
    reveal: bool = False,
) -> None:
    modified, bbox = paste_object(original, ep["overlay"], reveal=reveal)
    focus = ep["focus"]
    canvas, crop = crop_focus(
        modified,
        float(focus["x"]),
        float(focus["y"]),
        float(focus["zoom"]),
    )
    d = add_common_header(canvas, ep_index, True)
    text = ep["reveal"] if reveal else ep["hint"]
    draw_multiline_box(d, text, 65, 190, max_w=900, size=48 if reveal else 52)
    if reveal:
        x1, y1, x2, y2 = transform_bbox(bbox, crop)
        pad = 24
        d.rounded_rectangle(
            (x1 - pad, y1 - pad, x2 + pad, y2 + pad),
            radius=30,
            outline=rgb(ACCENT),
            width=12,
        )
    canvas.save(target, "PNG", optimize=True)


def save_original(original: Image.Image, ep: dict[str, Any], ep_index: int, target: Path) -> None:
    # The historical image itself occupies only this reserved region.
    canvas, image_box = contain_in_region(original)
    d = add_common_header(canvas, ep_index, False)

    credit = ep["original_credit"]
    if ep.get("original_note"):
        credit += "\n" + ep["original_note"]
    draw_multiline_box(
        d,
        credit,
        55,
        1025,
        max_w=970,
        size=25,
        padding=18,
        fill=(17, 16, 15, 255),
        bold=False,
    )

    # Hard invariant: all UI/credits are outside the source-image rectangle.
    if image_box[1] < 190 or image_box[3] > 1000:
        raise RuntimeError("Original image escaped its reserved region")
    canvas.save(target, "PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    rendered: list[str] = []

    # Resolve fonts before touching outputs so a bad environment fails early.
    font_path("sans")
    font_path("sans_bold")

    for index, ep in enumerate(manifest["episodes"], 1):
        src = args.assets / ep["asset_filename"]
        meta = args.assets / ep["metadata_filename"]
        if not src.exists() or not meta.exists():
            raise SystemExit(
                f"Missing source or metadata for {ep['id']}. "
                "Run fetch_loc_assets.py first."
            )
        original = Image.open(src).convert("RGB")
        epdir = args.out / ep["id"]
        epdir.mkdir(parents=True, exist_ok=True)
        outputs = [epdir / f"{ep['id']}_s{n}.png" for n in range(1, 5)]

        save_slide1(original, ep, index, outputs[0])
        save_hint(original, ep, index, outputs[1], False)
        save_hint(original, ep, index, outputs[2], True)
        save_original(original, ep, index, outputs[3])
        rendered.extend(map(str, outputs))

    (args.out / "ig11_render_manifest.json").write_text(
        json.dumps(
            {"source": manifest["id"], "outputs": rendered},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Rendered {len(rendered)} slides")


if __name__ == "__main__":
    main()
