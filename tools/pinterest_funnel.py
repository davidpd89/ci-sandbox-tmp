"""Embudo Pinterest de solo lectura: estadísticas orgánicas y atribución GA4 separadas.

Acepta CSV normalizados explícitos; NO consulta cuentas, no publica ni modifica
registros operativos. Ausencia de observación es ND, nunca cero o conversión.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

PIN_FIELDS = ("fecha", "tablero", "pin_id", "origen", "periodo", "nivel", "impresiones", "guardados", "clics_pin", "clics_salientes")
WEB_FIELDS = ("fecha", "campana_utm", "fuente", "medio", "ambito", "modelo_atribucion", "nombre_evento", "sesiones", "eventos_clave")
PIN_METRICS = PIN_FIELDS[6:]
MAX_ROWS = 20000
MAX_FILE_BYTES = 10_000_000


class InvalidMetrics(ValueError):
    """Entrada incompleta o ambigua: no producir cifras parciales."""


def _read(path, columns):
    if path is None:
        return None
    try:
        if Path(path).stat().st_size > MAX_FILE_BYTES:
            raise InvalidMetrics("archivo CSV demasiado grande")
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True, restkey="__extra__")
            if tuple(reader.fieldnames or ()) != columns:
                raise InvalidMetrics("cabecera no coincide con el contrato")
            rows = []
            for number, row in enumerate(reader, 2):
                if number > MAX_ROWS + 1:
                    raise InvalidMetrics("demasiadas filas")
                if "__extra__" in row or any(value is None for value in row.values()):
                    raise InvalidMetrics(f"fila {number} truncada o con columnas extra")
                rows.append(row)
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise InvalidMetrics(f"CSV ilegible ({type(exc).__name__})") from exc


def _day(value):
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidMetrics("fecha no válida") from exc


def _label(value, field):
    if not value or value != value.strip() or len(value) > 120 or any(ord(c) < 32 or c == "|" for c in value):
        raise InvalidMetrics(f"{field} vacío o inseguro")
    return value


def _amount(value, *, decimal=False):
    if value == "":
        return None
    if not re.fullmatch(r"\d+(?:\.\d+)?" if decimal else r"\d+", value):
        raise InvalidMetrics("métrica no numérica o negativa")
    try:
        result = Decimal(value) if decimal else int(value)
    except (InvalidOperation, ValueError) as exc:
        raise InvalidMetrics("métrica inválida") from exc
    if result > 10**15:
        raise InvalidMetrics("métrica fuera de rango")
    return result


def _sum_complete(rows, field):
    values = [row[field] for row in rows]
    return sum(values) if values and all(v is not None for v in values) else None


def _pin_report(rows, target):
    if rows is None:
        return {"estado": "no_aportado", "tableros": {}, "totales": {m: None for m in PIN_METRICS}, "motivo_totales": "sin_exportacion"}
    seen, groups, levels = set(), {}, set()
    for row in rows:
        _day(row["fecha"])
        board = _label(row["tablero"], "tablero")
        pin = _label(row["pin_id"], "pin_id")
        if row["origen"] not in ("pinterest_analytics", "consulta_manual"):
            raise InvalidMetrics("origen Pinterest no identificado")
        if row["periodo"] != "diario":
            raise InvalidMetrics("solo se admiten métricas de un día, no acumulados vitalicios")
        level = row["nivel"]
        if level not in ("pin", "tablero") or (level == "tablero") != (pin == "-"):
            raise InvalidMetrics("nivel/pin_id incompatibles")
        if level == "pin" and not re.fullmatch(r"[0-9]{1,32}", pin):
            raise InvalidMetrics("pin_id debe ser el ID numérico normalizado")
        key = (row["fecha"], level, pin if level == "pin" else board)
        if key in seen:
            raise InvalidMetrics("Pin o tablero duplicado en el mismo día")
        seen.add(key)
        numbers = {m: _amount(row[m]) for m in PIN_METRICS}
        if row["fecha"] == target:
            levels.add(level)
            groups.setdefault(board, []).append((pin, numbers))
    if len(levels) > 1:
        raise InvalidMetrics("no mezclar estadísticas de Pines con agregados de tableros")
    by_board = {}
    for board, entries in sorted(groups.items()):
        # Pinterest agrega actividad de imágenes/URL compartidas entre Pins;
        # diferentes IDs no prueban conjuntos estadísticos independientes.
        safe = len(entries) == 1
        by_board[board] = {
            **({m: entries[0][1][m] if safe else None for m in PIN_METRICS}),
            "detalle": {pin: metrics for pin, metrics in entries} if "pin" in levels else {},
            "unidad_unica_en_tablero": safe,
        }
    # Incluso los agregados de distintos tableros pueden solaparse.
    single = len(groups) == 1 and len(next(iter(groups.values()))) == 1 if groups else False
    has_metrics = any(value is not None for entries in groups.values() for _, metrics in entries for value in metrics.values())
    return {"estado": "observado" if has_metrics else "sin_metricas_fecha" if groups else "sin_filas_fecha", "tableros": by_board,
            "totales": {m: next(iter(groups.values()))[0][1][m] if single else None for m in PIN_METRICS},
            "motivo_totales": "una_unidad_observada" if single else "sin_filas_fecha" if not groups else "solapamiento_no_descartado"}


def _web_report(rows, target):
    blank = {"sesiones": None, "eventos_clave": None}
    if rows is None:
        return {"estado": "no_aportado", "campanas": {}, "totales": blank}
    seen, groups, mediums = set(), {}, {}
    for row in rows:
        _day(row["fecha"])
        camp = _label(row["campana_utm"], "campana_utm")
        medium = _label(row["medio"], "medio")
        if row["fuente"].lower() not in ("pinterest", "pinterest.com", "www.pinterest.com"):
            raise InvalidMetrics("fuente distinta de Pinterest")
        scope = row["ambito"]
        if scope == "sesion":
            if row["modelo_atribucion"] != "ultimo_clic_sesion" or row["nombre_evento"] != "-" or row["eventos_clave"] != "":
                raise InvalidMetrics("dimensiones GA4 de sesión incompatibles")
            data = {"sesiones": _amount(row["sesiones"]), "eventos_clave": None}
        elif scope == "evento":
            if row["modelo_atribucion"] not in ("ultimo_clic", "basado_en_datos") or row["sesiones"] != "":
                raise InvalidMetrics("dimensiones GA4 de evento incompatibles")
            event = _label(row["nombre_evento"], "nombre_evento")
            if not re.fullmatch(r"[^\W\d_]\w{0,39}", event, re.UNICODE):
                raise InvalidMetrics("nombre de evento GA4 inválido; no aceptar filas 'todos' o totales")
            data = {"sesiones": None, "eventos_clave": _amount(row["eventos_clave"], decimal=True)}
        else:
            raise InvalidMetrics("ámbito GA4 no reconocido")
        key = (row["fecha"], camp, scope, row["nombre_evento"])
        if key in seen:
            raise InvalidMetrics("agregado web duplicado o modelos mezclados")
        seen.add(key)
        if row["fecha"] == target:
            mediums.setdefault(camp, set()).add((row["fuente"].casefold(), medium.casefold()))
            groups.setdefault(camp, []).append((scope, data, row["modelo_atribucion"]))
    if any(len(values) > 1 for values in mediums.values()):
        raise InvalidMetrics("campaña mezclada entre fuentes/medios de GA4")
    result = {}
    for camp, items in sorted(groups.items()):
        event_models = {model for scope, _, model in items if scope == "evento"}
        if len(event_models) > 1:
            raise InvalidMetrics("campaña con modelos GA4 de evento mezclados")
        result[camp] = {
            "sesiones": _sum_complete([data for scope, data, _ in items if scope == "sesion"], "sesiones"),
            "eventos_clave": _sum_complete([data for scope, data, _ in items if scope == "evento"], "eventos_clave"),
            "modelo_eventos": next(iter(event_models), None),
            "nombres_evento": sorted({row["nombre_evento"] for row in rows if row["fecha"] == target and row["campana_utm"] == camp and row["ambito"] == "evento"}),
        }
    # No sumar campañas con modelos de atribución de evento incompatibles.
    models = {r["modelo_eventos"] for r in result.values() if r["modelo_eventos"]}
    web_totals = {"sesiones": _sum_complete(list(result.values()), "sesiones"),
                  "eventos_clave": _sum_complete(list(result.values()), "eventos_clave") if len(models) <= 1 else None}
    has_metrics = any(value is not None for campaign in result.values() for field, value in campaign.items() if field in blank)
    return {"estado": "observado" if has_metrics else "sin_metricas_fecha" if result else "sin_filas_fecha", "campanas": result,
            "totales": web_totals}


def build_report(day, *, pins=None, web=None):
    day = _day(str(day)).isoformat()
    return {"version_esquema": 2, "fecha": day, "tipo": "observacion_sin_conversion_inferida", "pinterest": _pin_report(_read(pins, PIN_FIELDS), day),
            "web_ga4": _web_report(_read(web, WEB_FIELDS), day),
            "aviso": "No sumar clics y sesiones ni calcular conversiones desde impresiones o guardados; GA4 atribuye eventos bajo su propio modelo."}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Métricas Pinterest/GA4: solo lectura, sin red")
    parser.add_argument("--day", required=True, help="YYYY-MM-DD")
    parser.add_argument("--pins", type=Path, help="CSV normalizado de Analytics Pinterest")
    parser.add_argument("--web", type=Path, help="CSV normalizado de GA4")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.day, pins=args.pins, web=args.web)
    except InvalidMetrics as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
