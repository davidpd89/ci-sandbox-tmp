"""Dashboard offline, solo lectura: exportacion agregada de nueve redes.

No importa ejecutores ni consulta cuentas. Requiere --root y --output explicitos.
Datos por lista cerrada; nunca exporta textos, handles, targets, logs ni rutas.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import math
import os
from pathlib import Path
import re
import statistics
import tempfile

NETWORK_QUEUES = {
    "x": "WEB", "threads": "WEB", "facebook": "WEB",
    "pinterest": "WEB", "reddit": "WEB", "instagram": "WEB",
    "bluesky": "API", "mastodon": "API", "tiktok": "MOBILE",
}
ROUND_STATES = ("ok", "parcial", "error", "saltada", "ocupada")
PHASES = ("pre", "scan", "plan", "execute", "post", "bulk")
TIMING = re.compile(r"\[TIEMPO_ETAPA\]\s+phase=(pre|scan|plan|execute|post|bulk)\b[^\n]{0,240}?\bsegundos=(\d+(?:\.\d+)?)")
LOG_NAME = re.compile(r"mech_(\d{4}-\d{2}-\d{2})_[0-9]{4,6}\.log\Z")
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_LOG_BYTES = 1024 * 1024
MAX_LOG_FILES = 500


def _date(value):
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _read_csv(path):
    """None significa ausente/ilegible; [] significa fuente válida sin filas."""
    if not path.is_file():
        return None
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return None
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or any(not field for field in reader.fieldnames):
                return None
            rows = []
            for index, row in enumerate(reader):
                if index >= 250_000:
                    return None
                rows.append(row)
            return rows
    except (OSError, UnicodeError, csv.Error):
        return None


def _read_json(path):
    if not path.is_file():
        return None
    try:
        if path.stat().st_size > MAX_LOG_BYTES:
            return None
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, UnicodeError, ValueError):
        return None


def _breaker(path, now):
    source = _read_json(path)
    if source is None:
        return {"status": "sin_datos", "fails": None}
    if not isinstance(source, dict):
        return {"status": "invalido", "fails": None}
    fails = source.get("fails")
    if type(fails) is not int or fails < 0:
        return {"status": "invalido", "fails": None}
    until = source.get("open_until")
    if until:
        try:
            expiry = dt.datetime.fromisoformat(until)
            if expiry.tzinfo is not None:  # estado local legacy: sin zona
                return {"status": "invalido", "fails": None}
        except (TypeError, ValueError):
            return {"status": "invalido", "fails": None}
        if expiry > now:
            return {"status": "abierto", "fails": fails}
    return {"status": "cerrado", "fails": fails}


def _pending_counts(path):
    source = _read_json(path)
    if not isinstance(source, dict):
        return None
    counts = {name: 0 for name in NETWORK_QUEUES}
    for entry in source.values():
        if not isinstance(entry, dict) or not isinstance(entry.get("network"), str):
            return None
        name = entry["network"].casefold()
        if name in counts:
            counts[name] += 1
    return counts


def _phases(folder, cutoff, today):
    """Solo estadísticas de tiempos; jamás se conserva texto del log."""
    if not folder.is_dir():
        return None
    try:
        names = sorted(folder.iterdir(), reverse=True)
    except OSError:
        return None
    samples = {phase: [] for phase in PHASES}
    inspected = 0
    for path in names:
        m = LOG_NAME.fullmatch(path.name)
        day = _date(m.group(1)) if m else None
        if day is None or not cutoff <= day <= today or not path.is_file():
            continue
        inspected += 1
        if inspected > MAX_LOG_FILES:
            break
        try:
            if path.stat().st_size > MAX_LOG_BYTES:
                continue
            with path.open(encoding="utf-8", errors="replace") as stream:
                for row in stream:
                    match = TIMING.search(row)
                    if match:
                        seconds = _number(match.group(2))
                        if seconds is not None:
                            samples[match.group(1)].append(seconds)
        except OSError:
            continue
    result = {}
    for phase, values in samples.items():
        if values:
            ordered = sorted(values)
            result[phase] = {
                "samples": len(values),
                "mean_seconds": round(statistics.mean(values), 2),
                "p95_seconds": round(ordered[math.ceil(len(ordered) * .95) - 1], 2),
            }
    return result


def _rounds(rows, net, cutoff, today):
    if rows is None:
        return None
    selected = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("red") or "").casefold() != net:
            continue
        day = _date(row.get("fecha"))
        if day is None or not cutoff <= day <= today:
            continue
        state = row.get("estado")
        if state not in ROUND_STATES:
            continue
        selected.append((day, state, _number(row.get("minutos"))))
    values = [minutes for _, _, minutes in selected if minutes is not None]
    return {
        "total": len(selected),
        "states": {state: sum(s == state for _, s, _ in selected) for state in ROUND_STATES},
        "mean_minutes": round(statistics.mean(values), 2) if values else None,
        "p95_minutes": round(sorted(values)[math.ceil(len(values) * .95) - 1], 2) if values else None,
        "by_day": {str(day): sum(d == day for d, _, _ in selected)
                   for day in (cutoff + dt.timedelta(days=i) for i in range((today - cutoff).days + 1))},
    }


def _actions(rows, cutoff, today):
    if rows is None:
        return None
    confirmed = failures = pending = skipped = 0
    by_day = {str(cutoff + dt.timedelta(days=i)): 0 for i in range((today - cutoff).days + 1)}
    for row in rows:
        if not isinstance(row, dict):
            continue
        day = _date(row.get("fecha"))
        if day is None or not cutoff <= day <= today:
            continue
        status = (row.get("resultado") or "").casefold()
        if status in ("confirmado", "publicado"):
            confirmed += 1
            by_day[str(day)] += 1
        elif status.startswith("saltado_") or status == "omitido":
            skipped += 1
        elif "incierto" in status or "pendiente_verificacion" in status:
            pending += 1
        elif status:
            failures += 1
    return {"confirmed_records": confirmed, "failed_records": failures,
            "pending_verification": pending, "skipped_records": skipped, "by_day": by_day}


def collect(root, *, as_of, days=7):
    """Puro en la salida; solo lectura de ficheros bajo root."""
    if not 1 <= days <= 31:
        raise ValueError("days debe estar entre 1 y 31")
    now = as_of
    today = now.date()
    cutoff = today - dt.timedelta(days=days - 1)
    rounds = _read_csv(root / "00_OPERATIVO" / "tiempos_rondas.csv")
    pending = _pending_counts(root / "00_OPERATIVO" / "_cola_respuestas" / "pending.json")
    networks = {}
    for net, queue in NETWORK_QUEUES.items():
        folder = root / ("SISTEMA_DIARIO_" + net.upper())
        stats = _actions(_read_csv(folder / "registro_interacciones.csv"), cutoff, today)
        round_stats = _rounds(rounds, net, cutoff, today)
        breaker = _breaker(folder / "cache" / "breaker.json", now)
        phase_stats = _phases(folder / "cache", cutoff, today)
        gaps = []
        if stats is None:
            gaps.append("registro")
        if round_stats is None:
            gaps.append("rondas")
        if pending is None:
            gaps.append("cola_respuestas")
        if breaker["status"] in ("sin_datos", "invalido"):
            gaps.append("breaker")
        item = {
            "queue": queue, "actions": stats, "rounds": round_stats,
            "pending_replies": pending[net] if pending is not None else None,
            "breaker": breaker, "phases": phase_stats, "missing_sources": gaps,
        }
        networks[net] = item
    queues = {}
    for queue in ("WEB", "API", "MOBILE"):
        members = [net for net, item in networks.items() if item["queue"] == queue]
        round_values = [networks[n]["rounds"]["total"] for n in members if networks[n]["rounds"] is not None]
        action_values = [networks[n]["actions"]["confirmed_records"] for n in members if networks[n]["actions"] is not None]
        queues[queue] = {
            "networks": members, "rounds_observed": sum(round_values) if round_values else None,
            "confirmed_records_observed": sum(action_values) if action_values else None,
            "networks_with_round_data": len(round_values),
            "networks_with_action_data": len(action_values),
            "open_breakers": sum(networks[n]["breaker"]["status"] == "abierto" for n in members),
        }
    return {"schema_version": 1, "as_of": now.isoformat(timespec="seconds"),
            "days": days, "coverage": {"round_csv": rounds is not None, "reply_queue": pending is not None},
            "queues": queues, "networks": networks}


def render_html(report):
    """HTML estático sin JavaScript, sin CDN ni valores de usuario."""
    esc = lambda value: html.escape(str(value), quote=True)
    parts = [
        '<!doctype html><html lang="es"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>Observabilidad RRSS · resumen saneado</title>",
        "<style>body{font:15px system-ui,sans-serif;max-width:1150px;margin:2rem auto;padding:0 1rem;color:#17202a}"
        "h1{font-size:1.8rem}h2{margin-top:2rem}table{border-collapse:collapse;width:100%}"
        "th,td{padding:.6rem;text-align:left;border-bottom:1px solid #d7dce0}"
        "th{background:#f4f6f7}td{font-variant-numeric:tabular-nums}"
        ".scroll{overflow-x:auto}.muted{color:#58636e}.alert{font-weight:bold}"
        ".bar{display:inline-block;background:#374e63;height:.75rem;min-width:2px}"
        "small{font-size:.82rem}</style>",
        "<h1>Panel RRSS · observabilidad</h1>",
        "<p>Ventana de " + esc(report["days"]) + " días. Corte: " + esc(report["as_of"]) +
        ". Datos agregados; sin cuentas ni contenidos.</p>",
        "<h2>Colas</h2><div class=scroll><table><thead><tr><th>Cola</th><th>Rondas observadas</th>"
        "<th>Confirmaciones registradas</th><th>Cobertura rondas</th><th>Cortacircuitos abiertos</th></tr></thead><tbody>",
    ]
    def fmt(value):
        return "—" if value is None else esc(value)
    for queue, item in report["queues"].items():
        parts.append("<tr><td>" + esc(queue) + "</td><td>" + fmt(item["rounds_observed"]) +
                     "</td><td>" + fmt(item["confirmed_records_observed"]) + "</td><td>" +
                     esc(item["networks_with_round_data"]) + "/" + esc(len(item["networks"])) +
                     "</td><td>" + esc(item["open_breakers"]) + "</td></tr>")
    parts.append("</tbody></table></div><h2>Redes</h2><div class=scroll><table><thead><tr>"
                 "<th>Red</th><th>Cola</th><th>Confirmadas¹</th><th>Rondas</th><th>Fallidas</th>"
                 "<th>Ocupadas</th><th>Pendientes respuesta</th><th>Media ronda</th>"
                 "<th>Breaker</th><th>Fuentes ausentes</th></tr></thead><tbody>")
    for name, item in report["networks"].items():
        actions, rounds = item["actions"], item["rounds"]
        status = item["breaker"]["status"]
        parts.append("<tr><td>" + esc(name) + "</td><td>" + esc(item["queue"]) + "</td><td>" +
                     fmt(actions["confirmed_records"] if actions else None) + "</td><td>" +
                     fmt(rounds["total"] if rounds else None) + "</td><td>" +
                     fmt(rounds["states"]["error"] if rounds else None) + "</td><td>" +
                     fmt(rounds["states"]["ocupada"] if rounds else None) + "</td><td>" +
                     fmt(item["pending_replies"]) + "</td><td>" +
                     fmt(rounds["mean_minutes"] if rounds else None) + "</td><td>" +
                     esc(status) + "</td><td>" + esc(", ".join(item["missing_sources"]) or "—") + "</td></tr>")
    parts.append("</tbody></table></div><p class=muted><small>¹ Filas confirmadas/publicadas del registro, "
                 "no identidades únicas ni éxitos atribuidos. «—» indica fuente ausente; cero indica "
                 "fuente presente sin datos en la ventana. Cola de respuestas compartida: "
                 "no equivale a publicaciones pendientes.</small></p>")
    parts.append("<h2>Tendencia diaria: confirmaciones registradas</h2>")
    for name, item in report["networks"].items():
        if item["actions"] is None:
            continue
        values = item["actions"]["by_day"]
        maximum = max(values.values(), default=0)
        parts.append("<h3>" + esc(name) + "</h3><div>")
        for day, count in values.items():
            width = round(100 * count / maximum) if maximum else 0
            parts.append("<div><small>" + esc(day) + " · " + esc(count) + "</small> "
                         "<span class=bar style='width:" + str(width) + "%'></span></div>")
        parts.append("</div>")
    parts.append("<p class=muted>Exportación local, estática, sin consultas externas.</p></html>")
    return "\n".join(parts)


def _atomic_text(target, content):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".observability-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="directorio de datos; solo lectura")
    parser.add_argument("--output", required=True, type=Path, help="directorio de artefactos saneados")
    parser.add_argument("--as-of", help="fecha/hora local ISO (para ensayo reproducible)")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        parser.error("--root no es un directorio")
    try:
        now = dt.datetime.fromisoformat(args.as_of) if args.as_of else dt.datetime.now()
        if now.tzinfo is not None:
            parser.error("--as-of debe ser hora local sin zona (legacy)")
        report = collect(args.root, as_of=now, days=args.days)
    except ValueError as exc:
        parser.error(str(exc))
    _atomic_text(args.output / "dashboard.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    _atomic_text(args.output / "dashboard.html", render_html(report))
    print("Dashboard saneado creado: dashboard.json, dashboard.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
