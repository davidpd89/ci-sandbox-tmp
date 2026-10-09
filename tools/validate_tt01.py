#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools" / "tiktok_pov" / "tt01_manifest.json"
DOWNLOADER = ROOT / "tools" / "tiktok_pov" / "fetch_references.py"
README = ROOT / "tools" / "tiktok_pov" / "README.md"


def fail(msg: str) -> None:
    raise SystemExit("ERROR TT-01: " + msg)


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = data.get("items") or []

    if data.get("production_route") != "REAL_DIRECT":
        fail("la ruta principal debe seguir siendo REAL_DIRECT")
    if [x.get("id") for x in items] != [f"tt01_{i:02d}" for i in range(1, 11)]:
        fail("deben existir exactamente tt01_01…tt01_10 en orden")

    expected = {
        "tt01_01": {
            "caption": "Ayer, donde está esa puerta, había un perchero. Con eso ya debería bastar para no tocar el pomo.",
            "reference_url": "https://www.pexels.com/photo/person-standing-in-a-passage-20849981/",
        },
        "tt01_02": {
            "caption": "Dijo tu nombre sin darle importancia. Un segundo después, el héroe tuvo que preguntarlo.",
            "reference_url": "https://www.pexels.com/photo/a-couple-inside-a-dark-room-6670067/",
        },
        "tt01_03": {
            "caption": "Una moneda sobre la mesa. «Nada a cambio». Mejor mirar la letra pequeña antes de guardársela.",
            "reference_url": "https://www.pexels.com/photo/person-hand-holding-old-coin-12689958/",
        },
        "tt01_09": {
            "caption": "La carta llega de mañana y no explica el futuro. Solo te deja una orden para hoy.",
            "reference_url": "https://www.pexels.com/photo/close-up-of-woman-taking-out-a-blank-piece-of-paper-form-an-envelope-7318933/",
        },
    }

    by_id = {x["id"]: x for x in items}
    for item_id, spec in expected.items():
        item = by_id[item_id]
        for key, value in spec.items():
            if item.get(key) != value:
                fail(f"{item_id}: {key} desincronizado")

    bad_caption_patterns = (
        "Lo inquietante no es",
        "Lo peor no es",
        "La sexta silla no da miedo. Da miedo",
        "Hay regalos que necesitan",
        "Eso es todo lo que necesitas saber",
    )
    captions = "\n".join(x.get("caption", "") for x in items)
    for pattern in bad_caption_patterns:
        if pattern in captions:
            fail(f"reapareció caption explicativo retirado: {pattern!r}")

    if "Yo miraría" in captions or "yo miraría" in captions:
        fail("reapareció primera persona innecesaria en caption")

    for item in items:
        if len(item.get("hashtags") or []) != 4:
            fail(f"{item['id']}: debe mantener 4 hashtags cerrados")
        if not str(item.get("reference_url", "")).startswith("https://www.pexels.com/photo/"):
            fail(f"{item['id']}: referencia no Pexels exacta")
        if "DESACTIVADO" not in item.get("generation_prompt", ""):
            fail(f"{item['id']}: generation_prompt debe seguir explícitamente desactivado")
        if "DESACTIVADO" not in item.get("slide2_edit", ""):
            fail(f"{item['id']}: slide2_edit generativo debe seguir desactivado")
        if "foto real" not in json.dumps(item.get("visual_json", {}), ensure_ascii=False):
            fail(f"{item['id']}: visual_json perdió la ruta de foto real")

    downloader = DOWNLOADER.read_text(encoding="utf-8")
    for marker in (
        'data.get("production_route") != "REAL_DIRECT"',
        '"image-to-image"',
        '"regenerar personas"',
        '"sustituir el asset automáticamente"',
    ):
        if marker not in downloader:
            fail(f"downloader perdió guardia {marker!r}")

    readme = README.read_text(encoding="utf-8")
    if "Ruta principal: fotografía real directa" not in readme:
        fail("README dejó de declarar la fotografía real como ruta principal")
    if "image-to-image solo como última opción" not in readme:
        fail("README perdió la regla que relega image-to-image")

    print("OK: TT-01 conserva foto real directa, referencias vigentes y captions auditados.")


if __name__ == "__main__":
    main()
