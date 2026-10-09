"""Lectura forense de KPIs locales, sin API, SQLite, locks ni escrituras.

Los CSV legacy NO contienen un ID de evento fiable y parte de los registros
no tiene cabecera. No se deduce éxito remoto de colas, planes ni rondas.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

NETWORKS = ("bluesky", "mastodon", "x", "threads", "facebook", "pinterest", "reddit", "tiktok")
SCHEMA_VERSION = 1
# loyalty.HARVEST solo cosecha en estas redes en la base de esta PR.
INBOUND_HARVEST_NETWORKS = frozenset(("bluesky", "mastodon"))
MADRID = ZoneInfo("Europe/Madrid")
CONFIRMED = frozenset(("confirmado", "publicado"))
SOURCE_PATTERN = re.compile(r"(?:^|[\s|;])(?:source|fuente|origen)=([\w.:-]+)", re.I)
THOUSANDS = re.compile(r"\d{1,3}(?:[.,]\d{3})+")


def _local_day(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value = value.strip()
        if len(value) == 10:
            return date.fromisoformat(value)
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (stamp.astimezone(MADRID) if stamp.tzinfo else stamp).date()
    except ValueError:
        return None


def _integer(value):
    text = str(value or "").strip()
    # Un CSV corrupto puede contener miles de dígitos: int() los rechaza
    # en Python 3.11 y tumbaría el informe de todas las redes.
    if not 1 <= len(text) <= 32 or not text.isascii():
        return None
    if text.isdecimal():
        return int(text)
    if THOUSANDS.fullmatch(text):
        return int(text.replace(".", "").replace(",", ""))
    return None


def _rows(path):
    """Devuelve (filas, error). Errores de permisos/BOM/corrupción visibles."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.reader(stream, strict=True)), None
    except FileNotFoundError:
        return [], "ausente"
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], type(exc).__name__


def _mapping(rows, columns, *, required=None):
    """Devuelve (filas mapeadas, error); nunca trunca columnas en silencio."""
    if rows and rows[0] and rows[0][0].strip().casefold() == "fecha":
        names = [name.strip().casefold() for name in rows[0]]
        required = set(columns if required is None else required)
        if len(names) != len(set(names)) or not required.issubset(names):
            return (), "cabecera_invalida"
        return ((dict(zip(names, row)), len(row) != len(names))
                for row in rows[1:]), None
    return ((dict(zip(columns, row)), len(row) != len(columns))
            for row in rows), None


def _source(record):
    for key in ("source", "fuente", "origen"):
        found = str(record.get(key) or "").strip()
        if found:
            return found[:80]
    match = SOURCE_PATTERN.search(str(record.get("notas") or ""))
    return match.group(1)[:80] if match else None


def _status(result):
    result = str(result or "").strip().casefold()
    if result in CONFIRMED:
        return "confirmadas"
    if result.startswith(("pendiente", "incierto")) or "incierto" in result:
        return "inciertas"
    if result.startswith(("fallo", "error", "parada")):
        return "fallidas_registradas"
    if result.startswith(("saltado", "omitido", "no_intentado", "abstenido")):
        return "omitidas_registradas"
    return "resultado_desconocido"


def _activity(root, net, day):
    path = root / f"SISTEMA_DIARIO_{net.upper()}" / "registro_interacciones.csv"
    rows, error = _rows(path)
    columns = ("fecha", "cuenta", "url", "tipo", "texto", "resultado", "notas") if net == "reddit" else (
        "fecha", "cuenta", "tipo", "post_resumen", "texto", "resultado", "notas")
    # Los CSV reales nombrados usan aliases distintos por red
    # (texto_usado, subreddit/hilo_url...). Solo estos tres campos son
    # necesarios para computar la actividad; el legacy sin cabecera sigue
    # siendo posicional.
    mapped, schema_error = _mapping(
        rows, columns, required=("fecha", "tipo", "resultado")
    )
    if schema_error:
        return {}, {}, {}, schema_error, 0, max(len(rows) - 1, 0)
    counts, by_kind, by_source = Counter(), Counter(), Counter()
    duplicates = bad = 0
    seen = set()
    for entry, malformed in mapped:
        local_day = _local_day(entry.get("fecha"))
        if malformed or local_day is None:
            bad += 1
            continue
        if local_day != day:
            continue
        # Sin ID de evento: eliminar solo filas *idénticas*; no deduplicar
        # por cuenta, tipo o fecha, pues hay acciones legítimas repetidas.
        fingerprint = tuple(sorted((str(k), str(v)) for k, v in entry.items()))
        if fingerprint in seen:
            duplicates += 1
            continue
        seen.add(fingerprint)
        outcome = _status(entry.get("resultado"))
        counts[outcome] += 1
        if outcome == "confirmadas":
            kind = str(entry.get("tipo") or "sin_tipo").strip().casefold()
            by_kind[kind] += 1
            by_source[_source(entry) or "sin_atribucion"] += 1
    return dict(counts), dict(sorted(by_kind.items())), dict(sorted(by_source.items())), error, duplicates, bad


def _followers(root, net, day):
    path = root / f"SISTEMA_DIARIO_{net.upper()}" / "metricas.csv"
    rows, error = _rows(path)
    if error:
        return None, error

    # Con cabecera, la semántica manda: Reddit registra karma_visible y no
    # puede reinterpretarse como seguidores. El legacy sin cabecera conserva
    # la segunda columna solo en redes cuyo histórico sí era de seguidores.
    data_rows = rows
    follower_index = 1
    if rows and rows[0] and rows[0][0].strip().casefold() == "fecha":
        names = [name.strip().casefold() for name in rows[0]]
        if len(names) != len(set(names)) or "seguidores" not in names:
            return None, "sin_columna_seguidores"
        follower_index = names.index("seguidores")
        data_rows = rows[1:]
    elif net == "reddit":
        return None, "sin_columna_seguidores"

    previous = current = None
    for row in data_rows:
        if len(row) <= follower_index:
            continue
        stamp, value = _local_day(row[0]), _integer(row[follower_index])
        if stamp is None or value is None:
            continue
        if stamp < day and (previous is None or stamp >= previous[0]):
            previous = (stamp, value)
        elif stamp == day:
            current = (stamp, value)
    if current is None:
        return None, "sin_snapshot_del_dia"
    if previous is None:
        return None, "sin_snapshot_previo"
    if (day - previous[0]).days > 7:
        return None, "snapshot_previo_obsoleto"
    return current[1] - previous[1], "dos_snapshots_locales"


def _inbound(root, day):
    rows, error = _rows(root / "00_OPERATIVO" / "inbound_interacciones.csv")
    if error:
        return None, error
    mapped, schema_error = _mapping(rows, ("fecha", "red", "handle", "tipo"))
    if schema_error:
        return None, schema_error
    counts = Counter()
    seen = set()
    incomplete = False
    for entry, malformed in mapped:
        local_day = _local_day(entry.get("fecha"))
        if malformed or local_day is None:
            incomplete = True
            continue
        if local_day != day:
            continue
        if (entry.get("red") not in NETWORKS or not entry.get("handle")
                or entry.get("tipo") not in ("comment", "like", "repost", "follow")):
            incomplete = True
            continue
        key = (entry.get("fecha"), entry.get("red"), entry.get("handle"), entry.get("tipo"))
        if key in seen:
            continue
        seen.add(key)
        if entry.get("tipo") == "comment":
            counts[entry["red"]] += 1
    # Una fila indescifrable podría ocultar otro comentario; el cero deja
    # de ser un valor defendible, incluso si hay otras filas correctas.
    if incomplete:
        return None, "registro_inbound_parcial"
    return counts, "cuentas_tipo_dia_solo_harvest"


def build_report(root, day):
    """Ocho redes, contrato explícito de desconocidos; no abre rutas en escritura."""
    root = Path(root)
    if isinstance(day, datetime):
        day = (day.astimezone(MADRID) if day.tzinfo else day).date()
    elif not isinstance(day, date):
        day = date.fromisoformat(str(day))
    inbound, inbound_coverage = _inbound(root, day)
    result = {"schema_version": SCHEMA_VERSION, "day": day.isoformat(), "timezone": "Europe/Madrid", "networks": {}}
    for net in NETWORKS:
        statuses, kinds, sources, file_error, duplicates, malformed = _activity(root, net, day)
        follower_delta, follower_coverage = _followers(root, net, day)
        coverage = (file_error or ("registro_parcial_filas_invalidas"
                                   if malformed else "registro_legacy_sin_ids"))

        def observed_status(key):
            if file_error:
                return None
            count = statuses.get(key, 0)
            # Los valores positivos son evidencia parcial (cota inferior).
            # Si faltan filas, cero no equivale a ausencia de actividad.
            return None if malformed and count == 0 else count

        observed = observed_status("confirmadas")
        result["networks"][net] = {
            "confirmed_rows": observed,
            "confirmed_by_kind": kinds,
            "confirmed_by_source": sources,
            "pending_unknown_rows": observed_status("inciertas"),
            "failed_logged_rows": observed_status("fallidas_registradas"),
            "omitted_logged_rows": observed_status("omitidas_registradas"),
            "unclassified_rows": observed_status("resultado_desconocido"),
            "duplicate_identical_rows": duplicates,
            "malformed_rows": malformed,
            "outbound_coverage": coverage,
            "incoming_comment_account_days": None if inbound is None or net not in INBOUND_HARVEST_NETWORKS else inbound.get(net, 0),
            "incoming_coverage": inbound_coverage if net in INBOUND_HARVEST_NETWORKS else "sin_cosecha_instrumentada",
            "followers_net": follower_delta,
            "followers_coverage": follower_coverage,
            "denominators": {key: None for key in (
                "candidates", "planned", "queued", "written", "abstained", "rejected", "attempted", "replies_to_own_comments")},
        }
    return result


def render_markdown(report):
    lines = [f"# KPIs observables — {report['day']} (Europe/Madrid)", "",
             "| Red | Filas confirmadas* | Pendientes/unknown | Fallidas registradas | Comentarios entrantes** | Seguidores netos*** | Procedencia confirmada |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for net, row in report["networks"].items():
        fmt = lambda value: "ND" if value is None else str(value)
        known = sum(v for k, v in row["confirmed_by_source"].items() if k != "sin_atribucion")
        attribution = f"{known}/{row['confirmed_rows']}" if row["confirmed_rows"] is not None else "ND"
        lines.append(f"| {net} | {fmt(row['confirmed_rows'])} | {fmt(row['pending_unknown_rows'])} | {fmt(row['failed_logged_rows'])} | {fmt(row['incoming_comment_account_days'])} | {fmt(row['followers_net'])} | {attribution} |")
    lines += ["", "* No son ACK remotos revalidados: son filas de registro; los duplicados idénticos se excluyen. Si hay filas malformadas, los recuentos positivos son cotas inferiores y el cero se muestra ND. Sin IDs estables no se garantiza unicidad ni cobertura completa.",
              "** Cuentas/tipo/día registradas por cosecha; no son todas las respuestas ni atribuyen causalidad a acciones propias.",
              "*** Diferencia entre la última observación del día y el último snapshot previo (máximo 7 días); ND no significa cero.",
              "Planes, candidatos, intentos, rechazos y respuestas causadas son ND sin eventos instrumentados. Nunca se deducen del número de rondas."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="KPIs locales de solo lectura para las ocho redes")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--day", default=datetime.now(MADRID).date().isoformat())
    parser.add_argument("--json", action="store_true", help="emitir JSON por stdout; no escribe ficheros")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.root, args.day)
    except ValueError as exc:
        parser.error(f"día inválido: {exc}")
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
