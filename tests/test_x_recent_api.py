"""Offline contract tests for the optional Tweepy read adapter (PR #122)."""
import datetime as dt
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import x_recent_api as xapi

NOW = dt.datetime(2026, 10, 10, 9, 0, tzinfo=dt.timezone.utc)


def sample(*, post_id="12345", username="Lectora", author_id="654", lang="es",
           created_at="2026-10-10T08:00:00Z", text="¿Qué fantasía recomendáis?"):
    return {"data": [{"id": post_id, "author_id": author_id, "lang": lang,
                      "created_at": created_at, "text": text}],
            "includes": {"users": [{"id": author_id, "username": username}]}, "meta": {}}


class QueryTests(unittest.TestCase):
    def test_spanish_filters_and_unicode_dedupe(self):
        q = xapi.build_queries(["romantasy", "fantasía", "fantasi\u0301a", "#BookTok"])
        self.assertEqual(q, ['("romantasy" OR "fantasía" OR #BookTok) lang:es -is:retweet'])

    def test_multiple_queries_limited(self):
        q = xapi.build_queries(["fantasía", "romantasy", "novela juvenil"], max_per_query=2)
        self.assertEqual(len(q), 2)
        self.assertTrue(all(len(k) <= 512 for k in q))
        with self.assertRaises(ValueError):
            xapi.build_queries(["fantasía", "romantasy", "novela juvenil"], max_per_query=1, max_groups=2)

    def test_reject_operator_injection_and_invalid_types(self):
        for term in ['"foo" -is:retweet', 'abc (lang:en)', "-from:davidporto", "bad\nquery", 123]:
            with self.subTest(term=term), self.assertRaises(ValueError):
                xapi.build_queries([term])


class NormalizeTests(unittest.TestCase):
    def test_normalization_preserves_post_remote_identity(self):
        row = xapi.normalize_page(sample(), now=NOW)[0]
        self.assertEqual(row["url"], "https://x.com/Lectora/status/12345")
        self.assertEqual(row["author_id"], "654")
        self.assertEqual(row["age_hours"], 1.0)
        self.assertEqual(row["source"], xapi.X_SOURCE)

    def test_reject_missing_or_mismatched_author(self):
        response = sample()
        response["includes"]["users"] = [{"id": "456", "username": "Lectora"}]
        self.assertEqual(xapi.normalize_page(response, now=NOW), [])
        response = sample(username="Lectora/status/1")
        self.assertEqual(xapi.normalize_page(response, now=NOW), [])

    def test_only_spanish_not_repost_and_not_self(self):
        self.assertEqual(xapi.normalize_page(sample(lang="en"), now=NOW), [])
        self.assertEqual(xapi.normalize_page(sample(username="DavidPortoDiaz"), now=NOW), [])
        response = sample()
        response["data"][0]["referenced_tweets"] = [{"type": "retweeted", "id": "10"}]
        self.assertEqual(xapi.normalize_page(response, now=NOW), [])

    def test_future_missing_and_stale_dates_are_not_guessed(self):
        for value in ["2026-10-11T10:00:00Z", "2026-09-01T12:00:00Z", None, "2026-10-10T09:00:00"]:
            with self.subTest(value=value):
                self.assertEqual(xapi.normalize_page(sample(created_at=value), now=NOW), [])

    def test_reject_bad_ids_and_partial_error_response(self):
        for value in ["abc", "0", "1/2", True]:
            self.assertEqual(xapi.normalize_page(sample(post_id=value), now=NOW), [])
        with self.assertRaises(xapi.InvalidXResponse):
            xapi.normalize_page({**sample(), "errors": [{"detail": "partial"}]}, now=NOW)

    def test_duplicate_posts_and_conflicting_user_expansions(self):
        response = sample()
        response["data"] *= 2
        self.assertEqual(len(xapi.normalize_page(response, now=NOW)), 1)
        response["includes"]["users"].append({"id": "654", "username": "Otra"})
        with self.assertRaises(xapi.InvalidXResponse):
            xapi.normalize_page(response, now=NOW)

    def test_accept_tweepy_object_models(self):
        obj = types.SimpleNamespace(data=[types.SimpleNamespace(data=sample()["data"][0])],
            includes={"users": [types.SimpleNamespace(data=sample()["includes"]["users"][0])]}, meta={})
        self.assertEqual(len(xapi.normalize_page(obj, now=NOW)), 1)

    def test_require_aware_test_clock(self):
        with self.assertRaises(ValueError):
            xapi.normalize_page(sample(), now=dt.datetime(2026, 10, 10))


class CollectorTests(unittest.TestCase):
    def test_read_only_client_and_pagination_dedupe(self):
        class Client:
            def __init__(self): self.calls = []
            def search_recent_tweets(self, **kwargs):
                self.calls.append(kwargs)
                response = sample()
                if len(self.calls) == 1:
                    response["meta"] = {"next_token": "next"}
                return response
        client = Client()
        posts = xapi.collect_recent(client, xapi.build_queries(["fantasía"]), now=NOW, max_pages=2)
        self.assertEqual(len(posts), 1)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[1]["next_token"], "next")
        self.assertEqual(client.calls[0]["expansions"], ["author_id"])

    def test_duplicate_pagination_token_fails_closed(self):
        class Client:
            def search_recent_tweets(self, **kwargs):
                return {**sample(), "meta": {"next_token": "repeat"}}
        with self.assertRaises(xapi.InvalidXResponse):
            xapi.collect_recent(Client(), xapi.build_queries(["fantasía"]), now=NOW, max_pages=3)

    def test_rate_limit_propagates_without_retry(self):
        class Limit(Exception): pass
        class Client:
            calls = 0
            def search_recent_tweets(self, **kwargs):
                self.calls += 1
                raise Limit("429")
        c = Client()
        with self.assertRaises(Limit):
            xapi.collect_recent(c, xapi.build_queries(["fantasía"]), now=NOW)
        self.assertEqual(c.calls, 1)

    def test_invalid_budget_does_not_make_network_calls(self):
        class Client:
            def search_recent_tweets(self, **kwargs):
                raise AssertionError("no debería llamarse")
        with self.assertRaises(ValueError):
            xapi.collect_recent(Client(), ["malicious lang:en"], now=NOW)
        with self.assertRaises(ValueError):
            xapi.collect_recent(Client(), xapi.build_queries(["fantasía"]), max_pages=4)

    def test_stage_reuses_existing_pool_interface(self):
        posts = xapi.normalize_page(sample(), now=NOW)
        fake = types.SimpleNamespace(record_posts=lambda db, rows, source, today=None: (db, rows, source, today))
        with patch.dict(sys.modules, {"x_pool": fake}):
            result = xapi.stage_in_existing_pool("db", posts, today="2026-10-10")
        self.assertEqual(result[0], "db")
        self.assertEqual(result[1], posts)
        self.assertEqual(result[2], xapi.X_SOURCE)


if __name__ == "__main__":
    unittest.main()
