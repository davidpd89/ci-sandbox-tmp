#!/usr/bin/env python3
"""Regresiones de canon y pipeline para TT-02."""
from __future__ import annotations

import json
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools" / "manecillas_slideshow"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR TT-02: {message}")


def main() -> None:
    required = [BASE / "README.md", BASE / "tt02_manifest.json", BASE / "render_manecillas_slideshow.py"]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        fail("faltan archivos: " + ", ".join(missing))
    try:
        py_compile.compile(str(BASE / "render_manecillas_slideshow.py"), doraise=True)
    except py_compile.PyCompileError as exc:
        fail(f"renderer no compila: {exc.msg}")

    data = json.loads((BASE / "tt02_manifest.json").read_text(encoding="utf-8"))
    if data.get("canonical_source", {}).get("drive_id") != "1CtjHvvy7BxBm-H7I5CXh5p7wK3QcykCt":
        fail("ha cambiado el documento canónico")
    cover = data.get("cover") or {}
    expected_cover = {
        "drive_id": "1SClEck69kTqbqorViNxks1t1Axwu-Vy1",
        "asset": "portada-las-manecillas-del-recuerdo-1024x1536.png",
        "width": 1024,
        "height": 1536,
        "sha256": "1361ed45dad7cfea9f9e07de08369ef4e656867f9ecc370c429571cfba0b1e8b",
    }
    for key, value in expected_cover.items():
        if cover.get(key) != value:
            fail(f"portada desincronizada en {key}: {cover.get(key)!r}")
    if "no programar" not in data.get("schedule_rule", "").casefold():
        fail("schedule_rule debe bloquear programación sin autorización")

    posts = data.get("posts") or []
    if [p.get("id") for p in posts] != ["tt02_01", "tt02_02", "tt02_03"]:
        fail("deben existir exactamente las tres piezas en orden")
    if data.get("gate_items") != ["tt02_01"]:
        fail("gate debe empezar por TT-02-01")

    expected = {
        "tt02_01": [
            "Un niño cuenta cuántas veces su abuelo mira el reloj durante el desayuno.",
            "Tomás contó las siete veces que su abuelo miró el reloj durante el desayuno.",
            "Los domingos normales, Manuel apenas lo miraba; el tiempo con los nietos era otra cosa, más despacio.",
            "Pero hoy cada minuto se veía venir desde lejos y el niño ya sabía por qué: mañana era la cita con el cardiólogo.",
            "El sol se colaba por las cortinas gastadas, formando manchas doradas que bailaban sobre la mesa de nogal.",
            "En la cocina del abuelo Manuel, el chocolate de los domingos tenía su propio orden: primero el cacao, después el azúcar, después el silencio.",
            "Este domingo el chocolate llevaba cinco minutos en la mesa y ninguno de los dos lo había tocado.",
            "Tomás, que acababa de cumplir once años, balanceaba las piernas sin apartar los ojos de su abuelo.",
            "Van siete veces, pensó.",
        ],
        "tt02_02": [
            "Un reloj deja de ser corriente en cuanto alguien pregunta cuánto vale.",
            "Mientras tanto, la mujer examina el reloj de la vitrina principal como si fuera el Santo Grial.",
            "—¿Este reloj también está en venta?",
            "—Ese no se toca. —Ramón se pone serio—. Ese es especial.",
            "«Aquí está. La primera que muerde el anzuelo».",
            "Los tres clientes se acercan a la vitrina, moscas a la miel. Sonríe por dentro.",
            "—Perteneció a alguien muy famoso. No puedo dar detalles.",
            "—¿Cuánto vale?\n—No está en venta. Es una pieza de museo.",
            "«Mentira número uno. Ahora a inflar la demanda».",
        ],
        "tt02_03": [
            "¿Qué pasa cuando una generación deja de saber cómo suena una hora?",
            "—¿Ese reloj es analógico?\n—Sí.",
            "—¿Puedo?",
            "Dudó un momento, luego se lo quitó y se lo pasó. Martín lo examinó con fascinación.",
            "—Es increíble. En un mundo donde todo se actualiza constantemente, donde todo es Smart, esto simplemente… es.",
            "—Escuchó el tic-tac—. ¿Sabe? Mi generación no conoce este sonido.",
            "Para nosotros, las horas son silenciosas. Digitales.",
            "—¿Qué notas con el sonido?",
            "—Suena… honesto. Como si no tuviera nada que demostrar. Como si cada segundo valiera por sí mismo.",
        ],
    }

    for post in posts:
        if len(post.get("slides") or []) != 10 or post["slides"][-1].get("kind") != "cover":
            fail(f"{post['id']}: debe contener 9 slides de texto + portada")
        texts = [slide.get("text") for slide in post["slides"][:9]]
        if texts != expected[post["id"]]:
            fail(f"{post['id']}: texto/canon desincronizado")
        if len(post.get("hashtags") or []) != 4:
            fail(f"{post['id']}: debe conservar cuatro hashtags")
        if not str(post.get("reference_url", "")).startswith("https://www.pexels.com/photo/"):
            fail(f"{post['id']}: referencia principal no es Pexels exacta")
        if not str(post.get("backup_reference_url", "")).startswith("https://www.pexels.com/photo/"):
            fail(f"{post['id']}: backup no está documentado como Pexels exacto")
    first = posts[0]["slides"]
    if first[0].get("note") != "Fragmento real · Las manecillas del recuerdo":
        fail("TT-02-01 slide 1 perdió la identificación de fragmento")
    if first[8].get("note") != "El fragmento se corta aquí.":
        fail("TT-02-01 slide 9 perdió el corte obligatorio")

    renderer = (BASE / "render_manecillas_slideshow.py").read_text(encoding="utf-8")
    for marker in ("TT02_COVER_BLOCKED", "TT02_SOURCE_BLOCKED", "TT02_RENDER_BLOCKED", "sha256", "RENDERED_NOT_SCHEDULED", "document.fonts.load"):
        if marker not in renderer:
            fail(f"renderer perdió guardia {marker!r}")
    if "image-to-image" in renderer.casefold() or "generation_prompt" in renderer:
        fail("renderer principal no debe abrir una ruta generativa")

    readme = (BASE / "README.md").read_text(encoding="utf-8")
    for marker in (expected_cover["sha256"], "Photo Mode", "no programar", "Van siete veces, pensó."):
        if marker.casefold() not in readme.casefold():
            fail(f"README perdió regla {marker!r}")

    print("OK: TT-02 conserva canon, portada real, stock directo y bloqueo de programación.")


if __name__ == "__main__":
    main()
