#!/usr/bin/env python3
"""Descarga exclusivamente imágenes Open Access / Public Domain de The Met para IG-12."""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
ASSETS = ROOT / "assets"
METADATA = ROOT / "metadata"
API = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}"

def fetch_json(url: str) -> dict:
<<<<<<< HEAD
    req = urllib.request.Request(url, headers={"User-Agent": "AutoraDemo-RRSS/IG12"})
=======
    req = urllib.request.Request(url, headers={"User-Agent": "DavidPorto-RRSS/IG12"})
>>>>>>> origin/research/public-reuse-parent
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def download(url: str, dest: pathlib.Path) -> None:
<<<<<<< HEAD
    req = urllib.request.Request(url, headers={"User-Agent": "AutoraDemo-RRSS/IG12"})
=======
    req = urllib.request.Request(url, headers={"User-Agent": "DavidPorto-RRSS/IG12"})
>>>>>>> origin/research/public-reuse-parent
    with urllib.request.urlopen(req, timeout=60) as response, dest.open("wb") as fh:
        fh.write(response.read())

def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ASSETS.mkdir(parents=True, exist_ok=True)
    METADATA.mkdir(parents=True, exist_ok=True)

    for item in data["items"]:
        object_id = item["object_id"]
        meta = fetch_json(API.format(object_id=object_id))

        checks = {
            "objectID": meta.get("objectID") == object_id,
            "public_domain": meta.get("isPublicDomain") is True,
            "primary_image": bool(meta.get("primaryImage")),
            "title": (meta.get("title") or "").strip() == item["title"].strip(),
        }
        if item["artist"] != "Autor no identificado en ficha":
            checks["artist"] = item["artist"].lower() in (meta.get("artistDisplayName") or "").lower()

        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            print(f"BLOCKED {item['id']} — checks failed: {', '.join(failed)}", file=sys.stderr)
            return 2

        ext = pathlib.Path(meta["primaryImage"].split("?", 1)[0]).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png"}:
            ext = ".jpg"
        dest = ASSETS / f"{item['id']}{ext}"
        download(meta["primaryImage"], dest)
        (METADATA / f"{item['id']}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"PUBLIC_DOMAIN_OK {item['id']} -> {dest.name}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
