"""Expansion offline de etiquetas a partir de posts observados por adaptadores.

No efectua llamadas de red, no publica y no lee ni modifica estados de cuentas.
Python 3.11; entradas JSON de colectores externos; salida agregada sin identidades.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

NETWORKS = frozenset(("x", "threads", "facebook", "pinterest", "reddit",
                      "bluesky", "mastodon", "tiktok", "instagram"))
TAG_NETWORKS = NETWORKS - {"reddit"}
TAG_RE = re.compile(r"(?<![\w#])#([^\W\d_][\w]{1,47})", re.UNICODE)
VALID = re.compile(r"[^\W\d_][\w]{1,47}\Z", re.UNICODE)
NOISE = ("sorteo", "gratis", "giveaway", "descarga", "casino",
         "crypto", "cripto", "followback", "f4f", "nsfw")
DEFAULT_SEEDS = {
    "fantasia": ["fantasía", "romantasy", "novela fantástica"],
    "lectura": ["lectura", "leyendo", "reseña de libro"],
    "escritura": ["escribiendo", "manuscrito", "corrección de novela"],
    "libro": ["libro juvenil", "nueva novela"],
    "actualidad": ["feria del libro", "novedad editorial"],
}
DEFAULT_CACHE = Path(__file__).resolve().parents[1] / "00_OPERATIVO" / "hashtag_expansion.json"


def fold(text):
    text = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def tag(value):
    # La identidad de una etiqueta no debe confundir año/ano o niño/nino.
    # NFC une las representaciones Unicode equivalentes sin borrar tildes.
    value = unicodedata.normalize("NFC", str(value).strip().lstrip("#"))
    return value.casefold() if VALID.fullmatch(value) else ""


def instant(value):
    if not isinstance(value, str):
        raise ValueError("fecha no es cadena")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("fecha sin zona")
    return parsed.astimezone(timezone.utc)


def extract(text, declared=None):
    text = unicodedata.normalize("NFC", text)
    found = {tag(m.group(1)) for m in TAG_RE.finditer(text)}
    if declared is not None:
        if not isinstance(declared, list):
            raise ValueError("tags debe ser una lista")
        found.update(tag(value) for value in declared)
    return {x for x in found if x and not any(noise in fold(x) for noise in NOISE)}


def _has_seed(text, seed):
    seed = fold(seed).strip()
    return bool(seed and re.search(r"(?<!\w)" + re.escape(seed) + r"(?!\w)", text))


def _feedback(rows):
    """Agrega resultados por etiqueta sin repetir eventos ni ventanas.

    El productor puede entregar (event_id, window) para distinguir ventanas
    genuinas con igual resultado. En el legado sin esas claves, solo se
    eliminan filas *exactamente* iguales dentro de una misma ingesta.
    """
    unkeyed, keyed, conflicts = set(), {}, set()
    for row in rows:
        try:
            network, label = row["network"], tag(row["tag"])
            values = tuple(row.get(k, 0) for k in
                           ("eligible", "engaged", "replies", "followers"))
            eligible, engaged, replies, follows = values
            if (network not in NETWORKS or not label or
                    any(type(v) is not int or v < 0 for v in values) or
                    engaged > eligible or
                    (eligible == 0 and (engaged or replies or follows))):
                continue
            has_event = "event_id" in row or "window" in row
            if has_event:
                identifier = row.get("event_id")
                if (not isinstance(identifier, str) or
                        not 0 < len(identifier.strip()) <= 256 or
                        any(ord(ch) < 32 for ch in identifier)):
                    continue
                window = instant(row["window"]).isoformat()
                key = (network, label, window, identifier.strip())
                if key in conflicts:
                    continue
                if key in keyed:
                    if keyed[key] != values:
                        # Dos versiones del mismo evento: no elegir al azar.
                        del keyed[key]
                        conflicts.add(key)
                else:
                    keyed[key] = values
            else:
                unkeyed.add((network, label, values))
        except (KeyError, ValueError, TypeError, OverflowError):
            continue

    result = defaultdict(lambda: [0, 0, 0, 0])
    for network, label, values in unkeyed:
        for i, value in enumerate(values):
            result[network, label][i] += value
    for (network, label, _window, _event), values in keyed.items():
        for i, value in enumerate(values):
            result[network, label][i] += value
    return result

def build_snapshot(observations, *, seeds=None, feedback=(), now=None,
                   max_post_age_days=14, ttl_hours=48, min_authors=2,
                   max_per_network=10):
    """Ranking por coocurrencia temática, autores, frescura y resultado medido.

    Observaciones: network, source, post_id, author_id, created_at, text, tags?.
    Una misma publicación vista en varios colectores conserva sus fuentes.
    """
    now = instant(now) if isinstance(now, str) else (now or datetime.now(timezone.utc))
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now sin zona")
    now = now.astimezone(timezone.utc)
    seeds = DEFAULT_SEEDS if seeds is None else seeds
    if not (isinstance(observations, list) and isinstance(feedback, (list, tuple))
            and isinstance(seeds, dict) and seeds and
            all(isinstance(k, str) and k.strip() and isinstance(v, list)
                and v and all(isinstance(s, str) and s.strip() for s in v)
                for k, v in seeds.items()) and
            0 < max_post_age_days <= 365 and 0 < ttl_hours <= 168 and
            min_authors >= 1 and 1 <= max_per_network <= 100):
        raise ValueError("datos o limites invalidos")
    posts = {}
    diagnostic = {"input": len(observations), "invalid": 0, "stale": 0, "duplicates": 0}
    for row in observations:
        try:
            network = row["network"]
            source, pid, author = (row[k] for k in ("source", "post_id", "author_id"))
            if (network not in NETWORKS or not all(isinstance(x, str) and
                    0 < len(x.strip()) <= 256 for x in (source, pid, author))):
                raise ValueError("identidad invalida")
            date = instant(row["created_at"])
            text = row["text"]
            if not isinstance(text, str) or len(text) > 10000:
                raise ValueError("texto invalido")
            tags = extract(text, row.get("tags"))
        except (KeyError, TypeError, ValueError, OverflowError):
            diagnostic["invalid"] += 1
            continue
        if date > now or now - date > timedelta(days=max_post_age_days):
            diagnostic["stale"] += 1
            continue
        key = network, pid
        if key in posts:
            diagnostic["duplicates"] += 1
            if posts[key]["author"] == author and posts[key]["text"] == text:
                posts[key]["sources"].add(source)
            continue
        posts[key] = {"network": network, "author": author, "text": text,
                      "folded": fold(text), "date": date, "tags": tags,
                      "sources": {source}}
    diagnostic["unique"] = len(posts)
    totals = defaultdict(set)
    pairs = defaultdict(lambda: {"posts": set(), "authors": set(),
                                 "sources": set(), "latest": None})
    for (network, pid), item in posts.items():
        for candidate in item["tags"]:
            totals[network, candidate].add(pid)
        for topic, expressions in seeds.items():
            if not any(_has_seed(item["folded"], x) for x in expressions):
                continue
            exclude = {tag(seed) for seed in expressions}
            for candidate in item["tags"] - exclude:
                stat = pairs[network, topic, candidate]
                stat["posts"].add(pid)
                stat["authors"].add(item["author"])
                stat["sources"].update(item["sources"])
                if stat["latest"] is None or item["date"] > stat["latest"]:
                    stat["latest"] = item["date"]
    outcomes = _feedback(feedback)
    by_network = defaultdict(list)
    for (network, topic, candidate), stat in pairs.items():
        authors, count = len(stat["authors"]), len(stat["posts"])
        assoc = count / len(totals[network, candidate])
        if authors < min_authors or assoc < 0.6:
            continue
        eligible, engaged, replies, followers = outcomes[network, candidate]
        yield_rate = min(1.0, (engaged + 1) / (eligible + 2) +
                         0.05 * min(replies + 2 * followers, eligible) / max(eligible, 1))
        age = (now - stat["latest"]).total_seconds() / 86400
        score = round(0.55 * assoc + 0.2 * min(authors / 5, 1) +
                      0.15 * max(0, 1 - age / max_post_age_days) +
                      0.1 * yield_rate, 4)
        by_network[network].append({
            "tag": candidate, "topic": topic, "score": score,
            "authors": authors, "posts": count, "association": round(assoc, 4),
            "sources": sorted(stat["sources"]), "feedback_eligible": eligible})
    networks = {}
    for network in sorted(NETWORKS):
        buckets = defaultdict(list)
        for row in by_network[network]:
            buckets[row["topic"]].append(row)
        for rows in buckets.values():
            rows.sort(key=lambda row: (-int(row["score"] * 10),
                hashlib.sha256((now.date().isoformat() + network + row["tag"]).encode()).hexdigest()))
        selected, used, topics = [], set(), sorted(buckets)
        while topics and len(selected) < max_per_network:
            remaining = []
            for topic in topics:
                while buckets[topic] and buckets[topic][0]["tag"] in used:
                    buckets[topic].pop(0)
                if not buckets[topic]:
                    continue
                row = buckets[topic].pop(0)
                selected.append(row)
                used.add(row["tag"])
                if buckets[topic]:
                    remaining.append(topic)
                if len(selected) == max_per_network:
                    break
            topics = remaining
        selected.sort(key=lambda row: -row["score"])
        tags = [row["tag"] for row in selected]
        networks[network] = {"hashtags": tags if network in TAG_NETWORKS else [],
                             "busquedas": tags, "candidates": selected}
    diagnostic["qualified"] = sum(map(len, by_network.values()))
    diagnostic["selected"] = sum(len(x["candidates"]) for x in networks.values())
    return {"schema": 1, "as_of": now.isoformat(),
            "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(),
            "networks": networks, "diagnostics": diagnostic}


def snapshot_terms(network, kind="hashtags", *, path=None, now=None):
    """Una cache corrupta, ausente o caducada equivale a lista vacia."""
    if network not in NETWORKS or kind not in ("hashtags", "busquedas"):
        return []
    path = DEFAULT_CACHE if path is None else Path(path)
    try:
        if path.stat().st_size > 2_000_000:
            return []
        snap = json.loads(path.read_text(encoding="utf-8"))
        now = instant(now) if isinstance(now, str) else (now or datetime.now(timezone.utc))
        if (now.tzinfo is None or now.utcoffset() is None or snap["schema"] != 1 or
                not (instant(snap["as_of"]) <= now <= instant(snap["expires_at"]))):
            return []
        items = snap["networks"][network][kind]
        if not isinstance(items, list) or len(items) > 100:
            return []
        output = []
        for raw in items:
            normalized = tag(raw)
            if not normalized:
                return []
            if normalized not in output:
                output.append(normalized)
        return output
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return []


def save_snapshot(path, snapshot):
    """Exportacion solicitada explicitamente, atomica incluso en Windows."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=target.parent, encoding="utf-8",
                                         prefix=".hashtag-", suffix=".tmp", delete=False) as file:
            temp = Path(file.name)
            json.dump(snapshot, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main(argv=None):
    cli = argparse.ArgumentParser(description="Ranking offline, sin acceso a redes")
    cli.add_argument("--observations", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--now", required=True)
    cli.add_argument("--seeds", type=Path)
    cli.add_argument("--feedback", type=Path)
    args = cli.parse_args(argv)
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    snap = build_snapshot(read(args.observations),
                          seeds=read(args.seeds) if args.seeds else None,
                          feedback=read(args.feedback) if args.feedback else (),
                          now=args.now)
    save_snapshot(args.output, snap)
    print(json.dumps(snap["diagnostics"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
