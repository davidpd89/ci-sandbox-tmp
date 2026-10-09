from __future__ import annotations

import argparse
import re
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def has_contract(text: str, name: str) -> bool:
    return bool(re.search(rf"(^|\n){re.escape(name)}\s*:", text))


def text_without_internal_notes(text: str) -> str:
    ignored_prefixes = (
        "canva_nota:",
        "nota_pausa:",
        "motivo:",
    )
    return "\n".join(
        line for line in text.splitlines()
        if not line.strip().lower().startswith(ignored_prefixes)
    )


def validate_file(path: Path) -> tuple[str, list[str], list[str]]:
    text = read(path)
    public_text = text_without_internal_notes(text)
    errors: list[str] = []
    warnings: list[str] = []

    if not has_contract(text, "PIEZA") and not has_contract(text, "id"):
        warnings.append("missing PIEZA")
    if "lista_para_programar" in text and "QA_RESULT:" not in text:
        errors.append("lista_para_programar without QA_RESULT")
    if "QA_RESULT:" in text and "status: pass" not in text and "status: fail" not in text:
        warnings.append("QA_RESULT without explicit status")
    is_video = any(token in text.lower() for token in ["reel", "short", "video", "tiktok"])
    if is_video and "video_provider_decision:" not in text and "proveedor_video:" not in text:
        warnings.append("video-like piece without video_provider_decision")
    if is_video and "MONTAGE_PRESET:" not in text and "montaje_preset:" not in text:
        errors.append("video-like piece without MONTAGE_PRESET")
    if "asset_origen:" in text and "fuente_real:" not in text:
        errors.append("asset_origen without fuente_real")
    if any(cliche in public_text.lower() for cliche in ["no es solo", "descubre", "adentrate", "una historia que"]):
        errors.append("AI/copywriting cliche detected")
    return str(path), errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RRSS content contracts")
    parser.add_argument("paths", nargs="+", help="files or directories to validate")
    args = parser.parse_args()

    files: list[Path] = []
    for raw in args.paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.suffix.lower() in {".md", ".yaml", ".yml", ".json"})
        else:
            files.append(path)

    any_errors = False
    for file in files:
        name, errors, warnings = validate_file(file)
        status = "FAIL" if errors else "PASS"
        any_errors = any_errors or bool(errors)
        print(f"[{status}] {name}")
        for err in errors:
            print(f"  error: {err}")
        for warn in warnings:
            print(f"  warn: {warn}")
    return 1 if any_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
