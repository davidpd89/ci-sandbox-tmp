"""Panel local de rondas, exclusivamente lectura de fuentes operativas.

Solo el HTML de salida se escribe. No importa daily_review (muta historial),
no consulta APIs, no abre perfiles y no muestra texto, handles o rutas privadas.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import date, datetime, timedelta
from html import escape
import json
import os
from pathlib import Path
import sys
import time
import webbrowser

from zoneinfo import ZoneInfo

import kpi_report
from round_canaries import _confirmed

NETWORKS = tuple(dict.fromkeys((*kpi_report.NETWORKS, "instagram")))
STATES = frozenset(("ok", "parcial", "error", "saltada", "ocupada"))
MADRID = ZoneInfo("Europe/Madrid")
REQUIRED = {"fecha", "red", "fin", "estado", "confirmadas", "fallos", "saltadas", "minutos"}
KINDS = {
    "follows": frozenset(("follow", "seguir", "seguimiento")),
    "likes": frozenset(("like", "favourite", "favorite", "me_gusta", "fav", "like_external")),
    "textos": frozenset(("reply", "comment", "comentario", "respuesta", "comment_external", "reply_external")),
}


def _rounds(path: Path):
    if not path.is_file():
        return [], "ausente"
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
                return [], "cabecera_invalida"
            output, invalid = [], 0
            for row in reader:
                # DictReader almacena columnas sobrantes bajo la clave None y
                # completa columnas ausentes con None: ambas son corrupción.
                if None in row or any(row.get(key) is None for key in REQUIRED):
                    invalid += 1
                    continue
                if row.get("red") not in NETWORKS:
                    continue
                try:
                    day = date.fromisoformat(row["fecha"])
                    clock = datetime.strptime(row["fin"], "%H:%M:%S").time()
                    state = row["estado"]
                    count = _confirmed(row["confirmadas"])
                    fails, skips = int(row["fallos"]), int(row["saltadas"])
                    minutes = float(row["minutos"])
                    if (state not in STATES or count is None or not 0 <= fails <= 1000000
                            or not 0 <= skips <= 1000000 or not 0 <= minutes <= 1440):
                        raise ValueError("fuera de rango")
                    output.append({"day": day, "red": row["red"], "at": datetime.combine(day, clock),
                                   "state": state, "confirmed": count, "fails": fails,
                                   "skips": skips, "minutes": minutes})
                except (TypeError, ValueError, KeyError, OverflowError):
                    invalid += 1
            return output, (f"filas_invalidas:{invalid}" if invalid else None)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        return [], type(exc).__name__


def _counts(kpi):
    if kpi["confirmed_rows"] is None:
        return {kind: None for kind in KINDS}
    by_kind = kpi["confirmed_by_kind"]
    return {key: sum(value for name, value in by_kind.items()
                     if name.casefold().split("+")[0] in variants)
            for key, variants in KINDS.items()}


def _instagram_kpi(root, day):
    # Adaptador de solo lectura: mismo contrato que #64; no atribuye ACK remoto.
    counts, kinds, _, error, duplicates, malformed = kpi_report._activity(root, "instagram", day)
    delta, coverage = kpi_report._followers(root, "instagram", day)
    return {"confirmed_rows": None if error else counts.get("confirmadas", 0),
            "confirmed_by_kind": kinds, "followers_net": delta,
            "followers_coverage": coverage, "outbound_coverage": error or "registro_legacy_sin_ids",
            "duplicate_identical_rows": duplicates, "malformed_rows": malformed}


# Mismos códigos para canarios, anomalías y panel; los datos privados no
# pueden introducir claves libres que se impriman como HTML.
from alert_codes import ALERT_CODES, BLOCKING_CODES
MAX_ALERTS = 40


def _safe_alerts(root, now, collect):
    try:
        data = collect(root, now=now.astimezone(MADRID).replace(tzinfo=None))
        raw = data.get("alerts", ())
        if not isinstance(raw, list):
            raise ValueError("alertas inválidas")
        alerts, seen = [], set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            net = item.get("network") if item.get("network") in NETWORKS else "sistema"
            code = item.get("code")
            # Unknown codes are reported without ever displaying their raw value.
            code = code if isinstance(code, str) and code in ALERT_CODES else "CANARIO_NO_RECONOCIDO"
            severity = item.get("severity") if item.get("severity") in ("alta", "media", "baja") else "media"
            key = (net, code, severity)
            if key in seen:
                continue
            seen.add(key)
            alerts.append({"red": net, "code": code, "severity": severity})
            if len(alerts) >= MAX_ALERTS:
                break
        return alerts
    except (OSError, ValueError, TypeError, ImportError, KeyError):
        return [{"red": "sistema", "code": "CANARIOS_NO_DISPONIBLES", "severity": "alta"}]


def _tiktok_guard_alert(root, now):
    """Consulta la barrera compartida existente: no altera el descanso ni la cuenta.

    Un límite solo de seguimiento NO equivale a prohibir likes/comentarios.
    """
    try:
        import tiktok_safety as safety
    except ImportError:
        return {"red": "tiktok", "code": "TIKTOK_ESTADO_SEGURIDAD_INVALIDO", "severity": "alta"}
    try:
        default_root = Path(__file__).resolve().parents[1]
        path = (safety.COOLDOWN_PATH if root.resolve() == default_root.resolve() else
                str(root / "SISTEMA_DIARIO_TIKTOK" / "bulk_cooldown.json"))
        blocked = set()
        for kind in ("follow", "like"):
            try:
                safety.require_writable(path, now=now, kind=kind)
            except safety.SafetyBlocked:
                blocked.add(kind)
        if blocked == {"follow", "like"}:
            return {"red": "tiktok", "code": "TIKTOK_ESCRITURA_BLOQUEADA", "severity": "alta"}
        if blocked == {"follow"}:
            return {"red": "tiktok", "code": "TIKTOK_SEGUIR_EN_DESCANSO", "severity": "media"}
        return None
    except (OSError, ValueError, TypeError, safety.SafetyStateError):
        return {"red": "tiktok", "code": "TIKTOK_ESTADO_SEGURIDAD_INVALIDO", "severity": "alta"}


def _queue_summary(root):
    folder = root / "00_OPERATIVO" / "_cola_respuestas"
    result = {}
    for name in ("pending", "answers"):
        try:
            data = json.loads((folder / (name + ".json")).read_text(encoding="utf-8"))
            result[name] = len(data) if isinstance(data, dict) else None
        except (OSError, ValueError, UnicodeError):
            result[name] = None
    for chain, label in (("web", "WEB"), ("api", "API"), ("tiktok", "MÓVIL")):
        # Lock presente NO prueba proceso activo. Nunca copiar PID al HTML.
        result[label] = (root / "00_OPERATIVO" / f"cola_rondas_{chain}.lock").exists()
    result["parar"] = (root / "00_OPERATIVO" / "cola_parar.flag").exists()
    result["recargar"] = (root / "00_OPERATIVO" / "cola_recargar.flag").exists()
    return result


def build(root, *, now=None, targets=None, kpi_builder=None, canaries_collector=None):
    root = Path(root)
    now = now or datetime.now(MADRID)
    if now.tzinfo is None:
        now = now.replace(tzinfo=MADRID)
    day = now.astimezone(MADRID).date()
    kpi_builder = kpi_builder or kpi_report.build_report
    current = kpi_builder(root, day)["networks"]
    if canaries_collector is None:
        from round_canaries import collect
        canaries_collector = collect
    alerts = _safe_alerts(root, now, canaries_collector)
    tiktok_guard = _tiktok_guard_alert(root, now)
    if tiktok_guard:
        alerts.append(tiktok_guard)
    rounds, error = _rounds(root / "00_OPERATIVO" / "tiempos_rondas.csv")
    window = [day - timedelta(days=offset) for offset in range(13, -1, -1)]
    grouped = defaultdict(list)
    for item in rounds if error is None else ():
        # No construir métricas parciales a partir de CSV corrupto.
        if item["day"] in window and item["at"].replace(tzinfo=MADRID) <= now:
            grouped[(item["red"], item["day"])].append(item)
    networks = {}
    for net in NETWORKS:
        kpi = current[net] if net in current else _instagram_kpi(root, day)
        today = sorted(grouped[(net, day)], key=lambda r: r["at"])
        # Comparar la misma hora del día: evita interpretar una mañana
        # parcial como caída frente a siete jornadas completas.
        past = [[r for r in grouped[(net, d)] if r["at"].time() <= now.time()]
                for d in window[-8:-1]]
        daily_rounds = [sum(r["confirmed"] for r in rows) for rows in past if rows]
        average = sum(daily_rounds) / len(daily_rounds) if daily_rounds else None
        last = today[-1] if today else None
        done = sum(item["state"] in ("ok", "parcial") for item in today)
        n_errors = sum(item["state"] == "error" for item in today)
        issues = [a["code"] for a in alerts if a["red"] == net]
        blocker = any(a["code"] in BLOCKING_CODES and a["red"] == net for a in alerts)
        danger = any(a["severity"] == "alta" and a["red"] == net for a in alerts)
        status = ("pausada" if blocker else
                  "error" if (last and last["state"] == "error") or danger else
                  "aviso" if n_errors or issues or (last and last["state"] in ("saltada", "ocupada", "parcial")) or (done and kpi["confirmed_rows"] == 0) else
                  "ok" if done else "sin_datos")
        history = []
        for historical_day in window:
            entries = grouped[(net, historical_day)]
            history.append({"day": historical_day.isoformat(),
                            "status": ("sin_datos" if not entries else
                                       "error" if max(entries, key=lambda x: x["at"])["state"] == "error" else
                                       "aviso" if any(x["state"] in ("error", "parcial", "saltada", "ocupada") for x in entries) else
                                       "ok" if any(x["state"] == "ok" for x in entries) else "aviso"),
                            "total": sum(x["confirmed"] for x in entries) if entries else None})
        networks[net] = {"status": status, "rounds": done if error is None else None,
                         "target": (targets or {}).get(net), "last": last,
                         "errors": sum(x["fails"] for x in today) if error is None else None,
                         "round_errors": n_errors if error is None else None,
                         "skipped": sum(x["state"] == "saltada" for x in today) if error is None else None,
                         "busy": sum(x["state"] == "ocupada" for x in today) if error is None else None,
                         "confirmed_rows": kpi["confirmed_rows"], "kinds": _counts(kpi),
                         "followers_net": kpi["followers_net"],
                         "coverage": kpi["outbound_coverage"],
                         "mean7_round_confirmed": average, "trend_rounds": (None if error is not None or not average else
                         round(100 * (sum(x["confirmed"] for x in today) / average - 1))),
                         "history": history, "alerts": issues}
    if error:
        alerts.insert(0, {"red": "sistema", "code": "REGISTRO_RONDAS_" + ("INVALIDO" if error != "ausente" else "AUSENTE"), "severity": "alta"})
    return {"day": day.isoformat(), "at": now.isoformat(timespec="seconds"),
            "networks": networks, "alerts": alerts, "queue": _queue_summary(root)}


def _display(value):
    return "ND" if value is None else str(value)


def render_text(data, red=None):
    lines = [f"Estado de rondas · {data['at']} · Filas legacy (NO ACK remoto verificado)",
             "Red          Estado      Rondas     Última     Filas  Follows  Likes  Textos  Fallos  Salt/Ocup  Δseg  vs7d"]
    for name, info in data["networks"].items():
        if red and red != name:
            continue
        last = info["last"]
        stamp = (last["at"].strftime("%H:%M") + "/" + last["state"][:3]) if last else "ND"
        line = (f"{name:<12} {info['status']:<11} "
                f"{(_display(info['rounds'])+'/'+_display(info['target'])):<10} {stamp:<10} "
                f"{_display(info['confirmed_rows']):>5} "
                f"{_display(info['kinds']['follows']):>7} {_display(info['kinds']['likes']):>6} "
                f"{_display(info['kinds']['textos']):>7} {_display(info['errors']):>6} "
                f"{(_display(info['skipped'])+'/'+_display(info['busy'])):<9} {_display(info['followers_net']):>5} "
                f"{(_display(info['trend_rounds'])+'%') if info['trend_rounds'] is not None else 'ND':>6}")
        lines.append(line)
    lines += ["", "Alertas (códigos; sin datos privados):"] + [f"- {a['red']}: {a['code']}" for a in data["alerts"]]
    lines.append("ND = no disponible; las rondas y los registros de interacción son fuentes diferentes.")
    return "\n".join(lines) + "\n"


def render_html(data, red=None, live=False):
    def e(value):
        return escape(_display(value), quote=True)
    filtered = [(n, v) for n, v in data["networks"].items() if not red or n == red]
    rows = []
    for net, item in filtered:
        latest = item["last"]
        last = f"{latest['at']:%H:%M} · {latest['state']}" if latest else "ND"
        h = "".join(f'<span class="cell {x["status"]}" title="{e(x["day"])}: {e(x["total"])}">{e(x["day"][-2:])}</span>' for x in item["history"])
        rows.append(f'<tr><th>{e(net)}</th><td class="{e(item["status"])}">{e(item["status"])}</td>'
                    f'<td>{e(item["rounds"])}/{e(item["target"])}</td><td>{e(last)}</td>'
                    f'<td>{e(item["confirmed_rows"])}</td><td>{e(item["kinds"]["follows"])}</td>'
                    f'<td>{e(item["kinds"]["likes"])}</td><td>{e(item["kinds"]["textos"])}</td>'
                    f'<td>{e(item["errors"])}</td><td>{e(item["skipped"])}/{e(item["busy"])}</td>'
                    f'<td>{e(item["followers_net"])}</td><td>{e(str(item["trend_rounds"]) + "%" if item["trend_rounds"] is not None else None)}</td><td>{h}</td></tr>')
    alerts = "".join(f'<li class="alert-{e(x["severity"])}">{e(x["red"])} · {e(x["severity"])}: {e(x["code"])}</li>' for x in data["alerts"])
    q = data["queue"]
    locks = " · ".join(f"{e(c)}: {'lock presente (no implica activo)' if q[c] else 'sin lock'}" for c in ("WEB", "API", "MÓVIL"))
    refresh = '<meta http-equiv="refresh" content="30">' if live else ""
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8">{refresh}'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;">'
            '<title>Estado de rondas</title><style>'
            'body{font:15px system-ui,sans-serif;background:#f5f6f8;color:#18212e;margin:24px}'
            'main{max-width:1600px;margin:auto}h1{margin-bottom:4px}.muted{color:#475467}'
            '.wrap{overflow-x:auto;background:white;border:1px solid #ccd2dc;border-radius:8px}'
            'table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:10px;border-bottom:1px solid #e7e9ef;text-align:left;white-space:nowrap}'
            '.ok{background:#dcfce7}.aviso{background:#fef3c7}.pausada,.error{background:#fee2e2}'
            '.sin_datos{background:#e5e7eb}.cell{display:inline-block;padding:4px;margin:1px;border-radius:3px}'
            '.notice{background:white;padding:12px;border-radius:8px;margin:12px 0}ul{margin-bottom:4px}.alert-alta{border-left:4px solid #991b1b;padding-left:8px}.alert-media{border-left:4px solid #92400e;padding-left:8px}'
            '</style></head><body><main><h1>Estado de las rondas</h1>'
            f'<p class="muted">Actualizado {e(data["at"])} · Sin red ni lectura de credenciales · ND ≠ 0</p>'
            f'<div class="notice">{locks}<p>Respuestas pendientes: {e(q["pending"])} · respuestas almacenadas: {e(q["answers"])}'
            f' · señal parar: {e(q["parar"])} · recargar: {e(q["recargar"])}</p></div>'
            f'<section class="notice"><h2>Avisos</h2><ul>{alerts or "<li>Sin alertas registradas</li>"}</ul></section>'
            '<div class="wrap"><table><thead><tr><th>Red</th><th>Estado</th><th>Rondas</th>'
            '<th>Última</th><th>Filas confirmadas*</th><th>Follows*</th><th>Likes*</th>'
            '<th>Textos*</th><th>Fallos de acciones</th><th>Rondas saltadas/ocupadas</th><th>Δ seguidores*</th><th>vs7d rondas</th><th>14 días: rondas</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            '<p class="muted">* Fuente: registros locales heredados; no implica ACK remoto ni causalidad. '
            'Histórico: estados observados por día; «saltada» no acredita una pausa. ND si no hay filas. '
            'Comparación vs7d: confirmaciones anotadas en tiempos_rondas, solo días observados (ND si no hay base). Objetivos no acreditados aparecen como ND. No se muestran textos ni destinatarios.</p>'
            '</main></body></html>')


def write_html(path, html):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sólo se reemplaza el HTML publicado, nunca CSV, locks ni JSON operativos.
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(html, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vista local, sin escrituras operativas")
    parser.add_argument("texto", nargs="?", choices=["texto"])
    parser.add_argument("--red", choices=NETWORKS)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--html-path", type=Path)
    parser.add_argument("--vivo", action="store_true", help="regenera el HTML cada 30 s hasta Ctrl+C")
    args = parser.parse_args(argv)
    path = args.html_path or args.root / "00_OPERATIVO" / "ESTADO_RONDAS.html"
    if args.texto and args.vivo:
        parser.error("texto y --vivo no son compatibles")
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    first = True
    try:
        while True:
            report = build(args.root)
            if args.texto:
                print(render_text(report, args.red), end="")
                return 0
            write_html(path, render_html(report, args.red, live=args.vivo))
            if first:
                print(f"Panel local actualizado: {path}")
                if args.vivo:
                    webbrowser.open(path.resolve().as_uri())
            first = False
            if not args.vivo:
                return 0
            time.sleep(30)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
