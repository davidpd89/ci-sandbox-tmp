"""Exploración API amplia para la ronda de crecimiento de Mastodon.

La lectura y expansión del grafo se resuelven mecánicamente; la IA recibe una
vista compacta con identificadores para elegir acciones editoriales. Este módulo
no ejecuta escrituras.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
import uuid
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import mastodon_interact as m
import mastodon_stream_collect as stream_cache
import scan_common as sc
import growth_policy as gp

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON")
CONFIG_PATH = os.path.join(ROOT, "growth_config.json")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICS_CSV = os.path.join(ROOT, "discovery_metrics.csv")
SEEN_CSV = os.path.join(ROOT, "growth_seen.csv")


class ReadBudgetExceeded(RuntimeError):
    pass


def _norm(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(ch for ch in value if not unicodedata.combining(ch)).split())


def _hits(text, terms):
    value = _norm(text)
    total = 0
    for term in terms:
        normalized = _norm(term)
        if not normalized:
            continue
        if " " in normalized:
            total += normalized in value
        else:
            total += bool(re.search(rf"(?<![\w]){re.escape(normalized)}(?![\w])", value))
    return total


def _load_config(path):
    with open(path, encoding="utf-8") as stream:
        config = json.load(stream)
    if config.get("version") != 1:
        raise RuntimeError("growth_config.json: versión no soportada")
    if os.path.abspath(path) == os.path.abspath(CONFIG_PATH):
        try:   # 05/10: la rampa de volumen (volume_ramp.py) sube las palancas por etapas, igual que en Bluesky
            import volume_ramp
            config = volume_ramp.overlay_mastodon(config)
        except Exception:
            pass
    return config


def _load_seen(path, *, today, days):
    seen = {}
    if not os.path.exists(path) or not os.path.getsize(path):
        return seen
    cutoff = today - dt.timedelta(days=max(0, int(days)))
    with open(path, encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            try:
                date = dt.date.fromisoformat((row.get("fecha") or "")[:10])
            except ValueError:
                continue
            acct = (row.get("acct") or "").strip().casefold()
            if acct and date >= cutoff and (acct not in seen or date > seen[acct]):
                seen[acct] = date
    return seen


def _load_metrics(path, *, today, days):
    metrics = {}
    if not os.path.exists(path) or not os.path.getsize(path):
        return metrics
    cutoff = today - dt.timedelta(days=max(0, int(days)))
    with open(path, encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            try:
                date = dt.date.fromisoformat((row.get("fecha") or "")[:10])
                fetched = int(row.get("fetched") or 0)
                accepted = int(row.get("accepted") or 0)
                fresh = int(row.get("new_accounts") or 0)
            except (ValueError, TypeError):
                continue
            if date < cutoff:
                continue
            key = (row.get("surface") or "", row.get("key") or "")
            item = metrics.setdefault(key, {
                "runs": 0, "fetched": 0, "accepted": 0,
                "new_accounts": 0, "last_date": None,
            })
            item["runs"] += 1
            item["fetched"] += fetched
            item["accepted"] += accepted
            item["new_accounts"] += fresh
            if item["last_date"] is None or date > item["last_date"]:
                item["last_date"] = date
    return metrics


def _rank_queries(queries, metrics, surface, today):
    def score(query):
        row = metrics.get((surface, query))
        if not row:
            return (0, 0.0, query)
        age = (today - row["last_date"]).days if row["last_date"] else 999
        denominator = max(1, row["fetched"])
        yield_rate = (row["accepted"] + 2 * row["new_accounts"]) / denominator
        return (1 if age == 0 else 0, -yield_rate - min(age, 30) / 100, query)
    return sorted(dict.fromkeys(str(q) for q in queries), key=score)


def _append_csv(path, header, rows):
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        if not exists:
            writer.writerow(header)
        writer.writerows(rows)


class Collector:
    def __init__(self, config, *, today=None, write_metrics=True, run_id=None):
        m.set_priority("scan")                  # 06/10: las lecturas del scan dejan siempre margen de cupo (mastodon_budget.py) a quien escribe en otro proceso
        self.config = config
        self.today = today or dt.date.today()
        self.run_id = run_id or f"{self.today.isoformat()}-{uuid.uuid4().hex[:8]}"
        budgets = config["budgets"]
        self.maximum = int(budgets["max_read_requests"])
        self.reads = 0
        # Pacing real por rate-limit (29/09, a peticion explicita de David:
        # "se pueden hacer aunque tarden no pasa nada al ser una api, configuras
        # tiempos y listo"). mastodon.social da 300 peticiones/5min reales via
        # cabeceras X-RateLimit-* - antes el scan solo reaccionaba a un 429 ya
        # disparado; ahora espera de forma proactiva cuando la cuota real esta
        # a punto de agotarse, en vez de cortar el scan entero a mitad.
        self.rate_limit_safety_margin = int(budgets.get("rate_limit_safety_margin", 5))
        self.rate_limit_max_wait_seconds = int(
            budgets.get("rate_limit_max_wait_seconds", 310)
        )
        self.paced_seconds = 0.0
        self.current_surface = "health"
        self.surfaces = set()
        self.write_metrics = write_metrics
        self.known = {
            str(handle).lstrip("@").casefold(): date
            for handle, date in sc.known_accounts(REGISTRO_CSV).items()
        }
        self.discarded = {
            str(handle).lstrip("@").casefold()
            for handle in sc.discarded_handles(REGISTRO_CSV)
        }
        discovery = config["discovery"]
        self.seen = _load_seen(
            SEEN_CSV,
            today=self.today,
            days=discovery.get("seen_days", 7),
        )
        self.metrics = _load_metrics(
            METRICS_CSV,
            today=self.today,
            days=discovery.get("metric_days", 30),
        )
        self.candidates = {}
        self.posts = {}
        self.source_stats = defaultdict(
            lambda: {"fetched": 0, "accepted": 0, "new_accounts": set()}
        )
        self.issues = []
        self.exhausted = False
        self.own = None
        self.own_id = None
        self._request_hook_prev = None

    def _before_request(self, _url):
        if self.exhausted:
            raise ReadBudgetExceeded("scan detenido tras rate limit o fallo de autenticación")
        if self.reads >= self.maximum:
            self.exhausted = True
            raise ReadBudgetExceeded(
                f"presupuesto de lectura agotado ({self.reads}/{self.maximum})"
            )
        self._pace_for_rate_limit()
        self.reads += 1

    def _pace_for_rate_limit(self):
        """Si la cuota real que reporta mastodon.social esta a punto de
        agotarse, esperar hasta que la ventana se renueve en vez de seguir
        pidiendo hasta un 429 real. Solo actua sobre datos reales (cabeceras
        de la ultima respuesta) - sin cabeceras todavia (primera peticion del
        proceso) no hace nada."""
        snapshot = m.rate_limit_snapshot()
        remaining = snapshot.get("remaining")
        reset = snapshot.get("reset")
        if remaining is None or reset is None or remaining > self.rate_limit_safety_margin:
            return
        wait_seconds = (reset - dt.datetime.now(dt.timezone.utc)).total_seconds()
        if wait_seconds <= 0:
            return
        wait_seconds = min(wait_seconds, self.rate_limit_max_wait_seconds) + 2
        self.issues.append(
            f"pacing: cuota real casi agotada ({remaining} restantes) - "
            f"esperando {wait_seconds:.0f}s a que la ventana se renueve"
        )
        self.paced_seconds += wait_seconds
        time.sleep(wait_seconds)

    def use_surface(self, name):
        self.current_surface = name
        self.surfaces.add(name)

    def _account(self, account, source, key=""):
        if not isinstance(account, dict):
            return None
        acct = str(account.get("acct") or "").strip().casefold()
        if not acct or _is_own_acct(self, acct) or acct in self.discarded:
            return None
        if sc.is_feed_bridge(acct):
            return None
        if sc.is_political(m._plain_text(account.get("note", ""))):
            return None
        if len(self.candidates) >= int(self.config["budgets"]["max_candidates"]):
            return None
        item = self.candidates.setdefault(acct, {
            "acct": acct,
            "account_id": str(account.get("id") or ""),
            "display_name": m._plain_text(account.get("display_name", "")),
            "bio": m._plain_text(account.get("note", "")),
            "followers": int(account.get("followers_count") or 0),
            "following_count": int(account.get("following_count") or 0),
            "statuses_count": int(account.get("statuses_count") or 0),
            "last_status_at": account.get("last_status_at"),
            "locked": bool(account.get("locked")),
            "bot": bool(account.get("bot")),
            "sources": set(),
            "source_keys": set(),
            "posts": set(),
            "known_date": self.known.get(acct) or (self.known.get(acct.split("@")[0]) if "@" in acct else None),   # el registro guarda las cuentas de otras instancias sin host
            "seen_date": self.seen.get(acct),
            "following": False,
            "followed_by": False,
            "blocked": False,
            "muting": False,
            "source_order": [],
        })
        # Refrescar datos ligeros si un endpoint devuelve una cuenta más completa.
        for key_name, value in (
            ("account_id", account.get("id")),
            ("display_name", m._plain_text(account.get("display_name", ""))),
            ("bio", m._plain_text(account.get("note", ""))),
            ("followers", account.get("followers_count")),
            ("following_count", account.get("following_count")),
            ("statuses_count", account.get("statuses_count")),
            ("last_status_at", account.get("last_status_at")),
            ("locked", account.get("locked")),
            ("bot", account.get("bot")),
        ):
            if value is not None:
                item[key_name] = value
        item["sources"].add(source)
        if source not in item.setdefault("source_order", []):
            item["source_order"].append(source)      # orden real de llegada: la primera es la fuente first-touch
        if key:
            item["source_keys"].add(f"{source}:{key}")
        return item

    def add_status(self, status, source, key=""):
        if not isinstance(status, dict):
            return False
        if status.get("reblog") and isinstance(status["reblog"], dict):
            status = status["reblog"]
        account = status.get("account") or {}
        acct = str(account.get("acct") or "").strip().casefold()
        status_id = str(status.get("id") or "")
        url = status.get("url") or status.get("uri")
        visibility = status.get("visibility")
        text = m._plain_text(status.get("content", ""))
        if not acct or not status_id or not url or not text:
            return False
        if visibility not in {"public", "unlisted"}:
            return False
        if status.get("sensitive") or status.get("spoiler_text"):
            # Mantener como hallazgo solo si tiene afinidad; no proponer respuesta.
            if not _hits(text, self.config["niche_terms"]):
                return False
        if acct in self.discarded or sc.is_political(text):
            return False
        if not _hits(text + " " + m._plain_text(account.get("note", "")), self.config["niche_terms"]):
            return False
        own_post = _is_own_acct(self, acct)
        item = None if own_post else self._account(account, source, key)
        if own_post:
            # El post propio es una semilla de conversación/engagers, nunca un
            # perfil que se propone seguir o incluir en el shortlist.
            item = self.candidates.get(acct)
        if not own_post and item is None:
            return False
        if item is not None:
            item["posts"].add(status_id)
        post = self.posts.get(status_id)
        if post is None:
            post = {
                "id": status_id,
                "url": url,
                "acct": acct,
                "text": text,
                "visibility": visibility,
                "sensitive": bool(status.get("sensitive") or status.get("spoiler_text")),
                "created_at": status.get("created_at") or "",
                "language": str(status.get("language") or "").casefold(),
                "replies": int(status.get("replies_count") or 0),
                "favourites": int(status.get("favourites_count") or 0),
                "boosts": int(status.get("reblogs_count") or 0),
                "quotes": int(status.get("quotes_count") or 0),
                "favourited": bool(status.get("favourited")),
                "reblogged": bool(status.get("reblogged")),
                "tags": [
                    str(tag.get("name") or "").lstrip("#")
                    for tag in status.get("tags", [])
                    if isinstance(tag, dict) and tag.get("name")
                ],
                "sources": set(),
                "source_keys": set(),
            }
            self.posts[status_id] = post
        post["sources"].add(source)
        if key:
            post["source_keys"].add(key)
        # REST responses may include viewer state. It overrides public-stream
        # snapshots so we do not suggest an existing favourite/boost.
        for field in ("favourited", "reblogged"):
            if field in status:
                post[field] = bool(status.get(field))
        return True

    def add_account(self, account, source, key=""):
        return self._account(account, source, key) is not None

    def collect(self, surface, key, producer, consumer):
        if self.exhausted:
            return []
        self.use_surface(surface)
        before = set(self.candidates)
        try:
            result = m.patient(producer, waits=3, priority="scan")       # 06/10: un 429 (cupo gastado por algo ajeno) se espera, no corta la superficie
        except ReadBudgetExceeded as exc:
            self.issues.append(str(exc))
            self.exhausted = True
            return []
        except m.MastodonRateLimitExceeded as exc:
            self.issues.append(f"rate_limit: {exc}; retry_after={exc.retry_after}")
            self.exhausted = True
            return []
        except m.MastodonAPIError as exc:
            self.issues.append(f"{surface}:{key}: {exc}")
            if exc.status_code in (401, 403):
                self.exhausted = True
            return []
        except Exception as exc:
            self.issues.append(f"{surface}:{key}: {type(exc).__name__}: {exc}")
            return []
        rows = list(result or [])
        accepted = sum(1 for row in rows if consumer(row))
        self.source_stats[(surface, str(key))]["fetched"] += len(rows)
        self.source_stats[(surface, str(key))]["accepted"] += accepted
        self.source_stats[(surface, str(key))]["new_accounts"].update(
            set(self.candidates) - before
        )
        return rows


def _walk_statuses(value):
    if isinstance(value, dict):
        if isinstance(value.get("id"), (str, int)) and isinstance(value.get("account"), dict):
            yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _walk_statuses(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_statuses(child)


def _query_selection(c):
    count = int(c.config["coverage"]["post_queries_per_round"])
    grouped = []
    for family in c.config["query_families"]:
        family_name = family["name"]
        for query in _rank_queries(
            family["queries"], c.metrics, f"post_search:{family_name}", c.today
        ):
            grouped.append((family_name, query))
    # Una selección intercalada evita que una familia ocupe toda la ronda.
    selected = []
    offsets = defaultdict(int)
    while len(selected) < count:
        added = False
        for family in c.config["query_families"]:
            name = family["name"]
            queries = [q for fam, q in grouped if fam == name]
            if offsets[name] < len(queries):
                selected.append((name, queries[offsets[name]]))
                offsets[name] += 1
                added = True
                if len(selected) >= count:
                    break
        if not added:
            break
    return selected


def _tag_selection(c, discovered=()):
    counts = defaultdict(int)
    for tag in discovered:
        normalized = str(tag or "").strip().lstrip("#")
        if normalized:
            counts[normalized.casefold()] += 1
    emerging = [
        tag for tag in dict.fromkeys(str(x).strip().lstrip("#") for x in discovered)
        if tag and (counts[tag.casefold()] >= 2 or _hits(tag, c.config["niche_terms"]) > 0)
    ]
    emerging.sort(key=lambda tag: (-counts[tag.casefold()], tag.casefold()))
    pool = list(dict.fromkeys(str(tag).lstrip("#") for tag in c.config.get("hashtags", [])))
    ranked = _rank_queries(pool, c.metrics, "hashtag", c.today)
    limit = int(c.config["coverage"]["hashtags_per_round"])
    # Reservar parte del lote para etiquetas emergentes; el resto rota y aprende
    # rendimiento de etiquetas configuradas sin volver el set determinista/pobre.
    emerging_slots = min(max(0, limit // 3), len(emerging))
    selected = emerging[:emerging_slots]
    selected_set = {tag.casefold() for tag in selected}
    selected.extend(tag for tag in ranked if tag.casefold() not in selected_set)
    return selected[:limit]


def _is_fresh(c, acct):
    return acct not in c.known and acct not in c.seen


def _is_own_acct(c, acct):
    own = str(c.own or "").casefold()
    acct = str(acct or "").casefold()
    return bool(own and acct in {own, f"{own}@mastodon.social"})


def _source_metric_rows(c):
    for (surface, key), row in c.source_stats.items():
        fresh = sum(1 for acct in row["new_accounts"] if _is_fresh(c, acct))
        yield [
            c.today.isoformat(), c.run_id, surface, key,
            row["fetched"], row["accepted"], fresh,
        ]


def _rank_profile(c, item):
    score = len(item["sources"]) * 1.25
    score += min(5, _hits(item["bio"], c.config["niche_terms"])) * 0.65
    score += min(4, len(item["posts"])) * 0.3
    if item["followed_by"]:
        score += 2.0
    if item["following"]:
        score -= 0.5
    if item["bot"]:
        score -= 2.0
    if item["locked"]:
        score -= 0.25
    if item["seen_date"]:
        age = max(0, (c.today - item["seen_date"]).days)
        if age < 3:
            score -= 1.0
    for status_id in item["posts"]:
        post = c.posts.get(status_id)
        if post:
            score += min(4, _hits(post["text"], c.config["niche_terms"])) * 0.25
            score += min(3, post["replies"]) * 0.25
            score += min(12, post["favourites"]) * 0.035
            score += min(8, post["boosts"]) * 0.06
    return round(score, 3)


def _spanish_post(post):
    """True/False/None. El campo `language` del estado (lo declara el autor o lo detecta la instancia) manda; sin el, heuristica de palabras funcionales."""
    language = post.get("language") or ""
    if language:
        return language == "es" or language.startswith("es-")
    import text_common as bp
    text = post.get("text") or ""
    if len(text.split()) < 4:
        return None
    return bp.looks_spanish(text)


def _post_actions(item, post, lane="community", today=None, config=None):
    """Acciones posibles sobre un estado. A un lector NUEVO (lane acquisition) solo se le escribe en su idioma y sobre estados recientes (05/10, como en Bluesky):
    el scan ofrecia favoritos a estados en otros idiomas y de hace meses."""
    actions = []
    if post["visibility"] in {"public", "unlisted"} and not post["sensitive"]:
        # 06/10: el 38 % de los favoritos del plan eran a estados en otros idiomas: el filtro de idioma solo cubria a lectores NUEVOS y la comunidad (cuentas que ya seguimos,
        # sobre todo de Bookstodon en ingles) lo saltaba. Desde el 06/10 (David) el filtro es total: solo espanol, tambien con quien ya nos sigue.
        if _spanish_post(post) is False:        # 06/10 (David): solo espanol, tambien a la comunidad y a quien ya nos sigue
            return []
        limit = gp.max_post_age_days(config, lane)
        try:
            age = ((today or dt.date.today()) - dt.date.fromisoformat(str(post.get("created_at") or "")[:10])).days
        except ValueError:
            age = None
        fresh = age is None or age <= limit
        if not post["favourited"] and fresh:
            actions.append("favourite")
        if not post["reblogged"]:
            actions.append("boost")
        actions.append("reply")
    return actions


def _expand_discovery(c):
    budgets = c.config["budgets"]
    discovery = c.config["discovery"]
    c.use_surface("conversation_replies")
    seeds = sorted(
        c.posts.values(),
        key=lambda post: (
            -(post["replies"] * 2 + post["favourites"] * 0.2 + post["boosts"] * 0.35),
            post["id"],
        ),
    )
    thread_limit = int(budgets["thread_seeds"])
    for seed in [row for row in seeds if row["replies"] > 0][:thread_limit]:
        if c.exhausted:
            break
        c.collect(
            "conversation_replies", seed["id"],
            lambda sid=seed["id"]: _walk_statuses(m.status_context(sid).get("descendants", [])),
            lambda status, sid=seed["id"]: c.add_status(status, "thread_commenter", sid),
        )

    engager_limit = int(budgets["engager_seeds"])
    c.use_surface("status_engagers")
    seeds = sorted(
        c.posts.values(),
        key=lambda post: (-(post["favourites"] + post["boosts"] * 1.5), post["id"]),
    )
    for seed in seeds[:engager_limit]:
        if c.exhausted:
            break
        for kind in ("favourites", "boosts", "quotes"):
            if c.exhausted:
                break
            if kind == "quotes" and not c.config.get("supports_quotes_endpoint", False):
                continue
            count_key = "favourites" if kind == "favourites" else "boosts"
            if kind != "quotes" and seed[count_key] <= 0:
                continue
            if kind == "quotes" and seed["quotes"] <= 0:
                continue
            c.collect(
                "status_engagers", f"{kind}:{seed['id']}",
                lambda sid=seed["id"], k=kind: m.status_engagers(
                    sid, k, max_pages=1,
                ),
                lambda account, k=kind, sid=seed["id"]: c.add_account(
                    account, "status_" + k, sid,
                ),
            )

    depth_limit = int(discovery["frontier_depth"])
    per_depth = int(discovery["second_wave_seeds"])
    visited = set()
    for depth in range(depth_limit):
        c.use_surface("author_statuses")
        frontier = []
        for item in sorted(
            c.candidates.values(),
            key=lambda x: (-_rank_profile(c, x), x["acct"]),
        ):
            if item["account_id"] and item["acct"] not in visited:
                frontier.append(item)
                visited.add(item["acct"])
                if len(frontier) >= per_depth:
                    break
        c.use_surface("author_statuses")
        for item in frontier:
            if c.exhausted:
                break
            c.collect(
                "author_statuses", item["acct"],
                lambda account_id=item["account_id"]: m.account_statuses(
                    account_id,
                    limit=int(budgets["profile_statuses"]),
                    max_pages=int(budgets["profile_status_pages"]),
                ),
                lambda status, acct=item["acct"]: c.add_status(
                    status, "author_status", acct,
                ),
            )
        if depth + 1 >= depth_limit or c.exhausted:
            break
        # New active posts discovered from authors open a bounded next wave.
        new_seeds = [
            post for post in c.posts.values()
            if post["id"] not in {x["id"] for x in seeds}
            and (post["replies"] or post["favourites"] or post["boosts"])
        ]
        for seed in sorted(new_seeds, key=lambda x: (-(x["replies"] + x["favourites"] + x["boosts"]), x["id"]))[:per_depth]:
            if c.exhausted:
                break
            c.collect(
                "conversation_replies", f"wave{depth + 2}:{seed['id']}",
                lambda sid=seed["id"]: _walk_statuses(m.status_context(sid).get("descendants", [])),
                lambda status, sid=seed["id"]: c.add_status(status, "thread_commenter", sid),
            )

    c.use_surface("account_neighbors")
    graph_limit = int(budgets["graph_seeds"])
    graph_seeds = sorted(
        c.candidates.values(),
        key=lambda x: (-_rank_profile(c, x), x["acct"]),
    )[:graph_limit]
    for item in graph_seeds:
        if c.exhausted:
            break
        for kind in ("followers", "following"):
            c.collect(
                "account_neighbors", f"{kind}:{item['acct']}",
                lambda account_id=item["account_id"], k=kind: m.account_neighbors(
                    account_id,
                    k,
                    limit=40,
                    max_pages=int(budgets["neighbor_pages"]),
                ),
                lambda account, k=kind, acct=item["acct"]: c.add_account(
                    account, f"{k}_neighbor", acct,
                ),
            )


def _hydrate_relationships(c):
    ids = list(dict.fromkeys(
        item["account_id"] for item in c.candidates.values()
        if item["account_id"]
    ))
    c.use_surface("relationships")
    for start in range(0, len(ids), 40):
        chunk = ids[start:start + 40]
        if c.exhausted:
            break
        try:
            rows = c.collect(
                "relationships", f"batch:{start // 40 + 1}",
                lambda ids=chunk: m._get("accounts/relationships", {"id[]": ids}),
                lambda _row: True,
            )
        except Exception as exc:  # pragma: no cover - collect already handles API failures
            c.issues.append(f"relationships: {exc}")
            continue
        for relation in rows:
            account_id = str(relation.get("id") or "")
            for item in c.candidates.values():
                if item["account_id"] == account_id:
                    item["following"] = bool(relation.get("following"))
                    item["followed_by"] = bool(relation.get("followed_by"))
                    item["blocked"] = bool(relation.get("blocking") or relation.get("blocked_by"))
                    item["muting"] = bool(relation.get("muting"))
                    break


def _refresh_cached_viewer_state(c, shortlist):
    """Refresh viewer flags only for cached statuses likely to be proposed."""
    ids = []
    for item in shortlist:
        for status_id in item.get("posts") or set():
            post = c.posts.get(status_id)
            if post and "stream_cache" in post.get("sources", set()):
                ids.append(status_id)
    ids = list(dict.fromkeys(ids))
    if not ids:
        c.use_surface("cached_status_actionability")
        return
    c.use_surface("cached_status_actionability")
    for start in range(0, len(ids), 40):
        if c.exhausted:
            break
        chunk = ids[start:start + 40]
        rows = c.collect(
            "cached_status_actionability", f"batch:{start // 40 + 1}",
            lambda ids=chunk: m._get("statuses", {"id[]": ids}),
            lambda _row: True,
        )
        for status in rows:
            stored = c.posts.get(str(status.get("id") or ""))
            if not stored:
                continue
            stored["favourited"] = bool(status.get("favourited"))
            stored["reblogged"] = bool(status.get("reblogged"))


def _consume_stream_cache(c):
    stream = c.config.get("streaming") or {}
    raw_path = stream.get("db_path")
    if not raw_path:
        c.use_surface("stream_cache")
        return
    db_path = os.path.join(os.path.dirname(ROOT), raw_path)
    try:
        statuses = stream_cache.read_recent(
            db_path,
            limit=int(stream.get("cache_statuses", 200)),
        )
    except Exception as exc:
        c.issues.append(f"stream_cache: {type(exc).__name__}: {exc}")
        c.use_surface("stream_cache")
        return
    c.collect(
        "stream_cache", "recent_matches",
        lambda: statuses,
        lambda status: c.add_status(status, "stream_cache", "recent_matches"),
    )


def _recent(last_status_at, today, max_days):
    try:
        last = dt.date.fromisoformat(str(last_status_at or "")[:10])
    except ValueError:
        return False
    return (today - last).days <= max_days


def _spanish_account(c, item):
    """True si la cuenta es de nuestro publico: su biografia no es CLARAMENTE de otro idioma y sus estados (si los tenemos) son en espanol o gallego; sin estados hace falta que la
    biografia lo parezca. 06/10: se seguia a cuentas solo en aleman (11 de 488) porque «ni espanol ni ingles» pasaba el filtro; una de ellas pregunto en Bluesky si nuestra cuenta era falsa."""
    import text_common as tc
    text = f"{item.get('display_name') or ''} {item.get('bio') or ''}"
    if tc.foreign_language(text):
        return False
    known_posts = getattr(c, "posts", {}) or {}
    langs = [(known_posts[sid].get("language") or "") for sid in item["posts"] if sid in known_posts and known_posts[sid].get("language")]
    if langs:
        good = sum(1 for lang in langs if lang.startswith(("es", "gl")))
        return good * 2 >= len(langs)
    return bool(tc.looks_spanish(text))


def _follow_pool(c, first_touch=None):
    """Cuentas con alta probabilidad de seguirnos de vuelta (medido el 02/10:
    following>=100 y >=0.8*followers -> 43% follow-back, 9/21; el resto 6%,
    5/84; >=2000 seguidores 0/10). Se calcula sobre TODOS los candidatos
    vistos, no solo el shortlist de 90 por score, que descartaba casi todas."""
    cfg = c.config.get("follow_pool") or {}
    min_following = int(cfg.get("min_following", 100))
    min_ratio = float(cfg.get("min_ratio", 0.8))
    max_followers = int(cfg.get("max_followers", 2000))
    min_statuses = int(cfg.get("min_statuses", 20))
    max_inactive = int(cfg.get("max_inactive_days", 30))
    limit = int(cfg.get("limit", 300))
    pool = []
    for item in c.candidates.values():
        if (item["following"] or item["blocked"] or item["muting"]
                or item["bot"] or item["locked"]):
            continue
        if item["known_date"] is not None and not item["followed_by"]:
            continue
        followers = int(item["followers"] or 0)
        following = int(item["following_count"] or 0)
        if following < min_following or followers > max_followers:
            continue
        if following < min_ratio * followers:
            continue
        if int(item["statuses_count"] or 0) < min_statuses:
            continue
        if not _recent(item["last_status_at"], c.today, max_inactive):
            continue
        niche = _hits(item["bio"], c.config["niche_terms"])
        if niche < 1 and not item["posts"]:
            continue
        if sc.looks_activist(item["bio"]) or sc.looks_activist(item["display_name"]):
            continue
        if not _spanish_account(c, item):
            continue
        score = niche + (1 if item["posts"] else 0) + min(following, 1000) / 1000
        if item["followed_by"]:
            score += 5
        pool.append({
            "acct": item["acct"],
            "account_id": item["account_id"],
            "first_source": (first_touch or {}).get(item["acct"]) or next(iter(item.get("source_order") or ()), ""),
            "followers": followers,
            "following_count": following,
            "bio": item["bio"][:140],
            "score": round(score, 3),
        })
    pool.sort(key=lambda row: (-row["score"], row["acct"]))
    return pool[:limit]


def _pool_account(item):
    """Cuenta en formato de la API de Mastodon a partir de un candidato del scan (para la reserva persistente)."""
    return {"id": item["account_id"], "acct": item["acct"], "display_name": item["display_name"], "note": item["bio"], "followers_count": item["followers"],
            "following_count": item["following_count"], "statuses_count": item["statuses_count"], "last_status_at": item["last_status_at"],
            "locked": item["locked"], "bot": item["bot"]}


def _hashtag_rows(c, tag):
    """Estados de un hashtag SIN releer cada ronda la cabeza del timeline (05/10, consulta F a GPT: «ya los habiamos favoriteado»): una pagina de lo mas nuevo (y las que
    hagan falta hasta enlazar con lo ya leido) mas `hashtag_backfill_pages` paginas HACIA ATRAS desde el estado mas antiguo ya recorrido. Los cursores viven en la reserva."""
    import mastodon_pool as pool
    budgets = c.config["budgets"]
    backfill_pages = int(budgets.get("hashtag_backfill_pages", 2))
    head_pages = int(budgets.get("hashtag_pages", 3))
    try:
        db = pool.connect()
        newest, oldest = pool.get_cursor(db, "hashtag", tag)
    except Exception:
        db, newest, oldest = None, None, None
    rows, seen_ids = [], set()

    def take(batch):
        fresh = [row for row in batch if str(row.get("id")) not in seen_ids]
        seen_ids.update(str(row.get("id")) for row in batch)
        rows.extend(fresh)
        return fresh

    try:
        # cabeza: la pagina mas nueva; si no enlaza con lo ya leido sigue hacia atras hasta enlazar (o hasta head_pages)
        max_id = None
        for page in range(max(1, head_pages)):
            batch, max_id = m.hashtag_page(tag, max_id=max_id)
            take(batch)
            ids = [int(r["id"]) for r in batch if str(r.get("id", "")).isdigit()]
            if not batch or not max_id:
                break
            if newest and ids and min(ids) <= int(newest):
                break          # enlazo con lo ya leido; sin cursor (primera vez) sigue hasta head_pages
        # retrospectiva: desde el mas antiguo ya recorrido
        back_from = oldest
        for _ in range(backfill_pages if oldest else 0):
            batch, back_from = m.hashtag_page(tag, max_id=back_from)
            take(batch)
            if not batch or not back_from:
                break
        all_ids = [int(r["id"]) for r in rows if str(r.get("id", "")).isdigit()]
        if db is not None and all_ids:
            pool.set_cursor(db, "hashtag", tag, str(max(all_ids)), str(min(all_ids)), c.today.isoformat())
    finally:
        if db is not None:
            db.close()
    return rows


def _resolve_status(url):
    """El estado remoto como estado LOCAL de mastodon.social (una lectura: `search?resolve=true` devuelve estado y autor con sus ids locales)."""
    result = m.search(url, "statuses", limit=5, resolve=True)
    wanted = url.rstrip("/")
    return [st for st in result.get("statuses", []) if str(st.get("url") or "").rstrip("/") == wanted or str(st.get("uri") or "").rstrip("/") == wanted]


def _consume_remote(c):
    """Estados en espanol de las instancias hispanohablantes (`mastodon_remote.py`, 06/10): se LEEN sin gastar nuestro cupo y aqui cada uno se resuelve con una lectura.
    Cada lectura trae un estado favoriteable de un autor del nicho: ~100 % de rendimiento frente a ~25 % de un perfil de la reserva que ni siquiera trae estados."""
    limit = int(c.config["budgets"].get("remote_resolve", 0))
    if limit <= 0:
        return
    import mastodon_pool as pool
    import mastodon_remote as remote
    c.use_surface("remote_timeline")
    exclude = set(c.known) | set(c.discarded) | {str(c.own or "")} | {f"{c.own}@mastodon.social"}
    try:
        db = pool.connect()
        remote.ensure(db)
        bare = set(c.known) | set(c.discarded)
        if len(remote.pick(db, limit, exclude_accts=exclude, exclude_bare=bare, today=c.today)) < limit:       # reserva corta: leer las instancias (no cuesta nada de nuestro cupo)
            remote.mine(db, today=c.today)
        rows = remote.pick(db, limit, exclude_accts=exclude, exclude_bare=bare, today=c.today)
    except Exception as exc:
        c.issues.append(f"remote: {type(exc).__name__}: {exc}")
        return
    try:
        for row in rows:
            if c.exhausted:
                break
            c.collect("remote_timeline", row["host"], lambda u=row["url"]: _resolve_status(u),
                      lambda status, h=row["host"]: c.add_status(status, "remote_timeline", h))
            remote.mark(db, row["url"], "resolved")
    finally:
        db.close()


def _consume_pool(c):
    """Cuentas de la reserva persistente (`mastodon_pool.py`) como fuente `pool` (05/10): seguidores/seguidos y favoriteadores de las semillas del nicho."""
    limit = int(c.config["budgets"].get("pool_candidates", 0))
    if limit <= 0:
        return
    import mastodon_pool as pool
    c.use_surface("pool")
    try:
        db = pool.connect()
    except Exception as exc:
        c.issues.append(f"pool: {type(exc).__name__}: {exc}")
        return
    try:
        rows = pool.top_candidates(db, limit, today=c.today.isoformat(), relaxed=True, exclude=set(c.known) | set(c.discarded) | {str(c.own or "")} | {f"{c.own}@mastodon.social"})
    except Exception as exc:
        c.issues.append(f"pool: {type(exc).__name__}: {exc}")
        return
    finally:
        db.close()
    before = set(c.candidates)
    accepted = 0
    for row in rows:
        account = {"id": row["account_id"], "acct": row["acct"], "display_name": row["display"], "note": row["bio"], "followers_count": row["followers"],
                   "following_count": row["following"], "statuses_count": row["statuses"], "last_status_at": row["last_status_at"], "locked": bool(row["locked"])}
        if c.add_account(account, "pool", f"semillas={min(row['seeds_count'], 5)}"):
            accepted += 1
    c.source_stats[("pool", "offer")]["fetched"] += len(rows)
    c.source_stats[("pool", "offer")]["accepted"] += accepted
    c.source_stats[("pool", "offer")]["new_accounts"].update(set(c.candidates) - before)


def _vet_shortlist_gaps(c):
    """Estados de los perfiles que YA estan en la shortlist y no tienen ninguno (05/10; en Bluesky el 59 % de la shortlist estaba asi): sin estado no hay favorito.
    Cada verificacion es una lectura (`accounts/:id/statuses`); tope `vet_gap_profiles`."""
    limit = int(c.config["budgets"].get("vet_gap_profiles", 0))
    if limit <= 0:
        return
    ordered = sorted(c.candidates.values(), key=lambda item: (-_rank_profile(c, item), item["acct"]))[:int(c.config["budgets"]["shortlist_profiles"])]
    gaps = [item for item in ordered if not item["posts"] and item["account_id"] and not item["blocked"] and not item["muting"]][:limit]
    c.use_surface("author_statuses")
    budgets = c.config["budgets"]
    for item in gaps:
        if c.exhausted:
            break
        c.collect(
            "author_statuses", item["acct"],
            lambda account_id=item["account_id"]: m.account_statuses(account_id, limit=int(budgets["profile_statuses"]), max_pages=1),
            lambda status, acct=item["acct"]: c.add_status(status, "author_status", acct),
        )


def _first_touch_map(c, items):
    """{acct: fuente first-touch} desde la reserva; registra la de los handles nuevos y persiste todo lo que este scan encontro (union de fuentes)."""
    try:
        import mastodon_pool as pool
        db = pool.connect()
    except Exception as exc:
        c.issues.append(f"first_touch: {type(exc).__name__}: {exc}")
        return {}
    try:
        handles = [item["acct"] for item in items]
        stored = pool.first_touch(db, handles)
        new = {item["acct"]: item["source_order"][0] for item in items if item["acct"] not in stored and item.get("source_order")}
        if new:
            pool.record_touch(db, new, c.today.isoformat())
        rows = [(_pool_account(item), str((item.get("source_order") or ["desconocida"])[0])) for item in c.candidates.values()
                if item["account_id"] and "pool" not in item["sources"] and not item["blocked"] and not item["muting"]]
        pool.record_scan_candidates(db, rows, c.today.isoformat())
        return {**new, **stored}
    except Exception as exc:
        c.issues.append(f"first_touch: {type(exc).__name__}: {exc}")
        return {}
    finally:
        db.close()


ACTIONABLE_BONUS = 3.0


def _has_favourite_post(c, item):
    """True si el perfil ya trae algun estado sobre el que se puede dar favorito (publico, reciente, en su idioma, aun sin favorito)."""
    lane = "community" if (item["known_date"] or item["following"] or item["followed_by"]) else "acquisition"
    for status_id in item["posts"]:
        post = c.posts.get(status_id)
        if post and "favourite" in _post_actions(item, post, lane, c.today, c.config):
            return True
    return False


def _shortlist_rank(c, item):
    """Puntuacion de perfil + un bonus si ya tiene un estado favoriteable (06/10: el 48 % de la shortlist de 700 no tenia ningun estado y solo 88 perfiles daban favorito: la
    reserva colaba perfiles sin posts por delante de los que ya los traian de un hashtag; esos huecos se rellenan despues, con `_vet_shortlist_gaps`)."""
    return _rank_profile(c, item) + (ACTIONABLE_BONUS if _has_favourite_post(c, item) else 0.0)


def _build_output(c):
    shortlist_limit = int(c.config["budgets"]["shortlist_profiles"])
    ordered = sorted(
        c.candidates.values(),
        key=lambda item: (-_shortlist_rank(c, item), item["acct"]),
    )[:shortlist_limit]
    first_touch = _first_touch_map(c, ordered)
    _refresh_cached_viewer_state(c, ordered)
    shortlist = []
    for index, item in enumerate(ordered, start=1):
        item["score"] = _rank_profile(c, item)
        actions = []
        if (
            not item["following"] and not item["blocked"] and not item["muting"]
            and (item["known_date"] is None or item["followed_by"])
            and _spanish_account(c, item)        # solo a gente de nuestro publico (06/10, David): quien nos sigue en otro idioma no pasa nada, pero no se le sigue de vuelta
        ):
            actions.append("follow")
        posts = sorted(
            (c.posts[status_id] for status_id in item["posts"] if status_id in c.posts),
            key=lambda post: (
                post["replies"] * 2 + post["favourites"] * 0.2 + post["boosts"] * 0.35,
                post["created_at"],
            ),
            reverse=True,
        )[:int(c.config["budgets"]["posts_per_profile"])]
        lane = "community" if (
            item["known_date"] or item["following"] or item["followed_by"]
        ) else "acquisition"
        post_rows = []
        for p_index, post in enumerate(posts, start=1):
            post_rows.append({
                "id": f"M{index:03d}-P{p_index}",
                "status_id": post["id"],
                "url": post["url"],
                "text": post["text"],
                "visibility": post["visibility"],
                "sensitive": post["sensitive"],
                "created_at": post["created_at"],
                "stats": {
                    "replies": post["replies"],
                    "favourites": post["favourites"],
                    "boosts": post["boosts"],
                    "quotes": post["quotes"],
                },
                "sources": sorted(post["sources"]),
                "language": post.get("language") or "",
                "actions": _post_actions(item, post, lane, c.today, c.config),
            })
        shortlist.append({
            "id": f"M{index:03d}",
            "instance": m.BASE.split("://", 1)[-1].rstrip("/"),
            "lane": lane,
            "acct": item["acct"],
            "account_id": item["account_id"],
            "first_source": first_touch.get(item["acct"]) or next(iter(item.get("source_order") or ()), ""),
            "display_name": item["display_name"],
            "bio": item["bio"],
            "followers": item["followers"],
            "following_count": item["following_count"],
            "statuses_count": item["statuses_count"],
            "last_status_at": item["last_status_at"],
            "locked": item["locked"],
            "bot": item["bot"],
            "following": item["following"],
            "followed_by": item["followed_by"],
            # known_date viene de sc.known_accounts() (compartido entre redes,
            # ver scan_common.py) y ya es el string crudo de la columna
            # "fecha" del CSV, no un date - a diferencia de seen_date (abajo),
            # que sí se parsea con dt.date.fromisoformat en _load_seen().
            # Bug real encontrado en vivo el 29/09: .isoformat() sobre un str
            # revienta con AttributeError en cuanto hay una sola cuenta
            # conocida, es decir, en cualquier sesion con historial real.
            "known_date": item["known_date"] or None,
            "seen_date": item["seen_date"].isoformat() if item["seen_date"] else None,
            "score": item["score"],
            "sources": sorted(item["sources"]),
            "source_keys": sorted(item["source_keys"]),
            "actions": actions,
            "posts": post_rows,
        })

    required = set(c.config["coverage"]["required_surfaces"])
    # Bug real visto en vivo el 29/09: post_search se registra en
    # c.surfaces con un sufijo por familia de consultas
    # ("post_search:autores", "post_search:fantasia", ...) via collect(),
    # nunca como el string pelado "post_search" que pide required_surfaces -
    # una resta de sets directa lo marcaba SIEMPRE como no cubierto aunque
    # se hubiera ejecutado 4 veces, dando un falso "coverage incompleta"
    # (y con --strict, un exit code 2 injustificado) en cualquier ronda.
    covered_prefixes = {name.split(":", 1)[0] for name in c.surfaces}
    missing = sorted(required - c.surfaces - covered_prefixes)
    fresh = sum(1 for item in shortlist if item["lane"] == "acquisition" and not item["seen_date"])
    totals = {
        "profiles_seen": len(c.candidates),
        "posts_seen": len(c.posts),
        "shortlist": len(shortlist),
        "acquisition": sum(row["lane"] == "acquisition" for row in shortlist),
        "community": sum(row["lane"] == "community" for row in shortlist),
        "fresh_acquisition": fresh,
    }
    source_metrics = {
        f"{surface}:{key}": {
            "fetched": row["fetched"],
            "accepted": row["accepted"],
            "new_accounts": sum(1 for acct in row["new_accounts"] if _is_fresh(c, acct)),
        }
        for (surface, key), row in c.source_stats.items()
    }
    result = {
        "run_id": c.run_id,
        "date": c.today.isoformat(),
        "budget": {
            "used": c.reads,
            "maximum": c.maximum,
            "remaining": max(0, c.maximum - c.reads),
            "paced_seconds": round(c.paced_seconds, 1),
        },
        "coverage": {
            "attempted": sorted(c.surfaces),
            "required": sorted(required),
            "missing": missing,
        },
        "totals": totals,
        "issues": c.issues,
        "stopped": c.exhausted,
        "source_metrics": source_metrics,
        "auto_plan": [],
        "follow_pool": _follow_pool(c, first_touch),
        "shortlist": shortlist,
    }
    if c.write_metrics:
        _append_csv(
            METRICS_CSV,
            ["fecha", "run_id", "surface", "key", "fetched", "accepted", "new_accounts"],
            list(_source_metric_rows(c)),
        )
        rows = []
        for item in shortlist:
            for post in item["posts"]:
                rows.append([c.today.isoformat(), item["acct"], post["status_id"]])
            if not item["posts"]:
                rows.append([c.today.isoformat(), item["acct"], ""])
        _append_csv(SEEN_CSV, ["fecha", "acct", "status_id"], rows)
    return result


def run(*, config_path=CONFIG_PATH, write_metrics=True, today=None):
    config = _load_config(config_path)
    c = Collector(config, today=today, write_metrics=write_metrics)
    previous_hook = m._set_request_hook(c._before_request)
    try:
        c.use_surface("health")
        me = m._get("accounts/verify_credentials")
        acct = str(me.get("acct") or "").casefold()
        if str(me.get("username") or "").casefold() != m.HANDLE.casefold() or acct not in {
            m.HANDLE.casefold(), f"{m.HANDLE}@mastodon.social",
        }:
            raise m.WrongAccountActive("token Mastodon no pertenece a la cuenta esperada")
        c.own = acct
        c.own_id = str(me.get("id") or "")
        if "supports_quotes_endpoint" not in config:
            try:
                config["supports_quotes_endpoint"] = m.patient(m.supports_status_quotes, waits=3, priority="scan")
            except m.MastodonRateLimitExceeded as exc:
                c.issues.append(f"rate_limit_quote_capability: {exc}")
                c.exhausted = True
        b = config["budgets"]

        _consume_stream_cache(c)

        # Señales de reciprocidad y contenido propio para reabrir conversaciones.
        def add_notification(row):
            account = row.get("account") or {}
            typ = row.get("type")
            status = row.get("status")
            if status:
                return c.add_status(status, "notification", typ or "")
            if typ in {"follow", "follow_request"}:
                return c.add_account(account, "notification", typ)
            return False

        c.collect(
            "notifications", "recent",
            lambda: m.notifications(80, max_pages=b["notifications_pages"]),
            add_notification,
        )
        c.collect(
            "own_posts", c.own,
            lambda: m.account_statuses(c.own_id, limit=40, max_pages=2),
            lambda status: c.add_status(status, "own_post", c.own),
        )

        c.collect(
            "home_timeline", "home",
            lambda: m.home_timeline(40, max_pages=b["timeline_pages"]),
            lambda status: c.add_status(status, "home_timeline", "home"),
        )
        c.collect(
            "local_timeline", "local",
            lambda: m.public_timeline(40, local=True, max_pages=b["timeline_pages"]),
            lambda status: c.add_status(status, "local_timeline", "local"),
        )

        followed = c.collect(
            "followed_tags", "subscriptions",
            m.followed_tags,
            lambda _tag: True,
        )
        for tag in followed:
            if c.exhausted:
                break
            name = tag.get("name") if isinstance(tag, dict) else str(tag)
            if not name:
                continue
            c.collect(
                "hashtag_timelines", f"followed:{name}",
                lambda n=name: _hashtag_rows(c, n),
                lambda status, n=name: c.add_status(status, "followed_tag", n),
            )

        trends = c.collect(
            "trending_tags", "instance",
            lambda: m.trending_tags(20),
            lambda _tag: True,
        )
        c.collect(
            "trending_statuses", "instance",
            lambda: m.trending_statuses(40),
            lambda status: c.add_status(status, "trending_status", "instance"),
        )
        links = c.collect(
            "trending_links", "instance",
            lambda: m.trending_links(20),
            lambda _link: True,
        )
        for link in links:
            if c.exhausted:
                break
            url = link.get("url") if isinstance(link, dict) else None
            if url:
                c.collect(
                    "trending_links", url,
                    lambda target=url: m.link_timeline(target, limit=40, max_pages=1),
                    lambda status, target=url: c.add_status(status, "trending_link", target),
                )

        c.collect(
            "domain_search", "autorademodiaz.com",
            lambda: m.search_statuses("autorademodiaz.com", limit=40, max_pages=b["search_pages"]),
            lambda status: c.add_status(status, "domain_search", "autorademodiaz.com"),
        )

        selected_queries = _query_selection(c)
        for family, query in selected_queries:
            if c.exhausted:
                break
            c.collect(
                "post_search:" + family, query,
                lambda q=query: m.search_statuses(q, limit=40, max_pages=b["search_pages"]),
                lambda status, q=query, fam=family: c.add_status(status, "post_search", f"{fam}:{q}"),
            )

        account_queries = _rank_queries(
            config["account_queries"], c.metrics, "account_search", c.today
        )[:int(config["coverage"]["account_queries_per_round"])]
        for query in account_queries:
            if c.exhausted:
                break
            c.collect(
                "account_search", query,
                lambda q=query: m.search_accounts_pages(q, limit=40, max_pages=2),
                lambda account, q=query: c.add_account(account, "account_search", q),
            )

        # Etiquetas emergentes aprendidas de los posts ya leídos más las tendencias.
        dynamic_tags = [tag for status in c.posts.values() for tag in status.get("tags", [])]
        dynamic_tags.extend(
            str(tag.get("name") or "") for tag in trends if isinstance(tag, dict)
        )
        tags = _tag_selection(c, dynamic_tags)
        for tag in tags:
            if c.exhausted:
                break
            c.collect(
                "hashtag_timelines", tag,
                lambda t=tag: _hashtag_rows(c, t),
                lambda status, t=tag: c.add_status(status, "hashtag", t),
            )

        _consume_remote(c)
        _consume_pool(c)
        _hydrate_relationships(c)
        _expand_discovery(c)
        _hydrate_relationships(c)
        _vet_shortlist_gaps(c)
        return _build_output(c)
    finally:
        m._set_request_hook(previous_hook)


def compact_ai_view(result):
    profiles = []
    for item in result.get("shortlist", []):
        profiles.append({
            key: item.get(key)
            for key in (
                "id", "lane", "acct", "display_name", "bio", "followers",
                "following_count", "last_status_at", "locked", "bot",
                "following", "followed_by", "score", "sources", "actions",
            )
        } | {"posts": [
            {
                key: post.get(key)
                for key in ("id", "text", "visibility", "created_at", "stats", "actions")
            }
            for post in item.get("posts", [])
        ]}
        )
    return {
        "run_id": result.get("run_id"),
        "date": result.get("date"),
        "budget": result.get("budget"),
        "coverage": result.get("coverage"),
        "totals": result.get("totals"),
        "issues": result.get("issues"),
        "shortlist": profiles,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_PATH)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--ai-json", action="store_true")
    parser.add_argument("--state-out")
    parser.add_argument("--no-metrics", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(config_path=args.config, write_metrics=not args.no_metrics)
    except (m.MastodonRateLimitExceeded, m.WrongAccountActive, m.MastodonAPIError) as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(result, ensure_ascii=False))
        return 2
    if args.state_out:
        with open(args.state_out, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    payload = compact_ai_view(result) if args.ai_json else result
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":") if args.json or args.ai_json else None, indent=None if args.json or args.ai_json else 2))
    return 0 if not result.get("coverage", {}).get("missing") else 2


if __name__ == "__main__":
    raise SystemExit(main())
