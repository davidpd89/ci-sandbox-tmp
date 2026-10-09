#!/usr/bin/env python3
"""Regresiones críticas del pipeline IG-02."""
from __future__ import annotations

import json
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools" / "writing_carousel"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR IG-02: {message}")


def main() -> None:
    required = [
        BASE / "README.md",
        BASE / "ig02_manifest.json",
        BASE / "fetch_references.py",
        BASE / "render_writing_carousel.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        fail("faltan archivos: " + ", ".join(missing))

    for path in (BASE / "fetch_references.py", BASE / "render_writing_carousel.py"):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            fail(f"Python no compila {path.name}: {exc.msg}")

    try:
        data = json.loads((BASE / "ig02_manifest.json").read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"manifest JSON inválido: {exc}")

    posts = data.get("posts") or []
    ids = [p.get("id") for p in posts]
    expected_ids = [f"ig02_{n:02d}" for n in range(1, 7)]
    if ids != expected_ids:
        fail(f"IDs/orden inesperados: {ids}")
    expected_counts = [9, 8, 7, 8, 8, 8]
    if [len(p.get("slides") or []) for p in posts] != expected_counts:
        fail("recuento de slides distinto del documento auditado")
    if data.get("gate_items") != ["ig02_01", "ig02_02"]:
        fail("gate debe seguir siendo IG-02-01 + IG-02-02")
    if "no programar" not in data.get("schedule_rule", "").casefold():
        fail("schedule_rule debe bloquear programación sin autorización")

    for post in posts:
        if not str(post.get("reference_url", "")).startswith("https://www.pexels.com/photo/"):
            fail(f"{post['id']}: referencia principal no es Pexels exacta")
        if len(post.get("hashtags") or []) != 4:
            fail(f"{post['id']}: debe conservar 4 hashtags")
        if not post.get("caption") or not post.get("asset"):
            fail(f"{post['id']}: falta caption o asset")
        slides = post["slides"]
        finals = [s for s in slides if s.get("kind") == "final"]
        if len(finals) != 1 or slides[-1].get("kind") != "final":
            fail(f"{post['id']}: debe tener una única slide final y ser la última")
        if not str(finals[0].get("cta", "")).startswith("GUARDA"):
            fail(f"{post['id']}: CTA final debe ser solo la acción guardar")
        for slide in slides[:-1]:
            if slide.get("cta"):
                fail(f"{post['id']}: CTA inesperada antes de la última slide")
            if not slide.get("title"):
                fail(f"{post['id']}: slide sin título")
        if any(marker in json.dumps(post, ensure_ascii=False).upper() for marker in ("[ENLACE]", "[TODO]", "[TBD]")):
            fail(f"{post['id']}: placeholder pendiente")

    renderer = (BASE / "render_writing_carousel.py").read_text(encoding="utf-8")
    for marker in ("IG02_RENDER_BLOCKED", "Playfair+Display:wght@700", "Inter:wght@500;600;700", "RENDERED_NOT_SCHEDULED"):
        if marker not in renderer:
            fail(f"renderer perdió guardia {marker!r}")
    if "LIKE" in renderer or "COMENTA" in renderer or "SIGUE" in renderer:
        fail("renderer ha recuperado CTAs adicionales")

    readme = (BASE / "README.md").read_text(encoding="utf-8")
    for marker in ("IG02_RENDER_BLOCKED", "no programar", "una referencia Pexels exacta por carrusel"):
        if marker.casefold() not in readme.casefold():
            fail(f"README perdió regla {marker!r}")

    print("OK: IG-02 íntegro, ejecutable y sin decisiones abiertas de imagen/CTA/programación.")


if __name__ == "__main__":
    main()
