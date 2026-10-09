#!/usr/bin/env python3
"""Exporta un post IG-01 renderizado a la carpeta revisable de nuevas ideas."""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SYSTEM_DIR = ROOT / "nuevas ideas rrss" / "02 — Instagram" / "IG-01 — SISTEMA carruseles BookTok verificables"
OUT_ROOT = SYSTEM_DIR / "01_PUBLICACIONES"
QA_DIR = SYSTEM_DIR / "05_QA"


def slug_title(text: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in " -_" else " " for ch in text)
    return " ".join(clean.split())[:80].strip()


def contact_sheet(paths: list[Path], out: Path) -> None:
    thumb_w, thumb_h = 360, 450
    cols = 3
    rows = math.ceil(len(paths) / cols)
    sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (18, 18, 18))
    for index, path in enumerate(paths):
        img = Image.open(path).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(img, ((index % cols) * thumb_w, (index // cols) * thumb_h))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=92)


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--build", type=Path, default=Path("build/ig01"))
    parser.add_argument("--assets", type=Path, default=Path("build/ig01/assets"))
    parser.add_argument("--post", required=True)
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    post = next((item for item in data["posts"] if item["id"] == args.post), None)
    if not post:
        raise SystemExit(f"ERROR: no existe {args.post}")

    post_build = args.build / args.post
    if not post_build.exists():
        raise SystemExit(f"ERROR: no existe render: {post_build}")

    number = args.post.replace("ig01_", "IG-01-")
    first_title = post["slides"][0].get("title", args.post)
    folder_name = post.get("review_slug") or f"{number} - {slug_title(first_title)}"
    review_dir = OUT_ROOT / folder_name
    output_dir = review_dir / "04_OUTPUT"
    source_dir = review_dir / "01_FUENTES"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    pngs = sorted(post_build.glob("*.png"))
    for png in pngs:
        shutil.copy2(png, output_dir / png.name)

    copy_if_exists(post_build / "metadata.json", output_dir / "metadata.json")
    contact_sheet(pngs, output_dir / "contact_sheet.jpg")
    shutil.copy2(output_dir / "contact_sheet.jpg", QA_DIR / f"{number}_contact_sheet.jpg")

    used_covers = set()
    used_backgrounds = set()
    for slide in post["slides"]:
        if slide.get("cover"):
            used_covers.add(slide["cover"])
        used_covers.update(slide.get("covers", []))
        if slide.get("background"):
            used_backgrounds.add(slide["background"])
    if data.get("default_soft_background_cycle"):
        used_backgrounds.update(data["default_soft_background_cycle"])

    for slug in sorted(used_covers):
        spec = data["covers"][slug]
        copy_if_exists(args.assets / spec["asset"], source_dir / spec["asset"])
        copy_if_exists(args.assets / f"{slug}.source.json", source_dir / f"{slug}.source.json")

    for key in sorted(used_backgrounds):
        spec = data["soft_backgrounds"][key]
        copy_if_exists(args.assets / spec["asset"], source_dir / spec["asset"])
        copy_if_exists(args.assets / f"background_{key}.source.json", source_dir / f"background_{key}.source.json")

    caption = post["caption"] + "\n\n" + " ".join(post["hashtags"]) + "\n"
    (review_dir / "caption.txt").write_text(caption, encoding="utf-8")
    (review_dir / "README.md").write_text(
        f"# {number} - {first_title}\n\n"
        "Salida revisable generada con `tools/booktok_carousel`.\n\n"
        "- `04_OUTPUT/`: PNG finales y contacto.\n"
        "- `01_FUENTES/`: portadas/fondos usados y sidecars de trazabilidad.\n"
        "- `caption.txt`: caption y hashtags exactos del manifest.\n",
        encoding="utf-8",
    )

    print(f"OK export -> {review_dir}")
    print(f"QA -> {QA_DIR / (number + '_contact_sheet.jpg')}")


if __name__ == "__main__":
    main()
