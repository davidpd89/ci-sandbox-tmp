"""Caídas sostenidas en rondas productivas; diagnóstico local y de solo lectura.

No confundir ausencia de muestra con una ronda productiva que confirmó cero.
Las pausas, rondas saltadas y errores se diagnostican en otros canarios.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from round_canaries import _confirmed, NETWORKS

BASELINE_DAYS = 7
MIN_BASELINE_DAYS = 4
MIN_ROUNDS_PER_DAY = 3
MIN_BASELINE_PER_ROUND = 2.0
DROP_RATIO = 0.4
MAX_ACTIONS_PER_ROUND = 1_000_000
REQUIRED_COLUMNS = {"fecha", "red", "fin", "estado", "confirmadas"}
KNOWN_STATES = frozenset(("ok", "parcial", "error", "saltada", "ocupada"))
MEASURED_STATES = frozenset(("ok", "parcial"))


def _today(now):
    """Un instante con zona se interpreta en Madrid, no en la fecha UTC."""
    if now is None:
        return dt.datetime.now().date()  # reloj local del PC operativo (Madrid)
    if isinstance(now, dt.datetime):
        if now.tzinfo is not None:
            try:
                return now.astimezone(ZoneInfo("Europe/Madrid")).date()
            except ZoneInfoNotFoundError:
                return None  # no inventar zona en Windows sin tzdata
        return now.date()  # reloj local/inyectado del proyecto
    if isinstance(now, dt.date):
        return now
    return None


def collect(root, *, now=None):
    """Un aviso por red solo con >=2 días completos, 4 días de referencia.

    Las confirmaciones positivas de 'ok'/'parcial' son muestras evaluables;
    en el productor de CSV, una ronda con cero pasa a 'saltada' o 'error'.
    CSV incompleto en la ventana de una red invalida esa red, no las demás.
    """
    today = _today(now)
    if today is None:
        return []
    days = [today - dt.timedelta(days=k) for k in range(1, BASELINE_DAYS + 3)]
    included = {day.isoformat() for day in days}
    totals = {net: {day: [0, 0] for day in included} for net in NETWORKS}
    invalid = set()
    path = Path(root) / "00_OPERATIVO" / "tiempos_rondas.csv"

    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if (not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames))
                    or not REQUIRED_COLUMNS.issubset(reader.fieldnames)):
                return []
            for row in reader:
                network = row.get("red")
                day = row.get("fecha")
                if network not in totals:
                    # Fila reciente sin red atribuible: un dato perdido
                    # impide demostrar una caída en cualquier red.
                    if not network and day in included:
                        invalid.update(NETWORKS)
                    continue
                if not isinstance(day, str) or len(day) != 10:
                    invalid.add(network)
                    continue
                try:
                    dt.date.fromisoformat(day)
                except ValueError:
                    invalid.add(network)
                    continue
                if day not in included:
                    continue
                state = row.get("estado")
                if None in row or not row.get("fin") or state not in KNOWN_STATES:
                    invalid.add(network)
                    continue
                if state not in MEASURED_STATES:
                    continue  # no deducir cero por pausa/ausencia/error
                raw = row.get("confirmadas")
                if not isinstance(raw, str) or not raw.strip():
                    invalid.add(network)
                    continue
                try:
                    count = _confirmed(raw)
                except (ValueError, OverflowError, RecursionError):
                    count = None
                if count is None or not 1 <= count <= MAX_ACTIONS_PER_ROUND:
                    invalid.add(network)
                    continue
                bucket = totals[network][day]
                bucket[0] += count
                bucket[1] += 1
    except (OSError, UnicodeError, csv.Error):
        return []

    alerts = []
    for network in NETWORKS:
        if network in invalid:
            continue
        values = []
        rounds = []
        for day in days:
            confirmed, n = totals[network][day.isoformat()]
            rounds.append(n)
            values.append(confirmed / n if n >= MIN_ROUNDS_PER_DAY else None)
        recent = values[:2]
        baseline = [value for value in values[2:] if value is not None]
        if any(value is None for value in recent) or len(baseline) < MIN_BASELINE_DAYS:
            continue
        reference = median(baseline)
        if reference < MIN_BASELINE_PER_ROUND:
            continue
        if all(value <= reference * DROP_RATIO for value in recent):
            alerts.append({"code": "CAIDA_RENDIMIENTO_SOSTENIDA",
                           "severity": "media", "network": network,
                           "baseline_days": len(baseline), "recent_days": 2,
                           "recent_valid_rounds": rounds[:2],
                           "baseline_actions_per_round": round(reference, 2),
                           "recent_actions_per_round": [round(v, 2) for v in recent],
                           "threshold_ratio": DROP_RATIO})
    return alerts
