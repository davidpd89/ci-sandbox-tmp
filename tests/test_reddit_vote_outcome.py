"""El ejecutor Reddit no convierte un voto ya existente o incierto en éxito."""
import importlib
import datetime as dt
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

fake = types.ModuleType("reddit_interact")
fake.BotWarningDetected = type("BotWarningDetected", (RuntimeError,), {})
fake.AlreadyCommented = type("AlreadyCommented", (RuntimeError,), {})
fake.comment = lambda *a, **k: None
fake.vote = lambda *a, **k: "already"
fake._check_length = lambda text: None
fake._check_micro_comment = lambda text: None
fake._check_spanish_orthography = lambda text: None
fake._thread_identity = lambda url: ("libros", "abc")
fake._normalize_subreddit_name = lambda value: (
    value[3:] if value.startswith("/r/") else value[2:] if value.startswith("r/") else value
)

# Cargar bajo nombre único: otro test puede importar el ejecutor real durante
# pytest collection; import_module devolvería ese módulo ya cacheado.
spec = importlib.util.spec_from_file_location(
    "_reddit_execute_vote_fixture", pathlib.Path(__file__).resolve().parents[1] / "tools" / "reddit_execute.py"
)
ex = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"reddit_interact": fake}):
    spec.loader.exec_module(ex)


class RedditVoteOutcomeTests(unittest.TestCase):
    def test_existing_vote_is_skipped_not_confirmed(self):
        plan = [{"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
                 "subreddit": "libros", "direction": "up"}]
        with patch.object(ex, "_pause", return_value=None):
            result = ex.run_plan(plan)
        self.assertEqual(result[0]["resultado"], "saltado_ya_votado")

    def test_subreddit_metadata_mismatch_blocks_before_vote(self):
        plan = [{"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
                 "subreddit": "escribir", "direction": "up"}]
        with patch.object(ex.r, "vote") as vote, \
             patch.object(ex, "_pause", return_value=None):
            result = ex.run_plan(plan)
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))
        vote.assert_not_called()

    def test_missing_subreddit_is_derived_from_validated_url(self):
        plan = [{"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
                 "direction": "up"}]
        with patch.object(ex.r, "vote", return_value="already"), \
             patch.object(ex, "_pause", return_value=None):
            result = ex.run_plan(plan)
        self.assertEqual(result[0]["subreddit"], "libros")
        self.assertEqual(result[0]["resultado"], "saltado_ya_votado")

    def test_invalid_later_item_blocks_entire_plan_before_first_write(self):
        plan = [
            {"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
             "subreddit": "libros", "direction": "up"},
            {"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
             "subreddit": "escribir", "direction": "up"},
        ]
        with patch.object(ex.r, "vote") as vote, \
             patch.object(ex, "_pause", return_value=None):
            result = ex.run_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))
        vote.assert_not_called()

    def test_duplicate_votes_on_same_thread_are_rejected_before_writes(self):
        plan = [
            {"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
             "subreddit": "libros", "direction": "up"},
            {"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/otro/",
             "subreddit": "libros", "direction": "down"},
        ]
        with patch.object(ex.r, "vote") as vote:
            result = ex.run_plan(plan)
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))
        vote.assert_not_called()

    def test_repeated_comment_text_across_subreddits_omits_second_comment(self):
        recent = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat()
        plan = [
            {"kind": "comment", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
             "subreddit": "libros", "text": "Una observación útil.", "post_created_at": recent},
            {"kind": "comment", "url": "https://www.reddit.com/r/escribir/comments/def/t/",
             "subreddit": "escribir", "text": "  una   OBSERVACIÓN útil.  ", "post_created_at": recent},
        ]

        def identity(url):
            return ("escribir", "def") if "/r/escribir/" in url else ("libros", "abc")

        with patch.object(ex.r, "_thread_identity", side_effect=identity), \
             patch.object(ex, "_recent_micro_repeat", return_value=False), \
             patch.object(ex.sc, "guard_plan_item"), \
             patch.object(ex.r, "comment") as comment, \
             patch.object(ex, "_pause", return_value=None):
            result = ex.run_plan(plan)

        self.assertEqual([x["resultado"] for x in result],
                         ["saltado_preflight_texto_repetido_lote", "confirmado"])
        comment.assert_called_once()

    def test_recent_microtext_in_later_comment_does_not_block_valid_vote(self):
        plan = [
            {"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
             "subreddit": "libros", "direction": "up"},
            {"kind": "comment", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
             "subreddit": "libros", "text": "texto repetido"},
        ]
        with patch.object(ex, "_recent_micro_repeat", return_value=True), \
             patch.object(ex.r, "vote", return_value="created") as vote, \
             patch.object(ex.r, "comment") as comment, \
             patch.object(ex.sc, "guard_plan_item"), \
             patch.object(ex, "_pause", return_value=None):
            result = ex.run_plan(plan)
        self.assertEqual([x["resultado"] for x in result],
                         ["saltado_preflight_microtexto_publicado", "confirmado"])
        vote.assert_called_once()
        comment.assert_not_called()

    def test_local_comment_validation_in_later_item_blocks_first_write(self):
        plan = [
            {"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
             "subreddit": "libros", "direction": "up"},
            {"kind": "comment", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
             "subreddit": "libros", "text": "texto con posible error"},
        ]
        with patch.object(ex.dup, "check", return_value=[]), \
             patch.object(ex.r, "_check_spanish_orthography",
                          side_effect=ValueError("posible tilde perdida")), \
             patch.object(ex.r, "vote") as vote:
            result = ex.run_plan(plan)
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))
        vote.assert_not_called()

    def test_missing_vote_confirmation_becomes_failure(self):
        plan = [{"kind": "vote", "url": "https://www.reddit.com/r/libros/comments/abc/t/",
                 "subreddit": "libros", "direction": "up"}]
        with patch.object(ex.r, "vote", return_value=None), \
             patch.object(ex, "_pause", return_value=None):
            result = ex.run_plan(plan)
        self.assertTrue(result[0]["resultado"].startswith("fallo:"))


if __name__ == "__main__":
    unittest.main()
