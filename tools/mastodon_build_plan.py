"""Expande decisiones Mxxx/Mxxx-Px a un plan Mastodon ejecutable.

Entrada de decisiones:
{
  "actions": [
    {"candidate": "M001", "kind": "follow"},
    {"post": "M001-P1", "kind": "reply", "text": "..."}
  ]
}
No impone cuota por tipo de acción: conserva únicamente propuestas válidas del scan
más la decisión editorial explícita.
"""
from __future__ import annotations

import sys

import scan_common as _sc
from candidate_identity import resolve_author, resolve_post_ref
from reply_provenance import carry_decision_proof

VALID = {"follow", "favourite", "boost", "reply"}
TEXT_KINDS = {"reply"}


def build(scan, decisions):
    if not isinstance(scan, dict):
        raise ValueError("state Mastodon debe ser objeto JSON")
    if not isinstance(decisions, dict) or not isinstance(decisions.get("actions"), list):
        raise ValueError("decisions debe contener actions[]")

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

    pool = {
        str(row.get("acct") or "").casefold(): row
        for row in scan.get("follow_pool") or []
        if row.get("acct")
    }

    plan = []
    seen = set()
    for index, decision in enumerate(decisions["actions"], start=1):
        if not isinstance(decision, dict):
            raise ValueError(f"decisión {index}: debe ser objeto")
        kind = decision.get("kind")
        if kind not in VALID:
            raise ValueError(f"decisión {index}: kind inválido {kind!r}")
        if kind == "follow" and decision.get("account"):
            entry = pool.get(str(decision["account"]).casefold())
            if not entry:
                raise ValueError(
                    f"decisión {index}: account fuera de follow_pool {decision['account']!r}"
                )
            row = {
                "handle": resolve_author("mastodon", entry),
                "kind": kind,
                "lane": "pool",
                "account_id": entry.get("account_id"),
                "motivo": (
                    "growth:follow_pool:"
                    f"followers={entry['followers']},following={entry['following_count']}"
                    + (f":src={entry['first_source']}" if entry.get("first_source") else "")
                ),
            }
            key = (kind, entry["acct"].casefold())
        elif kind == "follow":
            cid = decision.get("candidate")
            candidate = candidates.get(cid)
            if not candidate:
                raise ValueError(f"decisión {index}: candidate desconocido {cid!r}")
            if kind not in (candidate.get("actions") or []):
                raise ValueError(f"decisión {index}: follow no propuesto para {cid}")
            row = {
                "handle": resolve_author("mastodon", candidate),
                "kind": kind,
                "lane": candidate.get("lane", "unknown"),
                "account_id": candidate.get("account_id"),
                "motivo": f"growth:{cid}:" + ",".join(candidate.get("sources") or []) + (f":src={candidate['first_source']}" if candidate.get("first_source") else ""),
            }
            key = (kind, candidate["acct"].casefold())
        else:
            pid = decision.get("post")
            pair = posts.get(pid)
            if not pair:
                raise ValueError(f"decisión {index}: post desconocido {pid!r}")
            candidate, post = pair
            # Las decisiones nuevas atan el ID compacto a la referencia remota.
            # Las manuales antiguas sin post_uri conservan compatibilidad.
            if decision.get("post_uri") is not None and decision["post_uri"] != resolve_post_ref("mastodon", post):
                raise ValueError(f"decisión {index}: referencia remota distinta tras reescaneo")
            if kind not in (post.get("actions") or []):
                raise ValueError(f"decisión {index}: {kind} no propuesto para {pid}")
            row = {
                "handle": resolve_author("mastodon", candidate),
                "kind": kind,
                "lane": candidate.get("lane", "unknown"),
                "url": post["url"],
                "status_id": str(post["status_id"]),
                "created_at": post.get("created_at") or "",
                "post_created_at": post.get("created_at") or "",
                "motivo": f"growth:{pid}:" + ",".join(post.get("sources") or []) + (f":src={candidate['first_source']}" if candidate.get("first_source") else ""),
            }
            key = row["status_id"]
            if kind in TEXT_KINDS:
                text = decision.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(f"decisión {index}: {kind} exige text")
                row["text"] = text.strip()
                _sc.opinion_guard(post.get("text", ""), row["text"])
                row["post_text"] = post.get("text", "")  # contexto para el filtro de opinion del ejecutor
                row = carry_decision_proof(row, decision, "mastodon", post.get("text", ""))
                if row is None:
                    continue
        if key in seen:
            raise ValueError(f"decisión {index}: acción duplicada {key}")
        seen.add(key)
        plan.append(row)
    return plan


def main(argv=None):
    import json
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 3:
        print(__doc__)
        return 1
    state_path, decisions_path, plan_path = argv
    with open(state_path, encoding="utf-8") as stream:
        state = json.load(stream)
    with open(decisions_path, encoding="utf-8") as stream:
        decisions = json.load(stream)
    plan = build(state, decisions)
    with open(plan_path, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Plan Mastodon: {len(plan)} acciones -> {plan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
