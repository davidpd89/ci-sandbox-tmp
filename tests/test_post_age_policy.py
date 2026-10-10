"""Anti-necroposting comun (09/10/2026): un unico criterio de antiguedad para las nueve redes."""
import datetime as dt
import pathlib
import re
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import conversation_turn_policy as ctp
import post_age_policy as pap

NOW = dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.timezone.utc)
_B32 = "234567abcdefghijklmnopqrstuvwxyz"


def mastodon_id(when):
    return str(int(when.timestamp() * 1000) << 16)


def x_id(when):
    return str((int(when.timestamp() * 1000) - 1288834974657) << 22)


def tid(when):
    value = int(when.timestamp() * 1_000_000) << 10
    return "".join(_B32[(value >> (5 * i)) & 31] for i in reversed(range(13)))


def ago(days):
    return NOW - dt.timedelta(days=days)


class PerNetworkAgeTests(unittest.TestCase):
    def test_mastodon_opaque_id_never_certifies_post_age(self):
        item = {"kind": "reply", "status_id": mastodon_id(ago(1))}
        self.assertEqual(pap.check("mastodon", item, now=NOW), (False, "edad_desconocida"))
        item["post_created_at"] = ago(10).isoformat()
        self.assertEqual(pap.check("mastodon", item, now=NOW), (False, "post_antiguo"))
        item["post_created_at"] = ago(1).isoformat()
        self.assertEqual(pap.check("mastodon", item, now=NOW), (True, "edad_ok"))

    def test_x_snowflake_from_url(self):
        item = {"kind": "reply", "url": f"https://x.com/alguien/status/{x_id(ago(30))}"}
        self.assertEqual(pap.check("x", item, now=NOW), (False, "post_antiguo"))
        item["url"] = f"https://x.com/alguien/status/{x_id(ago(0.5))}"
        self.assertTrue(pap.check("x", item, now=NOW)[0])

    def test_bluesky_tid_from_at_uri(self):
        item = {"kind": "reply", "_target_uri": f"at://did:plc:abc/app.bsky.feed.post/{tid(ago(20))}"}
        self.assertEqual(pap.check("bluesky", item, now=NOW), (False, "post_antiguo"))
        item["_target_uri"] = f"at://did:plc:abc/app.bsky.feed.post/{tid(ago(0.2))}"
        # El TID puede ser elegido por el cliente: no certifica la fecha del post.
        self.assertEqual(pap.check("bluesky", item, now=NOW),
                         (False, "edad_desconocida"))
        item["post_created_at"] = ago(0.2).isoformat()
        self.assertEqual(pap.check("bluesky", item, now=NOW), (True, "edad_ok"))

    def test_explicit_date_works_for_any_network(self):
        for network in ("threads", "facebook", "pinterest", "reddit", "tiktok", "instagram"):
            old = {"kind": "comment", "post_created_at": ago(9).isoformat()}
            self.assertEqual(pap.check(network, old, now=NOW), (False, "post_antiguo"), network)
            new = {"kind": "comment", "post_created_at": ago(1).isoformat()}
            self.assertTrue(pap.check(network, new, now=NOW)[0], network)

    def test_unknown_age_text_is_blocked_but_likes_remain_compatible(self):
        for kind in ("reply", "comment", "comment_external", "quote"):
            self.assertEqual(pap.check("threads", {"kind": kind, "url": "https://threads.com/x"}, now=NOW), (False, "edad_desconocida"))
        self.assertEqual(pap.check("threads", {"kind": "like"}, now=NOW), (True, "edad_desconocida"))

    def test_queued_action_created_at_is_not_target_date(self):
        item = {"kind": "reply", "created_at": ago(0.1).isoformat(),
                "url": "https://example.test/ancient"}
        self.assertEqual(pap.check("threads", item, now=NOW),
                         (False, "edad_desconocida"))
        item["post_created_at"] = ago(9).isoformat()
        self.assertEqual(pap.check("threads", item, now=NOW),
                         (False, "post_antiguo"))

    def test_kind_limits(self):
        base = {"post_created_at": ago(10).isoformat()}
        self.assertFalse(pap.check("x", {**base, "kind": "reply"}, now=NOW)[0])
        self.assertFalse(pap.check("x", {**base, "kind": "boost"}, now=NOW)[0])
        self.assertTrue(pap.check("x", {**base, "kind": "like"}, now=NOW)[0])
        self.assertTrue(pap.check("x", {**base, "kind": "follow"}, now=NOW)[0])

    def test_followup_gets_a_longer_window(self):
        item = {"kind": "reply", "post_created_at": ago(5).isoformat(), "motivo": "fidelizacion:contestar_a_su_comentario"}
        self.assertTrue(pap.check("mastodon", item, now=NOW)[0])
        item["post_created_at"] = ago(9).isoformat()
        self.assertFalse(pap.check("mastodon", item, now=NOW)[0])

    def test_garbage_never_raises(self):
        for item in ({}, {"kind": None}, {"kind": "follow"}):
            self.assertTrue(pap.check("mastodon", item, now=NOW)[0])
        for item in ({"kind": "reply", "post_created_at": "no-fecha"},
                     {"kind": "reply", "status_id": "9" * 30}):
            self.assertEqual(pap.check("mastodon", item, now=NOW),
                             (False, "edad_desconocida"))


class SharedChokePointTests(unittest.TestCase):
    def test_turn_policy_applies_it_to_every_network(self):
        old = {"kind": "reply", "text": "hola", "post_created_at": "2020-01-01T00:00:00+00:00"}
        for network in ("bluesky", "mastodon", "x", "threads", "facebook", "pinterest", "reddit", "tiktok"):
            self.assertEqual(ctp.check_execution(network, dict(old)), (False, "post_antiguo"), network)

    def test_every_executor_calls_the_shared_policy_before_acting(self):
        # Si un ejecutor nuevo no llama a check_execution, el tope de edad no le aplica: este test lo detecta.
        for name in ("x", "threads", "facebook", "bluesky", "mastodon", "reddit", "tiktok_mobile", "instagram"):
            source = (TOOLS / f"{name}_execute.py").read_text(encoding="utf-8")
            self.assertRegex(source, r"ctp\.check_execution\(", name)
        pinterest = (TOOLS / "pinterest_growth.py").read_text(encoding="utf-8")
        self.assertIn('ctp.check_execution("pinterest", item)', pinterest)
        reddit_secondary = (TOOLS / "reddit_comments.py").read_text(encoding="utf-8")
        self.assertIn('ctp.check_execution("reddit", extra)', reddit_secondary)


if __name__ == "__main__":
    unittest.main()
