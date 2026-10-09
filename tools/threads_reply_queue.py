"""Cola de respuestas de Threads: las mejores ocasiones de la reserva para escribir 10-25 replies a mano (05/10/2026).

Consulta G a GPT: Meta indica que las replies son casi la mitad de las visualizaciones de Threads y que la conversacion favorece la recomendacion; 10-25 buenas conversaciones valen mas que otros
100 likes. Reglas de voz (GUIA_VOZ_REPLIES.md): 20-80 caracteres, formatos variados, sin hashtags, sin mencionar a David ni su libro, sin rellenar los 500 caracteres.

Elige de `threads_pool.py` posts de las ultimas 24 h, del nicho, en espanol, que invitan a conversar (pregunta, peticion de recomendacion), de cuentas con las que no hemos hablado en 30 dias; uno por cuenta.

    python tools/threads_reply_queue.py [--n 20]
    python tools/threads_reply_queue.py plan decisiones.json     # {"replies": [{"permalink": "...", "text": "..."}]} -> threads_plan_replies.json
Despues: python tools/threads_execute.py SISTEMA_DIARIO_THREADS/threads_plan_replies.json
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc
import threads_build_plan as tb
import threads_pool as pool

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_THREADS")
REGISTRO = os.path.join(ROOT, "registro_interacciones.csv")
PLAN_OUT = os.path.join(ROOT, "threads_plan_replies.json")


def replied_handles(days=30, today=None):
    today = today or datetime.date.today()
    out = set()
    try:
        with open(REGISTRO, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                try:
                    age = (today - datetime.date.fromisoformat((row.get("fecha") or "")[:10])).days
                except ValueError:
                    continue
                if "reply" in (row.get("tipo") or "").split("+") and age <= days:
                    out.add((row.get("cuenta") or "").strip().lstrip("@").casefold())
    except OSError:
        pass
    return frozenset(out)


def candidates(db, *, n=20, replied=frozenset(), now=None, max_age_hours=24):
    out = []
    for row in pool.pick(db, n * 6, exclude_handles=replied, now=now, max_age_hours=max_age_hours):
        text = row["text"]
        if not (sc.invites_conversation(text) or "?" in text or "¿" in text):
            continue
        if sc.asks_for_opinion(text) or not 40 <= len(text) <= 400:
            continue
        out.append(row)
        if len(out) >= n:
            break
    return out


def build_plan(db, decisions):
    """Plan solo de replies a partir de las decisiones escritas a mano (permalink + texto)."""
    plan = []
    for entry in decisions.get("replies") or []:
        permalink = str(entry.get("permalink") or "").rstrip("/")
        row = db.execute("SELECT handle, text FROM posts WHERE permalink = ?", (permalink,)).fetchone()
        if not row:
            raise ValueError(f"permalink fuera de la reserva: {permalink!r}")
        plan.append({"handle": row[0], "kind": "reply", "permalink": permalink, "text_fragment": tb.fragment(row[1]), "text": entry["text"],
                     "motivo": "growth:reply_queue"})
    return plan


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    db = pool.connect()
    try:
        if argv and argv[0] == "plan":
            with open(argv[1], encoding="utf-8") as stream:
                plan = build_plan(db, json.load(stream))
            with open(PLAN_OUT, "w", encoding="utf-8") as stream:
                json.dump(plan, stream, ensure_ascii=False, indent=1)
            print(f"{len(plan)} replies -> {PLAN_OUT}")
            return 0
        n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 20
        rows = candidates(db, n=n, replied=replied_handles())
        for row in rows:
            print(f"@{row['handle']} [{row['score']}] {row['permalink']}\n   {row['text'][:240]}")
        print(f"-- {len(rows)} candidatos")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
