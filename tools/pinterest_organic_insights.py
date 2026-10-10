"""Informe de métricas orgánicas de Pines propios (offline por defecto).

Adapta el esquema `pin_metrics.{90d,lifetime_metrics}` de Pinterest API v5.
NO confunde clickthrough con visitas confirmadas a la web, ni tasas con
incrementos causales de seguidores. No lee ni modifica cuentas salvo --api-read
explícito, que delega en la auditoría de lectura existente y verifica identidad.
Referencias: pinterest/api-quickstart@592b4bac (Apache-2.0) y
pinterest/api-description@51aca009 (MIT, esquema OpenAPI v5).
"""
from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping

WINDOWS = ("90d", "lifetime_metrics")
FIELDS = ("impression", "pin_click", "clickthrough", "save")
MAX_PINS = 10000


def _count(source, name):
    val = source.get(name)
    return val if type(val) is int and val >= 0 else None


def summarize(pins, *, window="90d", min_impressions=100):
    """Comparación descriptiva de Pins propios; sin decidir interacciones ajenas.

    Un dato ausente permanece None. Nunca sustituir lifetime por 90d:
    son cohortes de tiempo no comparables. IDs duplicados fallan cerrado.
    """
    if window not in WINDOWS:
        raise ValueError("ventana de métricas desconocida")
    if type(min_impressions) is not int or not 1 <= min_impressions <= 1000000:
        raise ValueError("min_impressions inválido")
    if not isinstance(pins, (list, tuple)) or len(pins) > MAX_PINS:
        raise ValueError("esperada lista acotada de Pines")
    seen, rows = set(), []
    for pin in pins:
        if not isinstance(pin, Mapping):
            raise ValueError("Pin no estructurado")
        native_id = pin.get("id")
        if (type(native_id) not in (str, int) or
                not str(native_id).strip() or isinstance(native_id, str) and len(native_id) > 128):
            raise ValueError("Pin sin ID estable")
        native_id = str(native_id).strip()
        if native_id in seen:
            raise ValueError("Pin duplicado")
        seen.add(native_id)
        metrics = pin.get("pin_metrics")
        block = metrics.get(window) if isinstance(metrics, Mapping) else None
        if not isinstance(block, Mapping):
            block = {}
        counts = {field: _count(block, field) for field in FIELDS}
        imp = counts["impression"]
        sufficient = imp is not None and imp >= min_impressions
        # El campo clickthrough se conserva como tal; API no certifica venta.
        ratio = ((counts["clickthrough"] / imp) if sufficient and
                 counts["clickthrough"] is not None and imp > 0 else None)
        rows.append({
            "network": "pinterest", "source": "api_v5_owned_pin_metrics",
            "pin_id": native_id,
            "title": str(pin.get("title") or "")[:100],
            "window": window,
            "metrics": counts,
            "clickthrough_per_impression": round(ratio, 6) if ratio is not None else None,
            "comparable": ratio is not None,
        })
    comparable = sorted(
        (row for row in rows if row["comparable"]),
        key=lambda r: (-r["clickthrough_per_impression"],
                       -r["metrics"]["impression"], r["pin_id"]),
    )
    return {
        "network": "pinterest", "source": "api_v5_owned_pin_metrics",
        "window": window, "min_impressions": min_impressions,
        "total_pins": len(rows), "comparable_pins": len(comparable),
        "ranked": comparable, "unranked": [r for r in rows if not r["comparable"]],
        "interpretation": "descriptivo; clickthrough no acredita ventas ni seguidores",
    }


def _from_json(path):
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    if isinstance(data, dict):
        if data.get("bookmark") not in (None, ""):
            raise ValueError("paginación incompleta: bookmark presente")
        data = data.get("items")
    if not isinstance(data, list):
        raise ValueError("el JSON debe contener items completos o una lista")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="dos pines sintéticos, sin red")
    source.add_argument("--input", help="JSON exportado de GET /v5/pins?pin_metrics=true")
    source.add_argument("--api-read", action="store_true",
                        help="lectura API opcional con token del entorno y verificación de identidad")
    parser.add_argument("--window", choices=WINDOWS, default="90d")
    parser.add_argument("--min-impressions", type=int, default=100)
    args = parser.parse_args(argv)
    if args.demo:
        pins = [
            {"id": "101", "title": "Fantasía juvenil", "pin_metrics": {"90d": {
                "impression": 1000, "pin_click": 30, "clickthrough": 12}}},
            {"id": "102", "title": "Mapas de fantasía", "pin_metrics": {"90d": {
                "impression": 20, "pin_click": 3, "clickthrough": 2}}},
        ]
    elif args.input:
        pins = _from_json(args.input)
    else:
        import pinterest_api_audit as audit
        # Lectura explícita, verificación de cuenta y paginación completa.
        pins = list(audit.list_pins(os.environ.get("PINTEREST_ACCESS_TOKEN"),
                                   include_metrics=True))
    print(json.dumps(summarize(pins, window=args.window,
                               min_impressions=args.min_impressions),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
