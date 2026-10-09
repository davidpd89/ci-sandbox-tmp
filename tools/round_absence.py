"""Alarma offline de cadenas sin actividad esperada, sin tocar procesos ni cuentas.

No confundir una cadena ocupada (lock vivo) con una caída. El CSV conserva
el histórico completo de hoy para calcular si ya se alcanzó el objetivo.
"""
import csv
import datetime as dt
from pathlib import Path

CHAINS = {
    "web": ("x", "threads", "facebook", "pinterest"),
    "api": ("bluesky", "mastodon"),
    "tiktok": ("tiktok",),
}
FIRST_ALERT_HOUR = 10
LAST_ALERT_HOUR = 23
QUIET_MINUTES = 180


def _counts_today(path, now):
    """None = fichero ilegible, no emitir falsos avisos de ausencia."""
    if not path.exists():
        return {}
    counts = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"fecha", "red", "estado"}.issubset(reader.fieldnames):
            return None
        for row in reader:
            if row.get("fecha") != now.date().isoformat():
                continue
            if row.get("estado") in ("ok", "parcial"):
                network = row.get("red")
                counts[network] = counts.get(network, 0) + 1
    return counts


def collect(root, now, recent, *, targets=None, owner_is_live=None):
    """Un aviso por red pendiente solo si falta progreso Y falta dueño vivo.

    El inicio matinal tiene margen; no hay alarma durante parada explícita,
    fuera de horas ni cuando todas las rondas de una red están cumplidas.
    """
    root = Path(root)
    if not FIRST_ALERT_HOUR <= now.hour < LAST_ALERT_HOUR:
        return []
    op = root / "00_OPERATIVO"
    if (op / "cola_parar.flag").exists():
        return []
    # No suponer que un proyecto recién clonado tiene Scheduler instalado.
    # Exigir evidencia local de cola ya desplegada: logs o lock de cadena.
    if not any((op / f"cola_rondas_{chain}.log").exists()
               or (op / f"cola_rondas_{chain}.lock").exists()
               for chain in CHAINS):
        return []
    try:
        counts = _counts_today(op / "tiempos_rondas.csv", now)
    except (OSError, UnicodeError, csv.Error):
        return []
    if counts is None:
        return []
    if targets is None:
        from round_queue import rounds_target
        try:
            targets = {network: rounds_target(network)
                       for names in CHAINS.values() for network in names}
        except (OSError, ValueError, KeyError, TypeError):
            return []
    if owner_is_live is None:
        from round_queue import _owner_is_live
        owner_is_live = _owner_is_live

    alerts = []
    for chain, networks in CHAINS.items():
        path = op / f"cola_rondas_{chain}.lock"
        try:
            owner = path.read_text(encoding="ascii").strip()
            live = bool(owner_is_live(owner))
        except (FileNotFoundError, OSError, UnicodeError, ValueError):
            live = False
        if live:
            continue  # Puede estar dentro de una ronda larga, sin fila CSV aún.
        for network in networks:
            quota = targets.get(network, 0)
            if not isinstance(quota, int) or quota <= 0 or counts.get(network, 0) >= quota:
                continue
            latest = max((row["when"] for row in recent if row["network"] == network),
                         default=None)
            if latest is not None and (now - latest).total_seconds() < QUIET_MINUTES * 60:
                continue
            alerts.append({
                "code": "SIN_RONDAS_ESPERADAS", "severity": "alta",
                "network": network, "chain": chain,
                "rounds_completed_today": counts.get(network, 0),
                "rounds_target": quota,
                "minutes_without_finished_round": (
                    int((now - latest).total_seconds() // 60) if latest else None
                ),
            })
    return alerts
