"""R6: canarios de salud basados SOLO en ficheros locales, sin IA ni red.

Lectura: tiempos_rondas.csv, _cola_respuestas/pending.json/worker.lock y
SISTEMA_DIARIO_*/cache/breaker.json. Nunca accede a cuentas ni inicia rondas.
Uso: python tools/round_canaries.py --check-only
     python tools/round_canaries.py  # exporta 00_OPERATIVO/cache/alertas_rondas.json

Esta PR prepara el canario; su activación cada 30-60 min en Windows y la
integración en el panel requieren comprobación local y PR separada.
"""
from __future__ import annotations

import argparse
import ast
import csv
import datetime as dt
import json
import os
import pathlib
import sys
import stat
import threading

NETWORKS = ("bluesky", "mastodon", "threads", "x", "facebook",
            "pinterest", "reddit", "tiktok")
COLUMNS = {"fecha", "red", "fin", "estado", "confirmadas", "fallos", "codigo"}
LOOKBACK_MINUTES = 180
STALE_WORKER_MINUTES = 25
WORKER_HOURS = range(8, 23)


def _alert(code: str, severity: str, network: str | None = None, **details) -> dict:
    return {"code": code, "severity": severity, "network": network, **details}


def _confirmed(text: object) -> int | None:
    """CSV actual: "{'like': 39, 'follow': 1}"; no hacer eval()."""
    if isinstance(text, int) and not isinstance(text, bool):
        return text if text >= 0 else None
    if not isinstance(text, str) or len(text) > 2048:
        return None
    value = text.strip()
    if value in ("", "{}"):
        return 0          # 08/10: la cola escribe `confirmadas` vacio en rondas saltada/ocupada/error (datos reales); no es un registro corrupto
    if value.isdecimal():
        return int(value)
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError, TypeError, RecursionError, MemoryError):
        return None
    if not isinstance(parsed, dict):
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 1000000
               for v in parsed.values()):
        return None
    return sum(parsed.values())


def _read_recent(path: pathlib.Path, now: dt.datetime) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not COLUMNS.issubset(reader.fieldnames):
            raise ValueError("cabecera de tiempos_rondas.csv incorrecta")
        recent = []
        for row in reader:
            if not row.get("fecha") or not row.get("fin"):
                raise ValueError("fila sin fecha/fin")
            try:
                when = dt.datetime.fromisoformat(row["fecha"] + "T" + row["fin"])
                failed = int(row["fallos"])
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError("fila temporal o contadores inválidos") from exc
            minutes = (now - when).total_seconds() / 60
            if minutes < 0 or minutes > LOOKBACK_MINUTES:
                continue
            if failed < 0:
                raise ValueError("fallos negativos")
            confirmed = _confirmed(row["confirmadas"])
            if confirmed is None:
                raise ValueError("desglose de confirmaciones inválido")
            if row.get("red") not in NETWORKS:
                continue
            code = (row.get("codigo") or "").strip()
            # Código de salida numérico, nunca texto privado de la ronda.
            code = int(code) if len(code) <= 6 and code.lstrip("-").isdigit() else None
            recent.append({"network": row["red"], "state": row["estado"],
                           "when": when, "confirmed": confirmed, "failed": failed,
                           "return_code": code})
    return recent


def _breaker_alerts(root: pathlib.Path, now: dt.datetime) -> list[dict]:
    alerts = []
    for network in NETWORKS:
        path = root / f"SISTEMA_DIARIO_{network.upper()}" / "cache" / "breaker.json"
        if not path.exists():
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            until = obj.get("open_until") if isinstance(obj, dict) else None
            if until:
                end = dt.datetime.fromisoformat(until)
                if now < end:
                    alerts.append(_alert("CORTACIRCUITOS_ABIERTO", "alta", network,
                                         until=end.isoformat(timespec="minutes")))
        except (OSError, ValueError, TypeError) :
            alerts.append(_alert("BREAKER_INVALIDO", "alta", network))
    return alerts


def _worker_alerts(root: pathlib.Path, now: dt.datetime, pid_alive) -> list[dict]:
    if now.hour not in WORKER_HOURS:
        return []
    folder = root / "00_OPERATIVO" / "_cola_respuestas"
    pending_file = folder / "pending.json"
    if not pending_file.exists():
        return []
    try:
        pending = json.loads(pending_file.read_text(encoding="utf-8"))
        if not isinstance(pending, dict):
            raise ValueError("pending debe ser objeto")
        if not pending:
            return []
        ages = []
        for item in pending.values():
            if not isinstance(item, dict) or not isinstance(item.get("ts"), str):
                raise ValueError("entrada sin ts")
            ages.append((now - dt.datetime.fromisoformat(item["ts"])).total_seconds() / 60)
        if not ages or max(ages) < STALE_WORKER_MINUTES:
            return []
    except (OSError, ValueError, TypeError):
        return [_alert("COLA_INVALIDA", "alta")]

    try:
        pid = int((folder / "worker.lock").read_text(encoding="utf-8").strip())
        active = pid > 0 and bool(pid_alive(pid))
    except (OSError, ValueError, TypeError):
        active = False
    return [] if active else [
        _alert("TRABAJADOR_PARADO", "alta", pending_count=len(pending),
               oldest_minutes=int(max(ages)))
    ]



RECOVERY_WINDOW_SECONDS = 24 * 60 * 60
RECOVERY_ESCALATION_COUNT = 3  # criterio local: 1-2 avisos; 3+ alta
EVENT_RETENTION_DAYS = 7
MAX_EVENT_BYTES = 16_384
RECOVERED_QUEUE_FILES = ("answers.json", "pending.json")


def _unique_event_pairs(pairs: list[tuple[str, object]]) -> dict:
    """El emisor nunca escribe claves repetidas: no aceptar ambigüedades."""
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("clave JSON de evento repetida")
        result[name] = value
    return result


def _reject_event_constant(value: str):
    """NaN/Infinity se admiten por defecto en Python, pero no en JSON RFC 8259."""
    raise ValueError("constante JSON no válida")


def _read_local_event(path: pathlib.Path) -> dict | None:
    """Lectura acotada por BYTES y tipo de archivo; no sigue symlinks estables."""
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_EVENT_BYTES:
            return None
        with path.open("rb") as stream:
            raw = stream.read(MAX_EVENT_BYTES + 1)
            opened = os.fstat(stream.fileno())
        if (len(raw) > MAX_EVENT_BYTES or
                (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)):
            return None
        data = json.loads(raw.decode("utf-8"),
                          object_pairs_hook=_unique_event_pairs,
                          parse_constant=_reject_event_constant)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, UnicodeError, TypeError):
        return None


def _event_age_seconds(event: dict, now: dt.datetime) -> float | None:
    """Los eventos R8/R5 guardan hora local sin offset; acepta ISO con offset."""
    raw = event.get("at")
    if not isinstance(raw, str) or len(raw) > 48:
        return None
    try:
        stamp = dt.datetime.fromisoformat(raw)
        if now.tzinfo is None and stamp.tzinfo is not None:
            now = now.astimezone()  # interpretar now local, no UTC por defecto
        elif now.tzinfo is not None and stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=now.tzinfo)
        return (now - stamp).total_seconds()
    except (ValueError, OverflowError, TypeError):
        return None


def _queue_recovery_alerts(root: pathlib.Path, now: dt.datetime) -> list[dict]:
    """Agrega los eventos de #105 (24 h); solo etiquetas de cola permitidas."""
    directory = root / "00_OPERATIVO" / "cache" / "errores_cola"
    try:
        if not directory.is_dir():
            return []
        count = 0
        affected = set()
        latest_age = None
        for path in directory.glob("*.json"):
            event = _read_local_event(path)
            if not event or event.get("code") != "COLA_CORRUPTA_RECUPERADA":
                continue
            age = _event_age_seconds(event, now)
            if age is None or not 0 <= age <= RECOVERY_WINDOW_SECONDS:
                continue
            count += 1
            file_name = event.get("file")
            affected.add(file_name if isinstance(file_name, str)
                         and file_name in RECOVERED_QUEUE_FILES else "desconocido")
            latest_age = age if latest_age is None else min(latest_age, age)
    except OSError:
        # Lectura imposible: no aparentar que la cola está sana.
        return [_alert("REGISTRO_EVENTOS_COLA_INACCESIBLE", "alta")]
    if not count:
        return []
    severity = "alta" if count >= RECOVERY_ESCALATION_COUNT else "media"
    return [_alert("COLA_CORRUPTA_RECUPERADA", severity,
                   events_in_24h=count, files=sorted(affected),
                   last_event_age_minutes=int(latest_age // 60))]


def prune_event_history(root: str | pathlib.Path, *,
                        now: dt.datetime | None = None) -> int:
    """Retiene eventos >=7 d; sin purgar copias de cuarentena ni archivos nuevos.

    Requiere fecha del evento Y antigüedad física. Revalida metadatos antes
    de borrar para evitar un archivo reemplazado durante la lectura.
    Solo lo llama el CLI de exportación; --check-only siempre es solo lectura.
    """
    root = pathlib.Path(root)
    now = now or dt.datetime.now()
    cutoff = now.timestamp() - EVENT_RETENTION_DAYS * 86400
    removed = 0
    for folder in ("errores_cola", "errores_plan"):
        directory = root / "00_OPERATIVO" / "cache" / folder
        try:
            if not directory.is_dir():
                continue
            for path in directory.glob("*.json"):
                try:
                    before = path.lstat()
                    if (not stat.S_ISREG(before.st_mode) or
                            before.st_mtime >= cutoff):
                        continue
                    event = _read_local_event(path)
                    if not event:
                        continue
                    if folder == "errores_cola":
                        recognized = event.get("code") == "COLA_CORRUPTA_RECUPERADA"
                    else:
                        recognized = (event.get("schema") == 1
                                      and event.get("red") in NETWORKS
                                      and isinstance(event.get("stage"), str))
                    age = _event_age_seconds(event, now)
                    if not recognized or age is None or age <= EVENT_RETENTION_DAYS * 86400:
                        continue
                    after = path.lstat()
                    # No eliminar si cambió desde que se validó o ahora es un link.
                    fingerprint = lambda obj: (obj.st_dev, obj.st_ino, obj.st_size,
                                                obj.st_mtime_ns, obj.st_ctime_ns)
                    if (not stat.S_ISREG(after.st_mode)
                            or fingerprint(before) != fingerprint(after)):
                        continue
                    path.unlink()
                    removed += 1
                except (OSError, ValueError):
                    # Limpieza best-effort, nunca impide emitir el informe.
                    continue
        except OSError:
            continue
    return removed


def collect(root: str | pathlib.Path, *, now: dt.datetime | None = None,
            pid_alive=None) -> dict:
    """Informe agregado, sin copiar mensajes privados ni handles."""
    root = pathlib.Path(root)
    now = now or dt.datetime.now()
    if pid_alive is None:
        from mobile_runtime import _pid_alive
        pid_alive = _pid_alive
    alerts = []
    register_valid = True
    try:
        rows = _read_recent(root / "00_OPERATIVO" / "tiempos_rondas.csv", now)
    except (OSError, ValueError):
        rows = []
        register_valid = False
        alerts.append(_alert("REGISTRO_INVALIDO", "alta"))
    per_network = {}
    for network in NETWORKS:
        recent = sorted((r for r in rows if r["network"] == network), key=lambda r: r["when"])
        attempts = [r for r in recent if r["state"] in ("ok", "parcial", "error")]
        if not recent:
            continue
        per_network[network] = {
            "rounds_in_window": len(recent),
            "attempts_in_window": len(attempts),
            "confirmed_in_window": sum(r["confirmed"] for r in attempts),
            "errors_in_window": sum(r["state"] == "error" for r in attempts),
            "partial_in_window": sum(r["state"] == "parcial" for r in attempts),
        }
        if recent[-1]["state"] == "parcial":
            alerts.append(_alert("RONDA_PARCIAL", "media", network,
                                 failed=recent[-1]["failed"]))
        consecutive = 0
        for item in reversed(attempts):
            if item["state"] != "error":
                break
            consecutive += 1
        if consecutive >= 3:
            alerts.append(_alert("ERRORES_SEGUIDOS", "alta", network,
                                 consecutive=consecutive,
                                 last_return_code=attempts[-1]["return_code"],
                                 last_failed_actions=attempts[-1]["failed"]))
        if len(attempts) >= 3 and all(r["confirmed"] == 0 for r in attempts[-3:]):
            alerts.append(_alert("SIN_CONFIRMACIONES", "alta", network, last_attempts=3))

    if register_valid:
        from round_absence import collect as expected_rounds_alerts
        alerts.extend(expected_rounds_alerts(root, now, rows))
    alerts.extend(_breaker_alerts(root, now))
    alerts.extend(_worker_alerts(root, now, pid_alive))
    alerts.extend(_queue_recovery_alerts(root, now))
    # Plan local: al menos 3 fallos recientes generan alerta; se conserva
    # también el lector de cuarentena ya incorporado por #120.
    from plan_failure_events import collect_alerts
    alerts.extend(collect_alerts(root, now=now))
    return {
        "schema": 1, "generated_at": now.isoformat(timespec="seconds"),
        "window_minutes": LOOKBACK_MINUTES, "by_network": per_network, "alerts": alerts,
    }


def save_report(path: str | pathlib.Path, report: dict) -> None:
    """Solo agregados, escritura atómica incluso con lectores del panel."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Canarios RRSS: no interactúa con redes")
    parser.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[1]))
    parser.add_argument("--check-only", action="store_true",
                        help="solo lectura: no genera fichero de alerta")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    try:
        report = collect(root)
        if not args.check_only:
            save_report(root / "00_OPERATIVO" / "cache" / "alertas_rondas.json", report)
            prune_event_history(root)
    except OSError as exc:
        print(f"FALLO_CANARIO: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps({
        "alert_count": len(report["alerts"]),
        "high_severity": sum(x["severity"] == "alta" for x in report["alerts"]),
        "codes": sorted({x["code"] for x in report["alerts"]}),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
