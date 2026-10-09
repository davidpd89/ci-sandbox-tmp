"""Reddit solo microrrespuestas y preguntas de respuesta corta (03/10)."""
import pathlib
import subprocess
import sys
import unittest

TOOLS = str(pathlib.Path(__file__).resolve().parents[1] / "tools")


def run_clean(code):
    proc = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {TOOLS!r})\n" + code],
                          capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, proc.stdout + proc.stderr


class MicroCommentTests(unittest.TestCase):
    def test_valid_micro_answers(self):
        code = ("import reddit_interact as r\n"
                "for t in ('Escribir.', 'Machado, Lorca, Miguel Hernández', 'Ganas de más.', 'Sí'):\n"
                "    r._check_micro_comment(t)\nprint('OK')\n")
        rc, out = run_clean(code)
        self.assertEqual(rc, 0, out)
        self.assertIn("OK", out)

    def test_rejects_long_justified_questions_links_and_multiline(self):
        code = ("import reddit_interact as r\n"
                "bad = ['Escribir porque me ayuda a entender mejor el mundo que me rodea', 'Escribir, ¿y tú?',\n"
                "       'Mira autorademodiaz.com', 'Uno' + chr(10) + 'dos', '', 'x' * 70, 'a b c d e f g h i']\n"
                "for t in bad:\n"
                "    try:\n        r._check_micro_comment(t)\n        print('PASO', repr(t))\n"
                "    except ValueError:\n        pass\nprint('FIN')\n")
        rc, out = run_clean(code)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("PASO", out)
        self.assertIn("FIN", out)

    def test_executor_preflight_blocks_long_comment(self):
        code = ("import reddit_execute as ex\n"
                "plan = [{'kind': 'comment', 'url': 'https://www.reddit.com/r/libros/comments/1abc23/titulo/',\n"
                "         'subreddit': 'libros', 'text': 'Escribir porque me ayuda mucho a entender mejor el mundo que me rodea'}]\n"
                "try:\n    ex._preflight_plan(plan)\nexcept ValueError as exc:\n    print('BLOQUEADO', exc)\n")
        rc, out = run_clean(code)
        self.assertEqual(rc, 0, out)
        self.assertIn("BLOQUEADO", out)


class ScopeTests(unittest.TestCase):
    def test_only_short_answer_question_threads_are_candidates(self):
        code = ("import reddit_scan as s\n"
                "yes = ['¿Cuáles son tus tres poetas españoles favoritos?', 'Cuál es para ti el sentido de la vida',\n"
                "       'Acabo de ver Eyes Wide Shut, alguna interpretación del final??']\n"
                "no = ['Os dejo mi relato, ¿qué os parece mi historia?', 'Foto de mi estantería', 'Reseña de 1984 de Orwell']\n"
                "assert all(s.is_short_answer_thread(t) for t in yes), [t for t in yes if not s.is_short_answer_thread(t)]\n"
                "assert not any(s.is_short_answer_thread(t) for t in no), [t for t in no if s.is_short_answer_thread(t)]\n"
                "assert s.SUBREDDITS == ['libros', 'filosofia_en_espanol']\nprint('OK')\n")
        rc, out = run_clean(code)
        self.assertEqual(rc, 0, out)
        self.assertIn("OK", out)




class MicroDuplicateTests(unittest.TestCase):
    def test_micro_answer_not_blocked_by_cross_network_substring_but_not_repeated_back_to_back(self):
        code = (
            "import csv, os, tempfile\n"
            "import reddit_execute as ex\n"
            "tmp = os.path.join(tempfile.mkdtemp(), 'reg.csv')\n"
            "with open(tmp, 'w', newline='', encoding='utf-8') as f:\n"
            "    w = csv.writer(f); w.writerow(['fecha','cuenta','tipo','post_resumen','texto_usado','resultado','notas'])\n"
            "    for t in ['Escribir.', 'Ganas de más.', 'Sí']:\n"
            "        w.writerow(['2026-10-03','r/libros','comentario','','"+"'+t+'"+"','publicado',''])\n"
            "assert ex._recent_micro_repeat('escribir', registro=tmp)\n"
            "assert ex._recent_micro_repeat('Sí', registro=tmp)\n"
            "assert not ex._recent_micro_repeat('Poesía', registro=tmp)\n"
            "assert not ex._recent_micro_repeat('Escribir', registro=os.path.join(os.path.dirname(tmp), 'nada.csv'))\n"
            "print('OK')\n"
        )
        rc, out = run_clean(code)
        self.assertEqual(rc, 0, out)
        self.assertIn("OK", out)


class MechanicalDryTests(unittest.TestCase):
    def test_dry_run_skips_the_like_step(self):
        code = (
            "import tempfile, mechanical_round as mr\n"
            "calls = []\n"
            "def runner(cmd):\n    calls.append(' '.join(cmd))\n    return 0, '{\"actions\": 3}'\n"
            "mr.ROOT = tempfile.mkdtemp()\n"
            "mr.LOCK_DIR = mr.ROOT\n"
            "mr.run('bluesky', dry=True, runner=runner, out=lambda *_: None)\n"
            "assert not any('--like' in c for c in calls), calls\n"
            "mr.run('bluesky', dry=False, runner=runner, out=lambda *_: None)\n"
            "assert any('--like' in c for c in calls), calls\n"
            "print('OK')\n"
        )
        rc, out = run_clean(code)
        self.assertEqual(rc, 0, out)
        self.assertIn("OK", out)


if __name__ == "__main__":
    unittest.main()
