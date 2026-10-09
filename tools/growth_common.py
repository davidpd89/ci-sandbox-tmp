"""Utilidades genéricas para rondas de crecimiento orgánico.

La idea compartida no es "hacer N acciones", sino cubrir fuentes de descubrimiento
con un presupuesto de lectura y aprender qué consultas generan candidatos útiles.
Las redes conservan su implementación específica de API/DOM.
"""
from __future__ import annotations

import csv
import datetime
import math
import os
from collections import defaultdict


class ReadBudgetExceeded(RuntimeError):
    pass


class ReadBudget:
    def __init__(self, maximum):
        maximum = int(maximum)
        if maximum < 1:
            raise ValueError("maximum debe ser >= 1")
        self.maximum = maximum
        self.used = 0
        self.by_surface = defaultdict(int)

    def take(self, surface, cost=1):
        cost = int(cost)
        if cost < 1:
            raise ValueError("cost debe ser >= 1")
        if self.used + cost > self.maximum:
            raise ReadBudgetExceeded(
                f"presupuesto de lectura agotado: {self.used}/{self.maximum}"
            )
        self.used += cost
        self.by_surface[str(surface)] += cost

    @property
    def remaining(self):
        return max(0, self.maximum - self.used)

    def can_spend(self, cost=1, *, reserve=0):
        cost = max(0, int(cost))
        reserve = max(0, int(reserve))
        return self.remaining >= cost + reserve

    def snapshot(self):
        return {
            "used": self.used,
            "maximum": self.maximum,
            "remaining": self.remaining,
            "by_surface": dict(self.by_surface),
        }


def load_discovery_metrics(path, *, days=30, today=None):
    """Agrega rendimiento reciente por (surface, key)."""
    today = today or datetime.date.today()
    cutoff = today - datetime.timedelta(days=max(0, int(days)))
    stats = {}
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return stats
    with open(path, encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"fecha", "surface", "key", "fetched", "accepted", "new_handles"}
        fields = set(reader.fieldnames or ())
        if not required.issubset(fields):
            raise RuntimeError(
                f"discovery_metrics.csv inválido: faltan {sorted(required - fields)}"
            )
        for line_no, row in enumerate(reader, start=2):
            try:
                date = datetime.date.fromisoformat((row.get("fecha") or "").strip())
                fetched = int(row.get("fetched") or 0)
                accepted = int(row.get("accepted") or 0)
                new_handles = int(row.get("new_handles") or 0)
            except (ValueError, TypeError) as exc:
                raise RuntimeError(
                    f"discovery_metrics.csv inválido en línea {line_no}"
                ) from exc
            if date < cutoff:
                continue
            key = ((row.get("surface") or "").strip(), (row.get("key") or "").strip())
            if not all(key):
                continue
            item = stats.setdefault(key, {
                "attempts": 0,
                "fetched": 0,
                "accepted": 0,
                "new_handles": 0,
                "last_date": None,
            })
            item["attempts"] += 1
            item["fetched"] += max(0, fetched)
            item["accepted"] += max(0, accepted)
            item["new_handles"] += max(0, new_handles)
            if item["last_date"] is None or date > item["last_date"]:
                item["last_date"] = date
    return stats


def rank_keys(keys, stats, *, surface, today=None):
    """Ordena consultas por utilidad + exploración + tiempo sin usarse.

    Nunca usadas van primero. Entre usadas, prima generar handles nuevos y
    candidatos válidos, pero una consulta que lleva días sin probar recibe bonus.
    """
    today = today or datetime.date.today()
    ranked = []
    for index, key in enumerate(keys):
        metric = stats.get((surface, key))
        if not metric:
            score = 1000.0 - index / 1000.0
        else:
            attempts = max(1, metric["attempts"])
            fetched = max(1, metric["fetched"])
            accepted_rate = metric["accepted"] / fetched
            new_rate = metric["new_handles"] / fetched
            last_date = metric["last_date"] or today
            stale_days = max(0, (today - last_date).days)
            stale_bonus = min(stale_days / 7.0, 1.0) * 0.35
            explore_bonus = 0.25 / math.sqrt(attempts)
            same_day_penalty = 2.0 if stale_days == 0 else 0.0
            score = (
                accepted_rate * 1.4
                + new_rate * 2.0
                + stale_bonus
                + explore_bonus
                - same_day_penalty
            )
        ranked.append((score, key))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [key for _, key in ranked]


def append_discovery_metric(
    path, *, date, run_id, surface, key, fetched, accepted, new_handles
):
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        if not exists:
            writer.writerow([
                "fecha", "run_id", "surface", "key",
                "fetched", "accepted", "new_handles",
            ])
        writer.writerow([
            date, run_id, surface, key,
            int(fetched), int(accepted), int(new_handles),
        ])
