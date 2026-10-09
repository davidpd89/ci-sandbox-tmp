import datetime
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import x_bank_publish as xb

NOW = datetime.datetime(2026, 10, 10, 13, 30)
BANK = [{"id": "a", "text": "¿Uno?"}, {"id": "b", "text": "¿Dos?"}]


class ChooseTests(unittest.TestCase):
    def test_one_per_day(self):
        log = [{"id": "a", "when": datetime.datetime(2026, 10, 10, 9, 0)}]
        item, why = xb.choose(BANK, log, now=NOW, rng=random.Random(1))
        self.assertIsNone(item)
        self.assertIn("hoy", why)

    def test_min_gap_with_other_automatic_post(self):
        item, why = xb.choose(BANK, [], now=NOW, last_other_post=datetime.datetime(2026, 10, 10, 10, 0))
        self.assertIsNone(item)
        self.assertIn("minimo", why)
        item, _ = xb.choose(BANK, [], now=NOW, last_other_post=datetime.datetime(2026, 10, 10, 6, 0), rng=random.Random(1))
        self.assertIsNotNone(item)

    def test_never_repeats(self):
        log = [{"id": "a", "when": datetime.datetime(2026, 10, 8, 13, 0)}]
        item, _ = xb.choose(BANK, log, now=NOW, rng=random.Random(3))
        self.assertEqual(item["id"], "b")
        log.append({"id": "b", "when": datetime.datetime(2026, 10, 9, 13, 0)})
        item, why = xb.choose(BANK, log, now=NOW)
        self.assertIsNone(item)
        self.assertIn("agotado", why)

    def test_record_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "posts.csv")
            xb.record({"id": "a", "text": "¿Uno?"}, "https://x.com/u/status/1", now=NOW, path=path)
            rows = xb.read_log(path)
            self.assertEqual([r["id"] for r in rows], ["a"])
            self.assertEqual(rows[0]["when"], NOW.replace(second=0))


class RealBankTests(unittest.TestCase):
    def test_bank_is_clean(self):
        bank = xb.load_bank()
        self.assertGreaterEqual(len(bank), 25)
        ids = [i["id"] for i in bank]
        self.assertEqual(len(ids), len(set(ids)))
        for item in bank:
            self.assertLessEqual(len(item["text"]), 270)
            self.assertNotIn("http", item["text"])
            self.assertNotIn("#", item["text"])
            self.assertNotIn("Samuel", item["text"])

    def test_bank_passes_spanish_orthography_check(self):
        import x_interact as x
        for item in xb.load_bank():
            x._check_spanish_orthography(item["text"])
            x._check_length(item["text"])


if __name__ == "__main__":
    unittest.main()
