#!/usr/bin/env python3
"""Descarga únicamente la fotografía Pexels declarada en TT-01.

Ruta vigente: foto real exacta -> crop/zoom/oscurecido CSS -> texto por renderer.
No genera, no edita personas y no busca alternativas silenciosas.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import urllib.request
from pathlib import Path

UA = "rrss-davidporto-production-kit/2.0 (+https://davidportodiaz.com)"


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def fetch_bytes(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.geturl(), r.headers.get_content_type()


def meta(html: str, prop: str) -> str | None:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(prop)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, flags=re.I)
        if m:
            return html_lib.unescape(m.group(1))
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path, default=Path("build/tt01/assets"))
    ap.add_argument("--item", help="Ej. tt01_01; omitir para todos")
    args = ap.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if data.get("production_route") != "REAL_DIRECT":
        raise SystemExit("ERROR TT-01: production_route debe ser REAL_DIRECT")

    items = data["items"]
    if args.item:
        items = [x for x in items if x["id"] == args.item]
        if not items:
            raise SystemExit(f"ERROR: no existe {args.item}")

    args.out.mkdir(parents=True, exist_ok=True)
    for item in items:
        page_url = item["reference_url"]
        if "pexels.com/photo/" not in page_url:
            raise SystemExit(f"ERROR {item['id']}: referencia no Pexels: {page_url}")

        page = fetch_text(page_url)
        if "Free to use" not in page and "free to use" not in page.lower():
            raise SystemExit(
                f"ERROR {item['id']}: la página ya no expone la señal 'Free to use'; "
                f"revisar manualmente {page_url}"
            )

        image_url = meta(page, "og:image")
        title = meta(page, "og:title") or meta(page, "twitter:title") or ""
        if not image_url:
            raise SystemExit(
                f"ERROR {item['id']}: Pexels no expone og:image; no se busca sustituto. {page_url}"
            )

        blob, final_url, content_type = fetch_bytes(image_url)
        if not content_type.startswith("image/"):
            raise SystemExit(f"ERROR {item['id']}: og:image no devolvió imagen ({content_type})")

        dest = args.out / item["assets"]["reference"]
        dest.write_bytes(blob)
        sidecar = {
            "id": item["id"],
            "source_page": page_url,
            "page_title": title,
            "resolved_image_url": image_url,
            "download_final_url": final_url,
            "bytes": len(blob),
            "content_type": content_type,
            "pexels_free_to_use_signal": True,
            "production_route": "REAL_DIRECT",
            "reference_reason": item["reference_reason"],
            "visual_json": item["visual_json"],
            "allowed_transformations": [
                "crop determinista",
                "zoom moderado",
                "ajuste de exposición/contraste",
                "oscurecido/overlay CSS",
                "texto HTML/CSS"
            ],
            "forbidden_transformations": [
                "image-to-image",
                "regenerar personas",
                "añadir objetos fantásticos",
                "texto generado dentro de la foto",
                "sustituir el asset automáticamente"
            ]
        }
        (args.out / f"{item['id']}.reference.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"OK {item['id']} -> {dest} ({len(blob)} bytes) [REAL_DIRECT]")


if __name__ == "__main__":
    main()
