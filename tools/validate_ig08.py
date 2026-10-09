#!/usr/bin/env python3
"""Regresiones críticas del piloto IG-08 / base TT-04."""
from __future__ import annotations

import json
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools" / "microcomic"
SCENES = BASE / "scenes"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR IG-08: {message}")


def main() -> None:
    required = [
        BASE / "README.md",
        BASE / "character_lector_a_v1.json",
        BASE / "check_fonts.py",
        BASE / "render_microcomic.py",
        BASE / "make_tiktok_frames.py",
    ] + [SCENES / f"ig08_{n:02d}.json" for n in range(1, 7)]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        fail("faltan archivos: " + ", ".join(missing))

    for path in (BASE / "check_fonts.py", BASE / "render_microcomic.py", BASE / "make_tiktok_frames.py"):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            fail(f"Python no compila {path.name}: {exc.msg}")

    character = json.loads((BASE / "character_lector_a_v1.json").read_text(encoding="utf-8"))
    if character.get("id") != "LECTOR_A_v1" or character.get("wardrobe_locked") is not True:
        fail("biblia debe seguir siendo LECTOR_A_v1 con wardrobe_locked=true")

    palette = character.get("palette") or {}
    expected_palette = {
        "line": "#241D18",
        "skin": "#D4A077",
        "hair": "#2C211B",
        "sweatshirt": "#E7DDCA",
        "trousers": "#32302F",
        "socks": "#F4F0E9",
        "accent": "#C27937",
        "background": "#F6F0E6",
        "background_secondary": "#CBD3D7",
    }
    if palette != expected_palette:
        fail("paleta de LECTOR_A_v1 ha cambiado")

    geometry = character.get("geometry") or {}
    expected_geometry = {
        "stroke_px": 12,
        "head_width_px": 132,
        "head_height_px": 144,
        "normal_eye_diameter_px": 12,
        "alarm_eye_diameter_px": 16,
        "mouth_min_px": 28,
        "mouth_max_px": 44,
        "torso_width_px": 250,
        "torso_height_px": 300,
        "limb_stroke_px": 36,
        "book_width_px": 130,
        "book_height_px": 200,
    }
    for key, value in expected_geometry.items():
        if geometry.get(key) != value:
            fail(f"geometría LECTOR_A_v1 cambió en {key}: {geometry.get(key)!r}")

    allowed = set(character.get("expressions") or [])
    expected_expressions = {"neutral", "cansado", "alarma", "sospecha", "contento", "resignado"}
    if allowed != expected_expressions:
        fail(f"lista de expresiones cambió: {sorted(allowed)}")

    expected_captions = {
        "ig08_01": "02:31. El despertador de mañana no participa en esta negociación.",
        "ig08_02": "La pila tenía ocho. Ahora tiene nueve. Matemáticamente, esto va mal.",
        "ig08_03": "Se entrega con confianza. Se recupera con inspección de daños.",
        "ig08_04": "La sinopsis podía haberse detenido tres líneas antes.",
        "ig08_05": "Arkhadion: apuntado. Varek: página 4. Aún no ha empezado la batalla.",
        "ig08_06": "Quedan doce páginas y de repente preparar té parece una tarea urgente.",
    }
    expected_hashtags = {
        "ig08_01": ["#Bookstagram", "#HumorLector", "#LibrosEnEspañol", "#Lectores"],
        "ig08_02": ["#Bookstagram", "#TBR", "#HumorLector", "#LibrosEnEspañol"],
        "ig08_03": ["#Bookstagram", "#HumorLector", "#PrestarLibros", "#Lectores"],
        "ig08_04": ["#Bookstagram", "#Sinopsis", "#HumorLector", "#LibrosEnEspañol"],
        "ig08_05": ["#Bookstagram", "#Fantasía", "#HumorLector", "#PrimerCapítulo"],
        "ig08_06": ["#Bookstagram", "#Lectores", "#FinalDeLibro", "#LibrosEnEspañol"],
    }

    scenes: dict[str, dict] = {}
    for n in range(1, 7):
        path = SCENES / f"ig08_{n:02d}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        scenes[data["id"]] = data
        if data.get("id") != f"ig08_{n:02d}":
            fail(f"{path.name}: id desincronizado")
        if data.get("character_version") != "LECTOR_A_v1":
            fail(f"{data['id']}: debe declarar LECTOR_A_v1")
        if data.get("style"):
            fail(f"{data['id']}: no puede sobreescribir estilo por episodio")
        if not str(data.get("reference_url", "")).startswith("https://www.pexels.com/photo/"):
            fail(f"{data['id']}: referencia no es Pexels exacta")
        if "pexels.com" not in str(data.get("source_license", "")):
            fail(f"{data['id']}: licencia Pexels ausente")
        if data.get("caption") != expected_captions[data["id"]]:
            fail(f"{data['id']}: caption auditado desincronizado")
        if data.get("hashtags") != expected_hashtags[data["id"]]:
            fail(f"{data['id']}: hashtags auditados desincronizados")
        if data.get("first_comment") is not None:
            fail(f"{data['id']}: first_comment debe seguir vacío")
        panels = data.get("panels") or []
        if len(panels) != 4:
            fail(f"{data['id']}: debe contener exactamente 4 paneles")
        for idx, panel in enumerate(panels, start=1):
            if panel.get("expression", "neutral") not in allowed:
                fail(f"{data['id']} panel {idx}: expresión fuera de biblia")

    captions_blob = "\n".join(expected_captions.values())
    for old in (
        "Hay capítulos que empiezan cortos",
        "El error fue pensar que la pila",
        "Prestar un libro también es una forma",
        "Hay contraportadas que necesitan saber parar",
        "Cuando necesitas tus propios apuntes",
        "A veces leer más despacio",
    ):
        if old in captions_blob:
            fail(f"reapareció caption genérico retirado: {old!r}")

    first = scenes["ig08_01"]["panels"]
    if [p.get("clock") for p in first] != ["23:48", "00:36", "01:52", "02:31"]:
        fail("IG-08-01 perdió la secuencia exacta de horas")
    if [p.get("bubble") for p in first] != [
        "Uno más y duermo.", None, "Este capítulo tiene seis páginas.", "Tenía seis páginas y una traición."
    ]:
        fail("IG-08-01 perdió diálogo exacto")
    if [p.get("expression") for p in first] != ["neutral", "neutral", "cansado", "alarma"]:
        fail("IG-08-01 perdió expresiones cerradas")

    sixth = scenes["ig08_06"]["panels"]
    if sixth[0].get("action") != "bed_pages":
        fail("IG-08-06 panel 1 debe usar bed_pages")
    if sixth[0].get("small_text") or sixth[0].get("bubble") or sixth[0].get("note"):
        fail("IG-08-06 panel 1 debe seguir sin texto")
    if any("Quedan doce páginas" in json.dumps(p, ensure_ascii=False) for p in sixth):
        fail("IG-08-06 recuperó el texto visual prohibido 'Quedan doce páginas.'")

    renderer = (BASE / "render_microcomic.py").read_text(encoding="utf-8")
    required_markers = (
        "load_character", "character_sha256", "IG08_RENDER_BLOCKED", "FONT_FACE_CSS",
        "local('Inter')", "document.fonts.load", "object-fit:contain",
        "near_end=(action == \"bed_pages\")", "RENDERED_NOT_SCHEDULED",
    )
    for marker in required_markers:
        if marker not in renderer:
            fail(f"renderer perdió guardia {marker!r}")
    if "object-fit:cover" in renderer:
        fail("slide 5 no puede recuperar object-fit:cover")

    converter = (BASE / "make_tiktok_frames.py").read_text(encoding="utf-8")
    converter_markers = (
        "SOURCE_W = 1080", "SOURCE_H = 1350", "TARGET_W = 1080", "TARGET_H = 1920",
        "TT04_CONVERT_BLOCKED", "load_source_manifest", "character_sha256", "slide5_fit",
        "source_manifest_sha256", "source_sha256", "output_sha256", "RENDERED_NOT_SCHEDULED",
        "\"cropped\": False", "\"stretched\": False", "\"offset\": [x, y]",
    )
    for marker in converter_markers:
        if marker not in converter:
            fail(f"conversor TT-04 perdió guardia {marker!r}")
    if "resize(" in converter:
        fail("TT-04 no debe reescalar los renders 1080×1350 de IG-08")

    readme = (BASE / "README.md").read_text(encoding="utf-8")
    for marker in (
        "132×144", "250×300", "character_sha256", "object-fit: contain",
        "Quedan doce páginas.", "RENDERED_NOT_SCHEDULED", "no programar"
    ):
        if marker.casefold() not in readme.casefold():
            fail(f"README perdió regla {marker!r}")

    print("OK: IG-08/TT-04 conservan biblia, copy humano, paneles completos, trazabilidad y estado no programado.")


if __name__ == "__main__":
    main()
