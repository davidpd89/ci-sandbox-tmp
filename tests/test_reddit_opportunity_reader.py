"""Hermetic Reddit opportunity tests: no OAuth, HTTP, browsers or writes."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reddit_opportunity_reader as r

NOW = dt.datetime(2026, 10, 10, 9, tzinfo=dt.timezone.utc)


def post(*, post_id="abc123", sub="libros", title="¿Qué libros de fantasía lees?",
         author="lector_es", created=None, body="", score=12, comments=4, ratio=.75):
    if created is None:
        created = NOW.timestamp() - 3600
    return types.SimpleNamespace(
        id=post_id, subreddit=types.SimpleNamespace(display_name=sub),
        author=(types.SimpleNamespace(name=author) if author is not None else None),
        created_utc=created, title=title, selftext=body, score=score,
        num_comments=comments, upvote_ratio=ratio,
    )


class FakeSubreddit:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        data = self.data.get(query, [])
        if isinstance(data, BaseException):
            raise data
        return iter(data)


class FakeReddit:
    def __init__(self, mapping):
        self.mapping = {k: FakeSubreddit(v) for k, v in mapping.items()}
        self.queried = []

    def subreddit(self, name):
        self.queried.append(name)
        return self.mapping[name]


class RedditOpportunityTests(unittest.TestCase):
    def collect(self, client=None, **kwargs):
        return r.collect(client or FakeReddit({"libros": {}}),
                         as_of=NOW, subreddits=["libros"],
                         queries=["fantasía"], **kwargs)

    def test_real_praw_search_signature_read_only(self):
        cli = FakeReddit({"libros": {"fantasía": [post()]}})
        found = self.collect(cli)
        self.assertEqual(cli.mapping["libros"].calls,
                         [("fantasía", {"sort": "new", "time_filter": "week", "limit": 25})])
        self.assertEqual(found["diagnostics"]["accepted"], 1)
        row = found["observations"][0]
        self.assertEqual((row["post_id"], row["subreddit"]), ("abc123", "libros"))
        self.assertEqual(row["queue"], "API")
        self.assertEqual(row["status"], "manual_review_required")
        self.assertEqual(row["verified_actions"], [])
        self.assertIsNone(row["language"])
        self.assertEqual(row["queries"], ["fantasía"])
        self.assertTrue(row["url"].endswith("/comments/abc123/"))
        self.assertIn("fantasia", row["topic_hints"])
        self.assertTrue(row["question_hint"])

    def test_dedupes_cross_query_and_canonical_id(self):
        p1 = post(post_id="ABC123")
        p2 = post(post_id="abc123")
        cli = FakeReddit({"libros": {"fantasía": [p1], "libros": [p2]}})
        found = r.collect(cli, as_of=NOW, subreddits=["libros"],
                          queries=["fantasía", "libros"])
        self.assertEqual(len(found["observations"]), 1)
        self.assertEqual(found["observations"][0]["queries"], ["fantasía", "libros"])
        self.assertEqual(found["diagnostics"]["duplicates"], 1)

    def test_conflicting_same_remote_id_aborts(self):
        cli = FakeReddit({"libros": {
            "fantasía": [post(title="Una")], "libros": [post(title="Otra")]
        }})
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            r.collect(cli, as_of=NOW, subreddits=["libros"],
                      queries=["fantasía", "libros"])

    def test_rejects_unapproved_subreddits_and_rall(self):
        for subs in (["all"], ["escribir"], ["libros", "escribir"], [],
                     ["libros", "LIBROS"], ["libros;all"], ["../../all"]):
            with self.subTest(subs=subs), self.assertRaises(ValueError):
                r.collect(FakeReddit({}), as_of=NOW, subreddits=subs,
                          queries=["fantasía"])

    def test_never_follows_urls_or_results_to_other_communities(self):
        cli = FakeReddit({"libros": {"fantasía": [
            post(sub="escribir"), post(post_id="abc124")
        ]}})
        found = self.collect(cli)
        self.assertEqual(found["diagnostics"]["rejected"], 1)
        self.assertEqual(found["observations"][0]["post_id"], "abc124")
        self.assertEqual(cli.queried, ["libros"])

    def test_timestamp_timezone_and_missing_evidence(self):
        bad = [post(post_id="a001", created=NOW.timestamp() + 1),
               post(post_id="a002", created=NOW.timestamp() - 8 * 86400),
               post(post_id="a003", created=True),
               post(post_id="a004", created=float("nan")),
               post(post_id="a005", created=None)]
        bad[-1].created_utc = None
        cli = FakeReddit({"libros": {"fantasía": bad}})
        found = self.collect(cli)
        self.assertEqual(len(found["observations"]), 0)
        self.assertEqual(found["diagnostics"]["rejected"], 5)
        with self.assertRaises(ValueError):
            r.collect(cli, as_of=NOW.replace(tzinfo=None),
                      subreddits=["libros"], queries=["fantasía"])

    def test_invalid_post_id_title_and_deleted_account(self):
        cli = FakeReddit({"libros": {"fantasía": [
            post(post_id="hello/world"),
            post(post_id="aaa111", title=""),
            post(post_id="bbb222", author="[deleted]"),
            post(post_id="ccc333", author=None),
        ]}})
        found = self.collect(cli)
        self.assertEqual(len(found["observations"]), 2)
        self.assertTrue(all(x["author"] is None for x in found["observations"]))

    def test_signal_not_language_guess(self):
        result = r.text_signals("¿Qué romantasy recomiendas?",
                                "Me gustan los dragones y enemies to lovers")
        self.assertIn("romantasy", result["topic_hints"])
        self.assertIn("fantasia", result["topic_hints"])
        self.assertTrue(result["question_hint"])
        self.assertEqual(r.text_signals("Mi texto no es sobre fantasías")["topic_hints"], [])
        self.assertEqual(r.text_signals("El libro", "sin pregunta")["question_hint"], False)

    def test_missing_numeric_engagement_remains_unknown(self):
        cli = FakeReddit({"libros": {"fantasía": [
            post(score=True, comments=-1, ratio=2.3)
        ]}})
        row = self.collect(cli)["observations"][0]
        self.assertIsNone(row["score"])
        self.assertIsNone(row["comment_count"])
        self.assertIsNone(row["upvote_ratio"])

    def test_api_errors_propagate_without_false_complete(self):
        for err in (RuntimeError("429"), RuntimeError("503")):
            cli = FakeReddit({"libros": {"fantasía": err}})
            with self.subTest(error=str(err)), self.assertRaisesRegex(RuntimeError, str(err)):
                self.collect(cli)

    def test_oversized_stream_fails_closed(self):
        # A faulty adapter ignores PRAW's limit. Hard ceiling also applies
        # to repeated scans from different terms.
        cli = FakeReddit({"libros": {"fantasía": [post()] * 1001}})
        with self.assertRaisesRegex(ValueError, "unbounded"):
            self.collect(cli)

    def test_bounded_queries_and_limits(self):
        for kw in ([], ["a"], ["fantasía", "fantasía"], ["a" * 101],
                   [chr(10) + "fantasía"], ["xx"] * 21):
            with self.subTest(queries=kw), self.assertRaises(ValueError):
                r.collect(FakeReddit({}), as_of=NOW,
                          subreddits=["libros"], queries=kw)
        for value in (0, 101, True, "50"):
            with self.subTest(limit=value), self.assertRaises(ValueError):
                self.collect(limit_per_query=value)
        for value in (0, 31, True, "7"):
            with self.subTest(age=value), self.assertRaises(ValueError):
                self.collect(max_age_days=value)

    def test_multisubreddit_explicit(self):
        cli = FakeReddit({
            "libros": {"lectura": [post(post_id="abc321")]},
            "filosofia_en_espanol": {"lectura": [
                post(post_id="def321", sub="filosofia_en_espanol")
            ]}
        })
        result = r.collect(cli, as_of=NOW,
                           subreddits=["libros", "filosofia_en_espanol"],
                           queries=["lectura"])
        self.assertEqual(len(result["observations"]), 2)
        self.assertEqual(set(cli.queried), {"libros", "filosofia_en_espanol"})

    def test_review_only_jsonl_roundtrip(self):
        rows = self.collect(FakeReddit({"libros": {"fantasía": [post()]}}))["observations"]
        exported = r.to_jsonl(rows)
        self.assertEqual(json.loads(exported)["status"], "manual_review_required")
        self.assertEqual(json.loads(exported)["language"], None)
        self.assertIn("fantasía", exported)
        with self.assertRaises(ValueError):
            r.to_jsonl([{"network": "reddit", "status": "executable"}])

    def test_optional_praw_factory_receives_only_explicit_credentials(self):
        calls = []
        stub = types.ModuleType("praw")
        def constructor(**kw):
            calls.append(kw)
            return types.SimpleNamespace(read_only=True)
        stub.Reddit = constructor
        with patch.dict(sys.modules, {"praw": stub}):
            client = r.make_praw_readonly_client(
                client_id="id", client_secret="s", user_agent="test/1")
        self.assertTrue(client.read_only)
        self.assertEqual(calls, [{"client_id": "id",
                                  "client_secret": "s",
                                  "user_agent": "test/1"}])
        for empty in ("", "  ", None):
            with self.assertRaises(ValueError):
                r.make_praw_readonly_client(
                    client_id="id", client_secret=empty, user_agent="test/1")

    def test_factory_aborts_if_client_not_readonly(self):
        stub = types.ModuleType("praw")
        stub.Reddit = lambda **kw: types.SimpleNamespace(read_only=False)
        with patch.dict(sys.modules, {"praw": stub}), self.assertRaisesRegex(
                RuntimeError, "read-only"):
            r.make_praw_readonly_client(client_id="id", client_secret="sec",
                                        user_agent="test/1")


if __name__ == "__main__":
    unittest.main()
