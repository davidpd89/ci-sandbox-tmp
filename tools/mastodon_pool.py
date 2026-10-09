"""Mastodon: reserva persistente de candidatos (pool) minada del grafo y la conducta alrededor de las semillas del nicho (05/10/2026).

Es la misma arquitectura que `bluesky_pool.py` (la consulta E a GPT y la medicion del embudo mostraron que el techo no era la API sino la OFERTA de cuentas
nuevas) adaptada a Mastodon:
  * mastodon.social da 300 peticiones por 5 minutos y las LECTURAS comparten ese cupo con las escrituras (1 peticion/s): leer bien importa mas que en Bluesky.
    Las cuentas de la API de Mastodon llegan COMPLETAS (bio, seguidores, seguidos, ultimo estado, bot, locked) en cada lista de seguidores/likers: no hay paso de
    hidratacion y cada peticion de 80 cuentas cuesta ~0,0125 lecturas por cuenta.
  * Semillas = cuentas hispanohablantes del nicho que ya conocemos: las que seguimos nosotros, las que dan favoritos/boosts a David y las que encuentra la
    busqueda de cuentas; se filtran con `seed_quality` (bio en espanol, del nicho, con audiencia, no bot).
  * De cada semilla se leen: quien dio favorito/boost a sus estados recientes (conducta reciente: la mejor senal), sus seguidores y sus seguidos
    (`/accounts/:id/followers|following`, 80 por pagina con cursor `max_id` que se retoma).
  * Cada cuenta guarda cuantas semillas distintas la tienen en su grafo, su conducta, su fuente first-touch (inmutable) y el idioma de su bio. El scan la ofrece
    como fuente `pool`. Tabla `touch` = primera fuente por la que el scan vio cada handle.

    python tools/mastodon_pool.py seeds                  # reconstruye mastodon_seeds.json (siguiendo propio + busqueda de cuentas)
    python tools/mastodon_pool.py mine [--pages 60]      # lee conducta y grafo de las semillas que toquen
    python tools/mastodon_pool.py stats | top [--n 20]
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import text_common as bp          # clasificadores de texto compartidos (nicho, espanol, ingles, portugues, catalan, spam)
import pool_common as pc          # conexion, first-touch y cursores compartidos con la reserva de Bluesky
import scan_common as sc
import growth_policy as gp
import reciprocity as rb_recip       # cuentas reciprocas (follow-back): bonus de oferta y promocion de hubs, comun a todas las redes

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON")
DB_PATH = os.path.join(ROOT, "cache", "pool.sqlite3")
SEEDS_JSON = os.path.join(ROOT, "mastodon_seeds.json")

PAGE = 80
OFFER_AGAIN_DAYS = gp.OFFER_AGAIN_DAYS
MAX_PAGES_PER_SEED_RUN = 4
REFRESH_PAGES = 1
REFRESH_GRAPH_DAYS = 7
ENGAGEMENT_STATUSES_PER_SEED = 5
STATUS_MAX_AGE_DAYS = 14
STATUS_MIN_ENGAGEMENT = 2
HUGE_ACCOUNT = gp.FOLLOW_MAX_FOLLOWERS
MAX_INACTIVE_DAYS = gp.MAX_INACTIVE_DAYS
PAUSE_SECONDS = 0.8                 # ~1,2 peticiones/s: el cupo es 300 por 5 minutos y las escrituras tambien lo usan
KIND_SOURCE = {"followers": "seed_follower", "following": "seed_following", "favourited": "seed_favouriter", "reblogged": "seed_booster", "endorsed": "seed_endorsement"}
NON_SEED_KINDS = {"scan", "suggested", "directory"}      # evidencias que NO cuentan como semilla del nicho en seeds_count (el servidor sugiere, el directorio lista a quien se apunto)
HTML_TAG = re.compile(r"<[^>]+>")


def plain(html):
    return re.sub(r"\s+", " ", HTML_TAG.sub(" ", str(html or ""))).strip()


def classify(account):
    """(motivo_de_descarte | None, bio_hits, spanish, followers). Solo se descarta lo seguro: politica/ligue/sexo, spam, bots, cuentas puente, inactivas."""
    bio = plain(account.get("note"))
    name = plain(account.get("display_name"))
    acct = str(account.get("acct") or "")
    text = f"{name} {bio}"
    followers = account.get("followers_count")
    if account.get("bot"):
        return "bot", 0, False, followers
    if account.get("group"):
        return "grupo", 0, False, followers
    if sc.is_feed_bridge(acct):
        return "cuenta puente", 0, False, followers
    if sc.is_political(text) or sc.looks_activist(text):
        return "politica/ligue/sexo", 0, False, followers
    if bp.SPAM.search(text):
        return "spam", 0, False, followers
    if bp.other_language(text):
        return "otro idioma", 0, False, followers
    last = account.get("last_status_at")
    if last:
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(str(last)[:10])).days
            if age > MAX_INACTIVE_DAYS:
                return "inactiva", 0, False, followers
        except ValueError:
            pass
    elif account.get("statuses_count") == 0:
        return "sin estados", 0, False, followers
    following = account.get("following_count")
    if following is not None and followers is not None and int(following) > 5000 and int(followers) < 100:
        return "granja de follows", 0, False, followers
    return None, bp.niche_hits(text), bp.looks_spanish(bio) or bp.looks_spanish(name), followers


def connect(path=None):
    """RRSS_MASTODON_POOL_PATH aisla los tests de la reserva real."""
    path = path or os.environ.get("RRSS_MASTODON_POOL_PATH") or DB_PATH
    db = pc.connect_sqlite(path)
    db.execute(
        """CREATE TABLE IF NOT EXISTS accounts (
            acct TEXT PRIMARY KEY, account_id TEXT, display TEXT, bio TEXT, followers INTEGER, following INTEGER, statuses INTEGER, last_status_at TEXT,
            locked INTEGER NOT NULL DEFAULT 0, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, seeds_count INTEGER NOT NULL DEFAULT 0,
            bio_hits INTEGER NOT NULL DEFAULT 0, spanish INTEGER NOT NULL DEFAULT 0, english INTEGER NOT NULL DEFAULT 0, reject TEXT,
            behav INTEGER NOT NULL DEFAULT 0, last_engaged TEXT, offered_at TEXT, offered_count INTEGER NOT NULL DEFAULT 0, first_source TEXT
        )"""
    )
    db.execute("CREATE TABLE IF NOT EXISTS edges (acct TEXT NOT NULL, seed TEXT NOT NULL, kind TEXT NOT NULL, PRIMARY KEY (acct, seed, kind))")
    db.execute(
        """CREATE TABLE IF NOT EXISTS mined (
            seed TEXT NOT NULL, kind TEXT NOT NULL, cursor TEXT, pages INTEGER NOT NULL DEFAULT 0, accounts INTEGER NOT NULL DEFAULT 0,
            done INTEGER NOT NULL DEFAULT 0, last_run TEXT, PRIMARY KEY (seed, kind)
        )"""
    )
    pc.ensure_touch_table(db)
    pc.ensure_cursors_table(db)
    db.execute("CREATE INDEX IF NOT EXISTS idx_accounts_pick ON accounts(reject, spanish, seeds_count)")
    db.commit()
    return db


def upsert(db, account, seed, kind, today):
    """Anota la cuenta y la evidencia (seed, kind): followers | following | favourited | reblogged | scan. True si la cuenta es nueva en la reserva."""
    acct = str(account.get("acct") or "").strip().casefold()
    if not acct:
        return False
    reject, hits, spanish, followers = classify(account)
    bio = plain(account.get("note"))[:300]
    english = int(bp.looks_english(bio))
    cur = db.execute("SELECT 1 FROM accounts WHERE acct = ?", (acct,)).fetchone()
    values = (str(account.get("id") or ""), plain(account.get("display_name")), bio, followers, account.get("following_count"), account.get("statuses_count"),
              account.get("last_status_at"), int(bool(account.get("locked"))))
    if cur is None:
        db.execute(
            "INSERT INTO accounts(acct, account_id, display, bio, followers, following, statuses, last_status_at, locked, first_seen, last_seen, seeds_count, "
            "bio_hits, spanish, english, reject, first_source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (acct, *values, today, today, 0, hits, int(spanish), english, reject, seed if kind in NON_SEED_KINDS else KIND_SOURCE.get(kind, kind)),
        )
    else:
        db.execute(
            "UPDATE accounts SET account_id=?, display=?, bio=?, followers=?, following=?, statuses=?, last_status_at=?, locked=?, last_seen=?, bio_hits=?, spanish=?, "
            "english=?, reject=? WHERE acct=?", (*values, today, hits, int(spanish), english, reject, acct))
    changed = db.execute("INSERT OR IGNORE INTO edges(acct, seed, kind) VALUES(?,?,?)", (acct, seed, kind)).rowcount
    if changed and kind not in NON_SEED_KINDS:
        db.execute("UPDATE accounts SET seeds_count = (SELECT COUNT(DISTINCT seed) FROM edges WHERE acct = ? AND kind NOT IN ('scan','suggested','directory')) WHERE acct = ?", (acct, acct))
        if kind in ("favourited", "reblogged"):
            db.execute("UPDATE accounts SET behav = (SELECT COUNT(*) FROM edges WHERE acct = ? AND kind IN ('favourited','reblogged')) WHERE acct = ?", (acct, acct))
    if kind in ("favourited", "reblogged"):
        db.execute("UPDATE accounts SET last_engaged = ? WHERE acct = ?", (today, acct))
    return cur is None


def record_scan_candidates(db, accounts, today=None):
    """Persiste lo que el scan descubrio por cualquier superficie. `accounts`: [(cuenta de la API, fuente)]."""
    today = today or datetime.date.today().isoformat()
    new = 0
    for account, source in accounts:
        if account.get("acct") and account.get("note") is not None:
            new += 1 if upsert(db, account, f"scan:{source}", "scan", today) else 0
    db.commit()
    return new


def seed_quality(account):
    """Semilla = cuenta del nicho en espanol con audiencia, activa y que no es bot ni puente. Misma regla de idioma que en Bluesky (`bp.seed_quality`)."""
    reject, hits, spanish, followers = classify(account)
    if reject or (followers or 0) < 60:
        return False
    return bp.seed_quality({"bio": plain(account.get("note")), "type": "autor"}) and hits >= 1


def build_seeds(own_following, searched, existing=None, today=None):
    """{acct: info}: lo que ya habia + las cuentas que seguimos + las halladas por busqueda, solo las que pasan `seed_quality`."""
    today = today or datetime.date.today().isoformat()
    seeds = dict(existing or {})
    for source, accounts in (("siguiendo", own_following), ("busqueda", searched)):
        for account in accounts:
            acct = str(account.get("acct") or "").casefold()
            if not acct or acct in seeds or not seed_quality(account):
                continue
            seeds[acct] = {"account_id": str(account.get("id") or ""), "followers": int(account.get("followers_count") or 0), "bio": plain(account.get("note"))[:200],
                           "origin": source, "discovered": today}
    return seeds


def load_seeds(path=SEEDS_JSON):
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def promote_hubs(db, n=10, path=SEEDS_JSON):
    """Ciclo de descubrimiento (07/10, @rober): de las cuentas ya leidas, las 'super reciprocas' en espanol/nicho (1.500+ seguidores, 1.000+ seguidos, seguidos/seguidores 0,6-2,5) pasan a ser SEMILLAS:
    el minero lee sus seguidores y sus seguidos y aparecen nuevos hubs. Devuelve los hubs anadidos."""
    seeds = load_seeds(path)
    rows = []
    for acct, account_id, bio, followers, following, statuses, spanish, bio_hits in db.execute(
            "SELECT acct, account_id, bio, followers, following, statuses, spanish, bio_hits FROM accounts WHERE reject IS NULL AND account_id != '' AND followers >= ? AND following >= ?",
            (rb_recip.SUPER_MIN_FOLLOWERS, rb_recip.SUPER_MIN_FOLLOWING)):
        rows.append({"handle": acct, "account_id": account_id, "bio": bio or "", "followers": followers, "following": following, "statuses": statuses, "ok": bool(spanish)})
    picks = rb_recip.select_hubs(rows, exclude=seeds, n=n)
    today = datetime.date.today().isoformat()
    for row in picks:
        seeds[row["handle"]] = {"account_id": row["account_id"], "bio": row["bio"][:200], "discovered": today, "followers": row["followers"], "following": row["following"], "origin": "hub"}
    if picks:
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(seeds, stream, ensure_ascii=False, indent=1, sort_keys=True)
        rb_recip.register("mastodon", picks)
    return picks


def pick_work(db, seeds, limit=40, today=None, hubs=()):
    """[(seed, kind, cursor, refresh)]: primero lo nunca minado (la conducta antes que el grafo), luego lo inacabado con cursor y por ultimo refrescos
    (conducta cada dia, grafo cada semana, solo la primera pagina)."""
    today = today or datetime.date.today().isoformat()
    state = {(row[0], row[1]): row for row in db.execute("SELECT seed, kind, cursor, pages, accounts, done, last_run FROM mined")}
    week_ago = (datetime.date.fromisoformat(today) - datetime.timedelta(days=REFRESH_GRAPH_DAYS)).isoformat()
    fresh, resume, stale = [], [], []
    for seed in seeds:
        for kind in ("engagement", "followers", "following"):
            row = state.get((seed, kind))
            if row is None:
                fresh.append((seed, kind, None, False))
            elif not row[5] and row[2]:
                resume.append((seed, kind, row[2], False))
            elif row[5]:
                last = row[6] or ""
                if (kind == "engagement" and last < today) or (kind != "engagement" and last <= week_ago):
                    stale.append((last, seed, kind))
    for hub in hubs:
        row = state.get((hub, "engagement"))
        if row is None:
            fresh.append((hub, "engagement", None, False))
        elif (row[6] or "") < today:
            stale.append((row[6] or "", hub, "engagement"))
    stale.sort()
    return (fresh + resume + [(seed, kind, None, True) for _, seed, kind in stale])[:limit]


def _age_days(value, today):
    try:
        return (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(str(value)[:10])).days
    except ValueError:
        return 10 ** 6


def mine_engagement(db, api, seed, account_id, today):
    """Quien dio favorito/boost a los estados recientes de la semilla. `api.statuses(account_id)` y `api.engagers(status_id, kind)` -> lista de cuentas."""
    spent = seen = new = 0
    statuses = api.statuses(account_id)
    spent += 1
    picked = []
    for status in statuses or []:
        favourites, boosts = int(status.get("favourites_count") or 0), int(status.get("reblogs_count") or 0)
        if favourites + boosts >= STATUS_MIN_ENGAGEMENT and _age_days(status.get("created_at"), today) <= STATUS_MAX_AGE_DAYS:
            picked.append((favourites + 2 * boosts, status))
    picked.sort(key=lambda pair: -pair[0])
    for _, status in picked[:ENGAGEMENT_STATUSES_PER_SEED]:
        for kind, label, count in (("favourites", "favourited", status.get("favourites_count")), ("boosts", "reblogged", status.get("reblogs_count"))):
            if not int(count or 0):
                continue
            rows = api.engagers(status["id"], kind)
            spent += 1
            for account in rows or []:
                seen += 1
                new += 1 if upsert(db, account, seed, label, today) else 0
    return spent, seen, new


def mine(db, api, seeds, *, pages=60, today=None, sleep=time.sleep, pause=PAUSE_SECONDS, hubs=()):
    """`api`: objeto con statuses(account_id), engagers(status_id, kind) y neighbors(account_id, kind, cursor) -> (cuentas, siguiente_cursor)."""
    today = today or datetime.date.today().isoformat()
    spent = new = seen = 0
    for seed, kind, cursor, refresh in pick_work(db, list(seeds), limit=max(8, pages), today=today, hubs=hubs):
        if spent >= pages:
            break
        info = seeds.get(seed) or {}
        account_id = info.get("account_id") or ""
        if not account_id:
            row = db.execute("SELECT account_id FROM accounts WHERE acct = ?", (seed,)).fetchone()
            account_id = row[0] if row else ""
        if not account_id:
            continue
        if kind == "engagement":
            try:
                used, got, fresh = mine_engagement(db, api, seed, account_id, today)
            except Exception as exc:
                if "404" in str(exc) or "not found" in str(exc).lower():
                    used, got, fresh = 1, 0, 0
                else:
                    raise
            spent, seen, new = spent + used, seen + got, new + fresh
            db.execute(
                "INSERT INTO mined(seed, kind, cursor, pages, accounts, done, last_run) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(seed, kind) DO UPDATE SET pages=pages+excluded.pages, accounts=accounts+excluded.accounts, done=1, last_run=excluded.last_run",
                (seed, kind, None, used, got, 1, today))
            db.commit()
            if pause:
                sleep(pause)
            continue
        got_pages, total_here, done = 0, 0, 0
        limit_pages = REFRESH_PAGES if refresh else MAX_PAGES_PER_SEED_RUN
        label = "followers" if kind == "followers" else "following"
        while got_pages < limit_pages and spent < pages:
            try:
                accounts, cursor = api.neighbors(account_id, kind, cursor)
            except Exception as exc:
                if "404" in str(exc) or "401" in str(exc) or "403" in str(exc) or "not found" in str(exc).lower():
                    done = 1          # lista oculta o cuenta que ya no existe: no se insiste
                    break
                raise
            spent += 1
            got_pages += 1
            for account in accounts or []:
                seen += 1
                total_here += 1
                new += 1 if upsert(db, account, seed, label, today) else 0
            if not cursor:
                done = 1
                break
            if pause:
                sleep(pause)
        if refresh:
            done, cursor = 1, None
        db.execute(
            "INSERT INTO mined(seed, kind, cursor, pages, accounts, done, last_run) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(seed, kind) DO UPDATE SET cursor=excluded.cursor, pages=pages+excluded.pages, accounts=accounts+excluded.accounts, "
            "done=excluded.done, last_run=excluded.last_run", (seed, kind, None if done else cursor, got_pages, total_here, done, today))
        db.commit()
    return {"pages": spent, "new": new, "seen": seen}


DIRECTORY_PAGES_PER_RUN = 3
ENDORSEMENT_SEEDS_PER_RUN = 10


def mine_extras(db, api, seeds, *, today=None, budget=20, sleep=time.sleep, pause=PAUSE_SECONDS):
    """Superficies oficiales que el scan no usaba (consulta F a GPT): sugerencias personalizadas del servidor (`/api/v2/suggestions`, 1 lectura = hasta 80 cuentas), directorio
    de perfiles que se apuntaron a discovery (`/api/v1/directory`, con cursor `offset`) y cuentas que las semillas destacan (`/accounts/:id/endorsements`)."""
    today = today or datetime.date.today().isoformat()
    spent = new = 0
    last = {(r[0], r[1]): r[2] for r in db.execute("SELECT seed, kind, last_run FROM mined")}
    if spent < budget and (last.get(("suggestions", "suggested")) or "") < today:
        try:
            rows = api.suggestions()
            spent += 1
            for item in rows or []:
                account = item.get("account") if isinstance(item, dict) and "account" in item else item
                if isinstance(account, dict):
                    new += 1 if upsert(db, account, "suggestions", "suggested", today) else 0
            db.execute("INSERT INTO mined(seed, kind, cursor, pages, accounts, done, last_run) VALUES('suggestions','suggested',NULL,1,?,1,?) "
                       "ON CONFLICT(seed, kind) DO UPDATE SET pages=pages+1, last_run=excluded.last_run", (len(rows or []), today))
            db.commit()
        except Exception:
            pass
    row = db.execute("SELECT cursor FROM mined WHERE seed='directory' AND kind='directory'").fetchone()
    offset = int(row[0]) if row and row[0] else 0
    for _ in range(DIRECTORY_PAGES_PER_RUN):
        if spent >= budget:
            break
        try:
            rows = api.directory(offset)
        except Exception:
            break
        spent += 1
        for account in rows or []:
            new += 1 if upsert(db, account, "directory", "directory", today) else 0
        offset = offset + PAGE if rows else 0            # al agotarse vuelve a empezar (el orden `active` cambia)
        db.execute("INSERT INTO mined(seed, kind, cursor, pages, accounts, done, last_run) VALUES('directory','directory',?,1,?,0,?) "
                   "ON CONFLICT(seed, kind) DO UPDATE SET cursor=excluded.cursor, pages=pages+1, last_run=excluded.last_run", (str(offset), len(rows or []), today))
        db.commit()
        if pause:
            sleep(pause)
    week_ago = (datetime.date.fromisoformat(today) - datetime.timedelta(days=REFRESH_GRAPH_DAYS)).isoformat()
    todo = [seed for seed in seeds if (last.get((seed, "endorsements")) or "") <= week_ago][:ENDORSEMENT_SEEDS_PER_RUN]
    for seed in todo:
        if spent >= budget:
            break
        account_id = (seeds.get(seed) or {}).get("account_id")
        if not account_id:
            continue
        try:
            rows = api.endorsements(account_id)
        except Exception:
            rows = []
        spent += 1
        for account in rows or []:
            new += 1 if upsert(db, account, seed, "endorsed", today) else 0
        db.execute("INSERT INTO mined(seed, kind, cursor, pages, accounts, done, last_run) VALUES(?,'endorsements',NULL,1,?,1,?) "
                   "ON CONFLICT(seed, kind) DO UPDATE SET pages=pages+1, last_run=excluded.last_run", (seed, len(rows or []), today))
        db.commit()
        if pause:
            sleep(pause)
    return {"pages": spent, "new": new}


def load_hubs(db, n=80, exclude=()):
    """Cuentas del propio nicho (100-20.000 seguidores, bio del nicho en espanol) cuyos estados mueven a otros: se leen sus favoriteadores/boosters (2 saltos)."""
    banned = {str(h).casefold() for h in exclude}
    rows = db.execute("SELECT acct FROM accounts WHERE reject IS NULL AND spanish = 1 AND bio_hits >= 2 AND followers BETWEEN 100 AND ? AND account_id != '' "
                      "ORDER BY seeds_count DESC, bio_hits DESC, followers DESC LIMIT ?", (HUGE_ACCOUNT, n * 6)).fetchall()
    last = {row[0]: row[1] for row in db.execute("SELECT seed, last_run FROM mined WHERE kind = 'engagement'")}
    hubs = [row[0] for row in rows if row[0] not in banned]
    hubs.sort(key=lambda acct: last.get(acct) or "")
    return hubs[:n]


def affinity(row):
    # En Mastodon la comunidad hispanohablante es pequena y muy entrelazada: quien da favoritos a una editorial puede ser de tecnologia o politica, asi que la bio del nicho
    # pesa mas que la conducta (al reves que en Bluesky).
    score = 1.5 * min(row["seeds_count"], 5) + 2.5 * min(row["bio_hits"], 4) + (2.0 if row["spanish"] else 0.0) + 1.5 * min(row.get("behav") or 0, 3)
    followers, statuses = row["followers"], row["statuses"]
    score += 0.8 if followers is not None and 20 <= followers <= 3000 else 0.0
    score += 0.5 if statuses is not None and statuses >= 30 else 0.0
    score -= 1.0 if followers is not None and followers > HUGE_ACCOUNT else 0.0
    score -= 2.0 if row.get("english") else 0.0
    score -= 0.5 if row.get("locked") else 0.0
    score += rb_recip.declared_bonus(row.get("bio"))
    score += rb_recip.affinity_bonus(followers, row.get("following"), statuses)      # 07/10: quien sigue casi tantas cuentas como le siguen suele devolver el follow
    return round(score, 2)


def usable(row, relaxed=False):
    """Entra por cualquier evidencia fuerte: bio del nicho en espanol, 2+ semillas, o conducta en estados de semillas (si su bio no es inglesa). Con `relaxed` (el scan lo pide para no quedarse
    corto de oferta, 06/10) tambien entra quien tiene la bio en espanol y esta en el grafo de UNA semilla del nicho (lector de una editorial/autor/libreria aunque su bio no diga «libros»:
    1.316 cuentas descartadas); el scan las ordena por detras de las que si traen evidencia fuerte."""
    if row["reject"]:
        return False
    if row.get("english") and row["seeds_count"] < 2:
        return False
    strong = bool((row["spanish"] and row["bio_hits"] >= 1) or row["seeds_count"] >= 2 or row.get("behav", 0) >= 1)
    return strong or bool(relaxed and row["spanish"] and row["seeds_count"] >= 1)


COLS = ("acct", "account_id", "display", "bio", "followers", "following", "statuses", "last_status_at", "locked", "seeds_count", "bio_hits", "spanish", "english",
        "reject", "behav", "offered_at", "first_source")


def top_candidates(db, n=200, *, today=None, mark=True, again_days=OFFER_AGAIN_DAYS, exclude=(), relaxed=False):
    today = today or datetime.date.today().isoformat()
    floor = (datetime.date.fromisoformat(today) - datetime.timedelta(days=again_days)).isoformat()
    rows = db.execute("SELECT " + ",".join(COLS) + " FROM accounts WHERE reject IS NULL AND (offered_at IS NULL OR offered_at <= ?) "
                      "ORDER BY behav DESC, seeds_count DESC, bio_hits DESC LIMIT ?", (floor, max(n * 8, 4000))).fetchall()
    ranked = []
    for values in rows:
        row = dict(zip(COLS, values))
        if usable(row, relaxed) and row["acct"] not in exclude:
            row["score"] = affinity(row) - (0.0 if usable(row) else 3.0)
            ranked.append(row)
    ranked.sort(key=lambda row: (-row["score"], row["acct"]))
    chosen = ranked[:n]
    if mark and chosen:
        db.executemany("UPDATE accounts SET offered_at=?, offered_count=offered_count+1 WHERE acct=?", [(today, row["acct"]) for row in chosen])
        db.commit()
    return chosen


first_touch = pc.first_touch
record_touch = pc.record_touch
get_cursor = pc.get_cursor
set_cursor = pc.set_cursor


def stats(db, today=None):
    today = today or datetime.date.today().isoformat()
    total = db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    rejected = db.execute("SELECT COUNT(*) FROM accounts WHERE reject IS NOT NULL").fetchone()[0]
    floor = (datetime.date.fromisoformat(today) - datetime.timedelta(days=OFFER_AGAIN_DAYS)).isoformat()
    avail = behavioral = 0
    for values in db.execute("SELECT " + ",".join(COLS) + " FROM accounts WHERE reject IS NULL"):
        row = dict(zip(COLS, values))
        if usable(row, True) and (row["offered_at"] is None or row["offered_at"] <= floor):       # lo que el scan puede usar (con la regla relajada)
            avail += 1
            behavioral += 1 if row["behav"] else 0
    mined = db.execute("SELECT COUNT(*), SUM(done) FROM mined").fetchone()
    return {"accounts": total, "rejected": rejected, "available_now": avail, "available_with_behavior": behavioral,
            "seed_lists_mined": mined[0] or 0, "seed_lists_done": mined[1] or 0}


class LiveApi:
    """Adaptador sobre `mastodon_interact` (una peticion por llamada, cursor `max_id` tomado de la cabecera Link)."""

    def __init__(self):
        import mastodon_interact as m
        self.m = m

    def statuses(self, account_id):
        return self.m._get(f"accounts/{account_id}/statuses", {"limit": 40, "exclude_replies": "true", "exclude_reblogs": "true"})

    def engagers(self, status_id, kind):
        endpoint = "favourited_by" if kind == "favourites" else "reblogged_by"
        return self.m._get(f"statuses/{status_id}/{endpoint}", {"limit": PAGE})

    def suggestions(self):
        return self.m._get_v2("suggestions", {"limit": PAGE}) or []

    def directory(self, offset):
        return self.m._get("directory", {"order": "active", "local": "false", "limit": PAGE, "offset": int(offset)})

    def endorsements(self, account_id):
        return self.m._get(f"accounts/{account_id}/endorsements", {"limit": PAGE})

    def neighbors(self, account_id, kind, cursor):
        params = {"limit": PAGE}
        if cursor:
            params["max_id"] = cursor
        response = self.m._get_response(f"{self.m.API}/accounts/{account_id}/{kind}", params)
        rows = response.json()
        link = str(response.headers.get("Link") or "")
        match = re.search(r'max_id=(\d+)[^>]*>\s*;\s*rel="next"', link)
        return (rows if isinstance(rows, list) else []), (match.group(1) if match else None)


def refresh_seeds(m):
    """Reconstruye mastodon_seeds.json con lo que seguimos y lo que encuentra la busqueda de cuentas (solo lectura)."""
    me = m._get("accounts/verify_credentials")
    own_following = m._get_paginated(f"accounts/{me['id']}/following", {"limit": PAGE}, max_pages=8)
    cfg = json.load(open(os.path.join(ROOT, "growth_config.json"), encoding="utf-8"))
    searched = []
    for query in (cfg.get("account_queries") or []) + ["editorial", "editorial fantasía", "librería", "libros", "escritora", "escritor fantasía", "reseñas de libros", "club de lectura",
                                                         "biblioteca", "rol de mesa", "cómic", "novela juvenil", "autor indie", "booktuber", "traductora"]:
        try:
            searched.extend(m._get_v2("search", {"q": query, "type": "accounts", "limit": 40}).get("accounts") or [])
        except Exception:
            continue
    seeds = build_seeds(own_following, searched, existing=load_seeds())
    with open(SEEDS_JSON, "w", encoding="utf-8") as stream:
        json.dump(seeds, stream, ensure_ascii=False, indent=1, sort_keys=True)
    return seeds


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    db = connect()
    try:
        import mastodon_interact as _m
        _m.set_priority("scan")                 # el minero de la reserva lee a mansalva: deja siempre margen de cupo a ejecutores y herramientas
        if argv[0] == "seeds":
            import mastodon_interact as m
            seeds = refresh_seeds(m)
            print(f"semillas: {len(seeds)}")
        elif argv[0] == "mine":
            pages = int(argv[argv.index("--pages") + 1]) if "--pages" in argv else 60
            seeds = load_seeds()
            hubs = load_hubs(db, n=int(argv[argv.index("--hubs") + 1]) if "--hubs" in argv else 60, exclude=seeds)
            api = LiveApi()
            result = mine(db, api, seeds, pages=pages, hubs=hubs)
            extra = mine_extras(db, api, seeds)
            result["pages"] += extra["pages"]
            result["new"] += extra["new"]
            promoted = promote_hubs(db)
            if promoted:
                print("hubs reciprocos nuevos: " + ", ".join(f"{h['handle']} ({h['followers']}/{h['following']})" for h in promoted))
            print(f"semillas: {len(seeds)} hubs: {len(hubs)} | peticiones: {result['pages']} | perfiles leidos: {result['seen']} | cuentas nuevas: {result['new']}")
            print(json.dumps(stats(db), ensure_ascii=False))
        elif argv[0] == "stats":
            print(json.dumps(stats(db), ensure_ascii=False))
        elif argv[0] == "top":
            n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 20
            for row in top_candidates(db, n, mark=False):
                print(f"{row['score']:>5}  {row['acct']:<40} semillas={row['seeds_count']} conducta={row['behav']} nicho={row['bio_hits']} es={row['spanish']} seg={row['followers']}  {row['bio'][:60]!r}")
        else:
            print(__doc__)
            return 2
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
