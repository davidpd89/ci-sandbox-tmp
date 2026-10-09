"""Regresión: votar un hilo no significa que se haya comentado."""
import csv
import importlib
import pathlib
import sys
import tempfile
import types
import unittest
import urllib.parse
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

fake_reddit = types.ModuleType("reddit_interact")


def _fake_thread_identity(url):
    parts = urllib.parse.urlsplit(url).path.strip("/").split("/")
    if len(parts) < 4 or parts[0].casefold() != "r" or parts[2].casefold() != "comments":
        raise ValueError("invalid thread")
    return parts[1].casefold(), parts[3].casefold()


fake_reddit._thread_identity = _fake_thread_identity
with patch.dict(sys.modules, {"reddit_interact": fake_reddit}):
    reddit_scan = importlib.import_module("reddit_scan")


class RedditVoteDoesNotCountAsCommentTests(unittest.TestCase):
    def test_votes_not_labelled_already_commented(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "registro.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                w = csv.writer(stream)
                w.writerow(["fecha", "subreddit", "hilo_url", "tipo", "texto_usado", "resultado", "notas"])
                w.writerow(["2026-09-24", "r/libros", "https://www.reddit.com/r/libros/comments/a/", "voto_positivo", "", "confirmado", ""])
                w.writerow(["2026-09-24", "r/libros", "https://www.reddit.com/r/libros/comments/b/titulo-viejo/", "comentario", "Hola", "confirmado", ""])
                w.writerow(["2026-09-24", "r/libros", "https://reddit.com/r/libros/comments/c/slug-viejo/", "comentario", "Quizá salió", "", ""])
                w.writerow(["2026-09-24", "r/libros", "https://www.reddit.com/not-a-thread", "comentario", "Rota", "confirmado", ""])
            with patch.object(reddit_scan, "REGISTRO_CSV", str(path)):
                known = reddit_scan._known_threads()
                uncertain = reddit_scan._uncertain_threads()
        self.assertNotIn(("libros", "a"), known)
        self.assertIn(("libros", "b"), known)
        self.assertNotIn(("libros", "c"), known)
        self.assertIn(("libros", "c"), uncertain)
        self.assertNotIn(("libros", "not-a-thread"), known)

    def test_slug_or_host_variant_maps_to_same_history_identity(self):
        self.assertEqual(
            reddit_scan._thread_key(
                "https://www.reddit.com/r/libros/comments/abc123/titulo-viejo/"
            ),
            reddit_scan._thread_key(
                "https://reddit.com/r/libros/comments/ABC123/titulo-nuevo/"
            ),
        )


if __name__ == "__main__":
    unittest.main()
