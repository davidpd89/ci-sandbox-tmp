"""Regresiones offline del motor amplio de crecimiento Bluesky."""
import copy
import datetime
import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

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
    True,
    "OK",
    {"handle": "davidportodiaz.bsky.social"},
)
stub._own_reply_parent_uris = lambda: set()

with patch.dict(sys.modules, {"bluesky_interact": stub}):
    import bluesky_growth_scan as gs


def post(handle, rkey, text, *, likes=0, reposts=0, replies=0, quotes=0):
    return {
        "uri": f"at://did:plc:{handle.split('.')[0]}/app.bsky.feed.post/{rkey}",
        "author": {
            "handle": handle,
            "displayName": handle.split(".")[0],
            "description": "Lectora de fantasía y novelas",
        },
        "record": {
            "text": text,
            "createdAt": "2026-09-29T08:00:00Z",
        },
        "likeCount": likes,
        "repostCount": reposts,
        "replyCount": replies,
        "quoteCount": quotes,
    }


class GrowthScanTests(unittest.TestCase):
    def setUp(self):
        # Tres fuentes locales que Collector lee al iniciar: ningún test
        # debe acceder a registro/growth_seen/metrics del árbol operativo.
        self._scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self._scratch.cleanup)
        for key, name in (
            ("REGISTRO_CSV", "registro_interacciones.csv"),
            ("SEEN_CSV", "growth_seen.csv"),
            ("METRICS_CSV", "discovery_metrics.csv"),
        ):
            patcher = patch.object(gs, key, os.path.join(self._scratch.name, name))
            patcher.start()
            self.addCleanup(patcher.stop)

    def config(self):
        cfg = copy.deepcopy(gs._load_config())
        cfg["coverage"]["post_queries_per_family"] = 1
        cfg["coverage"]["actor_queries_total"] = 2
        cfg["tag_queries"] = []
        cfg["budgets"]["max_read_requests"] = 200
        cfg["budgets"]["max_candidates"] = 300
        return cfg

    def collector(self):
        c = gs.Collector(
            self.config(),
            write_metrics=False,
            today=datetime.date(2026, 9, 29),
            run_id="test",
        )
        c.own_handle = "davidportodiaz.bsky.social"
        c.own_did = "did:plc:david"
        return c

    def test_search_is_not_skipped_when_timeline_already_has_many_candidates(self):
        c = self.collector()
        timeline = [
            post(
                f"lector{i}.bsky.social",
                f"t{i}",
                "Estoy leyendo una novela de fantasía.",
            )
            for i in range(20)
        ]
        v2_content_calls = []
        actor_calls = []

        def fake_get(base, path, params, auth):
            if path == "app.bsky.feed.searchPostsV2":
                if params.get("excludeReplies"):
                    v2_content_calls.append(dict(params))
                    index = len(v2_content_calls)
                    return {"posts": [
                        post(
                            f"search{index}.bsky.social",
                            f"s{index}",
                            "Lectura y libros de fantasía.",
                        )
                    ]}
                return {"posts": []}
            return {}

        def fake_actors(query, limit=25):
            actor_calls.append(query)
            return [{
                "handle": f"actor{len(actor_calls)}.bsky.social",
                "description": "Escritora de fantasía",
            }]

        with patch.object(gs.b, "_get_notifications", return_value=[]), \
             patch.object(gs.b, "_get_timeline", return_value=timeline), \
             patch.object(gs.b, "_get", side_effect=fake_get), \
             patch.object(gs.b, "_search_posts", return_value=[]), \
             patch.object(gs.b, "_search_actors", side_effect=fake_actors):
            gs._initial_discovery(c)

        self.assertEqual(
            len(v2_content_calls),
            len(c.config["query_families"]),
        )
        self.assertTrue(all(x["excludeReplies"] for x in v2_content_calls))
        self.assertEqual(len(actor_calls), 2)
        self.assertGreater(len(c.candidates), 20)

    def test_starter_pack_follow_keeps_acquisition_source(self):
        c = self.collector()
        pack_uri = (
            "at://did:plc:curadora/app.bsky.graph.starterpack/fantasia"
        )
        c.add_notification_post({
            "reason": "starterpack-joined",
            "author": {
                "handle": "nueva-lectora.bsky.social",
                "description": "Lectora de fantasía",
            },
            "starterPack": {"uri": pack_uri},
            "record": {},
        })
        item = c.candidates["nueva-lectora.bsky.social"]
        self.assertIn(
            f"notification:starterpack-joined:{pack_uri}",
            item["source_keys"],
        )

    def test_record_post_targets_cover_like_repost_reply_and_quotes(self):
        parent = "at://did:plc:a/app.bsky.feed.post/parent"
        root = "at://did:plc:a/app.bsky.feed.post/root"
        quoted = "at://did:plc:b/app.bsky.feed.post/quoted"
        nested = "at://did:plc:c/app.bsky.feed.post/nested"
        value = {
            "subject": {"uri": parent},
            "reply": {
                "parent": {"uri": parent},
                "root": {"uri": root},
            },
            "embed": {
                "record": {
                    "uri": quoted,
                    "record": {"uri": nested},
                }
            },
        }
        self.assertEqual(
            gs._record_post_targets(value),
            [parent, root, quoted, nested],
        )

    def test_valued_history_hydrates_previous_interaction_targets(self):
        c = self.collector()
        targets = {
            "app.bsky.feed.like": "at://did:plc:a/app.bsky.feed.post/liked",
            "app.bsky.feed.repost": "at://did:plc:b/app.bsky.feed.post/reposted",
        }
        reply_uri = "at://did:plc:c/app.bsky.feed.post/replied"
        quote_uri = "at://did:plc:d/app.bsky.feed.post/quoted"

        def view(uri):
            handle = uri.split("/")[2].replace("did:plc:", "") + ".bsky.social"
            return {
                "uri": uri,
                "author": {
                    "handle": handle,
                    "description": "Lectora de fantasía",
                },
                "record": {
                    "text": "Lectura de fantasía y libros.",
                    "createdAt": "2026-09-29T06:00:00Z",
                },
            }

        def fake_get(base, path, params, auth):
            if path == "com.atproto.repo.listRecords":
                collection = params["collection"]
                if collection in targets:
                    return {"records": [{
                        "value": {"subject": {"uri": targets[collection]}}
                    }]}
                if collection == "app.bsky.feed.post":
                    return {"records": [{
                        "value": {
                            "reply": {
                                "parent": {"uri": reply_uri},
                                "root": {"uri": reply_uri},
                            },
                            "embed": {"record": {"uri": quote_uri}},
                        }
                    }]}
            if path == "app.bsky.feed.getPosts":
                return {"posts": [view(uri) for uri in params["uris"]]}
            raise AssertionError(path)

        with patch.object(gs.b, "_get", side_effect=fake_get):
            rows = gs._discover_valued_history(c)

        uris = {row["uri"] for row in rows}
        self.assertEqual(
            uris,
            set(targets.values()) | {reply_uri, quote_uri},
        )
        self.assertTrue(all("valued_history" in row["sources"] for row in rows))
        self.assertIn("valued_history", c.coverage()["attempted"])

    def test_search_content_v2_excludes_replies(self):
        c = self.collector()
        calls = []

        def fake_get(base, path, params, auth):
            calls.append((path, dict(params), auth))
            return {"posts": []}

        with patch.object(gs.b, "_get", side_effect=fake_get):
            rows = gs._search_content_v2(
                c, "lectura", 60, sort="recent"
            )

        self.assertEqual(rows, [])
        path, params, auth = calls[0]
        self.assertEqual(path, "app.bsky.feed.searchPostsV2")
        self.assertTrue(auth)
        self.assertTrue(params["excludeReplies"])
        self.assertEqual(params["languages"], ["es"])
        self.assertEqual(params["sort"], "recent")

    def test_search_content_v2_falls_back_to_v1_only_on_normal_error(self):
        c = self.collector()
        with patch.object(gs.b, "_get", side_effect=RuntimeError("no v2")), \
             patch.object(gs.b, "_search_posts", return_value=["fallback"]) as v1:
            rows = gs._search_content_v2(
                c, "lectura", 60, sort="top", since="2026-09-01T00:00:00Z"
            )
        self.assertEqual(rows, ["fallback"])
        v1.assert_called_once()
        self.assertTrue(any("fallback=v1" in issue for issue in c.issues))

    def test_search_content_v2_does_not_hide_rate_limit(self):
        c = self.collector()
        with patch.object(
            gs.b, "_get", side_effect=gs.b.RateLimitExceeded("429")
        ), patch.object(gs.b, "_search_posts") as v1:
            with self.assertRaises(gs.b.RateLimitExceeded):
                gs._search_content_v2(c, "lectura", 60)
        v1.assert_not_called()

    def test_niche_match_uses_word_boundaries(self):
        self.assertEqual(gs._hits("facebook"), 0)
        self.assertGreater(gs._hits("book community"), 0)
        self.assertGreater(gs._hits("Estoy leyendo fantasía"), 0)

    def test_jetstream_cache_adds_recurring_authors_as_candidates(self):
        c = self.collector()
        with patch.object(
            gs.js_cache,
            "read_recent_matches",
            return_value=[],
        ), patch.object(
            gs.js_cache,
            "read_active_authors",
            return_value=[{
                "did": "did:plc:repeat",
                "posts": 4,
                "matches": 6,
                "last_time_us": 1,
            }],
        ), patch.object(
            gs.b,
            "_get",
            return_value={"profiles": [{
                "did": "did:plc:repeat",
                "handle": "recurrente.bsky.social",
                "description": "Lectora de fantasía y libros",
                "viewer": {},
            }]},
        ):
            c.config["jetstream"]["db_path"] = "fake.sqlite3"
            gs._consume_jetstream_cache(c)

        item = c.candidates["recurrente.bsky.social"]
        self.assertIn("jetstream_author", item["sources"])
        self.assertTrue(any("4 posts afines" in x for x in item["signals"]))

    def test_bookmarks_become_strong_post_seeds(self):
        c = self.collector()
        bookmarked = post(
            "guardada.bsky.social",
            "saved",
            "Una reseña de fantasía que quiero releer.",
        )
        with patch.object(
            gs.b,
            "_get",
            return_value={"bookmarks": [{"item": bookmarked}]},
        ):
            gs._discover_bookmarks(c)
        item = c.candidates["guardada.bsky.social"]
        self.assertIn("bookmark", item["sources"])
        stored = c.posts[bookmarked["uri"]]
        self.assertIn("bookmark", stored["sources"])

    def test_manual_blocks_and_mutes_exclude_future_discovery(self):
        c = self.collector()
        responses = {
            "app.bsky.graph.getBlocks": {
                "blocks": [{"handle": "bloqueada.bsky.social"}],
            },
            "app.bsky.graph.getMutes": {
                "mutes": [{"handle": "silenciada.bsky.social"}],
            },
        }
        with patch.object(
            gs.b,
            "_get",
            side_effect=lambda base, path, params, auth: responses[path],
        ):
            gs._load_relationship_exclusions(c)

        self.assertFalse(c.add_actor(
            {"handle": "bloqueada.bsky.social", "description": "Lectora"},
            "actor_search",
        ))
        self.assertFalse(c.add_actor(
            {"handle": "silenciada.bsky.social", "description": "Lectora"},
            "actor_search",
        ))
        self.assertIn("relationship_exclusions", c.coverage()["attempted"])

    def test_activity_subscriptions_become_priority_candidates(self):
        c = self.collector()
        with patch.object(
            gs.b,
            "_get",
            return_value={"subscriptions": [{
                "did": "did:plc:sub",
                "handle": "suscrita.bsky.social",
                "description": "Escritora y lectora de fantasía",
            }]},
        ):
            gs._discover_activity_subscriptions(c)
        item = c.candidates["suscrita.bsky.social"]
        self.assertIn("activity_subscription", item["sources"])
        self.assertIn("activity_subscriptions", c.coverage()["attempted"])

    def test_structured_tags_are_preserved_for_dynamic_learning(self):
        p = post("tags.bsky.social", "tagged", "Hoy toca lectura")
        p["record"]["tags"] = ["FantasyReaders", "BookSky"]
        p["record"]["facets"] = [{
            "features": [{
                "$type": "app.bsky.richtext.facet#tag",
                "tag": "Romantasy",
            }]
        }]
        self.assertEqual(
            gs._structured_tags(p),
            ["FantasyReaders", "BookSky", "Romantasy"],
        )
        c = self.collector()
        c.add_post(p, "post_search", key="x")
        row = next(iter(c.posts.values()))
        self.assertEqual(
            row["tags"],
            ["FantasyReaders", "BookSky", "Romantasy"],
        )

    def test_thread_expansion_keeps_all_commenters_not_only_first(self):
        c = self.collector()
        seed = post(
            "semilla.bsky.social", "root",
            "¿Qué fantasía estáis leyendo?", replies=2,
        )
        seed_row = {
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
        }
        reply1 = post(
            "uno.bsky.social", "r1",
            "Estoy con una saga fantástica y me está encantando.",
        )
        reply2 = post(
            "dos.bsky.social", "r2",
            "Yo terminé ayer una novela de fantasía juvenil.",
        )
        thread = {
            "thread": {
                "post": seed,
                "replies": [
                    {"post": reply1, "replies": [{"post": reply2, "replies": []}]},
                ],
            }
        }
        with patch.object(gs.b, "_get", return_value=thread):
            gs._expand_threads(c, [seed_row])
        self.assertIn("uno.bsky.social", c.candidates)
        self.assertIn("dos.bsky.social", c.candidates)

    def test_zero_count_edges_do_not_spend_requests(self):
        c = self.collector()
        seed = post(
            "semilla.bsky.social", "quiet",
            "Una lectura de fantasía sin interacciones todavía.",
        )
        row = {
            "uri": seed["uri"],
            "url": gs._post_url(seed),
            "handle": "semilla.bsky.social",
            "text": seed["record"]["text"],
            "likes": 0,
            "reposts": 0,
            "replies": 0,
            "quotes": 0,
            "created_at": seed["record"]["createdAt"],
            "sources": {"post_search"},
            "source_keys": set(),
        }

        with patch.object(
            gs.b, "_post_engagers",
            side_effect=AssertionError("no debe abrir aristas vacías"),
        ), patch.object(
            gs.b, "_get",
            side_effect=AssertionError("no debe abrir un hilo sin replies"),
        ):
            before = c.budget.used
            gs._expand_threads(c, [row])
            gs._expand_engagers(c, [row])
            self.assertEqual(c.budget.used, before)

    def test_engager_expansion_opens_only_nonzero_edge_kinds(self):
        c = self.collector()
        seed = post(
            "semilla.bsky.social", "liked",
            "Una lectura de fantasía con likes.", likes=3,
        )
        row = {
            "uri": seed["uri"],
            "url": gs._post_url(seed),
            "handle": "semilla.bsky.social",
            "text": seed["record"]["text"],
            "likes": 3,
            "reposts": 0,
            "replies": 0,
            "quotes": 0,
            "created_at": seed["record"]["createdAt"],
            "sources": {"post_search"},
            "source_keys": set(),
        }
        kinds = []

        def fake_engagers(url, kind, limit):
            kinds.append(kind)
            return []

        with patch.object(gs.b, "_post_engagers", side_effect=fake_engagers):
            gs._expand_engagers(c, [row])

        self.assertEqual(kinds, ["likes"])

    def test_second_wave_reopens_only_vetted_active_posts(self):
        c = self.collector()
        c.config["budgets"]["second_wave_seeds"] = 2
        active = post(
            "vetada.bsky.social", "active",
            "¿Qué fantasía os ha sorprendido este mes?",
            likes=2, replies=1,
        )
        quiet = post(
            "vetada.bsky.social", "quiet",
            "Otra reflexión sobre fantasía.",
        )
        c.add_post(active, "author_feed", key="vetada.bsky.social")
        c.add_post(quiet, "author_feed", key="vetada.bsky.social")
        active_row = c.posts[active["uri"]]
        thread_calls = []
        engager_calls = []

        def fake_thread(collector, uri):
            thread_calls.append(uri)
            return []

        def fake_engagers(url, kind, limit):
            engager_calls.append(kind)
            return []

        with patch.object(gs, "_thread_posts", side_effect=fake_thread), patch.object(
            gs.b, "_post_engagers", side_effect=fake_engagers
        ):
            gs._expand_second_wave(c)

        self.assertEqual(thread_calls, [active_row["uri"]])
        self.assertEqual(engager_calls, ["likes"])

    def test_second_wave_diversifies_authors_and_records_yield(self):
        c = self.collector()
        c.config["budgets"]["second_wave_seeds"] = 2
        c.config["budgets"]["second_wave_min_new_handles"] = 1
        for rkey, handle, likes, replies in (
            ("a1", "a.bsky.social", 20, 5),
            ("a2", "a.bsky.social", 18, 4),
            ("b1", "b.bsky.social", 2, 1),
        ):
            c.add_post(
                post(
                    handle, rkey,
                    "Fantasía y lecturas para conversar con otros lectores.",
                    likes=likes, replies=replies,
                ),
                "author_feed", key=handle,
            )

        visited = []
        def fake_thread(collector, uri):
            visited.append(uri)
            collector.add_actor(
                {
                    "handle": f"nuevo{len(visited)}.bsky.social",
                    "description": "Lector de fantasía",
                },
                "thread_commenter",
                key=uri,
            )
            return []

        with patch.object(gs, "_thread_posts", side_effect=fake_thread), patch.object(
            gs.b, "_post_engagers", return_value=[]
        ):
            gs._expand_second_wave(c)

        self.assertEqual(len(visited), 2)
        handles = {c.posts[uri]["handle"] for uri in visited}
        self.assertEqual(handles, {"a.bsky.social", "b.bsky.social"})
        stats = [
            row for (surface, _), row in c.source_stats.items()
            if surface == "second_wave"
        ]
        self.assertEqual(len(stats), 2)
        self.assertTrue(all(len(row["new_handles"]) == 1 for row in stats))

    def test_relationship_lane_separates_community_from_acquisition(self):
        self.assertEqual(
            gs._relationship_lane({
                "known_date": "2026-09-20", "sources": {"valued_history"}
            }),
            "community",
        )
        self.assertEqual(
            gs._relationship_lane({
                "known_date": None, "following": False, "followed_by": False,
                "sources": {"post_search", "thread_commenter"},
            }),
            "acquisition",
        )
        self.assertEqual(
            gs._relationship_lane({
                "known_date": None, "following": False, "followed_by": True,
                "sources": {"notification"},
            }),
            "community",
        )

    def test_shortlist_reserves_acquisition_slots(self):
        c = self.collector()
        c.config["shortlist"]["acquisition_min"] = 3
        c.config["shortlist"]["community_target"] = 1
        c.config["shortlist"]["acquisition_cooldown_days"] = 3

        for i in range(6):
            item = c._candidate(f"nuevo{i}.bsky.social")
            item["sources"].add("post_search")
            item["score"] = 10 - i
        for i in range(6):
            item = c._candidate(f"conocido{i}.bsky.social")
            item["sources"].add("notification")
            item["known_date"] = "2026-09-29"
            item["score"] = 20 - i

        selected = gs._select_shortlist_candidates(c, 4)
        lanes = [gs._relationship_lane(item) for item in selected]
        self.assertEqual(lanes.count("acquisition"), 3)
        self.assertEqual(lanes.count("community"), 1)

    def test_shortlist_prefers_unseen_acquisition(self):
        c = self.collector()
        c.config["shortlist"]["acquisition_min"] = 2
        c.config["shortlist"]["community_target"] = 0
        c.config["shortlist"]["acquisition_cooldown_days"] = 3

        old = c._candidate("repetido.bsky.social")
        old["sources"].add("post_search")
        old["score"] = 100
        old["seen_date"] = datetime.date(2026, 9, 28)
        for i in range(2):
            item = c._candidate(f"fresco{i}.bsky.social")
            item["sources"].add("post_search")
            item["score"] = 5 - i

        selected = gs._select_shortlist_candidates(c, 2)
        self.assertEqual(
            {item["handle"] for item in selected},
            {"fresco0.bsky.social", "fresco1.bsky.social"},
        )

    def test_post_actions_remove_already_liked_and_reposted(self):
        c = self.collector()
        item = c._candidate("lectora.bsky.social")
        item["sources"].add("post_search")
        item["score"] = 10
        row = {
            "uri": "at://did:plc:lectora/app.bsky.feed.post/1",
            "url": "https://bsky.app/profile/lectora.bsky.social/post/1",
            "text": "¿Qué novela de fantasía os ha sorprendido más este año?",
            "likes": 10,
            "reposts": 2,
            "replies": 4,
            "quotes": 1,
            "bookmarks": 0,
            "reply_disabled": False,
            "embedding_disabled": False,
            "liked": True,
            "reposted": True,
        }
        actions = gs._post_actions(c, item, row)
        self.assertNotIn("like", actions)
        self.assertNotIn("repost", actions)
        self.assertIn("reply", actions)

    def test_frontier_continues_only_productive_branch(self):
        c = self.collector()
        c.config["budgets"]["second_wave_seeds"] = 1
        c.config["budgets"]["second_wave_depth"] = 2
        c.config["budgets"]["second_wave_profiles_per_depth"] = 1
        c.config["budgets"]["second_wave_min_new_handles"] = 1

        root = post(
            "semilla.bsky.social", "root",
            "Fantasía: ¿qué estáis leyendo?", replies=1,
        )
        c.add_post(root, "author_feed", key="semilla.bsky.social")
        child_uri = "at://did:plc:nuevo1/app.bsky.feed.post/child"
        thread_calls = []

        def fake_thread(collector, uri):
            thread_calls.append(uri)
            if uri == root["uri"]:
                return [post(
                    "nuevo1.bsky.social", "reply",
                    "Estoy leyendo una novela de fantasía.",
                )]
            if uri == child_uri:
                return [post(
                    "nuevo2.bsky.social", "reply2",
                    "También leo fantasía juvenil.",
                )]
            return []

        def fake_vet(collector, handles):
            self.assertEqual(handles, ["nuevo1.bsky.social"])
            child = post(
                "nuevo1.bsky.social", "child",
                "Otra conversación sobre fantasía.", replies=1,
            )
            collector.add_post(
                child, "author_feed", key="nuevo1.bsky.social"
            )

        with patch.object(gs, "_thread_posts", side_effect=fake_thread), \
             patch.object(gs.b, "_post_engagers", return_value=[]), \
             patch.object(gs, "_hydrate_selected_profiles"), \
             patch.object(gs, "_vet_selected_author_feeds", side_effect=fake_vet):
            gs._expand_second_wave(c)

        self.assertEqual(thread_calls, [root["uri"], child_uri])
        self.assertIn("nuevo2.bsky.social", c.candidates)
        keys = {
            key for (surface, key) in c.source_stats
            if surface == "second_wave"
        }
        self.assertTrue(any(key.startswith("d1:") for key in keys))
        self.assertTrue(any(key.startswith("d2:") for key in keys))

    def test_expansion_seeds_prefer_new_accounts(self):
        c = self.collector()
        for i in range(3):
            item = c._candidate(f"nuevo-seed{i}.bsky.social")
            item["sources"].add("post_search")
        for i in range(3):
            item = c._candidate(f"conocido-seed{i}.bsky.social")
            item["sources"].add("notification")
            item["known_date"] = "2026-09-29"

        seeds = gs._expansion_seed_candidates(c, 2)
        self.assertTrue(all(item["known_date"] is None for item in seeds))

    def test_unverified_relationship_never_offers_follow(self):
        c = self.collector()
        c.config["shortlist"]["profiles"] = 1
        c.config["shortlist"]["acquisition_min"] = 1
        c.config["shortlist"]["community_target"] = 0
        item = c._candidate("sin-viewer.bsky.social")
        item["sources"].add("post_search")
        item["profile"] = {
            "handle": "sin-viewer.bsky.social",
            "description": "Lector de fantasía y novelas",
        }
        row = post(
            "sin-viewer.bsky.social", "p1",
            "Estoy leyendo una novela de fantasía que me está sorprendiendo.",
        )
        c.add_post(row, "post_search", key="fantasía")

        result = gs._build_output(c)
        self.assertEqual(len(result["shortlist"]), 1)
        self.assertNotIn("follow", result["shortlist"][0]["actions"])
        self.assertEqual(result["readiness"]["acquisition_target"], 1)
        self.assertEqual(result["readiness"]["fresh_acquisition_candidates"], 1)
        self.assertTrue(result["readiness"]["fresh_target_met"])

    def test_high_score_candidate_is_auto_followed_without_ai(self):
        """29/09: David pidio explicitamente que un candidato claramente bueno
        no espere a que la IA lo revise uno a uno - el umbral mecanico
        (auto_follow_score_min) debe poner el follow directo en auto_plan,
        preservando la puntuacion (bio/spam/politica ya filtrados) como unica
        garantia, sin quitarle el candidato del shortlist (transparencia)."""
        c = self.collector()
        c.config["shortlist"]["profiles"] = 1
        c.config["shortlist"]["acquisition_min"] = 1
        c.config["shortlist"]["community_target"] = 0
        c.config["shortlist"]["auto_follow_score_min"] = 1.0
        item = c._candidate("candidato-fuerte.bsky.social")
        item["sources"].add("post_search")
        item["following"] = False
        item["profile"] = {
            "handle": "candidato-fuerte.bsky.social",
            "description": "Lectora de fantasía y novela negra",
        }
        row = post(
            "candidato-fuerte.bsky.social", "p1",
            "Estoy leyendo una novela de fantasía que me está sorprendiendo.",
        )
        c.add_post(row, "post_search", key="fantasía")

        result = gs._build_output(c)
        follows = [a for a in result["auto_plan"] if a["kind"] == "follow"]
        self.assertEqual(len(follows), 1)
        self.assertEqual(follows[0]["handle"], "candidato-fuerte.bsky.social")
        self.assertIn("umbral_mecanico", follows[0]["motivo"])
        # Transparencia: sigue apareciendo en el shortlist aunque ya se haya
        # decidido - la IA no debe tener que adivinar por que no se le pide
        # revisarlo.
        self.assertEqual(len(result["shortlist"]), 1)
        self.assertIn("follow", result["shortlist"][0]["actions"])

    def test_low_score_candidate_is_not_auto_followed(self):
        c = self.collector()
        c.config["shortlist"]["profiles"] = 1
        c.config["shortlist"]["acquisition_min"] = 1
        c.config["shortlist"]["community_target"] = 0
        c.config["shortlist"]["auto_follow_score_min"] = 999.0
        item = c._candidate("candidato-dudoso.bsky.social")
        item["sources"].add("post_search")
        item["following"] = False
        item["profile"] = {
            "handle": "candidato-dudoso.bsky.social",
            "description": "Lector de fantasía",
        }
        row = post(
            "candidato-dudoso.bsky.social", "p1",
            "Estoy leyendo una novela de fantasía.",
        )
        c.add_post(row, "post_search", key="fantasía")

        result = gs._build_output(c)
        self.assertEqual(
            [a for a in result["auto_plan"] if a["kind"] == "follow"], []
        )
        self.assertIn("follow", result["shortlist"][0]["actions"])

    def test_high_score_new_discovery_like_is_auto_approved(self):
        """El umbral de like (auto_like_score_min) cubre el caso que antes
        obligaba a revisar likes de descubrimiento nuevo uno a uno aunque el
        post ya puntuara muy alto por afinidad/conversacion real."""
        c = self.collector()
        c.config["shortlist"]["profiles"] = 1
        c.config["shortlist"]["acquisition_min"] = 1
        c.config["shortlist"]["community_target"] = 0
        c.config["shortlist"]["auto_like_score_min"] = 1.0
        item = c._candidate("descubrimiento-fuerte.bsky.social")
        item["sources"].add("post_search")
        item["profile"] = {
            "handle": "descubrimiento-fuerte.bsky.social",
            "description": "Lectora de fantasía",
        }
        row = post(
            "descubrimiento-fuerte.bsky.social", "p1",
            "Estoy leyendo una novela de fantasía que me está sorprendiendo.",
        )
        c.add_post(row, "post_search", key="fantasía")

        result = gs._build_output(c)
        likes = [a for a in result["auto_plan"] if a["kind"] == "like"]
        self.assertEqual(len(likes), 1)
        self.assertEqual(likes[0]["handle"], "descubrimiento-fuerte.bsky.social")
        self.assertIn("umbral_mecanico", likes[0]["motivo"])

    def test_high_score_like_skips_off_niche_post_from_off_niche_account(self):
        """02/10: el score es de la cuenta; un post fuera de nicho de una
        cuenta sin bio de nicho no debe recibir like automatico."""
        c = self.collector()
        c.config["shortlist"]["profiles"] = 1
        c.config["shortlist"]["acquisition_min"] = 1
        c.config["shortlist"]["community_target"] = 0
        c.config["shortlist"]["auto_like_score_min"] = 0.0
        item = c._candidate("periodico.bsky.social")
        item["sources"].add("popular_feed")
        item["profile"] = {"handle": "periodico.bsky.social", "description": "Noticias"}
        row = post(
            "periodico.bsky.social", "p1",
            "El equipo gana el partido de ayer por tres goles de diferencia.",
        )
        row["author"]["description"] = "Noticias"
        c.add_post(row, "popular_feed", key="books")

        result = gs._build_output(c)
        likes = [a for a in result["auto_plan"] if a["kind"] == "like"]
        self.assertEqual(likes, [])

    def test_invalid_handle_is_excluded_from_shortlist_and_plan(self):
        """02/10: handle.invalid bloqueaba el preflight de todo el lote."""
        c = self.collector()
        c.config["shortlist"]["profiles"] = 5
        c.config["shortlist"]["auto_like_score_min"] = 0.0
        row = post("handle.invalid", "p1", "Estoy leyendo una novela de fantasía")
        c.add_post(row, "post_search", key="fantasía")
        result = gs._build_output(c)
        self.assertEqual([s["handle"] for s in result["shortlist"]], [])
        self.assertEqual(result["auto_plan"], [])

    def test_joined_starter_pack_becomes_acquisition_surface(self):
        c = self.collector()
        c.config["budgets"]["joined_starter_pack_expansions"] = 1
        c.add_actor(
            {"handle": "semilla-pack.bsky.social", "description": "Lectora de fantasía"},
            "post_search",
            key="fantasía",
        )
        pack_uri = "at://did:plc:curador/app.bsky.graph.starterpack/libros"
        list_uri = "at://did:plc:curador/app.bsky.graph.list/libros"

        def fake_get(base, path, params, auth):
            if path == "app.bsky.actor.getProfiles":
                return {"profiles": [{
                    "did": "did:plc:semilla",
                    "handle": "semilla-pack.bsky.social",
                    "description": "Lectora de fantasía",
                    "followersCount": 20,
                    "followsCount": 30,
                    "postsCount": 50,
                    "viewer": {},
                    "joinedViaStarterPack": {
                        "uri": pack_uri,
                        "record": {
                            "name": "Lectores de fantasía",
                            "description": "Libros y fantasía",
                            "list": list_uri,
                        },
                        "joinedWeekCount": 4,
                        "joinedAllTimeCount": 20,
                    },
                }]}
            if path == "app.bsky.graph.getList":
                self.assertEqual(params["list"], list_uri)
                return {"items": [{
                    "subject": {
                        "handle": "miembro-pack.bsky.social",
                        "description": "Lector de novelas y fantasía",
                    }
                }]}
            raise AssertionError(path)

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._hydrate_selected_profiles(c, ["semilla-pack.bsky.social"])
            gs._expand_joined_starter_packs(c)

        seed = c.candidates["semilla-pack.bsky.social"]
        self.assertIn("joined_starter_pack", seed["sources"])
        self.assertIn(
            f"joined_starter_pack:{pack_uri}", seed["source_keys"]
        )
        self.assertIn("miembro-pack.bsky.social", c.candidates)

    def test_old_notification_does_not_bypass_community_cooldown(self):
        c = self.collector()
        item = c._candidate("relacion.bsky.social")
        item["sources"].add("notification")
        item["known_date"] = "2026-09-29"
        item["score"] = 10
        item["last_notification_at"] = "2026-09-20T10:00:00Z"
        item["notification_unread"] = True
        self.assertEqual(gs._community_priority(c, item), 7.0)

        item["last_notification_at"] = "2026-09-29T08:00:00Z"
        self.assertEqual(gs._community_priority(c, item), 10.0)

    def test_notification_records_unread_and_recency(self):
        c = self.collector()
        c.add_notification_post({
            "reason": "follow",
            "isRead": False,
            "indexedAt": "2026-09-29T08:30:00Z",
            "author": {
                "handle": "reciente.bsky.social",
                "description": "Lector de fantasía",
            },
            "record": {},
        })
        item = c.candidates["reciente.bsky.social"]
        self.assertTrue(item["notification_unread"])
        self.assertEqual(
            item["last_notification_at"], "2026-09-29T08:30:00Z"
        )
        self.assertIn("notification_unread", item["sources"])

    def test_frontier_historical_yield_boosts_good_hub(self):
        c = self.collector()
        low = post(
            "low.bsky.social", "low",
            "Fantasía y libros.", replies=1,
        )
        high = post(
            "high.bsky.social", "high",
            "Fantasía y libros.", replies=1,
        )
        c.add_post(low, "author_feed", key="low.bsky.social")
        c.add_post(high, "author_feed", key="high.bsky.social")
        c.query_stats[("second_wave_author", "high.bsky.social")] = {
            "attempts": 2,
            "new_handles": 10,
        }

        seeds = gs._frontier_posts(c, None, set(), 1)
        self.assertEqual(seeds[0]["handle"], "high.bsky.social")

    def test_post_can_offer_like_reply_repost_and_quote(self):
        c = self.collector()
        item = {
            "handle": "lectora.bsky.social",
            "sources": {"post_search", "thread_commenter"},
            "source_keys": set(),
            "profile": {
                "description": "Lectora de fantasía y literatura",
                "followersCount": 100,
                "followsCount": 120,
                "postsCount": 300,
            },
            "posts": set(),
            "known_date": None,
            "following": False,
            "score": 8.0,
            "signals": [],
        }
        p = post(
            "lectora.bsky.social",
            "good",
            "Estoy leyendo una novela de fantasía con un worldbuilding enorme. "
            "¿Qué os funciona más: descubrir el mundo poco a poco o tener un mapa desde el inicio?",
            likes=12,
            reposts=3,
            replies=7,
        )
        self.assertEqual(
            gs._post_actions(c, item, {
                "uri": p["uri"],
                "url": gs._post_url(p),
                "text": p["record"]["text"],
                "likes": 12,
                "reposts": 3,
                "replies": 7,
                "quotes": 1,
                "created_at": p["record"]["createdAt"],
                "sources": {"post_search"},
                "source_keys": set(),
            }),
            ["like", "reply", "repost", "quote"],
        )

    def test_graph_neighbors_expand_followers_and_follows(self):
        c = self.collector()
        c.add_actor(
            {
                "handle": "semilla.bsky.social",
                "description": "Autora de fantasía y lectora",
            },
            "actor_search",
        )
        calls = []

        def fake_get(base, path, params, auth):
            calls.append((path, params["actor"]))
            if path.endswith("getFollowers"):
                return {
                    "followers": [{
                        "handle": "seguidora.bsky.social",
                        "description": "Lectora de novelas",
                    }]
                }
            if path.endswith("getFollows"):
                return {
                    "follows": [{
                        "handle": "seguida.bsky.social",
                        "description": "Escritora de fantasía",
                    }]
                }
            raise AssertionError(path)

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._expand_graph_neighbors(c)

        self.assertIn("seguidora.bsky.social", c.candidates)
        self.assertIn("seguida.bsky.social", c.candidates)
        self.assertIn("follower_neighbor", c.candidates["seguidora.bsky.social"]["sources"])
        self.assertIn("following_neighbor", c.candidates["seguida.bsky.social"]["sources"])
        self.assertEqual(
            {path for path, _ in calls},
            {"app.bsky.graph.getFollowers", "app.bsky.graph.getFollows"},
        )

    def test_starter_pack_members_enter_same_candidate_pipeline(self):
        c = self.collector()
        c.add_actor(
            {
                "handle": "curadora.bsky.social",
                "description": "BookSky, fantasía y lecturas",
            },
            "actor_search",
        )
        list_uri = (
            "at://did:plc:curadora/app.bsky.graph.list/packlist"
        )

        def fake_get(base, path, params, auth):
            if path == "app.bsky.graph.getActorStarterPacks":
                return {
                    "starterPacks": [{
                        "uri": "at://did:plc:curadora/app.bsky.graph.starterpack/x",
                        "record": {
                            "name": "Lectores de fantasía",
                            "description": "BookSky en español",
                            "list": list_uri,
                        },
                    }]
                }
            if path == "app.bsky.graph.getList":
                self.assertEqual(params["list"], list_uri)
                return {
                    "list": {},
                    "items": [{
                        "subject": {
                            "handle": "miembro.bsky.social",
                            "description": "Lector de fantasía juvenil",
                        }
                    }],
                }
            raise AssertionError(path)

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._expand_starter_packs(c)

        self.assertIn("miembro.bsky.social", c.candidates)
        self.assertIn("starter_pack", c.candidates["miembro.bsky.social"]["sources"])

    def test_substantive_affine_post_can_offer_reply_without_question_mark(self):
        c = self.collector()
        item = {
            "handle": "comentadora.bsky.social",
            "sources": {"thread_commenter", "author_feed"},
            "source_keys": set(),
            "profile": {"description": "Lectora de fantasía y novelas"},
            "posts": set(),
            "known_date": None,
            "following": False,
            "score": 7.0,
            "signals": ["comenta en conversaciones reales"],
        }
        row = {
            "uri": "at://did:plc:x/app.bsky.feed.post/opinion",
            "url": "https://bsky.app/profile/comentadora.bsky.social/post/opinion",
            "text": (
                "La fantasía me funciona mucho más cuando el mundo se descubre "
                "a través de las decisiones de los personajes."
            ),
            "likes": 1,
            "reposts": 0,
            "replies": 0,
            "quotes": 0,
            "created_at": "2026-09-29T08:00:00Z",
            "sources": {"author_feed"},
            "source_keys": set(),
        }
        self.assertIn("reply", gs._post_actions(c, item, row))

    def test_reply_and_quote_are_not_offered_when_viewer_disables_them(self):
        c = self.collector()
        item = {
            "handle": "cerrada.bsky.social",
            "sources": {"post_search", "thread_commenter"},
            "source_keys": set(),
            "profile": {"description": "Lectora de fantasía"},
            "posts": set(),
            "known_date": None,
            "following": False,
            "score": 8.0,
            "signals": [],
        }
        row = {
            "uri": "at://did:plc:x/app.bsky.feed.post/closed",
            "url": "https://bsky.app/profile/cerrada.bsky.social/post/closed",
            "text": (
                "La fantasía me funciona por cómo construye el mundo y los personajes. "
                "¿Qué os interesa más cuando empezáis una saga nueva?"
            ),
            "likes": 8,
            "reposts": 2,
            "replies": 4,
            "quotes": 1,
            "bookmarks": 2,
            "reply_disabled": True,
            "embedding_disabled": True,
            "created_at": "2026-09-29T08:00:00Z",
            "sources": {"post_search"},
            "source_keys": set(),
        }
        actions = gs._post_actions(c, item, row)
        self.assertIn("like", actions)
        self.assertIn("repost", actions)
        self.assertNotIn("reply", actions)
        self.assertNotIn("quote", actions)

    def test_actionability_refresh_reads_viewer_state_in_batches(self):
        c = self.collector()
        p = post(
            "autora.bsky.social",
            "one",
            "Lectura de fantasía con una conversación interesante.",
        )
        c.add_post(p, "post_search", key="fantasía")
        c.candidates["autora.bsky.social"]["score"] = 8.0

        def fake_get(base, path, params, auth):
            self.assertEqual(path, "app.bsky.feed.getPosts")
            self.assertTrue(auth)
            return {"posts": [{
                **p,
                "viewer": {
                    "replyDisabled": True,
                    "embeddingDisabled": False,
                },
            }]}

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._refresh_post_actionability(c)

        stored = c.posts[p["uri"]]
        self.assertTrue(stored["reply_disabled"])
        self.assertFalse(stored["embedding_disabled"])
        self.assertIn("post_actionability", c.coverage()["attempted"])

    def test_valued_likers_become_taste_listener_targets(self):
        c = self.collector()
        seed = post(
            "semilla.bsky.social",
            "root",
            "Una lectura de fantasía que David ya valoró.",
        )
        seed_row = {
            "uri": seed["uri"],
            "url": gs._post_url(seed),
            "handle": "semilla.bsky.social",
            "text": seed["record"]["text"],
            "likes": 3,
            "reposts": 0,
            "replies": 0,
            "quotes": 0,
            "bookmarks": 0,
            "created_at": seed["record"]["createdAt"],
            "sources": {"valued_history"},
            "source_keys": set(),
        }

        def fake_engagers(url, kind, limit):
            if kind == "likes":
                return [{"actor": {
                    "did": "did:plc:curator",
                    "handle": "curator.bsky.social",
                    "description": "Lectora de fantasía y libros",
                }}]
            return []

        with patch.object(gs.b, "_post_engagers", side_effect=fake_engagers):
            gs._expand_engagers(c, [seed_row], track_colikers=True)

        self.assertEqual(c.coliker_counts["did:plc:curator"], 1)
        output = gs._build_output(c)
        self.assertEqual(
            output["taste_listener_dids"][0]["did"],
            "did:plc:curator",
        )
        compact = gs.compact_ai_view(output)
        self.assertNotIn("taste_listener_dids", compact)

    def test_taste_cache_hydrates_posts_and_marks_path_breadth(self):
        c = self.collector()
        uri = "at://did:plc:author/app.bsky.feed.post/taste"
        hydrated = {
            "uri": uri,
            "author": {
                "did": "did:plc:author",
                "handle": "descubierta.bsky.social",
                "description": "Lectora de fantasía",
            },
            "record": {
                "text": "Una fantasía que me ha sorprendido mucho.",
                "createdAt": "2026-09-29T08:00:00Z",
            },
            "likeCount": 3,
            "repostCount": 0,
            "replyCount": 1,
            "quoteCount": 0,
        }
        with patch.object(
            gs.taste_cache,
            "read_candidate_posts",
            return_value=[{"uri": uri, "paths": 3, "last_time_us": 1}],
        ), patch.object(
            gs.b,
            "_get",
            return_value={"posts": [hydrated]},
        ):
            gs._consume_taste_cache(c)

        item = c.candidates["descubierta.bsky.social"]
        self.assertIn("taste_like", item["sources"])
        self.assertEqual(c.posts[uri]["taste_paths"], 3)
        self.assertTrue(any("3 curadores afines" in x for x in item["signals"]))

    def test_good_small_post_can_offer_repost_without_popularity_gate(self):
        c = self.collector()
        item = {
            "handle": "pequena.bsky.social",
            "sources": {"thread_commenter", "post_search"},
            "source_keys": set(),
            "profile": {"description": "Lectora y escritora de fantasía"},
            "posts": set(),
            "known_date": None,
            "following": False,
            "score": 7.0,
            "signals": [],
        }
        row = {
            "uri": "at://did:plc:x/app.bsky.feed.post/small",
            "url": "https://bsky.app/profile/pequena.bsky.social/post/small",
            "text": (
                "Esta novela de fantasía me está funcionando por cómo presenta "
                "el mundo sin explicarlo todo de golpe."
            ),
            "likes": 0,
            "reposts": 0,
            "replies": 0,
            "quotes": 0,
            "created_at": "2026-09-29T08:00:00Z",
            "sources": {"post_search"},
            "source_keys": set(),
        }
        self.assertIn("repost", gs._post_actions(c, item, row))

    def test_coverage_tracks_attempted_surfaces_even_with_zero_results(self):
        c = self.collector()
        for surface in c.config["coverage"]["required_surfaces"]:
            c.mark_attempted(surface)
        self.assertEqual(c.coverage()["missing"], [])

    def test_ai_view_excludes_detailed_source_metrics(self):
        full = {
            "run_id": "x",
            "date": "2026-09-29",
            "budget": {},
            "coverage": {},
            "totals": {},
            "auto_plan": [],
            "shortlist": [],
            "source_metrics": {"post_search:lectura": {"fetched": 100}},
            "issues": [],
        }
        compact = gs.ai_view(full)
        self.assertNotIn("source_metrics", compact)
        self.assertIn("shortlist", compact)

    def test_discovery_yields_to_profile_review_reserve(self):
        cfg = self.config()
        cfg["budgets"]["max_read_requests"] = 10
        cfg["budgets"]["profile_review_reserve"] = 3
        c = gs.Collector(
            cfg,
            write_metrics=False,
            today=datetime.date(2026, 9, 29),
            run_id="reserve",
        )
        for _ in range(7):
            c.call("post_search", lambda: None)
        c.protect_review_budget = True

        with self.assertRaises(gs.ReviewReserveReached):
            c.call("graph_neighbors", lambda: None)

        # La reserva existe precisamente para estas lecturas de revisión.
        self.assertIsNone(c.call("author_feed", lambda: None))
        self.assertEqual(c.budget.remaining, 2)

    def test_compact_ai_view_hides_urls_sources_and_auto_plan(self):
        full = {
            "run_id": "r1",
            "date": "2026-09-29",
            "budget": {"used": 10, "maximum": 280, "remaining": 270},
            "coverage": {"missing": []},
            "totals": {"auto_plan": 3, "shortlist": 1},
            "auto_plan": [{
                "handle": "x.bsky.social",
                "kind": "like",
                "url": "https://bsky.app/profile/x/post/1",
            }],
            "shortlist": [{
                "id": "G001",
                "handle": "lectora.bsky.social",
                "score": 8.5,
                "sources": ["post_search", "thread_commenter"],
                "signals": ["bio afín"],
                "profile": {
                    "display_name": "Lectora",
                    "bio": "Fantasía y libros",
                    "followers": 10,
                    "following": 20,
                    "posts": 30,
                },
                "actions": ["follow", "interact"],
                "posts": [{
                    "id": "G001-P1",
                    "url": "https://bsky.app/profile/lectora/post/a",
                    "text": "Una lectura de fantasía.",
                    "sources": ["post_search"],
                    "actions": ["like", "reply"],
                    "stats": {
                        "likes": 1, "reposts": 2, "replies": 3,
                        "quotes": 4, "bookmarks": 5,
                    },
                }],
            }],
            "issues": [],
        }
        compact = gs.compact_ai_view(full)
        encoded = __import__("json").dumps(compact)
        self.assertNotIn("https://", encoded)
        self.assertNotIn('"sources"', encoded)
        self.assertNotIn('"auto_plan"', encoded)
        self.assertEqual(compact["auto_plan_count"], 3)
        self.assertEqual(
            compact["shortlist"][0]["posts"][0]["eng"],
            [1, 2, 3, 4, 5],
        )

    def test_candidate_cap_limits_memory_not_source_coverage(self):
        cfg = self.config()
        cfg["budgets"]["max_candidates"] = 2
        c = gs.Collector(
            cfg,
            write_metrics=False,
            today=datetime.date(2026, 9, 29),
            run_id="cap",
        )
        c.own_handle = "davidportodiaz.bsky.social"
        self.assertTrue(c.add_post(post("a.bsky.social", "a", "Lectura libro"), "post_search"))
        self.assertTrue(c.add_post(post("b.bsky.social", "b", "Lectura libro"), "post_search"))
        self.assertFalse(c.add_post(post("c.bsky.social", "c", "Lectura libro"), "post_search"))
        c.mark_attempted("actor_search")
        self.assertIn("actor_search", c.coverage()["attempted"])

    def test_like_is_not_offered_for_posts_older_than_the_limit(self):
        """05/10: se daban likes a posts de hace 338 dias."""
        c = self.collector()
        c.config["shortlist"]["like_max_age_days"] = 45
        item = c._candidate("lectora.bsky.social")
        item["sources"].add("post_search")
        old = post("lectora.bsky.social", "viejo", "Estoy leyendo una novela de fantasía muy buena.")
        old["record"]["createdAt"] = "2025-11-01T08:00:00Z"
        recent = post("lectora.bsky.social", "nuevo", "Estoy leyendo una novela de fantasía muy buena.")
        c.add_post(old, "post_search", key="q")
        c.add_post(recent, "post_search", key="q")
        by_uri = {p["uri"]: p for p in c.posts.values()}
        self.assertNotIn("like", gs._post_actions(c, item, by_uri[old["uri"]]))
        self.assertIn("like", gs._post_actions(c, item, by_uri[recent["uri"]]))

    def test_shortlist_gaps_get_their_author_feed_vetted(self):
        """05/10: 594 de 1.000 perfiles de la shortlist no tenian ningun post y no podian recibir like."""
        c = self.collector()
        c.config["shortlist"]["profiles"] = 3
        c.config["shortlist"]["acquisition_min"] = 3
        c.config["budgets"]["vet_gap_profiles"] = 2
        for name in ("a", "b", "c"):
            item = c._candidate(f"{name}.bsky.social")
            item["sources"].add("pool")
            item["profile"] = {"handle": f"{name}.bsky.social", "description": "Lectora de fantasía y novelas"}
        feeds = []

        def fake_get(base, path, params, auth):
            if path == "app.bsky.feed.getAuthorFeed":
                feeds.append(params["actor"])
                handle = params["actor"]
                return {"feed": [{"post": post(handle, "p1", "Estoy leyendo una novela de fantasía.")}]}
            return {}

        with patch.object(gs.b, "_get", side_effect=fake_get):
            gs._vet_shortlist_gaps(c)
        self.assertEqual(len(feeds), 2)                                 # tope vet_gap_profiles
        self.assertEqual(sum(1 for i in c.candidates.values() if i["posts"]), 2)

    def test_pool_offers_accounts_as_candidates_and_skips_known_and_self(self):
        import bluesky_pool as pool
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "pool.sqlite3")
            db = pool.connect(db_path)
            for handle in ("nueva.bsky.social", "conocida.bsky.social", "davidportodiaz.bsky.social"):
                pool.upsert(db, {"did": "did:plc:" + handle.split(".")[0], "handle": handle, "description": "Lectora de fantasía y novela juvenil"},
                            "ed.bsky.social", "followers", "2026-09-29")
            db.commit()
            db.close()
            c = self.collector()
            c.config["budgets"]["pool_candidates"] = 10
            c.known["conocida.bsky.social"] = datetime.date(2026, 9, 1)
            original = pool.connect
            with patch.object(pool, "connect", lambda path=None: original(db_path)):
                gs._consume_pool(c)
        self.assertIn("nueva.bsky.social", c.candidates)
        self.assertIn("pool", c.candidates["nueva.bsky.social"]["sources"])
        self.assertNotIn("davidportodiaz.bsky.social", c.candidates)
        self.assertNotIn("pool", c.candidates.get("conocida.bsky.social", {}).get("sources", set()))

    def test_pool_scan_failure_does_not_consume_unexamined_reserve(self):
        import bluesky_pool as pool
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "pool.sqlite3")
            db = pool.connect(db_path)
            pool.upsert(db, {"did": "did:plc:lectora", "handle": "lectora.bsky.social",
                             "description": "Lectora de fantasía y novelas"},
                        "semilla.bsky.social", "followers", "2026-10-05")
            db.commit()
            db.close()
            c = self.collector()
            c.config["budgets"]["pool_candidates"] = 5
            original_connect = pool.connect
            with patch.object(pool, "connect", lambda path=None: original_connect(db_path)), \
                 patch.object(c, "add_actor", side_effect=RuntimeError("fallo simulado")):
                gs._consume_pool(c)
            db = original_connect(db_path)
            try:
                row = db.execute("SELECT offered_at, offered_count FROM accounts WHERE did=?",
                                 ("did:plc:lectora",)).fetchone()
                self.assertEqual(row, (None, 0))
            finally:
                db.close()
            self.assertTrue(any("fallo simulado" in line for line in c.issues))

    def test_pool_marks_examined_rows_only_after_consumption(self):
        import bluesky_pool as pool
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "pool.sqlite3")
            db = pool.connect(db_path)
            pool.upsert(db, {"did": "did:plc:lectora", "handle": "lectora.bsky.social",
                             "description": "Lectora de fantasía y novelas"},
                        "semilla.bsky.social", "followers", "2026-10-05")
            db.commit()
            db.close()
            c = self.collector()
            c.config["budgets"]["pool_candidates"] = 5
            original_connect = pool.connect
            with patch.object(pool, "connect", lambda path=None: original_connect(db_path)):
                gs._consume_pool(c)
            db = original_connect(db_path)
            try:
                row = db.execute("SELECT offered_at, offered_count FROM accounts WHERE did=?",
                                 ("did:plc:lectora",)).fetchone()
                self.assertEqual(row, (c.today.isoformat(), 1))
            finally:
                db.close()
            self.assertIn("lectora.bsky.social", c.candidates)

    def test_pool_full_shortlist_keeps_unexamined_reserve_eligible(self):
        import bluesky_pool as pool
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pool.sqlite3")
            db = pool.connect(path)
            pool.upsert(db, {"did": "did:plc:book", "handle": "book.bsky.social",
                             "description": "Lector de libros y fantasía"},
                        "semilla.bsky.social", "followers", "2026-10-05")
            db.commit()
            db.close()
            c = self.collector()
            c.config["budgets"]["pool_candidates"] = 5
            c.config["budgets"]["max_candidates"] = 0
            original_connect = pool.connect
            with patch.object(pool, "connect", lambda path=None: original_connect(path or
                                            os.path.join(tmp, "pool.sqlite3"))):
                gs._consume_pool(c)
            db = original_connect(path)
            try:
                self.assertEqual(db.execute(
                    "SELECT offered_at, offered_count FROM accounts WHERE did='did:plc:book'"
                ).fetchone(), (None, 0))
            finally:
                db.close()

    def test_pool_consumption_holds_exclusive_sqlite_claim_lock(self):
        import bluesky_pool as pool
        import sqlite3
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pool.sqlite3")
            first = pool.connect(path)
            pool.upsert(first, {"did": "did:plc:writer", "handle": "writer.bsky.social",
                                "description": "Lectora de fantasía y novela"},
                        "semilla.bsky.social", "followers", "2026-10-05")
            first.commit()
            first.close()
            second = sqlite3.connect(path, timeout=0.01)
            c = self.collector()
            c.config["budgets"]["pool_candidates"] = 1
            old_add = c.add_actor
            checked = []

            def assert_locked(actor, source, *, key=""):
                with self.assertRaises(sqlite3.OperationalError):
                    second.execute("BEGIN IMMEDIATE")
                checked.append(True)
                return old_add(actor, source, key=key)

            original_connect = pool.connect
            try:
                with patch.object(pool, "connect", lambda ignored=None: original_connect(path)), \
                     patch.object(c, "add_actor", side_effect=assert_locked):
                    gs._consume_pool(c)
            finally:
                second.close()
            self.assertTrue(checked)
            check = original_connect(path)
            try:
                self.assertEqual(check.execute(
                    "SELECT offered_count FROM accounts WHERE did='did:plc:writer'"
                ).fetchone(), (1,))
            finally:
                check.close()

    def test_pool_mid_batch_failure_rolls_back_offer_claims(self):
        import bluesky_pool as pool
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pool.sqlite3")
            db = pool.connect(path)
            for handle in ("first.bsky.social", "second.bsky.social"):
                pool.upsert(db, {"did": "did:plc:" + handle.split(".")[0],
                                 "handle": handle,
                                 "description": "Lectora de fantasía y novela"},
                            "semilla.bsky.social", "followers", "2026-10-05")
            db.commit()
            db.close()
            c = self.collector()
            c.config["budgets"]["pool_candidates"] = 2
            calls = []
            original_add = c.add_actor

            def fail_second(actor, source, *, key=""):
                calls.append(actor["did"])
                if len(calls) == 2:
                    raise RuntimeError("second profile failed")
                return original_add(actor, source, key=key)

            original_connect = pool.connect
            with patch.object(pool, "connect", lambda ignored=None: original_connect(path)), \
                 patch.object(c, "add_actor", side_effect=fail_second):
                gs._consume_pool(c)
            self.assertEqual(len(calls), 2)
            db = original_connect(path)
            try:
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM accounts WHERE offered_at IS NOT NULL"
                ).fetchone(), (0,))
            finally:
                db.close()
            self.assertTrue(any("second profile failed" in i for i in c.issues))

    def test_reassigned_handle_never_merges_two_dids(self):
        c = self.collector()
        first = {"handle": "reader.bsky.social", "did": "did:plc:first",
                 "description": "Lectora de fantasía y novela"}
        second = {"handle": "reader.bsky.social", "did": "did:plc:second",
                  "description": "Lectora de fantasía y novela"}
        self.assertTrue(c.add_actor(first, "source_first"))
        self.assertFalse(c.add_actor(second, "source_second"))
        item = c.candidates["reader.bsky.social"]
        self.assertEqual(item["profile"]["did"], "did:plc:first")
        self.assertNotIn("source_second", item["sources"])
        self.assertIn("BLUESKY_CONFLICTO_IDENTIDAD_DID", c.issues)
        row = post("reader.bsky.social", "different-did", "Lectura de fantasía")
        row["author"]["did"] = "did:plc:second"
        self.assertFalse(c.add_post(row, "source_second"))
        self.assertNotIn(row["uri"], c.posts)

    def test_author_rejected_for_spam_cannot_enter_via_post(self):
        c = self.collector()
        row = post("spam.bsky.social", "rkey", "Leo fantasía juvenil")
        row["author"]["description"] = "casino crypto trading"
        self.assertFalse(c.add_post(row, "post_search"))
        self.assertNotIn(row["uri"], c.posts)
        self.assertNotIn("spam.bsky.social", c.candidates)

    def test_invalid_actor_and_post_shapes_fail_closed(self):
        c = self.collector()
        self.assertFalse(c.add_actor({"handle": 17, "description": "lectura"}, "x"))
        self.assertFalse(c.add_actor({"handle": "x.bsky.social",
                                     "description": {"not": "text"}}, "x"))
        self.assertFalse(c.add_post({"author": "bad", "record": {}}, "x"))
        self.assertFalse(c.add_post({"author": {"handle": "x.bsky.social"},
                                     "record": {"text": [1]},
                                     "uri": "at://did:plc:x/app.bsky.feed.post/r"}, "x"))
        self.assertEqual(c.candidates, {})
        self.assertEqual(c.posts, {})

    def test_shortlist_identity_dedup_uses_did_not_mutable_handle(self):
        a = {"handle": "old.bsky.social", "profile": {"did": "did:plc:same"},
             "score": 5.0, "posts": {"p1"}}
        b = {"handle": "new.example", "profile": {"did": "did:plc:same"},
             "score": 8.0, "posts": {"p1", "p2"}}
        other = {"handle": "other.bsky.social",
                 "profile": {"did": "did:plc:other"},
                 "score": 4.0, "posts": set()}
        no_did = {"handle": "unknown.bsky.social", "profile": {},
                  "score": 3.0, "posts": set()}
        chosen = gs._unique_account_items([a, b, other, no_did, a])
        self.assertEqual({x["handle"] for x in chosen},
                         {"new.example", "other.bsky.social", "unknown.bsky.social"})
        self.assertEqual(len(chosen), 3)

    def test_author_feeds_can_be_fetched_in_parallel_with_budget_and_errors(self):
        c = self.collector()
        c.config["budgets"]["fetch_workers"] = 4
        c.config["budgets"]["max_read_requests"] = 5
        c.budget = gs.gc.ReadBudget(5)
        names = ["a", "b", "c", "d", "e", "f"]
        for name in names:
            c._candidate(f"{name}.bsky.social")["sources"].add("pool")

        def fake_get(base, path, params, auth):
            if params["actor"] == "c.bsky.social":
                raise RuntimeError("GET getAuthorFeed fallo (400): Profile not found")
            return {"feed": [{"post": post(params["actor"], "p1", "Estoy leyendo una novela de fantasía.")}]}

        with patch.object(gs.b, "_get", side_effect=fake_get):
            with self.assertRaises(gs.gc.ReadBudgetExceeded):       # el sexto handle ya no tiene presupuesto: igual que en secuencial
                gs._vet_selected_author_feeds(c, [f"{n}.bsky.social" for n in names])
        self.assertEqual(c.budget.used, 5)
        with_posts = {h for h, i in c.candidates.items() if i["posts"]}
        self.assertEqual(with_posts, {"a.bsky.social", "b.bsky.social", "d.bsky.social", "e.bsky.social"})
        self.assertTrue(any("c.bsky.social" in issue for issue in c.issues))

    def test_attribution_uses_immutable_first_touch_source(self):
        """Consulta E: ordenar las fuentes alfabeticamente destruia el orden real; un scan posterior no puede cambiar la fuente de un handle ya visto."""
        def build(order):
            c = self.collector()
            c.config["shortlist"].update({"profiles": 1, "acquisition_min": 1, "community_target": 0, "auto_like_score_min": 1.0})
            item = c._candidate("primerafuente.bsky.social")
            item["profile"] = {"handle": "primerafuente.bsky.social", "description": "Lectora de fantasía"}
            for source in order:
                item["sources"].add(source)
                gs._note_source(item, source)
            c.add_post(post("primerafuente.bsky.social", "p1", "Estoy leyendo una novela de fantasía muy buena."), order[0], key="q")
            likes = [a for a in gs._build_output(c)["auto_plan"] if a["kind"] == "like"]
            return likes[0]["motivo"]

        first = build(["pool", "post_search"])
        later = build(["jetstream_cache", "pool"])        # otro dia el handle llega antes por Jetstream: la primera vez fue el pool
        self.assertIn(":src=pool", first)
        self.assertIn(":src=pool", later)
        self.assertNotIn(":src=jetstream_cache", later)

    def _plan_for(self, handle, bio, texts, *, langs=None, like_min=1.0, follow_min=1.0):
        c = self.collector()
        c.config["shortlist"].update({"profiles": 1, "acquisition_min": 1, "community_target": 0, "auto_like_score_min": like_min, "auto_follow_score_min": follow_min})
        item = c._candidate(handle)
        item["sources"].add("post_search")
        item["profile"] = {"handle": handle, "description": bio}
        item["following"] = False
        for i, text in enumerate(texts):
            row = post(handle, f"p{i}", text)
            row["author"]["description"] = bio
            if langs is not None:
                row["record"]["langs"] = langs
            c.add_post(row, "post_search", key="q")
        return gs._build_output(c)["auto_plan"]

    def test_non_spanish_posts_and_accounts_get_no_like_or_follow(self):
        """05/10: el plan llevaba likes a posts en ingles/portugues/japones de cuentas con la bio 'afin'."""
        plan = self._plan_for("autor-ingles.bsky.social", "Fantasy writer and book reader", ["My new fantasy book is out today, thank you all for reading"], langs=["en"])
        self.assertEqual(plan, [])
        plan = self._plan_for("autor-ingles2.bsky.social", "Fantasy writer and book reader", ["My new fantasy book is out today, thank you all for reading"])      # sin etiqueta: heuristica
        self.assertEqual(plan, [])

    def test_spanish_niche_account_still_gets_like_and_follow(self):
        plan = self._plan_for("lectora-es.bsky.social", "Lectora de fantasía y novelas", ["Estoy leyendo una novela de fantasía que me está encantando mucho"], langs=["es"])
        self.assertEqual({a["kind"] for a in plan}, {"like", "follow"})

    def test_like_by_bio_alone_needs_two_niche_terms_and_no_activism(self):
        off_topic = ["Hoy hace un día precioso en la ciudad y me voy a pasear un rato por el parque"]
        weak_bio = self._plan_for("bio-debil.bsky.social", "Lectora", off_topic, langs=["es"])
        self.assertEqual([a for a in weak_bio if a["kind"] == "like"], [])
        strong_bio = self._plan_for("bio-fuerte.bsky.social", "Lectora de fantasía y novelas", off_topic, langs=["es"])
        self.assertEqual(len([a for a in strong_bio if a["kind"] == "like"]), 1)
        c = self.collector()
        c.config["shortlist"].update({"profiles": 1, "acquisition_min": 1, "community_target": 0, "auto_like_score_min": 1.0})
        item = c._candidate("comenta.bsky.social")
        item["sources"].add("post_search")
        item["profile"] = {"handle": "comenta.bsky.social", "description": "Lectora de fantasía y novelas"}
        row = post("comenta.bsky.social", "p1", "Qué bien, me alegro mucho de verlo por aquí hoy mismo")
        row["record"]["langs"] = ["es"]
        row["record"]["reply"] = {"parent": {"uri": "at://x/app.bsky.feed.post/1"}}
        c.add_post(row, "post_search", key="q")
        self.assertEqual([a for a in gs._build_output(c)["auto_plan"] if a["kind"] == "like"], [])      # comentario suelto: no
        activist = self._plan_for("bio-activista.bsky.social", "Lectora de fantasía y novelas", ["Hay que salir a la calle a luchar contra el fascismo y el genocidio ya mismo"], langs=["es"])
        self.assertEqual([a for a in activist if a["kind"] == "like"], [])

    def test_huge_accounts_get_likes_but_no_follow(self):
        c = self.collector()
        c.config["shortlist"].update({"profiles": 1, "acquisition_min": 1, "community_target": 0, "auto_like_score_min": 1.0, "auto_follow_score_min": 1.0})
        item = c._candidate("gigante.bsky.social")
        item["sources"].add("post_search")
        item["profile"] = {"handle": "gigante.bsky.social", "description": "Editorial de fantasía y novelas", "followersCount": 90000}
        item["following"] = False
        row = post("gigante.bsky.social", "p1", "Ya está en librerías la nueva novela de fantasía de nuestro catálogo")
        row["record"]["langs"] = ["es"]
        c.add_post(row, "post_search", key="q")
        kinds = {a["kind"] for a in gs._build_output(c)["auto_plan"]}
        self.assertEqual(kinds, {"like"})

    def test_auto_repost_is_capped_strict_and_coexists_with_the_like(self):
        c = self.collector()
        c.config["shortlist"].update({"profiles": 5, "acquisition_min": 5, "community_target": 0, "auto_like_score_min": 1.0, "auto_follow_score_min": 99.0, "auto_repost_per_round": 1})
        texts = {
            "fuerte1": "Reseña de una novela de fantasía juvenil: la saga de dragones y magia que estaba esperando leer este otoño",
            "fuerte2": "Terminé de leer esta novela de fantasía épica y la reseña la subo mañana, qué libro tan bueno",
            "inglés": "Reading a fantasy novel and writing a review of the book this week, what a saga",
            "debil": "Estoy leyendo un libro muy bueno que me han regalado hace poco",
            "promo": "Nueva novela de fantasía épica con saga de dragones, consíguela aquí en tienda.com con descuento",
        }
        for name, text in texts.items():
            item = c._candidate(f"{name}.bsky.social")
            item["sources"].add("post_search")
            item["profile"] = {"handle": f"{name}.bsky.social", "description": "Lectora de fantasía y novelas", "followersCount": 300}
            row = post(f"{name}.bsky.social", "p1", text)
            row["author"]["description"] = "Lectora de fantasía y novelas"
            row["record"]["langs"] = ["en"] if name == "inglés" else ["es"]
            c.add_post(row, "post_search", key="q")
        plan = gs._build_output(c)["auto_plan"]
        reposts = [a for a in plan if a["kind"] == "repost"]
        self.assertEqual(len(reposts), 1)                                   # tope por ronda
        self.assertTrue(reposts[0]["handle"].startswith("fuerte"))          # solo posts claramente del nicho, en espanol y sin publicidad/enlaces
        liked_same_post = [a for a in plan if a["kind"] == "like" and a["url"] == reposts[0]["url"]]
        self.assertEqual(liked_same_post, [])                               # un post, una interaccion: el ejecutor rechazaria TODO el lote con like + repost
        urls = [a["url"] for a in plan if "url" in a]
        self.assertEqual(len(urls), len(set(urls)))
        c.config["shortlist"]["auto_repost_per_round"] = 0
        self.assertEqual([a for a in gs._build_output(c)["auto_plan"] if a["kind"] == "repost"], [])


if __name__ == "__main__":
    unittest.main()
