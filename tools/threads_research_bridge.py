"""Importador offline de exportaciones JSON/JSONL de th a la reserva Threads.

Origen del esquema: Egor01KKK/threads-content-research-agent, Apache-2.0,
commit 981cccd2eb53d44f46cc5675b2388c8c7a6ad758 (2026-09-13),
docs/OUTPUT-SCHEMA.md. No se copia su recolector Go ni se accede a Threads.
El núcleo de validación/dedupe es común; solo Threads tiene adaptador probado.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

NETWORKS = frozenset({"bluesky", "mastodon", "x", "threads", "facebook",
                      "pinterest", "reddit", "tiktok", "instagram"})
MAX_BYTES = 5_000_000
MAX_ROWS = 2_000
_USERNAME = re.compile(r"[A-Za-z0-9_.]{1,30}\Z")
_POST = re.compile(r"/(@[A-Za-z0-9_.]+)/post/([A-Za-z0-9_-]+)\Z")


def read_export(path):
    """Lee JSON array, export corpus, o JSONL; nunca ejecuta contenido."""
    p = Path(path)
    if not p.is_file() or p.stat().st_size > MAX_BYTES:
        raise ValueError("exportación ausente o superior a 5 MB")
    raw = p.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if isinstance(data, dict):
        data = data.get("corpus", data.get("data"))
    if not isinstance(data, list) or len(data) > MAX_ROWS:
        raise ValueError("formato no compatible o más de 2000 filas")
    return data


def _timestamp(value, now):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("sin_fecha")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("fecha_invalida") from exc
    if parsed.tzinfo is None:
        raise ValueError("fecha_sin_zona")
    age = (now - parsed.astimezone(timezone.utc)).total_seconds() / 3600
    if age < -0.1 or age > 24 * 365:
        raise ValueError("fecha_fuera_rango")
    return max(0.0, age)


def _threads_row(item, now):
    if not isinstance(item, dict):
        raise ValueError("fila_invalida")
    row = item.get("post", item)
    if not isinstance(row, dict):
        raise ValueError("post_invalido")
    handle = row.get("author_username") or row.get("username")
    url = row.get("url") or row.get("permalink")
    body = row.get("text")
    if not isinstance(handle, str) or not _USERNAME.fullmatch(handle.lstrip("@")):
        raise ValueError("autor_invalido")
    if not isinstance(url, str):
        raise ValueError("url_invalida")
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in
            ("threads.com", "www.threads.com", "threads.net", "www.threads.net")
            or parts.username or parts.password or parts.port):
        raise ValueError("url_invalida")
    match = _POST.fullmatch(parts.path.rstrip("/"))
    if not match or match.group(1)[1:].casefold() != handle.lstrip("@").casefold():
        raise ValueError("identidad_no_coincide")
    if not isinstance(body, str) or not body.strip() or len(body) > 20_000:
        raise ValueError("texto_invalido")
    age = _timestamp(row.get("timestamp") or row.get("published_at"), now)
    canonical_url = f"https://www.threads.com/{match.group(1)}/post/{match.group(2)}"
    return (handle.lstrip("@"), canonical_url, " ".join(body.split()),
            "search:th_export", age, None)


ADAPTERS = {"threads": _threads_row}


def normalize(network, records, *, now=None):
    """Descartar ID contradictorio sin elegir ganador; no inferir antigüedad."""
    if network not in NETWORKS:
        raise ValueError("red desconocida")
    if network not in ADAPTERS:
        raise NotImplementedError(f"sin adaptador de exportación probado para {network}")
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("now debe incluir zona horaria")
    if not isinstance(records, list) or len(records) > MAX_ROWS:
        raise ValueError("filas inválidas")
    grouped, duplicates, errors = {}, Counter(), Counter()
    for item in records:
        try:
            parsed = ADAPTERS[network](item, now)
        except (ValueError, TypeError) as exc:
            errors[str(exc)] += 1
            continue
        key = parsed[1]
        if key not in grouped:
            grouped[key] = parsed
        elif grouped[key] is None:
            continue  # Un tercer registro no rehabilita un conflicto.
        elif grouped[key][:4] != parsed[:4]:
            grouped[key] = None
        else:
            duplicates[key] += 1
            old = grouped[key]
            grouped[key] = (*old[:4], max(old[4], parsed[4]), None)
    output = [row for row in grouped.values() if row is not None]
    valid_duplicates = sum(duplicates[key] for key, row in grouped.items() if row is not None)
    errors["conflicto_duplicado"] += sum(row is None for row in grouped.values())
    return output, {"recibidos": len(records), "validos_unicos": len(output),
                    "descartados": dict(sorted(errors.items())),
                    "duplicados_identicos": valid_duplicates}


def ingest_rows(rows, *, db_path):
    """Escritura SOLO en SQLite local indicada; cero operaciones de red."""
    if not db_path:
        raise ValueError("--db obligatorio para importación local")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import browser_pool
    db = browser_pool.connect(str(db_path))
    try:
        return browser_pool.record_post_rows(db, rows)
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON/JSONL de th, ya exportado")
    parser.add_argument("--network", choices=sorted(ADAPTERS), default="threads")
    parser.add_argument("--write-pool", action="store_true", help="persistir localmente en SQLite")
    parser.add_argument("--db", help="ruta SQLite explícita, sin pool real por defecto")
    args = parser.parse_args(argv)
    if args.db and not args.write_pool:
        parser.error("--db requiere --write-pool")
    if args.write_pool and not args.db:
        parser.error("--write-pool requiere --db")
    rows, report = normalize(args.network, read_export(args.input))
    report["network"] = args.network
    report["mode"] = "write_local_pool" if args.write_pool else "dry_run"
    if args.write_pool:
        report["insertados"] = ingest_rows(rows, db_path=args.db)
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
