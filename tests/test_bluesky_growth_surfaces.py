"""Superficies nuevas del motor de crecimiento Bluesky; todo offline."""
import copy
import datetime
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

# CI no instala requests: aislar la capa XRPC igual que el resto de tests Bluesky.
stub = types.ModuleType("bluesky_interact")
stub.PUBLIC_BASE = "https://public.api.bsky.app/xrpc"
stub.AUTH_BASE = "https://bsky.social/xrpc"
stub.RateLimitExceeded = type("RateLimitExceeded", (RuntimeError,), {})
stub._get_notifications = lambda *a, **k: []
stub._get_timeline = lambda *a, **k: []
stub._search_posts = lambda *a, **k: []
stub._search_actors = lambda *a, **k: []
stub._get = lambda *a, **k: {}
stub._post_engagers = lambda *a, **k: []
stub._health_check = lambda: (
    True, "OK", {"handle": "davidportodiaz.bsky.social", "did": "did:plc:david"}
)
stub._own_reply_parent_uris = lambda: set()

with patch.dict(sys.modules, {"bluesky_interact": stub}):
    import bluesky_growth_scan as gs


def post(handle, rkey, text):
    return {
        "uri": f"at://did:plc:{handle.split('.')[0]}/app.bsky.feed.post/{rkey}",
        "author": {
            "handle": handle,
            "displayName": handle.split(".")[0],
            "description": "Lectora de fantasía y novelas",
        },
        "record": {"text": text, "createdAt": "2026-09-29T08:00:00Z"},
        "likeCount": 0,
        "repostCount": 0,
        "replyCount": 0,
        "quoteCount": 0,
    }


class GrowthSurfaceTests(unittest.TestCase):
    def setUp(self):
        # Bug real 29/09: Collector lee discovery_metrics.csv del repo real sin
        # forma de inyectar una ruta - una ronda real ejecutada el mismo dia
        # acumulaba historial de queries que este test no esperaba, haciendo
        # que test_repeated_discovered_hashtag_opens_new_search pasara de 1 a
        # 5 llamadas segun cuanto se hubiera usado el sistema en produccion.
        # Aislar la ruta evita que los tests dependan de cuanto se ha operado
        # la cuenta real.
        patcher = patch.object(gs, "METRICS_CSV", "__no_such_metrics__.csv")
        patcher.start()
        self.addCleanup(patcher.stop)

    def collector(self):
        cfg = copy.deepcopy(gs._load_config())
        cfg["budgets"]["max_read_requests"] = 500
        cfg["budgets"]["max_candidates"] = 500
        cfg["coverage"]["replies_only_queries_total"] = 2
        cfg["budgets"]["actor_menu_seeds"] = 1
        cfg["budgets"]["lists_per_actor"] = 1
        cfg["budgets"]["actor_feeds_per_actor"] = 1
        c = gs.Collector(
            cfg,
            write_metrics=False,
            today=datetime.date(2026, 9, 29),
            run_id="surface-test",
        )
        c.own_handle = "davidportodiaz.bsky.social"
        c.own_did = "did:plc:david"
        return c

    def test_replies_only_search_finds_active_commenter(self):
        c = self.collector()
        calls = []

        def fake_get(base, path, params, auth):
            calls.append((path, dict(params)))
            if path == "app.bsky.feed.searchPostsV2":
                # requests.get serializa un bool Python como "True"/"False" (mayuscula),
                # y searchPostsV2 real lo rechaza (400 InvalidRequest) - bug real
                # encontrado en produccion el 29/09. El stub reproduce esa exigencia
                # para que este test no vuelva a aceptar un bool crudo.
                for key in ("repliesOnly", "excludeReplies"):
                    if key in params and not isinstance(params[key], str):
                        raise RuntimeError(
                            f"GET app.bsky.feed.searchPostsV2 fallo (400): "
                            f"Expected boolean value type (got {params[key]!r})"
                        )
                return {
                    "posts": [post(
                        "comentador.bsky.social", "r1",
                        "Yo también estoy leyendo fantasía juvenil este mes.",
                    )]
                }
            return {}

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._search_replies_v2(c)

        v2 = [params for path, params in calls if path.endswith("searchPostsV2")]
        self.assertEqual(len(v2), 2)
        self.assertTrue(all(params["repliesOnly"] == "true" for params in v2))
        self.assertIn("comentador.bsky.social", c.candidates)
        self.assertIn("reply_search", c.candidates["comentador.bsky.social"]["sources"])

    def test_followers_and_following_are_used_as_relationship_seeds(self):
        c = self.collector()
        calls = []

        def fake_get(base, path, params, auth):
            calls.append(path)
            if path == "app.bsky.graph.getFollowers":
                return {"followers": [{
                    "handle": "follower.bsky.social",
                    "description": "Lectora de fantasía",
                }]}
            if path == "app.bsky.graph.getFollows":
                return {"follows": [{
                    "handle": "following.bsky.social",
                    "description": "Escritor y lector",
                }]}
            raise AssertionError(path)

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._discover_own_network(c)

        self.assertEqual(
            set(calls),
            {"app.bsky.graph.getFollowers", "app.bsky.graph.getFollows"},
        )
        self.assertIn("own_follower", c.candidates["follower.bsky.social"]["sources"])
        self.assertIn("own_following", c.candidates["following.bsky.social"]["sources"])

    def test_own_post_engagers_recover_likers_reposters_quotes_and_replies(self):
        c = self.collector()
        root = post(
            "davidportodiaz.bsky.social", "own1",
            "¿Qué fantasía estáis leyendo?",
        )
        root["likeCount"] = 5
        root["replyCount"] = 2

        def fake_get(base, path, params, auth):
            if path == "app.bsky.feed.getAuthorFeed":
                return {"feed": [{"post": root}]}
            if path == "app.bsky.feed.searchPostsV2":
                return {"posts": [
                    root,
                    post(
                        "reply-own.bsky.social", "r1",
                        "Yo estoy leyendo romantasy.",
                    ),
                ]}
            raise AssertionError(path)

        def fake_engagers(url_or_uri, kind, limit):
            if kind == "likes":
                return [{"actor": {
                    "handle": "like-own.bsky.social",
                    "description": "Lectora de libros",
                }}]
            if kind == "reposts":
                return [{
                    "handle": "repost-own.bsky.social",
                    "description": "Escritor de fantasía",
                }]
            if kind == "quotes":
                return [post(
                    "quote-own.bsky.social", "q1",
                    "Este hilo de fantasía me interesa.",
                )]
            raise AssertionError(kind)

        with patch.object(gs.b, "_get", side_effect=fake_get), \
             patch.object(gs.b, "_post_engagers", side_effect=fake_engagers):
            gs._discover_own_post_engagers(c)

        self.assertIn("like-own.bsky.social", c.candidates)
        self.assertIn("repost-own.bsky.social", c.candidates)
        self.assertIn("quote-own.bsky.social", c.candidates)
        self.assertIn("reply-own.bsky.social", c.candidates)
        self.assertIn("own_post_liker", c.candidates["like-own.bsky.social"]["sources"])
        self.assertIn("own_post_reply", c.candidates["reply-own.bsky.social"]["sources"])

    def test_personalized_explore_uses_interest_and_language_headers(self):
        c = self.collector()
        c.preference_interests = ["books", "fantasy"]
        c.preference_interests_updated_at = "2026-09-29T06:00:00Z"
        c.config["budgets"]["personalized_pack_expansions"] = 0
        calls = []

        def fake_get(base, path, params, auth, extra_headers=None):
            calls.append((path, dict(params), dict(extra_headers or {})))
            if path == "app.bsky.unspecced.getSuggestedStarterPacks":
                return {"starterPacks": []}
            return {"actors": [{
                "handle": f"{path.rsplit('.', 1)[-1].lower()}.bsky.social",
                "description": "Lectora de fantasía y libros",
            }]}

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._discover_personalized_recommendations(c)

        paths = {path for path, _, _ in calls}
        self.assertIn(
            "app.bsky.unspecced.getSuggestedUsersForDiscover", paths
        )
        self.assertIn(
            "app.bsky.unspecced.getSuggestedUsersForExplore", paths
        )
        self.assertIn(
            "app.bsky.unspecced.getSuggestedUsersForSeeMore", paths
        )
        self.assertIn(
            "app.bsky.unspecced.getSuggestedStarterPacks", paths
        )
        for _, _, headers in calls:
            self.assertEqual(headers["Accept-Language"], "es")
            self.assertEqual(
                headers["x-atproto-bsky-topics"],
                "books,fantasy;2026-09-29T06:00:00Z",
            )

    def test_viewer_state_uses_followed_by_and_list_exclusions(self):
        c = self.collector()
        c.add_actor({
            "handle": "reciproca.bsky.social",
            "description": "Lectora de fantasía",
            "viewer": {
                "followedBy": "at://did:plc:x/app.bsky.graph.follow/abc",
                "activitySubscription": {"post": True},
            },
        }, "actor_search")
        item = c.candidates["reciproca.bsky.social"]
        self.assertTrue(item["followed_by"])
        self.assertTrue(item["activity_subscription"])
        self.assertGreater(gs._pre_score(item), 4.0)

        c.add_actor({
            "handle": "mutelist.bsky.social",
            "description": "Lectora de fantasía",
            "viewer": {"mutedByList": {"uri": "at://list"}},
        }, "actor_search")
        self.assertEqual(
            c.candidates["mutelist.bsky.social"]["excluded_reason"],
            "muted",
        )

        c.add_actor({
            "handle": "blocklist.bsky.social",
            "description": "Lectora de fantasía",
            "viewer": {"blockingByList": {"uri": "at://list"}},
        }, "actor_search")
        self.assertEqual(
            c.candidates["blocklist.bsky.social"]["excluded_reason"],
            "blocking",
        )

    def test_native_suggestions_enter_same_profile_pipeline(self):
        c = self.collector()

        def fake_get(base, path, params, auth):
            self.assertEqual(path, "app.bsky.actor.getSuggestions")
            self.assertTrue(auth)
            return {"actors": [{
                "handle": "sugerida.bsky.social",
                "description": "Escritora de fantasía y lectora",
            }]}

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._discover_suggested_accounts(c)

        self.assertIn("sugerida.bsky.social", c.candidates)
        self.assertIn(
            "suggested_account",
            c.candidates["sugerida.bsky.social"]["sources"],
        )

    def test_direct_starter_pack_search_uses_v2_and_expands_members(self):
        c = self.collector()
        c.config["budgets"]["starter_pack_queries_per_round"] = 1
        list_uri = "at://did:plc:pack/app.bsky.graph.list/readers"
        calls = []

        def fake_get(base, path, params, auth):
            calls.append(path)
            if path == "app.bsky.graph.searchStarterPacksV2":
                return {"starterPacks": [{
                    "uri": "at://did:plc:pack/app.bsky.graph.starterpack/x",
                    "creator": {
                        "handle": "pack-owner.bsky.social",
                        "description": "BookSky y fantasía",
                    },
                    "list": {"uri": list_uri, "name": "Lectores"},
                    "record": {
                        "name": "Lectores de fantasía",
                        "description": "BookSky en español",
                    },
                }]}
            if path == "app.bsky.graph.getList":
                self.assertEqual(params["list"], list_uri)
                return {"items": [{"subject": {
                    "handle": "pack-member.bsky.social",
                    "description": "Lectora de fantasía",
                }}]}
            raise AssertionError(path)

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._search_starter_packs(c)

        self.assertIn("app.bsky.graph.searchStarterPacksV2", calls)
        self.assertIn("pack-owner.bsky.social", c.candidates)
        self.assertIn("pack-member.bsky.social", c.candidates)

    def test_thread_search_v2_reads_many_commenters_before_tree_fallback(self):
        c = self.collector()
        seed = post(
            "semilla.bsky.social", "root",
            "¿Qué fantasía estáis leyendo?",
        )
        reply1 = post(
            "comentador1.bsky.social", "r1",
            "Estoy leyendo fantasía épica.",
        )
        reply2 = post(
            "comentador2.bsky.social", "r2",
            "Yo estoy con romantasy esta semana.",
        )
        calls = []

        def fake_get(base, path, params, auth):
            calls.append(path)
            if path == "app.bsky.feed.searchPostsV2":
                self.assertEqual(params["threadRootUri"], seed["uri"])
                self.assertEqual(params["limit"], 100)
                return {"posts": [seed, reply1, reply2]}
            raise AssertionError(path)

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._expand_threads(c, [{
                "uri": seed["uri"],
                "url": gs._post_url(seed),
                "handle": "semilla.bsky.social",
                "text": seed["record"]["text"],
                "likes": 0,
                "reposts": 0,
                "replies": 2,
                "quotes": 0,
                "created_at": seed["record"]["createdAt"],
                "sources": {"post_search"},
                "source_keys": set(),
            }])

        self.assertEqual(calls, ["app.bsky.feed.searchPostsV2"])
        self.assertIn("comentador1.bsky.social", c.candidates)
        self.assertIn("comentador2.bsky.social", c.candidates)

    def test_saved_feed_and_list_become_candidates(self):
        c = self.collector()
        feed_uri = "at://did:plc:feed/app.bsky.feed.generator/books"
        list_uri = "at://did:plc:list/app.bsky.graph.list/readers"

        def fake_get(base, path, params, auth):
            if path == "app.bsky.actor.getPreferences":
                return {
                    "preferences": [{
                        "$type": "app.bsky.actor.defs#savedFeedsPrefV2",
                        "items": [
                            {"type": "feed", "value": feed_uri, "pinned": True},
                            {"type": "list", "value": list_uri, "pinned": False},
                        ],
                    }]
                }
            if path == "app.bsky.feed.getFeed":
                return {"feed": [{"post": post(
                    "desde-feed.bsky.social", "f1",
                    "Libros y fantasía para este otoño.",
                )}]}
            if path == "app.bsky.feed.getListFeed":
                return {"feed": [{"post": post(
                    "desde-lista.bsky.social", "l1",
                    "Estoy leyendo una novela de fantasía.",
                )}]}
            raise AssertionError(path)

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._discover_own_preferences(c)

        self.assertIn("desde-feed.bsky.social", c.candidates)
        self.assertIn("desde-lista.bsky.social", c.candidates)
        self.assertIn("saved_feed", c.candidates["desde-feed.bsky.social"]["sources"])

    def test_actor_profile_menus_expand_list_and_feed(self):
        c = self.collector()
        c.add_actor({
            "handle": "curadora.bsky.social",
            "description": "Lectora de fantasía y libros",
            "followersCount": 100,
            "followsCount": 90,
            "postsCount": 120,
            "associated": {"lists": 1, "feedgens": 1},
            "viewer": {},
        }, "actor_search")

        list_uri = "at://did:plc:curadora/app.bsky.graph.list/fantasia"
        feed_uri = "at://did:plc:curadora/app.bsky.feed.generator/libros"

        def fake_get(base, path, params, auth):
            if path == "app.bsky.graph.getLists":
                self.assertEqual(params["purposes"], ["curatelist"])
                return {"lists": [{
                    "uri": list_uri,
                    "name": "Lectores de fantasía",
                    "description": "Comunidad de libros",
                    "listItemCount": 30,
                }]}
            if path == "app.bsky.feed.getListFeed":
                return {"feed": [{"post": post(
                    "list-post.bsky.social", "lp",
                    "Mi lectura de fantasía de esta semana.",
                )}]}
            if path == "app.bsky.graph.getList":
                return {"items": [{"subject": {
                    "handle": "list-member.bsky.social",
                    "description": "Lector de fantasía",
                }}]}
            if path == "app.bsky.feed.getActorFeeds":
                return {"feeds": [{
                    "uri": feed_uri,
                    "displayName": "Fantasy Books",
                    "description": "Libros y fantasía",
                    "likeCount": 20,
                }]}
            if path == "app.bsky.feed.getFeed":
                return {"feed": [{"post": post(
                    "feed-post.bsky.social", "fp",
                    "Una novela de fantasía que recomiendo.",
                )}]}
            raise AssertionError(path)

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._expand_actor_menus(c)

        self.assertIn("list-member.bsky.social", c.candidates)
        self.assertIn("list-post.bsky.social", c.candidates)
        self.assertIn("feed-post.bsky.social", c.candidates)
        self.assertIn("curated_list", c.candidates["list-member.bsky.social"]["sources"])
        self.assertIn("actor_feed", c.candidates["feed-post.bsky.social"]["sources"])

    def test_known_followers_add_social_context_not_an_auto_action(self):
        c = self.collector()
        c.add_actor({
            "handle": "nueva.bsky.social",
            "description": "Escritora de fantasía",
            "followersCount": 20,
            "followsCount": 30,
            "postsCount": 40,
            "viewer": {},
        }, "actor_search")

        def fake_get(base, path, params, auth):
            self.assertEqual(path, "app.bsky.graph.getKnownFollowers")
            return {"followers": [
                {"handle": "conocida1.bsky.social"},
                {"handle": "conocida2.bsky.social"},
            ]}

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._enrich_known_followers(c)

        item = c.candidates["nueva.bsky.social"]
        self.assertEqual(item["known_followers_count"], 2)
        self.assertIn("known_follower", item["sources"])
        gs._profile_score(c, item)
        self.assertTrue(any("2 conexiones" in x for x in item["signals"]))

    def test_repeated_discovered_hashtag_opens_new_search(self):
        c = self.collector()
        c.add_post(post(
            "a.bsky.social", "a",
            "Mi lectura fantástica #MundosMagicos",
        ), "post_search")
        c.add_post(post(
            "b.bsky.social", "b",
            "Otro libro de fantasía #MundosMagicos",
        ), "post_search")
        calls = []

        def fake_search(query, lang="es", limit=20, **kwargs):
            calls.append((query, kwargs))
            return []

        with patch.object(gs.b, "_search_posts", side_effect=fake_search):
            gs._expand_dynamic_tags(c)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["tag"], ["MundosMagicos"])

    def test_dynamic_hashtag_from_previous_day_is_reused(self):
        c = self.collector()
        yesterday = datetime.date(2026, 9, 28)
        c.query_stats = {
            ("dynamic_tag", "LectoresDeDragones"): {
                "attempts": 2,
                "fetched": 40,
                "accepted": 18,
                "new_handles": 12,
                "last_date": yesterday,
            }
        }
        calls = []

        def fake_search(query, lang="es", limit=20, **kwargs):
            calls.append((query, kwargs))
            return []

        with patch.object(gs.b, "_search_posts", side_effect=fake_search):
            gs._expand_dynamic_tags(c)

        self.assertTrue(any(
            query == "LectoresDeDragones" and kwargs.get("tag") == ["LectoresDeDragones"]
            for query, kwargs in calls
        ))

    def test_diversity_reserves_space_for_liker_source(self):
        c = self.collector()
        for i in range(10):
            c.add_actor({
                "handle": f"search{i}.bsky.social",
                "description": "Lector de fantasía",
            }, "post_search")
        c.add_actor({
            "handle": "liker-especial.bsky.social",
            "description": "Lectora",
        }, "liker")

        selected = gs._diverse_candidates(
            c.candidates.values(), 4, gs._pre_score
        )
        self.assertIn(
            "liker-especial.bsky.social",
            {item["handle"] for item in selected},
        )


    def test_trending_uses_current_get_trends_surface(self):
        c = self.collector()
        c.preference_interests = ["books", "fantasy"]
        c.preference_interests_updated_at = "2026-09-29T08:00:00Z"
        calls = []
        searched = []

        def fake_get(base, path, params, auth, extra_headers=None):
            calls.append((path, dict(params), auth, dict(extra_headers or {})))
            self.assertEqual(path, "app.bsky.unspecced.getTrends")
            return {
                "trends": [
                    {"topic": "fantasía", "displayName": "Fantasía"},
                    {"topic": "elecciones", "displayName": "Elecciones"},
                ]
            }

        def fake_search(query, lang="es", limit=20, **kwargs):
            searched.append((query, lang, limit, kwargs))
            return []

        with patch.object(gs.b, "_get", side_effect=fake_get), patch.object(
            gs.b, "_search_posts", side_effect=fake_search
        ):
            gs._discover_trending_topics(c)

        self.assertEqual(calls, [(
            "app.bsky.unspecced.getTrends",
            {"limit": 25},
            True,
            {
                "Accept-Language": "es",
                "x-atproto-bsky-topics":
                    "books,fantasy;2026-09-29T08:00:00Z",
            },
        )])
        self.assertEqual([row[0] for row in searched], ["fantasía"])
        self.assertNotIn("app.bsky.unspecced.getTrendingTopics", {
            row[0] for row in calls
        })


if __name__ == "__main__":
    unittest.main()
