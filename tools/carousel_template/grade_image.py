#!/usr/bin/env python3
"""Grade and crop a real photo for the canonical 1080x1350 Instagram carousel.

Usage:
  python tools/carousel_template/grade_image.py input.jpg output.jpg [crop_top_bias]

crop_top_bias: 0.0=top, 0.5=center, 1.0=bottom. Default 0.5.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps

SIZE = (1080, 1350)
TERRACOTTA = (180, 110, 60)


def grade(src: Path, dst: Path, bias: float) -> None:
    if not src.exists():
        raise SystemExit(f"ERROR: no existe {src}")
    bias = min(1.0, max(0.0, bias))
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im = ImageOps.fit(im, SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, bias))
        im = ImageEnhance.Color(im).enhance(0.78)
        im = ImageEnhance.Contrast(im).enhance(1.15)
        im = ImageEnhance.Brightness(im).enhance(0.80)
        tint = Image.new("RGB", SIZE, TERRACOTTA)
        im = Image.blend(im, tint, 0.16)
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, quality=94, optimize=True, subsampling=0)
    print(f"OK {dst} 1080x1350 bias={bias:.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("crop_top_bias", nargs="?", type=float, default=0.5)
    args = ap.parse_args()
    grade(Path(args.input), Path(args.output), args.crop_top_bias)


if __name__ == "__main__":
    main()
