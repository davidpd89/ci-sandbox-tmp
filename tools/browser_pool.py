"""Reserva persistente de candidatos de las redes por NAVEGADOR (Threads y X; 06/10/2026).

`threads_pool.py` era la unica reserva: guarda en SQLite todo lo que el scan ve (posts con scroll, cuentas de la pestana de personas y de las listas de seguidores de las semillas) y el
constructor del plan elige entre lo acumulado. X necesita exactamente lo mismo, asi que la logica comun vive aqui y cada red solo aporta lo suyo:

  * como se lee un post (Threads: texto con cabecera «usuario hace 3 h»; X: cuerpo, idioma y fecha ya estructurados) -> `record_post_rows` recibe filas ya normalizadas;
  * la ruta de la base (`SISTEMA_DIARIO_<RED>/cache/pool.sqlite3`) y la variable que la aisla en los tests.

Politica de idioma (David 06/10: «nos orientamos al espanol»): una cuenta o post cuyo texto esta en otro idioma (ingles, aleman, frances, italiano, neerlandes, portugues) se guarda con
`spanish = 0` y nunca se ofrece. Atribucion first-touch por fuente (`pool_common`).
"""
from __future__ import annotations

import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pool_common as pc
import scan_common as sc
import reciprocity as rb_recip      # cuentas reciprocas (follow-back), comun a todas las redes
import text_common as tc

MAX_AGE_HOURS = 72
SPAM = re.compile(r"drive\.google|pdf (?:gratis|drive)|libros? pdf|descarga(?:r)? gratis|t\.me/|wa\.me/|sorteo|giveaway|onlyfans", re.I)
SPANISH_LANGS = {"es", "gl"}
POST_COLS = ("permalink", "handle", "text", "source", "first_seen", "age_hours", "niche", "spanish", "status", "seen_count")
ACCOUNT_COLS = ("handle", "display", "bio", "source", "seed", "first_seen", "niche", "spanish", "status", "seen_count")
SEED_NICHE_MIN = 2           # una cuenta cuya biografia suma >=2 terminos del nicho se vuelve semilla (se minan sus seguidores)
SEED_MIN_FOLLOWERS = 150     # con menos seguidores la lista casi no aporta
REMINE_DAYS = 6


def connect(path):
    db = pc.connect_sqlite(path)
    db.execute(
        """CREATE TABLE IF NOT EXISTS posts (
            permalink TEXT PRIMARY KEY, handle TEXT NOT NULL, text TEXT NOT NULL, source TEXT NOT NULL, first_seen TEXT NOT NULL, age_hours REAL,
            niche INTEGER NOT NULL DEFAULT 0, spanish INTEGER, status TEXT NOT NULL DEFAULT 'new', acted_at TEXT, seen_count INTEGER NOT NULL DEFAULT 1
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_posts_pick ON posts(status, first_seen)")
    db.execute(
        """CREATE TABLE IF NOT EXISTS accounts (
            handle TEXT PRIMARY KEY, display TEXT, bio TEXT, source TEXT NOT NULL, seed TEXT, first_seen TEXT NOT NULL, niche INTEGER NOT NULL DEFAULT 0,
            spanish INTEGER, status TEXT NOT NULL DEFAULT 'new', acted_at TEXT, seen_count INTEGER NOT NULL DEFAULT 1
        )"""
    )
    db.execute("CREATE TABLE IF NOT EXISTS seeds (handle TEXT PRIMARY KEY, source TEXT, followers INTEGER, last_mined TEXT, mined_count INTEGER NOT NULL DEFAULT 0)")
    pc.ensure_touch_table(db)
    db.commit()
    return db


def spanish_flag(text, lang=None):
    """1 = en espanol, 0 = en otro idioma, None = no se sabe. `lang`: el idioma que asigna la propia red al post (X: `es`, `en`, `und`…), mas fiable que el texto."""
    lang = (lang or "").casefold()
    if lang in SPANISH_LANGS:
        return 1
    if lang and lang != "und" and lang not in ("ca", "eu", "qme", "qht", "zxx"):
        return 0
    if tc.looks_spanish(text):
        return 1
    return 0 if tc.foreign_language(text) else None


def record_post_rows(db, rows, today=None):
    """rows: [(handle, permalink, cuerpo, fuente, edad_en_horas|None, idioma|None)]. Guarda lo nuevo, cuenta repeticiones y apunta la fuente first-touch de cada cuenta.
    Devuelve cuantos posts eran nuevos."""
    today = today or datetime.date.today().isoformat()
    new, touches = 0, {}
    for handle, permalink, body, source, age, lang in rows:
        handle = str(handle or "").lstrip("@")
        if not handle or not permalink:
            continue
        permalink = permalink.rstrip("/")
        body = " ".join(str(body or "").split())
        if not body or sc.is_political(body) or SPAM.search(body):
            continue
        if db.execute("SELECT 1 FROM posts WHERE permalink = ?", (permalink,)).fetchone():
            db.execute("UPDATE posts SET seen_count = seen_count + 1 WHERE permalink = ?", (permalink,))
            continue
        db.execute("INSERT INTO posts(permalink, handle, text, source, first_seen, age_hours, niche, spanish) VALUES(?,?,?,?,?,?,?,?)",
                   (permalink, handle, body[:400], source, today, age, tc.niche_hits(body), spanish_flag(body, lang)))
        touches.setdefault(handle.casefold(), source)
        new += 1
    if touches:
        pc.record_touch(db, touches, today)
    db.commit()
    return new


def estimated_age_hours(row, now=None):
    """Edad ahora = edad cuando se vio + tiempo desde que se vio (si se desconoce la inicial se supone 12 h)."""
    now = now or datetime.datetime.now()
    seen = datetime.datetime.fromisoformat(row["first_seen"])
    since = max(0.0, (now - seen).total_seconds() / 3600)
    return (row["age_hours"] if row["age_hours"] is not None else 12.0) + since


def fragment_key(handle, text, size=30):
    """Clave (cuenta, primeras letras del cuerpo) para reconocer un post ya tratado aunque el registro solo guarde el fragmento de texto (no el permalink)."""
    return (str(handle).lstrip("@").casefold(), " ".join(str(text or "").split()).casefold()[:size])


def pick(db, n, *, exclude_handles=frozenset(), exclude_fragments=frozenset(), now=None, max_age_hours=MAX_AGE_HOURS):
    """Los mejores posts aun sin accion: del nicho, no en otro idioma, recientes, uno por cuenta, de cuentas que no estan en `exclude_handles` y cuyo cuerpo no coincide
    con un fragmento ya registrado."""
    now = now or datetime.datetime.now()
    rows = [dict(zip(POST_COLS, r)) for r in db.execute("SELECT " + ",".join(POST_COLS) + " FROM posts WHERE status = 'new' AND niche >= 1")]
    scored = []
    for row in rows:
        if row["spanish"] == 0 or row["handle"].casefold() in exclude_handles or fragment_key(row["handle"], row["text"]) in exclude_fragments:
            continue
        age = estimated_age_hours(row, now)
        if age > max_age_hours:
            continue
        score = 3 * min(row["niche"], 3) + (2 if row["spanish"] == 1 else 0) + (2 if sc.invites_conversation(row["text"]) else 0) + max(0.0, 3 - age / 24) + min(row["seen_count"], 3) * 0.3
        scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["permalink"]))
    out, used = [], set()
    for score, row in scored:
        key = row["handle"].casefold()
        if key in used:
            continue
        used.add(key)
        row["score"] = round(score, 2)
        out.append(row)
        if len(out) >= n:
            break
    return out


def mark(db, permalink, status, today=None):
    db.execute("UPDATE posts SET status = ?, acted_at = ? WHERE permalink = ?", (status, today or datetime.date.today().isoformat(), permalink.rstrip("/")))
    db.commit()


def record_accounts(db, rows, my_handle, today=None):
    """rows: [(handle, nombre, bio, fuente, semilla)]. Guarda cuentas nuevas (sin politica/activismo/spam), cuenta repeticiones, apunta la fuente first-touch y marca como
    semilla las del nicho claro cuando vienen de una busqueda de perfiles. Devuelve cuantas eran nuevas."""
    today = today or datetime.date.today().isoformat()
    new, touches = 0, {}
    for handle, name, bio, source, seed in rows:
        handle = str(handle or "").lstrip("@")
        if not handle or handle.casefold() == str(my_handle).casefold():
            continue
        text = f"{name or ''} {bio or ''}".strip()
        if sc.is_political(text) or sc.looks_activist(text) or SPAM.search(text):
            continue
        niche = tc.niche_hits(text)
        if db.execute("SELECT 1 FROM accounts WHERE handle = ? COLLATE NOCASE", (handle,)).fetchone():
            db.execute("UPDATE accounts SET seen_count = seen_count + 1 WHERE handle = ? COLLATE NOCASE", (handle,))
        else:
            db.execute("INSERT INTO accounts(handle, display, bio, source, seed, first_seen, niche, spanish) VALUES(?,?,?,?,?,?,?,?)",
                       (handle, (name or "")[:80], (bio or "")[:300], source, seed, today, niche, spanish_flag(text) if text else None))
            touches.setdefault(handle.casefold(), source)
            new += 1
        if source.startswith("profiles:") and niche >= SEED_NICHE_MIN:
            db.execute("INSERT OR IGNORE INTO seeds(handle, source) VALUES(?,?)", (handle, source))
    if touches:
        pc.record_touch(db, touches, today)
    db.commit()
    return new


def add_seeds(db, handles, source="manual"):
    for handle in handles:
        db.execute("INSERT OR IGNORE INTO seeds(handle, source) VALUES(?,?)", (str(handle).lstrip("@"), source))
    db.commit()


def due_seeds(db, n, today=None):
    """Semillas cuya lista de seguidores toca leer: las nunca leidas primero, luego las leidas hace mas de REMINE_DAYS dias (mas antigua primero)."""
    today = today or datetime.date.today()
    floor = (today - datetime.timedelta(days=REMINE_DAYS)).isoformat()
    rows = db.execute("SELECT handle FROM seeds WHERE (followers IS NULL OR followers >= ?) AND (last_mined IS NULL OR last_mined <= ?) "
                      "ORDER BY last_mined IS NOT NULL, last_mined, rowid LIMIT ?", (SEED_MIN_FOLLOWERS, floor, n)).fetchall()
    return [r[0] for r in rows]


def mark_seed(db, handle, followers=None, today=None):
    db.execute("UPDATE seeds SET last_mined = ?, mined_count = mined_count + 1, followers = COALESCE(?, followers) WHERE handle = ? COLLATE NOCASE",
               (today or datetime.date.today().isoformat(), followers, handle))
    db.commit()


def pick_accounts(db, n, *, exclude_handles=frozenset()):
    """Las mejores cuentas aun sin tocar: del nicho (bio con terminos), no en otro idioma; las de bio vacia o sin nicho solo si salen de la lista de seguidores de una semilla
    y su nombre/bio esta en espanol. Las que acaban de seguirnos (`backfollow`) van primero siempre."""
    rows = [dict(zip(ACCOUNT_COLS, r)) for r in db.execute("SELECT " + ",".join(ACCOUNT_COLS) + " FROM accounts WHERE status = 'new'")]
    scored = []
    for row in rows:
        if row["spanish"] == 0 or (row["handle"].casefold() in exclude_handles and row["source"] != "backfollow"):
            continue
        backfollow = row["source"] == "backfollow"
        if not backfollow and row["niche"] < 1 and not (row["source"].startswith("followers:") and row["spanish"] == 1):
            continue
        row["score"] = (50 if backfollow else 0) + round(3 * min(row["niche"], 3) + (2 if row["spanish"] == 1 else 0) + (1.5 if row["source"].startswith("profiles:") else 0) + min(row["seen_count"], 4) * 0.5
                                                         + rb_recip.declared_bonus(row.get("bio")), 2)       # 07/10: la bio declara que devuelve el follow
        scored.append(row)
    scored.sort(key=lambda r: (-r["score"], r["handle"].casefold()))
    return scored[:n]


def mark_account(db, handle, status, today=None):
    db.execute("UPDATE accounts SET status = ?, acted_at = ? WHERE handle = ? COLLATE NOCASE", (status, today or datetime.date.today().isoformat(), str(handle).lstrip("@")))
    db.commit()


def first_touch(db, handles):
    return pc.first_touch(db, handles)


def stats(db, now=None):
    now = now or datetime.datetime.now()
    total = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    fresh = [dict(zip(POST_COLS, r)) for r in db.execute("SELECT " + ",".join(POST_COLS) + " FROM posts WHERE status = 'new' AND niche >= 1")]
    available = [r for r in fresh if r["spanish"] != 0 and estimated_age_hours(r, now) <= MAX_AGE_HOURS]
    return {"posts": total, "available_now": len(available), "available_accounts": len({r["handle"].casefold() for r in available}),
            "acted": db.execute("SELECT COUNT(*) FROM posts WHERE status != 'new'").fetchone()[0],
            "accounts": db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
            "accounts_available": db.execute("SELECT COUNT(*) FROM accounts WHERE status = 'new' AND (spanish IS NULL OR spanish = 1) AND niche >= 1").fetchone()[0],
            "seeds": db.execute("SELECT COUNT(*) FROM seeds").fetchone()[0]}
