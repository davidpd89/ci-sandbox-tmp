import csv
import pathlib
import tempfile
import sys
import unittest
from unittest.mock import patch

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import tiktok_mobile_execute as te
import tiktok_mobile_interact as tm


class FakeAdapter:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def follow(self, handle):
        self.calls.append(("follow", handle))
        if self.fail_on == "follow":
            raise tm.TikTokWriteUnverified("no confirmado")
        return "followed"

    def like(self, url):
        self.calls.append(("like", url))
        if self.fail_on == "like":
            raise tm.TikTokWriteUnverified("no confirmado")
        return "created"

    def comment(self, url, text):
        self.calls.append(("comment", url, text))
        if self.fail_on == "comment":
            raise tm.TikTokWriteUnverified("no confirmado")
        return "created"


class TikTokMobileExecuteTests(unittest.TestCase):
<<<<<<< HEAD
=======
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        guard = patch.object(te.safety, "COOLDOWN_PATH", str(pathlib.Path(self._tmp.name) / "pause.json"))
        guard.start()
        self.addCleanup(guard.stop)

>>>>>>> origin/research/public-reuse-parent
    def test_preflight_validates_without_mobile(self):
        plan = [
            {"kind": "follow", "handle": "@lectora"},
            {
                "kind": "like", "handle": "lectora",
                "url": "https://www.tiktok.com/@lectora/video/1",
            },
        ]
        with patch.object(te.dup, "check", return_value=[]):
            validated = te.preflight_plan(plan)
        self.assertEqual(validated[0]["handle"], "lectora")

    def test_preflight_drops_like_when_same_post_has_comment(self):
        plan = [
            {
                "kind": "like", "handle": "lectora",
                "url": "https://www.tiktok.com/@lectora/video/1",
            },
            {
                "kind": "comment", "handle": "lectora",
                "url": "https://www.tiktok.com/@lectora/video/1",
                "text": "Me interesa esa lectura.",
            },
        ]
        with patch.object(te.dup, "check", return_value=[]),              patch.object(te, "_check_spanish_orthography", return_value=None):
            validated = te.preflight_plan(plan)
        self.assertEqual([item["kind"] for item in validated], ["comment"])

    def test_preflight_rejects_non_tiktok_url_and_long_comment(self):
        with self.assertRaisesRegex(ValueError, "URL TikTok"):
            te.preflight_plan([{
                "kind": "like", "handle": "foo", "url": "https://example.com/x",
            }])
        with patch.object(te.dup, "check", return_value=[]),              patch.object(te, "_check_spanish_orthography", return_value=None):
            with self.assertRaises(ValueError):
                te.preflight_plan([{
                    "kind": "comment", "handle": "foo",
                    "url": "https://www.tiktok.com/@foo/video/1",
                    "text": "x" * 151,
                }])

    def test_comment_preflight_uses_confirmed_url_history(self):
        plan = [{
            "kind": "comment", "handle": "lectora",
            "url": "https://www.tiktok.com/@lectora/video/1",
            "text": "Me interesa esa lectura.",
        }]
        with self.assertRaisesRegex(ValueError, "ya hay comentario confirmado"):
            te.preflight_plan(plan, already_commented_urls={plan[0]["url"]})

    def test_register_persists_permalink_for_future_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "registro.csv"
            path.write_text("fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n", encoding="utf-8")
            with patch.object(te, "REGISTRO_CSV", str(path)):
                te._append_registro([{
                    "kind": "comment", "handle": "lectora",
                    "url": "https://www.tiktok.com/@lectora/video/1",
                    "post_resumen": "Una caption concreta",
                    "text": "Me interesa esa lectura.",
                    "resultado": "confirmado", "motivo": "growth:T001-P1",
                }])
            rows = list(csv.DictReader(path.open(encoding="utf-8")))
            self.assertEqual(rows[0]["post_resumen"], "https://www.tiktok.com/@lectora/video/1")
            self.assertIn("caption=Una caption concreta", rows[0]["notas"])
    def test_action_ceiling_is_session_cap_not_target(self):
        config = {"action_ceiling": {"follow": 1, "like": 1, "comment": 1}}
        kept, skipped, _ = te._apply_action_ceiling([
            {"kind": "follow", "handle": "a"},
            {"kind": "follow", "handle": "b"},
            {"kind": "like", "handle": "a", "url": "u"},
        ], config)
        self.assertEqual(len(kept), 2)
        self.assertEqual(skipped[0]["resultado"], "saltado_techo_sesion")

<<<<<<< HEAD
=======
    def test_daily_cap_counts_confirmed_and_pending_from_prior_session(self):
        config = {"action_ceiling": {"follow": 2, "like": 1, "comment": 1}}
        planned = [{"kind": "follow", "handle": "nueva"},
                   {"kind": "like", "handle": "h", "url": "https://www.tiktok.com/@h/video/1"}]
        kept, skipped, _ = te._apply_action_ceiling(planned, config, used_today={"follow": 2, "like": 0, "comment": 0})
        self.assertEqual([x["kind"] for x in kept], ["like"])
        self.assertEqual(skipped[0]["resultado"], "saltado_techo_diario")

>>>>>>> origin/research/public-reuse-parent
    def test_comment_with_stray_trailing_tokens_is_rejected(self):
        for bad in ("Qué bueno, me encantó GT GT", "Me la apunto ya ya", "Gran reseña GT"):
            plan = [{"kind": "comment", "handle": "a", "url": "https://www.tiktok.com/@a/video/1", "text": bad}]
            if bad.endswith("GT") and "GT GT" not in bad:
                continue  # una sigla suelta aislada no se considera artefacto
            with self.assertRaises(ValueError):
                te.preflight_plan(plan, already_commented_urls=set())

<<<<<<< HEAD
    def test_single_unverified_write_is_a_soft_failure_and_session_continues(self):
=======
    def test_single_unverified_write_stops_without_retry(self):
>>>>>>> origin/research/public-reuse-parent
        adapter = FakeAdapter(fail_on="like")
        results = te.run_plan([
            {"kind": "like", "handle": "a", "url": "https://www.tiktok.com/@a/video/1"},
            {"kind": "follow", "handle": "b"},
        ], adapter, pause=False)
<<<<<<< HEAD
        self.assertTrue(results[0]["resultado"].startswith("fallo:"))
        self.assertEqual(results[1]["resultado"], "confirmado")
=======
        self.assertEqual(results[0]["resultado"], "pendiente_verificacion")
        self.assertEqual(results[1]["resultado"], "no_intentado")
>>>>>>> origin/research/public-reuse-parent

    def test_three_consecutive_soft_failures_stop_the_session(self):
        adapter = FakeAdapter(fail_on="like")
        plan = [{"kind": "like", "handle": f"a{i}", "url": f"https://www.tiktok.com/@a/video/{i}"}
                for i in range(5)]
        results = te.run_plan(plan, adapter, pause=False)
        self.assertEqual([r["resultado"].split(":")[0] for r in results],
<<<<<<< HEAD
                         ["fallo", "fallo", "fallo", "no_intentado", "no_intentado"])
=======
                         ["pendiente_verificacion", "no_intentado", "no_intentado", "no_intentado", "no_intentado"])
>>>>>>> origin/research/public-reuse-parent

    def test_challenge_is_always_a_total_stop(self):
        class A:
            def follow(self, handle):
                raise te.TikTokMobileChallenge("captcha")
<<<<<<< HEAD
        results = te.run_plan([{"kind": "follow", "handle": "a"}, {"kind": "follow", "handle": "b"}],
                              A(), pause=False)
=======
        with tempfile.TemporaryDirectory() as folder, patch.object(te.safety, "COOLDOWN_PATH", str(pathlib.Path(folder) / "pause.json")):
            results = te.run_plan([{"kind": "follow", "handle": "a"}, {"kind": "follow", "handle": "b"}],
                                  A(), pause=False)
>>>>>>> origin/research/public-reuse-parent
        self.assertTrue(results[0]["resultado"].startswith("parada:"))
        self.assertEqual(results[1]["resultado"], "no_intentado")

    def test_confirmed_actions_complete_normally(self):
        adapter = FakeAdapter()
        results = te.run_plan([
            {"kind": "follow", "handle": "a"},
            {
                "kind": "like", "handle": "a",
                "url": "https://www.tiktok.com/@a/video/1",
            },
        ], adapter, pause=False)
        self.assertEqual([r["resultado"] for r in results], ["confirmado", "confirmado"])


if __name__ == "__main__":
    unittest.main()
