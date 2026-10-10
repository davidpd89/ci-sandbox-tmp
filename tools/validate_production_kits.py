#!/usr/bin/env python3
"""Control de integridad de los kits de producción RRSS.

Comprueba estructura ejecutable, JSON/Python, placeholders y regresiones críticas.
No descarga assets ni sustituye gates visuales/factuales.
"""
from __future__ import annotations

import json
import py_compile
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = {
    "ESTRATEGIA": [
        "01_Estrategia/prioridad_redes_y_orden_produccion_2026-08-18.md",
        "01_Estrategia/estado_kits_produccion_2026-08-18.md",
        "01_Estrategia/START_HERE_PRODUCCION.md",
        "01_Estrategia/checklist_calidad_post.md",
    ],
    "TT-01": ["tools/tiktok_pov/README.md", "tools/tiktok_pov/tt01_manifest.json", "tools/tiktok_pov/fetch_references.py", "tools/tiktok_pov/render_pov_cards.py"],
    "IG-01": ["tools/booktok_carousel/README.md", "tools/booktok_carousel/ig01_manifest.json", "tools/booktok_carousel/fetch_assets.py", "tools/booktok_carousel/render_booktok.py"],
    "IG-09": ["tools/interactive_story/README.md", "tools/interactive_story/ig09_story.json", "tools/interactive_story/render_interactive_story.py"],
    "IG-11": ["tools/archive_impossible/README.md", "tools/archive_impossible/ig11_manifest.json", "tools/archive_impossible/fetch_loc_assets.py", "tools/archive_impossible/render_archive_impossible.py"],
    "IG-12": ["tools/met_bookish_memes/README.md", "tools/met_bookish_memes/manifest.json", "tools/met_bookish_memes/download_met.py", "tools/met_bookish_memes/render_carousel.py"],
    "IG-13": ["tools/literary_places/README.md", "tools/literary_places/manifest.json", "tools/literary_places/download_commons.py", "tools/literary_places/render_carousel.py"],
    "IG-14": ["tools/fake_books/README.md", "tools/fake_books/ig14_manifest.json", "tools/fake_books/render_fake_books.py"],
    "IG-15-21": [
        "tools/documentary_carousel/README.md", "tools/documentary_carousel/render_documentary.py",
        "tools/documentary_carousel/manifests/ig15.json", "tools/documentary_carousel/manifests/ig16.json",
        "tools/documentary_carousel/manifests/ig18.json", "tools/documentary_carousel/manifests/ig19.json",
        "tools/documentary_carousel/manifests/ig20.json", "tools/documentary_carousel/manifests/ig21.json",
        "tools/text_carousel/README.md", "tools/text_carousel/ig17_manifest.json", "tools/text_carousel/render_text_carousel.py",
    ],
    "MICROCOMIC": [
        "tools/microcomic/README.md", "tools/microcomic/character_lector_a_v1.json",
        "tools/microcomic/check_fonts.py", "tools/microcomic/render_microcomic.py",
        "tools/microcomic/render_manecillas_opening.py", "tools/microcomic/make_tiktok_frames.py",
    ],
    "TT-05": ["tools/tiktok_excerpt/README.md", "tools/tiktok_excerpt/tt05_manifest.json", "tools/tiktok_excerpt/render_excerpt_cards.py"],
    "FB-02": ["tools/facebook_story_reel/README.md", "tools/facebook_story_reel/fb02_manifest.json", "tools/facebook_story_reel/download_assets.py", "tools/facebook_story_reel/render_story_reel.py"],
}

TOOL_DIRS = [
    "tools/tiktok_pov", "tools/booktok_carousel", "tools/interactive_story", "tools/archive_impossible",
    "tools/met_bookish_memes", "tools/literary_places", "tools/fake_books", "tools/microcomic",
    "tools/documentary_carousel", "tools/text_carousel", "tools/tiktok_excerpt", "tools/facebook_story_reel",
]

PRODUCTION_MANIFESTS = [
    "tools/tiktok_pov/tt01_manifest.json", "tools/booktok_carousel/ig01_manifest.json",
    "tools/interactive_story/ig09_story.json", "tools/archive_impossible/ig11_manifest.json",
    "tools/met_bookish_memes/manifest.json", "tools/literary_places/manifest.json",
    "tools/fake_books/ig14_manifest.json", "tools/documentary_carousel/manifests/ig15.json",
    "tools/documentary_carousel/manifests/ig16.json", "tools/text_carousel/ig17_manifest.json",
    "tools/documentary_carousel/manifests/ig18.json", "tools/documentary_carousel/manifests/ig19.json",
    "tools/documentary_carousel/manifests/ig20.json", "tools/documentary_carousel/manifests/ig21.json",
    "tools/tiktok_excerpt/tt05_manifest.json", "tools/facebook_story_reel/fb02_manifest.json",
]

LITERAL_PLACEHOLDERS = ("[ENLACE]", "[ENLACE OFICIAL]", "[TODO]", "[TBD]", "<URL>", "YOUR_URL")
PENDING_PREFIXES = ("TODO", "TBD", "POR DEFINIR", "PENDIENTE DE ELEGIR", "ELEGIR IMAGEN", "BUSCAR FOTO", "BUSCAR IMAGEN")


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def load_json(rel: str) -> Any:
    try:
        return json.loads(read(rel))
    except Exception as exc:
        fail(f"JSON inválido {rel}: {exc}")


def strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def joined(value: Any) -> str:
    return "\n".join(strings(value))


def by_id(manifest: dict[str, Any], item_id: str) -> dict[str, Any]:
    for key in ("items", "posts", "episodes"):
        for item in manifest.get(key) or []:
            if item.get("id") == item_id:
                return item
    fail(f"no existe {item_id} en {manifest.get('series') or manifest.get('id') or 'manifest'}")
    raise AssertionError


def slide_by_n(item: dict[str, Any], n: int) -> dict[str, Any]:
    for slide in item.get("slides") or []:
        if slide.get("n") == n:
            return slide
    fail(f"{item.get('id')}: no existe slide n={n}")
    raise AssertionError


def require_markers(rel: str, markers: tuple[str, ...], label: str) -> None:
    text = read(rel)
    for marker in markers:
        if marker not in text:
            fail(f"{label}: falta guardia {marker!r} en {rel}")


def reject_markers(rel: str, markers: tuple[str, ...], label: str) -> None:
    text = read(rel)
    for marker in markers:
        if marker in text:
            fail(f"{label}: reapareció patrón prohibido {marker!r} en {rel}")


def validate_placeholders(rel: str) -> None:
    for text in strings(load_json(rel)):
        upper = text.upper()
        for marker in LITERAL_PLACEHOLDERS:
            if marker in upper:
                fail(f"marcador pendiente {marker!r} en {rel}: {text[:120]!r}")
        stripped = upper.strip()
        for marker in PENDING_PREFIXES:
            if stripped == marker or re.match(rf"^{re.escape(marker)}\s*(?::|[-—–])", stripped):
                fail(f"marcador pendiente {marker!r} en {rel}: {text[:120]!r}")


def validate_required() -> None:
    missing = [f"{kit}: {rel}" for kit, paths in REQUIRED.items() for rel in paths if not (ROOT / rel).exists()]
    if missing:
        fail("faltan archivos obligatorios:\n- " + "\n- ".join(missing))


def validate_code() -> None:
    for rel_dir in TOOL_DIRS:
        directory = ROOT / rel_dir
        for path in directory.rglob("*.json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                fail(f"JSON inválido {path.relative_to(ROOT)}: {exc}")
        for path in directory.rglob("*.py"):
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                fail(f"Python no compila {path.relative_to(ROOT)}: {exc.msg}")


def validate_tt01() -> None:
    m = load_json("tools/tiktok_pov/tt01_manifest.json")
    items = m.get("items") or []
    if len(items) != 10 or [x.get("id") for x in items] != [f"tt01_{i:02d}" for i in range(1, 11)]:
        fail("TT-01 debe contener exactamente tt01_01…tt01_10 en orden")
    for item in items:
        if len(item.get("hashtags") or []) != 4:
            fail(f"{item['id']}: TT-01 debe conservar 4 hashtags")
        if not str(item.get("reference_url", "")).startswith("https://www.pexels.com/photo/"):
            fail(f"{item['id']}: referencia TT-01 no es Pexels exacta")
        if not item.get("visual_json") or not item.get("generation_prompt") or not item.get("slide2_edit"):
            fail(f"{item['id']}: falta JSON/prompt/edición cerrada")
        for key in ("reference", "slide1", "slide2"):
            if not (item.get("assets") or {}).get(key):
                fail(f"{item['id']}: falta assets.{key}")
    if by_id(m, "tt01_01").get("hook") != "POV: la puerta no estaba ahí ayer.":
        fail("TT-01-01 hook desincronizado")
    if "Él no estaba escuchando." not in by_id(m, "tt01_02").get("payoff", ""):
        fail("TT-01-02 payoff desincronizado")


def validate_ig01() -> None:
    m = load_json("tools/booktok_carousel/ig01_manifest.json")
    posts = m.get("posts") or []
    if [p.get("id") for p in posts] != [f"ig01_{i:02d}" for i in range(1, 7)]:
        fail("IG-01 debe contener exactamente ig01_01…ig01_06 en orden")
    covers = m.get("covers") or {}
    required_covers = {"mas_que_rivales","cambiar_el_juego","alas_de_sangre","binding_13","keeping_13","saving_6","redeeming_6","si_fueramos_eternos","hasta_estrellas","amor_fuera_serie","wild_love","dorayaki"}
    if set(covers) != required_covers:
        fail("IG-01: inventario de portadas distinto del auditado")
    for slug, spec in covers.items():
        if not spec.get("asset") or not spec.get("url"):
            fail(f"IG-01 cover {slug}: falta asset/url")
        if spec.get("source_type") == "publisher" and not spec.get("expected_page_title"):
            fail(f"IG-01 cover {slug}: editorial sin expected_page_title")
        if spec.get("source_type") == "google_books" and not spec.get("book_id"):
            fail(f"IG-01 cover {slug}: Google Books sin book_id")
    for post in posts:
        if len(post.get("hashtags") or []) != 4:
            fail(f"{post['id']}: IG-01 debe conservar 4 hashtags")
    gate_covers = by_id(m, "ig01_01")["slides"][0].get("covers")
    if gate_covers != ["mas_que_rivales","binding_13","keeping_13"]:
        fail("IG-01-01: portadas del gate desincronizadas")
    if "primera lista oficial" not in by_id(m, "ig01_01").get("caption", ""):
        fail("IG-01-01: caption perdió la referencia temporal de marzo")
    lower = joined(m).casefold()
    if "top actual" in lower or "ahora mismo" in lower:
        fail("IG-01 no puede presentar marzo de 2026 como ranking actual")
    travel = m.get("travel_backgrounds") or {}
    if set(travel) != {"cork","rockies","tokyo"}:
        fail("IG-01-05: deben existir exactamente cork/rockies/tokyo")
    for key, spec in travel.items():
        if not str(spec.get("url", "")).startswith("https://www.pexels.com/photo/") or not spec.get("final_asset") or not spec.get("visual_json"):
            fail(f"IG-01 travel {key}: referencia/final_asset/JSON incompletos")
    if "Rose Hill es ficticio" not in joined(by_id(m, "ig01_05")):
        fail("IG-01-05 debe conservar que Rose Hill es ficticio")


def validate_ig09() -> None:
    m = load_json("tools/interactive_story/ig09_story.json")
    ep1 = by_id(m, "ig09_ep01")
    if slide_by_n(ep1, 3).get("emphasis") != "NO LA USES AQUÍ.":
        fail("IG-09 EP1-S3 debe declarar énfasis exacto en Inter 800")
    ep3 = by_id(m, "ig09_ep03")
    if slide_by_n(ep3, 2).get("body") != "Dentro aparece una fotografía.\n\nEs la misma puerta.\n\nPero está instalada en un andén.":
        fail("IG-09 EP3-S2 recuperó una variante manual sobre/consigna")
    require_markers(
        "tools/interactive_story/render_interactive_story.py",
        ("IG09_RENDER_BLOCKED", "document.fonts.check", "Inter:wght@600;700;800", "body_markup", "emphasis"),
        "IG-09",
    )


def validate_ig10() -> None:
    rel = "tools/microcomic/render_manecillas_opening.py"
    text = read(rel)
    source_lines = (
        "Tomás contó las siete veces que su abuelo miró el reloj durante el desayuno.",
        "Los domingos normales, Manuel apenas lo miraba.",
        "Mañana era la cita con el cardiólogo.",
        "El chocolate llevaba cinco minutos en la mesa y ninguno de los dos lo había tocado.",
    )
    for line in source_lines:
        if line not in text:
            fail(f"IG-10 perdió línea canónica: {line!r}")
    require_markers(rel, ("IG10_RENDER_BLOCKED", "local('Inter')", "object-fit:contain", "Slide 5 keeps every panel complete"), "IG-10")
    if "object-fit:cover" in text:
        fail("IG-10 no puede recortar los cuatro paneles de slide 5 con object-fit:cover")
    if '<div class="brand">DAVID PORTO DÍAZ</div></body></html>' in text:
        fail("IG-10 slide 5 recuperó la firma extra bajo el crédito")


def validate_ig11() -> None:
    m = load_json("tools/archive_impossible/ig11_manifest.json")
    if len(m.get("episodes") or []) != 4:
        fail("IG-11 debe conservar 4 episodios")
    qr = by_id(m, "ig11_04")["overlay"]
    if qr.get("type") != "qr" or qr.get("target") != by_id(m, "ig11_04").get("item_url"):
        fail("IG-11-04 QR debe apuntar exactamente al item LOC")
    if abs(float(qr.get("reveal_scale", 0)) - 1.62) > 0.001:
        fail("IG-11-04 debe conservar reveal_scale=1.62")
    rel = "tools/archive_impossible/render_archive_impossible.py"
    require_markers(rel, ("IG11_RENDER_BLOCKED", "reveal_scale", "reveal=reveal", "fc-match"), "IG-11")
    reject_markers(rel, ("ImageFont.load_default()",), "IG-11")


def validate_ig12() -> None:
    m = load_json("tools/met_bookish_memes/manifest.json")
    items = m.get("items") or []
    if [x.get("id") for x in items] != [f"ig12_{i:02d}" for i in range(1, 7)]:
        fail("IG-12 debe conservar ig12_01…ig12_06")
    if by_id(m, "ig12_06").get("display_artist") != "":
        fail("IG-12-06 no debe imprimir 'Autor no identificado en ficha' en la creatividad")
    if "«SIN SPOILERS.»" not in joined(by_id(m, "ig12_06")) or "«DIEZ MINUTOS Y A DORMIR.»" not in joined(by_id(m, "ig12_01")):
        fail("IG-12 debe conservar comillas españolas en el texto visual")
    rel = "tools/met_bookish_memes/render_carousel.py"
    require_markers(rel, ("IG12_RENDER_BLOCKED", "display_artist"), "IG-12")
    reject_markers(rel, ("ImageFont.load_default()",), "IG-12")


def validate_ig13() -> None:
    m = load_json("tools/literary_places/manifest.json")
    item = by_id(m, "ig13_02")
    text = joined(item)
    if "ESTA LIBRERÍA\nSIGUE ALOJANDO ESCRITORES" not in text:
        fail("IG-13-02 debe conservar el hook auditado sobre el programa Tumbleweed actual")
    if "sigue ofreciendo residencias a escritores no publicados" not in item.get("caption", ""):
        fail("IG-13-02 caption desincronizado con el programa Tumbleweed actual")
    if "HAY ESCRITORES\nQUE DUERMEN EN ESTA LIBRERÍA" in text:
        fail("IG-13-02 recuperó el hook antiguo que confundía tradición y programa actual")
    rel = "tools/literary_places/render_carousel.py"
    require_markers(rel, ("IG13_RENDER_BLOCKED",), "IG-13")
    reject_markers(rel, ("ImageFont.load_default()",), "IG-13")


def validate_ig14() -> None:
    fake = load_json("tools/fake_books/ig14_manifest.json")
    if fake.get("id") != "IG-14_LIBROS_QUE_NO_EXISTEN_v1" or len(fake.get("episodes") or []) != 6:
        fail("IG-14 fake_books desincronizado")
    require_markers(
        "tools/fake_books/render_fake_books.py",
        ("require_font", "Playfair Display", "Inter", "No se permite fallback tipográfico silencioso"),
        "IG-14",
    )


def validate_ig15() -> None:
    m = load_json("tools/documentary_carousel/manifests/ig15.json")
    if m.get("gate_items") != ["ig15_01", "ig15_02", "ig15_05"]:
        fail("IG-15 gate debe ser 01+02+05")
    for post in m.get("posts") or []:
        for slide in post.get("slides") or []:
            if slide.get("image") and not slide.get("detail_card"):
                fail(f"{post.get('id')}: todo asset IG-15 debe conservar detail_card=true")
    active = by_id(m, "ig15_06")
    active_text = joined(active.get("slides") or [])
    if not all(x in active_text for x in ("W.37.21R", "The Walters", "CC0")):
        fail("IG-15-06 debe producirse desde The Walters W.37.21R · CC0")
    for slide in active.get("slides") or []:
        if "harley" in joined(slide).casefold():
            fail("IG-15-06 no puede usar Harley como slide/fuente activa")


def validate_ig16() -> None:
    text = joined(by_id(load_json("tools/documentary_carousel/manifests/ig16.json"), "ig16_06"))
    if "pellethepoet" not in text or "CC BY 2.0" not in text:
        fail("IG-16-06 debe conservar pellethepoet · CC BY 2.0")


def validate_ig18() -> None:
    m = load_json("tools/documentary_carousel/manifests/ig18.json")
    if m.get("gate_items") != ["ig18_01", "ig18_03", "ig18_06"]:
        fail("IG-18 gate debe ser Stuttgart+Beinecke+Kansas (01+03+06)")
    text = joined(by_id(m, "ig18_06"))
    if not all(x in text for x in ("Library_(17010263631).jpg", "Dean Hochman", "CC BY 2.0")):
        fail("IG-18-06 debe conservar asset HD Dean Hochman · CC BY 2.0")
    if "42 títulos" in text:
        fail("IG-18-06 no puede recuperar 42 títulos")


def validate_ig19() -> None:
    m = load_json("tools/documentary_carousel/manifests/ig19.json")
    if m.get("gate_items") != ["ig19_01", "ig19_05", "ig19_06"]:
        fail("IG-19 gate debe ser California+Kong+Tabula (01+05+06)")
    if "1813_Pinkerton_Map_of_Western_Africa" not in joined(by_id(m, "ig19_05")):
        fail("IG-19-05 debe conservar Pinkerton 1813 HD")
    if "Este mapa necesitaba un continente al sur" in joined(m):
        fail("IG-19-04 recuperó interpretación retirada")


def validate_ig20() -> None:
    text = joined(load_json("tools/documentary_carousel/manifests/ig20.json"))
    stale_values = (
        "Casi 60 millones", "Más de 60 millones de objetos", "60 millones de objetos",
        "35 millones", "5,1 millones", "Más de 100 conjuntos", "Más de 100 colecciones",
        "cerca de medio millón", "Cientos de miles de items Public Domain",
    )
    for stale in stale_values:
        if stale.casefold() in text.casefold():
            fail(f"IG-20 no debe congelar contador vivo: {stale!r}")
    if "recuento vivo" not in text.casefold() and "no congelar una cifra" not in text.casefold() and "no fijar una cifra" not in text.casefold():
        fail("IG-20 debe conservar instrucción de revalidar contadores")


def validate_ig21() -> None:
    m = load_json("tools/documentary_carousel/manifests/ig21.json")
    if "casi ridícula" in joined(m).casefold():
        fail("IG-21 no puede recuperar 'casi ridícula'")
    q = joined(by_id(m, "ig21_06"))
    if "don-quijote-de-la-mancha--13" not in q or "_3.html" not in q:
        fail("IG-21-06 debe conservar fuente del capítulo I")


def validate_renderer_guards() -> None:
    require_markers(
        "tools/documentary_carousel/render_documentary.py",
        ("DOCUMENTARY_RENDER_BLOCKED", "document.fonts.check", "Inter 500", "Playfair Display 900"),
        "IG-15/16/18/19/20/21",
    )
    require_markers(
        "tools/text_carousel/render_text_carousel.py",
        ("TEXT_CAROUSEL_BLOCKED", "Noto Sans", "document.fonts.check"),
        "IG-17",
    )
    require_markers(
        "tools/tiktok_excerpt/render_excerpt_cards.py",
        ("TT-05 bloqueado", "document.fonts.check", "Playfair Display 700"),
        "TT-05",
    )
    require_markers(
        "tools/facebook_story_reel/render_story_reel.py",
        ("require_font", "expected_family", "fallback tipográfico silencioso"),
        "FB-02",
    )


def validate_microcomic() -> None:
    readme = read("tools/microcomic/README.md")
    preflight = read("tools/microcomic/check_fonts.py")
    if "python tools/microcomic/check_fonts.py" not in readme:
        fail("IG-08/TT-04 README debe exigir el preflight tipográfico")
    if "IG-08 BLOQUEADO" not in preflight or 'local("Inter")' not in preflight:
        fail("IG-08/TT-04 preflight no bloquea la ausencia de Inter")


def validate_tt05() -> None:
    m = load_json("tools/tiktok_excerpt/tt05_manifest.json")
    if len(m.get("items") or []) != 6:
        fail("TT-05 debe contener 6 items")
    text = joined(m).casefold()
    for stale in ("quién le contó el chisme", "también puede llegar torcida", "pardo bazán no presenta quieto al personaje"):
        if stale in text:
            fail(f"TT-05 recuperó copy retirado: {stale!r}")


def validate_fb02() -> None:
    m = load_json("tools/facebook_story_reel/fb02_manifest.json")
    items = m.get("items") or []
    if len(items) != 6:
        fail("FB-02 debe contener 6 items")
    for item in items:
        if item.get("download", {}).get("type") == "commons" and not (item.get("asset_audit") or {}).get("license_contains"):
            fail(f"{item['id']}: Commons sin gate de licencia")
    if (by_id(m, "fb02_06").get("asset_audit") or {}).get("artist_contains") != "pellethepoet":
        fail("FB-02-06 debe validar autor pellethepoet")
    if by_id(m, "fb02_02").get("asset_audit"):
        fail("FB-02-02 volvelle no puede fingir gate automático")
    if "revalidar British Library + Europeana" not in by_id(m, "fb02_02").get("license", ""):
        fail("FB-02-02 debe conservar revalidación manual")


def validate_strategy() -> None:
    state = read("01_Estrategia/estado_kits_produccion_2026-08-18.md")
    priority = read("01_Estrategia/prioridad_redes_y_orden_produccion_2026-08-18.md")
    start = read("01_Estrategia/START_HERE_PRODUCCION.md")
    sf, pf = state.casefold(), priority.casefold()
    for kit in ("IG-01","IG-08","IG-09","IG-10","IG-11","IG-12","IG-13","IG-14","IG-15","IG-16","IG-17","IG-18","IG-19","IG-20","IG-21","TT-01","TT-02","TT-03","TT-04","TT-05","FB-01","FB-02","PIN-02","YT-01","YT-02","BS-01","GBP-01"):
        if kit.casefold() not in sf:
            fail(f"estado maestro no contiene {kit}")
    for marker in ("bloqueado por elegibilidad", "7 piezas activas", "backlog auditado", "screening direccional", "tt-05", "fb-02"):
        if marker not in pf:
            fail(f"prioridad desincronizada: falta {marker!r}")
    for marker in ("TT-01-01", "TT-01-02", "IG-01-01", "tools/validate_production_kits.py"):
        if marker not in start:
            fail(f"START_HERE no contiene {marker}")


def main() -> None:
    validate_required()
    validate_code()
    for rel in PRODUCTION_MANIFESTS:
        validate_placeholders(rel)
    if (ROOT / "tools/fake_books/ig12_manifest.json").exists():
        fail("ha reaparecido tools/fake_books/ig12_manifest.json; fake_books es IG-14")
    validate_tt01()
    validate_ig01()
    validate_ig09()
    validate_ig10()
    validate_ig11()
    validate_ig12()
    validate_ig13()
    validate_ig14()
    validate_ig15()
    validate_ig16()
    validate_ig18()
    validate_ig19()
    validate_ig20()
    validate_ig21()
    validate_renderer_guards()
    validate_microcomic()
    validate_tt05()
    validate_fb02()
    validate_strategy()
    print("OK: kits íntegros, JSON/Python válidos, manifests sin placeholders y gates críticos sincronizados.")


if __name__ == "__main__":
    main()
