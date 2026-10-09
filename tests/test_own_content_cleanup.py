"""own_content_cleanup.py (02/10): barrido de huella propia con mas de N dias."""
import csv
import datetime
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import own_content_cleanup as oc

TODAY = datetime.date(2026, 10, 2)
DID = "did:plc:yo"


def item(ref, kind="reply", created="2026-08-01", protected=False, text="hola"):
    return {"ref": ref, "kind": kind, "created": created, "text": text, "protected": protected}


class SelectTests(unittest.TestCase):
    def test_only_old_enough_and_selected_kinds(self):
        got = oc.select_expired([
            item("viejo"), item("reciente", created="2026-09-20"),
            item("original", kind="post"), item("cita", kind="quote"),
        ], TODAY)
        self.assertEqual([i["ref"] for i in got], ["viejo", "cita"])

    def test_boundary_day_is_deleted_and_day_after_is_kept(self):
        self.assertEqual(len(oc.select_expired([item("a", created="2026-09-02")], TODAY)), 1)
        self.assertEqual(len(oc.select_expired([item("a", created="2026-09-03")], TODAY)), 0)

    def test_protected_and_undated_never_selected(self):
        got = oc.select_expired([item("a", protected=True), item("b", created="")], TODAY)
        self.assertEqual(got, [])

    def test_posts_only_when_explicitly_requested(self):
        got = oc.select_expired([item("o", kind="post")], TODAY, kinds=("post",))
        self.assertEqual(len(got), 1)


class ClassifyTests(unittest.TestCase):
    OWN = f"at://{DID}/app.bsky.feed.post/"
    OTHER = "at://did:plc:otro/app.bsky.feed.post/"

    def rec(self, value, rkey="x"):
        return {"uri": f"at://{DID}/app.bsky.feed.post/{rkey}", "value": {"createdAt": "2026-08-01T10:00:00Z", **value}}

    def test_bluesky_reply_in_foreign_thread_is_deletable_even_as_part_two(self):
        foreign = {"reply": {"root": {"uri": self.OTHER + "1"}, "parent": {"uri": self.OTHER + "1"}}}
        self.assertEqual(oc.classify_bluesky(self.rec(foreign), DID)["protected"], False)
        part_two = {"reply": {"root": {"uri": self.OTHER + "1"}, "parent": {"uri": self.OWN + "p1"}}}
        item = oc.classify_bluesky(self.rec(part_two), DID)
        self.assertEqual((item["kind"], item["protected"]), ("reply", False))  # se va junto a la parte 1

    def test_bluesky_reply_inside_our_own_thread_is_protected_by_root(self):
        under_our_post = {"reply": {"root": {"uri": self.OWN + "orig"}, "parent": {"uri": self.OTHER + "comment"}}}
        self.assertTrue(oc.classify_bluesky(self.rec(under_our_post), DID)["protected"])

    def test_bluesky_quote_only_when_embedding_a_foreign_post(self):
        foreign = {"embed": {"$type": "app.bsky.embed.record", "record": {"uri": self.OTHER + "9"}}}
        self.assertEqual(oc.classify_bluesky(self.rec(foreign), DID)["kind"], "quote")
        with_media = {"embed": {"$type": "app.bsky.embed.recordWithMedia",
                                "record": {"record": {"uri": self.OTHER + "9"}}}}
        self.assertEqual(oc.classify_bluesky(self.rec(with_media), DID)["kind"], "quote")
        own_quote = {"embed": {"$type": "app.bsky.embed.record", "record": {"uri": self.OWN + "old"}}}
        self.assertEqual(oc.classify_bluesky(self.rec(own_quote), DID)["kind"], "post")
        starterpack = {"embed": {"$type": "app.bsky.embed.record",
                                 "record": {"uri": f"at://{DID}/app.bsky.graph.starterpack/abc"}}}
        self.assertEqual(oc.classify_bluesky(self.rec(starterpack), DID)["kind"], "post")
        self.assertEqual(oc.classify_bluesky(self.rec({"text": "x"}), DID)["kind"], "post")

    def test_bluesky_pinned_post_is_protected_whatever_its_kind(self):
        quote = {"embed": {"$type": "app.bsky.embed.record", "record": {"uri": self.OTHER + "9"}}}
        record = self.rec(quote, rkey="pin")
        self.assertTrue(oc.classify_bluesky(record, DID, pinned_uri=record["uri"])["protected"])
        self.assertFalse(oc.classify_bluesky(record, DID, pinned_uri="otro")["protected"])

    def test_mastodon_reply_boost_pinned_and_own_thread(self):
        base = {"id": "10", "created_at": "2026-08-01T10:00:00Z", "content": "<p>Hola &amp; adios</p>"}
        reply = oc.classify_mastodon({**base, "in_reply_to_id": "5", "in_reply_to_account_id": "99"}, "1")
        self.assertEqual((reply["kind"], reply["protected"], reply["text"], reply["parent_id"]),
                         ("reply", False, "Hola & adios", "5"))
        self.assertTrue(oc.classify_mastodon({**base, "in_reply_to_id": "5", "in_reply_to_account_id": "1"}, "1")["protected"])
        boost = oc.classify_mastodon({**base, "reblog": {"id": "777", "url": "https://x/1"}}, "1")
        self.assertEqual((boost["kind"], boost["ref"]), ("repost", "777"))
        self.assertTrue(oc.classify_mastodon({**base, "pinned": True}, "1")["protected"])
        pinned_reply = oc.classify_mastodon({**base, "pinned": True, "in_reply_to_id": "5",
                                             "in_reply_to_account_id": "99"}, "1")
        self.assertTrue(pinned_reply["protected"])  # fijado gana aunque sea una reply ajena


class VerifyTests(unittest.TestCase):
    def test_verify_filters_due_items_before_counting_or_deleting(self):
        calls = []
        adapter = {"list": lambda: [item("a", created="2026-07-01"), item("b", created="2026-07-02")],
                   "delete": lambda it: calls.append(it["ref"]),
                   "verify": lambda it: it["ref"] != "a"}
        res = oc.run(adapter, today=TODAY, apply=True, out=lambda *_: None)
        self.assertEqual((calls, res["due"]), (["b"], 1))


class RunTests(unittest.TestCase):
    def adapter(self, items, fail=None):
        calls = []

        def delete(it):
            if fail and it["ref"] == fail[0]:
                raise fail[1]
            calls.append(it["ref"])
        return {"list": lambda: items, "delete": delete}, calls

    def test_dry_run_deletes_nothing(self):
        ad, calls = self.adapter([item("a")])
        res = oc.run(ad, today=TODAY, out=lambda *_: None)
        self.assertEqual((calls, res["deleted"]), ([], 0))

    def test_apply_deletes_logs_and_respects_limit(self):
        ad, calls = self.adapter([item("a", created="2026-07-01"), item("b"), item("c")])
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log.csv")
            res = oc.run(ad, today=TODAY, apply=True, limit=2, log_path=log, out=lambda *_: None)
            with open(log, encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(calls, ["a", "b"])
        self.assertEqual((res["deleted"], [r["ref"] for r in rows]), (2, ["a", "b"]))

    def test_rate_limit_stops_batch_and_other_errors_continue(self):
        ad, calls = self.adapter([item("a", created="2026-07-01"), item("b"), item("c", created="2026-08-02")],
                                 fail=("b", oc.StopBatch("429")))
        res = oc.run(ad, today=TODAY, apply=True, out=lambda *_: None)
        self.assertEqual((calls, res["stopped"]), (["a"], True))
        ad, calls = self.adapter([item("a", created="2026-07-01"), item("b")], fail=("a", ValueError("x")))
        res = oc.run(ad, today=TODAY, apply=True, out=lambda *_: None)
        self.assertEqual((calls, res["failed"], res["deleted"]), (["b"], 1, 1))


if __name__ == "__main__":
    unittest.main()
