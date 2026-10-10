"""Auditoría local de relaciones TikTok: solo lectura, nunca unfollow.

No usa TikTok, navegador, HTTP, tokens ni archivos de salida. La ausencia de
followback en un snapshot de seguidos NO demuestra no reciprocidad.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

VALID_HANDLE = re.compile(r"[A-Za-z0-9._]{2,32}\Z")
CONFIRMED = frozenset({"confirmado", "publicado"})
ENGAGEMENT = frozenset({"reply", "comment", "comentario", "like", "favourite"})
UNCERTAIN = frozenset({"pendiente_verificacion", "incierto", "intento_pendiente"})


def normalize(value):
    if not isinstance(value, str):
        return None
    value = value.strip().lstrip("@").casefold()
    return value if VALID_HANDLE.fullmatch(value) else None


def parse_day(value, *, today):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
            return None
        parsed = dt.date.fromisoformat(value.strip())
        return parsed if parsed <= today else None
    except ValueError:
        return None


def read_csv(path, required):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(required).issubset(reader.fieldnames):
            raise ValueError(f"{path}: columnas incompletas")
        rows = list(reader)
        if any(None in row or any(row.get(k) is None for k in required) for row in rows):
            raise ValueError(f"{path}: línea CSV incompleta")
        return rows


def report(following, actions, inbound, *, today, observed_on=None, protected=()):
    """Devuelve datos de revisión; no recomienda ni ejecuta unfollow.

    Históricos faltantes, formatos dudosos o fechas futuras -> incertidumbre.
    'Amigos' es indicio positivo; nunca inferir reciprocidad negativa.
    """
    if not isinstance(today, dt.date) or isinstance(today, dt.datetime):
        raise ValueError("today debe ser date")
    if not isinstance(following, list) or not isinstance(actions, list) or not isinstance(inbound, list):
        raise ValueError("fuentes inválidas")
    snap = parse_day(observed_on, today=today) if observed_on else None
    fresh = snap is not None and (today - snap).days <= 2
    safe = {h for x in protected if (h := normalize(x))}
    per_handle = {}
    action_index = {}
    inbound_index = {}
    for event in actions:
        if isinstance(event, dict) and (h := normalize(event.get("cuenta"))):
            action_index.setdefault(h, []).append(event)
    for event in inbound:
        if (isinstance(event, dict) and event.get("red") == "tiktok"
                and (h := normalize(event.get("handle")))):
            inbound_index.setdefault(h, []).append(event)
    counts = Counter()
    for item in following:
        h = normalize(item.get("handle")) if isinstance(item, dict) else None
        if not h:
            counts["sin_identidad"] += 1
            continue
        per_handle.setdefault(h, []).append(item)
    rows = []
    for h, items in sorted(per_handle.items()):
        reasons = []
        follow_dates, uncertain, engaged, stale_follow = [], False, False, False
        for event in action_index.get(h, ()):
            kind = (event.get("tipo") or "").strip().casefold()
            result = (event.get("resultado") or "").strip().casefold()
            day = parse_day(event.get("fecha"), today=today)
            if kind in {"follow", "unfollow"} and (result not in CONFIRMED or day is None):
                uncertain = True
            if kind == "follow" and result in CONFIRMED and day:
                follow_dates.append(day)
            if kind == "unfollow" and result in CONFIRMED and day:
                stale_follow = True
            if kind in ENGAGEMENT and result in CONFIRMED:
                engaged = True
            if kind in ENGAGEMENT and (result in UNCERTAIN or not day):
                uncertain = True
        for event in inbound_index.get(h, ()):
            day = parse_day(event.get("fecha"), today=today)
            if day is None:
                uncertain = True
            elif (event.get("tipo") or "").strip().casefold() in ("follow", "comment", "reply", "like"):
                engaged = True
        age = (today - max(follow_dates)).days if follow_dates else None
        statuses = {str(item.get("status") or "").strip().casefold() for item in items}
        mutual = statuses & {"amigos", "friends"}
        if h in safe:
            category, reasons = "protegida", ["lista manual protegida"]
        elif len(items) != 1 or stale_follow or uncertain:
            category = "revision_incertidumbre"
            reasons.append("duplicado, estado contradictorio o ACK incierto")
        elif mutual:
            category, reasons = "protegida", ["amistad indicada por snapshot"]
        elif engaged:
            category, reasons = "protegida", ["interacción documentada"]
        elif not fresh:
            category, reasons = "revision_incertidumbre", ["snapshot sin fecha fiable o antiguo"]
        elif age is None:
            category, reasons = "revision_incertidumbre", ["no consta follow confirmado con fecha"]
        elif age < 7:
            category, reasons = "espera", ["menos de 7 días desde follow confirmado"]
        elif age < 21:
            category, reasons = "revision_7_20", ["reciprocidad no acreditada; revisión humana"]
        else:
            category, reasons = "revision_21_mas", ["21+ días; reciprocidad no acreditada, NO es prueba negativa"]
        counts[category] += 1
        rows.append({"handle": h, "categoria": category, "edad_dias": age,
                     "motivo": "; ".join(reasons), "accion": "ninguna"})
    return {"fecha_informe": today.isoformat(), "fecha_snapshot_declarada": snap.isoformat() if snap else None,
            "snapshot_reciente": fresh, "cobertura": "parcial_o_desconocida",
            "cuentas_observadas": len(per_handle), "totales": dict(sorted(counts.items())),
            "cuentas": rows, "acciones_remotas": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Informe offline de relaciones TikTok; jamás unfollow")
    parser.add_argument("--following", required=True, help="JSON capturado previamente; no consulta red")
    parser.add_argument("--registro", required=True, help="CSV local histórico")
    parser.add_argument("--inbound", required=True, help="CSV local de eventos entrantes")
    parser.add_argument("--observed-on", required=True, help="Fecha declarada del snapshot YYYY-MM-DD")
    parser.add_argument("--today", default=dt.date.today().isoformat())
    parser.add_argument("--details", action="store_true", help="Incluir handles solo en salida local")
    args = parser.parse_args(argv)
    today = dt.date.fromisoformat(args.today)
    with Path(args.following).open(encoding="utf-8") as stream:
        following = json.load(stream)
    actions = read_csv(args.registro, {"fecha", "cuenta", "tipo", "resultado"})
    inbound = read_csv(args.inbound, {"fecha", "red", "handle", "tipo"})
    # Reutilizar exclusiones existentes sin ejecutar acciones, por importación.
    from tiktok_following_audit import KEEP_HANDLES
    data = report(following, actions, inbound, today=today,
                  observed_on=args.observed_on, protected=KEEP_HANDLES)
    if not args.details:
        data.pop("cuentas")  # Privacidad: no listar identidades sin petición explícita
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
