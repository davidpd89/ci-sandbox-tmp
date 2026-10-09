"""Norma de reposts/boosts para TODAS las redes (07/10/2026, David): los reposts automaticos llenaban el feed de contenido ajeno (hilos politicos, respuestas sueltas, gente del f4f).

Nueva norma:
  * como MAXIMO 3 reposts (repost/boost/cita) al dia por red, y solo si el candidato esta marcado `curated: True` (lo elige `repost_curator.py`: gente de NUESTRA comunidad que nos comenta,
    nos reposta o nos sigue, con un post propio, bonito y de nicho). El plan automatico normal ya no reposta nada.
  * cada repost se retira solo a las 24 h (`growth_policy.SHARE_TTL_DAYS = 1`).
  * captar se hace con seguir y comentar; el repost queda para fidelizar.
"""
from __future__ import annotations

import csv
import datetime
import os

MAX_PER_DAY = 3
SHARE_KINDS = ("repost", "boost", "quote")


def done_today(registro_csv, today=None):
    """Reposts/boosts/citas confirmados hoy segun el registro de la red."""
    today = (today or datetime.date.today()).isoformat()
    n = 0
    try:
        with open(registro_csv, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if (row.get("fecha") or "")[:10] == today and row.get("resultado") in ("confirmado", "publicado") and any(k in SHARE_KINDS for k in (row.get("tipo") or "").split("+")):
                    n += 1
    except OSError:
        pass
    return n


def filter_plan(plan, already=0):
    """(plan sin reposts no curados ni por encima del tope diario, cuantos se quitaron)."""
    room = max(0, MAX_PER_DAY - int(already))
    kept, dropped = [], 0
    for item in plan:
        if item.get("kind") in SHARE_KINDS:
            if item.get("curated") and room > 0:
                room -= 1
            else:
                dropped += 1
                continue
        kept.append(item)
    return kept, dropped


def guard(plan, registro_csv):
    """Tope en el EJECUTOR (07/10): da igual quien haya construido el plan (ronda, oleada, script suelto): un repost/boost/cita sin `curated` o por encima de 3/dia no se ejecuta."""
    kept, dropped = filter_plan(list(plan), done_today(registro_csv))
    if dropped:
        print(f"[norma de reposts] {dropped} reposts/boosts/citas quitados (max {MAX_PER_DAY}/dia y solo curados)")
    return kept
