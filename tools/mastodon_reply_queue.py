"""Cola de respuestas de Mastodon: las mejores ocasiones del ultimo scan para escribir 15-30 replies al dia a mano (05/10/2026).

Gemela de `bluesky_reply_queue.py`. Consulta F a GPT: las replies de David son editoriales (lo unico que escribe la IA) y se miden por variedad y respuesta; en Mastodon
ademas: sin hashtags en las respuestas (no dan alcance y un hashtag seguido las hace aparecer en Home), sin emojis personalizados (el shortcode es de cada servidor), sin
content warning en una respuesta literaria normal, y NUNCA llevar el hilo hacia David o su libro («precisamente yo escribo…»): eso es lo que se percibe como spam.

Lee `mastodon_growth_state.json` y filtra: estado en espanol (`language`) del nicho (>=1 termino), <=3 dias, 50-300 caracteres, publico/unlisted y no sensible, sin enlaces,
sin peticiones de opinion sobre su trabajo, cuenta de 20-5.000 seguidores, no bot, y a la que no hayamos escrito en 30 dias. Una sola por cuenta.

    python tools/mastodon_reply_queue.py [--n 30]
    python tools/mastodon_reply_queue.py plan decisiones.json     # {"replies": [{"post": "M003-P1", "text": "..."}]} -> mastodon_plan_replies.json
Despues: python tools/mastodon_execute.py mastodon_plan_replies.json
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE = os.path.join(ROOT, "mastodon_growth_state.json")
REGISTRO = os.path.join(ROOT, "SISTEMA_DIARIO_MASTODON", "registro_interacciones.csv")
MAX_AGE_DAYS = 3


def _age(created, today):
    try:
        return (today - datetime.date.fromisoformat(str(created)[:10])).days
    except ValueError:
        return 99


def candidates(state, *, today=None, replied=frozenset(), limit=30):
    import text_common as bp
    today = today or datetime.date.today()
    out = []
    for item in state.get("shortlist") or []:
        followers = int(item.get("followers") or 0)
        acct = str(item.get("acct") or "").casefold()
        if not 20 <= followers <= 5000 or item.get("bot") or acct in replied:
            continue
        for post in item.get("posts") or []:
            text = re.sub(r"\s+", " ", str(post.get("text") or "")).strip()
            language = str(post.get("language") or "")
            if "reply" not in (post.get("actions") or []) or (language and not language.startswith("es")):
                continue
            if post.get("sensitive") or post.get("visibility") not in ("public", "unlisted"):
                continue
            if not 50 <= len(text) <= 300 or _age(post.get("created_at"), today) > MAX_AGE_DAYS:
                continue
            if re.search(r"https?://|www\.", text) or sc.is_political(text) or sc.asks_for_opinion(text):
                continue
            hits = bp.niche_hits(text)
            if hits < 1:
                continue
            stats = post.get("stats") or {}
            score = 3 * min(hits, 3) + (2 if sc.invites_conversation(text) else 0) + (1 if "?" in text else 0) + (1 if followers <= 1500 else 0) + (1 if stats.get("replies") else 0)
            out.append({"post": post["id"], "acct": item["acct"], "followers": followers, "score": score, "text": text, "url": post.get("url")})
    out.sort(key=lambda row: (-row["score"], row["acct"]))
    picked, used = [], set()
    for row in out:
        if row["acct"] in used:
            continue
        used.add(row["acct"])
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def replied_accounts(days=30, today=None):
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
    """Plan solo de replies (sin el auto_plan) a partir de las decisiones escritas a mano."""
    import mastodon_build_plan as bp
    actions = [{"post": row["post"], "kind": "reply", "text": row["text"]} for row in decisions.get("replies") or []]
    return bp.build({"shortlist": state.get("shortlist") or [], "auto_plan": [], "follow_pool": state.get("follow_pool") or []}, {"actions": actions})


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    with open(STATE, encoding="utf-8") as stream:
        state = json.load(stream)
    if argv and argv[0] == "plan":
        with open(argv[1], encoding="utf-8") as stream:
            decisions = json.load(stream)
        plan = build_plan(state, decisions)
        out = argv[2] if len(argv) > 2 else os.path.join(ROOT, "mastodon_plan_replies.json")
        with open(out, "w", encoding="utf-8") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=1)
        print(f"{len(plan)} replies -> {out}")
        return 0
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 30
    rows = candidates(state, replied=replied_accounts(), limit=n)
    for row in rows:
        print(f"{row['post']} @{row['acct']} ({row['followers']} seg.) [{row['score']}] {row['text']}")
    print(f"-- {len(rows)} candidatos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
