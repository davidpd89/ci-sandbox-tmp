"""Ingesta OFFLINE de resultados SERP hacia una revisión humana multirred.

Adaptado del esquema get_serp_results (src/api.py) y de la deduplicación
remove_duplicates_serp_results (src/utils.py) de HasData/social-listening-tool
MIT, commit 086ddc5894c6c3c8b48841496f1dc339db299899.
Sin conexión a HasData, Meta ni a cuentas; NO crea acciones ni observaciones reales.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

NETWORKS = frozenset({"facebook", "instagram", "threads", "x", "bluesky",
                      "mastodon", "pinterest", "reddit", "tiktok"})
HOSTS = {
    "facebook": {"facebook.com", "www.facebook.com", "m.facebook.com"},
    "instagram": {"instagram.com", "www.instagram.com"},
    "threads": {"threads.net", "www.threads.net", "threads.com", "www.threads.com"},
    "x": {"x.com", "www.x.com", "twitter.com", "www.twitter.com"},
    "bluesky": {"bsky.app"},
    "pinterest": {"pinterest.com", "www.pinterest.com", "es.pinterest.com"},
    "reddit": {"reddit.com", "www.reddit.com", "old.reddit.com"},
    "tiktok": {"tiktok.com", "www.tiktok.com", "m.tiktok.com"},
}
TRACKERS = frozenset({"fbclid", "gclid", "igshid", "ref_src", "ref_url"})
INTENTS = (
    ("pide_recomendacion", re.compile(r"(?:\brecomend[a-záéíóúñ]+\b|\bqu[eé] (?:libro|saga|novela) (?:me |nos )?(?:recomend[aá]is|recomiendan)\b|\bbusco (?:un |una )?(?:libro|novela|romantasy)\b)", re.I)),
    ("debate_lector", re.compile(r"\b(?:tropos?|enemies.to.lovers|final(?:es)?|personajes?|worldbuilding|fantas[ií]a|romantasy|club de lectura)\b", re.I)),
    ("lectura_actual", re.compile(r"\b(?:leyendo|lectura actual|tbr|rese[nñ]a|lecturas del mes)\b", re.I)),
)
LITERARY = re.compile(r"\b(?:libros?|novelas?|sagas?|lectur(?:a|as)|lector(?:a|es|as)?|fantas[ií]a|romantasy|escritor(?:a|es|as)?|rese[nñ]as?|booktok|bookstagram)\b", re.I)
MAX_BATCH = 5000


def canonical_url(value: object) -> str | None:
    """Canoniza un enlace SERP solo para deduplicación local, no para navegar."""
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
        return None
    try:
        u = urlsplit(value)
        if u.scheme != "https" or not u.hostname or u.username or u.password or u.port not in (None, 443):
            return None
        host = u.hostname.lower()
        if len(host) > 253 or not re.fullmatch(r"[a-z0-9.-]+", host, re.ASCII) or ".." in host:
            return None
        if host.startswith("www.") and any(host[4:] in hosts for hosts in HOSTS.values()):
            host = host[4:]
        if host == "m.facebook.com":
            host = "facebook.com"
        if not u.path or u.path == "/":
            return None
        path = u.path.rstrip("/")
        query = urlencode(sorted((k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                                 if not k.lower().startswith("utm_") and k.lower() not in TRACKERS))
        return urlunsplit(("https", host, path, query, ""))
    except (ValueError, UnicodeError):
        return None


def network_and_surface(url: str, declared: object = None) -> tuple[str, str] | None:
    u = urlsplit(url)
    host, path = u.hostname or "", u.path
    net = next((name for name, hosts in HOSTS.items() if host in hosts), None)
    if net is None and declared == "mastodon" and re.fullmatch(r"/@[^/]+/\d+", path):
        net = "mastodon"  # dominio de instancia variable; requiere declaración explícita
    if net is None or (declared is not None and declared != net):
        return None
    if net == "facebook":
        if path.startswith("/groups/") or path == "/groups":
            return net, "group_manual"
        if re.fullmatch(r"/[^/]+/(?:posts|permalink)/[a-zA-Z0-9._-]+", path) and not u.query:
            return net, "page_post_unverified"
        return net, "ambiguous_manual"
    if net == "reddit" and "/comments/" not in path:
        return net, "community_manual"
    return net, "post_unverified"


def _strength(row: dict) -> tuple[int, int, int]:
    text = (str(row.get("title") or "") + " " + str(row.get("snippet") or ""))[:2000]
    return (int(bool(LITERARY.search(text))), int(bool(INTENTS[0][1].search(text))), len(text))


def dedupe_serp(results: list[dict]) -> tuple[list[tuple[dict, str]], Counter]:
    """Adaptación de remove_duplicates_serp_results: URL canónica y errores medidos."""
    unique, seen, stats = [], {}, Counter()
    for row in results:
        if not isinstance(row, dict):
            stats["invalid_row"] += 1
            continue
        url = canonical_url(row.get("link"))
        if not url:
            stats["invalid_url"] += 1
        elif url in seen:
            stats["duplicate"] += 1
            index = seen[url]
            if _strength(row) > _strength(unique[index][0]):
                unique[index] = (row, url)
        else:
            seen[url] = len(unique)
            unique.append((row, url))
    return unique, stats


def import_results(results: list[dict]) -> dict:
    """Nueve adaptadores de enlace; ninguna pista SERP acredita recencia ni permisos."""
    if not isinstance(results, list) or len(results) > MAX_BATCH:
        raise ValueError("Se requiere una lista de hasta 5000 resultados")
    unique, counters = dedupe_serp(results)
    candidates = []
    for row, url in unique:
        surface = network_and_surface(url, row.get("network"))
        if not surface:
            counters["unsupported_or_mismatched_network"] += 1
            continue
        network, kind = surface
        title = row.get("title") if isinstance(row.get("title"), str) else ""
        snippet = row.get("snippet") if isinstance(row.get("snippet"), str) else ""
        text = (title + " " + snippet)[:2000]
        if not LITERARY.search(text):
            counters["without_literary_evidence"] += 1
            continue
        intent = next((name for name, pattern in INTENTS if pattern.search(text)), "interes_lector")
        candidates.append({"network": network, "url": url, "surface": kind,
                           "intent": intent, "source_kind": "serp_snippet",
                           "published_at": None, "author_id_verified": False,
                           "permission_verified": False, "action_allowed": False,
                           "review_required": True})
        counters["review_" + network] += 1
    return {"schema_version": 1, "candidates": candidates,
            "counts": {key: counters[key] for key in sorted(counters)},
            "input_count": len(results), "review_count": len(candidates)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Revisar resultados SERP sin conexión ni acciones")
    parser.add_argument("input", type=Path, help="JSON local: lista, o {organicResults:[...]}")
    parser.add_argument("--output", type=Path, help="Archivo local; sin opción, salida estándar")
    args = parser.parse_args(argv)
    data = json.loads(args.input.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("organicResults")
    report = import_results(data)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
