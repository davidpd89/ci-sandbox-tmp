import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import threads_build_plan as plan
import threads_pool as pool


class ThreadsRepliesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pool.connect(os.path.join(self.tmp.name, "pool.sqlite3"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_reply_by_intent_from_pool(self):
        pool.record_posts(self.db, [("lectora_ana", "https://www.threads.com/@lectora_ana/post/AAA1", "lectora_ana\n1 h\nAcabo de terminar esta novela de fantasía y me ha encantado, qué lectura", "search:t"),
                                    ("otra_cuenta", "https://www.threads.com/@otra_cuenta/post/BBB2", "otra_cuenta\n1 h\nBuenos días a todos", "search:t")])
        registro = os.path.join(self.tmp.name, "registro.csv")
        replies = plan.build_replies(self.db, 3, registro, rng=random.Random(1))
        self.assertEqual(len(replies), 1)
        item = replies[0]
        self.assertEqual((item["kind"], item["handle"], item["bank"]), ("reply", "lectora_ana", True))
        self.assertTrue(item["text_fragment"] and item["text"])
        self.assertIn("finished_book", item["motivo"])


if __name__ == "__main__":
    unittest.main()
