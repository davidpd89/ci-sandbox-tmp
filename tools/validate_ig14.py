#!/usr/bin/env python3
"""Regresiones críticas de IG-14 — Libros que no existen."""
from __future__ import annotations

import json
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools" / "fake_books"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR IG-14: {message}")


def main() -> None:
    required = [
        BASE / "README.md",
        BASE / "ig14_manifest.json",
        BASE / "ig14_social_copy.json",
        BASE / "render_fake_books.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        fail("faltan archivos: " + ", ".join(missing))
    try:
        py_compile.compile(str(BASE / "render_fake_books.py"), doraise=True)
    except py_compile.PyCompileError as exc:
        fail(f"renderer no compila: {exc.msg}")

    data = json.loads((BASE / "ig14_manifest.json").read_text(encoding="utf-8"))
    social = json.loads((BASE / "ig14_social_copy.json").read_text(encoding="utf-8"))

    if data.get("id") != "IG-14_LIBROS_QUE_NO_EXISTEN_v1":
        fail("id de serie desincronizado")
    if social.get("series_id") != data.get("id"):
        fail("sidecar social no corresponde al manifest visual")
    if social.get("status") != "COPY_READY_NOT_SCHEDULED":
        fail("sidecar social debe seguir no programado")
    if data.get("canvas") != [1080, 1350]:
        fail("canvas debe seguir siendo 1080×1350")
    if data.get("disclosure_cover") != "EDICIÓN IMAGINARIA":
        fail("slide 1 debe conservar EDICIÓN IMAGINARIA")
    if data.get("disclosure_back") != "NO EXISTE. DE MOMENTO.":
        fail("slide 2 debe conservar NO EXISTE. DE MOMENTO.")
<<<<<<< HEAD
    if data.get("brand_line") != "ARCHIVO DE PROBLEMAS DE LECTORES · AUTORA DEMO DÍAZ":
=======
    if data.get("brand_line") != "ARCHIVO DE PROBLEMAS DE LECTORES · DAVID PORTO DÍAZ":
>>>>>>> origin/research/public-reuse-parent
        fail("brand_line desincronizada")

    episodes = data.get("episodes") or []
    social_items = social.get("items") or []
    expected_ids = [f"ig14_{n:02d}" for n in range(1, 7)]
    if [ep.get("id") for ep in episodes] != expected_ids:
        fail("deben existir exactamente ig14_01…ig14_06 en orden")
    if [item.get("id") for item in social_items] != expected_ids:
        fail("copy social debe contener exactamente ig14_01…ig14_06 en el mismo orden")

    expected_symbols = ["bookmark_corner", "character_map", "suitcase_books", "redacted_blurb", "thin_pages", "book_bag"]
    expected_palettes = ["F", "B", "D", "C", "E", "A"]
    if [ep.get("symbol") for ep in episodes] != expected_symbols:
        fail("inventario/orden de símbolos ha cambiado")
    if [ep.get("palette") for ep in episodes] != expected_palettes:
        fail("orden de paletas ha cambiado")

    forbidden = ("ISBN", "editorial ficticia", "precio", "★★★★★", "compra ya")
    blob = json.dumps(data, ensure_ascii=False).casefold()
    for marker in forbidden:
        if marker.casefold() in blob:
            fail(f"manifest recuperó elemento que puede fingir un libro real: {marker!r}")
    for ep in episodes:
        if not ep.get("title") or not ep.get("subtitle") or not ep.get("back"):
            fail(f"{ep['id']}: falta título/subtítulo/contraportada")
        if len(ep.get("includes") or []) != 3:
            fail(f"{ep['id']}: debe contener exactamente tres elementos INCLUYE")

    expected_captions = [
        "El género de terror tiene subcategorías muy específicas.",
        "La nota en el móvil termina en «(?)». Ahí empieza la documentación.",
        "Tres días fuera requieren, por prudencia, unas mil doscientas páginas.",
        "Una contraportada también puede saber cuándo callarse.",
        "Doce páginas son suficientes para posponerlas cuarenta minutos.",
        "Mirar es gratis. La logística posterior no siempre.",
    ]
    if [x.get("caption") for x in social_items] != expected_captions:
        fail("captions sociales desincronizados respecto al kit auditado")
    for item in social_items:
        if len(item.get("hashtags") or []) != 4:
            fail(f"{item['id']}: debe mantener exactamente cuatro hashtags")
        if item.get("first_comment") is not None:
            fail(f"{item['id']}: no debe añadir comentario fijado por rutina")
        caption = item.get("caption", "")
        if caption.rstrip().endswith("?"):
            fail(f"{item['id']}: caption no debe recuperar pregunta automática")
        for marker in ("Etiqueta a", "Dale like", "Si sabes, sabes", "A todos nos ha pasado"):
            if marker.casefold() in caption.casefold():
                fail(f"{item['id']}: reapareció fórmula genérica {marker!r}")

    renderer = (BASE / "render_fake_books.py").read_text(encoding="utf-8")
    markers = (
        "IG14_RENDER_BLOCKED", "Playfair Display:style=ExtraBold", "Inter:style=SemiBold", "Inter:style=Medium",
        "%{family}\\n%{style}\\n%{file}", "expected_styles", "fit_font", "no cabe ni a",
        "RENDERED_NOT_SCHEDULED", "font_policy", "1080", "1350"
    )
    for marker in markers:
        if marker not in renderer:
            fail(f"renderer perdió guardia {marker!r}")
    for bad in ("Georgia", "Arial", "DejaVu", "Liberation"):
        if bad in renderer:
            fail(f"renderer recuperó fallback prohibido {bad!r}")

    readme = (BASE / "README.md").read_text(encoding="utf-8")
    for marker in (
        "Playfair Display ExtraBold = peso 800", "Inter SemiBold = peso 600", "Inter Medium = peso 500",
        "IG14_RENDER_BLOCKED", "RENDERED_NOT_SCHEDULED", "EDICIÓN IMAGINARIA", "NO EXISTE. DE MOMENTO.",
        "ig14_social_copy.json", "first_comment", "no programar"
    ):
        if marker.casefold() not in readme.casefold():
            fail(f"README perdió regla {marker!r}")

    print("OK: IG-14 conserva disclosures, seis episodios, copy social, pesos auditados y estado no programado.")


if __name__ == "__main__":
    main()
