#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1920
DURATIONS = [2.8, 4.7, 5.5, 6.0, 6.5, 4.5]
TRANSITION = 0.20
CREAM = (247, 241, 232)
ACCENT = (196, 120, 63)
MUTED = (210, 200, 188)


def require_font(query: str, expected_family: str) -> str:
    if not shutil.which("fc-match"):
        raise RuntimeError(
            "FB-02 bloqueado: no existe fc-match. Instala fontconfig y las fuentes auditadas "
            "Playfair Display e Inter antes de renderizar."
        )
    try:
        raw = subprocess.check_output(
            ["fc-match", "-f", "%{family}\n%{file}", query], text=True
        ).strip().splitlines()
    except Exception as exc:
        raise RuntimeError(f"FB-02 bloqueado: no se pudo resolver la fuente {query!r}") from exc

    if len(raw) < 2:
        raise RuntimeError(f"FB-02 bloqueado: fc-match no devolvió familia/ruta para {query!r}")

    family = raw[0].casefold()
    path = raw[1].strip()
    if expected_family.casefold() not in family or not Path(path).exists():
        raise RuntimeError(
            f"FB-02 bloqueado: se pidió {query!r}, pero fontconfig resolvió {raw[0]!r}. "
            "No se permite fallback tipográfico silencioso; instala la familia auditada y repite el gate."
        )
    return path


SERIF = require_font("Playfair Display:style=Bold", "Playfair Display")
SANS = require_font("Inter:style=Regular", "Inter")
SANS_B = require_font("Inter:style=Bold", "Inter")


def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = word if not current else current + " " + word
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    path: str,
    start: int,
    min_size: int,
    max_width: int,
    max_lines: int,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(start, min_size - 1, -2):
        font = ImageFont.truetype(path, size)
        lines = wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    font = ImageFont.truetype(path, min_size)
    return font, wrap(draw, text, font, max_width)


def contained_source(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    source = ImageOps.contain(image.convert("RGB"), size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (26, 22, 20))
    x = (size[0] - source.width) // 2
    y = (size[1] - source.height) // 2
    canvas.paste(source, (x, y))
    return canvas


def make_card(asset: Image.Image, text: str, index: int, out: Path) -> None:
    # El activo real es la base. El fondo es solo una ampliación desenfocada del mismo archivo.
    base = ImageOps.fit(asset.convert("RGB"), (W, H), method=Image.Resampling.LANCZOS)
    base = base.filter(ImageFilter.GaussianBlur(18))
    base = ImageEnhance.Brightness(base).enhance(0.34)
    draw = ImageDraw.Draw(base, "RGBA")

    source_h = 1060 if index == 0 else 1010
    source_top = 145
    source = contained_source(asset, (900, source_h))
    base.paste(source, (90, source_top))
    draw.rounded_rectangle(
        (88, source_top - 2, 992, source_top + source_h + 2),
        radius=20,
        outline=(247, 241, 232, 75),
        width=2,
    )

    panel_top = 1260 if index < 5 else 1285
    draw.rounded_rectangle(
        (70, panel_top, 1010, 1740), radius=28, fill=(15, 12, 11, 220)
    )
    draw.rectangle((106, panel_top + 48, 220, panel_top + 54), fill=ACCENT + (255,))

    path = SERIF if index == 0 else SANS_B
    start = 88 if index == 0 else 52
    min_size = 56 if index == 0 else 36
    font, lines = fit_font(
        draw, text, path, start, min_size, 828, 5 if index == 0 else 6
    )
    line_h = int(font.size * 1.22)
    total_h = line_h * len(lines)
    y = panel_top + (95 if index < 5 else 90)
    if y + total_h > 1700:
        y = max(panel_top + 75, 1700 - total_h)

    for line in lines:
        draw.text((126, y), line, font=font, fill=CREAM)
        y += line_h

    small = ImageFont.truetype(SANS, 28)
    label = "HISTORIA DEL LIBRO" if index < 5 else "FUENTE · LICENCIA"
    draw.text((126, 1774), label, font=small, fill=MUTED)
    draw.text((870, 1774), f"{index + 1}/6", font=small, fill=MUTED)

    out.parent.mkdir(parents=True, exist_ok=True)
    base.save(out, quality=94)


def render_video(cards: list[Path], out_file: Path, ffmpeg: str = "ffmpeg") -> None:
    if not shutil.which(ffmpeg):
        raise RuntimeError("ffmpeg no está disponible en PATH")

    with tempfile.TemporaryDirectory(prefix="fb02_") as tmp:
        tmpdir = Path(tmp)
        segments: list[Path] = []

        for i, (card, duration) in enumerate(zip(cards, DURATIONS)):
            segment = tmpdir / f"seg_{i}.mp4"
            segments.append(segment)
            vf = (
                "scale=1080:1920,"
                "zoompan=z='min(zoom+0.00008,1.015)':"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                "d=1:s=1080x1920:fps=30,format=yuv420p"
            )
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-framerate",
                    "30",
                    "-i",
                    str(card),
                    "-t",
                    str(duration),
                    "-vf",
                    vf,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    str(segment),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        command = [ffmpeg, "-y"]
        for segment in segments:
            command += ["-i", str(segment)]

        filters: list[str] = []
        previous = "0:v"
        offset = DURATIONS[0] - TRANSITION
        for i in range(1, len(segments)):
            out_label = f"x{i}"
            filters.append(
                f"[{previous}][{i}:v]xfade=transition=fade:"
                f"duration={TRANSITION}:offset={offset:.3f}[{out_label}]"
            )
            previous = out_label
            offset += DURATIONS[i] - TRANSITION

        command += [
            "-filter_complex",
            ";".join(filters),
            "-map",
            f"[{previous}]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out_file),
        ]
        subprocess.run(command, check=True)


def render_item(
    item: dict, assets: Path, out_root: Path, no_video: bool = False
) -> None:
    asset_path = assets / item["asset_file"]
    if not asset_path.exists():
        raise FileNotFoundError(
            f"Falta {asset_path}. Fuente exacta: {item['source_url']}"
        )

    asset = Image.open(asset_path)
    folder = out_root / item["id"]
    folder.mkdir(parents=True, exist_ok=True)

    cards: list[Path] = []
    for i, text in enumerate(item["blocks"]):
        card = folder / f"{i + 1:02d}.png"
        make_card(asset, text, i, card)
        cards.append(card)

    (folder / "metadata.json").write_text(
        json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not no_video:
        render_video(cards, folder / "reel.mp4")
    print(f"OK {item['id']} -> {folder}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--assets", type=Path, default=Path("build/fb02/assets"))
    parser.add_argument("--out", type=Path, default=Path("build/fb02"))
    parser.add_argument("--item", help="Ej. fb02_01; omitir para todos")
    parser.add_argument("--no-video", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    items = data["items"]
    if args.item:
        items = [x for x in items if x["id"] == args.item]
        if not items:
            raise SystemExit(f"No existe item {args.item}")

    for item in items:
        render_item(item, args.assets, args.out, args.no_video)


if __name__ == "__main__":
    main()
