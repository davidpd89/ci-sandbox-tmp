"""Threads: reserva persistente de posts candidatos (05/10/2026).

El mismo principio que `bluesky_pool.py` / `mastodon_pool.py` adaptado a una red por NAVEGADOR: el scan GUARDA todo lo que ve (con scroll son ~100-200 posts por ronda) y el constructor del
plan elige entre lo acumulado: posts recientes y del nicho, en espanol, de cuentas con las que aun no hemos hecho nada, uno por cuenta. Se desacopla el descubrimiento (caro: carga
paginas) de la ejecucion. Atribucion first-touch por fuente (`pool_common`).

06/10: la logica comun a las redes por navegador (esquema, cuentas, semillas, eleccion, estadisticas) vive en `browser_pool.py` y la comparte X (`x_pool.py`). Aqui queda lo propio de
Threads: leer un post desde el texto del listado («usuario hace 3 h …») y la ruta de su base.

    python tools/threads_pool.py stats
    python tools/threads_pool.py top [--n 20]
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import browser_pool as bpool
from browser_pool import (ACCOUNT_COLS, MAX_AGE_HOURS, REMINE_DAYS, SEED_MIN_FOLLOWERS, SEED_NICHE_MIN, SPAM, add_seeds, due_seeds, estimated_age_hours,  # noqa: F401  (API publica de la reserva)
                          first_touch, fragment_key, mark, mark_account, mark_seed, pick, pick_accounts, stats)

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_THREADS")
DB_PATH = os.path.join(ROOT, "cache", "pool.sqlite3")
COLS = bpool.POST_COLS
# cabecera del post en el volcado: «<usuario> [comunidad, hasta 2 palabras] <edad>»; la edad es «5 h», «3 min», «1 d», «2 sem» o una fecha «23/09/2026»
AGE = re.compile(r"(?<![\w/])(\d{1,3})\s*(minutos?|min|m|horas?|h|d[ií]as?|d|semanas?|sem|w)\b|(\d{1,2})/(\d{1,2})/(\d{4})", re.I)   # «3 días», «2 semanas» (06/10: no se reconocian y la edad quedaba en 12 h)


def parse_age_hours(text, now=None):
    """Edad del post en horas a partir de su cabecera (primeras ~80 letras del texto visible); None si no se reconoce."""
    head = " ".join(str(text or "").split())[:90]
    match = AGE.search(head)
    if not match:
        return None
    if match.group(1):
        n, unit = int(match.group(1)), match.group(2).casefold()
        return n / 60 if unit.startswith("m") else n if unit.startswith("h") else n * 24 if unit.startswith("d") else n * 24 * 7
    try:
        when = datetime.datetime(int(match.group(5)), int(match.group(4)), int(match.group(3)))
    except ValueError:
        return None
    return max(0.0, ((now or datetime.datetime.now()) - when).total_seconds() / 3600)


def body_of(text):
    """Texto del post sin la cabecera «usuario hace 3 h» ni los contadores finales."""
    flat = " ".join(str(text or "").split())
    match = AGE.search(flat[:90])
    if match:
        flat = flat[match.end():]
    return re.sub(r"(?:\s+\d+(?:[.,]\d+)?\s*[KkMm]?)+\s*$", "", flat).strip()


def connect(path=None):
    """RRSS_THREADS_POOL_PATH aisla los tests de la reserva real."""
    db = bpool.connect(path or os.environ.get("RRSS_THREADS_POOL_PATH") or DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS thread_discovery_quarantine (
        handle TEXT PRIMARY KEY COLLATE NOCASE,
        reason TEXT NOT NULL,
        first_seen TEXT NOT NULL
    )""")
    db.commit()
    return db


def quarantine_handles(db, handles, today=None):
    """Registrar cuarentena automática sin textos, URLs ni eliminar histórico.

    No se libera automáticamente una cuenta dudosa: revisión humana antes de
    cualquier levantamiento. La tabla es local y nunca se vuelca a métricas.
    """
    today = today or datetime.date.today().isoformat()
    handles = {str(handle).lstrip("@").strip().casefold() for handle in handles if handle}
    db.executemany(
        "INSERT OR IGNORE INTO thread_discovery_quarantine(handle, reason, first_seen) VALUES (?,?,?)",
        [(handle, "suspected_campaign", today) for handle in sorted(handles)]
    )
    db.commit()
    return len(handles)


def record_posts(db, rows, today=None):
    """Filtra campañas incluso cuando un productor evita threads_scan."""
    import threads_discovery_quality as quality
    parsed = [(handle, permalink, body_of(text), source, parse_age_hours(text), None)
              for handle, permalink, text, source in rows]
    suspect = quality.blocked_handles(parsed)
    if suspect:
        quarantine_handles(db, suspect, today=today)
    blocked = quality.quarantined_pool_handles(db)
    safe = [row for row in parsed
            if str(row[0]).lstrip("@").casefold() not in blocked]
    return bpool.record_post_rows(db, safe, today)


def record_accounts(db, rows, today=None):
    """Filtra engaños también en la primera escritura de perfiles/semillas.

    No modifica registros existentes ni exporta identidades sospechosas.
    """
    import threads_discovery_quality as dq
    rows = list(rows)
    suspect = dq.blocked_handles([
        {"handle": handle, "text": f"{name or ''} {bio or ''}"}
        for handle, name, bio, _source, _seed in rows
    ])
    denied = suspect | dq.quarantined_pool_handles(db)
    safe = [row for row in rows
            if str(row[0]).lstrip("@").casefold() not in denied]
    if suspect:
        quarantine_handles(db, suspect, today=today)
    return bpool.record_accounts(db, safe, "davidportodiaz", today)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    db = connect()
    try:
        if argv and argv[0] == "top":
            n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 20
            for row in pick(db, n):
                print(f"{row['score']:>5} @{row['handle']:<28} {row['source']:<28} {row['text'][:90]!r}")
        else:
            print(json.dumps(stats(db), ensure_ascii=False))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
