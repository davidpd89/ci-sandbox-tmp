"""Offline synthetic contracts for the read-only candidate ranker (Python 3.11)."""
import datetime as dt
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import target_quality_ranking as r

NOW = dt.datetime(2026, 10, 10, 8, tzinfo=dt.timezone.utc)


def account(network="bluesky", key="reader.example", *, hits=True, **changes):
    value = {
        "handle": key,
        "bio": "Leo fantasía juvenil, romantasy y libros" if hits else "Fotografía",
        "followers": 350, "sources": ["search", "mentions"],
        "actions": ["follow"], "lane": "acquisition",
        "posts": [],
    }
    if network == "mastodon":
        value["acct"] = key
    value.update(changes)
    return value


def post(key="https://example.org/p/1", **changes):
    result = {"url": key, "text": "Novela de fantasía juvenil",
              "created_at": "2026-10-09T08:00:00Z", "language": "es",
              "stats": {"replies": 3}, "actions": ["comment", "reply"]}
    result.update(changes)
    return result


def rank(network, rows, **kwargs):
    return r.rank_network(network, rows, as_of=NOW, **kwargs)


class RankingTests(unittest.TestCase):
    def test_supports_all_nine_with_explicit_missing_adapters(self):
        result = r.rank_all({"bluesky": [account()]}, as_of=NOW)
        self.assertEqual(set(result["networks"]), set(r.NETWORKS))
        self.assertEqual(result["networks"]["instagram"]["status"], "missing_input")
        self.assertEqual(result["networks"]["reddit"]["ranked"], [])

    def test_topical_account_beats_irrelevant_account_independent_of_input_order(self):
        high, low = account(key="books.example"), account(key="photos.example", hits=False)
        a = rank("bluesky", [low, high])["ranked"]
        b = rank("bluesky", [high, low])["ranked"]
        self.assertEqual([x["id"] for x in a], [x["id"] for x in b])
        self.assertEqual(a[0]["id"], "bluesky:books.example")
        self.assertGreater(a[0]["explanation"]["topic"]["points"], a[1]["explanation"]["topic"]["points"])

    def test_explanations_sum_to_score(self):
        item = rank("bluesky", [account()])["ranked"][0]
        self.assertAlmostEqual(sum(x["points"] for x in item["explanation"].values()), item["score"])
        self.assertLessEqual(item["coverage"], 1)
        self.assertIsNone(item["explanation"]["activity"]["value"])

    def test_invalid_identity_and_duplicates_are_rejected(self):
        res = rank("bluesky", [None, {"bio": "fantasía"}, account(), account()])
        self.assertEqual(res["ranked"], [])
        self.assertEqual({x["reason"] for x in res["rejected"]},
                         {"invalid_row", "missing_identity", "duplicate_identity"})

    def test_posts_are_ranked_by_topic_and_recency(self):
        recent = post("https://example.org/p/recent")
        old = post("https://example.org/p/old", created_at="2026-09-25T08:00:00Z",
                   text="No hablo de libros")
        entry = rank("bluesky", [account(posts=[old, recent])])["ranked"][0]
        self.assertEqual(entry["posts"][0]["id"], "bluesky:https://example.org/p/recent")
        self.assertEqual(len(entry["posts"]), 2)

    def test_necropost_excluded_even_if_native_actions_allow(self):
        row = account(posts=[post(created_at="2026-07-01T00:00:00Z")])
        got = rank("bluesky", [row])["ranked"][0]
        self.assertEqual(got["posts"], [])
        self.assertEqual(got["post_rejections"][0]["reason"], "post_outside_age_window")
        self.assertEqual([x["action"] for x in got["opportunities"]], ["follow"])

    def test_community_uses_its_own_age_limit(self):
        p = post(created_at="2026-09-11T08:00:00Z")
        self.assertEqual(len(rank("bluesky", [account(lane="community", posts=[p])])["ranked"][0]["posts"]), 1)
        self.assertEqual(len(rank("bluesky", [account(posts=[p])])["ranked"][0]["posts"]), 0)

    def test_future_and_naive_posts_are_not_ranked(self):
        rows = [post("https://x/p/future", created_at="2026-10-11T00:00:00+00:00"),
                post("https://x/p/naive", created_at="2026-10-09T08:00:00")]
        got = rank("bluesky", [account(posts=rows)])["ranked"][0]
        self.assertEqual(got["posts"], [])
        self.assertEqual({x["reason"] for x in got["post_rejections"]},
                         {"post_outside_age_window", "missing_post_timestamp"})

    def test_rejected_posts_do_not_inflate_account_topic(self):
        baseline = rank("bluesky", [account(hits=False)])["ranked"][0]
        for altered in (
            post(created_at="2026-01-01T00:00:00Z", text="fantasía romantasy libros"),
            post(created_at="2099-01-01T00:00:00Z", text="fantasía romantasy libros"),
            post(created_at="2026-10-09T08:00:00", text="fantasía romantasy libros"),
            post(language="en", text="fantasía romantasy libros"),
            {"text": "fantasía romantasy libros", "language": "es",
             "created_at": "2026-10-09T08:00:00Z"},
        ):
            with self.subTest(altered=altered):
                result = rank("bluesky", [account(hits=False, posts=[altered])])["ranked"][0]
                self.assertEqual(result["explanation"]["topic"], baseline["explanation"]["topic"])
                self.assertEqual(result["opportunities"], baseline["opportunities"])

    def test_unknown_language_cannot_increase_account_affinity_or_generate_post_action(self):
        row = account(hits=False, posts=[post(language=None, text="fantasía romantasy libros")])
        result = rank("bluesky", [row])["ranked"][0]
        self.assertEqual(result["explanation"]["topic"]["value"], 0.)
        self.assertEqual(result["posts"][0]["actions"], [])
        self.assertEqual([a["action"] for a in result["opportunities"]], ["follow"])

    def test_valid_spanish_post_adds_account_topic_evidence(self):
        result = rank("bluesky", [
            account(hits=False, posts=[post(text="fantasía romantasy libros")])
        ])["ranked"][0]
        self.assertGreater(result["explanation"]["topic"]["value"], 0.)
        self.assertIn("comment", [a["action"] for a in result["opportunities"]])

    def test_spanish_explicit_false_excludes_foreign_posts(self):
        row = account(posts=[post(language="en")])
        got = rank("bluesky", [row])["ranked"][0]
        self.assertEqual(got["posts"], [])
        self.assertEqual(got["post_rejections"][0]["reason"], "non_spanish_post")

    def test_unknown_language_never_claimed_spanish(self):
        row = account(posts=[post(language=None)])
        found = rank("bluesky", [row])["ranked"][0]["posts"][0]
        self.assertIsNone(found["explanation"]["spanish"]["value"])
        self.assertEqual(found["actions"], [])  # Unknown language is informational only.
        self.assertFalse(any(a.get("post_id") == found["id"] for a in
                             rank("bluesky", [row])["ranked"][0]["opportunities"]))

    def test_only_existing_actions_surface_no_auto_x_like(self):
        candidate = account("x", posts=[post(actions=["like", "reply", "repost"])],
                            actions=["follow", "like"])
        got = rank("x", [candidate])["ranked"][0]
        self.assertEqual({x["action"] for x in got["opportunities"]},
                         {"follow", "reply", "repost"})
        self.assertNotIn("like", repr(got["opportunities"]))

    def test_verified_mature_outcomes_raise_rank_without_claiming_conversion(self):
        good = account(key="a", hits=False)
        other = account(key="b", hits=False)
        base = rank("bluesky", [good, other])["ranked"]
        observed = {"bluesky:a": {
            "verified": True, "mature": True,
            "shared_exposure_verified": True, "trials": 100,
            "followbacks": 60, "responses": 40,
            "conversations": 20, "traffic": 15}}
        after = rank("bluesky", [good, other], outcomes=observed)["ranked"]
        self.assertLess(base[0]["score"], after[0]["score"])
        self.assertEqual(after[0]["id"], "bluesky:a")
        self.assertGreater(after[0]["explanation"]["outcomes"]["value"], 0)

    def test_tiny_or_unverified_observations_not_misrepresented(self):
        partial = {"bluesky:reader.example": {
            "verified": False, "mature": True, "trials": 100,
            "followbacks": 90, "responses": 80,
            "conversations": 40, "traffic": 20}}
        item = rank("bluesky", [account()], outcomes=partial)["ranked"][0]
        self.assertIsNone(item["explanation"]["outcomes"]["value"])
        partial["bluesky:reader.example"]["verified"] = True
        partial["bluesky:reader.example"]["trials"] = 2
        item = rank("bluesky", [account()], outcomes=partial)["ranked"][0]
        self.assertIsNone(item["explanation"]["outcomes"]["value"])

    def test_iso_spanish_language_not_prefix_match(self):
        for lang in ("est", "esoteric", "english", "esp"):
            with self.subTest(lang=lang):
                row = account(language=lang, posts=[post(language=lang)])
                ranked = rank("bluesky", [row])["ranked"][0]
                self.assertEqual(ranked["explanation"]["spanish"]["value"], 0.)
                self.assertEqual(ranked["posts"], [])
                self.assertEqual(ranked["post_rejections"][0]["reason"], "non_spanish_post")
        for lang in ("es", "ES-MX", "es_419", " es-ES "):
            with self.subTest(lang=lang):
                row = account(language=lang, posts=[post(language=lang)])
                ranked = rank("bluesky", [row])["ranked"][0]
                self.assertEqual(ranked["explanation"]["spanish"]["value"], 1.)
                self.assertEqual(len(ranked["posts"]), 1)
        self.assertEqual(r._language({"langs": ["en", "est"]}), 0.)
        self.assertEqual(r._language({"langs": ["en", "es-AR"]}), 1.)

    def test_shared_exposure_needs_explicit_verification(self):
        data = {"verified": True, "mature": True, "trials": 100,
                "followbacks": 80, "responses": 50,
                "conversations": 30, "traffic": 20}
        self.assertIsNone(r._outcome_signal(data))
        data["shared_exposure_verified"] = False
        self.assertIsNone(r._outcome_signal(data))
        data["shared_exposure_verified"] = True
        self.assertGreater(r._outcome_signal(data), 0.)

    def test_by_metric_denominators_and_censoring_are_independent(self):
        entries = dict(zip(("followbacks", "responses", "conversations", "traffic"),
                           ((60, 100), (6, 10), (5, 20), (12, 50))))
        data = {"verified": True, "mature": True,
                "by_metric": {name: {"successes": success, "trials": trials,
                                     "verified": True, "mature": True}
                              for name, (success, trials) in entries.items()}}
        self.assertGreater(r._outcome_signal(data), 0.)
        legacy = {"verified": True, "mature": True, "trials": 100,
                  "shared_exposure_verified": True,
                  "followbacks": 60, "responses": 6,
                  "conversations": 5, "traffic": 12}
        self.assertNotAlmostEqual(r._outcome_signal(data), r._outcome_signal(legacy))
        data["by_metric"]["responses"]["mature"] = False
        self.assertIsNone(r._outcome_signal(data))
        data["by_metric"]["responses"]["mature"] = True
        data["by_metric"]["conversations"]["trials"] = 2
        self.assertIsNone(r._outcome_signal(data))

    def test_native_bluesky_profile_and_post(self):
        row = {"did": "did:plc:synthetic", "handle": "fiction.test",
               "profile": {"bio": "Libros de fantasía", "followers": 150},
               "sources": ["feed", "search"], "actions": ["follow"],
               "posts": [{"uri": "at://did:plc:synthetic/app.bsky.feed.post/123",
                          "created_at": "2026-10-09T12:00:00Z", "es": True,
                          "text": "Recomiendo fantasía", "actions": ["reply"]}]}
        got = rank("bluesky", [row])["ranked"][0]
        self.assertEqual(got["id"], "bluesky:did:plc:synthetic")
        self.assertEqual(got["posts"][0]["explanation"]["spanish"]["value"], 1.)

    def test_native_mastodon_profile(self):
        value = account("mastodon", "reader@example.org", last_status_at="2026-10-09T00:00:00Z",
                        followers=900, posts=[post()], followed_by=True, instance="social.test")
        got = rank("mastodon", [value])["ranked"][0]
        self.assertEqual(got["id"], "mastodon:social.test/reader@example.org")
        self.assertGreater(got["explanation"]["reciprocity"]["points"], 0)

    def test_native_tiktok_missing_age_is_transparent(self):
        value = account("tiktok", "fantasyreader", independent=4,
                        posts=[{"url": "https://example.test/video", "caption": "fantasía",
                                "actions": ["comment"]}])
        got = rank("tiktok", [value])["ranked"][0]
        self.assertEqual(got["explanation"]["sources"]["value"], 1.)
        self.assertEqual(got["posts"], [])
        self.assertEqual(got["post_rejections"][0]["reason"], "missing_post_timestamp")

    def test_generic_input_adapters_all_platforms(self):
        for net in r.NETWORKS:
            with self.subTest(network=net):
                got = rank(net, [account(net)])["ranked"]
                self.assertEqual(len(got), 1)
                self.assertTrue(got[0]["id"].startswith(net + ":"))

    def test_pinterest_native_authors_without_auto_posts(self):
        payload = {"authors": [{"handle": "lecturas", "bio": "fantasía",
                                 "followers": 200, "score": 10,
                                 "actions": ["follow"]}]}
        result = r.rank_all({"pinterest": payload}, as_of=NOW)
        self.assertEqual(len(result["networks"]["pinterest"]["ranked"]), 1)
        self.assertEqual(result["networks"]["pinterest"]["adapter"], "normalized_input_only")

    def test_deduplicate_posts_and_reject_missing_stable_key(self):
        p = post()
        got = rank("bluesky", [account(posts=[p, p, {"id": "G100-P1",
                             "created_at": "2026-10-09T08:00:00Z"}])])["ranked"][0]
        self.assertEqual(len(got["posts"]), 1)
        self.assertEqual(len(got["post_rejections"]), 2)

    def test_cross_network_same_handle_never_pools(self):
        got = r.rank_all({"bluesky": [account()], "threads": [account("threads")]}, as_of=NOW)
        self.assertNotEqual(got["networks"]["bluesky"]["ranked"][0]["id"],
                            got["networks"]["threads"]["ranked"][0]["id"])

    def test_deterministic_on_input_shuffle_and_ties(self):
        a, b, c = [account(key=k) for k in ("a", "b", "c")]
        ids1 = [x["id"] for x in rank("bluesky", [a, b, c])["ranked"]]
        ids2 = [x["id"] for x in rank("bluesky", [c, a, b])["ranked"]]
        self.assertEqual(ids1, ids2)

    def test_numeric_nan_infinity_bool_not_used_as_evidence(self):
        value = account(followers=float("nan"), independent=True, followed_by="True")
        result = rank("bluesky", [value])["ranked"][0]
        self.assertIsNone(result["explanation"]["audience"]["value"])
        self.assertIsNone(result["explanation"]["reciprocity"]["value"])

    def test_explicit_invalid_args_raise(self):
        for options in ({"max_post_age_days": -1},
                        {"max_post_age_days": True}, {"community_post_age_days": 500}):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    rank("bluesky", [], **options)
        with self.assertRaises(ValueError):
            r.rank_network("unknown", [], as_of=NOW)
        with self.assertRaises(ValueError):
            r.rank_network("bluesky", [], as_of=dt.datetime(2026, 10, 10))
        with self.assertRaises(ValueError):
            rank("bluesky", [account()] * 10001)
        with self.assertRaises(ValueError):
            r.rank_all({"unknown": []}, as_of=NOW)

    def test_evaluation_compares_four_metrics_without_imputing_missing(self):
        heldout = {
            "a": {"followback": True, "response": True, "conversation": True, "traffic": True},
            "b": {"followback": False, "response": False, "conversation": False, "traffic": False},
            "c": {"followback": True},
        }
        report = r.evaluate_orders(["a", "b", "c"], ["b", "a", "c"], heldout, k=2)
        self.assertEqual(len(report), 4)
        self.assertGreater(report["response"]["candidate"]["ndcg"],
                           report["response"]["baseline"]["ndcg"])
        self.assertEqual(report["traffic"]["candidate"]["observed"], 2)
        self.assertEqual(report["followback"]["candidate"]["precision"], .5)

    def test_evaluation_unknown_labels_excluded(self):
        result = r.evaluate_orders(["unknown", "known"], [], {"known": {"traffic": 1}}, k=10)
        self.assertEqual(result["traffic"]["candidate"]["observed"], 1)
        self.assertEqual(result["traffic"]["candidate"]["unjudged"], 1)
        self.assertIsNone(result["traffic"]["candidate"]["precision"])
        self.assertIsNone(result["traffic"]["candidate"]["ndcg"])
        self.assertIsNone(result["traffic"]["baseline"]["precision"])

    def test_evaluation_topk_does_not_replace_unjudged_slots_with_later_labels(self):
        labels = {
            "good": {"response": 1}, "bad": {"response": 0},
            "later": {"response": 1},
        }
        got = r.evaluate_orders(["unknown", "bad", "good", "later"],
                                ["good", "bad"], labels, k=2)["response"]
        self.assertEqual(got["candidate"]["exposed"], 2)
        self.assertEqual(got["candidate"]["observed"], 1)
        self.assertIsNone(got["candidate"]["precision"])
        self.assertIsNone(got["candidate"]["ndcg"])
        self.assertEqual(got["baseline"]["precision"], .5)

    def test_evaluation_ideal_ndcg_includes_relevant_beyond_topk(self):
        labels = {key: {"followback": value} for key, value in
                  (("one", 1), ("zero", 0), ("two", 1), ("three", 1))}
        result = r.evaluate_orders(["zero", "one", "two", "three"],
                                   ["one", "two", "zero", "three"],
                                   labels, k=2)["followback"]
        self.assertLess(result["candidate"]["ndcg"], 0.4)
        self.assertEqual(result["baseline"]["ndcg"], 1.)

    def test_post_age_timezone_offsets_equivalent(self):
        p1 = post(created_at="2026-10-10T09:00:00+02:00")
        result = rank("bluesky", [account(posts=[p1])])["ranked"][0]
        self.assertEqual(len(result["posts"]), 1)


    def test_synthetic_replay_quality_vs_native_proxy(self):
        from target_quality_benchmark import replay
        data = replay()
        self.assertEqual(data["top_k"], 4)
        self.assertNotEqual(data["candidate_order"], data["legacy_order"])
        for metric in ("followback", "response", "conversation", "traffic"):
            self.assertEqual(data["metrics"][metric]["candidate"]["precision"], 1.)
            self.assertEqual(data["metrics"][metric]["baseline"]["precision"], 0.)
            self.assertEqual(data["metrics"][metric]["candidate"]["ndcg"], 1.)
            self.assertEqual(data["metrics"][metric]["baseline"]["ndcg"], 0.)

    def test_incomplete_outcomes_and_missing_posts_never_become_success(self):
        outcomes = {"bluesky:reader.example": {"verified": True, "mature": False,
                    "trials": 100, "followbacks": 80, "responses": 80,
                    "conversations": 80, "traffic": 80}}
        got = rank("bluesky", [account(posts=[{"text": "fantasía", "es": True}])],
                   outcomes=outcomes)["ranked"][0]
        self.assertIsNone(got["explanation"]["outcomes"]["value"])
        self.assertEqual(got["posts"], [])
        self.assertEqual(got["post_rejections"][0]["reason"], "missing_or_duplicate_post_key")


    def test_already_followed_never_proposes_duplicate_follow(self):
        for net in ("bluesky", "tiktok", "x"):
            row = account(net, following=True, followed=True, actions=["follow"])
            got = rank(net, [row])["ranked"][0]
            self.assertFalse(any(x["action"] == "follow" for x in got["opportunities"]))

    def test_future_profile_date_cannot_hide_recent_post_activity(self):
        row = account(last_status_at="2099-01-01T00:00:00Z",
                      posts=[post()])
        got = rank("bluesky", [row])["ranked"][0]
        self.assertGreater(got["explanation"]["activity"]["value"], 0)


if __name__ == "__main__":
    unittest.main()
