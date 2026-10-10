"""Distribucion offline de antiguedad del post destino, por red.

Complementa el gate de tools/post_age_policy.py (#8/privado); nunca autoriza
acciones. Solo se aceptan campos de publicacion con procedencia explicita.
No se leen cuentas, navegadores ni APIs; no se imprimen posts, URLs ni IDs.
Python 3.11, biblioteca estandar (Windows/Linux).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path

NETWORKS = (
    "x", "threads", "facebook", "pinterest", "reddit",
    "bluesky", "mastodon", "tiktok", "instagram",
)
BUCKETS = ("0_24h", "24_72h", "72_168h", "over_168h", "unknown", "future", "conflict")
ORIGIN_FIELDS = ("target_created_at", "post_created_at")
NESTED_FIELDS = (
    "created_at", "createdAt", "created_utc", "create_time",
    "created_time", "published_at", "timestamp",
)
# Campos de API sin ambiguedad como dato del post, aun en la raiz.
API_FIELDS = {
    "reddit": ("created_utc",),
    "tiktok": ("create_time",),
}
PLAN_SNAPSHOTS = {
    "x": "SISTEMA_DIARIO_X/x_plan.json",
    "threads": "SISTEMA_DIARIO_THREADS/threads_plan.json",
    "facebook": "SISTEMA_DIARIO_FACEBOOK/facebook_plan.json",
    "pinterest": "SISTEMA_DIARIO_PINTEREST/pinterest_plan.json",
    "reddit": None,  # No se ha verificado ruta unica para este orquestador.
    "bluesky": "bluesky_mech_plan.json",
    "mastodon": "mastodon_mech_plan.json",
    "tiktok": "tiktok_plan.json",
    "instagram": "SISTEMA_DIARIO_INSTAGRAM/instagram_plan.json",
}


def _parse(value):
    """UTC consciente; rechaza horas locales sin offset y epoch ambiguo."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.astimezone(dt.timezone.utc) if value.tzinfo and value.utcoffset() is not None else None
    if isinstance(value, str):
        value = value.strip()
        if re.fullmatch(r"[0-9]{10}(?:[0-9]{3})?", value):
            value = int(value)
        else:
            try:
                parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
                return _parse(parsed)
            except (ValueError, TypeError, OverflowError):
                return None
    if isinstance(value, (int, float)) and 1_000_000_000 < value < 10**16:
        try:
            return dt.datetime.fromtimestamp(
                value / (1000 if value >= 10**11 else 1), dt.timezone.utc
            )
        except (ValueError, OverflowError, OSError):
            return None
    return None


def _dates(network, row):
    """Lista de fechas *de origen*; no confundir con encolado/indexacion.

    Si dos metadatos de origen discrepan, la muestra es conflictiva:
    nunca escoger el mas reciente para mejorar artificialmente el embudo.
    """
    sources = []
    for field in ORIGIN_FIELDS + API_FIELDS.get(network, ()):
        when = _parse(row.get(field))
        if when is not None:
            sources.append((field, when))
    # Un escaner puede declarar expresamente que la raiz ES un post, no una tarea.
    if row.get("source_kind") == "post":
        for field in NESTED_FIELDS:
            when = _parse(row.get(field))
            if when is not None:
                sources.append(("post." + field, when))
    post = row.get("post")
    for prefix, record in (
        ("post", post),
        ("record", row.get("record")),
        ("post.record", post.get("record") if isinstance(post, dict) else None),
        ("status", row.get("status")),
        ("media", row.get("media")),
    ):
        if isinstance(record, dict):
            for field in NESTED_FIELDS:
                when = _parse(record.get(field))
                if when is not None:
                    sources.append((prefix + "." + field, when))
    return sources


def classify(network, row, *, now):
    """Devuelve (rango, origen) sin exponer datos individuales."""
    if network not in NETWORKS:
        raise ValueError("red no soportada")
    if not isinstance(row, dict):
        return "unknown", "none"
    now = _parse(now)
    if now is None:
        raise ValueError("now requiere un datetime con zona horaria")
    dates = _dates(network, row)
    if not dates:
        return "unknown", "none"
    if max(v for _, v in dates) - min(v for _, v in dates) > dt.timedelta(seconds=1):
        return "conflict", "multiple"
    source, when = dates[0]
    age = (now - when).total_seconds()
    if age < -300:
        return "future", source
    if age <= 24 * 3600:
        return "0_24h", source
    if age <= 72 * 3600:
        return "24_72h", source
    if age <= 168 * 3600:
        return "72_168h", source
    return "over_168h", source


def distribution(network, candidates, *, now):
    """Ventanas inclusivas acumuladas; desconocidos nunca suman como frescos."""
    if network not in NETWORKS:
        raise ValueError("red no soportada")
    if not isinstance(candidates, list):
        raise ValueError("se requiere lista de candidatos")
    counts = dict.fromkeys(BUCKETS, 0)
    sources = {}
    for row in candidates:
        bucket, source = classify(network, row, now=now)
        counts[bucket] += 1
        if bucket not in ("unknown", "conflict"):
            sources[source] = sources.get(source, 0) + 1
    return {
        "red": network,
        "total": len(candidates),
        "hasta_24h": counts["0_24h"],
        "hasta_72h": counts["0_24h"] + counts["24_72h"],
        "hasta_7d": counts["0_24h"] + counts["24_72h"] + counts["72_168h"],
        "rangos": counts,
        "origenes": dict(sorted(sources.items())),
    }


def report_samples(samples, *, now):
    """Matriz de nueve redes; ausente != cero, sin mezclar plataformas."""
    if not isinstance(samples, dict) or any(key not in NETWORKS for key in samples):
        raise ValueError("se requieren claves de redes conocidas")
    return {
        network: (
            {"estado": "sin_muestra"} if network not in samples
            else {"estado": "ok", **distribution(network, samples[network], now=now)}
        )
        for network in NETWORKS
    }


def _load_plan(path):
    if path.stat().st_size > 4_000_000:
        raise ValueError("fichero demasiado grande")
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, list):
        raise ValueError("el plan debe ser una lista")
    return payload


def audit_recent_plans(root, *, now=None, max_age_hours=36):
    """Instantanea agregada y read-only de las nueve rutas verificadas."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if _parse(now) is None or not 0 < max_age_hours <= 24 * 30:
        raise ValueError("reloj o ventana invalidos")
    root = Path(root)
    out = {}
    for network, relpath in PLAN_SNAPSHOTS.items():
        if relpath is None:
            out[network] = {"estado": "sin_ruta_verificada"}
            continue
        path = root / relpath
        try:
            hours = (now.timestamp() - path.stat().st_mtime) / 3600
            if not -1 <= hours <= max_age_hours:
                out[network] = {"estado": "plan_no_reciente"}
                continue
            out[network] = {
                "estado": "ok",
                **distribution(network, _load_plan(path), now=now),
            }
        except FileNotFoundError:
            out[network] = {"estado": "sin_plan"}
        except (OSError, ValueError, UnicodeError, OverflowError, TypeError):
            out[network] = {"estado": "plan_invalido"}
    return out


def daily_lines(root, *, now=None):
    """Seccion para el informe diario; solo numeros, ninguna URL o texto."""
    summary = audit_recent_plans(root, now=now)
    lines = ["## Antigüedad de publicaciones destino (24 h / 72 h / 7 días)", ""]
    for network in NETWORKS:
        row = summary[network]
        if row["estado"] != "ok":
            lines.append(f"- {network}: {row['estado']} (sin medición)")
        else:
            c = row["rangos"]
            lines.append(
                f"- {network}: {row['total']} candidatos; "
                f"≤24 h {row['hasta_24h']}, ≤72 h {row['hasta_72h']}, "
                f"≤7 d {row['hasta_7d']}; >7 d {c['over_168h']}, "
                f"sin fecha {c['unknown']}, futuras {c['future']}, "
                f"contradictorias {c['conflict']}"
            )
    return lines + [""]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auditoría offline; sin acciones sociales")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", help="JSON de red -> lista de candidatos (solo lectura)")
    group.add_argument("--root", help="directorio de planes recientes (solo lectura)")
    args = parser.parse_args(argv)
    try:
        if args.sample:
            path = Path(args.sample)
            if path.stat().st_size > 4_000_000:
                raise ValueError("sample excesivo")
            with path.open(encoding="utf-8") as stream:
                samples = json.load(stream)
            summary = report_samples(samples, now=dt.datetime.now(dt.timezone.utc))
        else:
            summary = audit_recent_plans(args.root)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, UnicodeError, OverflowError):
        # No revelar rutas ni contenido de planes privados en errores de consola.
        print(json.dumps({"estado": "entrada_invalida"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
