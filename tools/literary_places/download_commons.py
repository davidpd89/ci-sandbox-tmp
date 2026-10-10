#!/usr/bin/env python3
"""Descarga fotos exactas de Wikimedia Commons para IG-13 y valida licencia/autor."""

from __future__ import annotations
import html
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
ASSETS = ROOT / "assets"
METADATA = ROOT / "metadata"
API = "https://commons.wikimedia.org/w/api.php"

def strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()

def query_file(title: str) -> dict:
    params = {
        "action":"query","format":"json","prop":"imageinfo",
        "iiprop":"url|extmetadata","titles":title
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent":"AutoraDemo-RRSS/IG13"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    page = next(iter(data["query"]["pages"].values()))
    if "missing" in page or not page.get("imageinfo"):
        raise RuntimeError(f"Commons file missing: {title}")
    return page["imageinfo"][0]

def download(url: str, dest: pathlib.Path):
    req = urllib.request.Request(url, headers={"User-Agent":"AutoraDemo-RRSS/IG13"})
    with urllib.request.urlopen(req, timeout=60) as response, dest.open("wb") as fh:
        fh.write(response.read())

def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ASSETS.mkdir(parents=True, exist_ok=True)
    METADATA.mkdir(parents=True, exist_ok=True)
    for item in manifest["items"]:
        info = query_file(item["commons_file_title"])
        meta = info.get("extmetadata", {})
        license_short = strip_html(meta.get("LicenseShortName",{}).get("value",""))
        artist = strip_html(meta.get("Artist",{}).get("value",""))
        if item["expected_license"].lower() not in license_short.lower():
            print(f"BLOCKED {item['id']} license: expected {item['expected_license']!r}, got {license_short!r}", file=sys.stderr)
            return 2
        if item["expected_artist"].lower() not in artist.lower():
            print(f"BLOCKED {item['id']} artist: expected {item['expected_artist']!r}, got {artist!r}", file=sys.stderr)
            return 3
        url = info["url"]
        suffix = pathlib.Path(urllib.parse.urlparse(url).path).suffix.lower()
        if suffix not in {".jpg",".jpeg",".png",".webp"}:
            suffix = ".jpg"
        dest = ASSETS / f"{item['id']}{suffix}"
        download(url, dest)
        record = {
            "commons_file_title": item["commons_file_title"],
            "url": url,
            "descriptionurl": info.get("descriptionurl"),
            "license": license_short,
            "artist": artist,
            "raw_extmetadata": meta,
        }
        (METADATA / f"{item['id']}.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"COMMONS_OK {item['id']} — {license_short} — {artist}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
