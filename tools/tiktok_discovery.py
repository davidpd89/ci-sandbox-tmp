"""Motor de discovery nativo de TikTok (equivalente móvil de bluesky_growth_scan).

Superficies (todas lectura, validadas en el Xiaomi real):

  user_search   búsqueda -> pestaña Usuarios: editoriales, escritores, booktokers…
                (la fila ya trae @handle, seguidores, prueba social y relación)
  video_search  búsqueda -> pestaña Vídeos -> vídeo -> Comentarios -> comentaristas
                -> perfil (handle/contadores/bio)
  inbox         seguidores nuevos que aún no seguimos ("Seguir también")
  feeds         Para ti / Siguiendo (en tiktok_growth_scan)

Cada superficie devuelve filas de candidato homogéneas; el ranking, la memoria
(`growth_seen.csv`), la rotación de queries y las métricas (`discovery_metrics.csv`, formato
común de `growth_common`, el mismo que Bluesky) son comunes. Nunca escribe en la cuenta.
"""
from __future__ import annotations

import csv
import datetime
import os
import random
import re
import unicodedata
from typing import Any

import reciprocity      # nucleo comun de reciprocidad (follow-back), compartido por todas las redes

import growth_common as gc
import scan_common as sc
from mobile_client import MobileCliError
from tiktok_mobile_interact import (
    MY_HANDLE,
    TikTokMobileChallenge,
    TikTokTargetNotFound,
)
from tiktok_mobile_nav import TikTokNavigator, clean

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_TIKTOK")
SEEN_CSV = os.path.join(ROOT, "growth_seen.csv")
METRICS_CSV = os.path.join(ROOT, "discovery_metrics.csv")

SEEN_FIELDS = ["handle", "first_seen", "last_seen", "times_seen", "last_source"]


def _norm(value: Any) -> str:
    value = " ".join(str(value or "").casefold().split())
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def term_hits(text: str, terms: list[str]) -> int:
    value = _norm(text)
    tokens = set(re.findall(r"[a-z0-9_]+", value))
    hits = 0
    for term in terms:
        wanted = _norm(term)
        # Flexión regular plural española: «novelas» debe contar como
        # «novela», pero «novelazo»/subcadenas no acreditan nicho.
        if ((" " in wanted and wanted in value) or wanted in tokens
                or (" " not in wanted and len(wanted) >= 4
                    and not wanted.endswith("s") and wanted + "s" in tokens)):
            hits += 1
    return hits


def is_spam(text: str, terms: list[str]) -> bool:
    value = _norm(text)
    return any(_norm(term) in value for term in terms)


# --- memoria ----------------------------------------------------------------------
def load_seen(path: str = SEEN_CSV) -> dict[str, dict[str, str]]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", newline="") as stream:
        return {row["handle"].casefold(): row for row in csv.DictReader(stream)}


def save_seen(seen: dict[str, dict[str, str]], path: str = SEEN_CSV) -> None:
    with open(path, "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SEEN_FIELDS)
        writer.writeheader()
        for row in sorted(seen.values(), key=lambda r: r["handle"].casefold()):
            writer.writerow({k: row.get(k, "") for k in SEEN_FIELDS})


def touch_seen(seen: dict[str, dict[str, str]], handle: str, source: str, today: str) -> bool:
    """Marca visto; devuelve True si es un handle nuevo."""
    key = handle.casefold()
    row = seen.get(key)
    if row is None:
        seen[key] = {
            "handle": handle, "first_seen": today, "last_seen": today,
            "times_seen": "1", "last_source": source,
        }
        return True
    row["last_seen"] = today
    row["times_seen"] = str(int(row.get("times_seen") or 0) + 1)
    row["last_source"] = source
    return False


def recently_seen(seen: dict[str, dict[str, str]], handle: str, today: str, days: int) -> bool:
    row = seen.get(handle.casefold())
    if not row:
        return False
    try:
        last = datetime.date.fromisoformat(row["last_seen"])
        now = datetime.date.fromisoformat(today)
    except (KeyError, ValueError):
        return False
    return (now - last).days < days


def load_stats(path: str = METRICS_CSV) -> dict:
    """Rendimiento reciente por (surface, query): formato común a todas las redes."""
    return gc.load_discovery_metrics(path)


def pick_queries(candidates: list[str], surface: str, stats: dict, n: int) -> list[str]:
    """Rotación común (growth_common.rank_keys): nunca usadas primero, luego utilidad,
    exploración y tiempo sin usarse; penaliza repetir la misma query el mismo día."""
    return gc.rank_keys(list(dict.fromkeys(candidates)), stats, surface=surface)[: max(0, n)]


SEED_POOL_CSV = os.path.join(ROOT, "seed_pool.csv")
_SEED_WORDS = (
    "editorial", "libreria", "librería", "libros", "escritor", "escritora", "autor", "autora",
    "booktok", "booktoker", "lectora", "lector", "bookstagram",
)


def load_seed_pool(path: str = SEED_POOL_CSV) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as stream:
        rows = sorted(csv.DictReader(stream), key=lambda r: -float(r.get("score") or 0))
    return [r["handle"] for r in rows]


def update_seed_pool(rows: list[dict[str, Any]], config: dict, path: str = SEED_POOL_CSV,
                     *, max_size: int = 60) -> None:
    """Aprende semillas: cuentas del nicho con audiencia real (comentarios) se convierten en
    nuevas semillas para la siguiente ronda (como el frontier de Bluesky)."""
    pool: dict[str, dict[str, str]] = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as stream:
            pool = {r["handle"].casefold(): r for r in csv.DictReader(stream)}
    min_score = float((config.get("scoring") or {}).get("seed_min_score", 6))
    min_followers = int((config.get("scoring") or {}).get("seed_min_followers", 1500))
    for row in rows:
        followers = row.get("followers") or 0
        identity = _norm(" ".join([row["name"], row["handle"]]))
        hub = reciprocity.classify(row.get("followers"), row.get("following")) == "super"        # 07/10: hub recíproco del nicho = semilla (sus comentaristas devuelven follows)
        if row.get("score", 0) >= min_score and followers >= min_followers and (hub or any(_norm(w) in identity for w in _SEED_WORDS)):
            pool[row["handle"].casefold()] = {
                "handle": row["handle"], "score": str(row["score"]), "followers": str(followers),
            }
    best = sorted(pool.values(), key=lambda r: -float(r["score"]))[:max_size]
    with open(path, "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["handle", "score", "followers"])
        writer.writeheader()
        writer.writerows(best)


def append_metrics(metrics: list[dict[str, Any]], path: str = METRICS_CSV, *, run_id: str = "") -> None:
    for m in metrics:
        gc.append_discovery_metric(
            path, date=m["fecha"], run_id=run_id or m["fecha"], surface=m["surface"], key=m["query"],
            fetched=m["rows"], accepted=m["valid"], new_handles=m["new"],
        )


# --- candidatos y ranking -------------------------------------------------------------
def make_row(
    handle: str, *, source: str, name: str = "", bio: str = "", caption: str = "",
    followers: int | None = None, following: int | None = None, likes: int | None = None,
    relation: str | None = None, proof: str | None = None, url: str | None = None,
    comment_text: str = "", post_ref: dict | None = None,
) -> dict[str, Any]:
    return {
        "post_ref": post_ref,
        "handle": handle.lstrip("@"), "source": source, "name": name, "bio": bio,
        "caption": caption, "followers": followers, "following": following, "likes": likes,
        "relation": relation, "proof": proof, "url": url, "comment_text": comment_text,
    }


def validate_row(row: dict[str, Any], config: dict, *, discarded=frozenset()) -> bool:
    """Filtro mecánico: handle propio, política/spam/adulto, relación ya existente."""
    # La caption pertenece al creador del vídeo, no a quien escribió debajo.
    # Tampoco debe excluirse un comentarista por spam ajeno.
    own_caption = "" if row.get("source") in ("video_search:comment", "seed:comment") else row["caption"]
    text = " ".join(filter(None, [row["name"], row["bio"], own_caption, row.get("comment_text", "")]))
    if not text.strip():
        text = row["handle"]
    if row.get("relation") in ("following", "friends", "requested"):
        return False
    if not sc.is_valid_candidate(row["handle"], text, MY_HANDLE, discarded):
        return False
    if is_spam(text, config.get("spam_terms") or []):
        return False
    return True


_EN_WORDS = {"the", "and", "of", "writes", "author", "books", "my", "your", "for", "with", "writer", "romance", "fantasy", "reader", "love"}
_ES_WORDS = {"el", "la", "los", "las", "de", "y", "que", "libros", "escritora", "escritor", "lectora", "novela", "en", "un", "una", "mi", "con"}


def looks_english(text: str) -> bool:
    value = _norm(text)
    words = set(re.findall(r"[a-z]+", value))
    if re.search(r"[ñáéíóú¿¡]", str(text).casefold()):
        return False
    return len(words & _EN_WORDS) >= 1 and not (words & _ES_WORDS)


def assess_quality(row: dict[str, Any], config: dict, *, today: str | None = None) -> dict[str, str]:
    """Calidad de evidencia, no diagnóstico de «cuenta humana».

    Un handle/nombre con «libro» no demuestra afinidad ni actividad. Solo
    acredita un candidato para auto-follow la evidencia textual atribuible
    al propio perfil/vídeo/comentario. La fecha de publicación ausente es
    DESCONOCIDA: no atribuir actividad reciente ficticia.
    """
    terms = config.get("niche_terms") or []
    source = str(row.get("source") or "")
    bio = str(row.get("bio") or "")
    comment = str(row.get("comment_text") or "")
    caption = str(row.get("caption") or "")
    # En video_search:comment, caption corresponde al VÍDEO de otra cuenta,
    # no al autor del comentario. No atribuirle ese texto como contenido propio.
    owns_caption = source not in ("video_search:comment", "seed:comment")
    own_content = caption if owns_caption else ""
    own_text = " ".join(filter(None, [bio, comment, own_content]))
    if not own_text.strip() or term_hits(own_text, terms) == 0:
        return {"decision": "review", "reason": "sin_nicho_fuera_del_nombre",
                "activity": "unknown"}
    if looks_english(own_text):
        return {"decision": "review", "reason": "idioma_no_confirmado",
                "activity": "unknown"}
    business = re.search(
        r"editorial|ediciones|librer[ií]a|bookstore|publishing|tienda|shop|distribu",
        f"{row.get('handle') or ''} {row.get('name') or ''}", re.I,
    )
    if business:
        return {"decision": "review", "reason": "cuenta_organizacion",
                "activity": "unknown"}
    recent = str(row.get("last_post_date") or "").strip()
    if recent:
        try:
            last = datetime.date.fromisoformat(recent[:10])
            current = datetime.date.fromisoformat(today) if today else datetime.date.today()
            if last > current:
                return {"decision": "review", "reason": "fecha_actividad_inconsistente",
                        "activity": "unknown"}
            if (current - last).days > int((config.get("scoring") or {}).get("max_inactive_days", 45)):
                return {"decision": "review", "reason": "ultima_publicacion_antigua",
                        "activity": "stale"}
        except ValueError:
            return {"decision": "review", "reason": "fecha_actividad_invalida",
                    "activity": "unknown"}
    # El follow de entrada ya es una interacción observada y verificada:
    # una persona que NOS sigue no necesita publicar un vídeo para que
    # podamos corresponder, siempre que su bio sea del nicho.
    if (row.get("relation") == "follows_me" and
            term_hits(bio, terms) > 0):
        return {"decision": "eligible", "reason": "follow_entrante_y_bio_nicho",
                "activity": "inbound_follow"}
    # Una bio de libros sola, sin follow entrante, puede estar obsoleta:
    # exigir vídeo propio o comentario observado de esta cuenta.
    if not (own_content.strip() and term_hits(own_content, terms) or
            comment.strip() and term_hits(comment, terms)):
        return {"decision": "review", "reason": "actividad_no_observada",
                "activity": "unknown"}
    return {"decision": "eligible", "reason": "nicho_y_actividad_observada",
            "activity": "dated" if recent else "observed_undated"}


def score_row(row: dict[str, Any], config: dict) -> float:
    """Puntuación de afinidad. Calibrada con cuentas pequeñas/medianas del nicho primero."""
    terms = config.get("niche_terms") or []
    weights = config.get("scoring") or {}
    score = 0.0
    identity = " ".join(filter(None, [row["name"], row["handle"], row["bio"]]))
    score += min(3, term_hits(identity, terms)) * float(weights.get("identity_hit", 2.0))
    # La caption de un vídeo ajeno no puntúa como actividad de la
    # persona que escribió un comentario debajo del vídeo.
    own_caption = "" if row.get("source") in ("video_search:comment", "seed:comment") else row["caption"]
    activity = " ".join(filter(None, [own_caption, row.get("comment_text", "")]))
    score += min(3, term_hits(activity, terms)) * float(weights.get("activity_hit", 1.0))
    if row.get("proof") and term_hits(row["proof"], terms):
        score += float(weights.get("proof_hit", 1.0))
    if looks_english(" ".join(filter(None, [row["name"], row["bio"], own_caption, row.get("comment_text", "")]))):
        score -= float(weights.get("english_penalty", 3.0))
    # Reciprocidad solo cuenta si hay señal real de nicho (los bots de servicios también "siguen").
    if row.get("relation") == "follows_me" and score >= float(weights.get("follows_me_min_base", 2.0)):
        score += float(weights.get("follows_me", 6.0))
    # 07/10 (David: TikTok es donde mas se estila el follow-back): cuentas recientes que siguen casi tantas como las siguen, o cuya bio declara follow-back, devuelven el follow.
    # Como la reciprocidad de arriba, solo cuenta con senal real de nicho (los bots de servicios tambien dicen «sigo de vuelta»).
    if score >= float(weights.get("follows_me_min_base", 2.0)):
        score += float(weights.get("reciprocity_weight", 1.0)) * (
            reciprocity.affinity_bonus(row.get("followers"), row.get("following")) + reciprocity.declared_bonus(row.get("bio")))
    # 07/10: editoriales, librerias y tiendas no devuelven el follow (los candidatos del scan eran sobre todo editoriales): se prefieren lectores/escritores personales
    if re.search(r"editorial|ediciones|librer|bookstore|biblioteca|publishing|tienda|shop|distribu", f"{row.get('name') or ''} {row.get('handle') or ''}", re.I):
        score -= float(weights.get("business_penalty", 4.0))
    followers = row.get("followers")
    if followers is not None:
        low, high, huge = (
            int(weights.get("sweet_low", 100)),
            int(weights.get("sweet_high", 50_000)),
            int(weights.get("huge", 250_000)),
        )
        if low <= followers <= high:
            score += float(weights.get("sweet_spot", 2.0))
        elif followers > huge:
            score -= float(weights.get("huge_penalty", 2.0))
        elif followers < 10:
            score -= 1.0
    return score


# --- superficies ------------------------------------------------------------------------
def user_search_surface(nav: TikTokNavigator, query: str, config: dict, ctx: dict) -> list[dict[str, Any]]:
    pages = int(config["budgets"].get("user_search_pages", 3))
    nav.search(query, "Usuarios")
    rows = []
    for item in nav.read_user_results(max_pages=pages):
        rows.append(make_row(
            item["handle"], source="user_search", name=item["name"], bio=item["bio_line"],
            followers=item["followers"], likes=item["likes"], relation=item["relation"],
            proof=item["proof"],
        ))
    return rows


def _comment_worth_profile(text: str, config: dict) -> bool:
    if len(text.strip()) < 12 or is_spam(text, config.get("spam_terms") or []):
        return False
    if term_hits(text, config.get("niche_terms") or []) >= 1:
        return True
    return len(text.strip()) >= 40  # comentario sustantivo aunque no use términos del nicho


def _harvest_comments(nav: TikTokNavigator, caption: str, config: dict) -> list[dict[str, Any]]:
    """Con un vídeo abierto: lee comentarios, resuelve perfil de los relevantes."""
    b = config["budgets"]
    rows: list[dict[str, Any]] = []
    nav.open_comments()
    comments = [
        c for c in nav.read_comments(max_pages=int(b.get("comment_pages", 2)))
        if _comment_worth_profile(c["text"], config)
    ]
    for comment in comments[: int(b.get("commenters_per_video", 6))]:
        try:
            nav.open_commenter_profile(comment)
            profile = nav.read_profile()
        finally:
            nav.c.press("BACK", nav.device.id)
            time.sleep(1.0)
        if not profile.get("handle"):
            continue
        rows.append(make_row(
            profile["handle"], source="video_search:comment", name=profile.get("name") or comment["name"],
            bio=profile.get("bio") or "", caption=caption, followers=profile.get("followers"),
            following=profile.get("following"), likes=profile.get("likes"),
            relation=profile.get("relation"), comment_text=comment["text"],
        ))
    nav.c.press("BACK", nav.device.id)  # cierra el panel de comentarios
    time.sleep(0.8)
    return rows


def video_search_surface(nav: TikTokNavigator, query: str, config: dict, ctx: dict) -> list[dict[str, Any]]:
    b = config["budgets"]
    nav.search(query, "Vídeos")
    terms = config.get("niche_terms") or []
    cards = nav.video_cards()
    cards = [c for c in cards if term_hits(c["label"] + " " + c["author"], terms) >= 1]
    cards.sort(key=lambda c: -term_hits(c["label"] + " " + c["author"], terms))
    rows: list[dict[str, Any]] = []
    for card in cards[: int(b.get("videos_per_query", 2))]:
        caption = card["label"]
        nav.open_video(card)
        author = nav.a.resolve_author_handle(expect_feed=False)
        if author:
            rows.append(make_row(
                author, source="video_search:author", name=card["author"], caption=caption,
            ))
        rows.extend(_harvest_comments(nav, caption, config))
        nav.back_to_results()
    return rows


import time  # noqa: E402  (usado por las superficies)


def inbox_surface(nav: TikTokNavigator, query: str, config: dict, ctx: dict) -> list[dict[str, Any]]:
    """Nuevos seguidores -> perfil (handle/bio) -> candidatos de follow-back."""
    limit = int(config["budgets"].get("inbox_profiles", 8))
    nav.open_new_followers()
    followers = [r for r in nav.read_new_followers(limit=limit) if r["relation"] == "follows_me"]
    rows = []
    for follower in followers:
        try:
            nav._tap_element(follower["element"], 1.8)
            profile = nav.read_profile()
        finally:
            nav.c.press("BACK", nav.device.id)
            time.sleep(1.0)
        if not profile.get("handle"):
            continue
        rows.append(make_row(
            profile["handle"], source="inbox:new_follower", name=profile.get("name") or follower["name"],
            bio=profile.get("bio") or "", followers=profile.get("followers"),
            following=profile.get("following"), likes=profile.get("likes"), relation="follows_me",
        ))
    return rows


def _surface_fn(name: str):
    return globals()[f"{name}_surface"]




def run_surface(nav, surface, query, config, ctx):
    """Ejecuta una superficie y devuelve (rows_validas, stats). Un fallo de UI no mata la ronda."""
    today = ctx["today"]
    rows = None
    for attempt in range(2):  # un reintento de lectura tras volver al feed (solo lectura)
        try:
            rows = _surface_fn(surface)(nav, query, config, ctx)
            break
        except TikTokMobileChallenge:
            raise
        except (MobileCliError, TikTokTargetNotFound) as exc:
            ctx["issues"].append(f"{surface}[{query}] intento {attempt + 1}: {type(exc).__name__}: {exc}")
            try:
                nav.return_to_feed()
            except Exception:  # noqa: BLE001
                pass
    if rows is None:
        return [], {"rows": 0, "valid": 0, "new": 0}
    valid = []
    new = 0
    for row in rows:
        if not validate_row(row, config, discarded=ctx["discarded"]):
            continue
        row["ctx"] = f"{surface}:{query}"   # contexto independiente (query/semilla) para recurrencia
        # Procedencia explícita: source define el papel del candidato
        # (autor, comentarista, seguidor); query conserva la semilla/búsqueda.
        # Nunca atribuir la caption del vídeo al autor de un comentario.
        row["provenance"] = {
            "surface": surface, "query": query,
            "source": row["source"], "phase": "direct",
        }
        row["score"] = score_row(row, config)
        if touch_seen(ctx["seen"], row["handle"], row["source"], today):
            new += 1
        valid.append(row)
    ctx["metrics"].append({
        "fecha": today, "surface": surface, "query": query,
        "rows": len(rows), "valid": len(valid), "new": new,
    })
    try:
        nav.return_to_feed()
    except Exception as exc:  # noqa: BLE001
        ctx["issues"].append(f"return_to_feed tras {surface}[{query}]: {exc}")
    return valid, {"rows": len(rows), "valid": len(valid), "new": new}


def seed_comments_surface(nav: TikTokNavigator, seed: str, config: dict, ctx: dict) -> list[dict[str, Any]]:
    """Cuenta semilla (editorial/autor) -> sus vídeos recientes -> comentaristas."""
    b = config["budgets"]
    nav.a.open_profile(seed)
    time.sleep(1.5)
    profile = nav.read_profile()
    if (profile.get("handle") or "").casefold() != seed.casefold():
        raise TikTokTargetNotFound(f"perfil semilla inesperado: {profile.get('handle')!r}")
    rows = [make_row(
        seed, source="seed:profile", name=profile.get("name") or "", bio=profile.get("bio") or "",
        followers=profile.get("followers"), following=profile.get("following"),
        likes=profile.get("likes"), relation=profile.get("relation"),
    )]
    cells = nav.profile_video_cells()
    for ordinal, cell in enumerate(cells[: int(b.get("videos_per_seed", 2))]):
        nav._tap_element(cell, 2.2)
        caption = nav.current_caption()
        if caption:
            ref = nav.a.make_post_ref(seed, ordinal, caption)
            rows.append(make_row(seed, source="seed:post", name=profile.get("name") or "",
                                 caption=caption, url=ref["id"], followers=profile.get("followers"),
                                 relation=profile.get("relation"), post_ref=ref))
        rows.extend(_harvest_comments(nav, caption, config))
        nav.c.press("BACK", nav.device.id)  # vídeo -> perfil
        time.sleep(1.2)
    return rows


def author_posts_surface(nav: TikTokNavigator, handle: str, config: dict, ctx: dict) -> list[dict[str, Any]]:
    """Perfil candidato -> su vídeo reciente (no anclado) -> URL + caption.

    Es lo que convierte una persona en objetivo de like/comentario: sin URL de vídeo no hay
    acción de contenido. Solo lectura."""
    nav.a.open_profile(handle)
    time.sleep(1.5)
    profile = nav.read_profile()
    if (profile.get("handle") or "").casefold() != handle.casefold():
        raise TikTokTargetNotFound(f"perfil inesperado: {profile.get('handle')!r}")
    rows = []
    cells = nav.profile_video_cells()
    for ordinal, cell in enumerate(cells[: int(config["budgets"].get("author_posts_per_profile", 1))]):
        nav._tap_element(cell, 2.2)
        caption = nav.current_caption()
        nav.c.press("BACK", nav.device.id)  # vídeo -> perfil
        time.sleep(1.0)
        if caption:
            ref = nav.a.make_post_ref(handle, ordinal, caption)
            rows.append(make_row(
                handle, source="author_post", name=profile.get("name") or "", bio=profile.get("bio") or "",
                caption=caption, url=ref["id"], followers=profile.get("followers"),
                following=profile.get("following"), likes=profile.get("likes"),
                relation=profile.get("relation"), post_ref=ref,
            ))
    return rows
