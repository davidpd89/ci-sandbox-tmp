"""Discovery TikTok nativo, compacto y de lectura limitada.

No usa la API privada de TikTok ni el TikTok web histórico. Recorre únicamente las
superficies nativas habilitadas (por defecto Para ti/Siguiendo), filtra de forma
mecánica y entrega un shortlist con IDs Txxx para que la IA decida sin recibir
volcados de pantalla.

La búsqueda nativa está desactivada hasta validarla expresamente en el Xiaomi.
No ejecuta follow/like/comment.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc
from mobile_client import MobileCliError
from mobile_runtime import ensure_server, mobile_session_lock
from tiktok_mobile_interact import (
    MY_HANDLE,
    TikTokMobileAdapter,
    TikTokMobileChallenge,
    TikTokTargetNotFound,
    TikTokWrongAccount,
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_TIKTOK")
CONFIG_PATH = os.path.join(ROOT, "growth_config.json")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")


def _norm(value):
    value = " ".join(str(value or "").casefold().split())
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("version") != 1 or data.get("mode") != "supervised_native":
        raise RuntimeError("growth_config TikTok incompatible")
    import hashtag_query_consumers as hqc
    return hqc.extend_native_config("tiktok", data)


def _term_hits(text, terms):
    value = _norm(text)
    tokens = set(re.findall(r"[a-z0-9_]+", value))
    hits = 0
    for term in terms:
        wanted = _norm(term)
        if (" " in wanted and wanted in value) or wanted in tokens:
            hits += 1
    return hits


def _spammy(text, terms):
    value = _norm(text)
    return any(_norm(term) in value for term in terms)


def _followed_handles(path=REGISTRO_CSV):
    out = set()
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if (row.get("tipo") or "").strip().casefold() != "follow":
                continue
            if (row.get("resultado") or "").strip().casefold() not in (
                "confirmado", "publicado",
            ):
                continue
            handle = (row.get("cuenta") or "").strip().lstrip("@").casefold()
            if handle:
                out.add(handle)
    return out


def _needs_handle(snapshot, config):
    """El feed no muestra @handle: resolverlo (1 tap + BACK) solo si el post ya
    pasa anuncio/spam/nicho, para no recorrer perfiles de posts irrelevantes."""
    if snapshot.get("handle") or snapshot.get("is_ad"):
        return False
    caption = " ".join((snapshot.get("caption") or "").split())
    if not caption or _spammy(caption, config.get("spam_terms") or []):
        return False
    return _term_hits(caption, config.get("niche_terms") or []) >= 1


def _candidate_from_snapshot(snapshot, *, config, known, followed, discarded):
    handle = (snapshot.get("handle") or "").strip().lstrip("@")
    caption = " ".join((snapshot.get("caption") or "").split())
    if snapshot.get("is_ad"):
        return None
    if not sc.is_valid_candidate(handle, caption, MY_HANDLE, discarded):
        return None
    if _spammy(caption, config.get("spam_terms") or []):
        return None
    hits = _term_hits(caption, config.get("niche_terms") or [])
    if hits < 1:
        return None
    return {
        "handle": handle,
        "caption": caption,
        "source": snapshot.get("source") or "unknown",
        "niche_hits": hits,
        "known": handle.casefold() in known,
        "known_date": known.get(handle.casefold()),
        "followed": handle.casefold() in followed,
    }


# Contrato cerrado de roles. Un source desconocido puede conservarse para
# revisión, pero no acreditar afinidad, recurrencia o un plan automático.
TRUSTED_CANDIDATE_SOURCES = frozenset({
    "for_you", "following", "video_search:author", "video_search:comment",
    "user_search", "inbox:new_follower", "seed:profile", "seed:post",
    "author_post",
})
ACTIONABLE_POST_SOURCES = frozenset({
    "for_you", "following", "video_search:author", "seed:post", "author_post",
})

# Relaciones observables fuente/superficie. Un `provenance` copiado desde
# otro tipo de pantalla NO constituye prueba de autoría ni de comentario.
PROVENANCE_ROLES = {
    "user_search": frozenset({"user_search"}),
    "video_search": frozenset({"video_search:author", "video_search:comment"}),
    "seed_comments": frozenset({"seed:profile", "seed:post", "video_search:comment"}),
    "author_posts": frozenset({"author_post"}),
    "inbox": frozenset({"inbox:new_follower"}),
}


_CREATOR_WORDS = ("editorial", "libreria", "librería", "escritor", "escritora", "autor", "autora", "booktok")


def _lane(item):
    """community (ya nos conoce) / creator (escritores, editoriales, librerías) / acquisition."""
    if item["known"] or item.get("relation") == "follows_me":
        return "community"
    identity = _norm(" ".join([item.get("name", ""), item.get("handle", "")]))
    if any(_norm(word) in identity for word in _CREATOR_WORDS):
        return "creator"
    return "acquisition"


def _compact_shortlist(rows, *, limit, config=None):
    import tiktok_discovery as disc
    grouped = {}
    for row in rows:
        key = row["handle"].casefold()
        item = grouped.setdefault(key, {
            "handle": row["handle"],
            "known": row["known"],
            "known_date": row["known_date"],
            "followed": row["followed"],
            "sources": set(),
            "trusted_sources": set(),
            "provenance": {},
            "posts": [],
            "score": 0,
            "quality_decisions": set(),
            "quality_reasons": set(),
        })
        # Solo se evalua calidad con filas de fuente reconocida: una fuente desconocida
        # (p. ej. frontier historico) no puede aportar la evidencia que aprueba un follow.
        if config and config.get("niche_terms") and row["source"] in TRUSTED_CANDIDATE_SOURCES:
            evidence = disc.assess_quality(row, config)
            item["quality_decisions"].add(evidence["decision"])
            if evidence["decision"] != "eligible":
                item["quality_reasons"].add(evidence["reason"])
        # El orden de filas/checkpoints no puede revocar la evidencia de
        # un follow ya existente ni de una solicitud pendiente.
        item["known"] = bool(item["known"] or row["known"])
        item["followed"] = bool(
            item["followed"] or row["followed"]
            or row.get("relation") in ("following", "friends", "requested")
        )
        for extra in ("name", "bio", "followers", "relation", "proof", "comment_text"):
            if row.get(extra) and not item.get(extra):
                item[extra] = row[extra]
        source = row["source"]
        item["sources"].add(source)
        trusted = source in TRUSTED_CANDIDATE_SOURCES
        if trusted:
            item["trusted_sources"].add(source)
            item.setdefault("contexts", set()).add(row.get("ctx") or source)
        # Los hallazgos repetidos por frontier son evidencia de procedencia,
        # no otra acción ni otra puntuación de actividad del mismo perfil.
        origins = [row.get("provenance"), *(row.get("extra_provenance") or [])]
        for origin in origins:
            if not isinstance(origin, dict):
                continue
            origin_source = origin.get("source")
            if not isinstance(origin_source, str) or not origin_source:
                continue
            if origin is row.get("provenance") and origin_source != row["source"]:
                continue  # metadato contradictorio: no reinterpretar autorías
            surface = str(origin.get("surface") or "")
            query = str(origin.get("query") or "")
            phase = str(origin.get("phase") or "direct")
            if (origin_source not in TRUSTED_CANDIDATE_SOURCES
                    or phase not in ("direct", "frontier")
                    or (surface and origin_source not in PROVENANCE_ROLES.get(surface, ()))):
                continue
            item["provenance"][(surface, query, origin_source, phase)] = {
                "surface": surface, "query": query,
                "source": origin_source, "phase": phase,
            }
        # Nunca permitir que un checkpoint legado o source inesperado
        # eleve el score de una observación fiable del mismo handle.
        if trusted:
            item["score"] = max(item["score"], row.get("score", row["niche_hits"]))
        post_key = (row.get("url"), row["caption"])
        # Nunca convertir un origen antiguo/desconocido (incluido
        # frontier:video_search:comment) en vídeo propio accionable.
        if source not in ACTIONABLE_POST_SOURCES:
            continue
        if not any((p.get("url"), p["caption"]) == post_key for p in item["posts"]):
            actions = []
            if row.get("url"):
                actions.append("like")
                # En TikTok el comentario es la interacción principal con un creador:
                # se propone siempre salvo cierres de conversación; la IA decide.
                if not sc.is_conversation_closer(row["caption"]):
                    actions.append("comment")
            item["posts"].append({
                "url": row.get("url"),
                "post_ref": row.get("post_ref"),
                "caption": row["caption"],
                "source": row["source"],
                "actions": actions,
                "score": row["niche_hits"],
            })

    for item in grouped.values():
        # independent_source_count: en cuántos contextos INDEPENDIENTES (queries/semillas/superficies)
        # aparece. 3 búsquedas distintas + 2 semillas valen mucho más que 7 resultados de la misma query.
        independent = max(len(item.get("contexts", ())), len(item["trusted_sources"]))
        weight = float(((config or {}).get("scoring") or {}).get("recurrence_weight", 1.5))
        item["score"] += min(4, max(0, independent - 1)) * weight
        item["independent"] = independent
        # Mantener compatible la vista de análisis sin configuración; en el
        # flujo real sí hay config y no se aprueba un nombre aislado.
        blockers = {"ultima_publicacion_antigua", "fecha_actividad_inconsistente",
                    "fecha_actividad_invalida", "cuenta_organizacion",
                    "idioma_no_confirmado"}
        item["quality"] = (
            "eligible" if "eligible" in item["quality_decisions"] and
            not (item["quality_reasons"] & blockers) else "review"
        ) if config and config.get("niche_terms") else "unassessed"

    ranked = sorted(
        grouped.values(),
        key=lambda item: (
            -item["score"],
            item["known"],
            -len(item["sources"]),
            item["handle"].casefold(),
        ),
    )[: max(1, int(limit))]

    shortlist = []
    for ci, item in enumerate(ranked, start=1):
        cid = f"T{ci:03d}"
        candidate_actions = []
        min_follow = float(((config or {}).get("scoring") or {}).get("min_follow_score", 2))
        if (item["trusted_sources"] and not item["followed"]
                and item["score"] >= min_follow
                and item["quality"] in ("eligible", "unassessed")):
            candidate_actions.append("follow")
        posts = []
        for pi, post in enumerate(
            sorted(item["posts"], key=lambda p: -p["score"])[:2], start=1
        ):
            posts.append({
                "id": f"{cid}-P{pi}",
                "url": post["url"],
                "post_ref": post.get("post_ref"),
                "caption": post["caption"][:500],
                "source": post["source"],
                "actions": post["actions"],
            })
        shortlist.append({
            "id": cid,
            "handle": item["handle"],
            "known": item["known"],
            "known_date": item["known_date"],
            "followed": item["followed"],
            "sources": sorted(item["sources"]),
            "provenance": [item["provenance"][key] for key in sorted(item["provenance"])],
            "actions": candidate_actions,
            "posts": posts,
            "score": round(item["score"], 1),
            "quality": item["quality"],
            "quality_reasons": sorted(item["quality_reasons"]),
            "name": item.get("name", ""),
            "bio": (item.get("bio") or "")[:200],
            "followers": item.get("followers"),
            "relation": item.get("relation"),
            "proof": item.get("proof"),
            "context": (item.get("comment_text") or "")[:200],
            "independent": item.get("independent", 1),
            "lane": _lane(item),
        })
    return shortlist


CHECKPOINT = "tiktok_rows.jsonl"


def _checkpoint(rows_new, path=CHECKPOINT):
    """Persiste filas al instante: una ronda de 1-2 h no puede perderse por un corte."""
    if not rows_new:
        return
    with open(path, "a", encoding="utf-8") as stream:
        for row in rows_new:
            clean = {k: v for k, v in row.items() if k not in ("element", "button", "relation_element")}
            stream.write(json.dumps(clean, ensure_ascii=False, default=str) + chr(10))


def load_checkpoint(path=CHECKPOINT):
    if not os.path.exists(path):
        return []
    rows = []
    # Compatibilidad de lectura únicamente: los checkpoints antiguos de
    # frontier reetiquetaban autores/comentaristas y carecían de provenance.
    # No escribir ni migrar silenciosamente el historial original.
    recognized = {
        "video_search:comment", "video_search:author",
        "seed:profile", "seed:post", "user_search",
        "inbox:new_follower", "author_post",
    }
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            source = row.get("source") if isinstance(row, dict) else None
            if isinstance(source, str) and source.startswith("frontier:"):
                original = source[len("frontier:"):]
                if original in recognized:
                    row["source"] = original
                    row.setdefault("provenance", {
                        "surface": "", "query": "", "source": original,
                        "phase": "frontier",
                    })
            rows.append(row)
    return rows


def _progress(message):
    print(message, file=sys.stderr, flush=True)


def _run_discovery(adapter, config, known, followed, discarded, rows, issues, *, resume=False):
    """Superficies de búsqueda (Usuarios/Vídeos+comentarios). Añade filas compatibles."""
    surfaces = config.get("surfaces", {})
    wanted = [
        n for n in ("inbox", "user_search", "video_search", "seed_comments") if surfaces.get(n)
    ]
    if not wanted:
        return {}
    import datetime
    import tiktok_discovery as disc
    from tiktok_mobile_nav import TikTokNavigator

    nav = TikTokNavigator(adapter)
    today = datetime.date.today().isoformat()
    ctx = {
        "today": today, "seen": disc.load_seen(), "stats": disc.load_stats(),
        "metrics": [], "issues": issues, "discarded": discarded,
    }
    pools = {
        "inbox": (["nuevos seguidores"], "inbox_queries"),
        "seed_comments": (
            list(dict.fromkeys((config.get("seed_accounts") or []) + disc.load_seed_pool())),
            "seed_queries",
        ),
        "user_search": (config.get("actor_queries") or [], "user_search_queries"),
        "video_search": (config.get("video_queries") or [], "video_search_queries"),
    }
    stats = {}
    if resume:
        wanted = []  # las superficies principales ya están en el checkpoint
    for surface in wanted:
        queries, budget_key = pools[surface]
        query_limit = int(config["budgets"].get(budget_key, 2))
        chosen = disc.pick_queries(queries, surface, ctx["stats"], query_limit)
        # Una reserva dentro de la cuota, antes de run_surface; no basta
        # con añadir al final de los 86/144 términos preexistentes.
        if surface in ("user_search", "video_search"):
            import hashtag_query_consumers as hqc
            field = ("lexical_actor_queries" if surface == "user_search"
                     else "lexical_video_queries")
            now = datetime.datetime.now()
            chosen = hqc.reserve_fresh(
                chosen, config.get(field) or [], budget=query_limit,
                tick=now.toordinal() * 4 + now.hour // 6,
            )
        total = {"queries": chosen, "rows": 0, "valid": 0, "new": 0}
        for query in chosen:
            valid, st = disc.run_surface(nav, surface, query, config, ctx)
            _progress(f"[{surface}] {query!r}: filas={st['rows']} válidas={st['valid']} nuevas={st['new']}")
            for item in valid:
                handle = item["handle"]
                rows.append({
                    **item,
                    "niche_hits": max(1, int(item["score"])),
                    "known": handle.casefold() in known,
                    "known_date": known.get(handle.casefold()),
                    "followed": handle.casefold() in followed,
                    "caption": item.get("caption") or item.get("comment_text") or item.get("bio") or "",
                })
            _checkpoint(rows[-len(valid):] if valid else [])
            disc.save_seen(ctx["seen"])
            disc.append_metrics(ctx["metrics"])
            ctx["metrics"].clear()
            for key in ("rows", "valid", "new"):
                total[key] += st[key]
        stats[surface] = total
    _run_frontier(nav, config, ctx, rows, known, followed, stats)
    _run_author_posts(nav, config, ctx, rows, known, followed, stats)
    disc.update_seed_pool(rows, config)
    disc.save_seen(ctx["seen"])
    disc.append_metrics(ctx["metrics"])
    return stats


def build_auto_plan(shortlist, config):
    """Decisiones mecánicas (sin IA), como el auto_plan de Bluesky: follow cuando la
    puntuación ya supera `auto_follow_score_min` y like en posts de cuentas afines.
    Los comentarios nunca son automáticos: los escribe la IA a partir de la vista compacta."""
    scoring = config.get("scoring") or {}
    follow_min = float(scoring.get("auto_follow_score_min", 8))
    like_min = float(scoring.get("auto_like_score_min", 3))
    plan = []
    for candidate in shortlist:
        lane = candidate.get("lane") or "unknown"
        if ("follow" in (candidate.get("actions") or [])
                and candidate["score"] >= follow_min
                and candidate.get("quality") == "eligible"):
            plan.append({
                "kind": "follow", "handle": candidate["handle"], "lane": lane,
                "motivo": f"auto:{candidate['id']}:score={candidate['score']}:" + ",".join(candidate.get("sources") or []),
            })
        if candidate["score"] >= like_min:
            for post in candidate.get("posts") or []:
                if post.get("url") and "like" in (post.get("actions") or []):
                    plan.append({
                        "kind": "like", "handle": candidate["handle"], "lane": lane, "url": post["url"],
                        "post_ref": post.get("post_ref"),
                        "post_created_at": post.get("created_at") or post.get("create_time") or post.get("created_time") or "",
                        "post_resumen": (post.get("caption") or "")[:300],
                        "motivo": f"auto:{post['id']}:{post.get('source') or 'unknown'}",
                    })
                    break
    return plan


def compact_ai_view(state, *, decided=None):
    """Vista mínima para la IA: solo lo que necesita para decidir follow dudosos y comentarios."""
    decided = decided or set()
    auto_handles = {(r["kind"], r["handle"].casefold()) for r in state.get("auto_plan") or []}
    view = []
    for candidate in state.get("shortlist") or []:
        handle_key = candidate["handle"].casefold()
        posts = [
            {"id": p["id"], "caption": (p.get("caption") or "")[:140], "actions": p["actions"]}
            for p in candidate.get("posts") or [] if p.get("url")
        ]
        follow_open = "follow" in candidate["actions"] and ("follow", handle_key) not in auto_handles
        if not follow_open and not posts:
            continue
        view.append({
            "id": candidate["id"], "handle": candidate["handle"], "score": candidate["score"],
            "lane": candidate.get("lane"), "bio": (candidate.get("bio") or candidate.get("name") or "")[:110],
            "ctx": (candidate.get("context") or "")[:90],
            "follow": follow_open, "posts": posts,
        })
    return {"readiness": state.get("discovery"), "candidates": view}


def _run_author_posts(nav, config, ctx, rows, known, followed, stats):
    """Para los mejores candidatos sin vídeo accionable: abre su perfil y toma su vídeo reciente
    (URL + caption). Así cada persona del shortlist puede recibir follow + like + comentario."""
    import tiktok_discovery as disc
    b = config["budgets"]
    limit = int(b.get("author_posts_max", 0))
    if limit <= 0:
        return
    min_score = float(config["scoring"].get("author_posts_min_score", 5))
    have_url = {r["handle"].casefold() for r in rows if r.get("url")}
    ranked = sorted(
        {r["handle"].casefold(): r for r in rows
         if r.get("score", 0) >= min_score and r["handle"].casefold() not in have_url
         and r.get("relation") not in ("following", "friends")}.values(),
        key=lambda r: -r["score"],
    )[:limit]
    out = stats.setdefault("author_posts", {"queries": [], "rows": 0, "valid": 0, "new": 0})
    for row in ranked:
        valid, st = disc.run_surface(nav, "author_posts", row["handle"], config, ctx)
        out["queries"].append(row["handle"])
        for item in valid:
            rows.append({
                **item, "niche_hits": max(1, int(item["score"])),
                "ctx": f"author_posts:{row['handle']}",
                "known": item["handle"].casefold() in known,
                "known_date": known.get(item["handle"].casefold()),
                "followed": item["handle"].casefold() in followed,
                "caption": item.get("caption") or "",
            })
        for key in ("rows", "valid", "new"):
            out[key] += st[key]


def _run_frontier(nav, config, ctx, rows, known, followed, stats):
    """Frontier (ola 2): los mejores perfiles NUEVOS de esta ronda se tratan como semillas:
    sus vídeos recientes -> sus comentaristas. Solo si aportan handles nuevos se sigue (como Bluesky)."""
    import tiktok_discovery as disc
    b = config["budgets"]
    n = int(b.get("frontier_seeds", 3))
    if n <= 0 or not config.get("surfaces", {}).get("seed_comments"):
        return
    existing_rows = {r["handle"].casefold(): r for r in rows}
    taken = set(existing_rows)
    ranked = sorted(
        [r for r in rows if r.get("score", 0) >= float(config["scoring"].get("frontier_min_score", 7))
         and (r.get("followers") or 0) >= int(config["scoring"].get("frontier_min_followers", 300))
         and r["source"] != "seed:profile"],
        key=lambda r: -r["score"],
    )
    seeds = []
    for row in ranked:
        key = row["handle"].casefold()
        if key not in {s.casefold() for s in seeds}:
            seeds.append(row["handle"])
        if len(seeds) >= n:
            break
    stats_out = stats.setdefault("frontier", {"queries": seeds, "rows": 0, "valid": 0, "new": 0})
    for handle in seeds:
        valid, st = disc.run_surface(nav, "seed_comments", handle, config, ctx)
        new_rows = 0
        for item in valid:
            key = item["handle"].casefold()
            raw_origin = item.get("provenance")
            origin = ({**raw_origin, "phase": "frontier"}
                      if isinstance(raw_origin, dict)
                      and raw_origin.get("source") == item.get("source") else None)
            if key in taken:
                # Evitar perder una segunda semilla sin duplicar ni aumentar
                # el score, los posts o los follows del candidato ya conocido.
                if origin is not None:
                    other = existing_rows[key].setdefault("extra_provenance", [])
                    if origin not in other:
                        other.append(origin)
                continue
            taken.add(key)
            new_rows += 1
            candidate = {
                **item,
                # El rol no cambia al entrar por frontier: sigue siendo
                # comentarista del vídeo ajeno, no autor de esa caption.
                "provenance": origin,
                "niche_hits": max(1, int(item["score"])),
                "known": key in known,
                "known_date": known.get(key),
                "followed": key in followed,
                "caption": item.get("caption") or item.get("comment_text") or item.get("bio") or "",
            }
            rows.append(candidate)
            existing_rows[key] = candidate
        for key in ("rows", "valid", "new"):
            stats_out[key] += st[key]
        if new_rows < 2:      # rama poco productiva: no se sigue profundizando
            break


def collect(adapter, config, *, resume=False):
    known = {
        str(handle).casefold(): date
        for handle, date in sc.known_accounts(REGISTRO_CSV).items()
    }
    followed = _followed_handles(REGISTRO_CSV)
    discarded = {
        str(handle).casefold()
        for handle in sc.discarded_handles(REGISTRO_CSV)
    }
    rows = []
    issues = []
    attempted = 0
    max_total = max(1, int(config["budgets"]["max_posts_total"]))
    per_surface = max(1, int(config["budgets"]["posts_per_surface"]))

    adapter.verify_active_account(config.get("account") or MY_HANDLE)

    if resume:
        rows.extend(load_checkpoint())
    elif os.path.exists(CHECKPOINT):
        os.replace(CHECKPOINT, CHECKPOINT + ".prev")
    discovery_stats = _run_discovery(
        adapter, config, known, followed, discarded, rows, issues, resume=resume
    )

    surfaces = [
        name for name in ("for_you", "following")
        if config.get("surfaces", {}).get(name)
    ]

    for surface in surfaces:
        if attempted >= max_total:
            break
        opened = False
        for attempt in range(2):  # un banner in-app puede desviar el tap: reintento de lectura
            try:
                adapter.open_surface(surface)
                opened = True
                break
            except TikTokTargetNotFound as exc:
                issues.append(f"{surface}: abrir superficie intento {attempt + 1}: {exc}")
                try:
                    from tiktok_mobile_nav import TikTokNavigator
                    TikTokNavigator(adapter).return_to_feed()
                except Exception:  # noqa: BLE001
                    pass
        if not opened:
            continue
        for index in range(per_surface):
            if attempted >= max_total:
                break
            attempted += 1
            try:
                snapshot = adapter.current_post_snapshot(source=surface)
                if _needs_handle(snapshot, config):
                    snapshot["handle"] = adapter.resolve_author_handle()
                candidate = _candidate_from_snapshot(
                    snapshot, config=config, known=known, followed=followed, discarded=discarded
                )
                if candidate is not None:
                    # Copiar enlace solo para candidatos ya filtrados, no para todo el feed.
                    candidate["url"] = adapter.copy_current_post_url()
                    rows.append(candidate)
            except (TikTokMobileChallenge, MobileCliError):
                raise
            except Exception as exc:
                issues.append(f"{surface}[{index}]: {type(exc).__name__}: {exc}")
            if index < per_surface - 1 and attempted < max_total:
                adapter.swipe_next()

    return {
        "mode": "supervised_native",
        "account_verified": True,
        "surfaces": surfaces,
        "fetched_posts": attempted,
        "accepted_posts": len(rows),
        "discovery": discovery_stats,
        "issues": issues,
        "shortlist": (shortlist := _compact_shortlist(
            rows, limit=config["budgets"]["shortlist"], config=config
        )),
        "auto_plan": build_auto_plan(shortlist, config),
        "decision_contract": {
            "follow": {"candidate": "Txxx"},
            "like": {"post": "Txxx-Px"},
            "comment": {"post": "Txxx-Px", "text": "comentario"},
        },
    }


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--live-read",
        action="store_true",
        help="confirmación explícita de que se abrirá TikTok para lectura limitada",
    )
    parser.add_argument("--device", default=os.getenv("ANDROID_DEVICE_ID"))
    parser.add_argument("--out", help="escribe el estado JSON completo en este fichero")
    parser.add_argument("--resume", action="store_true", help="reutiliza filas ya recogidas en tiktok_rows.jsonl")
    args = parser.parse_args(argv)
    if not args.live_read:
        print("TikTok scan móvil: falta --live-read; no se abre la app.", file=sys.stderr)
        return 2

    config = _load_config()
    try:
        with mobile_session_lock():
            client = ensure_server(device_id=args.device)
            adapter = TikTokMobileAdapter(client, args.device)
            state = collect(adapter, config, resume=args.resume)
    except (TikTokMobileChallenge, TikTokWrongAccount, MobileCliError) as exc:
        print(f"PARADA TIKTOK: {exc}", file=sys.stderr)
        return 5

    if args.out:
        with open(args.out, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
    if args.json and not args.out:
        json.dump(state, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for candidate in state["shortlist"]:
            print(
                f"{candidate['id']} @{candidate['handle']} "
                f"score={candidate['score']} actions={candidate['actions']}"
            )
            for post in candidate["posts"]:
                print(
                    f"  {post['id']} actions={post['actions']} | "
                    f"{post['caption'][:160]}"
                )
        if state["issues"]:
            print("Incidencias:")
            for issue in state["issues"]:
                print(f"- {issue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
