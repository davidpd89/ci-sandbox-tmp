"""Threads: el shortcode permite vetar antigüedad, no demostrar publicación reciente."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import post_age_policy as pap

B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
NOW = dt.datetime.now(dt.timezone.utc)


def shortcode(when):
    value = (int(when.timestamp() * 1000) - 1314220021721) << 23
    out = ""
    while value:
        value, rest = divmod(value, 64)
        out = B64[rest] + out
    return out


def item(kind, when, **extra):
    return {"kind": kind, "permalink": f"https://www.threads.net/@alguien/post/{shortcode(when)}", **extra}


class ThreadsShortcodeTests(unittest.TestCase):
    def test_roundtrip_gives_the_embedded_instant(self):
        when = NOW - dt.timedelta(hours=5)
        decoded = pap.post_datetime("threads", item("reply", when))
        self.assertLess(abs((decoded - when).total_seconds()), 1)

    def test_recent_shortcode_is_not_proof_but_old_one_vetoes(self):
        recent = NOW - dt.timedelta(hours=5)
        self.assertEqual(pap.check("threads", item("reply", recent)),
                         (False, "edad_desconocida"))
        self.assertEqual(pap.check("threads", item("reply", NOW - dt.timedelta(days=9))),
                         (False, "post_antiguo"))
        self.assertEqual(pap.check("threads", item(
            "reply", recent, post_created_at=recent.isoformat())),
            (True, "edad_ok"))

    def test_explicit_date_wins_over_shortcode(self):
        old_code_recent_date = item("reply", NOW - dt.timedelta(days=30), post_created_at=(NOW - dt.timedelta(hours=1)).isoformat())
        self.assertEqual(pap.check("threads", old_code_recent_date), (True, "edad_ok"))

    def test_garbage_or_missing_code_is_unknown_and_text_fails_closed(self):
        for link in ("https://www.threads.net/@a/post/zz", "https://www.threads.net/@a/post/AAAAAAAAAA", "https://www.threads.net/@a"):
            allowed, reason = pap.check("threads", {"kind": "reply", "permalink": link})
            self.assertEqual((allowed, reason), (False, "edad_desconocida"))
        self.assertEqual(pap.check("threads", {"kind": "like", "permalink": "https://www.threads.net/@a"}), (True, "edad_desconocida"))


if __name__ == "__main__":
    unittest.main()
