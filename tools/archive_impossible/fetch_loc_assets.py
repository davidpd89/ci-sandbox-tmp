#!/usr/bin/env python3
"""Download the exact LOC source assets declared by IG-11 and preserve metadata.

Usage:
  python tools/archive_impossible/fetch_loc_assets.py \
    tools/archive_impossible/ig11_manifest.json \
    --out assets/archive_impossible

Dependency: requests
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import requests

UA = "David-Porto-RRSS-Archive-Puzzle/1.0 (+https://davidportodiaz.com/)"


def normalize_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        p = urlsplit(url)
        return urlunsplit(("https", p.netloc, p.path, p.query, p.fragment))
    return url


def strings(obj: Any) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from strings(value)


def candidate_score(url: str) -> int:
    u = url.lower().split("?", 1)[0]
    if not re.search(r"\.(jpe?g)$", u):
        return -10000
    score = 0
    if u.endswith("v.jpg") or u.endswith("v.jpeg"):
        score += 1000
    if u.endswith("r.jpg") or u.endswith("r.jpeg"):
        score += 700
    if "_150px" in u or "150px" in u:
        score -= 1000
    if "/master/" in u:
        score += 300
    if "/service/" in u or "/storage-services/" in u:
        score += 180
    # Prefer LOC-owned delivery hosts.
    if "loc.gov" in u:
        score += 100
    # Slight preference for longer file paths because they often identify full resources.
    score += min(len(u), 250) // 10
    return score


def api_url(item_url: str) -> str:
    base = item_url.rstrip("/") + "/"
    return base + "?fo=json&at=item,resources"


def first_text(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def verify_expected(ep: dict[str, Any], meta: dict[str, Any]) -> list[str]:
    item = meta.get("item") or {}
    blob = json.dumps(item, ensure_ascii=False).lower()
    problems: list[str] = []
    for field in ("expected_reproduction", "expected_date", "expected_creator", "expected_rights_phrase"):
        expected = str(ep.get(field, "")).strip()
        if expected and expected.lower() not in blob:
            problems.append(f"{field} not found in current LOC item JSON: {expected}")
    return problems


def download_episode(ep: dict[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    url = api_url(ep["item_url"])
    response = requests.get(url, headers={"User-Agent": UA}, timeout=45)
    response.raise_for_status()
    meta = response.json()

    problems = verify_expected(ep, meta)
    if problems:
        raise RuntimeError(ep["id"] + " metadata verification failed:\n- " + "\n- ".join(problems))

    urls = []
    for s in strings(meta):
        s = normalize_url(s.strip())
        if s.startswith("https://") and re.search(r"\.jpe?g(?:\?.*)?$", s.lower()):
            urls.append(s)
    urls = sorted(set(urls), key=candidate_score, reverse=True)
    if not urls or candidate_score(urls[0]) < 0:
        raise RuntimeError(f"No usable JPEG found for {ep['item_url']}")

    chosen = urls[0]
    img = requests.get(chosen, headers={"User-Agent": UA}, timeout=60)
    img.raise_for_status()
    asset_path = out / ep["asset_filename"]
    asset_path.write_bytes(img.content)

    item = meta.get("item") or {}
    record = {
        "episode_id": ep["id"],
        "item_url": ep["item_url"],
        "display_source_url": ep.get("display_source_url", ep["item_url"]),
        "api_url": url,
        "download_url": chosen,
        "title": item.get("title"),
        "creator": item.get("contributor_names") or item.get("contributors"),
        "date": item.get("date") or item.get("date_issued") or item.get("created_published"),
        "rights_advisory": item.get("rights_advisory"),
        "rights": item.get("rights"),
        "reproduction_number": item.get("reproduction_number"),
        "digital_id": item.get("digital_id"),
        "asset_path": str(asset_path),
        "expected": {k: ep.get(k) for k in ("expected_reproduction","expected_date","expected_creator","expected_rights_phrase")},
        "verified_against_current_json": True
    }
    (out / ep["metadata_filename"]).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{ep['id']}: {chosen} -> {asset_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    for ep in manifest["episodes"]:
        download_episode(ep, args.out)


if __name__ == "__main__":
    main()
