"""Construye un plan TikTok nativo desde IDs compactos Txxx/Txxx-Px.

La IA solo devuelve decisiones sobre el shortlist. El builder reconstruye handles,
URLs y contexto sin obligar a repetir dumps de UI o captions completos.
"""
from __future__ import annotations

import json
import sys

VALID = {"follow", "like", "comment"}
TEXT_KINDS = {"comment"}


def build(scan, decisions):
    if not isinstance(scan, dict) or not isinstance(scan.get("shortlist"), list):
        raise ValueError("scan TikTok inválido")
    if not isinstance(decisions, dict) or not isinstance(decisions.get("actions"), list):
        raise ValueError("decisions debe contener actions[]")

    candidates = {}
    posts = {}
    for candidate in scan["shortlist"]:
        cid = candidate.get("id")
        if not cid or cid in candidates:
            raise ValueError("candidate id inválido/duplicado")
        candidates[cid] = candidate
        for post in candidate.get("posts") or []:
            pid = post.get("id")
            if not pid or pid in posts:
                raise ValueError("post id inválido/duplicado")
            posts[pid] = (candidate, post)

    blocked = {str(h).lstrip("@").casefold() for h in (decisions.get("exclude") or [])}
    plan = [
        row for row in (scan.get("auto_plan") or [])
        if str(row.get("handle", "")).casefold() not in blocked
    ]
    auto_keys = {
        (row["kind"], row["handle"].casefold() if row["kind"] == "follow" else row.get("url"))
        for row in plan
    }
    seen = set()
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
            if kind not in (candidate.get("actions") or []):
                raise ValueError(f"decisión {index}: follow no propuesto para {cid}")
            row = {
                "kind": "follow",
                "handle": candidate["handle"],
                "motivo": f"growth:{cid}:" + ",".join(candidate.get("sources") or []),
            }
            key = ("follow", candidate["handle"].casefold())
        else:
            pid = decision.get("post")
            pair = posts.get(pid)
            if not pair:
                raise ValueError(f"decisión {index}: post desconocido {pid!r}")
            candidate, post = pair
            if kind not in (post.get("actions") or []):
                raise ValueError(f"decisión {index}: {kind} no propuesto para {pid}")
            url = post.get("url")
            if not isinstance(url, str) or not url.startswith(("https://", "tt://")):
                raise ValueError(
                    f"decisión {index}: {kind} exige permalink TikTok estable"
                )
            row = {
                "kind": kind,
                "handle": candidate["handle"],
                "url": url,
                "post_ref": post.get("post_ref"),
                "post_created_at": post.get("created_at") or post.get("create_time") or post.get("created_time") or "",
                "post_resumen": (post.get("caption") or "")[:500],
                "motivo": f"growth:{pid}:{post.get('source') or 'unknown'}",
            }
            key = (kind, url)
            if kind in TEXT_KINDS:
                text = decision.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(f"decisión {index}: comment exige text")
                row["text"] = text.strip()
        if key in auto_keys:
            continue  # ya decidida mecánicamente (auto_plan)
        if key in seen:
            raise ValueError(f"decisión {index}: acción duplicada")
        seen.add(key)
        plan.append(row)
    return plan


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
    print(f"Plan TikTok nativo: {len(plan)} acciones -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
