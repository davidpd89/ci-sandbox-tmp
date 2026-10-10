#!/usr/bin/env python3
"""Descarga solo las referencias Pexels declaradas en IG-02.

No busca sustitutos ni modifica la fotografía. Guarda el asset exacto y un sidecar
JSON con la página fuente y la licencia de Pexels.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import urllib.request
from pathlib import Path

UA = "rrss-davidporto-production-kit/1.0 (+https://davidportodiaz.com)"


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def fetch_bytes(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read(), response.geturl(), response.headers.get_content_type()


def meta(page: str, prop: str) -> str | None:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(prop)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, page, flags=re.I)
        if match:
            return html_lib.unescape(match.group(1))
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, default=Path("build/ig02/assets"))
    parser.add_argument("--item")
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    posts = data["posts"]
    if args.item:
        posts = [post for post in posts if post["id"] == args.item]
        if not posts:
            raise SystemExit(f"ERROR: no existe {args.item}")

    args.out.mkdir(parents=True, exist_ok=True)
    for post in posts:
        page_url = post["reference_url"]
        if "pexels.com/photo/" not in page_url:
            raise SystemExit(f"ERROR {post['id']}: referencia no Pexels: {page_url}")
        page = fetch_text(page_url)
        if "free to use" not in page.lower():
            raise SystemExit(
                f"ERROR {post['id']}: la página ya no expone la señal 'Free to use'; revisar manualmente {page_url}"
            )
        image_url = meta(page, "og:image")
        title = meta(page, "og:title") or meta(page, "twitter:title") or ""
        if not image_url:
            raise SystemExit(f"ERROR {post['id']}: Pexels no expone og:image; no se busca sustituto. {page_url}")
        blob, final_url, content_type = fetch_bytes(image_url)
        if not content_type.startswith("image/"):
            raise SystemExit(f"ERROR {post['id']}: og:image no devolvió imagen ({content_type})")
        destination = args.out / post["asset"]
        destination.write_bytes(blob)
        sidecar = {
            "id": post["id"],
            "source_page": page_url,
            "page_title": title,
            "resolved_image_url": image_url,
            "download_final_url": final_url,
            "bytes": len(blob),
            "content_type": content_type,
            "source": "Pexels",
            "license_url": data["license_url"],
            "pexels_free_to_use_signal": True,
            "production_route": data["production_route"],
        }
        (args.out / f"{post['id']}.reference.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"OK {post['id']} -> {destination} ({len(blob)} bytes)")


if __name__ == "__main__":
    main()
