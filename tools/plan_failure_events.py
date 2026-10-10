"""Eventos de fallo de plan. Sin acceso a cuentas ni texto ajeno."""
from __future__ import annotations
import datetime as dt
import json
import ntpath
import os
from pathlib import Path
import re
import uuid

NETWORKS = ("bluesky", "mastodon", "threads", "x", "facebook", "pinterest", "reddit", "tiktok")
STAGES = frozenset(("scan", "decide", "write", "plan", "build", "preflight"))
RETENTION_DAYS = 7
ALERT_WINDOW_MINUTES = 120
ALERT_THRESHOLD = 3
MAX_EVENT_BYTES = 2048


def _folder(root):
    return Path(root) / "00_OPERATIVO" / "cache" / "errores_plan"


def _safe_token(value):
    value = str(value or "")[:80]
    return value if re.fullmatch(r"[a-zA-Z0-9_.:-]{1,80}", value) else "unknown"


def prune(root, *, now=None):
    """Eliminar JSON de más de siete días. Tolerar carreras."""
    now = now or dt.datetime.now()
    cutoff = now.timestamp() - RETENTION_DAYS * 86400
    try:
        for path in _folder(root).glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except (FileNotFoundError, PermissionError, IsADirectoryError):
                continue
    except OSError:
        pass


def record(root, network, stage, log_path=None, *, cause="error", now=None):
    """Evento único con os.replace; sin stderr, texto de posts ni rutas."""
    if network not in NETWORKS or stage not in STAGES:
        return False
    now = now or dt.datetime.now()
    folder = _folder(root)
    name = f"{now:%Y%m%dT%H%M%S%f}_{os.getpid()}_{uuid.uuid4().hex}.json"
    data = {"schema": 1, "red": network, "stage": stage,
            "at": now.isoformat(timespec="microseconds"), "cause": _safe_token(cause),
            "log_name": _safe_token(ntpath.basename(str(log_path or "")))}
    tmp = folder / (name + ".tmp")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tmp.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.write("\n")
        os.replace(tmp, folder / name)
        prune(root, now=now)
        return True
    except OSError:
        return False
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def collect_alerts(root, *, now=None):
    """>=3 eventos/2 h por red. Lectura apta para canario/panel."""
    now = now or dt.datetime.now()
    groups = {net: [] for net in NETWORKS}
    try:
        for file in _folder(root).glob("*.json"):
            try:
                if file.stat().st_size > MAX_EVENT_BYTES:
                    continue
                event = json.loads(file.read_text(encoding="utf-8"))
                if not isinstance(event, dict) or event.get("schema") != 1:
                    continue
                network = event.get("red")
                if network not in groups or event.get("stage") not in STAGES:
                    continue
                when = dt.datetime.fromisoformat(event["at"])
                age = (now - when).total_seconds()
                if 0 <= age <= ALERT_WINDOW_MINUTES * 60:
                    groups[network].append((when, file.name, event))
            except (OSError, ValueError, TypeError, KeyError, OverflowError):
                continue
    except OSError:
        return []
    alerts = []
    for network, entries in groups.items():
        if len(entries) < ALERT_THRESHOLD:
            continue
        _, _, last = max(entries, key=lambda item: (item[0], item[1]))
        alerts.append({"code": "FALLO_PLAN_REPETIDO", "severity": "alta",
                       "network": network, "count": len(entries),
                       "window_minutes": ALERT_WINDOW_MINUTES,
                       "last_stage": last["stage"],
                       "last_cause": _safe_token(last.get("cause")),
                       "last_log_name": _safe_token(last.get("log_name"))})
    return alerts
