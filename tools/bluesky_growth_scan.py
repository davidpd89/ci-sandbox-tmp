"""Motor amplio de descubrimiento y crecimiento para Bluesky.

No ejecuta escrituras. Explora varias superficies de ATProto, expande el grafo desde
posts/perfiles prometedores, puntúa mecánicamente y devuelve un shortlist compacto.
La IA decide únicamente sobre ese shortlist; bluesky_build_plan.py reconstruye luego
el plan ejecutable sin repetir URLs/handles en el contexto.

Uso:
    python tools/bluesky_growth_scan.py --json
    python tools/bluesky_growth_scan.py --json --no-metrics
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
import uuid
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import bluesky_interact as b
import growth_common as gc
import scan_common as sc
import growth_policy as gp
import bluesky_jetstream_collect as js_cache
import bluesky_taste_collect as taste_cache

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
CONFIG_PATH = os.path.join(ROOT, "growth_config.json")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICS_CSV = os.path.join(ROOT, "discovery_metrics.csv")
SEEN_CSV = os.path.join(ROOT, "growth_seen.csv")

SOURCE_WEIGHTS = {
    "notification": 3.2,
    "notification_unread": 1.4,
    "activity_subscription": 3.6,
    "bookmark": 3.8,
    "own_follower": 3.4,
    "own_following": 1.5,
    "own_post_reply": 4.2,
    "own_post_liker": 3.0,
    "own_post_reposter": 3.2,
    "own_post_quote": 3.8,
    "thread_commenter": 3.5,
    "quote": 3.0,
    "reposter": 2.2,
    "liker": 1.7,
    "similar_account": 2.0,
    "suggested_account": 2.3,
    "suggested_discover": 2.8,
    "suggested_explore": 2.8,
    "suggested_see_more": 2.5,
    "suggested_starter_pack": 2.7,
    "follower_neighbor": 1.7,
    "following_neighbor": 1.9,
    "starter_pack": 2.1,
    "starter_pack_search": 2.5,
    "joined_starter_pack": 2.2,
    "known_follower": 1.6,
    "curated_list": 2.0,
    "actor_feed": 1.8,
    "saved_feed": 2.4,
    "own_like": 2.3,
    "valued_history": 3.3,
    "reply_search": 2.8,
    "jetstream_cache": 2.2,
    "jetstream_author": 2.8,
    "taste_like": 3.4,
    "popular_feed": 1.7,
    "trending_topic": 1.4,
    "actor_search": 2.0,
    "post_search": 2.0,
    "tag_search": 1.8,
    "custom_feed": 1.8,
    "timeline": 1.2,
    "domain": 3.0,
    "dynamic_tag": 2.1,
    "pool": 2.6,
}

DIVERSITY_SOURCES = (
    "notification",
    "activity_subscription",
    "bookmark",
    "own_post_reply",
    "own_post_liker",
    "own_post_reposter",
    "own_post_quote",
    "own_follower",
    "thread_commenter",
    "liker",
    "reposter",
    "quote",
    "reply_search",
    "post_search",
    "actor_search",
    "starter_pack_search",
    "starter_pack",
    "joined_starter_pack",
    "similar_account",
    "suggested_account",
    "suggested_discover",
    "suggested_explore",
    "suggested_see_more",
    "suggested_starter_pack",
    "follower_neighbor",
    "following_neighbor",
    "saved_feed",
    "own_like",
    "valued_history",
    "jetstream_cache",
    "jetstream_author",
    "taste_like",
    "curated_list",
    "actor_feed",
    "dynamic_tag",
    "pool",
)
NICHE_TERMS = (
    "leer", "lectura", "libro", "libros", "novela", "novelas", "lector",
    "lectora", "escritor", "escritora", "autor", "autora", "fantasia",
    "fantasy", "romantasy", "ciencia ficcion", "terror", "literatura",
    "literario", "literaria", "reseña", "resena", "biblioteca", "libreria",
    "booksky", "book", "books", "reader", "writer", "writing",
    "worldbuilding", "manuscrito", "borrador", "editorial",
    "club de lectura", "ficcion", "juvenil",
    # 05/10: ampliado con el vocabulario de GPT y los nichos adyacentes: con 38 terminos, un lector de relatos, poesia, comic o rol que no escribia "libro"
    # ni "novela" en su bio/posts no contaba como afin (la regla de nicho del like exige >=1 coincidencia). Sin palabras ambiguas (rol, magia, dragon).
    "reseñas", "tbr", "saga", "relato", "relatos", "cuento", "cuentos", "poesia", "poema", "poemas", "poeta", "poetisa", "comic", "comics", "manga",
    "novela grafica", "juegos de rol", "rol de mesa", "wip", "leyendo", "leido", "lecturas", "bibliofilo", "bibliofila", "booktok", "bookstagram", "bookish",
    "ebook", "audiolibro", "kindle", "feria del libro", "distopia", "alta fantasia", "novelista", "traductor", "traductora", "editora", "bestseller",
    "tolkien", "sanderson", "mitologia", "escribo", "escribiendo", "escribir", "narrativa", "ilustracion fantastica", "cuentista", "guionista",
)
SPAM_TERMS = (
    "follow back", "followback", "sigueme y te sigo", "sígueme y te sigo",
    "crypto", "casino", "betting", "giveaway", "airdrop", "nft",
    "overlay", "streamer graphics", "logo design", "commission open",
    "dm for promo", "promociono tu cuenta",
)
SELF_PROMO_HINTS = (
    "compra mi", "mi libro ya", "ya disponible", "amazon", "preventa",
    "pre-order", "buy my", "link en bio",
)


def _norm(value):
    value = " ".join(str(value or "").casefold().split())
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _term_matches(value, term):
    normalized = _norm(term)
    if not value or not normalized:
        return False
    if " " in normalized or not normalized.replace("_", "").isalnum():
        return normalized in value
    tokens = set(re.findall("[a-z0-9_]+", value))
    return normalized in tokens


def _hits(text, terms=NICHE_TERMS):
    value = _norm(text)
    return sum(1 for term in terms if _term_matches(value, term))


def _spammy(text):
    value = _norm(text)
    return any(_norm(term) in value for term in SPAM_TERMS)


def _self_promo(text):
    value = _norm(text)
    return any(_norm(term) in value for term in SELF_PROMO_HINTS)

def _load_seen(path, *, today, days=7):
    """Última exposición de handles/posts al shortlist para evitar Groundhog Day."""
    handles = {}
    posts = {}
    cutoff = today - datetime.timedelta(days=max(0, int(days)))
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return handles, posts
    import csv
    with open(path, encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"fecha", "handle", "post_uri"}
        if not required.issubset(set(reader.fieldnames or ())):
            return handles, posts
        for row in reader:
            try:
                date = datetime.date.fromisoformat((row.get("fecha") or "").strip())
            except ValueError:
                continue
            if date < cutoff:
                continue
            handle = (row.get("handle") or "").strip().lstrip("@").casefold()
            uri = (row.get("post_uri") or "").strip()
            if handle and (handle not in handles or date > handles[handle]):
                handles[handle] = date
            if uri and (uri not in posts or date > posts[uri]):
                posts[uri] = date
    return handles, posts


def _append_seen(path, *, date, run_id, shortlist):
    import csv
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        if not exists:
            writer.writerow(["fecha", "run_id", "handle", "post_uri", "lane"])
        for item in shortlist:
            posts = item.get("posts") or []
            if not posts:
                writer.writerow([
                    date, run_id, item.get("handle") or "", "",
                    item.get("lane") or "",
                ])
                continue
            for post in posts:
                writer.writerow([
                    date, run_id, item.get("handle") or "",
                    post.get("uri") or "", item.get("lane") or "",
                ])


def _days_since(value, today):
    if not value:
        return None
    if isinstance(value, datetime.date):
        date = value
    else:
        try:
            date = datetime.date.fromisoformat(str(value)[:10])
        except ValueError:
            return None
    return max(0, (today - date).days)



def _post_url(post):
    author = (post or {}).get("author") or {}
    uri = (post or {}).get("uri")
    handle = author.get("handle")
    if not uri or not handle:
        return None
    rkey = uri.rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def _created_at(post):
    record = (post or {}).get("record") or {}
    return record.get("createdAt") or (post or {}).get("indexedAt") or ""


SPANISH_FUNCTION_WORDS = frozenset(
    "el la los las un una de del que y en es por con para se su sus lo al mas muy pero como mi tu me te nos ya hay fue son ser ha han he sin sobre entre cuando todo "
    "todos esta este ese eso hoy aqui asi bien estoy tengo quiero leyendo libro novela".split()
)


def _spanish_text(text):
    words = [_norm(w) for w in re.findall(r"[a-záéíóúüñ]+", str(text or "").casefold())]
    if len(words) < 3:
        return None          # demasiado corto para decidir
    hits = sum(1 for w in words if w in SPANISH_FUNCTION_WORDS)
    return hits >= 2 and hits / len(words) >= 0.15


def _spanish_post(post):
    """True/False/None (no se sabe). La etiqueta de idioma del autor manda; sin ella, heuristica de palabras funcionales. 05/10: el 51 % de los likes del plan
    automatico no tenia ningun termino del nicho en el post y salian posts en ingles, portugues o japones de cuentas con la bio 'afin'."""
    langs = post.get("langs") or []
    if langs:
        return any(lang == "es" or lang.startswith("es-") for lang in langs)
    return _spanish_text(post.get("text"))


def _spanish_account(c, item):
    """Cuenta en espanol: su bio lo parece o la mayoria de sus posts verificados lo son (None sin datos)."""
    bio = (item.get("profile") or {}).get("description") or ""
    votes = [_spanish_post(c.posts[uri]) for uri in item.get("posts", ()) if uri in c.posts]
    votes = [v for v in votes if v is not None]
    if votes:
        return sum(1 for v in votes if v) / len(votes) >= 0.5
    verdict = _spanish_text(bio)
    return verdict


def _note_source(item, source):
    """Orden de llegada de las fuentes de un candidato: la primera es su fuente first-touch (el `set` de fuentes pierde ese orden)."""
    order = item.setdefault("source_order", [])
    if source not in order:
        order.append(source)


def _load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("version") != 1:
        raise RuntimeError("growth_config.json: versión no soportada")
    if path == CONFIG_PATH:   # la rampa de volumen (05/10) sube presupuestos y baja umbrales mecanicos por etapas; etapa 0 = sin cambios
        try:
            import volume_ramp
            data = volume_ramp.overlay(data)
        except Exception as exc:
            print(f"AVISO: no se aplico la rampa de volumen ({type(exc).__name__}: {exc}); se usa growth_config.json tal cual")
    return data


class ReviewReserveReached(gc.ReadBudgetExceeded):
    """Discovery debe ceder paso al vetting antes de agotar todo el presupuesto."""


class Collector:
    def __init__(self, config, *, write_metrics=True, today=None, run_id=None):
        self.config = config
        self.today = today or datetime.date.today()
        self.run_id = run_id or (
            self.today.isoformat() + "-" + uuid.uuid4().hex[:8]
        )
        self.write_metrics = write_metrics
        self.budget = gc.ReadBudget(config["budgets"]["max_read_requests"])
        self.known = {
            h.casefold(): date
            for h, date in sc.known_accounts(REGISTRO_CSV).items()
        }
        self.discarded = {
            h.casefold() for h in sc.discarded_handles(REGISTRO_CSV)
        }
        self.query_stats = gc.load_discovery_metrics(
            METRICS_CSV, days=30, today=self.today
        )
        seen_days = int(config.get("shortlist", {}).get("seen_window_days", 7))
        self.seen_handles, self.seen_posts = _load_seen(
            SEEN_CSV, today=self.today, days=seen_days
        )
        self.candidates = {}
        self.posts = {}
        self.source_stats = defaultdict(
            lambda: {"fetched": 0, "accepted": 0, "new_handles": set()}
        )
        self.attempted_surfaces = set()
        self.issues = []
        self.own_handle = None
        self.own_did = None
        self.own_reply_parents = set()
        self.preference_interests = []
        self.preference_interests_updated_at = None
        self.coliker_counts = defaultdict(int)
        self.protect_review_budget = False

    def mark_attempted(self, surface):
        self.attempted_surfaces.add(str(surface))

    def call(self, surface, fn, *args, **kwargs):
        self.mark_attempted(surface)
        reserve = int(self.config["budgets"].get("profile_review_reserve", 0))
        review_surface = surface in {"profile_batch", "author_feed"}
        if (
            self.protect_review_budget
            and not review_surface
            and not self.budget.can_spend(1, reserve=reserve)
        ):
            raise ReviewReserveReached(
                f"reserva de revisión alcanzada: quedan "
                f"{self.budget.remaining} lecturas; {reserve} protegidas"
            )
        self.budget.take(surface)
        return fn(*args, **kwargs)

    def metric(self, surface, key, fetched, accepted, new_handles):
        row = self.source_stats[(surface, key)]
        row["fetched"] += int(fetched)
        row["accepted"] += int(accepted)
        row["new_handles"].update(new_handles)
        if self.write_metrics:
            gc.append_discovery_metric(
                METRICS_CSV,
                date=self.today.isoformat(),
                run_id=self.run_id,
                surface=surface,
                key=key,
                fetched=fetched,
                accepted=accepted,
                new_handles=len(set(new_handles)),
            )

    def _apply_viewer_state(self, item, profile):
        viewer = profile.get("viewer") if isinstance(profile, dict) else None
        if not isinstance(viewer, dict):
            return
        item["following"] = bool(viewer.get("following"))
        item["followed_by"] = bool(viewer.get("followedBy"))
        item["activity_subscription"] = bool(viewer.get("activitySubscription"))
        if viewer.get("muted") or viewer.get("mutedByList"):
            item["excluded_reason"] = "muted"
        elif viewer.get("blockedBy"):
            item["excluded_reason"] = "blocked_by"
        elif viewer.get("blocking") or viewer.get("blockingByList"):
            item["excluded_reason"] = "blocking"
        known = viewer.get("knownFollowers")
        if isinstance(known, dict):
            item["known_followers_count"] = max(
                int(item.get("known_followers_count") or 0),
                int(known.get("count") or 0),
            )

    def _candidate(self, handle):
        handle = (handle or "").strip().lstrip("@").casefold()
        if not handle or handle == self.own_handle or handle in self.discarded:
            return None
        if handle not in self.candidates:
            maximum = int(self.config["budgets"]["max_candidates"])
            if len(self.candidates) >= maximum:
                return None
        item = self.candidates.setdefault(handle, {
            "handle": handle,
            "sources": set(),
            "source_keys": set(),
            "profile": None,
            "posts": set(),
            "known_date": self.known.get(handle),
            "seen_date": self.seen_handles.get(handle),
            "last_notification_at": None,
            "notification_unread": False,
            "following": None,
            "followed_by": False,
            "activity_subscription": False,
            "known_followers_count": 0,
            "excluded_reason": None,
            "score": 0.0,
            "signals": [],
            "source_order": [],
        })
        return item

    def add_actor(self, actor, source, *, key=""):
        if not isinstance(actor, dict):
            return False
        handle = actor.get("handle")
        item = self._candidate(handle)
        if item is None:
            return False
        description = actor.get("description") or ""
        if sc.is_political(description) or _spammy(description):
            return False
        item["sources"].add(source)
        _note_source(item, source)
        if key:
            item["source_keys"].add(f"{source}:{key}")
        if actor.get("did") or actor.get("description") is not None:
            current = item.get("profile") or {}
            merged = dict(current)
            for field in (
                "did", "handle", "displayName", "description", "followersCount",
                "followsCount", "postsCount", "viewer", "createdAt",
                "joinedViaStarterPack",
            ):
                if actor.get(field) is not None:
                    merged[field] = actor.get(field)
            item["profile"] = merged
            self._apply_viewer_state(item, merged)
        return True

    def add_post(self, post, source, *, key=""):
        if not isinstance(post, dict):
            return False
        author = post.get("author") or {}
        text = ((post.get("record") or {}).get("text") or "").strip()
        handle = author.get("handle")
        uri = post.get("uri")
        url = _post_url(post)
        if not handle or not uri or not url or not text:
            return False
        if handle.casefold() == self.own_handle or handle.casefold() in self.discarded:
            return False
        if sc.is_political(text) or _spammy(text):
            return False
        item = self._candidate(handle)
        if item is None:
            return False
        self.add_actor(author, source, key=key)
        item["sources"].add(source)
        _note_source(item, source)
        if key:
            item["source_keys"].add(f"{source}:{key}")
        item["posts"].add(uri)
        existing = self.posts.get(uri)
        if existing is None:
            self.posts[uri] = {
                "uri": uri,
                "url": url,
                "handle": handle.casefold(),
                "text": text,
                "likes": int(post.get("likeCount") or 0),
                "reposts": int(post.get("repostCount") or 0),
                "replies": int(post.get("replyCount") or 0),
                "quotes": int(post.get("quoteCount") or 0),
                "bookmarks": int(post.get("bookmarkCount") or 0),
                "created_at": _created_at(post),
                "is_reply": bool((post.get("record") or {}).get("reply")),
                "langs": [str(x).casefold() for x in ((post.get("record") or {}).get("langs") or []) if isinstance(x, str)],
                "tags": _structured_tags(post),
                "reply_disabled": bool(
                    (post.get("viewer") or {}).get("replyDisabled")
                ) if isinstance(post.get("viewer"), dict) else None,
                "embedding_disabled": bool(
                    (post.get("viewer") or {}).get("embeddingDisabled")
                ) if isinstance(post.get("viewer"), dict) else None,
                "liked": bool(
                    (post.get("viewer") or {}).get("like")
                ) if isinstance(post.get("viewer"), dict) else False,
                "reposted": bool(
                    (post.get("viewer") or {}).get("repost")
                ) if isinstance(post.get("viewer"), dict) else False,
                "seen_date": self.seen_posts.get(uri),
                "sources": {source},
                "source_keys": {key} if key else set(),
            }
        else:
            existing["sources"].add(source)
            if key:
                existing["source_keys"].add(key)
            viewer = post.get("viewer")
            if isinstance(viewer, dict):
                existing["reply_disabled"] = bool(viewer.get("replyDisabled"))
                existing["embedding_disabled"] = bool(
                    viewer.get("embeddingDisabled")
                )
                existing["liked"] = bool(viewer.get("like"))
                existing["reposted"] = bool(viewer.get("repost"))
            if post.get("bookmarkCount") is not None:
                existing["bookmarks"] = int(post.get("bookmarkCount") or 0)
        return True

    def add_notification_post(self, notification):
        author = notification.get("author") or {}
        handle = author.get("handle")
        record = notification.get("record") or {}
        text = (record.get("text") or "").strip()
        uri = notification.get("uri")
        reason = notification.get("reason") or "unknown"

        def note_state():
            key = (handle or "").strip().lstrip("@").casefold()
            item = self.candidates.get(key)
            if not item:
                return
            indexed = notification.get("indexedAt")
            if isinstance(indexed, str) and (
                not item.get("last_notification_at")
                or indexed > item["last_notification_at"]
            ):
                item["last_notification_at"] = indexed
            if notification.get("isRead") is False:
                item["notification_unread"] = True
                item["sources"].add("notification_unread")

        if reason in ("reply", "mention", "quote") and uri and handle and text:
            pseudo = {
                "uri": uri,
                "author": author,
                "record": record,
                "indexedAt": notification.get("indexedAt"),
            }
            accepted = self.add_post(
                pseudo, "notification", key=reason
            )
            note_state()
            return accepted

        key = reason
        if reason == "starterpack-joined":
            pack = notification.get("starterPack")
            pack = pack if isinstance(pack, dict) else {}
            pack_uri = pack.get("uri")
            if isinstance(pack_uri, str) and pack_uri:
                key = f"{reason}:{pack_uri}"
        accepted = self.add_actor(author, "notification", key=key)
        note_state()
        return accepted

    def coverage(self):
        # Cobertura significa "se intentó la superficie", no "dio resultados".
        # Un día sin commenters sigue siendo una exploración correctamente hecha.
        attempted = set(self.attempted_surfaces)
        required = set(self.config["coverage"]["required_surfaces"])
        optional = set(self.config["coverage"].get("optional_surfaces") or [])
        return {
            "attempted": sorted(attempted),
            "required": sorted(required),
            "missing": sorted(required - attempted),
            "optional": sorted(optional),
            "optional_missing": sorted(optional - attempted),
        }


def _run_source(collector, surface, key, producer, consumer):
    before = set(collector.candidates)
    try:
        items = producer()
    except b.RateLimitExceeded:
        raise
    except gc.ReadBudgetExceeded:
        raise
    except Exception as exc:
        collector.issues.append(f"{surface}:{key}: {type(exc).__name__}: {exc}")
        return []
    items = list(items or [])
    accepted = 0
    for item in items:
        if consumer(item):
            accepted += 1
    new_handles = set(collector.candidates) - before
    collector.metric(surface, key, len(items), accepted, new_handles)
    return items


def _search_content_v2(c, query, limit, *, sort="recent", since=None):
    """Carril de posts originales; replies se descubren por su propio carril."""
    params = {
        "query": query,
        "limit": int(limit),
        "sort": sort,
        "languages": ["es"],
        "excludeReplies": "true",
    }
    if since:
        params["since"] = since
    try:
        return (
            c.call(
                "post_search",
                b._get,
                b.AUTH_BASE,
                "app.bsky.feed.searchPostsV2",
                params,
                auth=True,
            ).get("posts", [])
        )
    except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
        raise
    except Exception as exc:
        # searchPostsV2 es nuevo; conservar ruta estable si el AppView concreto
        # todavía no lo sirve o una query no es compatible.
        c.issues.append(
            f"post_search_v2:{query}: {type(exc).__name__}: {exc}; fallback=v1"
        )
        v1_sort = "latest" if sort == "recent" else "top"
        return c.call(
            "post_search",
            b._search_posts,
            query,
            "es",
            int(limit),
            sort=v1_sort,
            since=since,
        )


def _query_selection(collector):
    chosen = []
    per_family = int(collector.config["coverage"]["post_queries_per_family"])
    for family in collector.config["query_families"]:
        name = family["name"]
        queries = [str(q) for q in family["queries"]]
        ranked = gc.rank_keys(
            queries,
            collector.query_stats,
            surface=f"post_search:{name}",
            today=collector.today,
        )
        for query in ranked[:per_family]:
            chosen.append((name, query))
    return chosen


def _actor_query_selection(collector):
    queries = [str(q) for q in collector.config["actor_queries"]]
    ranked = gc.rank_keys(
        queries,
        collector.query_stats,
        surface="actor_search",
        today=collector.today,
    )
    return ranked[: int(collector.config["coverage"]["actor_queries_total"])]


def _reply_query_selection(collector):
    total = int(collector.config["coverage"]["replies_only_queries_total"])
    ranked = []
    for family in collector.config["query_families"]:
        name = family["name"]
        queries = gc.rank_keys(
            [str(q) for q in family["queries"]],
            collector.query_stats,
            surface=f"reply_search:{name}",
            today=collector.today,
        )
        if queries:
            ranked.append((name, queries[0]))
    return ranked[:total]


def _starter_pack_query_selection(collector):
    queries = [str(q) for q in collector.config.get("starter_pack_queries") or []]
    ranked = gc.rank_keys(
        queries,
        collector.query_stats,
        surface="starter_pack_search",
        today=collector.today,
    )
    return ranked[: int(collector.config["budgets"]["starter_pack_queries_per_round"])]


def _feed_query_selection(collector):
    queries = [str(q) for q in collector.config.get("feed_queries") or []]
    ranked = gc.rank_keys(
        queries,
        collector.query_stats,
        surface="popular_feed_search",
        today=collector.today,
    )
    return ranked[: int(collector.config["coverage"]["popular_feed_queries_per_round"])]


def _hydrate_post_uris(c, uris, source, key):
    """Hidratar posts en lotes de 25 para no convertir cache/listas en N llamadas."""
    unique = list(dict.fromkeys(uri for uri in uris if isinstance(uri, str) and uri.startswith("at://")))
    accepted = 0
    fetched = 0
    before = set(c.candidates)
    for start in range(0, len(unique), 25):
        chunk = unique[start:start + 25]
        data = c.call(
            source,
            b._get,
            b.AUTH_BASE,
            "app.bsky.feed.getPosts",
            {"uris": chunk},
            auth=True,
        )
        posts = list(data.get("posts") or [])
        fetched += len(posts)
        for post in posts:
            if c.add_post(post, source, key=key):
                accepted += 1
    c.metric(source, key, fetched, accepted, set(c.candidates) - before)
    return accepted


def _consume_jetstream_cache(c):
    jet = c.config.get("jetstream") or {}
    raw_path = jet.get("db_path")
    if not raw_path:
        return
    repo_root = os.path.dirname(ROOT)
    db_path = os.path.join(repo_root, raw_path)
    rows = js_cache.read_recent_matches(
        db_path,
        limit=int(c.config["budgets"]["jetstream_cache_posts"]),
    )
    if rows:
        # Los registros Jetstream no traen el handle hidratado. getPosts resuelve
        # autores/stats/viewer en 25 URIs por llamada.
        _hydrate_post_uris(
            c,
            [row["uri"] for row in rows],
            "jetstream_cache",
            "recent_matches",
        )

    # Una persona que aparece varias veces hablando del nicho durante horas/días
    # es una señal más fuerte que un hit aislado. Agregar localmente cuesta cero IA.
    authors = js_cache.read_active_authors(
        db_path,
        limit=int(c.config["budgets"]["jetstream_active_authors"]),
        min_posts=int(c.config["budgets"]["jetstream_min_author_posts"]),
        max_age_hours=int(c.config["budgets"]["jetstream_retention_hours"]),
    )
    dids = [row["did"] for row in authors]
    for start in range(0, len(dids), 25):
        chunk = dids[start:start + 25]
        if not chunk:
            continue
        try:
            data = c.call(
                "jetstream_cache",
                b._get,
                b.AUTH_BASE,
                "app.bsky.actor.getProfiles",
                {"actors": chunk},
                auth=True,
            )
        except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
            raise
        except Exception as exc:
            c.issues.append(
                f"jetstream_authors: {type(exc).__name__}: {exc}"
            )
            continue
        counts = {row["did"]: row["posts"] for row in authors}
        for profile in data.get("profiles") or []:
            did = profile.get("did")
            count = int(counts.get(did) or 0)
            if c.add_actor(profile, "jetstream_author", key=f"posts={count}"):
                item = c.candidates.get((profile.get("handle") or "").casefold())
                if item is not None and count >= 2:
                    item["signals"].append(
                        f"{count} posts afines recientes en escucha Jetstream"
                    )


def _consume_taste_cache(c):
    """Posts que están gustando a curadores/co-likers seleccionados previamente."""
    jet = c.config.get("jetstream") or {}
    raw_path = jet.get("db_path")
    if not raw_path:
        return
    db_path = os.path.join(os.path.dirname(ROOT), raw_path)
    rows = taste_cache.read_candidate_posts(
        db_path,
        limit=int(c.config["budgets"]["taste_cache_posts"]),
        min_paths=int(c.config["budgets"]["taste_min_paths"]),
        max_age_hours=int(c.config["budgets"]["taste_retention_hours"]),
    )
    if not rows:
        return

    _hydrate_post_uris(
        c,
        [row["uri"] for row in rows],
        "taste_like",
        "targeted_colikers",
    )
    by_uri = {row["uri"]: row for row in rows}
    for uri, row in by_uri.items():
        post = c.posts.get(uri)
        if not post:
            continue
        paths = int(row.get("paths") or 0)
        post["taste_paths"] = paths
        item = c.candidates.get(post["handle"])
        if item is not None and paths:
            item["signals"].append(
                f"{paths} curadores afines dieron like recientemente"
            )


def _discover_own_preferences(c):
    """Usar intereses y feeds/listas guardados: equivalente a abrir menús propios."""
    try:
        data = c.call(
            "saved_feeds",
            b._get,
            b.AUTH_BASE,
            "app.bsky.actor.getPreferences",
            {},
            auth=True,
        )
    except b.RateLimitExceeded:
        raise
    except gc.ReadBudgetExceeded:
        raise
    except Exception as exc:
        c.issues.append(f"saved_feeds:preferences: {type(exc).__name__}: {exc}")
        return

    interests = []
    saved = []
    for pref in data.get("preferences") or []:
        if not isinstance(pref, dict):
            continue
        ptype = str(pref.get("$type") or "")
        if ptype.endswith("#interestsPref"):
            interests.extend(str(x) for x in pref.get("tags") or [])
            c.preference_interests_updated_at = pref.get("updatedAt")
        elif ptype.endswith("#savedFeedsPrefV2"):
            saved.extend(pref.get("items") or [])
        elif ptype.endswith("#savedFeedsPref"):
            for uri in pref.get("saved") or []:
                kind = (
                    "list"
                    if isinstance(uri, str) and "/app.bsky.graph.list/" in uri
                    else "feed"
                )
                saved.append({
                    "type": kind,
                    "value": uri,
                    "pinned": uri in (pref.get("pinned") or []),
                })

    c.preference_interests = list(dict.fromkeys(interests))

    # Los intereses declarados por la propia cuenta pueden abrir queries nuevas,
    # pero con límite pequeño para que no desplacen el banco editorial.
    qlimit = int(c.config["coverage"]["preference_interest_queries"])
    for query in list(dict.fromkeys(interests))[:qlimit]:
        _run_source(
            c,
            "preference_interest",
            query,
            lambda q=query: c.call(
                "preference_interest",
                b._search_posts,
                q,
                "es",
                25,
                sort="latest",
            ),
            lambda post, q=query: c.add_post(post, "preference_interest", key=q),
        )

    limit = int(c.config["budgets"]["saved_feed_posts"])
    for item in saved[:12]:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        value = item.get("value")
        if not isinstance(value, str) or not value.startswith("at://"):
            continue
        if kind == "feed":
            _run_source(
                c,
                "saved_feeds",
                value,
                lambda uri=value: (
                    c.call(
                        "saved_feeds",
                        b._get,
                        b.AUTH_BASE,
                        "app.bsky.feed.getFeed",
                        {"feed": uri, "limit": limit},
                        auth=True,
                    ).get("feed", [])
                ),
                lambda row, uri=value: c.add_post(
                    (row or {}).get("post") or {},
                    "saved_feed",
                    key=uri,
                ),
            )
        elif kind == "list":
            _run_source(
                c,
                "saved_feeds",
                value,
                lambda uri=value: (
                    c.call(
                        "saved_feeds",
                        b._get,
                        b.PUBLIC_BASE,
                        "app.bsky.feed.getListFeed",
                        {"list": uri, "limit": limit},
                        auth=False,
                    ).get("feed", [])
                ),
                lambda row, uri=value: c.add_post(
                    (row or {}).get("post") or {},
                    "saved_feed",
                    key=uri,
                ),
            )


def _load_relationship_exclusions(c):
    """Bloqueos/mutes manuales prevalecen sobre cualquier discovery posterior."""
    c.mark_attempted("relationship_exclusions")
    page_cap = int(c.config["budgets"]["relationship_exclusion_pages"])
    for path, field in (
        ("app.bsky.graph.getBlocks", "blocks"),
        ("app.bsky.graph.getMutes", "mutes"),
    ):
        cursor = None
        for _ in range(page_cap):
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            try:
                data = c.call(
                    "relationship_exclusions",
                    b._get,
                    b.AUTH_BASE,
                    path,
                    params,
                    auth=True,
                )
            except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
                raise
            except Exception as exc:
                c.issues.append(
                    f"relationship_exclusions:{path}: "
                    f"{type(exc).__name__}: {exc}"
                )
                break
            for actor in data.get(field) or []:
                handle = (actor.get("handle") or "").strip().lstrip("@").casefold()
                if handle:
                    c.discarded.add(handle)
                    c.candidates.pop(handle, None)
            cursor = data.get("cursor")
            if not cursor:
                break


def _discover_bookmarks(c):
    """Bookmarks son selección humana explícita: usar posts como semillas fuertes."""
    limit = int(c.config["budgets"]["bookmarks_limit"])
    _run_source(
        c,
        "bookmarks",
        "own",
        lambda: (
            c.call(
                "bookmarks",
                b._get,
                b.AUTH_BASE,
                "app.bsky.bookmark.getBookmarks",
                {"limit": limit},
                auth=True,
            ).get("bookmarks", [])
        ),
        lambda row: c.add_post(
            (row or {}).get("item") or {},
            "bookmark",
            key="own",
        ),
    )


def _discover_activity_subscriptions(c):
    """Cuentas que David eligió explícitamente para recibir actividad."""
    limit = int(c.config["budgets"]["activity_subscriptions_limit"])
    _run_source(
        c,
        "activity_subscriptions",
        "own",
        lambda: (
            c.call(
                "activity_subscriptions",
                b._get,
                b.AUTH_BASE,
                "app.bsky.notification.listActivitySubscriptions",
                {"limit": limit},
                auth=True,
            ).get("subscriptions", [])
        ),
        lambda actor: c.add_actor(
            actor,
            "activity_subscription",
            key="own",
        ),
    )


def _discover_own_network(c):
    """Abrir los menús Seguidores/Siguiendo como semillas de relación."""
    limit = int(c.config["budgets"]["own_network_limit"])

    _run_source(
        c,
        "own_network",
        "followers",
        lambda: (
            c.call(
                "own_network",
                b._get,
                b.AUTH_BASE,
                "app.bsky.graph.getFollowers",
                {"actor": c.own_handle, "limit": limit, "sort": "latest"},
                auth=True,
            ).get("followers", [])
        ),
        lambda actor: c.add_actor(
            actor,
            "own_follower",
            key="followers",
        ),
    )

    _run_source(
        c,
        "own_network",
        "following",
        lambda: (
            c.call(
                "own_network",
                b._get,
                b.AUTH_BASE,
                "app.bsky.graph.getFollows",
                {"actor": c.own_handle, "limit": limit, "sort": "latest"},
                auth=True,
            ).get("follows", [])
        ),
        lambda actor: c.add_actor(
            actor,
            "own_following",
            key="following",
        ),
    )


def _discover_own_post_engagers(c):
    """Revisar quién comenta/reacciona a posts propios recientes.

    Notifications sigue siendo prioridad, pero esta ruta recupera audiencia activa
    aunque la notificación ya no esté en la primera página.
    """
    limit = int(c.config["budgets"]["own_posts_limit"])
    try:
        data = c.call(
            "own_post_engagers",
            b._get,
            b.AUTH_BASE,
            "app.bsky.feed.getAuthorFeed",
            {
                "actor": c.own_handle,
                "limit": limit,
                "filter": "posts_no_replies",
            },
            auth=True,
        )
    except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
        raise
    except Exception as exc:
        c.issues.append(
            f"own_post_engagers:feed: {type(exc).__name__}: {exc}"
        )
        return

    rows = list(data.get("feed") or [])
    seeds = []
    for row in rows:
        post = (row or {}).get("post") or {}
        if not post.get("uri"):
            continue
        seeds.append(post)
    seeds.sort(
        key=lambda post: (
            -(
                int(post.get("replyCount") or 0) * 3
                + int(post.get("quoteCount") or 0) * 3
                + int(post.get("repostCount") or 0) * 2
                + int(post.get("likeCount") or 0)
            ),
            str(post.get("indexedAt") or ""),
        )
    )
    seeds = seeds[: int(c.config["budgets"]["own_engagement_seeds"])]

    for seed in seeds:
        uri = seed["uri"]
        url = _post_url(seed) or uri

        _run_source(
            c,
            "own_post_engagers",
            f"likes:{uri}",
            lambda u=uri: c.call(
                "own_post_engagers",
                b._post_engagers,
                u,
                "likes",
                int(c.config["budgets"]["engager_likes_limit"]),
            ),
            lambda row, seed_url=url: c.add_actor(
                (row or {}).get("actor") or {},
                "own_post_liker",
                key=seed_url,
            ),
        )

        _run_source(
            c,
            "own_post_engagers",
            f"reposts:{uri}",
            lambda u=uri: c.call(
                "own_post_engagers",
                b._post_engagers,
                u,
                "reposts",
                int(c.config["budgets"]["engager_reposts_limit"]),
            ),
            lambda actor, seed_url=url: c.add_actor(
                actor or {},
                "own_post_reposter",
                key=seed_url,
            ),
        )

        _run_source(
            c,
            "own_post_engagers",
            f"quotes:{uri}",
            lambda u=uri: c.call(
                "own_post_engagers",
                b._post_engagers,
                u,
                "quotes",
                int(c.config["budgets"]["engager_quotes_limit"]),
            ),
            lambda quote, seed_url=url: c.add_post(
                quote,
                "own_post_quote",
                key=seed_url,
            ),
        )

        _run_source(
            c,
            "own_post_engagers",
            f"replies:{uri}",
            lambda u=uri: (
                c.call(
                    "own_post_engagers",
                    b._get,
                    b.AUTH_BASE,
                    "app.bsky.feed.searchPostsV2",
                    {
                        "threadRootUri": u,
                        "limit": int(c.config["budgets"]["thread_posts_limit"]),
                        "sort": "recent",
                    },
                    auth=True,
                ).get("posts", [])
            ),
            lambda reply, seed_uri=uri, seed_url=url: (
                reply.get("uri") != seed_uri
                and c.add_post(
                    reply,
                    "own_post_reply",
                    key=seed_url,
                )
            ),
        )


def _preference_headers(c):
    interests = [
        str(tag).strip()
        for tag in c.preference_interests
        if str(tag).strip()
    ]
    topics = ",".join(interests)
    if topics and c.preference_interests_updated_at:
        topics += f";{c.preference_interests_updated_at}"
    headers = {"Accept-Language": "es"}
    if topics:
        headers["x-atproto-bsky-topics"] = topics
    return headers


def _discover_personalized_recommendations(c):
    """Replica los carriles que usa el cliente oficial en Discover/Explore."""
    headers = _preference_headers(c)
    limit = int(c.config["budgets"]["personalized_suggestions_limit"])

    lanes = (
        (
            "suggested_discover",
            "app.bsky.unspecced.getSuggestedUsersForDiscover",
            {},
        ),
        (
            "suggested_explore",
            "app.bsky.unspecced.getSuggestedUsersForExplore",
            {},
        ),
        (
            "suggested_see_more",
            "app.bsky.unspecced.getSuggestedUsersForSeeMore",
            {},
        ),
    )
    for source, path, params in lanes:
        _run_source(
            c,
            source,
            "official",
            lambda p=path, q=params: (
                c.call(
                    source,
                    b._get,
                    b.AUTH_BASE,
                    p,
                    {**q, "limit": limit},
                    auth=True,
                    extra_headers=headers,
                ).get("actors", [])
            ),
            lambda actor, src=source: c.add_actor(
                actor,
                src,
                key="official",
            ),
        )

    # Starter packs personalizados por los mismos intereses que Explore.
    pack_limit = int(c.config["budgets"]["personalized_starter_packs_limit"])
    try:
        data = c.call(
            "suggested_starter_packs",
            b._get,
            b.AUTH_BASE,
            "app.bsky.unspecced.getSuggestedStarterPacks",
            {"limit": pack_limit},
            auth=True,
            extra_headers=headers,
        )
    except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
        raise
    except Exception as exc:
        c.issues.append(
            f"suggested_starter_packs: {type(exc).__name__}: {exc}"
        )
        return

    packs = list(data.get("starterPacks") or [])
    before = set(c.candidates)
    for pack in packs:
        creator = pack.get("creator") if isinstance(pack, dict) else None
        c.add_actor(
            creator or {},
            "suggested_starter_pack",
            key="official",
        )
    c.metric(
        "suggested_starter_packs",
        "official",
        len(packs),
        len(set(c.candidates) - before),
        set(c.candidates) - before,
    )

    expansions = int(c.config["budgets"]["personalized_pack_expansions"])
    item_limit = int(c.config["budgets"]["starter_pack_items"])
    ranked = sorted(
        packs,
        key=lambda pack: (
            -_hits(_menu_label(pack)),
            -int(((pack.get("list") or {}).get("listItemCount") or 0)
                 if isinstance(pack, dict) else 0),
        ),
    )
    for pack in ranked[:expansions]:
        uri = _starter_pack_list_uri(pack)
        if not uri:
            continue
        _run_source(
            c,
            "suggested_starter_packs",
            uri,
            lambda list_uri=uri: (
                c.call(
                    "suggested_starter_packs",
                    b._get,
                    b.PUBLIC_BASE,
                    "app.bsky.graph.getList",
                    {"list": list_uri, "limit": item_limit},
                    auth=False,
                ).get("items", [])
            ),
            lambda row, pack_uri=uri: c.add_actor(
                (row or {}).get("subject") or {},
                "suggested_starter_pack",
                key=pack_uri,
            ),
        )


def _discover_suggested_accounts(c):
    """Usar las sugerencias nativas de Bluesky como una cantera más."""
    limit = int(c.config["budgets"]["suggested_accounts_limit"])
    _run_source(
        c,
        "suggested_accounts",
        "native",
        lambda: (
            c.call(
                "suggested_accounts",
                b._get,
                b.AUTH_BASE,
                "app.bsky.actor.getSuggestions",
                {"limit": limit},
                auth=True,
            ).get("actors", [])
        ),
        lambda actor: c.add_actor(
            actor,
            "suggested_account",
            key="native",
        ),
    )


def _discover_own_likes(c):
    """Aprender de acciones humanas previas sin inferir gustos con IA."""
    limit = int(c.config["budgets"]["own_likes_limit"])
    _run_source(
        c,
        "own_likes",
        c.own_handle,
        lambda: (
            c.call(
                "own_likes",
                b._get,
                b.AUTH_BASE,
                "app.bsky.feed.getActorLikes",
                {"actor": c.own_handle, "limit": limit},
                auth=True,
            ).get("feed", [])
        ),
        lambda row: c.add_post(
            (row or {}).get("post") or {},
            "own_like",
            key="own_history",
        ),
    )


def _record_post_targets(value):
    """Extrae posts externos que una acción propia señaló como valiosos."""
    if not isinstance(value, dict):
        return []

    found = []
    subject = value.get("subject")
    if isinstance(subject, dict):
        uri = subject.get("uri")
        if isinstance(uri, str) and "/app.bsky.feed.post/" in uri:
            found.append(uri)

    reply = value.get("reply")
    if isinstance(reply, dict):
        for key in ("parent", "root"):
            ref = reply.get(key)
            uri = ref.get("uri") if isinstance(ref, dict) else None
            if isinstance(uri, str) and "/app.bsky.feed.post/" in uri:
                found.append(uri)

    embed = value.get("embed")
    if isinstance(embed, dict):
        record = embed.get("record")
        # app.bsky.embed.record
        uri = record.get("uri") if isinstance(record, dict) else None
        if isinstance(uri, str) and "/app.bsky.feed.post/" in uri:
            found.append(uri)
        # app.bsky.embed.recordWithMedia
        nested = record.get("record") if isinstance(record, dict) else None
        uri = nested.get("uri") if isinstance(nested, dict) else None
        if isinstance(uri, str) and "/app.bsky.feed.post/" in uri:
            found.append(uri)

    return list(dict.fromkeys(found))


def _discover_valued_history(c):
    """Persistir el criterio humano: likes/reposts/replies/quotes previos son semillas.

    No depende del CSV histórico, que en filas antiguas puede guardar un resumen en
    vez de una URL. Se leen los records reales del repo propio y se hidratan en lote.
    """
    c.mark_attempted("valued_history")
    if not c.own_did:
        c.issues.append("valued_history: falta DID propio")
        return []

    limit = int(c.config["budgets"]["valued_history_records"])
    targets = []
    for collection in (
        "app.bsky.feed.like",
        "app.bsky.feed.repost",
        "app.bsky.feed.post",
    ):
        try:
            data = c.call(
                "valued_history",
                b._get,
                b.AUTH_BASE,
                "com.atproto.repo.listRecords",
                {
                    "repo": c.own_did,
                    "collection": collection,
                    "limit": min(100, limit),
                    "reverse": True,
                },
                auth=True,
            )
        except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
            raise
        except Exception as exc:
            c.issues.append(
                f"valued_history:{collection}: {type(exc).__name__}: {exc}"
            )
            continue

        for row in data.get("records") or []:
            value = row.get("value") if isinstance(row, dict) else None
            targets.extend(_record_post_targets(value))
            if len(set(targets)) >= limit:
                break
        if len(set(targets)) >= limit:
            break

    targets = list(dict.fromkeys(targets))[:limit]
    if not targets:
        return []

    before = set(c.posts)
    _hydrate_post_uris(
        c,
        targets,
        "valued_history",
        "own_interaction_records",
    )
    return [
        c.posts[uri] for uri in targets
        if uri in c.posts and uri not in before
    ]


def _search_replies_v2(c):
    limit = int(c.config["budgets"]["reply_search_limit"])
    for family, query in _reply_query_selection(c):
        surface = f"reply_search:{family}"
        _run_source(
            c,
            surface,
            query,
            lambda q=query: (
                c.call(
                    "reply_search",
                    b._get,
                    b.AUTH_BASE,
                    "app.bsky.feed.searchPostsV2",
                    {
                        "query": q,
                        "limit": limit,
                        "sort": "recent",
                        "languages": ["es"],
                        "repliesOnly": "true",
                    },
                    auth=True,
                ).get("posts", [])
            ),
            lambda post, fam=family, q=query: c.add_post(
                post,
                "reply_search",
                key=f"{fam}:{q}",
            ),
        )


def _search_starter_packs(c):
    item_limit = int(c.config["budgets"]["starter_pack_items"])
    pack_limit = int(c.config["budgets"]["starter_pack_search_limit"])
    for query in _starter_pack_query_selection(c):
        before = set(c.candidates)
        try:
            data = c.call(
                "starter_pack_search",
                b._get,
                b.PUBLIC_BASE,
                "app.bsky.graph.searchStarterPacksV2",
                {"q": query, "limit": pack_limit},
                auth=False,
            )
        except b.RateLimitExceeded:
            raise
        except gc.ReadBudgetExceeded:
            raise
        except Exception as exc:
            c.issues.append(
                f"starter_pack_search:{query}: {type(exc).__name__}: {exc}"
            )
            continue

        packs = list(data.get("starterPacks") or [])
        accepted = 0
        for pack in packs:
            creator = pack.get("creator") if isinstance(pack, dict) else None
            if c.add_actor(creator or {}, "starter_pack_search", key=query):
                accepted += 1
        c.metric(
            "starter_pack_search",
            query,
            len(packs),
            accepted,
            set(c.candidates) - before,
        )

        # Solo los dos primeros packs por query se expanden a miembros.
        for pack in packs[:2]:
            list_uri = _starter_pack_list_uri(pack)
            if not list_uri:
                continue
            _run_source(
                c,
                "starter_pack_search",
                list_uri,
                lambda uri=list_uri: (
                    c.call(
                        "starter_pack_search",
                        b._get,
                        b.PUBLIC_BASE,
                        "app.bsky.graph.getList",
                        {"list": uri, "limit": item_limit},
                        auth=False,
                    ).get("items", [])
                ),
                lambda row, q=query: c.add_actor(
                    (row or {}).get("subject") or {},
                    "starter_pack_search",
                    key=q,
                ),
            )


def _search_popular_feeds(c):
    """Best-effort: endpoint unspecced, nunca condición de éxito de la ronda."""
    limit = int(c.config["budgets"]["custom_feed_posts"])
    for query in _feed_query_selection(c):
        try:
            data = c.call(
                "popular_feed_search",
                b._get,
                b.AUTH_BASE,
                "app.bsky.unspecced.getPopularFeedGenerators",
                {"query": query, "limit": 15},
                auth=True,
            )
        except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
            raise
        except Exception as exc:
            c.issues.append(
                f"popular_feed_search:{query}: {type(exc).__name__}: {exc}"
            )
            continue
        feeds = list(data.get("feeds") or [])
        before = set(c.candidates)
        # El AppView no garantiza que los primeros resultados sean del nicho.
        # Antes se aceptaba cualquiera si la CONSULTA era afín (casi siempre).
        # Seleccionar por señales del propio feed, sin duplicar URIs.
        relevant = []
        for feed in feeds:
            if not isinstance(feed, dict) or not feed.get("uri"):
                continue
            label = " ".join([
                str(feed.get("displayName") or ""),
                str(feed.get("description") or ""),
            ])
            hits = _hits(label)
            if not hits or sc.is_political(label):
                continue
            relevant.append((-hits, -(int(feed.get("likeCount") or 0)),
                             str(feed["uri"]), feed))
        seen_feeds = set()
        for _, _, uri, feed in sorted(relevant):
            if uri in seen_feeds:
                continue
            seen_feeds.add(uri)
            if len(seen_feeds) > 2:
                break
            _run_source(
                c,
                "popular_feed_search",
                uri,
                lambda furi=uri: (
                    c.call(
                        "popular_feed_search",
                        b._get,
                        b.AUTH_BASE,
                        "app.bsky.feed.getFeed",
                        {"feed": furi, "limit": limit},
                        auth=True,
                    ).get("feed", [])
                ),
                lambda row, q=query: c.add_post(
                    (row or {}).get("post") or {},
                    "popular_feed",
                    key=q,
                ),
            )
        new_handles = set(c.candidates) - before
        c.metric(
            "popular_feed_search",
            query,
            len(feeds),
            len(new_handles),
            new_handles,
        )


def _discover_trending_topics(c):
    """Abrir las tendencias que usa el cliente oficial y filtrar las afines.

    getTrends es la superficie que consume actualmente Explore/sidebar. Sigue
    siendo unspecced: una caída se registra y nunca hace fallar la ronda.
    """
    try:
        data = c.call(
            "trending_topics",
            b._get,
            b.AUTH_BASE,
            "app.bsky.unspecced.getTrends",
            {"limit": 25},
            auth=True,
            extra_headers=_preference_headers(c),
        )
    except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
        raise
    except Exception as exc:
        c.issues.append(
            f"trending_topics: {type(exc).__name__}: {exc}"
        )
        return

    trends = list(data.get("trends") or [])
    seen = set()
    for item in trends:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        label = " ".join([
            topic,
            str(item.get("displayName") or ""),
            str(item.get("description") or ""),
        ])
        key = _norm(topic)
        if not topic or key in seen or _hits(label) == 0 or sc.is_political(label):
            continue
        seen.add(key)
        _run_source(
            c,
            "trending_topics",
            topic,
            lambda q=topic: c.call(
                "trending_topics",
                b._search_posts,
                q,
                "es",
                25,
                sort="latest",
            ),
            lambda post, q=topic: c.add_post(
                post,
                "trending_topic",
                key=q,
            ),
        )
        if len(seen) >= 3:
            break

def _consume_pool(c):
    """Cuentas de la reserva persistente (`bluesky_pool.py`): seguidores/seguidos de las semillas del nicho, con bio y senal de varias semillas (05/10).

    Medido el 05/10: la shortlist solo veia 1.000-2.000 cuentas distintas al dia; 8.000 escrituras exigen 3.000-5.000. La reserva se rellena aparte (tarea horaria)
    y aqui se ofrecen las mejores no ofrecidas en los ultimos 3 dias. Cada una pasa por la misma tuberia (hidratar, verificar posts, puntuar)."""
    limit = int(c.config["budgets"].get("pool_candidates", 0))
    if limit <= 0:
        return
    import bluesky_pool as pool
    c.mark_attempted("pool")
    try:
        db = pool.connect()
    except Exception as exc:
        c.issues.append(f"pool: {type(exc).__name__}: {exc}")
        return
    try:
        rows = pool.top_candidates(db, limit, today=c.today.isoformat(), exclude=set(c.known) | set(c.discarded) | {c.own_handle})
    except Exception as exc:
        c.issues.append(f"pool: {type(exc).__name__}: {exc}")
        return
    finally:
        db.close()
    accepted, new = 0, []
    for row in rows:
        actor = {
            "did": row["did"], "handle": row["handle"], "displayName": row["display"], "description": row["bio"],
            "followersCount": row["followers"], "followsCount": row["follows"], "postsCount": row["posts"],
        }
        if c.add_actor(actor, "pool", key=f"semillas={min(row['seeds_count'], 5)}"):
            accepted += 1
            new.append(row["handle"])
            item = c.candidates.get(row["handle"])
            if item is not None and row["seeds_count"] >= 2:
                item["signals"].append(f"en el grafo de {row['seeds_count']} semillas del nicho")
    c.metric("pool", "offer", len(rows), accepted, new)


def _initial_discovery(c):
    notifications = _run_source(
        c, "notifications", "inbox",
        lambda: c.call("notifications", b._get_notifications, 100),
        c.add_notification_post,
    )

    # Lo que un humano revisaría justo después de notificaciones.
    _discover_activity_subscriptions(c)
    _discover_own_network(c)
    _discover_own_post_engagers(c)

    _run_source(
        c, "timeline", "home",
        lambda: c.call("timeline", b._get_timeline, 50),
        lambda post: c.add_post(post, "timeline", key="home"),
    )

    # Si existe cache Jetstream, usarla antes de abrir más búsquedas. No sustituye
    # ninguna superficie: simplemente convierte tiempo de escucha previo en candidatos.
    _consume_jetstream_cache(c)
    _consume_taste_cache(c)
    _consume_pool(c)

    # Menús/huella propia: qué hemos marcado con like, intereses y feeds/listas
    # guardados. Son señales humanas ya existentes, no preferencias inferidas por IA.
    _discover_own_likes(c)
    _discover_bookmarks(c)
    _discover_valued_history(c)
    _discover_own_preferences(c)
    _discover_personalized_recommendations(c)
    _discover_suggested_accounts(c)

    # 06/10: la superficie «domain» solo buscaba enlaces a autorademodiaz.com (casi nadie los comparte: 0 handles nuevos en >=5 ejecuciones). Ahora rota por una lista de dominios
    # donde los lectores comparten reseñas y compras de libros (config `domain_queries`): quien enlaza a Goodreads o a Casa del Libro es lector por definicion.
    domains = list(c.config.get("domain_queries") or ["autorademodiaz.com"])
    per_round = int(c.config.get("domains_per_round", 4))
    start = (c.today.toordinal() * per_round) % len(domains)
    for domain in [domains[(start + i) % len(domains)] for i in range(min(per_round, len(domains)))]:
        _run_source(
            c, "domain", domain,
            lambda domain=domain: c.call(
                "domain",
                b._search_posts,
                domain, "all", 25,
                domain=domain, sort="latest",
            ),
            lambda post, domain=domain: c.add_post(post, "domain", key=domain),
        )

    limit = int(c.config["budgets"]["post_search_limit"])
    family_seen = defaultdict(int)
    recent_since = (
        c.today - datetime.timedelta(days=14)
    ).isoformat() + "T00:00:00Z"
    for family, query in _query_selection(c):
        position = family_seen[family]
        family_seen[family] += 1
        sort = "recent" if position % 2 == 0 else "top"
        since = recent_since if sort == "top" else None
        surface = f"post_search:{family}"
        _run_source(
            c, surface, query,
            lambda q=query, order=sort, floor=since: _search_content_v2(
                c, q, limit, sort=order, since=floor
            ),
            lambda post, fam=family, q=query, order=sort: c.add_post(
                post, "post_search", key=f"{fam}:{order}:{q}"
            ),
        )

    # searchPostsV2 permite buscar específicamente REPLIES. Esto encuentra gente
    # que participa en conversaciones literarias aunque su post raíz no nos aparezca.
    _search_replies_v2(c)

    # Hashtags: rotación amplia, no dos etiquetas fijas.
    tags = c.config.get("tag_queries") or []
    ordinal = c.today.toordinal()
    tag_count = min(
        len(tags),
        int(c.config["coverage"].get("tag_queries_per_round", 5)),
    )
    selected = []
    seen = set()
    offset = 0
    while len(selected) < tag_count and offset < len(tags) * 2:
        item = tags[(ordinal + offset * 3) % len(tags)]
        key = str(item.get("tag") or "").casefold()
        if key and key not in seen:
            seen.add(key)
            selected.append(item)
        offset += 1
    for item in selected:
        tag, query = item["tag"], item["query"]
        _run_source(
            c, "tag_search", tag,
            lambda t=tag, q=query: c.call(
                "tag_search", b._search_posts,
                q, "es", limit, sort="latest", tag=[t],
            ),
            lambda post, t=tag: c.add_post(post, "tag_search", key=t),
        )

    actor_limit = int(c.config["budgets"]["actor_search_limit"])
    for query in _actor_query_selection(c):
        _run_source(
            c, "actor_search", query,
            lambda q=query: c.call(
                "actor_search", b._search_actors, q, actor_limit
            ),
            lambda actor, q=query: c.add_actor(actor, "actor_search", key=q),
        )

    # Buscar comunidades directamente, no solo packs creados por cuentas que ya
    # tuvimos la suerte de encontrar.
    _search_starter_packs(c)

    # Las superficies unspecced/experimentales se reservan para el final de
    # la ronda, para que nunca resten presupuesto a comentarios/grafo/perfiles.
    return notifications


def _diverse_candidates(items, limit, score_fn):
    """Evita que una sola superficie monopolice revisión y shortlist."""
    ranked = sorted(
        (
            item for item in items
            if not item.get("excluded_reason")
        ),
        key=lambda item: (-float(score_fn(item)), item["handle"]),
    )
    selected = []
    selected_handles = set()

    for source in DIVERSITY_SOURCES:
        match = next(
            (
                item for item in ranked
                if source in item.get("sources", set())
                and item["handle"] not in selected_handles
            ),
            None,
        )
        if match is not None:
            selected.append(match)
            selected_handles.add(match["handle"])
            if len(selected) >= limit:
                return selected

    for item in ranked:
        if item["handle"] in selected_handles:
            continue
        selected.append(item)
        selected_handles.add(item["handle"])
        if len(selected) >= limit:
            break
    return selected


def _diverse_seed_posts(posts, limit):
    ranked = sorted(
        list(posts),
        key=lambda post: (-_seed_post_score(post), post["url"]),
    )
    selected = []
    selected_uris = set()

    for source in DIVERSITY_SOURCES:
        match = next(
            (
                post for post in ranked
                if source in post.get("sources", set())
                and post["uri"] not in selected_uris
            ),
            None,
        )
        if match is not None:
            selected.append(match)
            selected_uris.add(match["uri"])
            if len(selected) >= limit:
                return selected

    for post in ranked:
        if post["uri"] in selected_uris:
            continue
        selected.append(post)
        selected_uris.add(post["uri"])
        if len(selected) >= limit:
            break
    return selected


def _structured_tags(post):
    record = (post or {}).get("record") or {}
    tags = []
    for tag in record.get("tags") or []:
        if isinstance(tag, str) and tag.strip():
            tags.append(tag.strip().lstrip("#"))

    for facet in record.get("facets") or []:
        if not isinstance(facet, dict):
            continue
        for feature in facet.get("features") or []:
            if not isinstance(feature, dict):
                continue
            tag = feature.get("tag")
            ftype = str(feature.get("$type") or "")
            if isinstance(tag, str) and tag.strip() and (
                not ftype or ftype.endswith("#tag")
            ):
                tags.append(tag.strip().lstrip("#"))
    return list(dict.fromkeys(tags))


_HASHTAG_RE = re.compile(r"(?<![\w#])#([\w]{2,64})", re.UNICODE)


def _expand_dynamic_tags(c):
    """Aprender hashtags actuales y reutilizar los que rindieron días anteriores."""
    configured = {
        _norm(item.get("tag") or "")
        for item in (c.config.get("tag_queries") or [])
    }
    counts = defaultdict(int)
    originals = {}
    for post in c.posts.values():
        discovered = [
            match.group(1)
            for match in _HASHTAG_RE.finditer(post.get("text") or "")
        ]
        # Los post views conservan record.tags/facets: no depender de que #tag
        # estuviera escrito literalmente en el texto.
        discovered.extend(_structured_tags({"record": post.get("record") or {}}))
        # En nuestro cache c.posts guardamos texto/stats, no el record completo.
        # Structured tags se adjuntan al crear el post abajo.
        discovered.extend(post.get("tags") or [])
        for tag in dict.fromkeys(discovered):
            key = _norm(tag)
            if not key or key in configured:
                continue
            if len(key) < 4 or sc.is_political(tag):
                continue
            counts[key] += 1
            originals.setdefault(key, tag)

    current_keys = sorted(
        (
            key for key in counts
            if counts[key] >= 2 or _hits(key) > 0
        ),
        key=lambda key: (-counts[key], -_hits(key), key),
    )
    current_tags = [originals[key] for key in current_keys]

    historical = [
        key
        for (surface, key) in c.query_stats
        if surface == "dynamic_tag"
        and _norm(key) not in configured
        and not sc.is_political(key)
    ]
    historical = gc.rank_keys(
        list(dict.fromkeys(historical)),
        c.query_stats,
        surface="dynamic_tag",
        today=c.today,
    )

    # Intercalar descubrimiento fresco y vocabulario que ya demostró rendimiento.
    combined = []
    width = max(len(current_tags), len(historical))
    for index in range(width):
        if index < len(current_tags):
            combined.append(current_tags[index])
        if index < len(historical):
            combined.append(historical[index])
    tags = list(dict.fromkeys(combined))

    limit = int(c.config["budgets"]["dynamic_tags_per_round"])
    post_limit = int(c.config["budgets"]["post_search_limit"])
    for tag in tags[:limit]:
        _run_source(
            c,
            "dynamic_tag",
            tag,
            lambda t=tag: c.call(
                "dynamic_tag",
                b._search_posts,
                t,
                "es",
                post_limit,
                sort="latest",
                tag=[t],
            ),
            lambda post, t=tag: c.add_post(
                post,
                "dynamic_tag",
                key=t,
            ),
        )


def _seed_post_score(post):
    return (
        _hits(post["text"]) * 2
        + min(post["replies"], 20) * 0.45
        + min(post["likes"], 50) * 0.08
        + min(post["reposts"], 20) * 0.15
        + min(post["quotes"], 10) * 0.25
        + min(post.get("bookmarks", 0), 25) * 0.12
        + min(post.get("taste_paths", 0), 5) * 0.9
    )


def _walk_replies(node):
    if not isinstance(node, dict):
        return
    post = node.get("post")
    if isinstance(post, dict):
        yield post
    for child in node.get("replies") or []:
        yield from _walk_replies(child)


def _thread_posts(c, uri):
    """Leer participantes de hilo con V2; árbol clásico solo como fallback."""
    try:
        data = c.call(
            "thread_commenters",
            b._get,
            b.AUTH_BASE,
            "app.bsky.feed.searchPostsV2",
            {
                "threadRootUri": uri,
                "limit": int(c.config["budgets"]["thread_posts_limit"]),
                "sort": "recent",
            },
            auth=True,
        )
        posts = data.get("posts")
        if isinstance(posts, list):
            return [
                post for post in posts
                if isinstance(post, dict) and post.get("uri") != uri
            ]
    except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
        raise
    except Exception as exc:
        c.issues.append(
            f"thread_search_v2:{uri}: {type(exc).__name__}: {exc}"
        )

    # Compatibilidad/fallback si el AppView aún no ofrece searchPostsV2.
    data = c.call(
        "thread_commenters",
        b._get,
        b.PUBLIC_BASE,
        "app.bsky.feed.getPostThread",
        {
            "uri": uri,
            "depth": int(c.config["budgets"]["thread_depth"]),
        },
        auth=False,
    )
    thread = data.get("thread") if isinstance(data, dict) else None
    if not isinstance(thread, dict):
        return []
    rows = []
    for reply in thread.get("replies") or []:
        rows.extend(_walk_replies(reply))
    return rows


def _expand_threads(c, seeds):
    # Cubierta aunque todos los PostView tengan replyCount=0: en ese caso la
    # optimización correcta es no gastar una lectura remota.
    c.mark_attempted("thread_commenters")
    for post in seeds:
        # El PostView ya trae replyCount: cero significa que abrir el hilo no
        # puede descubrir comentaristas y solo gastaría una lectura.
        if int(post.get("replies") or 0) <= 0:
            continue
        uri = post["uri"]
        url = post["url"]
        _run_source(
            c,
            "thread_commenters",
            uri,
            lambda u=uri: _thread_posts(c, u),
            lambda reply, seed=url: c.add_post(
                reply,
                "thread_commenter",
                key=seed,
            ),
        )


def _expand_engagers(c, seeds, *, track_colikers=False):
    # Cubierta aunque todos los contadores sean cero.
    c.mark_attempted("engagers")
    def consume_liker(row, seed):
        actor = (row or {}).get("actor") or {}
        accepted = c.add_actor(actor, "liker", key=seed)
        did = actor.get("did")
        if track_colikers and isinstance(did, str) and did.startswith("did:"):
            c.coliker_counts[did] += 1
        return accepted

    for post in seeds:
        url = post["url"]
        uri = post["uri"]

        if int(post.get("likes") or 0) > 0:
            _run_source(
                c, "engagers", f"likes:{uri}",
            lambda u=url: c.call(
                "engagers", b._post_engagers, u, "likes",
                int(c.config["budgets"]["engager_likes_limit"])
            ),
                lambda item, seed=url: consume_liker(item, seed),
            )

        if int(post.get("reposts") or 0) > 0:
            _run_source(
                c, "engagers", f"reposts:{uri}",
            lambda u=url: c.call(
                "engagers", b._post_engagers, u, "reposts",
                int(c.config["budgets"]["engager_reposts_limit"])
            ),
                lambda actor, seed=url: c.add_actor(
                    actor or {}, "reposter", key=seed
                ),
            )

        if int(post.get("quotes") or 0) > 0:
            _run_source(
                c, "engagers", f"quotes:{uri}",
            lambda u=url: c.call(
                "engagers", b._post_engagers, u, "quotes",
                int(c.config["budgets"]["engager_quotes_limit"])
            ),
                lambda quote, seed=url: c.add_post(
                    quote, "quote", key=seed
                ),
            )


def _pre_score(item):
    score = sum(SOURCE_WEIGHTS.get(source, 0.5) for source in item["sources"])
    score += min(len(item["sources"]), 4) * 0.6
    # Reaparecer desde padres/queries distintos es corroboración independiente.
    score += min(len(item.get("source_keys") or ()), 6) * 0.25
    profile = item.get("profile") or {}
    score += min(_hits(profile.get("description") or ""), 4) * 0.8
    if item.get("known_date"):
        score += 0.5
    if item.get("followed_by"):
        score += 2.2
    if item.get("activity_subscription"):
        score += 1.0
    return score


def _expansion_seed_candidates(c, limit):
    """Gastar expansión principalmente en nodos nuevos, con fallback relacional."""
    eligible = [
        item for item in c.candidates.values()
        if not item.get("excluded_reason")
    ]
    new = [
        item for item in eligible
        if not item.get("known_date")
        and not item.get("following")
        and not item.get("followed_by")
    ]
    selected = _diverse_candidates(new, int(limit), _pre_score)
    if len(selected) >= int(limit):
        return selected
    seen = {item["handle"] for item in selected}
    selected.extend(_diverse_candidates(
        (item for item in eligible if item["handle"] not in seen),
        int(limit) - len(selected),
        _pre_score,
    ))
    return selected[: int(limit)]


def _expand_similar_accounts(c):
    seeds = _expansion_seed_candidates(
        c, int(c.config["budgets"]["similar_actor_seeds"])
    )
    for item in seeds:
        handle = item["handle"]
        _run_source(
            c, "similar_accounts", handle,
            lambda h=handle: (
                c.call(
                    "similar_accounts", b._get,
                    b.PUBLIC_BASE,
                    "app.bsky.graph.getSuggestedFollowsByActor",
                    {"actor": h},
                    auth=False,
                ).get("suggestions", [])
            ),
            lambda actor, seed=handle: c.add_actor(
                actor, "similar_account", key=seed
            ),
        )


def _expand_graph_neighbors(c):
    """Abrir el grafo de perfiles prometedores sin seguir a nadie automáticamente."""
    seeds = _expansion_seed_candidates(
        c, int(c.config["budgets"]["graph_neighbor_seeds"])
    )
    limit = int(c.config["budgets"]["graph_neighbor_limit"])

    for item in seeds:
        handle = item["handle"]
        _run_source(
            c, "graph_neighbors", f"followers:{handle}",
            lambda h=handle: (
                c.call(
                    "graph_neighbors", b._get,
                    b.PUBLIC_BASE,
                    "app.bsky.graph.getFollowers",
                    {"actor": h, "limit": limit, "sort": "top"},
                    auth=False,
                ).get("followers", [])
            ),
            lambda actor, seed=handle: c.add_actor(
                actor, "follower_neighbor", key=seed
            ),
        )
        _run_source(
            c, "graph_neighbors", f"follows:{handle}",
            lambda h=handle: (
                c.call(
                    "graph_neighbors", b._get,
                    b.PUBLIC_BASE,
                    "app.bsky.graph.getFollows",
                    {"actor": h, "limit": limit, "sort": "top"},
                    auth=False,
                ).get("follows", [])
            ),
            lambda actor, seed=handle: c.add_actor(
                actor, "following_neighbor", key=seed
            ),
        )


def _starter_pack_list_uri(pack):
    if not isinstance(pack, dict):
        return None
    # searchStarterPacksV2 devuelve starterPackView con listViewBasic.
    list_view = pack.get("list")
    if isinstance(list_view, dict):
        uri = list_view.get("uri")
        if isinstance(uri, str) and uri.startswith("at://"):
            return uri
    # Compatibilidad con vistas/basic antiguas: el record raw contiene list.
    record = pack.get("record")
    if isinstance(record, dict):
        uri = record.get("list")
        if isinstance(uri, str) and uri.startswith("at://"):
            return uri
    return None


def _expand_starter_packs(c):
    """Revisar packs creados por perfiles fuertes y extraer sus miembros.

    Esta superficie es oportunista: no todos los actores crean starter packs.
    Los packs no se siguen en bloque; solo aportan candidatos al mismo ranking.
    """
    seeds = _expansion_seed_candidates(
        c, int(c.config["budgets"]["starter_pack_seeds"])
    )
    item_limit = int(c.config["budgets"]["starter_pack_items"])

    for item in seeds:
        handle = item["handle"]
        try:
            c.budget.take("starter_packs")
            data = b._get(
                b.PUBLIC_BASE,
                "app.bsky.graph.getActorStarterPacks",
                {"actor": handle, "limit": 10},
                auth=False,
            )
        except b.RateLimitExceeded:
            raise
        except gc.ReadBudgetExceeded:
            raise
        except Exception as exc:
            c.issues.append(
                f"starter_packs:{handle}: {type(exc).__name__}: {exc}"
            )
            continue

        packs = list(data.get("starterPacks") or [])
        relevant = []
        for pack in packs:
            record = pack.get("record") if isinstance(pack, dict) else None
            record = record if isinstance(record, dict) else {}
            label = " ".join([
                str(record.get("name") or ""),
                str(record.get("description") or ""),
            ])
            # Un creador ya bien situado puede tener un pack genérico útil,
            # pero los packs con señal literaria van primero.
            relevant.append((_hits(label), pack))
        relevant.sort(key=lambda pair: -pair[0])

        for _, pack in relevant[:2]:
            list_uri = _starter_pack_list_uri(pack)
            if not list_uri:
                continue
            name = ((pack.get("record") or {}).get("name") or list_uri)
            _run_source(
                c, "starter_packs", list_uri,
                lambda u=list_uri: (
                    c.call(
                        "starter_packs", b._get,
                        b.PUBLIC_BASE,
                        "app.bsky.graph.getList",
                        {"list": u, "limit": item_limit},
                        auth=False,
                    ).get("items", [])
                ),
                lambda row, pack_name=name: c.add_actor(
                    (row or {}).get("subject") or {},
                    "starter_pack",
                    key=str(pack_name),
                ),
            )


def _menu_label(view):
    if not isinstance(view, dict):
        return ""
    return " ".join([
        str(view.get("name") or ""),
        str(view.get("displayName") or ""),
        str(view.get("description") or ""),
    ]).strip()


def _expand_actor_menus(c):
    """Explorar listas y custom feeds creados por perfiles prometedores.

    Es el equivalente a entrar en el perfil de una cuenta buena y abrir sus menús.
    Las cuentas/posts encontrados vuelven al mismo filtro y shortlist.
    """
    # Incluso si todos los perfiles declaran cero listas/feeds, la superficie
    # se considera cubierta sin inventar una llamada remota.
    c.mark_attempted("curated_lists")
    c.mark_attempted("actor_feeds")

    seeds = sorted(
        c.candidates.values(),
        key=lambda item: (-_pre_score(item), item["handle"]),
    )[: int(c.config["budgets"]["actor_menu_seeds"])]
    list_limit = int(c.config["budgets"]["lists_per_actor"])
    feed_limit = int(c.config["budgets"]["actor_feeds_per_actor"])
    post_limit = int(c.config["budgets"]["saved_feed_posts"])

    for item in seeds:
        handle = item["handle"]
        profile = item.get("profile") or {}
        associated = profile.get("associated")
        associated = associated if isinstance(associated, dict) else {}

        # Listas curadas por la cuenta.
        if associated.get("lists", 1) != 0:
            try:
                data = c.call(
                    "curated_lists",
                    b._get,
                    b.PUBLIC_BASE,
                    "app.bsky.graph.getLists",
                    {
                        "actor": handle,
                        "limit": 25,
                        "purposes": ["curatelist"],
                    },
                    auth=False,
                )
                lists = list(data.get("lists") or [])
            except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
                raise
            except Exception as exc:
                c.issues.append(
                    f"curated_lists:{handle}: {type(exc).__name__}: {exc}"
                )
                lists = []

            ranked_lists = sorted(
                lists,
                key=lambda view: (
                    -_hits(_menu_label(view)),
                    -(int(view.get("listItemCount") or 0)),
                    str(view.get("uri") or ""),
                ),
            )
            chosen_lists = [
                view for view in ranked_lists
                if _hits(_menu_label(view)) > 0 or _pre_score(item) >= 6.0
            ][:list_limit]

            for view in chosen_lists:
                uri = view.get("uri")
                if not uri:
                    continue
                label = _menu_label(view) or uri

                # Qué publica la gente de esa lista.
                _run_source(
                    c,
                    "curated_lists",
                    f"feed:{uri}",
                    lambda list_uri=uri: (
                        c.call(
                            "curated_lists",
                            b._get,
                            b.PUBLIC_BASE,
                            "app.bsky.feed.getListFeed",
                            {"list": list_uri, "limit": post_limit},
                            auth=False,
                        ).get("feed", [])
                    ),
                    lambda row, name=label: c.add_post(
                        (row or {}).get("post") or {},
                        "curated_list",
                        key=name,
                    ),
                )

                # Y quién forma parte de ella.
                _run_source(
                    c,
                    "curated_lists",
                    f"members:{uri}",
                    lambda list_uri=uri: (
                        c.call(
                            "curated_lists",
                            b._get,
                            b.PUBLIC_BASE,
                            "app.bsky.graph.getList",
                            {
                                "list": list_uri,
                                "limit": int(c.config["budgets"]["starter_pack_items"]),
                            },
                            auth=False,
                        ).get("items", [])
                    ),
                    lambda row, name=label: c.add_actor(
                        (row or {}).get("subject") or {},
                        "curated_list",
                        key=name,
                    ),
                )

        # Custom feeds creados por la cuenta.
        if associated.get("feedgens", 1) != 0:
            try:
                data = c.call(
                    "actor_feeds",
                    b._get,
                    b.PUBLIC_BASE,
                    "app.bsky.feed.getActorFeeds",
                    {"actor": handle, "limit": 25},
                    auth=False,
                )
                feeds = list(data.get("feeds") or [])
            except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
                raise
            except Exception as exc:
                c.issues.append(
                    f"actor_feeds:{handle}: {type(exc).__name__}: {exc}"
                )
                feeds = []

            ranked_feeds = sorted(
                feeds,
                key=lambda view: (
                    -_hits(_menu_label(view)),
                    -(int(view.get("likeCount") or 0)),
                    str(view.get("uri") or ""),
                ),
            )
            chosen_feeds = [
                view for view in ranked_feeds
                if _hits(_menu_label(view)) > 0 or _pre_score(item) >= 6.0
            ][:feed_limit]
            for view in chosen_feeds:
                uri = view.get("uri")
                if not uri:
                    continue
                label = _menu_label(view) or uri
                _run_source(
                    c,
                    "actor_feeds",
                    uri,
                    lambda feed_uri=uri: (
                        c.call(
                            "actor_feeds",
                            b._get,
                            b.PUBLIC_BASE,
                            "app.bsky.feed.getFeed",
                            {"feed": feed_uri, "limit": post_limit},
                            auth=False,
                        ).get("feed", [])
                    ),
                    lambda row, name=label: c.add_post(
                        (row or {}).get("post") or {},
                        "actor_feed",
                        key=name,
                    ),
                )


def _enrich_known_followers(c):
    """Añadir contexto de conexiones ya conocidas del candidato.

    getKnownFollowers enumera seguidores del candidato que la cuenta autenticada
    ya sigue. Sirve como señal social, nunca como requisito de follow.
    """
    ordered = sorted(
        c.candidates.values(),
        key=lambda item: (-_pre_score(item), item["handle"]),
    )
    checks = int(c.config["budgets"]["known_followers_checks"])
    attempted = 0
    for item in ordered:
        if attempted >= checks:
            break
        if item.get("excluded_reason"):
            continue
        if item.get("following") or item.get("known_followers_count"):
            continue

        profile = item.get("profile") or {}
        viewer = profile.get("viewer")
        viewer = viewer if isinstance(viewer, dict) else {}
        cached = viewer.get("knownFollowers")
        if isinstance(cached, dict) and int(cached.get("count") or 0) > 0:
            count = int(cached.get("count") or 0)
            item["known_followers_count"] = count
            item["sources"].add("known_follower")
            continue

        attempted += 1
        try:
            data = c.call(
                "known_followers",
                b._get,
                b.AUTH_BASE,
                "app.bsky.graph.getKnownFollowers",
                {"actor": item["handle"], "limit": 20},
                auth=True,
            )
        except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
            raise
        except Exception as exc:
            c.issues.append(
                f"known_followers:{item['handle']}: {type(exc).__name__}: {exc}"
            )
            continue

        followers = list(data.get("followers") or [])
        if followers:
            item["known_followers_count"] = len(followers)
            item["sources"].add("known_follower")
            item["source_keys"].add(
                f"known_follower:{item['handle']}"
            )


def _explore_custom_feeds(c):
    try:
        c.budget.take("custom_feed")
        data = b._get(
            b.AUTH_BASE,
            "app.bsky.feed.getSuggestedFeeds",
            {"limit": 50},
            auth=True,
        )
    except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
        raise
    except Exception as exc:
        c.issues.append(f"custom_feed:suggestions: {type(exc).__name__}: {exc}")
        return

    relevant = []
    for feed in data.get("feeds") or []:
        haystack = " ".join([
            feed.get("displayName") or "",
            feed.get("description") or "",
        ])
        if _hits(haystack) > 0 and feed.get("uri"):
            relevant.append(feed)
    relevant.sort(
        key=lambda feed: (-_hits(
            " ".join([feed.get("displayName") or "", feed.get("description") or ""])
        ), -(feed.get("likeCount") or 0))
    )
    for feed in relevant[: int(c.config["budgets"]["custom_feeds"])]:
        uri = feed["uri"]
        _run_source(
            c, "custom_feed", uri,
            lambda u=uri: (
                c.call(
                    "custom_feed", b._get,
                    b.PUBLIC_BASE, "app.bsky.feed.getFeed",
                    {
                        "feed": u,
                        "limit": int(c.config["budgets"]["custom_feed_posts"]),
                    },
                    auth=False,
                ).get("feed", [])
            ),
            lambda row, name=feed.get("displayName") or uri: c.add_post(
                (row or {}).get("post") or {},
                "custom_feed",
                key=name,
            ),
        )


def _hydrate_selected_profiles(c, handles):
    """Hidratar un frontier concreto sin volver a revisar todo el universo."""
    unique = list(dict.fromkeys(
        str(handle).casefold() for handle in handles if handle
    ))
    pending = []
    for handle in unique:
        item = c.candidates.get(handle)
        if not item:
            continue
        profile = item.get("profile") or {}
        viewer = profile.get("viewer")
        detailed = (
            "followersCount" in profile
            and "followsCount" in profile
            and "postsCount" in profile
            and isinstance(viewer, dict)
        )
        if not detailed:
            pending.append(handle)

    batch_size = min(25, int(c.config["budgets"]["profile_batch_limit"]))
    for start in range(0, len(pending), batch_size):
        chunk = pending[start:start + batch_size]
        try:
            c.budget.take("profile_batch")
            data = b._get(
                b.AUTH_BASE,
                "app.bsky.actor.getProfiles",
                {"actors": chunk},
                auth=True,
            )
        except b.RateLimitExceeded:
            raise
        except gc.ReadBudgetExceeded:
            raise
        except Exception as exc:
            c.issues.append(f"profile_batch:{type(exc).__name__}: {exc}")
            continue
        for profile in data.get("profiles") or []:
            handle = (profile.get("handle") or "").casefold()
            item = c.candidates.get(handle)
            if not item:
                continue
            item["profile"] = profile
            c._apply_viewer_state(item, profile)
            joined_pack = profile.get("joinedViaStarterPack")
            if isinstance(joined_pack, dict):
                pack_uri = joined_pack.get("uri")
                if isinstance(pack_uri, str) and pack_uri.startswith("at://"):
                    item["sources"].add("joined_starter_pack")
                    item["source_keys"].add(
                        f"joined_starter_pack:{pack_uri}"
                    )
            bio = profile.get("description") or ""
            if sc.is_political(bio) or _spammy(bio):
                item["excluded_reason"] = "profile_filter"


def _hydrate_profiles(c):
    """Hidratar en batch solo perfiles que todavía no tengan vista detallada."""
    max_profiles = min(
        len(c.candidates),
        max(int(c.config["shortlist"]["profiles"]) * 2, 50),
    )
    ordered = _diverse_candidates(
        c.candidates.values(),
        max_profiles,
        _pre_score,
    )
    _hydrate_selected_profiles(
        c, [item["handle"] for item in ordered[:max_profiles]]
    )


def _expand_joined_starter_packs(c):
    """Abrir algunos packs que aparecen gratis al hidratar perfiles prometedores."""
    limit = int(c.config["budgets"].get("joined_starter_pack_expansions", 0))
    if limit <= 0:
        return
    packs = {}
    for item in c.candidates.values():
        if item.get("excluded_reason"):
            continue
        profile = item.get("profile") or {}
        pack = profile.get("joinedViaStarterPack")
        if not isinstance(pack, dict):
            continue
        uri = pack.get("uri")
        list_uri = _starter_pack_list_uri(pack)
        if not isinstance(uri, str) or not list_uri:
            continue
        record = pack.get("record") if isinstance(pack.get("record"), dict) else {}
        label = " ".join([
            str(record.get("name") or ""),
            str(record.get("description") or ""),
        ])
        score = (
            _hits(label) * 3
            + min(int(pack.get("joinedWeekCount") or 0), 20) * 0.15
            + min(int(pack.get("joinedAllTimeCount") or 0), 100) * 0.02
            + _pre_score(item) * 0.25
        )
        previous = packs.get(uri)
        if previous is None or score > previous[0]:
            packs[uri] = (score, list_uri)

    item_limit = int(c.config["budgets"]["starter_pack_items"])
    for pack_uri, (_, list_uri) in sorted(
        packs.items(), key=lambda pair: (-pair[1][0], pair[0])
    )[:limit]:
        _run_source(
            c,
            "joined_starter_pack",
            pack_uri,
            lambda u=list_uri: (
                c.call(
                    "joined_starter_pack", b._get,
                    b.PUBLIC_BASE,
                    "app.bsky.graph.getList",
                    {"list": u, "limit": item_limit},
                    auth=False,
                ).get("items", [])
            ),
            lambda row, uri=pack_uri: c.add_actor(
                (row or {}).get("subject") or {},
                "joined_starter_pack",
                key=uri,
            ),
        )


def _prefetch_author_feeds(c, handles, feed_limit, workers):
    """Descarga los feeds de autor en paralelo (05/10): 918 lecturas secuenciales a ~1,6 s eran 25 min por scan; con 6 hilos son ~4 min y quedan muy por
    debajo de las 3.000 peticiones cada 5 minutos por IP. El presupuesto se descuenta en el hilo principal y el resultado (o la excepcion) se consume en orden."""
    from concurrent.futures import ThreadPoolExecutor
    jobs = []
    for handle in handles:
        try:
            c.mark_attempted("author_feed")
            c.budget.take("author_feed")
        except gc.ReadBudgetExceeded:
            break
        jobs.append(handle)

    def fetch(handle):
        return b._get(
            b.PUBLIC_BASE, "app.bsky.feed.getAuthorFeed",
            {"actor": handle, "limit": feed_limit, "filter": "posts_with_replies"}, auth=False,
        ).get("feed", [])

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
        futures = {handle: executor.submit(fetch, handle) for handle in jobs}
    out = {}
    for handle, future in futures.items():
        try:
            out[handle] = future.result()
        except Exception as exc:
            out[handle] = exc
    return out


def _vet_selected_author_feeds(c, handles):
    feed_limit = int(c.config["budgets"]["author_feed_posts"])
    todo = []
    for handle in dict.fromkeys(str(h).casefold() for h in handles if h):
        item = c.candidates.get(handle)
        if item and not item.get("excluded_reason"):
            todo.append(handle)
    workers = int(c.config["budgets"].get("fetch_workers", 1))
    prefetched = _prefetch_author_feeds(c, todo, feed_limit, workers) if workers > 1 and len(todo) > 1 else {}

    def prefetched_result(handle):
        result = prefetched[handle]
        if isinstance(result, Exception):
            raise result
        return result

    for handle in todo:
        _run_source(
            c, "author_feed", handle,
            (lambda h=handle: prefetched_result(h)) if handle in prefetched else (
                lambda h=handle: (
                    c.call(
                        "author_feed", b._get,
                        b.PUBLIC_BASE,
                        "app.bsky.feed.getAuthorFeed",
                        {
                            "actor": h,
                            "limit": feed_limit,
                            "filter": "posts_with_replies",
                        },
                        auth=False,
                    ).get("feed", [])
                )
            ),
            lambda row, h=handle: c.add_post(
                (row or {}).get("post") or {},
                "author_feed",
                key=h,
            ),
        )


def _vet_author_feeds(c):
    limit = int(c.config["budgets"]["max_profiles_to_vet"])
    ordered = _diverse_candidates(
        c.candidates.values(),
        limit,
        _pre_score,
    )
    _vet_selected_author_feeds(
        c, [item["handle"] for item in ordered[:limit]]
    )


def _vet_shortlist_gaps(c):
    """Verifica los posts de los perfiles que YA estan en la shortlist y no tienen ninguno (05/10).

    Medido el 05/10: de 1.000 perfiles de la shortlist, 594 (375 con bio del nicho) no tenian ni un post cargado, porque `_vet_author_feeds` elige
    por `_pre_score` ANTES de hidratar la bio y la shortlist se ordena DESPUES. Un perfil sin post no puede recibir like: el embudo perdia el 59 % de la
    oferta, no por falta de lecturas (se gastaba el 32 % del presupuesto) sino por orden de las operaciones. Cada verificacion es 1 lectura.
    """
    limit = int(c.config["budgets"].get("vet_gap_profiles", 0))
    if limit <= 0:
        return
    for item in c.candidates.values():
        item["score"] = _profile_score(c, item)
    ranked = _select_shortlist_candidates(c, int(c.config["shortlist"]["profiles"]))
    gaps = [item["handle"] for item in ranked if not any(uri in c.posts for uri in item.get("posts", ()))]
    c.mark_attempted("vet_shortlist_gaps")
    _vet_selected_author_feeds(c, gaps[:limit])


def _second_wave_value(post):
    """Priorizar ramas con señal útil por lectura, no popularidad bruta."""
    replies = int(post.get("replies") or 0)
    likes = int(post.get("likes") or 0)
    reposts = int(post.get("reposts") or 0)
    quotes = int(post.get("quotes") or 0)
    # Una respuesta descubre conversación/actor con mucha más intención que un like.
    # Lograr 200 likes no debe desplazar a una conversación pequeña pero fértil.
    return (
        _hits(post.get("text") or "") * 2.0
        + min(replies, 12) * 0.65
        + min(quotes, 8) * 0.45
        + min(reposts, 12) * 0.20
        + min(likes, 30) * 0.08
    )


def _frontier_seed_score(c, post):
    score = _second_wave_value(post)
    item = c.candidates.get(post.get("handle")) or {}
    if (
        not item.get("known_date")
        and not item.get("following")
        and not item.get("followed_by")
    ):
        score += 1.5
    stats = c.query_stats.get(
        ("second_wave_author", str(post.get("handle") or "")),
        {},
    )
    attempts = int(stats.get("attempts") or 0)
    historical_new = int(stats.get("new_handles") or 0)
    if attempts > 0:
        score += min(historical_new / attempts, 8.0) * 0.35
    return score


def _frontier_posts(c, handles, visited_posts, limit):
    allowed = set(handles) if handles is not None else None
    candidates = []
    for post in c.posts.values():
        if "author_feed" not in post.get("sources", set()):
            continue
        if allowed is not None and post.get("handle") not in allowed:
            continue
        if post["uri"] in visited_posts:
            continue
        if (
            int(post.get("replies") or 0)
            + int(post.get("likes") or 0)
            + int(post.get("reposts") or 0)
            + int(post.get("quotes") or 0)
        ) <= 0:
            continue
        candidates.append(post)

    ordered = sorted(
        candidates,
        key=lambda post: (-_frontier_seed_score(c, post), post["url"]),
    )
    seeds = []
    authors = set()
    for post in ordered:
        author = post.get("handle")
        if author in authors:
            continue
        seeds.append(post)
        authors.add(author)
        if len(seeds) >= limit:
            break
    return seeds


def _expand_second_wave(c):
    """Frontier adaptativo: actor -> post -> actor -> post -> actor.

    Profundiza únicamente las ramas que producen handles nuevos, mantiene un
    conjunto de posts visitados y acota ancho, perfiles hidratados y profundidad.
    """
    c.mark_attempted("second_wave")
    width = int(c.config["budgets"].get("second_wave_seeds", 0))
    max_depth = int(c.config["budgets"].get("second_wave_depth", 1))
    profile_width = int(
        c.config["budgets"].get("second_wave_profiles_per_depth", width)
    )
    min_new = int(c.config["budgets"].get("second_wave_min_new_handles", 1))
    if width <= 0 or max_depth <= 0:
        return

    frontier_handles = None
    visited_posts = set()

    for depth in range(1, max_depth + 1):
        seeds = _frontier_posts(
            c, frontier_handles, visited_posts, width
        )
        if not seeds:
            break

        productive_handles = set()
        for post in seeds:
            visited_posts.add(post["uri"])
            before = set(c.candidates)
            _expand_threads(c, [post])
            _expand_engagers(c, [post])
            new_handles = set(c.candidates) - before
            gained = len(new_handles)
            c.metric(
                "second_wave",
                f"d{depth}:{post['uri']}",
                1,
                gained,
                new_handles,
            )
            c.metric(
                "second_wave_author",
                str(post.get("handle") or ""),
                1,
                gained,
                new_handles,
            )
            if gained >= min_new:
                productive_handles.update(new_handles)

        if depth >= max_depth or not productive_handles:
            break

        # Solo gastar profile/feed reads en los nuevos actores de ramas fértiles.
        ranked = sorted(
            (
                c.candidates[h] for h in productive_handles
                if h in c.candidates
                and not c.candidates[h].get("excluded_reason")
            ),
            key=lambda item: (-_pre_score(item), item["handle"]),
        )
        next_handles = [
            item["handle"] for item in ranked[:profile_width]
        ]
        if not next_handles:
            break
        _hydrate_selected_profiles(c, next_handles)

        # La hidratación puede revelar bio de spam/política que el ProfileView
        # ligero no incluía. No abrir author feeds de esos perfiles.
        next_handles = [
            h for h in next_handles
            if h in c.candidates and not c.candidates[h].get("excluded_reason")
        ]
        if not next_handles:
            break
        _vet_selected_author_feeds(c, next_handles)
        frontier_handles = next_handles

def _profile_score(c, item):
    # 02/10: "handle.invalid" (verificacion de handle fallida) llego al plan y
    # el preflight bloqueo todo el lote de 128 acciones por un solo handle.
    if str(item.get("handle") or "").endswith(".invalid"):
        item["excluded_reason"] = "handle invalido"
    if sc.is_feed_bridge(item.get("handle")):
        item["excluded_reason"] = "cuenta puente (no es una persona)"
    if item.get("excluded_reason"):
        return -1000.0
    profile = item.get("profile") or {}
    bio = profile.get("description") or ""
    posts = [c.posts[uri] for uri in item["posts"] if uri in c.posts]
    score = _pre_score(item)
    niche = _hits(bio)
    item["bio_hits"] = niche
    score += min(niche, 5) * 0.9

    relevant_posts = 0
    conversation_posts = 0
    for post in posts:
        post_hits = _hits(post["text"])
        if post_hits:
            relevant_posts += 1
            score += min(post_hits, 4) * 0.35
        if post["replies"] > 0 or sc.invites_conversation(post["text"]):
            conversation_posts += 1
    score += min(relevant_posts, 4) * 0.7
    score += min(conversation_posts, 3) * 0.35

    if "thread_commenter" in item["sources"]:
        item["signals"].append("comenta en conversaciones reales")
    if len(item["sources"]) >= 2:
        item["signals"].append("aparece por varias vías")
    if relevant_posts >= 2:
        item["signals"].append("varios posts recientes afines")
    if niche:
        item["signals"].append("bio afín al nicho")
    known_followers = int(item.get("known_followers_count") or 0)
    if known_followers:
        score += min(known_followers, 5) * 0.55
        item["signals"].append(
            f"{known_followers} conexiones ya seguidas también le siguen"
        )
    if item.get("followed_by"):
        item["signals"].append("ya sigue a David")
        score += 1.8
    if item.get("activity_subscription"):
        item["signals"].append("suscripción de actividad explícita")
        score += 0.8
    if item.get("following"):
        item["signals"].append("ya seguido")
        score -= 0.4
    if _spammy(bio):
        score -= 10
    return round(score, 2)


def _refresh_post_actionability(c):
    """Hidrata viewerState en lote antes de gastar IA en reply/quote."""
    c.mark_attempted("post_actionability")
    profile_limit = int(c.config["budgets"]["actionability_profiles"])
    candidates = _diverse_candidates(
        c.candidates.values(),
        profile_limit,
        _pre_score,
    )
    per_profile = int(c.config["shortlist"]["posts_per_profile"])
    uris = []
    for item in candidates:
        posts = sorted(
            (
                c.posts[uri]
                for uri in item.get("posts", set())
                if uri in c.posts
            ),
            key=lambda post: (-_seed_post_score(post), post["url"]),
        )
        uris.extend(post["uri"] for post in posts[:per_profile])

    unique = list(dict.fromkeys(uris))
    for start in range(0, len(unique), 25):
        chunk = unique[start:start + 25]
        if not chunk:
            continue
        try:
            data = c.call(
                "post_actionability",
                b._get,
                b.AUTH_BASE,
                "app.bsky.feed.getPosts",
                {"uris": chunk},
                auth=True,
            )
        except (b.RateLimitExceeded, gc.ReadBudgetExceeded):
            raise
        except Exception as exc:
            c.issues.append(
                f"post_actionability: {type(exc).__name__}: {exc}"
            )
            continue
        for post in data.get("posts") or []:
            uri = post.get("uri")
            stored = c.posts.get(uri)
            viewer = post.get("viewer")
            if not stored or not isinstance(viewer, dict):
                continue
            stored["reply_disabled"] = bool(viewer.get("replyDisabled"))
            stored["embedding_disabled"] = bool(
                viewer.get("embeddingDisabled")
            )
            stored["liked"] = bool(viewer.get("like"))
            stored["reposted"] = bool(viewer.get("repost"))


def _post_actions(c, item, post):
    """Proponer repertorio, no decidir por popularidad.

    El shortlist ya pasó filtros/ranking. Un post pequeño puede merecer interacción;
    likes/replies/reposts/quotes son posibilidades para la fase editorial.
    """
    actions = []
    if post["uri"] in c.own_reply_parents:
        return [] if post.get("liked") else ["like"]
    if _relationship_lane(item) == "acquisition" and _spanish_post(post) is False:
        return []      # a un lector nuevo solo se le escribe en su idioma (la cuenta de David es en espanol)

    words = len(post["text"].split())
    hits = _hits(post["text"])
    strong_profile = float(item.get("score") or _pre_score(item)) >= 5.0

    # 05/10: se daban likes a posts de hace 338 dias: pierde valor y delata al bot. Consulta E (GPT): adquisicion <=21 dias (prioridad a lo reciente), comunidad
    # (mutuos y relaciones existentes) hasta 45.
    community = _relationship_lane(item) == "community"
    max_age = gp.max_post_age_days(c.config, "community" if community else "acquisition")   # umbral comun a todas las redes (growth_policy)
    age = _days_since((post.get("created_at") or "")[:10], c.today)
    fresh_enough = age is None or age <= max_age
    if (hits > 0 or (strong_profile and words >= 5)) and not post.get("liked") and fresh_enough:
        actions.append("like")

    conversation_worthy = (
        not _self_promo(post["text"])
        and words >= 8
        and (
            sc.invites_conversation(post["text"])
            or hits > 0
            or strong_profile
        )
    )
    if conversation_worthy and not post.get("reply_disabled"):
        actions.append("reply")

    broad_value = (
        not _self_promo(post["text"])
        and words >= 10
        and (hits >= 2 or strong_profile)
    )
    if broad_value and not post.get("reposted"):
        actions.append("repost")
    if (
        broad_value
        and not post.get("embedding_disabled")
        and words >= 18
        and (post["replies"] > 0 or sc.invites_conversation(post["text"]))
    ):
        actions.append("quote")

    return list(dict.fromkeys(actions))


def _relationship_lane(item):
    """Separar cuidado de comunidad de captación sin duplicar candidatos."""
    sources = item.get("sources", set())
    if (
        item.get("known_date")
        or item.get("followed_by")
        or item.get("following")
        or "notification" in sources
        or "activity_subscription" in sources
        or "own_following" in sources
    ):
        return "community"
    return "acquisition"


def _community_priority(c, item):
    """Evitar machacar a la misma relación salvo conversación entrante real."""
    score = float(item.get("score") or _profile_score(c, item))
    sources = item.get("sources", set())
    notification_age = _days_since(item.get("last_notification_at"), c.today)
    if (
        (
            item.get("notification_unread")
            and notification_age is not None
            and notification_age <= 1
        )
        or sources & {"own_post_reply", "own_post_quote"}
    ):
        return score
    days = _days_since(item.get("known_date"), c.today)
    cooldown = int(c.config["shortlist"].get("community_cooldown_days", 2))
    if days is not None and days <= cooldown:
        score -= 3.0
    return score


def _select_shortlist_candidates(c, profile_limit):
    """Garantizar captación fresca sin abandonar relaciones que ya responden."""
    items = [
        item for item in c.candidates.values()
        if not item.get("excluded_reason")
    ]
    acquisition = [
        item for item in items if _relationship_lane(item) == "acquisition"
    ]
    community = [
        item for item in items if _relationship_lane(item) == "community"
    ]

    acq_target = min(
        profile_limit,
        int(c.config["shortlist"].get("acquisition_min", profile_limit)),
    )
    community_target = min(
        profile_limit - acq_target,
        int(c.config["shortlist"].get("community_target", profile_limit)),
    )
    cooldown = int(
        c.config["shortlist"].get("acquisition_cooldown_days", 3)
    )
    fresh_acquisition = []
    seen_acquisition = []
    for item in acquisition:
        age = _days_since(item.get("seen_date"), c.today)
        if age is not None and age <= cooldown:
            seen_acquisition.append(item)
        else:
            fresh_acquisition.append(item)

    selected = _diverse_candidates(
        fresh_acquisition, acq_target, lambda item: item["score"]
    )
    selected_handles = {item["handle"] for item in selected}

    # Si el nicho está temporalmente agotado, rellenar la cuota con candidatos
    # vistos recientemente es preferible a convertir toda la ronda en comunidad.
    if len(selected) < acq_target:
        fallback = _diverse_candidates(
            (
                item for item in seen_acquisition
                if item["handle"] not in selected_handles
            ),
            acq_target - len(selected),
            lambda item: item["score"],
        )
        selected.extend(fallback)
        selected_handles.update(item["handle"] for item in fallback)

    community_rows = _diverse_candidates(
        (
            item for item in community
            if item["handle"] not in selected_handles
        ),
        community_target,
        lambda item: _community_priority(c, item),
    )
    selected.extend(community_rows)
    selected_handles.update(item["handle"] for item in community_rows)

    # Relleno final sin romper la prioridad: primero adquisición sobrante y
    # después comunidad. Así 36 plazas no se convierten en 36 conocidos.
    remaining = profile_limit - len(selected)
    if remaining > 0:
        extra_acq = _diverse_candidates(
            (
                item for item in acquisition
                if item["handle"] not in selected_handles
            ),
            remaining,
            lambda item: item["score"],
        )
        selected.extend(extra_acq)
        selected_handles.update(item["handle"] for item in extra_acq)
        remaining = profile_limit - len(selected)
    if remaining > 0:
        extra_community = _diverse_candidates(
            (
                item for item in community
                if item["handle"] not in selected_handles
            ),
            remaining,
            lambda item: _community_priority(c, item),
        )
        selected.extend(extra_community)

    return selected[:profile_limit]


def _repost_worthy(c, item, post):
    """Criterio comun a todas las redes (`scan_common.share_worthy`); aqui solo se calculan los datos propios de Bluesky."""
    return sc.share_worthy(
        post["text"], spanish=_spanish_post(post), niche_hits=_hits(post["text"]),
        followers=(item.get("profile") or {}).get("followersCount"), age_days=_days_since((post.get("created_at") or "")[:10], c.today),
    )


def _age_bucket(post, today):
    """0 = hasta 3 dias, 1 = hasta 14, 2 = mas viejo (consulta E: el valor de un like decae con la edad del post; se elige lo reciente primero)."""
    age = _days_since((post.get("created_at") or "")[:10], today)
    return 0 if age is None or age <= 3 else 1 if age <= 14 else 2


def _persist_candidates(c):
    """Guarda en la reserva persistente todo lo que este scan encontro con perfil (union de fuentes; GPT, consulta E: «candidate reservoir multifuente»)."""
    try:
        import bluesky_pool as pool
        db = pool.connect()
    except Exception as exc:
        c.issues.append(f"pool_persist: {type(exc).__name__}: {exc}")
        return
    try:
        rows = []
        for item in c.candidates.values():
            profile = item.get("profile") or {}
            if item.get("excluded_reason") or "pool" in item.get("sources", ()) or not profile.get("did"):
                continue
            order = item.get("source_order") or sorted(item.get("sources") or ["desconocida"])
            rows.append((profile, str(order[0])))
        pool.record_scan_candidates(db, rows, c.today.isoformat())
    except Exception as exc:
        c.issues.append(f"pool_persist: {type(exc).__name__}: {exc}")
    finally:
        db.close()


def _first_touch_map(c, items):
    """{handle: fuente first-touch} desde la reserva persistente; registra la de los handles nuevos (INSERT OR IGNORE: nunca se pisa)."""
    try:
        import bluesky_pool as pool
        db = pool.connect()
    except Exception as exc:
        c.issues.append(f"first_touch: {type(exc).__name__}: {exc}")
        return {}
    try:
        handles = [item["handle"] for item in items]
        stored = pool.first_touch(db, handles)
        new = {
            item["handle"]: item["source_order"][0]
            for item in items if item["handle"] not in stored and item.get("source_order")
        }
        if new:
            pool.record_touch(db, new, c.today.isoformat())
        return {**new, **stored}
    except Exception as exc:
        c.issues.append(f"first_touch: {type(exc).__name__}: {exc}")
        return {}
    finally:
        db.close()


def _build_output(c):
    for item in c.candidates.values():
        item["score"] = _profile_score(c, item)

    profile_limit = int(c.config["shortlist"]["profiles"])
    ranked = _select_shortlist_candidates(c, profile_limit)
    shortlist = []
    auto_plan = []
    posts_per = int(c.config["shortlist"]["posts_per_profile"])
    # Umbrales de auto-aprobacion mecanica (29/09): un candidato/post que ya
    # puntua muy por encima de lo normal no necesita que la IA lo revise uno
    # a uno - la puntuacion ya incorpora bio/afinidad/politica/spam via
    # _profile_score. Por debajo del umbral, sigue yendo al shortlist para
    # revision real. float('inf') si el config no trae la clave (compat con
    # fixtures de test antiguas) desactiva la automatizacion, nunca la fuerza.
    auto_follow_min = float(
        c.config["shortlist"].get("auto_follow_score_min", float("inf"))
    )
    auto_like_min = float(
        c.config["shortlist"].get("auto_like_score_min", float("inf"))
    )

    first_touch = _first_touch_map(c, ranked[:profile_limit])
    _persist_candidates(c)
    repost_pool = []

    def _src(item, *groups):
        """Procedencia (05/10): fuente FIRST-TOUCH inmutable del candidato (la primera por la que el scan lo vio, guardada en la reserva) seguida de hasta 2 mas.
        GPT (consulta E): ordenar alfabeticamente destruia el orden real y un Jetstream posterior convertia un seed_liker en «Jetstream»."""
        names = []
        first = first_touch.get(item["handle"]) or next(iter(item.get("source_order") or ()), None)
        for group in ([[first]] if first else []) + [sorted(group or ()) for group in groups]:
            for name in group:
                label = str(name)[:40].replace(":", "/").replace("+", "_")
                if label not in names:
                    names.append(label)
        return "+".join(names[:3]) or "desconocida"   # hasta 3 rutas por las que llego (la atribucion usa la primera)

    for index, item in enumerate(ranked[:profile_limit], start=1):
        cid = f"G{index:03d}"
        profile = item.get("profile") or {}
        post_rows = []
        posts = sorted(
            (c.posts[uri] for uri in item["posts"] if uri in c.posts),
            key=lambda post: (
                1 if (
                    _days_since(post.get("seen_date"), c.today) is not None
                    and _days_since(post.get("seen_date"), c.today)
                    <= int(c.config["shortlist"].get("acquisition_cooldown_days", 3))
                ) else 0,
                _age_bucket(post, c.today),
                -_hits(post["text"]),
                -(post["replies"] + post["likes"] + post["reposts"]),
                post["url"],
            ),
        )
        for pidx, post in enumerate(posts[:posts_per], start=1):
            actions = _post_actions(c, item, post)
            if "repost" in actions and _repost_worthy(c, item, post):
                repost_pool.append((item["score"] + 2 * min(_hits(post["text"]), 3), item["handle"], post["url"],
                                    f"growth:auto_repost:score={item['score']}:src={_src(item, post['sources'], item['sources'])}",
                                    _relationship_lane(item)))
            post_rows.append({
                "id": f"{cid}-P{pidx}",
                "uri": post["uri"],
                "url": post["url"],
                "text": post["text"][:280],
                "created_at": post.get("created_at") or "",
                "es": _spanish_post(post),
                "stats": {
                    "likes": post["likes"],
                    "reposts": post["reposts"],
                    "replies": post["replies"],
                    "quotes": post["quotes"],
                    "bookmarks": post.get("bookmarks", 0),
                },
                "sources": sorted(post["sources"]),
                "actions": actions,
            })
            # Automatizar likes de relaciones ya existentes/reciprocidad, o de
            # un post cuya puntuacion ya es alta de por si (auto_like_min).
            if "like" in actions and item.get("known_date"):
                auto_plan.append({
                    "handle": item["handle"],
                    "kind": "like",
                    "lane": "community",
                    "url": post["url"],
                    "motivo": f"growth:auto_like:lane=community:relacion_existente:src={_src(item, post['sources'], item['sources'])}",
                })
            elif (
                "like" in actions
                and item.get("notification_unread")
                and (
                    _days_since(item.get("last_notification_at"), c.today)
                    is not None
                )
                and _days_since(item.get("last_notification_at"), c.today) <= 1
            ):
                auto_plan.append({
                    "handle": item["handle"],
                    "kind": "like",
                    "lane": "community",
                    "url": post["url"],
                    "motivo": f"growth:auto_like:lane=community:reciprocidad:src={_src(item, post['sources'], item['sources'])}",
                })
            elif (
                "like" in actions
                and item["score"] >= auto_like_min
                # 02/10: sin esta guarda el like automatico por score llego a
                # cuentas fuera de nicho (un periodico estadounidense, un blog
                # de beisbol): el score es de la cuenta, no de este post.
                and (
                    _hits(post["text"]) > 0
                    or (
                        # 05/10: un like por la bio sola llegaba a politica, noticias y chistes de cuentas que son del nicho: exige bio con >=2 terminos y
                        # que el post no sea activismo (el filtro politico de `add_post` es conservador pero no cubre todo)
                        int(item.get("bio_hits") or 0) >= 2
                        and not post.get("is_reply")      # un comentario suelto en un hilo ajeno («Qué cool!») no aporta nada si el post no es del nicho
                        and not sc.looks_activist(post["text"])
                    )
                )
            ):
                auto_plan.append({
                    "handle": item["handle"],
                    "kind": "like",
                    "lane": _relationship_lane(item),
                    "url": post["url"],
                    "motivo": f"growth:auto_like:score={item['score']}:umbral_mecanico:src={_src(item, post['sources'], item['sources'])}",
                })

        candidate_actions = []
        if item.get("following") is False and item["score"] >= 3.0:
            candidate_actions.append("follow")
        if any(row["actions"] for row in post_rows):
            candidate_actions.append("interact")

        follow_cap = gp.follow_max_followers(c.config)
        followers_count = profile.get("followersCount")
        if (
            "follow" in candidate_actions
            and item["score"] >= auto_follow_min
            and not (followers_count is not None and int(followers_count) > follow_cap)   # cuentas enormes casi nunca devuelven el follow; el like si les vale
            and (_relationship_lane(item) == "community" or _spanish_account(c, item) is not False)
        ):
            auto_plan.append({
                "handle": item["handle"],
                "kind": "follow",
                "lane": _relationship_lane(item),
                "motivo": f"growth:auto_follow:score={item['score']}:umbral_mecanico:src={_src(item, item['sources'])}",
            })

        shortlist.append({
            "id": cid,
            "did": profile.get("did") if isinstance(profile.get("did"), str) else None,
            "lane": _relationship_lane(item),
            "handle": item["handle"],
            "score": item["score"],
            "known_date": item.get("known_date"),
            "following": item.get("following"),
            "known_followers": int(item.get("known_followers_count") or 0),
            "sources": sorted(item["sources"]),
            "signals": list(dict.fromkeys(item["signals"]))[:5],
            "profile": {
                "display_name": profile.get("displayName") or "",
                "bio": (profile.get("description") or "")[:260],
                "followers": profile.get("followersCount"),
                "following": profile.get("followsCount"),
                "posts": profile.get("postsCount"),
            },
            "actions": candidate_actions,
            "posts": post_rows,
        })

    # Reposts automaticos (05/10, consulta E: 1,5-3 % del volumen, nunca cientos): un repost altera el feed de David y avisa al autor, asi que solo posts
    # claramente del nicho, en espanol, de cuentas pequenas, con tope por ronda (`auto_repost_per_round`; 0 = desactivado) y una sola por cuenta.
    repost_cap = int(c.config["shortlist"].get("auto_repost_per_round", 0))
    reposted_handles = set()
    for _, handle, url, motivo, lane in sorted(repost_pool, key=lambda row: (-row[0], row[1])):
        if len(reposted_handles) >= repost_cap:
            break
        if handle in reposted_handles:
            continue
        reposted_handles.add(handle)
        auto_plan.append({"handle": handle, "kind": "repost", "lane": lane, "url": url, "motivo": motivo})
    # El ejecutor rechaza TODO el lote si un post lleva dos interacciones (like + repost): 05/10 la ronda de las 17:55 (428 acciones) no ejecuto nada por esto.
    # El repost ya es la interaccion; se quita el like de ese post.
    reposted_urls = {a["url"] for a in auto_plan if a["kind"] == "repost"}
    auto_plan[:] = [a for a in auto_plan if not (a["kind"] == "like" and a.get("url") in reposted_urls)]

    # Dedupe auto_plan. Los "like" tienen url (dedupe por post); "follow" es
    # una relacion sin url (dedupe por handle+kind) - antes de auto_follow_min
    # todo lo que llegaba aqui era like, por eso el dedupe solo miraba url.
    deduped_auto = []
    seen_keys = set()
    for action in auto_plan:
        key = ("url", action["url"]) if "url" in action else (
            "handle", action["kind"], action["handle"]
        )   # un post recibe UNA interaccion (el ejecutor rechaza el lote si no)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_auto.append(action)

    # Siguiente ejecución del listener dirigido: primero co-likers corroborados,
    # después suscripciones/follows explícitos afines como cold-start.
    listener_limit = int(c.config["budgets"]["taste_listener_dids"])
    listeners = []
    seen_dids = set()
    for did, count in sorted(
        c.coliker_counts.items(),
        key=lambda pair: (-pair[1], pair[0]),
    ):
        if did == c.own_did or did in seen_dids:
            continue
        listeners.append({
            "did": did,
            "reason": "co_liker",
            "weight": int(count),
        })
        seen_dids.add(did)
        if len(listeners) >= listener_limit:
            break

    if len(listeners) < listener_limit:
        fallback = sorted(
            (
                item for item in c.candidates.values()
                if (
                    "activity_subscription" in item.get("sources", set())
                    or "own_following" in item.get("sources", set())
                )
                and not item.get("excluded_reason")
            ),
            key=lambda item: (-_pre_score(item), item["handle"]),
        )
        for item in fallback:
            profile = item.get("profile") or {}
            did = profile.get("did")
            if (
                not isinstance(did, str)
                or not did.startswith("did:")
                or did == c.own_did
                or did in seen_dids
            ):
                continue
            reason = (
                "activity_subscription"
                if "activity_subscription" in item.get("sources", set())
                else "following"
            )
            listeners.append({
                "did": did,
                "reason": reason,
                "weight": round(_pre_score(item), 2),
            })
            seen_dids.add(did)
            if len(listeners) >= listener_limit:
                break

    selected_items = ranked[:profile_limit]
    acq_cooldown = int(
        c.config["shortlist"].get("acquisition_cooldown_days", 3)
    )
    lane_totals = {
        "community": sum(
            1 for item in selected_items
            if _relationship_lane(item) == "community"
        ),
        "acquisition": sum(
            1 for item in selected_items
            if _relationship_lane(item) == "acquisition"
        ),
        "fresh_acquisition": sum(
            1 for item in selected_items
            if _relationship_lane(item) == "acquisition"
            and (
                _days_since(item.get("seen_date"), c.today) is None
                or _days_since(item.get("seen_date"), c.today) > acq_cooldown
            )
        ),
    }
    opportunity_counts = defaultdict(int)
    for candidate in shortlist:
        for action in candidate.get("actions") or []:
            opportunity_counts[action] += 1
        for post in candidate.get("posts") or []:
            for action in post.get("actions") or []:
                opportunity_counts[action] += 1
    acquisition_target = min(
        profile_limit,
        int(c.config["shortlist"].get("acquisition_min", profile_limit)),
    )
    readiness = {
        "acquisition_target": acquisition_target,
        "acquisition_candidates": lane_totals["acquisition"],
        "fresh_acquisition_candidates": lane_totals["fresh_acquisition"],
        "fresh_target_met": (
            lane_totals["fresh_acquisition"] >= acquisition_target
        ),
        "opportunities": dict(opportunity_counts),
    }

    if c.write_metrics:
        _append_seen(
            SEEN_CSV,
            date=c.today.isoformat(),
            run_id=c.run_id,
            shortlist=shortlist,
        )

    source_summary = {
        f"{surface}:{key}": {
            "fetched": row["fetched"],
            "accepted": row["accepted"],
            "new_handles": len(row["new_handles"]),
        }
        for (surface, key), row in c.source_stats.items()
    }
    return {
        "run_id": c.run_id,
        "date": c.today.isoformat(),
        "budget": c.budget.snapshot(),
        "coverage": c.coverage(),
        "totals": {
            "profiles_seen": len(c.candidates),
            "posts_seen": len(c.posts),
            "shortlist": len(shortlist),
            "auto_plan": len(deduped_auto),
            "community": lane_totals["community"],
            "acquisition": lane_totals["acquisition"],
            "fresh_acquisition": lane_totals["fresh_acquisition"],
        },
        "readiness": readiness,
        "auto_plan": deduped_auto,
        "taste_listener_dids": listeners,
        "shortlist": shortlist,
        "source_metrics": source_summary,
        "issues": c.issues,
    }


def run(*, config_path=CONFIG_PATH, write_metrics=True, today=None):
    config = _load_config(config_path)
    c = Collector(config, write_metrics=write_metrics, today=today)

    ok, msg, profile = c.call("health", b._health_check)
    if not ok:
        raise RuntimeError(msg)
    c.own_handle = profile["handle"].casefold()
    c.own_did = profile.get("did")
    c.own_reply_parents = c.call(
        "own_history", b._own_reply_parent_uris
    )

    # Fase 1: cobertura base. Aquí todavía no protegemos reserva: estas fuentes
    # definen el universo inicial y deben ejecutarse antes de expandir ramas.
    try:
        _load_relationship_exclusions(c)
        _initial_discovery(c)
        _expand_dynamic_tags(c)
    except gc.ReadBudgetExceeded as exc:
        c.issues.append(str(exc))

    # Fase 2: expansión larga. Se detiene cuando toca preservar el vetting.
    c.protect_review_budget = True
    try:
        valued = sorted(
            (
                post for post in c.posts.values()
                if post.get("sources", set()) & {
                    "valued_history", "bookmark", "own_like"
                }
            ),
            key=lambda post: (-_seed_post_score(post), post["url"]),
        )[: int(config["budgets"]["valued_history_seeds"])]
        _expand_threads(c, valued)
        _expand_engagers(c, valued, track_colikers=True)
        valued_uris = {post["uri"] for post in valued}

        seed_limit = max(
            int(config["budgets"]["thread_seeds"]),
            int(config["budgets"]["engager_seeds"]),
        )
        seed_posts = _diverse_seed_posts(
            (
                post for post in c.posts.values()
                if post["uri"] not in valued_uris
            ),
            seed_limit,
        )
        _expand_threads(
            c,
            seed_posts[: int(config["budgets"]["thread_seeds"])],
        )
        _expand_engagers(
            c,
            seed_posts[: int(config["budgets"]["engager_seeds"])],
        )
        _expand_similar_accounts(c)
        _expand_graph_neighbors(c)
        _expand_starter_packs(c)
        _explore_custom_feeds(c)
    except ReviewReserveReached as exc:
        c.issues.append(str(exc))
    except gc.ReadBudgetExceeded as exc:
        c.issues.append(str(exc))
    finally:
        c.protect_review_budget = False

    # Fase 3: revisar perfiles. Esta fase consume la reserva protegida.
    try:
        _hydrate_profiles(c)
        _expand_joined_starter_packs(c)
        _enrich_known_followers(c)
        _vet_author_feeds(c)
        # Núcleo de captación antes de menús/extras: no dejar que listas/feeds
        # consuman la reserva que necesita el paseo multi-ola.
        _expand_second_wave(c)
        _hydrate_profiles(c)
        _vet_shortlist_gaps(c)
        _refresh_post_actionability(c)
    except gc.ReadBudgetExceeded as exc:
        c.issues.append(str(exc))

    # Fase 4: extras solo si quedó margen después del vetting.
    c.protect_review_budget = False
    try:
        _expand_actor_menus(c)
        _explore_custom_feeds(c)
        _search_popular_feeds(c)
        _discover_trending_topics(c)
        # Los extras pueden introducir nuevos perfiles/posts; enriquecerlos solo
        # si queda presupuesto. Si no, el núcleo ya quedó revisado arriba.
        _hydrate_profiles(c)
        _refresh_post_actionability(c)
    except gc.ReadBudgetExceeded as exc:
        c.issues.append(str(exc))

    return _build_output(c)


def ai_view(result):
    """Vista compatible actual: sin métricas detalladas de auditoría."""
    keys = (
        "run_id", "date", "budget", "coverage", "totals", "readiness",
        "auto_plan", "shortlist", "issues",
    )
    return {key: result[key] for key in keys if key in result}


def compact_ai_view(result):
    """Vista mínima para que la IA decida sin cargar datos de ejecución.

    URLs, sources y auto_plan se conservan únicamente en el state completo que usa
    bluesky_build_plan.py. La IA responde por Gxxx/Gxxx-Px.
    """
    compact_profiles = []
    for candidate in result.get("shortlist") or []:
        profile = candidate.get("profile") or {}
        posts = []
        for post in candidate.get("posts") or []:
            stats = post.get("stats") or {}
            posts.append({
                "id": post.get("id"),
                "text": post.get("text"),
                "actions": post.get("actions") or [],
                "eng": [
                    int(stats.get("likes") or 0),
                    int(stats.get("reposts") or 0),
                    int(stats.get("replies") or 0),
                    int(stats.get("quotes") or 0),
                    int(stats.get("bookmarks") or 0),
                ],
            })
        compact_profiles.append({
            "id": candidate.get("id"),
            "lane": candidate.get("lane"),
            "handle": candidate.get("handle"),
            "score": candidate.get("score"),
            "signals": candidate.get("signals") or [],
            "profile": {
                "name": profile.get("display_name") or "",
                "bio": profile.get("bio") or "",
                "followers": profile.get("followers"),
                "following": profile.get("following"),
            },
            "actions": candidate.get("actions") or [],
            "posts": posts,
        })

    budget = result.get("budget") or {}
    coverage = result.get("coverage") or {}
    totals = result.get("totals") or {}
    return {
        "run_id": result.get("run_id"),
        "date": result.get("date"),
        "budget": {
            "used": budget.get("used"),
            "max": budget.get("maximum"),
            "remaining": budget.get("remaining"),
        },
        "coverage_missing": coverage.get("missing") or [],
        "totals": {
            "profiles_seen": totals.get("profiles_seen"),
            "posts_seen": totals.get("posts_seen"),
            "shortlist": totals.get("shortlist"),
            "community": totals.get("community"),
            "acquisition": totals.get("acquisition"),
            "fresh_acquisition": totals.get("fresh_acquisition"),
        },
        "readiness": result.get("readiness") or {},
        "auto_plan_count": int(totals.get("auto_plan") or 0),
        "shortlist": compact_profiles,
        "issues": result.get("issues") or [],
        "eng_order": ["likes", "reposts", "replies", "quotes", "bookmarks"],
    }



def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--ai-json",
        action="store_true",
        help="vista mínima para IA; usar con --state-out para el builder",
    )
    parser.add_argument("--audit-json", action="store_true")
    parser.add_argument("--state-out")
    parser.add_argument("--no-metrics", action="store_true")
    parser.add_argument("--config", default=CONFIG_PATH)
    args = parser.parse_args(argv)
    try:
        result = run(
            config_path=args.config,
            write_metrics=not args.no_metrics,
        )
    except Exception as exc:
        payload = {"error": f"{type(exc).__name__}: {exc}"}
        if args.json or args.ai_json or args.audit_json:
            print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        else:
            print(payload["error"])
        return 2

    if args.state_out:
        with open(args.state_out, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")

    if args.audit_json:
        payload = result
    elif args.ai_json:
        payload = compact_ai_view(result)
    else:
        payload = ai_view(result)

    if args.json or args.ai_json or args.audit_json:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
