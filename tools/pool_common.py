"""Piezas comunes de las reservas persistentes de candidatos (Bluesky y Mastodon; 05/10/2026).

`bluesky_pool.py` y `mastodon_pool.py` guardan en SQLite cuentas candidatas minadas de las semillas del nicho. Tienen esquemas de cuenta distintos (DID/handle frente a
acct/id), pero comparten esto, que se escribia dos veces:

  * conexion (carpeta, espera de 30 s, WAL si se puede: dos procesos comparten el fichero);
  * atribucion first-touch: tabla `touch` (primera fuente por la que el scan vio cada handle; `INSERT OR IGNORE`, inmutable);
  * cursores de timelines por superficie/clave (`newest_id` solo avanza, `oldest_id` solo retrocede).

Los clasificadores de texto (nicho, espanol, ingles, portugues, catalan, spam) viven en `bluesky_pool.py` y `mastodon_pool.py` los importa.
"""
import datetime
import os
import sqlite3


def connect_sqlite(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    try:
        db.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass      # otro proceso tiene el fichero abierto en modo diario: se sigue sin cambiar el modo
    return db


def ensure_touch_table(db):
    db.execute("CREATE TABLE IF NOT EXISTS touch (handle TEXT PRIMARY KEY, source TEXT NOT NULL, at TEXT NOT NULL)")


def ensure_cursors_table(db):
    db.execute("CREATE TABLE IF NOT EXISTS cursors (surface TEXT NOT NULL, key TEXT NOT NULL, newest_id TEXT, oldest_id TEXT, last_scan_at TEXT, PRIMARY KEY (surface, key))")


def first_touch(db, handles):
    """{handle: fuente} de la primera vez que el scan vio cada handle (atribucion first-touch, inmutable)."""
    handles = list(dict.fromkeys(str(h).casefold() for h in handles if h))
    out = {}
    for start in range(0, len(handles), 400):
        chunk = handles[start:start + 400]
        marks = ",".join("?" for _ in chunk)
        out.update({row[0]: row[1] for row in db.execute(f"SELECT handle, source FROM touch WHERE handle IN ({marks})", chunk)})
    return out


def record_touch(db, sources, today=None):
    """Guarda la primera fuente de cada handle. `INSERT OR IGNORE`: lo ya registrado no se pisa nunca."""
    today = today or datetime.date.today().isoformat()
    db.executemany("INSERT OR IGNORE INTO touch(handle, source, at) VALUES(?,?,?)", [(str(h).casefold(), s, today) for h, s in sources.items() if h and s])
    db.commit()


def get_cursor(db, surface, key):
    """(newest_id, oldest_id) ya leidos de un timeline; (None, None) si nunca se leyo."""
    row = db.execute("SELECT newest_id, oldest_id FROM cursors WHERE surface = ? AND key = ?", (surface, str(key).casefold())).fetchone()
    return (row[0], row[1]) if row else (None, None)


def set_cursor(db, surface, key, newest_id, oldest_id, today=None):
    """Guarda los cursores; `newest` solo avanza y `oldest` solo retrocede (nunca se pierde lo ya recorrido)."""
    old_newest, old_oldest = get_cursor(db, surface, key)
    newest = max([x for x in (old_newest, newest_id) if x], key=int, default=None)
    oldest = min([x for x in (old_oldest, oldest_id) if x], key=int, default=None)
    db.execute("INSERT INTO cursors(surface, key, newest_id, oldest_id, last_scan_at) VALUES(?,?,?,?,?) ON CONFLICT(surface, key) DO UPDATE SET "
               "newest_id=excluded.newest_id, oldest_id=excluded.oldest_id, last_scan_at=excluded.last_scan_at",
               (surface, str(key).casefold(), newest, oldest, today or datetime.date.today().isoformat()))
    db.commit()
