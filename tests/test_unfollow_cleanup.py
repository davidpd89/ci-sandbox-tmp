"""unfollow_cleanup generico (06/10): reglas, verificacion en vivo y registro; sin red."""
import contextlib
import datetime
import os
import pathlib
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
sys.modules.setdefault("requests", requests_stub)
import unfollow_cleanup as uc

TODAY = datetime.date(2026, 10, 6)


def row(account, days_ago, tipo="follow", resultado="confirmado"):
    when = (TODAY - datetime.timedelta(days=days_ago)).isoformat()
    return {"fecha": when, "cuenta": f"@{account}", "tipo": tipo, "resultado": resultado}


class RuleTests(unittest.TestCase):
    def test_non_reciprocal_after_grace_days_only(self):          # 07/10: plazo de 7 dias (antes 30)
        rows = [row("vieja", 10), row("nueva", 3), row("devuelve", 45)]
        out = uc.candidates(rows, ["devuelve"], TODAY)
        self.assertEqual([c["account"] for c in out], ["vieja"])

    def test_a_reply_earns_more_patience(self):
        rows = [row("charlada", 10), row("charlada", 9, tipo="reply", resultado="publicado")]
        self.assertEqual(uc.candidates(rows, [], TODAY), [])

    def test_foreign_language_bios_go_even_when_followed_by_hand_but_not_followers(self):
        following = {"hans": "Schreibt Fantasy und Science Fiction. Hat Ahnung von Büchern und schreibt auch über Romane.",
                     "john": "I love fantasy books and writing novels every single day of the week",
                     "ana": "Lectora de fantasía y novelas, escribo mucho",
                     "sinbio": "", "amigo": "I love fantasy books and writing novels every single day of the week"}
        out = uc.candidates([], ["amigo"], TODAY, following=following)
        self.assertEqual(sorted(c["account"] for c in out), ["hans", "john"])          # el que nos sigue no se toca; bio vacia o espanola, tampoco


class FakeAdapter:
    name = "fake"

    def __init__(self, following, followers, really_follow_us=()):
        self._following, self._followers, self.really = following, followers, set(really_follow_us)
        self.unfollowed = []

    @contextlib.contextmanager
    def session(self):
        yield

    def load(self):
        return self._following, self._followers

    def follows_me(self, account):
        return account in self.really

    def unfollow(self, account):
        self.unfollowed.append(account)
        return "unfollowed"


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "SISTEMA_DIARIO_FAKE"))
        self.old_root = uc.ROOT
        uc.ROOT = self.tmp.name
        uc.ga.ROOT = self.tmp.name
<<<<<<< HEAD
=======
        import circuit_breaker                      # la red de pruebas «fake» no esta en la lista cerrada del cortacircuitos (#154)
        saved = circuit_breaker.write_preflight
        circuit_breaker.write_preflight = lambda network, **kw: (True, "")
        self.addCleanup(setattr, circuit_breaker, "write_preflight", saved)
>>>>>>> origin/research/public-reuse-parent

    def tearDown(self):
        uc.ROOT = self.old_root
        uc.ga.ROOT = self.old_root
        self.tmp.cleanup()

    def test_live_check_protects_a_follower_missing_from_the_list_and_results_are_registered(self):
        german = "Schreibt Fantasy und Science Fiction. Hat Ahnung von Büchern und schreibt auch über Romane."
        adapter = FakeAdapter({"hans": german, "gerda": german}, [], really_follow_us={"gerda"})
        total, done, failed = uc.run("fake", apply=True, limit=10, adapter=adapter, sleep=lambda s: None, out=lambda *a: None)
        self.assertEqual((total, done, failed), (2, 1, 0))
        self.assertEqual(adapter.unfollowed, ["hans"])
        text = open(os.path.join(self.tmp.name, "SISTEMA_DIARIO_FAKE", "registro_interacciones.csv"), encoding="utf-8").read()
        self.assertIn("@hans,", text.replace(",unfollow", ""))
        self.assertIn("unfollow", text)
        self.assertNotIn("gerda", text)

    def test_report_mode_changes_nothing_and_limit_is_respected(self):
        german = "Schreibt Fantasy und Science Fiction. Hat Ahnung von Büchern und schreibt auch über Romane."
        adapter = FakeAdapter({f"h{i}": german for i in range(5)}, [])
        uc.run("fake", apply=False, adapter=adapter, sleep=lambda s: None, out=lambda *a: None)
        self.assertEqual(adapter.unfollowed, [])
        uc.run("fake", apply=True, limit=2, adapter=adapter, sleep=lambda s: None, out=lambda *a: None)
        self.assertEqual(len(adapter.unfollowed), 2)


if __name__ == "__main__":
    unittest.main()
