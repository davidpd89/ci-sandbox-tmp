#!/usr/bin/env python3
"""Descarga únicamente assets declarados en IG-01.

Portadas:
- abre la ficha exacta declarada;
- exige que el título de página siga conteniendo el título esperado;
- intenta JSON-LD `image` y después og:image;
- Google Books usa el book_id exacto.

Viajes:
- descarga únicamente la referencia Pexels principal declarada;
- no usa el backup automáticamente;
- guarda sidecar de trazabilidad.

Nunca busca una edición o una foto sustituta.
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


def get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def get_bytes(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.geturl(), r.headers.get_content_type()


def meta(html: str, prop: str) -> str | None:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(prop)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.I)
        if m:
            return html_lib.unescape(m.group(1))
    return None


def page_title(html: str) -> str:
    title = meta(html, "og:title")
    if title:
        return title
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    return html_lib.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else ""


def jsonld_images(html: str) -> list[str]:
    out: list[str] = []
    for raw in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, flags=re.I | re.S):
        try:
            data = json.loads(html_lib.unescape(raw))
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        for node in stack:
            if not isinstance(node, dict):
                continue
            image = node.get("image")
            if isinstance(image, str):
                out.append(image)
            elif isinstance(image, list):
                out.extend(x for x in image if isinstance(x, str))
            elif isinstance(image, dict) and isinstance(image.get("url"), str):
                out.append(image["url"])
    return out


def choose_cover_image(html: str) -> str:
    for candidate in jsonld_images(html):
        if candidate.startswith("http"):
            return candidate
    image = meta(html, "og:image")
    if image and image.startswith("http"):
        return image
    raise RuntimeError("la ficha no expone imagen de producto/og:image")


def download_cover(slug: str, spec: dict, out: Path) -> None:
    source_type = spec["source_type"]
    source_url = spec["url"]
    audit = {"slug":slug,"title":spec["title"],"source_type":source_type,"source_url":source_url}

    if source_type == "publisher":
        html = get_text(source_url)
        title = page_title(html)
        expected = spec["expected_page_title"]
        if expected.casefold() not in title.casefold():
            raise RuntimeError(f"{slug}: la ficha ya no parece la edición esperada. Esperado {expected!r}; título actual {title!r}")
        image_url = choose_cover_image(html)
        audit["page_title"] = title
    elif source_type == "google_books":
        book_id = spec["book_id"]
        html = get_text(source_url)
        title = page_title(html)
        if spec["title"].casefold() not in title.casefold():
            raise RuntimeError(f"{slug}: Google Books ya no devuelve la ficha esperada: {title!r}")
        image_url = f"https://books.google.com/books/content?id={urllib.parse.quote(book_id)}&printsec=frontcover&img=1&zoom=2&edge=curl&source=gbs_api"
        audit["page_title"] = title
        audit["book_id"] = book_id
    else:
        raise RuntimeError(f"{slug}: source_type no soportado: {source_type}")

    blob, final_url, ctype = get_bytes(image_url)
    if not ctype.startswith("image/"):
        raise RuntimeError(f"{slug}: la imagen resuelta no es imagen ({ctype})")
    dest = out / spec["asset"]
    dest.write_bytes(blob)
    audit.update({"resolved_image_url":image_url,"download_final_url":final_url,"content_type":ctype,"bytes":len(blob)})
    (out / f"{slug}.source.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK cover {slug} -> {dest}")


def download_travel(key: str, spec: dict, out: Path) -> None:
    url = spec["url"]
    if "pexels.com/photo/" not in url:
        raise RuntimeError(f"{key}: referencia no Pexels")
    html = get_text(url)
    if "free to use" not in html.casefold():
        raise RuntimeError(f"{key}: la ficha no expone señal 'Free to use'; revisar manualmente {url}")
    image_url = meta(html, "og:image")
    if not image_url:
        raise RuntimeError(f"{key}: Pexels no expone og:image")
    blob, final_url, ctype = get_bytes(image_url)
    if not ctype.startswith("image/"):
        raise RuntimeError(f"{key}: referencia resuelta no es imagen")
    dest = out / spec["asset"]
    dest.write_bytes(blob)
    audit = {
        "key":key,"source_url":url,"backup_url":spec.get("backup"),"resolved_image_url":image_url,
        "download_final_url":final_url,"bytes":len(blob),"content_type":ctype,"visual_json":spec["visual_json"],
        "production_note":"Esta es la referencia. Si se genera variación, guardar el resultado en final_asset. El backup nunca se usa automáticamente."
    }
    (out / f"travel_{key}.source.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK travel ref {key} -> {dest}")


def download_soft_background(key: str, spec: dict, out: Path) -> None:
    url = spec["url"]
    if "pexels.com/photo/" not in url:
        raise RuntimeError(f"{key}: fondo no Pexels")
    image_url = spec.get("direct_image_url")
    if not image_url:
        html = get_text(url)
        if "free to use" not in html.casefold():
            raise RuntimeError(f"{key}: la ficha no expone señal 'Free to use'; revisar manualmente {url}")
        image_url = meta(html, "og:image")
        if not image_url:
            raise RuntimeError(f"{key}: Pexels no expone og:image")
    blob, final_url, ctype = get_bytes(image_url)
    if not ctype.startswith("image/"):
        raise RuntimeError(f"{key}: fondo resuelto no es imagen")
    dest = out / spec["asset"]
    dest.write_bytes(blob)
    audit = {
        "key": key,
        "source_url": url,
        "direct_image_url": spec.get("direct_image_url"),
        "resolved_image_url": image_url,
        "download_final_url": final_url,
        "bytes": len(blob),
        "content_type": ctype,
        "description": spec.get("description"),
        "production_note": "Fondo suave Pexels para IG-01. Se usa desenfocado/oscurecido detrás de portadas reales."
    }
    (out / f"background_{key}.source.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK background {key} -> {dest}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path, default=Path("build/ig01/assets"))
    ap.add_argument("--cover", help="slug concreto")
    ap.add_argument("--travel", help="cork|rockies|tokyo")
    ap.add_argument("--background", help="fondo suave declarado en soft_backgrounds")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    if not any((args.cover, args.travel, args.background, args.all)):
        raise SystemExit("ERROR: usa --cover SLUG, --travel KEY, --background KEY o --all")
    if args.cover:
        download_cover(args.cover, data["covers"][args.cover], args.out)
    if args.travel:
        download_travel(args.travel, data["travel_backgrounds"][args.travel], args.out)
    if args.background:
        download_soft_background(args.background, data["soft_backgrounds"][args.background], args.out)
    if args.all:
        for slug, spec in data["covers"].items():
            download_cover(slug, spec, args.out)
        for key, spec in data.get("soft_backgrounds", {}).items():
            download_soft_background(key, spec, args.out)
        for key, spec in data["travel_backgrounds"].items():
            download_travel(key, spec, args.out)


if __name__ == "__main__":
    main()
