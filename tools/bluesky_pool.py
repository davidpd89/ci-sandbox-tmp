"""Bluesky: reserva persistente de candidatos (pool) minada del grafo y de la conducta alrededor de las semillas del nicho (05/10/2026).

Por que existe. Medido el 05/10: el motor veia ~1.000-2.000 cuentas distintas al dia en la shortlist (3.337 en toda la semana, el 59 % repetidas entre rondas) y para
llegar a ~8.000 escrituras/dia hacen falta 3.000-5.000 cuentas DISTINTAS al dia. El cuello de botella no es la cuota de la API, es la OFERTA de cuentas nuevas. El motor
rastrea cada ronda desde cero y solo abre 6 semillas x 40 seguidores; aqui se hace al reves: una reserva en SQLite que crece sola.

Como se llena (solo lectura, API publica, sin IA). Para cada semilla curada (`bluesky_seeds.json`: editoriales, librerias, autores, resenadores, clubes, rol, comic):
  * `likes`     -> quien dio like o repost a sus posts recientes (`getAuthorFeed` + `getLikes`/`getRepostedBy`): gente ACTIVA ahora en el nicho (consulta E a GPT: la mejor fuente);
  * `followers` -> `getFollowers` (100 por peticion, con cursor que se retoma en la siguiente ejecucion);
  * `follows`   -> `getFollows` (a quien siguen).
El perfil viene con la biografia, asi que cada cuenta nueva cuesta ~0,01 peticiones. Cada cuenta guarda cuantas semillas distintas la tienen en su grafo (`seeds_count`:
senal independiente del idioma), cuantas senales de CONDUCTA tiene (`behav`: likes/reposts a posts de semillas), la fuente por la que llego la primera vez
(`first_source`, inmutable: atribucion first-touch) y reglas de descarte solo para lo que es seguro descartar (politica/ligue/sexo, spam, etiquetas de moderacion negativas).
El tamano de la cuenta y la actividad NO descartan: el scan decide por accion (like si, follow solo en cuentas de tamano razonable).

Como se usa: `bluesky_growth_scan._consume_pool` ofrece al scan las N mejores cuentas no ofrecidas en los ultimos 3 dias como fuente `pool`; el resto de la tuberia
(hidratar, verificar posts, puntuar, plan) no cambia. La tabla `touch` guarda la primera fuente por la que el scan vio cada handle (`src=` del motivo de cada accion).

    python tools/bluesky_pool.py mine [--pages 60] [--enrich 400]   # lee la conducta y el grafo de las semillas que toquen (rotan; los cursores se retoman)
    python tools/bluesky_pool.py stats                               # tamano de la reserva y de lo aprovechable
    python tools/bluesky_pool.py top [--n 20]                        # las mejores cuentas disponibles
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc
import growth_policy as gp
import pool_common as pc          # conexion, first-touch y cursores compartidos con la reserva de Mastodon
import reciprocity as rb_recip       # cuentas reciprocas (follow-back), comun a todas las redes

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
DB_PATH = os.path.join(ROOT, "cache", "pool.sqlite3")
SEEDS_JSON = os.path.join(ROOT, "bluesky_seeds.json")
PUBLIC_BASE = "https://public.api.bsky.app/xrpc"

PAGE = 100
HUGE_ACCOUNT = gp.FOLLOW_MAX_FOLLOWERS   # no descarta: el scan no la sigue (casi nunca devuelve el follow) pero si puede darle like (umbral comun: growth_policy)
OFFER_AGAIN_DAYS = gp.OFFER_AGAIN_DAYS
MAX_PAGES_PER_SEED_RUN = 8          # una semilla enorme no se come la ejecucion: se retoma luego
REFRESH_PAGES = 2                   # al re-minar un grafo ya recorrido solo se leen las primeras paginas (lo mas nuevo)
REFRESH_GRAPH_DAYS = 7
LIKE_POSTS_PER_SEED = 5             # posts recientes de la semilla de los que se leen likers/reposters
LIKE_POST_MAX_AGE_DAYS = 14
LIKE_POST_MIN_ENGAGEMENT = 2
PAUSE_SECONDS = 0.35                # ~3 peticiones/s: muy por debajo de las 3.000 cada 5 minutos por IP
BAD_LABELS = frozenset({"!hide", "!takedown", "!suspend", "spam", "porn", "sexual", "nudity", "graphic-media", "gore", "intolerant", "rude",
                        "threat", "self-harm", "impersonation", "scam", "dmca-violation"})
KIND_SOURCE = {"followers": "seed_follower", "follows": "seed_following", "liked": "seed_liker", "reposted": "seed_reposter"}

# 06/10: los clasificadores de texto viven en `text_common.py` (los usan todas las redes); aqui se reexportan con los mismos nombres.
from text_common import (seed_quality, NICHE_TERMS, SPAM, SPANISH_WORDS, ENGLISH_WORDS, CATALAN_HINT, PORTUGUESE_HINT, _norm, niche_hits, looks_spanish, looks_english)  # noqa: E402,F401


def _bad_label(profile):
    """Etiquetas de moderacion negativas (no toda etiqueta es una sentencia: `!no-unauthenticated` o `bluesky-elder` no descartan a nadie)."""
    for label in profile.get("labels") or []:
        value = str((label or {}).get("val") if isinstance(label, dict) else label).casefold()
        if isinstance(label, dict) and label.get("neg"):
            continue
        if value in BAD_LABELS:
            return value
    return None


def classify(profile):
    """(motivo_de_descarte | None, bio_hits, spanish, followers|None). Descarta solo lo que es seguro descartar; sin red.

    `getFollowers`/`getFollows`/`getLikes` devuelven la vista BASICA del perfil (sin contadores). El tamano y la actividad ya no descartan (GPT 05/10): son rasgos
    que usa cada accion (el scan no sigue cuentas enormes; un perfil sin posts no puede recibir like). Solo la granja de follows evidente (>5.000 seguidos y <100
    seguidores) y las etiquetas de moderacion negativas se descartan."""
    bio = (profile.get("description") or "")
    name = profile.get("displayName") or ""
    followers = profile.get("followersCount")
    follows = profile.get("followsCount")
    text = f"{name} {bio}"
    if sc.is_political(text):
        return "politica/ligue/sexo", 0, False, followers
    if SPAM.search(text):
        return "spam", 0, False, followers
    if follows is not None and followers is not None and int(follows) > 5000 and int(followers) < 100:
        return "granja de follows", 0, False, followers
    label = _bad_label(profile)
    if label:
        return f"etiqueta {label}", 0, False, followers
    return None, niche_hits(text), looks_spanish(bio) or looks_spanish(name), followers


def connect(path=None):
    """RRSS_POOL_PATH aisla los tests de la reserva real (como RRSS_RAMP_PATH con la rampa)."""
    path = path or os.environ.get("RRSS_POOL_PATH") or DB_PATH
    db = pc.connect_sqlite(path)
    db.execute(
        """CREATE TABLE IF NOT EXISTS accounts (
            did TEXT PRIMARY KEY, handle TEXT NOT NULL, display TEXT, bio TEXT, followers INTEGER, follows INTEGER, posts INTEGER, enriched INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, seeds_count INTEGER NOT NULL DEFAULT 0,
            bio_hits INTEGER NOT NULL DEFAULT 0, spanish INTEGER NOT NULL DEFAULT 0, reject TEXT, offered_at TEXT, offered_count INTEGER NOT NULL DEFAULT 0,
            behav INTEGER NOT NULL DEFAULT 0, last_engaged TEXT, english INTEGER NOT NULL DEFAULT 0, first_source TEXT, first_source_at TEXT
        )"""
    )
    have = {row[1] for row in db.execute("PRAGMA table_info(accounts)")}
    for column, ddl in (("behav", "INTEGER NOT NULL DEFAULT 0"), ("last_engaged", "TEXT"), ("english", "INTEGER NOT NULL DEFAULT 0"),
                        ("first_source", "TEXT"), ("first_source_at", "TEXT")):
        if column not in have:       # migracion de la reserva creada por la primera version
            db.execute(f"ALTER TABLE accounts ADD COLUMN {column} {ddl}")
    db.execute("CREATE TABLE IF NOT EXISTS edges (did TEXT NOT NULL, seed TEXT NOT NULL, kind TEXT NOT NULL, PRIMARY KEY (did, seed, kind))")
    db.execute(
        """CREATE TABLE IF NOT EXISTS mined (
            seed TEXT NOT NULL, kind TEXT NOT NULL, cursor TEXT, pages INTEGER NOT NULL DEFAULT 0, accounts INTEGER NOT NULL DEFAULT 0,
            done INTEGER NOT NULL DEFAULT 0, last_run TEXT, PRIMARY KEY (seed, kind)
        )"""
    )
    pc.ensure_touch_table(db)
    db.execute("CREATE INDEX IF NOT EXISTS idx_accounts_pick ON accounts(reject, spanish, seeds_count)")
    db.commit()
    return db


def _count(profile, key):
    value = profile.get(key)
    return None if value is None else int(value)


def upsert(db, profile, seed, kind, today):
    """Anota la cuenta y la evidencia (seed, kind). `kind`: followers | follows | liked | reposted. Devuelve True si la cuenta es nueva en la reserva."""
    did = profile.get("did")
    handle = (profile.get("handle") or "").casefold()
    if not did or not handle or handle.endswith(".invalid"):
        return False
    reject, hits, spanish, followers = classify(profile)
    detailed = 1 if profile.get("followersCount") is not None else 0
    cur = db.execute("SELECT enriched FROM accounts WHERE did = ?", (did,)).fetchone()
    bio = (profile.get("description") or "")[:300]
    english = int(looks_english(bio))
    if cur is None:
        db.execute(
            "INSERT INTO accounts(did, handle, display, bio, followers, follows, posts, enriched, first_seen, last_seen, seeds_count, bio_hits, spanish, reject, english, "
            "first_source, first_source_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (did, handle, profile.get("displayName") or "", bio, followers, _count(profile, "followsCount"), _count(profile, "postsCount"), detailed,
             today, today, 0, hits, int(spanish), reject, english, seed if kind == "scan" else KIND_SOURCE.get(kind, kind), today),
        )
    elif detailed or not cur[0]:      # una vista basica no pisa contadores ya hidratados
        db.execute(
            "UPDATE accounts SET handle=?, display=?, bio=?, last_seen=?, bio_hits=?, spanish=?, english=?, reject=COALESCE(?, reject) WHERE did=?",
            (handle, profile.get("displayName") or "", bio, today, hits, int(spanish), english, reject, did),
        )
        if detailed:
            db.execute("UPDATE accounts SET followers=?, follows=?, posts=?, enriched=1, reject=? WHERE did=?",
                       (followers, _count(profile, "followsCount"), _count(profile, "postsCount"), reject, did))
    changed = db.execute("INSERT OR IGNORE INTO edges(did, seed, kind) VALUES(?,?,?)", (did, seed, kind)).rowcount
    if changed and kind != "scan":      # la evidencia del scan (otras superficies) no cuenta como semilla del nicho
        db.execute("UPDATE accounts SET seeds_count = (SELECT COUNT(DISTINCT seed) FROM edges WHERE did = ? AND kind != 'scan') WHERE did = ?", (did, did))
        if kind in ("liked", "reposted"):
            db.execute("UPDATE accounts SET behav = (SELECT COUNT(*) FROM edges WHERE did = ? AND kind IN ('liked','reposted')) WHERE did = ?", (did, did))
    if kind in ("liked", "reposted"):
        db.execute("UPDATE accounts SET last_engaged = ? WHERE did = ?", (today, did))
    return cur is None


def record_scan_candidates(db, candidates, today=None):
    """Persiste lo que el scan descubrio por CUALQUIER superficie (busquedas, hashtags, Jetstream, starter packs...): la reserva es la union de todas las fuentes y
    no se pierde lo que un dia no se aprovecho. `candidates`: [(perfil, fuente)]. Devuelve cuantas cuentas eran nuevas en la reserva."""
    today = today or datetime.date.today().isoformat()
    new = 0
    for profile, source in candidates:
        if profile.get("did") and profile.get("handle") and profile.get("description") is not None:
            new += 1 if upsert(db, profile, f"scan:{source}", "scan", today) else 0
    db.commit()
    return new


def enrich(db, get, *, limit=300, today=None):
    """Hidrata (getProfiles, 25 por peticion) las cuentas aprovechables aun sin contadores: aplica reglas de descarte y guarda tamano/actividad."""
    cols = ("did", "seeds_count", "bio_hits", "spanish", "reject", "behav", "english")
    todo = []
    query = ("SELECT " + ",".join(cols) + " FROM accounts WHERE enriched = 0 AND reject IS NULL "
             "ORDER BY behav DESC, seeds_count DESC, bio_hits DESC LIMIT ?")
    for values in db.execute(query, (limit * 6,)):
        row = dict(zip(cols, values))
        if usable(row):
            todo.append(row["did"])
        if len(todo) >= limit:
            break
    spent = 0
    for start in range(0, len(todo), 25):
        chunk = todo[start:start + 25]
        try:
            data = get("app.bsky.actor.getProfiles", {"actors": chunk})
        except Exception:
            break
        spent += 1
        for profile in data.get("profiles") or []:
            reject, hits, spanish, followers = classify(profile)
            db.execute("UPDATE accounts SET followers=?, follows=?, posts=?, enriched=1, reject=?, bio_hits=?, spanish=?, english=? WHERE did=?",
                       (followers, _count(profile, "followsCount"), _count(profile, "postsCount"), reject, hits, int(spanish),
                        int(looks_english(profile.get("description") or "")), profile.get("did")))
        db.commit()
    return {"pages": spent, "profiles": len(todo)}


def load_seeds(path=SEEDS_JSON):
    """Semillas del nicho ordenadas: primero las que dan mas gente en espanol (editoriales, librerias, resenadores, clubes, autores medianos)."""
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return []
    weight = {"editorial": 5, "libreria": 5, "resenador": 5, "hub": 5, "club": 4, "autor": 3, "rol": 3, "comic": 3}
    seeds = []
    for handle, info in (data or {}).items():
        followers = int((info or {}).get("followers") or 0)
        if followers < 80 or not seed_quality(info):      # sin audiencia no hay a quien minar
            continue
        seeds.append((handle, (info or {}).get("type") or "", followers, weight.get((info or {}).get("type"), 2)))
    seeds.sort(key=lambda row: (-row[3], -min(row[2], 8000), row[0]))
    return [row[0] for row in seeds]


def promote_hubs(db, n=10, path=SEEDS_JSON):
    """Ciclo de descubrimiento (07/10, @rober de Mastodon): cuentas ya leidas, en espanol/nicho, con 1.500+ seguidores, 1.000+ seguidos y seguidos/seguidores 0,6-2,5 pasan a SEMILLAS
    (tipo `hub`): el minero lee sus seguidores y seguidos y aparecen nuevos hubs."""
    try:
        with open(path, encoding="utf-8") as stream:
            seeds = json.load(stream)
    except (OSError, ValueError):
        seeds = {}
    rows = []
    for did, handle, bio, followers, follows, posts, spanish, bio_hits in db.execute(
            "SELECT did, handle, bio, followers, follows, posts, spanish, bio_hits FROM accounts WHERE reject IS NULL AND followers >= ? AND follows >= ?",
            (rb_recip.SUPER_MIN_FOLLOWERS, rb_recip.SUPER_MIN_FOLLOWING)):
        rows.append({"handle": handle, "did": did, "bio": bio or "", "followers": followers, "following": follows, "statuses": posts, "ok": bool(spanish)})
    picks = rb_recip.select_hubs(rows, exclude=seeds, n=n)
    today = datetime.date.today().isoformat()
    for row in picks:
        seeds[row["handle"]] = {"bio": row["bio"][:200], "did": row["did"], "discovered": today, "followers": row["followers"], "following": row["following"], "type": "hub", "yield": 0}
    if picks:
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(seeds, stream, ensure_ascii=False, indent=1, sort_keys=True)
        rb_recip.register("bluesky", picks)
    return picks


def load_hubs(db, n=120, exclude=()):
    """Cuentas del propio nicho (autores, resenadores, libreros de 300-20.000 seguidores) cuyos posts mueven a otros lectores: se leen sus likers/reposters igual que los de
    las semillas (dos saltos: quien da like a quien ya esta en el nicho). Rotan por la ultima vez que se minaron."""
    banned = {str(h).casefold() for h in exclude}
    cols = ("handle", "followers", "seeds_count", "bio_hits", "spanish", "reject", "english", "behav")
    rows = db.execute("SELECT " + ",".join(cols) + " FROM accounts WHERE reject IS NULL AND enriched = 1 AND followers BETWEEN 300 AND ? AND spanish = 1 AND bio_hits >= 2 "
                      "ORDER BY seeds_count DESC, bio_hits DESC, followers DESC LIMIT ?", (HUGE_ACCOUNT, n * 6)).fetchall()
    last = {row[0]: row[1] for row in db.execute("SELECT seed, last_run FROM mined WHERE kind = 'likes'")}
    hubs = [dict(zip(cols, row))["handle"] for row in rows if row[0] not in banned]
    hubs.sort(key=lambda handle: last.get(handle) or "")      # nunca minado primero, luego el mas antiguo
    return hubs[:n]


def pick_work(db, seeds, limit=40, today=None, hubs=()):
    """[(seed, kind, cursor, refresh)] a minar ahora. Primero lo nunca minado (la conducta antes que el grafo), luego lo inacabado con cursor y por ultimo los
    refrescos: la conducta (`likes`) cada dia y el grafo (seguidores/seguidos) cada semana, solo las primeras paginas (lo mas reciente)."""
    today = today or datetime.date.today().isoformat()
    state = {(row[0], row[1]): row for row in db.execute("SELECT seed, kind, cursor, pages, accounts, done, last_run FROM mined")}
    fresh, resume, stale = [], [], []
    week_ago = (datetime.date.fromisoformat(today) - datetime.timedelta(days=REFRESH_GRAPH_DAYS)).isoformat()
    for seed in seeds:
        for kind in ("likes", "followers", "follows"):
            row = state.get((seed, kind))
            if row is None:
                fresh.append((seed, kind, None, False))
            elif not row[5] and row[2]:
                resume.append((seed, kind, row[2], False))
            elif row[5]:
                last = row[6] or ""
                if (kind == "likes" and last < today) or (kind != "likes" and last <= week_ago):
                    stale.append((last, seed, kind))
    for hub in hubs:       # los hubs solo aportan conducta (likers/reposters), no su grafo completo
        row = state.get((hub, "likes"))
        if row is None:
            fresh.append((hub, "likes", None, False))
        elif (row[6] or "") < today:
            stale.append((row[6] or "", hub, "likes"))
    stale.sort()
    work = fresh + resume + [(seed, kind, None, True) for _, seed, kind in stale]
    return work[:limit]


def _age_days(value, today):
    try:
        return (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(str(value)[:10])).days
    except ValueError:
        return 10 ** 6


def mine_engagers(db, get, seed, today):
    """Quien dio like/repost a los posts recientes de la semilla. Devuelve (peticiones, perfiles leidos, cuentas nuevas)."""
    spent = seen = new = 0
    try:
        feed = get("app.bsky.feed.getAuthorFeed", {"actor": seed, "limit": 40, "filter": "posts_no_replies"})
    except Exception as exc:
        if "not found" in str(exc).lower() or "400" in str(exc):
            return 1, 0, 0
        raise
    spent += 1
    posts = []
    for row in feed.get("feed") or []:
        post = row.get("post") or {}
        if row.get("reason") or str((post.get("author") or {}).get("handle") or "").casefold() != seed.casefold():
            continue       # un repost de la semilla no es contenido suyo
        likes, reposts = int(post.get("likeCount") or 0), int(post.get("repostCount") or 0)
        created = (post.get("record") or {}).get("createdAt") or post.get("indexedAt")
        if likes + reposts >= LIKE_POST_MIN_ENGAGEMENT and _age_days(created, today) <= LIKE_POST_MAX_AGE_DAYS:
            posts.append((likes + 2 * reposts, post))
    posts.sort(key=lambda pair: -pair[0])
    for _, post in posts[:LIKE_POSTS_PER_SEED]:
        for endpoint, key, kind, count_key in (("app.bsky.feed.getLikes", "likes", "liked", "likeCount"), ("app.bsky.feed.getRepostedBy", "repostedBy", "reposted", "repostCount")):
            if not int(post.get(count_key) or 0):
                continue
            data = get(endpoint, {"uri": post["uri"], "limit": PAGE})
            spent += 1
            for item in data.get(key) or []:
                profile = item.get("actor") if key == "likes" else item
                if not isinstance(profile, dict):
                    continue
                seen += 1
                new += 1 if upsert(db, profile, seed, kind, today) else 0
    return spent, seen, new


def mine(db, get, seeds, *, pages=60, today=None, sleep=time.sleep, pause=PAUSE_SECONDS, hubs=()):
    """Minado de conducta (likes/reposts) y grafo (seguidores/seguidos). `get(path, params)` devuelve el JSON; se inyecta para probar sin red.
    Devuelve {'pages','new','seen'}."""
    today = today or datetime.date.today().isoformat()
    spent = new = seen = 0
    for seed, kind, cursor, refresh in pick_work(db, seeds, limit=max(8, pages), today=today, hubs=hubs):
        if spent >= pages:
            break
        if kind == "likes":
            used, got, fresh = mine_engagers(db, get, seed, today)
            spent += used
            seen += got
            new += fresh
            db.execute(
                "INSERT INTO mined(seed, kind, cursor, pages, accounts, done, last_run) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(seed, kind) DO UPDATE SET pages=pages+excluded.pages, accounts=accounts+excluded.accounts, done=1, last_run=excluded.last_run",
                (seed, kind, None, used, got, 1, today),
            )
            db.commit()
            if pause:
                sleep(pause)
            continue
        got_pages = 0
        total_here = 0
        done = 0
        limit_pages = REFRESH_PAGES if refresh else MAX_PAGES_PER_SEED_RUN
        while got_pages < limit_pages and spent < pages:
            params = {"actor": seed, "limit": PAGE}
            if cursor:
                params["cursor"] = cursor
            try:
                data = get("app.bsky.graph.getFollowers" if kind == "followers" else "app.bsky.graph.getFollows", params)
            except Exception as exc:        # semilla borrada o cuenta privada: se marca hecha para no insistir
                if "not found" in str(exc).lower() or "400" in str(exc):
                    done = 1
                    break
                raise
            spent += 1
            got_pages += 1
            rows = data.get("followers" if kind == "followers" else "follows") or []
            for profile in rows:
                seen += 1
                total_here += 1
                new += 1 if upsert(db, profile, seed, kind, today) else 0
            cursor = data.get("cursor")
            if not cursor:
                done = 1
                break
            if pause:
                sleep(pause)
        if refresh:       # un refresco no reabre el recorrido completo: queda hecho y se vuelve a tocar en una semana
            done, cursor = 1, None
        db.execute(
            "INSERT INTO mined(seed, kind, cursor, pages, accounts, done, last_run) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(seed, kind) DO UPDATE SET cursor=excluded.cursor, pages=pages+excluded.pages, accounts=accounts+excluded.accounts, "
            "done=excluded.done, last_run=excluded.last_run",
            (seed, kind, None if done else cursor, got_pages, total_here, done, today),
        )
        db.commit()
    return {"pages": spent, "new": new, "seen": seen}


def affinity(row):
    """Puntuacion de oferta (no de plan): conducta reciente en el nicho, semillas distintas en su grafo, bio del nicho, idioma, tamano y actividad razonables."""
    seeds_count, bio_hits, spanish, followers, posts = row["seeds_count"], row["bio_hits"], row["spanish"], row["followers"], row["posts"]
    behav = row.get("behav") or 0
    score = 2.0 * min(seeds_count, 5) + 1.5 * min(bio_hits, 4) + (2.0 if spanish else 0.0) + 2.5 * min(behav, 3)
    score += 0.8 if followers is not None and 30 <= followers <= 3000 else 0.0           # tamano donde el follow-back existe
    score += 0.5 if posts is not None and posts >= 30 else 0.0
    score -= 1.0 if followers is not None and followers > HUGE_ACCOUNT else 0.0
    score -= 2.0 if row.get("english") else 0.0
    score += rb_recip.declared_bonus(row.get("bio"))
    score += rb_recip.affinity_bonus(followers, row.get("follows"), posts)      # 07/10: quien sigue casi tantas cuentas como le siguen suele devolver el follow
    return round(score, 2)


def usable(row):
    """Entra por cualquier evidencia fuerte (GPT 05/10): bio del nicho en espanol, 2+ semillas en su grafo, o conducta en posts de semillas (si su bio no es inglesa)."""
    if row["reject"]:
        return False
    if row.get("english") and row["seeds_count"] < 2:
        return False
    return bool((row["spanish"] and row["bio_hits"] >= 1) or row["seeds_count"] >= 2 or (row.get("behav", 0) >= 1))


def top_candidates(db, n=200, *, today=None, mark=True, again_days=OFFER_AGAIN_DAYS, exclude=()):
    today = today or datetime.date.today().isoformat()
    floor = (datetime.date.fromisoformat(today) - datetime.timedelta(days=again_days)).isoformat()
    cols = ("did", "handle", "display", "bio", "followers", "follows", "posts", "seeds_count", "bio_hits", "spanish", "reject", "offered_at", "behav", "english",
            "first_source")
    rows = db.execute(
        "SELECT " + ",".join(cols) + " FROM accounts WHERE reject IS NULL AND (offered_at IS NULL OR offered_at <= ?) "
        "ORDER BY behav DESC, seeds_count DESC, bio_hits DESC LIMIT ?", (floor, max(n * 8, 4000))
    ).fetchall()
    ranked = []
    for values in rows:
        row = dict(zip(cols, values))
        if usable(row) and row["handle"] not in exclude:
            row["score"] = affinity(row)
            ranked.append(row)
    ranked.sort(key=lambda row: (-row["score"], row["handle"]))
    chosen = ranked[:n]
    if mark and chosen:
        db.executemany("UPDATE accounts SET offered_at=?, offered_count=offered_count+1 WHERE did=?", [(today, row["did"]) for row in chosen])
        db.commit()
    return chosen


first_touch = pc.first_touch
record_touch = pc.record_touch


def stats(db, today=None):
    today = today or datetime.date.today().isoformat()
    total = db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    rejected = db.execute("SELECT COUNT(*) FROM accounts WHERE reject IS NOT NULL").fetchone()[0]
    cols = ("seeds_count", "bio_hits", "spanish", "followers", "posts", "reject", "offered_at", "behav", "english")
    avail = behavioral = 0
    floor = (datetime.date.fromisoformat(today) - datetime.timedelta(days=OFFER_AGAIN_DAYS)).isoformat()
    for values in db.execute("SELECT " + ",".join(cols) + " FROM accounts WHERE reject IS NULL"):
        row = dict(zip(cols, values))
        if usable(row) and (row["offered_at"] is None or row["offered_at"] <= floor):
            avail += 1
            behavioral += 1 if row["behav"] else 0
    mined = db.execute("SELECT COUNT(*), SUM(done) FROM mined").fetchone()
    return {"accounts": total, "rejected": rejected, "available_now": avail, "available_with_behavior": behavioral,
            "seed_lists_mined": mined[0] or 0, "seed_lists_done": mined[1] or 0}


def _public_get(path, params):
    import bluesky_interact as b
    return b._get(PUBLIC_BASE, path, params, auth=False)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    db = connect()
    try:
        if argv[0] == "mine":
            pages = int(argv[argv.index("--pages") + 1]) if "--pages" in argv else 60
            seeds = load_seeds()
            hubs = load_hubs(db, n=int(argv[argv.index("--hubs") + 1]) if "--hubs" in argv else 120, exclude=seeds)
            result = mine(db, _public_get, seeds, pages=pages, hubs=hubs)
            result["enriched"] = enrich(db, _public_get, limit=int(argv[argv.index("--enrich") + 1]) if "--enrich" in argv else 400)
            promoted = promote_hubs(db)
            if promoted:
                print("hubs reciprocos nuevos: " + ", ".join(f"{h['handle']} ({h['followers']}/{h['following']})" for h in promoted))
            print(f"semillas: {len(seeds)} hubs: {len(hubs)} | peticiones: {result['pages']} | perfiles leidos: {result['seen']} | cuentas nuevas en la reserva: {result['new']} | hidratadas: {result['enriched']}")
            print(json.dumps(stats(db), ensure_ascii=False))
        elif argv[0] == "stats":
            print(json.dumps(stats(db), ensure_ascii=False))
        elif argv[0] == "top":
            n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 20
            for row in top_candidates(db, n, mark=False):
                print(f"{row['score']:>5}  {row['handle']:<42} semillas={row['seeds_count']} conducta={row['behav']} nicho={row['bio_hits']} es={row['spanish']} "
                      f"seg={row['followers']} via={row['first_source']}  {row['bio'][:60]!r}")
        else:
            print(__doc__)
            return 2
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
