"""Cola de respuestas de Bluesky: las mejores ocasiones del ultimo scan para escribir 20-40 replies al dia a mano (05/10/2026).

GPT (consulta E): con 8.000 escrituras no se mantiene un porcentaje artificial de replies; si se pueden producir 20-40 buenas, se hacen 20-40 (~0,3-0,5 % del
volumen). Las replies son lo que mas conversacion y follow-back da, y es lo unico que escribe la IA: esta herramienta le deja delante solo posts que lo merecen.

Lee `growth_state.json` (el scan completo) y filtra: post en espanol del nicho (>=1 termino), reciente (<=3 dias), 60-280 caracteres, sin enlaces ni
etiquetas en cadena, que no sea promocion propia ni peticion de opinion sobre su trabajo, cuenta de 30-5.000 seguidores y a la que no hayamos escrito ya.
Ordena por afinidad (señal de nicho del post + conversacion) y reparte para no concentrar en una sola cuenta.

    python tools/bluesky_reply_queue.py [--n 40]                 # lista candidatos (id de post, cuenta, texto)
    python tools/bluesky_reply_queue.py plan decisiones.json     # decisiones = {"replies": [{"post": "G003-P1", "text": "..."}]} -> plan.json (via bluesky_build_plan)
Despues: python tools/bluesky_execute.py plan.json
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE = os.path.join(ROOT, "growth_state.json")
REGISTRO = os.path.join(ROOT, "SISTEMA_DIARIO_BLUESKY", "registro_interacciones.csv")
MAX_AGE_DAYS = 3


def _niche_hits(text):
    import bluesky_growth_scan as gs
    return gs._hits(text)


def _age(created, today):
    try:
        return (today - datetime.date.fromisoformat(str(created)[:10])).days
    except ValueError:
        return 99


def candidates(state, *, today=None, replied=frozenset(), limit=40):
    today = today or datetime.date.today()
    out, per_account = [], {}
    for item in state.get("shortlist") or []:
        followers = (item.get("profile") or {}).get("followers") or 0
        if not 30 <= followers <= 5000:
            continue
        if item["handle"].casefold() in replied:
            continue
        for post in item.get("posts") or []:
            text = (post.get("text") or "").replace("\n", " ").strip()
            if "reply" not in (post.get("actions") or []) or post.get("es") is False:
                continue
            if not 60 <= len(text) <= 280 or _age(post.get("created_at"), today) > MAX_AGE_DAYS:
                continue
            if re.search(r"https?://|www\.|(#\w+\s*){3,}", text) or sc.is_political(text) or sc.asks_for_opinion(text):
                continue
            hits = _niche_hits(text)
            if hits < 1:
                continue
            score = 3 * min(hits, 3) + (2 if sc.invites_conversation(text) else 0) + (1 if "?" in text else 0) + (1 if followers <= 1500 else 0)
            out.append({"post": post["id"], "handle": item["handle"], "followers": followers, "score": score, "text": text, "url": post.get("url")})
    out.sort(key=lambda row: (-row["score"], row["handle"]))
    picked = []
    for row in out:
        if per_account.get(row["handle"]):
            continue          # una sola respuesta por cuenta
        per_account[row["handle"]] = 1
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def _replied_handles(days=30, today=None):
    """Cuentas a las que ya escribimos una reply en los ultimos `days` dias (una persona no necesita dos respuestas nuestras en un mes)."""
    import csv
    today = today or datetime.date.today()
    out = set()
    try:
        with open(REGISTRO, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if "reply" in (row.get("tipo") or "").split("+") and _age(row.get("fecha"), today) <= days:
                    out.add((row.get("cuenta") or "").strip().lstrip("@").casefold())
    except OSError:
        pass
    return frozenset(out)


def build_plan(state, decisions):
    """Plan solo de replies (sin el auto_plan mecanico) a partir de las decisiones escritas a mano."""
    import bluesky_build_plan as bp
    actions = [{"post": row["post"], "kind": "reply", "text": row["text"]} for row in decisions.get("replies") or []]
    scan = {"shortlist": state.get("shortlist") or [], "auto_plan": []}
    return bp.build(scan, {"actions": actions})


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    with open(STATE, encoding="utf-8") as stream:
        state = json.load(stream)
    if argv and argv[0] == "plan":
        with open(argv[1], encoding="utf-8") as stream:
            decisions = json.load(stream)
        plan = build_plan(state, decisions)
        out = argv[2] if len(argv) > 2 else os.path.join(ROOT, "plan_replies.json")
        with open(out, "w", encoding="utf-8") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=1)
        print(f"{len(plan)} replies -> {out}")
        return 0
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 40
    rows = candidates(state, replied=_replied_handles(), limit=n)
    for row in rows:
        print(f"{row['post']} @{row['handle']} ({row['followers']} seg.) [{row['score']}] {row['text']}")
    print(f"-- {len(rows)} candidatos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
