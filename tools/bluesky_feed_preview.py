"""Vista previa SOLO LECTURA del futuro feed literario de Bluesky.

Lee la tabla posts de bluesky_jetstream_collect.py; no publica feeds,
no abre conexiones, no autentica y no ejecuta acciones en redes.

Algoritmo de paginación adaptado de:
https://github.com/MarshalX/bluesky-feed-generator/blob/be500ba5be2c2006f0649c8ce8862943ac7966c3/server/algos/feed.py
MIT; upstream ordena indexed_at + cid y devuelve {'post': uri}.
Aquí se usa time_us + uri (esquema SQLite real del proyecto).
"""

from __future__ import annotations

import argparse
from contextlib import closing
import datetime as dt
import json
import os
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "SISTEMA_DIARIO_BLUESKY" / "cache" / "jetstream.sqlite3"
CURSOR_EOF = "eof"
_POST_URI = re.compile(r"^at://did:[a-z0-9]+:[a-zA-Z0-9._:%-]+/app\.bsky\.feed\.post/[a-zA-Z0-9._~-]+$")


def _cursor_key(cursor: str | None) -> tuple[int, str] | None:
    """Cursor opaco estable: timestamp microsegundos + URI (nunca offset)."""
    if cursor is None:
        return None
    if cursor == CURSOR_EOF:
        return (0, "")
    if not isinstance(cursor, str) or "::" not in cursor:
        raise ValueError("Cursor mal formado")
    stamp, uri = cursor.split("::", 1)
    if not stamp.isascii() or not stamp.isdecimal() or int(stamp) <= 0 or not _POST_URI.fullmatch(uri):
        raise ValueError("Cursor mal formado")
    return int(stamp), uri


def feed_page(
    db_path: str | os.PathLike[str] = DEFAULT_DB,
    *,
    cursor: str | None = None,
    limit: int = 30,
    max_age_hours: int = 48,
    min_matches: int = 1,
    now_us: int | None = None,
) -> dict:
    """Página compatible con getFeedSkeleton, construida con datos locales.

    El colector ya controla idioma, términos, política y borrados de eventos
    observados. Se excluyen replies, importaciones antiguas y fechas futuras.
    Esta vista no verifica si el post continúa visible en el AppView.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit debe estar entre 1 y 100")
    if isinstance(max_age_hours, bool) or not isinstance(max_age_hours, int) or not 1 <= max_age_hours <= 168:
        raise ValueError("max_age_hours debe estar entre 1 y 168")
    if isinstance(min_matches, bool) or not isinstance(min_matches, int) or min_matches < 1:
        raise ValueError("min_matches debe ser positivo")
    key = _cursor_key(cursor)
    if key == (0, ""):
        return {"cursor": CURSOR_EOF, "feed": []}
    if now_us is None:
        now_us = time.time_ns() // 1000
    if isinstance(now_us, bool) or not isinstance(now_us, int) or now_us <= 0:
        raise ValueError("now_us inválido")

    db_file = Path(db_path).resolve()
    if not db_file.is_file():
        raise FileNotFoundError(f"No existe caché Jetstream: {db_file}")
    floor = now_us - max_age_hours * 3_600_000_000
    # Fecha del registro Y momento del evento. Descarta imports de posts viejos.
    floor_iso = dt.datetime.fromtimestamp(floor / 1_000_000, dt.timezone.utc).isoformat()
    future_iso = dt.datetime.fromtimestamp((now_us + 300_000_000) / 1_000_000, dt.timezone.utc).isoformat()
    # Filtrar URI tras LIMIT puede crear un falso EOF si un lote contiene
    # registros corruptos. Avanzar por todas las filas leídas, pero emitir el
    # cursor de la última URI VÁLIDA entregada para no saltar candidatos.
    clean: list[tuple[str, int]] = []
    scan_key = key
    batch_size = max(100, limit * 2)
    # mode=ro evita crear/modificar archivos (también en Windows).
    with closing(sqlite3.connect(db_file.as_uri() + "?mode=ro", uri=True, timeout=5)) as connection:
        while len(clean) < limit:
            params: list[object] = [
                floor, now_us + 300_000_000, floor_iso, future_iso, min_matches,
            ]
            cursor_clause = ""
            if scan_key is not None:
                cursor_clause = "AND (time_us < ? OR (time_us = ? AND uri < ?))"
                params.extend((scan_key[0], scan_key[0], scan_key[1]))
            params.append(batch_size)
            rows = connection.execute(
                f"""
                SELECT uri, time_us FROM posts
                WHERE time_us BETWEEN ? AND ?
                  AND julianday(created_at) BETWEEN julianday(?) AND julianday(?)
                  AND match_count >= ?
                  AND reply_parent IS NULL
                  -- El colector guarda una lista JSON; un escalar u objeto
                  -- corrupto no puede convertirse en etiqueta de idioma.
                  AND json_type(CASE WHEN json_valid(posts.langs_json)
                      THEN posts.langs_json ELSE 'null' END) = 'array'
                  AND (langs_json = '[]' OR EXISTS (
                        SELECT 1 FROM json_each(CASE WHEN json_valid(posts.langs_json)
                            THEN posts.langs_json ELSE 'null' END)
                        WHERE lower(value) = 'es' OR lower(value) LIKE 'es-%'
                  ))
                  AND uri LIKE 'at://did:%/app.bsky.feed.post/%'
                  {cursor_clause}
                ORDER BY time_us DESC, uri DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            if not rows:
                break
            for uri, stamp in rows:
                if isinstance(uri, str) and _POST_URI.fullmatch(uri):
                    clean.append((uri, stamp))
                    if len(clean) == limit:
                        break
            if len(clean) == limit or len(rows) < batch_size:
                break
            scan_key = (rows[-1][1], rows[-1][0])

    feed = [{"post": uri} for uri, _ in clean]
    next_cursor = f"{clean[-1][1]}::{clean[-1][0]}" if clean else CURSOR_EOF
    return {"cursor": next_cursor, "feed": feed}


def export_skeleton(page: dict, path: Path) -> None:
    """Exporta JSON de QA local; NO publica ni registra feeds remotos."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(page, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Previsualizar feed literario sin publicar")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--cursor")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--max-age-hours", type=int, default=48)
    parser.add_argument("--min-matches", type=int, default=1)
    parser.add_argument("--export-json", type=Path, help="Archivo local de QA; no publica el feed")
    args = parser.parse_args(argv)
    result = feed_page(
        args.db, cursor=args.cursor, limit=args.limit,
        max_age_hours=args.max_age_hours, min_matches=args.min_matches,
    )
    if args.export_json is not None:
        export_skeleton(result, args.export_json)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
