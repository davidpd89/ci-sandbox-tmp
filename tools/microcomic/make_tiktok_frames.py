#!/usr/bin/env python3
"""Convierte los 5 PNG de IG-08 a TikTok 1080×1920 sin recortar ni estirar.

Requiere el manifest generado por render_microcomic.py en el mismo directorio.
No publica ni programa.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

SOURCE_W = 1080
SOURCE_H = 1350
TARGET_W = 1080
TARGET_H = 1920
BACKGROUND = (246, 240, 230)  # #F6F0E6
EXPECTED_CHARACTER = "LECTOR_A_v1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_source_manifest(input_dir: Path) -> tuple[Path, dict]:
    manifests = sorted(input_dir.glob("ig08_*_manifest.json"))
    if len(manifests) != 1:
        raise SystemExit(
            f"TT04_CONVERT_BLOCKED: expected exactly 1 IG-08 manifest in {input_dir}, found {len(manifests)}"
        )
    path = manifests[0]
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("character_version") != EXPECTED_CHARACTER:
        raise SystemExit(
            f"TT04_CONVERT_BLOCKED: character_version={data.get('character_version')!r}; expected {EXPECTED_CHARACTER!r}"
        )
    if not data.get("character_sha256"):
        raise SystemExit("TT04_CONVERT_BLOCKED: source manifest has no character_sha256")
    if data.get("slide5_fit") != "contain":
        raise SystemExit("TT04_CONVERT_BLOCKED: source IG-08 slide 5 was not rendered with contain")
    if data.get("status") != "RENDERED_NOT_SCHEDULED":
        raise SystemExit("TT04_CONVERT_BLOCKED: unexpected source production status")
    return path, data


def ordered_sources(input_dir: Path, manifest: dict) -> list[Path]:
    declared = manifest.get("outputs") or []
    if len(declared) != 5:
        raise SystemExit(f"TT04_CONVERT_BLOCKED: source manifest declares {len(declared)} outputs, expected 5")
    paths = [input_dir / Path(value).name for value in declared]
    if any(not path.exists() for path in paths):
        missing = [str(path) for path in paths if not path.exists()]
        raise SystemExit("TT04_CONVERT_BLOCKED: missing source PNGs: " + ", ".join(missing))
    if len({path.name for path in paths}) != 5:
        raise SystemExit("TT04_CONVERT_BLOCKED: duplicate source PNG names in manifest")
    expected_suffixes = ["_slide_1.png", "_slide_2.png", "_slide_3.png", "_slide_4.png", "_slide_5_full.png"]
    if not all(path.name.endswith(suffix) for path, suffix in zip(paths, expected_suffixes)):
        raise SystemExit(
            "TT04_CONVERT_BLOCKED: source manifest order must be slide 1 → 2 → 3 → 4 → slide 5 full"
        )
    return paths


def convert(src: Path, dst: Path) -> dict:
    with Image.open(src) as opened:
        if opened.size != (SOURCE_W, SOURCE_H):
            raise SystemExit(
                f"TT04_CONVERT_BLOCKED: {src.name} has {opened.size}; expected {(SOURCE_W, SOURCE_H)}"
            )
        im = opened.convert("RGB")

    # 1080×1350 entra íntegro en 1080×1920: no se escala ni se recorta.
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), BACKGROUND)
    x = (TARGET_W - SOURCE_W) // 2
    y = (TARGET_H - SOURCE_H) // 2  # 285 px arriba y abajo
    canvas.paste(im, (x, y))
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst, "PNG", optimize=True)

    with Image.open(dst) as check:
        if check.size != (TARGET_W, TARGET_H):
            raise SystemExit(f"TT04_CONVERT_BLOCKED: output {dst.name} has wrong size {check.size}")
    return {
        "source": src.name,
        "source_sha256": sha256(src),
        "output": dst.name,
        "output_sha256": sha256(dst),
        "source_size": [SOURCE_W, SOURCE_H],
        "output_size": [TARGET_W, TARGET_H],
        "offset": [x, y],
        "background": "#F6F0E6",
        "cropped": False,
        "stretched": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    manifest_path, source_manifest = load_source_manifest(args.input_dir)
    files = ordered_sources(args.input_dir, source_manifest)
    args.out.mkdir(parents=True, exist_ok=True)

    frames = []
    for idx, src in enumerate(files, 1):
        dst = args.out / f"tt_frame_{idx}.png"
        frames.append(convert(src, dst))
        print(dst)

    output_manifest = {
        "id": source_manifest.get("scene") or manifest_path.stem,
        "source_manifest": manifest_path.name,
        "source_manifest_sha256": sha256(manifest_path),
        "character_version": source_manifest["character_version"],
        "character_sha256": source_manifest["character_sha256"],
        "reference_url": source_manifest.get("reference_url"),
        "source_license": source_manifest.get("source_license"),
        "order": "panel 1 → panel 2 → panel 3 → panel 4 → tira completa",
        "frames": frames,
        "status": "RENDERED_NOT_SCHEDULED",
    }
    out_manifest = args.out / "tt04_manifest.json"
    out_manifest.write_text(json.dumps(output_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_manifest)


if __name__ == "__main__":
    main()
