"""Construye plan.json desde IDs compactos del growth scan de Bluesky.

La IA no repite handles ni URLs. Devuelve decisiones mínimas:
{
  "actions": [
    {"candidate": "G003", "kind": "follow"},
    {"post": "G003-P1", "kind": "like"},
    {"post": "G007-P1", "kind": "reply", "text": "..."}
  ]
}

Uso:
    python tools/bluesky_build_plan.py scan.json decisions.json plan.json
"""
from __future__ import annotations

import json
import sys

import scan_common as _sc
from candidate_identity import resolve_post_ref

VALID = {"follow", "like", "repost", "reply", "quote"}
TEXT_KINDS = {"reply", "quote"}


def _indexes(scan):
    candidates = {}
    posts = {}
    for candidate in scan.get("shortlist") or []:
        cid = candidate.get("id")
        if not cid or cid in candidates:
            raise ValueError("shortlist con candidate id inválido/duplicado")
        candidates[cid] = candidate
        for post in candidate.get("posts") or []:
            pid = post.get("id")
            if not pid or pid in posts:
                raise ValueError("shortlist con post id inválido/duplicado")
            posts[pid] = (candidate, post)
    return candidates, posts


def build(scan, decisions):
    if not isinstance(scan, dict):
        raise ValueError("scan debe ser objeto JSON")
    if not isinstance(decisions, dict) or not isinstance(decisions.get("actions"), list):
        raise ValueError("decisions debe contener actions[]")
    candidates, posts = _indexes(scan)
    plan = list(scan.get("auto_plan") or [])

    for index, decision in enumerate(decisions["actions"], start=1):
        if not isinstance(decision, dict):
            raise ValueError(f"decisión {index}: debe ser objeto")
        kind = decision.get("kind")
        if kind not in VALID:
            raise ValueError(f"decisión {index}: kind inválido {kind!r}")

        if kind == "follow":
            cid = decision.get("candidate")
            candidate = candidates.get(cid)
            if not candidate:
                raise ValueError(f"decisión {index}: candidate desconocido {cid!r}")
            if "follow" not in (candidate.get("actions") or []):
                raise ValueError(f"decisión {index}: follow no propuesto para {cid}")
            lane = candidate.get("lane") or "unknown"
            row = {
                "handle": candidate["handle"],
                "kind": "follow",
                "lane": lane,
                "motivo": (
                    f"growth:{cid}:lane={lane}:"
                    + ",".join(candidate.get("sources") or [])
                ),
            }
        else:
            pid = decision.get("post")
            pair = posts.get(pid)
            if not pair:
                raise ValueError(f"decisión {index}: post desconocido {pid!r}")
            candidate, post = pair
            # Las decisiones nuevas atan el ID compacto a la referencia remota.
            # Las manuales antiguas sin post_uri conservan compatibilidad.
            if decision.get("post_uri") is not None and decision["post_uri"] != resolve_post_ref("bluesky", post):
                raise ValueError(f"decisión {index}: referencia remota distinta tras reescaneo")
            if kind not in (post.get("actions") or []):
                raise ValueError(
                    f"decisión {index}: {kind} no propuesto para {pid}"
                )
            lane = candidate.get("lane") or "unknown"
            row = {
                "handle": candidate["handle"],
                "kind": kind,
                "lane": lane,
                "url": post["url"],
                "motivo": (
                    f"growth:{pid}:lane={lane}:"
                    + ",".join(post.get("sources") or [])
                ),
            }
            if kind in TEXT_KINDS:
                text = decision.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(f"decisión {index}: {kind} exige text")
                row["text"] = text.strip()
                _sc.opinion_guard(post.get("text", ""), row["text"])
                row["post_text"] = post.get("text", "")  # contexto para el filtro de opinion del ejecutor
        plan.append(row)

    # Dedupe exacto. El preflight del executor conserva la última barrera por AT-URI.
    unique = []
    seen = set()
    for row in plan:
        key = (row.get("kind"), row.get("handle"), row.get("url"), row.get("text"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 3:
        print(__doc__)
        return 1
    scan_path, decisions_path, output_path = argv
    with open(scan_path, encoding="utf-8") as stream:
        scan = json.load(stream)
    with open(decisions_path, encoding="utf-8") as stream:
        decisions = json.load(stream)
    plan = build(scan, decisions)
    with open(output_path, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Plan construido: {len(plan)} acciones -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
