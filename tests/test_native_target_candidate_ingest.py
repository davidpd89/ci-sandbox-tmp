"""Synthetic only. Contract and adversarial regression suite for six adapters."""
import copy
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import native_target_candidate_ingest as n

NOW = dt.datetime(2026, 10, 10, 12, tzinfo=dt.timezone.utc)
FRESH = "2026-10-09T12:00:00+00:00"
OLD = "2026-07-01T10:00:00Z"
SAMPLES = {
    "x": {"source": "busqueda", "handle": "lectora_1",
          "url": "https://x.com/lectora_1/status/12345",
          "text": "Fantasía juvenil", "kind": "reply"},
    "threads": {"source": "feed", "handle": "lectora.1",
                "permalink": "https://www.threads.net/@lectora.1/post/ABC123",
                "text": "Fantasía juvenil", "kind": "reply"},
    "facebook": {"tag": "busqueda:libros", "autor": "Lectora Uno",
                 "permalink": "https://www.facebook.com/page/posts/12345",
                 "text": "Libros", "known": False},
    "reddit": {"subreddit": "r/libros", "author": "lectora_1",
               "title": "¿Qué fantasía leemos?",
               "url": "https://www.reddit.com/r/libros/comments/abcd12/que_leemos/",
               "comment_count": 10, "score": 25},
    "pinterest": {"handle": "lectora_1", "bio": "Leo novelas y fantasía",
                  "followers": 32, "source": "perfil"},
    "instagram": {"source": "feed", "handle": "lectora_1",
                  "permalink": "https://www.instagram.com/p/ABC123/",
                  "text": "Leo romantasy", "kind": "comment"},
}


def run(network, row, **opts):
    if network == "pinterest":
        snapshot = {"authors": [row], "pins": []}
    else:
        snapshot = [row]
    return n.normalize_candidates(network, snapshot, as_of=NOW, **opts)


class TestContracts(unittest.TestCase):
    def test_nine_network_interop_six_are_explicit(self):
        result = n.normalize_all({"x": [SAMPLES["x"]]}, as_of=NOW)
        self.assertEqual(set(result), set(n.NETWORKS))
        self.assertEqual(result["instagram"]["status"], "unsupported")
        self.assertEqual(result["reddit"]["capture"], "memory_only")
        self.assertEqual(result["x"]["status"], "normalized_offline")
        self.assertIsNone(result["x"]["complete"])

    def test_six_network_profile_inputs(self):
        for net, example in SAMPLES.items():
            with self.subTest(net=net):
                row = copy.deepcopy(example)
                if net == "facebook":
                    row["account_id"] = "98765"
                res = run(net, row)
                self.assertEqual(res["status"], "normalized_offline")
                self.assertEqual(len(res["shortlist"]), 1)
                c = res["shortlist"][0]
                self.assertEqual(c["posts"], [])   # all current scan timestamps unknown
                self.assertEqual(c["actions"], [])  # scanner 'kind' is not permission
                self.assertIsNone(c["following"])
                self.assertIsNone(c["followed_by"])

    def test_facebook_display_name_not_stable(self):
        res = run("facebook", SAMPLES["facebook"])
        self.assertFalse(res["shortlist"])
        self.assertEqual(res["diagnostics"][0]["reason"], "missing_stable_account_identity")

    def test_snapshot_none_distinct_from_empty(self):
        self.assertEqual(n.normalize_candidates("x", None, as_of=NOW)["status"], "unsupported")
        self.assertEqual(n.normalize_candidates("x", [], as_of=NOW)["status"], "normalized_offline")
        self.assertIsNone(n.normalize_candidates("x", [], as_of=NOW)["complete"])

    def test_bounded_inputs(self):
        with self.assertRaises(ValueError):
            n.normalize_candidates("x", [{}] * 10001, as_of=NOW)
        with self.assertRaises(ValueError):
            n.normalize_candidates("x", "bad", as_of=NOW)

    def test_queue_identity_no_coercion(self):
        src = dict(SAMPLES["x"], queue="API")
        self.assertEqual(run("x", src, queue="API")["shortlist"][0]["posts"], [])
        self.assertEqual(run("x", src, queue="WEB")["diagnostics"][0]["reason"], "queue_mismatch")
        self.assertEqual(run("x", src, queue="MOBILE")["diagnostics"][0]["reason"], "queue_mismatch")
        with self.assertRaises(ValueError):
            run("x", src, queue="UNKNOWN")

    def test_invalid_age_as_of_or_lane(self):
        with self.assertRaises(ValueError):
            run("x", SAMPLES["x"], max_post_age_days=-1)
        with self.assertRaises(ValueError):
            run("x", SAMPLES["x"], lane="bad")
        with self.assertRaises(ValueError):
            n.normalize_candidates("x", [], as_of="2026-10-10T10:00:00")

    def test_fresh_post_all_six(self):
        for net, example in SAMPLES.items():
            with self.subTest(net=net):
                row = copy.deepcopy(example)
                if net == "pinterest":
                    pin = {"author": row["handle"], "url": "https://www.pinterest.com/pin/123456/",
                           "title": "Libros de fantasía", "desc": "reseña", "query": "fantasía",
                           "created_at": FRESH, "language": "es"}
                    res = n.normalize_candidates(net, {"authors": [row], "pins": [pin]}, as_of=NOW)
                else:
                    row["created_at"] = FRESH
                    row["language"] = "es"
                    if net == "facebook":
                        row["account_id"] = "98765"
                    res = run(net, row)
                self.assertEqual(len(res["shortlist"][0]["posts"]), 1, res)
                self.assertEqual(res["shortlist"][0]["posts"][0]["language"], "es")

    def test_unknown_language_keeps_evidence_but_no_action(self):
        row = dict(SAMPLES["x"], created_at=FRESH, verified_actions=["reply"])
        result = run("x", row)
        p = result["shortlist"][0]["posts"][0]
        self.assertIsNone(p["language"])
        self.assertEqual(p["actions"], [])
        self.assertEqual(result["diagnostics"][-1]["reason"], "unknown_post_language")

    def test_language_not_inferred_from_query(self):
        row = dict(SAMPLES["threads"], source="lang:es fantasy", created_at=FRESH)
        self.assertIsNone(run("threads", row)["shortlist"][0]["posts"][0]["language"])

    def test_foreign_language_rejected(self):
        row = dict(SAMPLES["x"], created_at=FRESH, lang="en", verified_actions=["reply"])
        res = run("x", row)
        self.assertEqual(res["shortlist"][0]["posts"], [])
        self.assertIn("non_spanish_post", [d["reason"] for d in res["diagnostics"]])

    def test_post_date_validation_future_old_naive(self):
        for date, reason in [(OLD, "post_outside_age_window"),
                             ("2026-10-11T12:00:00Z", "post_outside_age_window"),
                             ("2026-10-09T12:00:00", "missing_post_timestamp"),
                             (None, "missing_post_timestamp")]:
            with self.subTest(date=date):
                res = run("x", dict(SAMPLES["x"], created_at=date, language="es"))
                self.assertEqual(res["shortlist"][0]["posts"], [])
                self.assertIn(reason, [d["reason"] for d in res["diagnostics"]])

    def test_dst_equivalence_and_utc(self):
        row = dict(SAMPLES["x"], created_at="2026-10-09T14:00:00+02:00",
                   language="es")
        p = run("x", row)["shortlist"][0]["posts"][0]
        self.assertEqual(p["created_at"], FRESH)
        self.assertEqual(p["url"], "https://x.com/lectora_1/status/12345")

    def test_community_age_policy(self):
        row = dict(SAMPLES["x"], created_at="2026-09-05T12:00:00Z", language="es")
        self.assertEqual(run("x", row)["shortlist"][0]["posts"], [])
        self.assertEqual(len(run("x", row, lane="community")["shortlist"][0]["posts"]), 1)

    def test_account_duplicate_rows_combine_evidence(self):
        one = dict(SAMPLES["x"], source="feed", created_at=FRESH, language="es")
        two = dict(SAMPLES["x"], source="search", created_at=FRESH, language="es")
        two["url"] = "https://twitter.com/lectora_1/status/12345?utm_source=foo"
        out = n.normalize_candidates("x", [one, two], as_of=NOW)
        self.assertEqual(len(out["shortlist"]), 1)
        self.assertEqual(out["shortlist"][0]["sources"], ["feed", "search"])
        self.assertEqual(len(out["shortlist"][0]["posts"]), 1)

    def test_handle_rename_with_stable_id(self):
        a = dict(SAMPLES["x"], account_id="111", handle="antes", url=None)
        b = dict(SAMPLES["x"], account_id="111", handle="despues", url=None)
        res = n.normalize_candidates("x", [a, b], as_of=NOW)
        self.assertEqual(len(res["shortlist"]), 1)
        row = res["shortlist"][0]
        self.assertEqual(row["account_id"], "111")
        self.assertNotIn("handle", row)  # PR #66 _identity is handle-first
        self.assertEqual(row["observed_handle"], "despues")
        self.assertIn("handle_rename_for_stable_id", [d["reason"] for d in res["diagnostics"]])

    def test_stable_ids_do_not_collide_with_similar_handles(self):
        a = dict(SAMPLES["threads"], account_id="11", permalink=None)
        b = dict(SAMPLES["threads"], account_id="12", permalink=None)
        res = n.normalize_candidates("threads", [a, b], as_of=NOW)
        self.assertEqual(len(res["shortlist"]), 2)

    def test_no_fake_source_independence(self):
        row = dict(SAMPLES["x"], source=None)
        data = run("x", row)["shortlist"][0]
        self.assertIsNone(data["sources"])

    def test_followers_bools_rejected_not_zero(self):
        row = dict(SAMPLES["pinterest"], followers=True)
        self.assertIsNone(run("pinterest", row)["shortlist"][0]["followers"])

    def test_unverified_known_not_recprocity(self):
        row = dict(SAMPLES["facebook"], account_id="123")
        self.assertIsNone(run("facebook", row)["shortlist"][0]["following"])

    def test_tuples_instagram_scan_in_memory(self):
        row = ("feed", "lectora_1", "Libro", "https://www.instagram.com/p/ABCD123/", "like")
        res = n.normalize_candidates("instagram", [row], as_of=NOW)
        self.assertEqual(len(res["shortlist"]), 1)
        self.assertEqual(res["shortlist"][0]["posts"], [])
        self.assertEqual(res["capture"], "memory_only")

    def test_reddit_created_utc_epoch(self):
        example = dict(SAMPLES["reddit"], created_utc=1791547200, language="es")
        example["created_utc"] = int(dt.datetime(2026, 10, 9, 12, tzinfo=dt.timezone.utc).timestamp())
        res = run("reddit", example)
        self.assertEqual(len(res["shortlist"][0]["posts"]), 1)

    def test_no_bio_from_pinterest_pin_text(self):
        res = n.normalize_candidates("pinterest",
            {"authors": [], "pins": [{"author": "lectora_1",
                "url": "https://pinterest.com/pin/12345",
                "title": "fantasía", "desc": "muchos libros",
                "language": "es", "created_at": FRESH}]},
            as_of=NOW)
        self.assertIsNone(res["shortlist"][0]["bio"])
        self.assertEqual(res["shortlist"][0]["posts"][0]["text"], "fantasía muchos libros")

    def test_spoof_and_scan_ordinal_not_a_post(self):
        for url in ["https://evil.test/p/ABCD123",
                    "https://www.instagram.com/p/1/",
                    "https://www.instagram.com/accounts/login/",
                    "http://www.instagram.com/p/ABC123/",
                    "https://instagram.com.evil.test/p/ABC123/"]:
            with self.subTest(url=url):
                result = run("instagram", dict(SAMPLES["instagram"], permalink=url,
                                              language="es", created_at=FRESH))
                self.assertEqual(result["shortlist"][0]["posts"], [])
        self.assertEqual(n._permalink("x", "https://x.com/user/status/1"), "https://x.com/user/status/1")

    def test_author_mismatch_does_not_attach_post(self):
        row = dict(SAMPLES["x"], handle="different", created_at=FRESH, language="es")
        res = run("x", row)
        self.assertEqual(res["shortlist"][0]["posts"], [])
        self.assertEqual(res["diagnostics"][0]["reason"], "post_author_mismatch")

    def test_post_actions_require_verified_action_and_spanish(self):
        row = dict(SAMPLES["threads"], created_at=FRESH, language="es",
                   verified_actions=["comment", "repost", "like", "follow"])
        p = run("threads", row)["shortlist"][0]["posts"][0]
        self.assertEqual(p["actions"], ["comment", "repost", "follow"])
        self.assertNotIn("like", run("x", dict(SAMPLES["x"], verified_actions=["like"]))["shortlist"][0]["actions"])

    def test_reddit_no_author_no_identity(self):
        row = dict(SAMPLES["reddit"], author="[deleted]", created_utc=1790000000)
        self.assertFalse(run("reddit", row)["shortlist"])

    def test_rejection_does_not_change_input(self):
        source = {"authors": [dict(SAMPLES["pinterest"])], "pins": []}
        orig = copy.deepcopy(source)
        n.normalize_candidates("pinterest", source, as_of=NOW)
        self.assertEqual(source, orig)

    def test_rank_66_contract_no_dependency_import_or_side_effects(self):
        normalized = n.normalize_all({"x": [SAMPLES["x"]]}, as_of=NOW)
        called = {}
        def fake_rank_all(snapshots, *, as_of, **kw):
            called.update(snapshots)
            self.assertEqual(as_of, NOW)
            return {"networks": snapshots}
        out = n.rank_with_66(normalized, fake_rank_all, as_of=NOW)
        self.assertIn("x", called)
        self.assertNotIn("reddit", called)
        self.assertEqual(out["networks"]["x"]["shortlist"][0]["handle"], "lectora_1")


    def test_account_language_not_inferred_from_a_single_post(self):
        row = dict(SAMPLES["x"], created_at=FRESH, language="es")
        self.assertIsNone(run("x", row)["shortlist"][0]["language"])
        row["profile_language"] = "es"
        self.assertEqual(run("x", row)["shortlist"][0]["language"], "es")

    def test_same_permalink_conflicting_timestamps_discarded(self):
        row = dict(SAMPLES["x"], language="es", created_at=FRESH)
        changed = dict(row, created_at="2026-10-08T12:00:00Z")
        out = n.normalize_candidates("x", [row, changed], as_of=NOW)
        self.assertEqual(out["shortlist"][0]["posts"], [])
        self.assertIn("conflicting_post_timestamps",
                      [d["reason"] for d in out["diagnostics"]])

    def test_duplicate_post_enriches_explicit_language(self):
        first = dict(SAMPLES["x"], created_at=FRESH)
        second = dict(first, language="es")
        out = n.normalize_candidates("x", [first, second], as_of=NOW)
        self.assertEqual(out["shortlist"][0]["posts"][0]["language"], "es")

    def test_conflicting_follower_numbers_flagged(self):
        a = dict(SAMPLES["x"], followers=40)
        b = dict(SAMPLES["x"], followers=50)
        out = n.normalize_candidates("x", [a, b], as_of=NOW)
        self.assertEqual(out["shortlist"][0]["followers"], 40)
        self.assertIn("conflicting_follower_snapshots",
                      [d["reason"] for d in out["diagnostics"]])

    def test_timestamp_requires_post_publication_provenance(self):
        row = dict(SAMPLES["x"], created_at=None, timestamp=FRESH, language="es")
        result = run("x", row)
        self.assertEqual(result["shortlist"][0]["posts"], [])
        self.assertIn("missing_post_timestamp", [d["reason"] for d in result["diagnostics"]])
        row["timestamp_provenance"] = "post_published"
        self.assertEqual(len(run("x", row)["shortlist"][0]["posts"]), 1)
        row["timestamp_provenance"] = "scan_observed"
        self.assertEqual(run("x", row)["shortlist"][0]["posts"], [])

    def test_reddit_huge_epoch_rejects_without_exception(self):
        row = dict(SAMPLES["reddit"], created_utc=10 ** 400)
        out = run("reddit", row)
        self.assertEqual(out["shortlist"][0]["posts"], [])
        self.assertIn("missing_post_timestamp", [d["reason"] for d in out["diagnostics"]])

    def test_old_post_handle_with_confirmed_author_id(self):
        row = dict(SAMPLES["x"], account_id="123", handle="renombrada",
                   created_at=FRESH, language="es", author_id="123")
        out = run("x", row)
        self.assertEqual(len(out["shortlist"][0]["posts"]), 1)
        row.pop("author_id")
        self.assertEqual(run("x", row)["shortlist"][0]["posts"], [])

    def test_reddit_comment_count_is_engagement_not_profile_followers(self):
        row = dict(SAMPLES["reddit"], created_utc=FRESH, language="es")
        out = run("reddit", row)["shortlist"][0]
        self.assertIsNone(out["followers"])
        self.assertEqual(out["posts"][0]["stats"]["replies"], 10)


    def test_facebook_posts_groups_videos_and_story_urls(self):
        urls = [
            "https://www.facebook.com/lectores/posts/12345/",
            "https://www.facebook.com/lectores/videos/12345/",
            "https://www.facebook.com/lectores/posts/pfbidABCDE123/",
            "https://www.facebook.com/groups/lectura_fantasia/permalink/12345/",
            "https://m.facebook.com/story.php?story_fbid=12345&id=9876",
            "https://www.facebook.com/permalink.php?story_fbid=12345&id=9876",
        ]
        for url in urls:
            with self.subTest(url=url):
                row = dict(SAMPLES["facebook"], account_id="9876",
                           permalink=url, created_at=FRESH, language="es")
                res = run("facebook", row)
                self.assertEqual(len(res["shortlist"][0]["posts"]), 1, res)
        for url in ("https://www.facebook.com/lectores",
                    "https://www.facebook.com/groups/lectura_fantasia",
                    "https://evil.facebook.com/lectores/posts/12345/"):
            row = dict(SAMPLES["facebook"], account_id="9876",
                       permalink=url, created_at=FRESH, language="es")
            self.assertEqual(run("facebook", row)["shortlist"][0]["posts"], [])


    def test_estonian_is_not_spanish_but_regional_spanish_is(self):
        example = dict(SAMPLES["x"], created_at=FRESH, verified_actions=["reply"])
        rejected = run("x", dict(example, language="est"))
        self.assertEqual(rejected["shortlist"][0]["posts"], [])
        self.assertIn("non_spanish_post", [d["reason"] for d in rejected["diagnostics"]])
        accepted = run("x", dict(example, language="es-MX"))
        self.assertEqual(accepted["shortlist"][0]["posts"][0]["actions"], ["reply"])

    def test_explicit_post_author_id_mismatch_rejected_on_five_networks(self):
        for network in ("x", "threads", "facebook", "reddit", "instagram"):
            with self.subTest(network=network):
                row = dict(SAMPLES[network], account_id="111", author_id="222",
                           created_at=FRESH, language="es")
                result = run(network, row)
                self.assertEqual(result["shortlist"][0]["posts"], [])
                self.assertIn("post_author_mismatch",
                              [d["reason"] for d in result["diagnostics"]])

    def test_placeholder_ids_are_not_stable_remote_identity(self):
        for placeholder in ("unknown", "None", "null", "undefined", "deleted", "N/A"):
            with self.subTest(placeholder=placeholder):
                row = dict(SAMPLES["facebook"], account_id=placeholder,
                           created_at=FRESH, language="es")
                result = run("facebook", row)
                self.assertEqual(result["shortlist"], [])
                self.assertEqual(result["diagnostics"][0]["reason"],
                                 "missing_stable_account_identity")

    def test_nullable_language_and_account_id_fallbacks(self):
        row = dict(SAMPLES["x"], account_id=None, user_id="111",
                   created_at=FRESH, language=None, lang="es")
        result = run("x", row)
        self.assertEqual(result["shortlist"][0]["account_id"], "111")
        self.assertEqual(result["shortlist"][0]["posts"][0]["language"], "es")

    def test_facebook_generic_source_and_url_are_preserved(self):
        row = {"account_id": "111", "source": "lecturas",
               "url": "https://www.facebook.com/lectores/posts/12345",
               "created_at": FRESH, "language": "es"}
        result = run("facebook", row)
        self.assertEqual(result["shortlist"][0]["sources"], ["lecturas"])
        self.assertEqual(len(result["shortlist"][0]["posts"]), 1)

    def test_invalid_nested_shape_and_network(self):
        with self.assertRaises(ValueError):
            n.normalize_candidates("pinterest", {"authors": [], "pins": None}, as_of=NOW)
        with self.assertRaises(ValueError):
            n.normalize_candidates("bluesky", [], as_of=NOW)
        with self.assertRaises(ValueError):
            n.normalize_all({"unknown": []}, as_of=NOW)


    def test_conflicting_explicit_account_ids_rejected_across_six_networks(self):
        for network, original in SAMPLES.items():
            with self.subTest(network=network):
                row = dict(original, account_id="remote_A", user_id="remote_B",
                           verified_actions=["follow"])
                if network == "pinterest":
                    snapshot = {"authors": [row], "pins": []}
                else:
                    snapshot = [row]
                out = n.normalize_candidates(network, snapshot, as_of=NOW)
                self.assertEqual(out["shortlist"], [])
                self.assertIn("conflicting_account_ids",
                              [d["reason"] for d in out["diagnostics"]])

    def test_conflicting_ids_cannot_suppress_legitimate_handle_observation(self):
        # Pre-scan of stable handles must also ignore contradictory rows.
        valid_handle_only = dict(SAMPLES["threads"], permalink=None)
        conflicting = dict(valid_handle_only, account_id="remote_A",
                           user_id="remote_B")
        for order in ((valid_handle_only, conflicting),
                      (conflicting, valid_handle_only)):
            out = n.normalize_candidates("threads", list(order), as_of=NOW)
            self.assertEqual(len(out["shortlist"]), 1)
            self.assertEqual(out["shortlist"][0]["handle"], "lectora.1")
            self.assertIn("conflicting_account_ids",
                          [d["reason"] for d in out["diagnostics"]])
            self.assertNotIn("ambiguous_handle_with_stable_id",
                             [d["reason"] for d in out["diagnostics"]])

    def test_mixed_handle_and_id_fail_closed_independent_of_row_order(self):
        for network in ("x", "threads", "reddit", "pinterest", "instagram"):
            sample = dict(SAMPLES[network], url=None, permalink=None)
            if network == "pinterest":
                sample = {"handle": "lectora_1", "source": "search"}
            with self.subTest(network=network):
                with_id = dict(sample, account_id="remote_123")
                for order in ((sample, with_id), (with_id, sample)):
                    if network == "pinterest":
                        snap = {"authors": list(order), "pins": []}
                    else:
                        snap = list(order)
                    out = n.normalize_candidates(network, snap, as_of=NOW)
                    self.assertEqual(len(out["shortlist"]), 1)
                    self.assertEqual(out["shortlist"][0]["account_id"], "remote_123")
                    self.assertIn("ambiguous_handle_with_stable_id",
                                  [d["reason"] for d in out["diagnostics"]])

    def test_pinterest_metadata_survives_with_queue_and_author_provenance(self):
        pin = {"author": "lectora_1", "account_id": "p123", "author_id": "p123",
               "url": "https://www.pinterest.com/pin/44444/",
               "title": "Fantasía española", "query": "romantasy",
               "created_at": FRESH, "language": "es",
               "verified_actions": ["comment"], "queue": "API"}
        snap = {"authors": [], "pins": [pin]}
        web = n.normalize_candidates("pinterest", snap, as_of=NOW)
        self.assertEqual(web["shortlist"], [])
        self.assertIn("queue_mismatch", [d["reason"] for d in web["diagnostics"]])
        api = n.normalize_candidates("pinterest", snap, as_of=NOW, queue="API")
        self.assertEqual(api["shortlist"][0]["account_id"], "p123")
        self.assertEqual(api["shortlist"][0]["posts"][0]["actions"], ["comment"])
        mismatch = dict(pin, author_id="p999")
        fail = n.normalize_candidates("pinterest", {"authors": [], "pins": [mismatch]},
                                      as_of=NOW, queue="API")
        self.assertEqual(fail["shortlist"][0]["posts"], [])
        self.assertIn("post_author_mismatch",
                      [d["reason"] for d in fail["diagnostics"]])

    def test_pinterest_conflicting_handle_and_author_rejected(self):
        pin = {"author": "lector_1", "handle": "lector_2", "account_id": "p123",
               "url": "https://www.pinterest.com/pin/12345/",
               "created_at": FRESH, "language": "es"}
        out = n.normalize_candidates("pinterest",
                                     {"authors": [], "pins": [pin]}, as_of=NOW)
        self.assertEqual(out["shortlist"], [])
        self.assertIn("conflicting_pin_author_handles",
                      [d["reason"] for d in out["diagnostics"]])

    def test_one_post_cannot_generate_opportunities_for_two_account_ids(self):
        rows = [dict(SAMPLES["x"], account_id=uid, created_at=FRESH,
                     language="es", verified_actions=["reply"])
                for uid in ("111", "222")]
        out = n.normalize_candidates("x", rows, as_of=NOW)
        self.assertEqual(len(out["shortlist"]), 2)
        self.assertTrue(all(not row["posts"] for row in out["shortlist"]))
        self.assertIn("cross_account_post_collision",
                      [d["reason"] for d in out["diagnostics"]])

    def test_x_threads_immutable_post_id_survives_handle_changes(self):
        # A renamed profile does not turn one remote post into two posts.
        for network, base_url, suffix in (
            ("x", "https://x.com", "status/12345"),
            ("threads", "https://www.threads.net", "post/ABC123"),
        ):
            with self.subTest(network=network):
                def candidate(handle, account_id):
                    prefix = "@" if network == "threads" else ""
                    return {
                        "account_id": account_id, "author_id": account_id,
                        "handle": handle,
                        "url": f"{base_url}/{prefix}{handle}/{suffix}",
                        "created_at": FRESH, "language": "es",
                        "text": "Leo fantasía", "verified_actions": ["reply"],
                    }
                older = candidate("lectora_old", "remote_1")
                renamed = candidate("lectora_new", "remote_1")
                for rows in ([older, renamed], [renamed, older]):
                    out = n.normalize_candidates(network, rows, as_of=NOW)
                    self.assertEqual(len(out["shortlist"]), 1)
                    self.assertEqual(len(out["shortlist"][0]["posts"]), 1)
                    self.assertNotIn("cross_account_post_collision",
                                     [d["reason"] for d in out["diagnostics"]])
                # Distinct account IDs claiming the same remote ID must
                # not yield two ranked opportunities just by changing URLs.
                conflicting = candidate("otra_cuenta", "remote_2")
                out = n.normalize_candidates(network, [older, conflicting], as_of=NOW)
                self.assertEqual(len(out["shortlist"]), 2)
                self.assertTrue(all(not row["posts"] for row in out["shortlist"]))
                self.assertIn("cross_account_post_collision",
                              [d["reason"] for d in out["diagnostics"]])

    def test_x_handle_change_conflicting_post_dates_rejects_both(self):
        first = dict(SAMPLES["x"], handle="lectora_old",
                     url="https://x.com/lectora_old/status/12345",
                     account_id="remote_1", author_id="remote_1",
                     created_at=FRESH, language="es")
        second = dict(first, handle="lectora_new",
                      url="https://x.com/lectora_new/status/12345",
                      created_at="2026-10-08T12:00:00Z")
        out = n.normalize_candidates("x", [first, second], as_of=NOW)
        self.assertEqual(out["shortlist"][0]["posts"], [])
        self.assertIn("conflicting_post_timestamps",
                      [d["reason"] for d in out["diagnostics"]])

    def test_pinterest_author_profile_language_not_pin_language(self):
        author = dict(SAMPLES["pinterest"], language="es")
        pin = {"author": "lectora_1",
               "url": "https://www.pinterest.com/pin/14445/",
               "created_at": FRESH, "language": "en", "title": "Book"}
        out = n.normalize_candidates("pinterest",
                                     {"authors": [author], "pins": [pin]}, as_of=NOW)
        self.assertEqual(out["shortlist"][0]["language"], "es")
        self.assertEqual(out["shortlist"][0]["posts"], [])
        without_author_lang = dict(SAMPLES["pinterest"])
        out = n.normalize_candidates("pinterest",
                                     {"authors": [without_author_lang], "pins": [dict(pin, language="es")]},
                                     as_of=NOW)
        self.assertIsNone(out["shortlist"][0]["language"])
        self.assertEqual(len(out["shortlist"][0]["posts"]), 1)

    def test_real_ranker_nine_network_contract_and_missing_inputs(self):
        import target_quality_ranking as quality
        observations = {}
        for network in n.NETWORKS:
            if network == "pinterest":
                observations[network] = {
                    "authors": [dict(SAMPLES["pinterest"])],
                    "pins": [{"author": "lectora_1",
                              "url": "https://www.pinterest.com/pin/44444/",
                              "created_at": FRESH, "language": "es",
                              "title": "Fantasía juvenil"}]}
            else:
                row = dict(SAMPLES[network], created_at=FRESH, language="es")
                if network == "facebook":
                    row["account_id"] = "fb123"
                observations[network] = [row]
        normalized = n.normalize_all(observations, as_of=NOW)
        partial = n.rank_with_66(normalized, quality.rank_all, as_of=NOW)
        for name in n.NATIVE_NETWORKS:
            self.assertEqual(partial["networks"][name]["status"], "missing_input")
        native = {
            "bluesky": [{"handle": "lectora.example", "bio": "Leo fantasía"}],
            "mastodon": [{"acct": "lectora@example.org", "bio": "Leo libros"}],
            "tiktok": [{"handle": "lectora_tiktok", "bio": "Leo romantasy"}]}
        ranked = n.rank_with_66(normalized, quality.rank_all, as_of=NOW,
                                native_snapshots=native)
        self.assertEqual(set(ranked["networks"]), set(quality.NETWORKS))
        for network in quality.NETWORKS:
            with self.subTest(network=network):
                self.assertEqual(ranked["networks"][network]["status"], "ranked")
                self.assertEqual(len(ranked["networks"][network]["ranked"]), 1)
        with self.assertRaises(ValueError):
            n.rank_with_66(normalized, quality.rank_all, as_of=NOW,
                           native_snapshots={"x": []})

if __name__ == "__main__":
    unittest.main()
