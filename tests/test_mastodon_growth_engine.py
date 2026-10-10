"""Pruebas offline del motor amplio de crecimiento Mastodon."""
import copy
import datetime as dt
import json
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
requests_stub.post = lambda *a, **k: None
requests_stub.delete = lambda *a, **k: None
x_stub = types.ModuleType("x_interact")
x_stub._check_spanish_orthography = lambda text: None
sys.modules.setdefault("requests", requests_stub)
sys.modules.setdefault("x_interact", x_stub)

import mastodon_interact as m
import mastodon_growth_scan as gs
import mastodon_build_plan as bp
import mastodon_execute as execute


def account(acct, ident="1", **extra):
    return {
        "id": ident,
        "acct": acct,
        "username": acct.split("@", 1)[0],
        "display_name": acct,
        "note": "Lectora de fantasía y novelas",
        "followers_count": 30,
        "following_count": 40,
        "statuses_count": 100,
        **extra,
    }


def status(ident, acct="lectora@mastodon.social", text="Estoy leyendo fantasía juvenil", **extra):
    return {
        "id": str(ident),
        "url": f"https://mastodon.social/@{acct.split('@')[0]}/{ident}",
        "uri": f"https://mastodon.social/users/{acct.split('@')[0]}/statuses/{ident}",
        "visibility": "public",
        "content": f"<p>{text}</p>",
        "created_at": "2026-09-29T10:00:00Z",
        "replies_count": 2,
        "favourites_count": 4,
        "reblogs_count": 1,
        "account": account(acct, "1"),
        "tags": [{"name": "Bookstodon"}],
        **extra,
    }


class Response:
    def __init__(self, payload, *, status_code=200, headers=None, text=""):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


class MastodonPaginationTests(unittest.TestCase):
    def test_paginated_reader_follows_only_local_next_link(self):
        calls = []
        first = Response([{"id": "1"}], headers={
            "Link": '<https://mastodon.social/api/v1/notifications?max_id=1>; rel="next"'
        })
        second = Response([{"id": "2"}])

        def get(url, params=None, **kwargs):
            calls.append((url, params))
            return first if len(calls) == 1 else second

        with patch.object(m, "_headers", return_value={"Authorization": "Bearer test"}), \
             patch.object(m.requests, "get", side_effect=get):
            rows = m._get_paginated("notifications", {"limit": 1}, max_pages=2)

        self.assertEqual([row["id"] for row in rows], ["1", "2"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][1], {})

    def test_paginated_reader_rejects_off_instance_link(self):
        response = Response([], headers={
            "Link": '<https://evil.example/api/v1/notifications?max_id=1>; rel="next"'
        })
        with patch.object(m, "_headers", return_value={}), \
             patch.object(m.requests, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "fuera de la API local"):
                m._get_paginated("notifications", max_pages=2)

    def test_429_preserves_retry_after(self):
        response = Response({}, status_code=429, headers={"Retry-After": "30"}, text="slow down")
        with patch.object(m, "_headers", return_value={}), \
             patch.object(m.requests, "get", return_value=response):
            with self.assertRaises(m.MastodonRateLimitExceeded) as caught:
                m._get("notifications")
        self.assertEqual(caught.exception.retry_after, "30")

    def test_account_search_uses_offset_pages(self):
        params = []

        def search(_query, _kind, limit, **kwargs):
            params.append((limit, kwargs.get("offset")))
            return {"accounts": [{"id": str(len(params))}]}

        with patch.object(m, "search", side_effect=search):
            rows = m.search_accounts_pages("lectora", limit=1, max_pages=2)
        self.assertEqual([row["id"] for row in rows], ["1", "2"])
        self.assertEqual(params, [(1, 0), (1, 1)])

    def test_quote_engagers_capability_is_version_specific(self):
        with patch.object(m, "instance_info", return_value={"version": "4.5.1"}):
            self.assertTrue(m.supports_status_quotes())
        with patch.object(m, "instance_info", return_value={"version": "4.4.9"}):
            self.assertFalse(m.supports_status_quotes())


class MastodonGrowthScanTests(unittest.TestCase):
    def collector(self):
        config = gs._load_config(gs.CONFIG_PATH)
        return gs.Collector(
            config,
            today=dt.date(2026, 9, 29),
            write_metrics=False,
            run_id="test",
        )

    def test_scan_captures_profiles_posts_and_dynamic_tags(self):
        c = self.collector()
        c.own = "autorademodiaz"
        c.own_id = "david"
        c.use_surface("health")
        c.add_status(status("1"), "post_search", "fantasia")
        item = c.candidates["lectora@mastodon.social"]
        self.assertIn("1", item["posts"])
        self.assertEqual(c.posts["1"]["tags"], ["Bookstodon"])

    def test_own_post_is_seed_without_self_becoming_candidate(self):
        c = self.collector()
        c.own = "autorademodiaz"
        own_status = status("2", "autorademodiaz@mastodon.social")
        self.assertTrue(c.add_status(own_status, "own_post", "me"))
        self.assertNotIn("autorademodiaz@mastodon.social", c.candidates)
        self.assertIn("2", c.posts)

    def test_private_and_sensitive_statuses_do_not_offer_interactions(self):
        c = self.collector()
        c.own = "autorademodiaz"
        private = status("3", visibility="private")
        sensitive = status("4", sensitive=True)
        self.assertFalse(c.add_status(private, "post_search"))
        self.assertTrue(c.add_status(sensitive, "post_search"))
        item = c.candidates["lectora@mastodon.social"]
        stored = c.posts["4"]
        self.assertEqual(gs._post_actions(item, stored), [])

    def test_builder_accepts_more_than_legacy_daily_quota(self):
        scan_data = {
            "auto_plan": [],
            "shortlist": [],
        }
        for index in range(40):
            cid = f"M{index + 1:03d}"
            pid = cid + "-P1"
            scan_data["shortlist"].append({
                "id": cid,
                "acct": f"lectora{index}@mastodon.social",
                "lane": "acquisition",
                "sources": ["post_search"],
                "actions": ["follow"],
                "posts": [{
                    "id": pid,
                    "status_id": str(index + 1),
                    "url": f"https://mastodon.social/@lectora{index}/{index + 1}",
                    "sources": ["post_search"],
                    "actions": ["favourite", "reply"],
                }],
            })
        decisions = {"actions": [
            {"candidate": f"M{index + 1:03d}", "kind": "follow"}
            for index in range(40)
        ]}
        self.assertEqual(len(bp.build(scan_data, decisions)), 40)

    def test_repeated_action_on_same_status_is_rejected(self):
        scan_data = {
            "auto_plan": [],
            "shortlist": [{
                "id": "M001", "acct": "lectora@mastodon.social", "lane": "acquisition",
                "sources": ["post_search"], "actions": [],
                "posts": [{
                    "id": "M001-P1", "status_id": "7",
                    "url": "https://mastodon.social/@lectora/7",
                    "sources": ["post_search"], "actions": ["favourite", "boost"],
                }],
            }],
        }
        with self.assertRaisesRegex(ValueError, "duplicada"):
            bp.build(scan_data, {"actions": [
                {"post": "M001-P1", "kind": "favourite"},
                {"post": "M001-P1", "kind": "boost"},
            ]})

    def test_rate_limit_stops_further_reads(self):
        c = self.collector()
        c.own = "autorademodiaz"
        c.exhausted = True
        before = c.reads
        result = c.collect("post_search", "q", lambda: self.fail("no HTTP after stop"), lambda _: True)
        self.assertEqual(result, [])
        self.assertEqual(c.reads, before)

    def test_paces_instead_of_stopping_when_real_quota_is_low(self):
        # Pacing real por rate-limit (29/09): si la cuota real que reporta
        # mastodon.social esta casi agotada, el scan debe esperar hasta el
        # reset en vez de seguir pidiendo hasta un 429 real. Antes de esto,
        # solo existia el tope autoimpuesto (max_read_requests) que cortaba
        # el scan entero sin motivo real si aun quedaba cuota de verdad.
        c = self.collector()
        future_reset = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=12)
        with patch.object(
            m, "rate_limit_snapshot",
            return_value={"remaining": 2, "limit": 300, "reset": future_reset},
        ), patch("mastodon_growth_scan.time.sleep") as sleep_mock:
            c._before_request("https://mastodon.social/api/v1/example")
        self.assertTrue(sleep_mock.called)
        waited = sleep_mock.call_args[0][0]
        self.assertGreater(waited, 12)
        self.assertLess(waited, 20)
        self.assertEqual(c.reads, 1)
        self.assertTrue(any("pacing" in issue for issue in c.issues))

    def test_no_pacing_when_quota_is_healthy(self):
        c = self.collector()
        with patch.object(
            m, "rate_limit_snapshot",
            return_value={"remaining": 250, "limit": 300, "reset": dt.datetime.now(dt.timezone.utc)},
        ), patch("mastodon_growth_scan.time.sleep") as sleep_mock:
            c._before_request("https://mastodon.social/api/v1/example")
        sleep_mock.assert_not_called()

    def test_family_suffixed_surface_counts_as_covering_the_bare_requirement(self):
        # Bug real encontrado en vivo el 29/09: post_search se registra en
        # c.surfaces con sufijo de familia ("post_search:fantasia", etc via
        # collect()), nunca como el string pelado que pide required_surfaces
        # - una resta de sets directa lo marcaba siempre "missing" aunque se
        # hubiera ejecutado varias veces.
        c = self.collector()
        c.own = "autorademodiaz"
        self.assertIn("post_search", c.config["coverage"]["required_surfaces"])
        c.use_surface("post_search:fantasia")
        c.use_surface("post_search:autores")
        result = gs._build_output(c)
        self.assertNotIn("post_search", result["coverage"]["missing"])

    def test_build_output_handles_known_date_as_plain_string(self):
        # Bug real encontrado en vivo el 29/09: sc.known_accounts() (compartido
        # entre redes) devuelve el string crudo de la columna "fecha" del CSV,
        # nunca un date - _build_output llamaba .isoformat() sobre ese string y
        # reventaba con AttributeError en cualquier sesion con historial real
        # (o sea, siempre que exista al menos una cuenta conocida).
        c = self.collector()
        c.own = "autorademodiaz"
        c.known["lectora@mastodon.social"] = "2026-09-20"
        c.add_status(status("30"), "post_search", "fantasia")
        result = gs._build_output(c)
        item = result["shortlist"][0]
        self.assertEqual(item["known_date"], "2026-09-20")
        self.assertEqual(item["lane"], "community")

    def test_stream_cached_viewer_flags_are_refreshed_before_shortlist(self):
        c = self.collector()
        c.own = "autorademodiaz"
        cached = status("25")
        self.assertTrue(c.add_status(cached, "stream_cache", "test"))
        shortlist = [c.candidates["lectora@mastodon.social"]]
        with patch.object(m, "_get", return_value=[{
            "id": "25", "favourited": True, "reblogged": False,
        }]):
            gs._refresh_cached_viewer_state(c, shortlist)
        self.assertTrue(c.posts["25"]["favourited"])
        self.assertFalse(c.posts["25"]["reblogged"])


class MastodonPreflightTests(unittest.TestCase):
    def test_invalid_later_action_prevents_first_write(self):
        with patch.object(execute.m, "follow") as follow, \
             patch.object(execute, "_pause", return_value=None):
            result = execute.run_plan([
                {"kind": "follow", "handle": "lectora@mastodon.social"},
                {"kind": "reply", "handle": "lector", "url": "", "text": "Hola"},
            ])
        follow.assert_not_called()
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))


class MastodonExecutePacingTests(unittest.TestCase):
    def test_paces_before_writing_when_real_quota_is_low(self):
        future_reset = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=9)
        with patch.object(
            execute.m, "rate_limit_snapshot",
            return_value={"remaining": 1, "limit": 300, "reset": future_reset},
        ), patch.object(execute.time, "sleep") as sleep_mock:
            execute._pace_for_rate_limit()
        sleep_mock.assert_called_once()
        waited = sleep_mock.call_args[0][0]
        self.assertGreater(waited, 9)
        self.assertLess(waited, 15)

    def test_no_pacing_when_quota_is_healthy(self):
        with patch.object(
            execute.m, "rate_limit_snapshot",
            return_value={"remaining": 280, "limit": 300, "reset": dt.datetime.now(dt.timezone.utc)},
        ), patch.object(execute.time, "sleep") as sleep_mock:
            execute._pace_for_rate_limit()
        sleep_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
