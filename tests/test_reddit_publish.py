import datetime
import json
import os
import random
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import reddit_publish as rp

TODAY = datetime.date(2026, 10, 10)
BANK = [
    {"id": "a", "sub": "libros", "flair": "Discusión", "title": "¿Uno?", "body": ""},
    {"id": "b", "sub": "LectoresArg", "flair": "pregunta", "title": "¿Dos?", "body": ""},
    {"id": "c", "sub": "preguntaleareddit", "flair": "x", "title": "¿Tres?", "body": ""},
]


class ChooseTests(unittest.TestCase):
    def test_only_post_eligible_communities(self):
        item, _ = rp.choose(BANK, [], today=TODAY, rng=random.Random(1), allowed={"lectoresarg"})
        self.assertEqual(item["id"], "b")

    def test_commenting_community_never_chosen(self):
        for seed in range(20):
            item, _ = rp.choose(BANK, [], today=TODAY, rng=random.Random(seed), allowed={"preguntaleareddit", "lectoresarg"})
            self.assertNotEqual(item["sub"], "libros")

    def test_no_eligible_community(self):
        item, why = rp.choose(BANK, [], today=TODAY, allowed=set())
        self.assertIsNone(item)
        self.assertIn("ninguna", why)

    def test_without_state_file_everything_allowed(self):
        item, _ = rp.choose(BANK[:1], [], today=TODAY)
        self.assertEqual(item["id"], "a")


class StatesFileTests(unittest.TestCase):
    def test_eligible_subs_reads_post_eligible_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "estados.json")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump({"_leyenda": "x", "libros": {"state": "COMMENTING"}, "LectoresArg": {"state": "POST_ELIGIBLE"}}, stream)
            self.assertEqual(rp.eligible_subs(path), {"lectoresarg"})
            # Fichero de estados ausente nunca concede permiso universal:
            # antes None desactivaba el filtro de POST_ELIGIBLE.
            self.assertEqual(rp.eligible_subs(os.path.join(tmp, "no_existe.json")), set())

    def test_real_bank_and_states_are_consistent(self):
        bank = rp.load_bank()
        states = rp.eligible_subs()
        self.assertTrue(states)
        ids = [q["id"] for q in bank]
        self.assertEqual(len(ids), len(set(ids)))
        for q in bank:
            self.assertIn("¿", q["title"]) if q["sub"] in ("preguntaleareddit", "RedditPregunta") else None
            self.assertNotIn("sexo", q["title"].lower())
        self.assertTrue({q["sub"].casefold() for q in bank} & states)
        self.assertNotIn("rolenespanol", states)



class StateIntegrityTests(unittest.TestCase):
    def test_unreadable_csv_must_not_look_empty(self):
        with mock.patch("builtins.open", side_effect=PermissionError("CSV abierto en Excel")):
            with self.assertRaises(rp.RedditPublishError):
                rp.read_log("preguntas.csv")

    def test_corrupt_csv_row_or_header_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "preguntas.csv")
            for content in ("fecha,id,sub\\n2026-10-08,p1,libros\\n", "fecha,id,sub\\nfecha_mala,p1,libros\\n",
                            "fecha,id,sub\\n2026-10-08,p1\\n", "fecha,id\\n2026-10-08,p1\\n"):
                with open(path, "w", encoding="utf-8") as stream:
                    stream.write(content.replace("\\n", "\n"))
                if content.startswith("fecha,id,sub") and "2026-10-08,p1,libros" in content:
                    self.assertEqual(rp.read_log(path)[0]["id"], "p1")
                else:
                    with self.assertRaises(rp.RedditPublishError):
                        rp.read_log(path)

    def test_permalink_must_identify_same_subreddit(self):
        self.assertTrue(rp._valid_permalink("https://www.reddit.com/r/libros/comments/a1b2c3/titulo/", "libros"))
        self.assertFalse(rp._valid_permalink("https://www.reddit.com/r/escritura/comments/a1b2c3/", "libros"))
        self.assertFalse(rp._valid_permalink("https://example.com/r/libros/comments/a1b2c3/", "libros"))
        self.assertFalse(rp._valid_permalink("https://www.reddit.com/r/libros/123/", "libros"))
        self.assertFalse(rp._valid_permalink(None, "libros"))

    def test_missing_csv_is_allowed_only_when_really_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(rp.read_log(os.path.join(tmp, "no.csv")), [])

    def test_blocked_file_corrupt_or_invalid_schema_aborts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "blocked.json")
            for content in ('{"libros":', '["libros"]', '{"libros": null}'):
                with open(path, "w", encoding="utf-8") as stream:
                    stream.write(content)
                with self.assertRaises(rp.RedditPublishError):
                    rp.read_blocked(path)

    def test_blocked_write_failed_replace_keeps_previous_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "blocked.json")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump({"libros": "filtrado"}, stream)
            with mock.patch.object(rp.os, "replace", side_effect=PermissionError("sin permiso")):
                with self.assertRaises(PermissionError):
                    rp.write_blocked({"nueva": "filtrado"}, path)
            self.assertEqual(rp.read_blocked(path), {"libros": "filtrado"})

    def test_newest_removed_post_wins_over_older_approved_one(self):
        posts = [
            {"sub": "libros", "title": "nuevo", "removed": "automod_filtered", "created": 990},
            {"sub": "libros", "title": "viejo", "removed": None, "created": 900},
        ]
        for ordering in (posts, list(reversed(posts))):
            result = rp.refresh_blocked(ordering, {"nuevo", "viejo"}, {}, now=1000)
            self.assertIn("libros", result)
            self.assertIn("automod_filtered", result["libros"])
        # Una aprobación de otra pregunta NO libera una retirada sin resolver.
        posts[0]["removed"] = None
        posts[1]["removed"] = "automod_filtered"
        self.assertIn("libros", rp.refresh_blocked(posts, {"nuevo", "viejo"},
                                                 {"libros": "bloqueado"}, now=1000))
        # Al aprobarse también la pregunta retirada, ya no queda ninguna.
        posts[1]["removed"] = None
        self.assertNotIn("libros", rp.refresh_blocked(posts, {"nuevo", "viejo"},
                                                    {"libros": "bloqueado"}, now=1000))


if __name__ == "__main__":
    unittest.main()
