#!/usr/bin/env python3
"""Descarga SOLO los assets declarados en fb02_manifest.json.

- Wikimedia Commons: resuelve el original por API, valida licencia/autor esperados y guarda metadata.
- Página OG (PICRYL): extrae og:image de la URL exacta declarada.

Nunca busca sustitutos. Si falla una fuente o el asset Commons ya no coincide con el gate declarado, aborta esa pieza.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

<<<<<<< HEAD
UA = "rrss-autorademo-production-kit/1.0 (+https://autorademodiaz.com)"
=======
UA = "rrss-davidporto-production-kit/1.0 (+https://davidportodiaz.com)"
>>>>>>> origin/research/public-reuse-parent


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get_bytes(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.geturl()


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html_lib.unescape(value).split())


def norm(value: str | None) -> str:
    value = strip_html(value).casefold()
    value = value.replace("creative commons", "cc")
    value = value.replace("attribution", "by")
    value = re.sub(r"[^a-z0-9.]+", " ", value)
    return " ".join(value.split())


def commons_info(file_title: str) -> dict:
    params = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "titles": file_title,
        "redirects": "1",
    })
    data = get_json("https://commons.wikimedia.org/w/api.php?" + params)
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        raise RuntimeError(f"Commons no devolvió página para {file_title}")
    page = next(iter(pages.values()))
    infos = page.get("imageinfo") or []
    if not infos:
        raise RuntimeError(f"Commons no devolvió imageinfo para {file_title}")
    info = infos[0]
    meta = info.get("extmetadata") or {}
    return {
        "original_url": info["url"],
        "description_url": info.get("descriptionurl"),
        "license_short": strip_html((meta.get("LicenseShortName") or {}).get("value")),
        "license_url": strip_html((meta.get("LicenseUrl") or {}).get("value")),
        "artist": strip_html((meta.get("Artist") or {}).get("value")),
        "credit": strip_html((meta.get("Credit") or {}).get("value")),
        "object_name": strip_html((meta.get("ObjectName") or {}).get("value")),
    }


def validate_commons_asset(item: dict, info: dict) -> None:
    gate = item.get("asset_audit") or {}
    expected_license = gate.get("license_contains")
    if expected_license:
        actual = norm(info.get("license_short"))
        wanted = norm(expected_license)
        if wanted not in actual:
            raise RuntimeError(
                f"{item['id']}: licencia Commons cambió. "
                f"Esperado contiene {expected_license!r}; recibido {info.get('license_short')!r}."
            )

    expected_artist = gate.get("artist_contains")
    if expected_artist:
        actual_artist = norm(info.get("artist"))
        wanted_artist = norm(expected_artist)
        if wanted_artist not in actual_artist:
            raise RuntimeError(
                f"{item['id']}: autor Commons cambió. "
                f"Esperado contiene {expected_artist!r}; recibido {info.get('artist')!r}."
            )


def og_image(page_url: str) -> str:
    req = urllib.request.Request(page_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", "replace")
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    ]
    for pat in patterns:
        m = re.search(pat, raw, flags=re.I)
        if m:
            return html_lib.unescape(m.group(1))
    raise RuntimeError(f"No se encontró og:image en {page_url}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path, default=Path("build/fb02/assets"))
    ap.add_argument("--item", help="Ej. fb02_01; omitir para todos")
    args = ap.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    items = data["items"]
    if args.item:
        items = [x for x in items if x["id"] == args.item]
        if not items:
            raise SystemExit(f"No existe item {args.item}")

    args.out.mkdir(parents=True, exist_ok=True)
    for item in items:
        dl = item["download"]
        audit: dict = {
            "id": item["id"],
            "source_url": item["source_url"],
            "fact_source": item.get("fact_source"),
            "expected_license": item.get("license"),
            "asset_audit": item.get("asset_audit"),
            "download_type": dl["type"],
        }
        if dl["type"] == "commons":
            info = commons_info(dl["file_title"])
            validate_commons_asset(item, info)
            url = info["original_url"]
            audit.update(info)
            audit["asset_gate"] = "PASS"
        elif dl["type"] == "og_image":
            url = og_image(dl["page_url"])
            audit["resolved_og_image"] = url
            audit["asset_gate"] = "MANUAL_REVALIDATION_REQUIRED"
        else:
            raise RuntimeError(f"Tipo de descarga no soportado: {dl['type']}")

        blob, final_url = get_bytes(url)
        dest = args.out / item["asset_file"]
        dest.write_bytes(blob)
        audit["download_final_url"] = final_url
        audit["bytes"] = len(blob)
        (args.out / f"{item['id']}.source.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"OK {item['id']} -> {dest} ({len(blob)} bytes)")


if __name__ == "__main__":
    main()
