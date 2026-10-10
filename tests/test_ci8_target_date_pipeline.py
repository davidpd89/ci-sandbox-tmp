"""CI #8: conservar la fecha original hasta la política común, con datos sintéticos.

Esta prueba complementa la política ya presente en la base operativa. No
importa ejecutores ni llama API/red, no duplica la implementación de #169/#177.
"""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import bluesky_build_plan as bluesky
import mastodon_build_plan as mastodon
import threads_build_plan as threads
import tiktok_build_plan as tiktok
import post_age_policy as age

NOW = dt.datetime(2026, 10, 10, 12, tzinfo=dt.timezone.utc)


def posted(days):
    return (NOW - dt.timedelta(days=days)).isoformat()


def bluesky_item(timestamp):
    post = {"id": "G001-P1",
            "url": "https://bsky.app/profile/lectora.bsky.social/post/abc",
            "uri": "at://did:plc:lectora/app.bsky.feed.post/abc",
            "text": "Estoy leyendo una novela de fantasía",
            "created_at": timestamp, "actions": ["reply"]}
    scan = {"auto_plan": [], "shortlist": [
        {"id": "G001", "handle": "lectora.bsky.social", "lane": "acquisition",
         "sources": ["post_search"], "posts": [post]}]}
    return bluesky.build(scan, {"actions": [
        {"post": "G001-P1", "kind": "reply", "text": "Me interesa esa lectura."}]})[0]


def mastodon_item(timestamp):
    post = {"id": "M001-P1",
            "url": "https://mastodon.social/@lectora/1234",
            "status_id": "1234", "text": "Estoy leyendo fantasía",
            "created_at": timestamp, "actions": ["reply"], "sources": ["search"]}
    scan = {"shortlist": [
        {"id": "M001", "acct": "lectora@mastodon.social",
         "lane": "acquisition", "first_source": "search",
         "sources": ["search"], "posts": [post]}]}
    return mastodon.build(scan, {"actions": [
        {"post": "M001-P1", "kind": "reply", "text": "Me interesa esa lectura."}]})[0]


def tiktok_item(timestamp):
    post = {"id": "T001-P1",
            "url": "https://www.tiktok.com/@lectora/video/1234",
            "caption": "Reseña de fantasía", "source": "video_search",
            "created_at": timestamp, "actions": ["comment"]}
    scan = {"auto_plan": [], "shortlist": [
        {"id": "T001", "handle": "lectora",
         "sources": ["video_search"], "actions": [], "posts": [post]}]}
    return tiktok.build(scan, {"actions": [
        {"post": "T001-P1", "kind": "comment", "text": "Me interesa esa lectura."}]})[0]


class TargetPublicationProvenanceContract(unittest.TestCase):
    def test_api_and_mobile_builders_preserve_and_check_same_post_date(self):
        for network, builder, kind in (
            ("bluesky", bluesky_item, "reply"),
            ("mastodon", mastodon_item, "reply"),
            ("tiktok", tiktok_item, "comment"),
        ):
            for days, permitted, verdict in (
                (1, True, "edad_ok"),
                (10, False, "post_antiguo"),
                (None, False, "edad_desconocida"),
            ):
                with self.subTest(network=network, days=days):
                    value = posted(days) if days is not None else ""
                    row = builder(value)
                    self.assertEqual(row["kind"], kind)
                    self.assertEqual(row["post_created_at"], value)
                    self.assertEqual(age.check(network, row, now=NOW),
                                     (permitted, verdict))

    def test_threads_scan_explicit_date_survives_builder(self):
        candidate = {"handle": "lectora", "text": "Libros de fantasía y novelas",
                     "source": "book_search", "created_time": posted(35)}
        items = threads.build([candidate], max_follows=0)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_created_at"], posted(35))
        self.assertEqual(age.check("threads", items[0], now=NOW),
                         (False, "post_antiguo"))

    def test_threads_missing_date_is_not_replaced_by_scan_timestamp(self):
        candidate = {"handle": "lectora", "text": "Libros de fantasía y novelas",
                     "source": "book_search", "first_seen": posted(0.1)}
        items = threads.build([candidate], max_follows=0)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_created_at"], "")
        self.assertEqual(age.check("threads", items[0], now=NOW),
                         (True, "edad_desconocida"))


if __name__ == "__main__":
    unittest.main()
