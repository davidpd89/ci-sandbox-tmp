"""09/10/2026: el aviso real de TikTok («seguir con demasiada frecuencia») pausa SOLO los follows; like/comment siguen. Sin movil ni red."""
import csv
import datetime as dt
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import tiktok_safety as safety

NOW = dt.datetime(2026, 10, 9, 8, 0, tzinfo=dt.timezone.utc)
TOAST = "Estás usando la opción de seguir con demasiada frecuencia. Inténtalo más tarde."


def screen(text):
    return {"children": [{"type": "android.widget.TextView", "text": text, "rect": {"x": 0, "y": 500, "width": 900, "height": 80}}]}


class ScopedPauseTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "bulk_cooldown.json")

    def test_follow_limit_blocks_only_follows(self):
        minutes = safety.restrict("follow_limit", self.path, now=NOW)
        self.assertEqual(minutes, 60)
        state = json.load(open(self.path, encoding="utf-8"))
        self.assertEqual(state["scope"], "follow")
        self.assertNotIn("manual_review", state)          # no hace falta revision humana por un limite de seguir
        for kind in ("like", "comment"):
            safety.require_writable(self.path, now=NOW, kind=kind)           # no lanza
            self.assertEqual(safety.remaining_minutes(self.path, kind=kind), 0.)
        for kind in (None, "follow"):                                        # bulk y llamadores antiguos: bloqueado
            with self.assertRaises(safety.SafetyBlocked):
                safety.require_writable(self.path, now=NOW, kind=kind)
        self.assertTrue(safety.follow_paused(self.path, now=NOW))

    def test_ladder_escalates_and_is_capped(self):
        got = [safety.restrict("follow_limit", self.path, now=NOW + dt.timedelta(minutes=i)) for i in range(6)]
        self.assertEqual(got, [60, 120, 240, 480, 480, 480])

    def test_global_pause_is_never_downgraded_by_a_follow_limit(self):
        safety.restrict("challenge", self.path, now=NOW)
        safety.restrict("follow_limit", self.path, now=NOW)
        state = json.load(open(self.path, encoding="utf-8"))
        self.assertIsNone(state.get("scope"))
        self.assertTrue(state["manual_review"])
        with self.assertRaises(safety.SafetyBlocked):
            safety.require_writable(self.path, now=NOW, kind="like")

    def test_expired_follow_pause_allows_follows_again(self):
        safety.restrict("follow_limit", self.path, now=NOW)
        later = NOW + dt.timedelta(minutes=61)
        safety.require_writable(self.path, now=later, kind="follow")
        self.assertFalse(safety.follow_paused(self.path, now=later))

    def test_invalid_scope_fails_closed(self):
        with open(self.path, "w", encoding="utf-8") as stream:
            json.dump({"until": "2099-01-01T00:00:00+00:00", "scope": "todo"}, stream)
        with self.assertRaises(safety.SafetyStateError):
            safety.require_writable(self.path, kind="like")

    def test_observation_is_logged_with_daily_counts(self):
        with open(os.path.join(self.dir, "registro_interacciones.csv"), "w", newline="", encoding="utf-8") as stream:
            w = csv.writer(stream)
            w.writerow(["fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"])
            today = NOW.astimezone().date().isoformat()
            for i in range(3):
                w.writerow([today, f"@c{i}", "follow", "", "", "confirmado", ""])
            w.writerow([today, "@c9", "like", "post1", "", "confirmado", ""])
        safety.restrict("follow_limit", self.path, now=NOW)
        rows = list(csv.DictReader(open(os.path.join(self.dir, "limit_observations.csv"), encoding="utf-8")))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["follows_hoy"], rows[0]["likes_hoy"], rows[0]["descanso_min"]), ("3", "1", "60"))

    def test_observation_failure_never_breaks_the_stop(self):
        os.makedirs(os.path.join(self.dir, "limit_observations.csv"))      # un directorio donde iria el CSV
        self.assertEqual(safety.restrict("follow_limit", self.path, now=NOW), 60)


class ScreenClassificationTests(unittest.TestCase):
    def test_follow_toast_is_a_follow_limit(self):
        with self.assertRaises(safety.SafetyFollowLimit):
            safety.check_screen(screen(TOAST))

    def test_captcha_is_a_global_warning_not_a_follow_limit(self):
        with self.assertRaises(safety.SafetyWarning) as ctx:
            safety.check_screen(screen("Verifica que eres humano"))
        self.assertNotIsInstance(ctx.exception, safety.SafetyFollowLimit)

    def test_normal_screen_passes(self):
        safety.check_screen(screen("Para ti Siguiendo Amigos"))


class FakeAdapter:
    def __init__(self, tree_text=TOAST, follow_raises=True):
        self.calls, self.tree_text, self.follow_raises = [], tree_text, follow_raises
        self.shown = False

    def _tree(self):
        return screen(self.tree_text if self.shown else "Para ti")

    def follow(self, handle):
        self.calls.append(("follow", handle))
        if self.follow_raises:
            self.shown = True
            from tiktok_mobile_interact import TikTokWriteUnverified
            raise TikTokWriteUnverified("no quedó en Siguiendo")
        return "followed"

    def like(self, target):
        self.calls.append(("like", target))
        return "created"


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._saved = safety.COOLDOWN_PATH
        safety.COOLDOWN_PATH = os.path.join(self.dir, "bulk_cooldown.json")
        self.addCleanup(setattr, safety, "COOLDOWN_PATH", self._saved)

    def run_plan(self, plan, adapter):
        import tiktok_mobile_execute as ex
        saved = []
        results = ex.run_plan(plan, adapter, pause=False, on_result=saved.append)
        return results

    def test_follow_limit_skips_follows_and_keeps_liking(self):
        plan = [
            {"kind": "follow", "handle": "a"},
            {"kind": "like", "url": "https://www.tiktok.com/@x/video/1", "handle": "x", "post_text": "Una novela de fantasía que recomiendo a quienes disfrutan leyendo", "media_present": False},
            {"kind": "follow", "handle": "b"},
            {"kind": "like", "url": "https://www.tiktok.com/@y/video/2", "handle": "y", "post_text": "Reseña de una novela juvenil con dragones y magia para lectores", "media_present": False},
        ]
        adapter = FakeAdapter()
        results = self.run_plan(plan, adapter)
        outcomes = [r["resultado"] for r in results if r["resultado"] != "pendiente_verificacion"]
        self.assertEqual(outcomes, ["saltado_limite_follow", "confirmado", "saltado_limite_follow", "confirmado"])
        self.assertEqual([c for c in adapter.calls if c[0] == "follow"], [("follow", "a")])   # el segundo follow ni se intenta
        self.assertEqual(len([c for c in adapter.calls if c[0] == "like"]), 2)
        self.assertTrue(safety.follow_paused())

    def test_global_challenge_still_stops_everything(self):
        class Challenging(FakeAdapter):
            def _tree(self):
                return screen("Verifica que eres humano")
        plan = [{"kind": "like", "url": "https://www.tiktok.com/@x/video/1", "handle": "x"},
                {"kind": "like", "url": "https://www.tiktok.com/@y/video/2", "handle": "y"}]
        results = self.run_plan(plan, Challenging())
        self.assertEqual([r["resultado"] for r in results], ["parada:SafetyWarning", "no_intentado"])


class ExecutorMainPreflightTests(unittest.TestCase):
    def test_main_revalidation_under_lock_is_kind_aware(self):
        # 09/10: sin esto, una pausa solo de follows hacia `restricted` el ejecutor entero (12:52, 0,3 s) y las ruedas de like/comment no corrian.
        import inspect
        import tiktok_mobile_execute as ex
        source = inspect.getsource(ex.main)
        self.assertIn('safety.require_writable(kind="like" if any(i["kind"] != "follow" for i in kept) else None)', source)


if __name__ == "__main__":
    unittest.main()
