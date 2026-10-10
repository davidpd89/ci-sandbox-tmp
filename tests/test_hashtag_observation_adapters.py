"""Synthetic, offline parity/identity/attribution tests for PR #99.

SPDX-License-Identifier: MIT
"""
import copy
from datetime import datetime, timedelta, timezone
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from hashtag_observation_adapters import (FIELDS, NETWORKS, QUEUES,
                                          ObservationCollector)

NOW = "2026-10-10T10:00:00+00:00"
STAMP = "2026-10-09T10:00:00+00:00"
EPOCH = 1791540000  # 2026-10-09T10:00:00Z


def sample(network, *, post="42", author="123"):
    common = {
        "x": {"id_str": post, "user": {"id_str": author},
              "full_text": "Reseña de romantasy #Fantasía", "created_at": STAMP},
        "threads": {"id": post, "user_id": author,
                    "text": "Leyendo #Niño #Año", "timestamp": STAMP},
        "facebook": {"id": post, "from": {"id": author},
                     "message": "Libro juvenil #lectura", "created_time": STAMP},
        "pinterest": {"id": post, "creator": {"id": author},
                      "description": "Lectura y #Romantasy",
                      "created_at": STAMP, "tags": [{"name": "Escritura"}]},
        "reddit": {"name": "t3_" + post, "author_fullname": "t2_" + author,
                   "title": "Reseña de libro", "selftext": "#Fantasía juvenil",
                   "created_utc": EPOCH},
        "bluesky": {"uri": "at://did:plc:fake/app.bsky.feed.post/" + post,
                    "author": {"did": "did:plc:" + author},
                    "record": {"text": "Romantasy #Año", "createdAt": STAMP,
                    "facets": [{"features": [{"$type": "app.bsky.richtext.facet#tag",
                                               "tag": "Niño"}]}]}},
        "mastodon": {"url": "https://example.social/@user/" + post,
                     "account": {"url": "https://example.social/@author" + author},
                     "content": "<p>Reseña <b>#Fantasía</b> y escritura</p>",
                     "created_at": STAMP, "tags": [{"name": "Lectura"}]},
        "tiktok": {"id": post, "author": {"uid": author}, "desc": "Libro #Romantasy",
                   "createTime": EPOCH,
                   "textExtra": [{"hashtagName": "Niño"}],
                   "challenges": [{"title": "Fantasía"}]},
        "instagram": {"id": post, "user": {"id": author},
                      "caption": {"text": "Bookstagram #Lectura"},
                      "timestamp": STAMP, "hashtags": ["Niño"]},
    }
    return copy.deepcopy(common[network])


class ObservationTests(unittest.TestCase):
    def test_all_nine_networks_and_three_queues(self):
        self.assertEqual(len(NETWORKS), 9)
        self.assertEqual(len(QUEUES), 3)
        bridge = ObservationCollector(now=NOW)
        for queue in sorted(QUEUES):
            for n in sorted(NETWORKS):
                bridge.add_posts(n, queue, "native-synthetic", [sample(n)])
        self.assertEqual(len(bridge.to_engine_rows()), 27)
        self.assertEqual(bridge.aggregate_report()["unique_posts"], 9)
        self.assertEqual(bridge.counts["duplicates"], 18)
        self.assertEqual(sum(r["input"] for r in bridge.aggregate_report()["coverage"]), 27)
        self.assertEqual(set(FIELDS), NETWORKS)

    def test_engine_schema_and_native_hashtags(self):
        bridge = ObservationCollector(now=NOW)
        for network in sorted(NETWORKS):
            bridge.add_posts(network, "API", "reader", [sample(network)])
        for item in bridge.to_engine_rows():
            self.assertEqual(set(item), {"network", "source", "post_id", "author_id",
                                         "created_at", "text", "tags"})
            self.assertEqual(item["source"], "API:reader")
            self.assertTrue(item["created_at"].endswith("+00:00"))
            self.assertIsInstance(item["tags"], list)
            json.dumps(item, ensure_ascii=False)
        by_n = {x["network"]: x for x in bridge.to_engine_rows()}
        self.assertEqual(by_n["reddit"]["tags"], [])  # not a native hashtag surface
        self.assertIn("niño", by_n["bluesky"]["tags"])
        self.assertIn("niño", by_n["tiktok"]["tags"])
        self.assertIn("lectura", by_n["mastodon"]["tags"])
        self.assertIn("#Fantasía", by_n["mastodon"]["text"])
        self.assertNotIn("<p>", by_n["mastodon"]["text"])

    def test_distinct_same_post_id_across_networks(self):
        b = ObservationCollector(now=NOW)
        for n in ("x", "threads", "facebook", "instagram"):
            b.add_posts(n, "WEB", "same-id", [sample(n)])
        self.assertEqual(len(b.to_engine_rows()), 4)
        self.assertEqual(b.counts["duplicates"], 0)

    def test_duplicate_conflicts_are_removed_independent_of_order(self):
        a, b = sample("x"), sample("x")
        b["full_text"] = "Un texto distinto #fantasía"
        for rows in ([a, b], [b, a]):
            c = ObservationCollector(now=NOW)
            c.add_posts("x", "WEB", "s1", rows)
            self.assertEqual(c.to_engine_rows(), [])
            c.add_posts("x", "API", "s2", [a])
            self.assertEqual(c.to_engine_rows(), [])
            self.assertGreater(c.counts["conflicts"], 0)

    def test_multiple_sources_keep_unique_post_and_provenance(self):
        c = ObservationCollector(now=NOW)
        for q in ("API", "WEB", "MOBILE"):
            c.add_posts("x", q, "scan", [sample("x")])
        self.assertEqual(sorted(r["source"] for r in c.to_engine_rows()),
                         ["API:scan", "MOBILE:scan", "WEB:scan"])
        self.assertEqual(c.aggregate_report()["unique_posts"], 1)

    def test_malformed_and_unknown_dates(self):
        for network in NETWORKS:
            c = ObservationCollector(now=NOW)
            item = sample(network)
            # A post with no authoritative author or publication date is discarded.
            for category in (1, 3):
                wrong = copy.deepcopy(item)
                if network == "reddit":
                    wrong["author_fullname" if category == 1 else "created_utc"] = None
                elif network == "bluesky":
                    if category == 1:
                        wrong["author"]["did"] = None
                    else:
                        wrong["record"]["createdAt"] = None
                elif network == "mastodon":
                    if category == 1:
                        wrong["account"]["url"] = None
                    else:
                        wrong["created_at"] = None
                elif network == "tiktok":
                    wrong["author"]["uid"] = None if category == 1 else "123"
                    if category == 3:
                        wrong["createTime"] = None
                elif network == "instagram":
                    if category == 1:
                        wrong["user"]["id"] = None
                    else:
                        wrong["timestamp"] = None
                elif network == "x":
                    if category == 1:
                        wrong["user"]["id_str"] = None
                    else:
                        wrong["created_at"] = None
                elif network == "threads":
                    wrong["user_id" if category == 1 else "timestamp"] = None
                elif network == "facebook":
                    if category == 1:
                        wrong["from"]["id"] = None
                    else:
                        wrong["created_time"] = None
                else:
                    if category == 1:
                        wrong["creator"]["id"] = None
                    else:
                        wrong["created_at"] = None
                c.add_posts(network, "WEB", "bad", [wrong])
            self.assertEqual(c.to_engine_rows(), [], network)
            self.assertEqual(c.counts["invalid"], 2)

    def test_naive_future_old_empty_and_backfill(self):
        c = ObservationCollector(now=NOW, max_age_days=14)
        original = sample("threads")
        old = sample("threads", post="old")
        old["timestamp"] = "2026-09-01T00:00:00+00:00"
        naive = sample("threads", post="naive")
        naive["timestamp"] = "2026-10-09T00:00:00"
        future = sample("threads", post="future")
        future["timestamp"] = "2026-10-11T00:00:00+00:00"
        c.add_posts("threads", "API", "dates", [original, old, naive, future])
        c.add_posts("threads", "WEB", "empty", [])
        self.assertEqual(c.aggregate_report()["unique_posts"], 1)
        self.assertEqual(c.counts["stale"], 1)
        self.assertEqual(c.counts["future"], 1)
        self.assertEqual(c.counts["invalid"], 1)
        with self.assertRaises(ValueError):
            ObservationCollector(now=NOW, max_age_days=15)
        with self.assertRaises(ValueError):
            ObservationCollector(now="2026-10-10T10:00:00")

    def test_unicode_nfc_and_no_search_term_attribution(self):
        c = ObservationCollector(now=NOW)
        row = sample("bluesky")
        row["record"]["facets"][0]["features"][0]["tag"] = "nin\u0303o"
        c.add_posts("bluesky", "API", "query:#Inventado", [row])
        only = c.to_engine_rows()[0]
        self.assertIn("niño", only["tags"])
        self.assertNotIn("inventado", only["tags"])
        self.assertNotIn("ano", only["tags"])
        self.assertIn("#Año", only["text"])

    def test_mastodon_remote_id_not_assumed_global(self):
        c = ObservationCollector(now=NOW)
        row = sample("mastodon")
        row.pop("url")
        row["post_id"] = "42"
        c.add_posts("mastodon", "API", "fediverse", [row])
        self.assertEqual(c.to_engine_rows(), [])
        self.assertEqual(c.counts["invalid"], 1)

    def test_mastodon_urls_require_server_and_resource_path(self):
        # Without both authority and resource path these cannot disambiguate
        # identities across Mastodon instances, even if prefixed with https.
        bad_urls = ("https://", "https:///missing-host",
                    "https://example.social", "https://example.social/",
                    "ftp://example.social/@user/42",
                    "https://other@example.social/@user/42",
                    "https://[bad-ipv6/@user/42")
        for bad in bad_urls:
            for field in ("post", "author"):
                with self.subTest(url=bad, field=field):
                    row = sample("mastodon")
                    if field == "post":
                        row["url"] = bad
                    else:
                        row["account"]["url"] = bad
                    collector = ObservationCollector(now=NOW)
                    collector.add_posts("mastodon", "API", "identity", [row])
                    self.assertEqual(collector.to_engine_rows(), [])
                    self.assertEqual(collector.counts["invalid"], 1)
        collector = ObservationCollector(now=NOW)
        collector.add_posts("mastodon", "API", "identity", [sample("mastodon")])
        self.assertEqual(collector.aggregate_report()["unique_posts"], 1)

    def test_feedback_exactly_once_and_aggregate_without_raw_identifiers(self):
        c = ObservationCollector(now=NOW)
        row = {"event_id": "opaque-1", "window": STAMP, "tag": "#Año",
               "eligible": 10, "engaged": 3, "replies": 2, "followers": 1}
        c.add_feedback("bluesky", "API", "first", [row])
        c.add_feedback("bluesky", "WEB", "second", [row])
        c.add_feedback("threads", "API", "other", [row])
        a = c.feedback_aggregates()
        self.assertEqual(len(a), 2)
        self.assertTrue(all(r["eligible"] == 10 for r in a))
        self.assertNotIn("opaque-1", json.dumps(a, ensure_ascii=False))
        self.assertNotIn("opaque-1", json.dumps(c.aggregate_report()))
        self.assertEqual(c.counts["feedback_duplicates"], 1)

    def test_feedback_conflicts_without_denominator_or_window(self):
        c = ObservationCollector(now=NOW)
        ok = {"event_id": "c1", "window": STAMP, "tag": "Fantasía",
              "eligible": 8, "engaged": 2, "replies": 1, "followers": 0}
        conflict = dict(ok, engaged=3)
        c.add_feedback("instagram", "API", "A", [ok, conflict])
        c.add_feedback("instagram", "WEB", "B", [ok])
        c.add_feedback("instagram", "API", "B", [dict(ok, event_id="c2", eligible=None)])
        c.add_feedback("instagram", "API", "C", [dict(ok, event_id="c3", window="2026-10-09")])
        c.add_feedback("instagram", "API", "D", [dict(ok, event_id="c4", engaged=99)])
        self.assertEqual(c.feedback_aggregates(), [])
        self.assertEqual(c.counts["feedback_invalid"], 3)
        self.assertEqual(c.counts["feedback_conflicts"], 2)

    def test_html_inline_fragments_do_not_break_language_or_seeds(self):
        row = sample("mastodon")
        row["content"] = "<p>La <b>fantas</b>ía <i>juvenil</i><br>y lectura</p>"
        c = ObservationCollector(now=NOW)
        c.add_posts("mastodon", "API", "html", [row])
        self.assertEqual(c.to_engine_rows()[0]["text"],
                         "La fantasía juvenil y lectura")

    def test_global_capacity_retains_existing_idempotent_sources(self):
        c = ObservationCollector(now=NOW, max_unique_posts=1)
        c.add_posts("x", "WEB", "reader1", [sample("x", post="x1")])
        c.add_posts("x", "API", "reader2", [sample("x", post="x2")])
        c.add_posts("x", "MOBILE", "reader3", [sample("x", post="x1")])
        self.assertEqual(c.aggregate_report()["unique_posts"], 1)
        self.assertEqual(c.counts["capacity_skipped"], 1)
        self.assertEqual(c.counts["duplicates"], 1)
        self.assertEqual(len(c.to_engine_rows()), 2)
        with self.assertRaises(ValueError):
            ObservationCollector(now=NOW, max_unique_posts=0)

    def test_no_network_io_and_read_only_input(self):
        c = ObservationCollector(now=NOW)
        original = sample("instagram")
        before = copy.deepcopy(original)
        c.add_posts("instagram", "MOBILE", "snapshot", [original])
        self.assertEqual(original, before)
        self.assertFalse(any(x in vars(c) for x in ("session", "client", "browser")))
        self.assertEqual(len(c.to_engine_rows()), 1)
        bad = [{"caption": "sin fecha y sin autor", "id": "1"}]
        c.add_posts("instagram", "MOBILE", "profile", bad)
        self.assertEqual(c.counts["invalid"], 1)

    def test_adversarial_reddit_author_and_malformed_facets(self):
        reddit = sample("reddit")
        reddit.pop("author_fullname")
        reddit["author"] = "lectora_sintetica"
        bluesky = sample("bluesky")
        bluesky["record"]["facets"][0]["features"] = {"bad": "shape"}
        c = ObservationCollector(now=NOW)
        c.add_posts("reddit", "API", "praw", [reddit])
        c.add_posts("bluesky", "API", "atproto", [bluesky])
        self.assertEqual(len(c.to_engine_rows()), 2)
        self.assertEqual(c.counts["invalid"], 0)
        self.assertEqual(next(r for r in c.to_engine_rows()
                              if r["network"] == "reddit")["author_id"],
                         "lectora_sintetica")

    def test_zero_denominator_cannot_claim_a_reply(self):
        c = ObservationCollector(now=NOW)
        c.add_feedback("x", "WEB", "reader", [
            {"event_id": "fake", "window": STAMP, "tag": "lectura",
             "eligible": 0, "engaged": 0, "replies": 1, "followers": 0}])
        self.assertEqual(c.feedback_aggregates(), [])
        self.assertEqual(c.counts["feedback_invalid"], 1)

    def test_engine_identity_length_boundary(self):
        # #63 validates both identity fields to <=256 characters.
        bridge = ObservationCollector(now=NOW)
        bridge.add_posts("x", "API", "ids", [
            sample("x", post="p" * 256, author="a" * 256),
            sample("x", post="p" * 257, author="short"),
            sample("x", post="short", author="a" * 257),
        ])
        rows = bridge.to_engine_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["post_id"]), 256)
        self.assertEqual(len(rows[0]["author_id"]), 256)
        self.assertEqual(bridge.counts["invalid"], 2)

    def test_engine_rows_do_not_expose_mutable_collector_tags(self):
        bridge = ObservationCollector(now=NOW)
        sample_post = sample("bluesky")
        bridge.add_posts("bluesky", "API", "a", [sample_post])
        bridge.add_posts("bluesky", "WEB", "b", [sample_post])
        rows = bridge.to_engine_rows()
        self.assertEqual(len(rows), 2)
        original = list(rows[0]["tags"])
        rows[0]["tags"].append("inyectado")
        self.assertEqual(rows[1]["tags"], original)
        self.assertEqual(bridge.to_engine_rows()[0]["tags"], original)



    def test_full_network_queue_parity_with_real_engine(self):
        from hashtag_expansion import build_snapshot

        # Two distinct authors per platform, all three read-only queues.
        # This validates downstream shape, not availability of live producers.
        text_paths = {
            "x": ("full_text",), "threads": ("text",),
            "facebook": ("message",), "pinterest": ("description",),
            "reddit": ("title",), "bluesky": ("record", "text"),
            "mastodon": ("content",), "tiktok": ("desc",),
            "instagram": ("caption", "text"),
        }
        collector = ObservationCollector(now=NOW)
        for network in sorted(NETWORKS):
            batch = []
            for n in (1, 2):
                row = sample(network, post=f"post-{n}", author=f"author-{n}")
                container = row
                for key in text_paths[network][:-1]:
                    container = container[key]
                last = text_paths[network][-1]
                container[last] += " romantasy #Juvenil"
                batch.append(row)
            for queue in sorted(QUEUES):
                collector.add_posts(network, queue, "reader", batch)
        self.assertEqual(collector.aggregate_report()["unique_posts"], 18)
        snapshot = build_snapshot(collector.to_engine_rows(),
                                  now=NOW, seeds={"fantasia": ["romantasy"]})
        self.assertEqual(snapshot["diagnostics"]["unique"], 18)
        self.assertEqual(snapshot["diagnostics"]["invalid"], 0)
        for network in NETWORKS:
            result = snapshot["networks"][network]
            self.assertIn("juvenil", result["busquedas"], network)
            chosen = next(x for x in result["candidates"]
                          if x["tag"] == "juvenil")
            self.assertEqual(chosen["authors"], 2, network)
            self.assertEqual(chosen["sources"],
                             ["API:reader", "MOBILE:reader", "WEB:reader"], network)
            if network == "reddit":
                self.assertEqual(result["hashtags"], [])
            else:
                self.assertIn("juvenil", result["hashtags"], network)

    def test_end_to_end_with_current_hashtag_expansion_engine(self):
        # Genuine producer -> adapter -> current #63 engine composition,
        # not a mocked engine signature or an assumption about live feeds.
        from hashtag_expansion import build_snapshot

        collector = ObservationCollector(now=NOW)
        post_a = sample("bluesky", post="post-a", author="author-a")
        post_b = sample("bluesky", post="post-b", author="author-b")
        collector.add_posts("bluesky", "API", "feed", [post_a, post_b])
        collector.add_posts("bluesky", "WEB", "feed", [post_a])
        collector.add_posts("bluesky", "MOBILE", "missing-author",
                            [{"uri": "at://did:plc:fake/app.bsky.feed.post/unknown",
                              "record": {"text": "romantasy #Año", "createdAt": STAMP}}])
        collector.add_feedback("bluesky", "API", "measured", [
            {"event_id": "qualified-event", "window": STAMP, "tag": "#Año",
             "eligible": 10, "engaged": 3, "replies": 1, "followers": 0}])
        snapshot = build_snapshot(collector.to_engine_rows(),
                                  feedback=collector.feedback_aggregates(),
                                  now=NOW, seeds={"fantasia": ["romantasy"]})
        self.assertEqual(snapshot["diagnostics"]["invalid"], 0)
        self.assertEqual(snapshot["diagnostics"]["unique"], 2)
        self.assertEqual(collector.counts["invalid"], 1)
        candidates = snapshot["networks"]["bluesky"]["candidates"]
        year = next(row for row in candidates if row["tag"] == "año")
        self.assertEqual(year["authors"], 2)
        self.assertEqual(year["feedback_eligible"], 10)
        self.assertEqual(year["sources"], ["API:feed", "WEB:feed"])
        self.assertIn("año", snapshot["networks"]["bluesky"]["hashtags"])
        self.assertEqual(snapshot["networks"]["reddit"]["hashtags"], [])

    def test_epoch_seconds_as_strict_decimal_strings_across_networks(self):
        # Common native JSON variation: Unix seconds serialized as a string.
        # Reject ambiguous 8-digit dates and milliseconds, not impute dates.
        from hashtag_expansion import build_snapshot
        for network, field in (("reddit", "created_utc"),
                               ("tiktok", "createTime"),
                               ("instagram", "timestamp")):
            bridge = ObservationCollector(now=NOW)
            for index in (1, 2):
                item = sample(network, post=f"epoch-{index}",
                              author=f"author-{index}")
                item[field] = str(EPOCH)
                bridge.add_posts(network, "API", "native", [item])
            self.assertEqual(bridge.aggregate_report()["unique_posts"], 2, network)
            snapshot = build_snapshot(bridge.to_engine_rows(), now=NOW)
            self.assertEqual(snapshot["diagnostics"]["invalid"], 0, network)
            self.assertEqual(snapshot["diagnostics"]["unique"], 2, network)

            ambiguous = sample(network, post="ambiguous")
            ambiguous[field] = "20261009"
            milliseconds = sample(network, post="milliseconds")
            milliseconds[field] = str(EPOCH * 1000)
            bridge.add_posts(network, "API", "native", [ambiguous, milliseconds])
            self.assertEqual(bridge.counts["invalid"], 2, network)
            self.assertEqual(bridge.aggregate_report()["unique_posts"], 2, network)

    def test_control_characters_cannot_alias_stable_ids_or_provenance(self):
        # Identity and source names are reused in logs/ranking; reject
        # embedded control characters rather than silently treating them as IDs.
        for network in sorted(NETWORKS):
            bridge = ObservationCollector(now=NOW)
            invalid = sample(network, post="valid", author="author")
            if network == "reddit":
                invalid["author_fullname"] = "t2_au\nthor"
            elif network == "bluesky":
                invalid["author"]["did"] = "did:plc:au\nthor"
            elif network == "mastodon":
                invalid["account"]["url"] = "https://example.social/@au\nthor"
            elif network == "x":
                invalid["user"]["id_str"] = "au\nthor"
            elif network == "threads":
                invalid["user_id"] = "au\nthor"
            elif network == "facebook":
                invalid["from"]["id"] = "au\nthor"
            elif network == "pinterest":
                invalid["creator"]["id"] = "au\nthor"
            elif network == "tiktok":
                invalid["author"]["uid"] = "au\nthor"
            elif network == "instagram":
                invalid["user"]["id"] = "au\nthor"
            bridge.add_posts(network, "API", "read-only", [invalid])
            self.assertEqual(bridge.to_engine_rows(), [], network)
            self.assertEqual(bridge.counts["invalid"], 1, network)
        bridge = ObservationCollector(now=NOW)
        for source in ("channel\nspoof", "channel\x00spoof", "\rreader"):
            with self.assertRaises(ValueError):
                bridge.add_posts("x", "WEB", source, [sample("x")])
            with self.assertRaises(ValueError):
                bridge.add_feedback("x", "WEB", source, [])

    def test_strict_bad_scope_bounds_and_rollback(self):
        c = ObservationCollector(now=NOW)
        for args in (("fake", "WEB", "test", []),
                     ("x", "UNKNOWN", "test", []),
                     ("x", "API", "", []),
                     ("x", "API", "test", {}),
                     ("x", "API", "test", [{}] * 10001)):
            with self.assertRaises(ValueError):
                c.add_posts(*args)
        with self.assertRaises(ValueError):
            c.add_feedback("x", "API", "f", [{}] * 10001)
        self.assertEqual(c.aggregate_report()["unique_posts"], 0)
        self.assertEqual(c.feedback_aggregates(), [])
        # rollback: discard object; no external storage has ever been changed.


if __name__ == "__main__":
    unittest.main()
