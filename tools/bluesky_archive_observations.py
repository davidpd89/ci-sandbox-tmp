"""Puente offline del JSONL de ruggsea/bluesky-firehose-py (MIT) a observaciones.

Acepta registros YA capturados; nunca abre WebSocket, red, sesión ni archivos.
No sustituye el colector Jetstream v1/v2 ni decide acciones sociales.
Contrato de salida compatible con hashtag_expansion.build_snapshot (#63).
"""
from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence

DID = re.compile(r"did:(?:plc:[a-z2-7]{24}|web:[A-Za-z0-9.:%-]+)\Z")
RKEY = re.compile(r"[A-Za-z0-9._~-]{1,256}\Z")
MAX_EVENTS = 10_000


def _when(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(dt.timezone.utc).isoformat()


def normalize_archive_events(rows: Sequence):
    """Normaliza formatos posts-only y all-records de ruggsea, sin IO.

    Múltiples versiones incompatibles del mismo post se descartan; un evento
    delete en el lote prevalece sin importar el orden de entrada. El resultado
    es una *observación* de un archivo, nunca prueba de publicación actual.
    """
    if not isinstance(rows, (list, tuple)) or len(rows) > MAX_EVENTS:
        raise ValueError("archive rows must be a bounded sequence")
    posts, conflicts, deleted = {}, set(), set()
    diagnostics = {"input": len(rows), "invalid": 0, "non_spanish_or_unknown": 0,
                   "duplicates": 0, "conflicts": 0, "deletions": 0}
    for event in rows:
        if not isinstance(event, Mapping):
            diagnostics["invalid"] += 1
            continue
        outer_commit = event.get("commit") if event.get("kind") == "commit" else None
        if outer_commit is not None:
            if not isinstance(outer_commit, Mapping) or outer_commit.get("collection") != "app.bsky.feed.post":
                diagnostics["invalid"] += 1
                continue
            op, rkey, record = outer_commit.get("operation"), outer_commit.get("rkey"), outer_commit.get("record")
        else:
            if event.get("kind") is not None or event.get("commit") is not None:
                diagnostics["invalid"] += 1
                continue
            op, rkey, record = "create", event.get("rkey"), event.get("record")
        did = event.get("did")
        if (not isinstance(did, str) or len(did) > 200 or not DID.fullmatch(did) or
                not isinstance(rkey, str) or not RKEY.fullmatch(rkey)):
            diagnostics["invalid"] += 1
            continue
        pid = f"at://{did}/app.bsky.feed.post/{rkey}"
        if len(pid) > 256:
            diagnostics["invalid"] += 1
            continue
        if op == "delete":
            diagnostics["deletions"] += 1
            deleted.add(pid)
            posts.pop(pid, None)
            continue
        if op != "create" or not isinstance(record, Mapping):
            diagnostics["invalid"] += 1
            continue
        text, langs = record.get("text"), record.get("langs")
        if (not isinstance(text, str) or not text.strip() or len(text) > 10_000 or
                not isinstance(langs, list) or not langs or
                not all(isinstance(lang, str) for lang in langs)):
            diagnostics["invalid"] += 1
            continue
        if not any(lang.casefold().replace("_", "-").split("-", 1)[0] == "es" for lang in langs):
            diagnostics["non_spanish_or_unknown"] += 1
            continue
        stamp = _when(record.get("createdAt"))
        if stamp is None:
            diagnostics["invalid"] += 1
            continue
        tags = record.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) and len(tag) <= 64 for tag in tags):
            diagnostics["invalid"] += 1
            continue
        candidate = {"network": "bluesky", "source": "ruggsea_jetstream_archive",
                     "post_id": pid, "author_id": did,
                     "created_at": stamp, "text": text, "tags": tags}
        if pid in posts:
            if posts[pid] == candidate:
                diagnostics["duplicates"] += 1
            else:
                conflicts.add(pid)
                diagnostics["conflicts"] += 1
        else:
            posts[pid] = candidate
    return {"observations": [posts[k] for k in sorted(posts) if k not in deleted | conflicts],
            "diagnostics": diagnostics}
