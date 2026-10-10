"""Threads (06/10): fuentes nuevas (pestana Perfiles, listas de seguidores, busqueda Recientes), cuentas de la reserva, like_latest y rampa; sin red ni navegador."""
import ast
import datetime
import os
import pathlib
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import threads_pool as tp
import threads_build_plan as tb
import volume_ramp as vr

TODAY = datetime.date(2026, 10, 6)


def load_function(filename, name, namespace):
    source = ROOT / "tools" / filename
    node = next(n for n in ast.parse(source.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


class RowParserTests(unittest.TestCase):
    def parse(self, text, handles):
        ns = {"MY_HANDLE": "davidportodiaz", "_ROW_STOP": {"seguir", "siguiendo", "mas perfiles", "más perfiles", "verificado", "te sigue", "solicitado"}}
        return load_function("threads_interact.py", "parse_account_rows", ns)(text, handles)

    def test_profile_search_rows(self):
        text = "Perfiles\nbiblioteca_olvidada\nAndrea Libros y Fantasía\nlaucen_entre_libros\nLaura\nFantasía romántica\nMás perfiles\ngodboks\nGabos / Libros\nSeguir\ndavidportodiaz\nDavid"
        rows = self.parse(text, ["biblioteca_olvidada", "laucen_entre_libros", "godboks", "davidportodiaz"])
        self.assertEqual([r[0] for r in rows], ["biblioteca_olvidada", "laucen_entre_libros", "godboks"])     # nuestra propia cuenta no entra
        self.assertEqual(rows[1][1:], ("Laura", "Fantasía romántica"))

    def test_followers_dialog_rows_with_repeated_handle_as_name(self):
        text = "Seguidores\n1.766\nSeguidos\n226\nescritorapilarherraiz\nPilar Herráiz\nESCRITORA\nSeguir\nfjhf10\nfjhf10\nSeguir"
        rows = self.parse(text, ["escritorapilarherraiz", "fjhf10"])
        self.assertEqual(rows, [("escritorapilarherraiz", "Pilar Herráiz", "ESCRITORA"), ("fjhf10", "fjhf10", "")])


class AccountPoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = tp.connect(os.path.join(self.tmp.name, "pool.sqlite3"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_niche_accounts_are_stored_and_spanish_and_niche_ones_ranked_first(self):
        rows = [("lectora1", "Laura", "Libros de fantasía, novelas y lecturas de fantasía épica", "profiles:libros fantasía", None),
                ("english_dude", "Dan", "I love fantasy books and reading novels every day", "profiles:libros fantasía", None),
                ("politico", "Pol", "Libros y política: vota al partido", "profiles:libros", None),
                ("sin_bio", "Ana", "", "followers:el_bookle", "el_bookle")]
        self.assertEqual(tp.record_accounts(self.db, rows, TODAY.isoformat()), 3)      # el politico se descarta
        picked = tp.pick_accounts(self.db, 5)
        handles = [r["handle"] for r in picked]
        self.assertEqual(handles[0], "lectora1")
        self.assertNotIn("english_dude", handles)
        self.assertNotIn("politico", handles)
        self.assertNotIn("sin_bio", handles)           # sin nicho ni idioma reconocible no se ofrece

    def test_followers_of_a_seed_with_spanish_bio_are_offered_even_without_niche_terms(self):
        tp.record_accounts(self.db, [("juana", "Juana", "Madre de tres, amante del café y de la montaña", "followers:el_bookle", "el_bookle")], TODAY.isoformat())
        self.assertEqual([r["handle"] for r in tp.pick_accounts(self.db, 3)], ["juana"])

    def test_accounts_with_niche_bio_from_profile_search_become_seeds_and_are_mined_in_turn(self):
        tp.record_accounts(self.db, [("booktoker", "Marta", "Libros, reseñas de novelas y fantasía", "profiles:booktok español", None)], TODAY.isoformat())
        tp.add_seeds(self.db, ["el_bookle"])
        self.assertEqual(set(tp.due_seeds(self.db, 5, TODAY)), {"booktoker", "el_bookle"})
        tp.mark_seed(self.db, "booktoker", followers=900, today=TODAY.isoformat())
        self.assertEqual(tp.due_seeds(self.db, 5, TODAY), ["el_bookle"])               # ya leida hoy
        self.assertIn("booktoker", tp.due_seeds(self.db, 5, TODAY + datetime.timedelta(days=7)))   # vuelve a tocar pasada una semana

    def test_seed_with_few_followers_is_not_mined_again(self):
        tp.add_seeds(self.db, ["pequena"])
        tp.mark_seed(self.db, "pequena", followers=40, today=TODAY.isoformat())
        self.assertEqual(tp.due_seeds(self.db, 5, TODAY + datetime.timedelta(days=30)), [])

    def test_acted_accounts_are_not_offered_again_and_first_touch_is_kept(self):
        tp.record_accounts(self.db, [("lectora1", "Laura", "Libros y fantasía y novelas", "profiles:libros", None)], TODAY.isoformat())
        tp.record_accounts(self.db, [("lectora1", "Laura", "Libros y fantasía y novelas", "followers:otra", "otra")], TODAY.isoformat())
        self.assertEqual(tp.first_touch(self.db, ["lectora1"])["lectora1"], "profiles:libros")
        tp.mark_account(self.db, "lectora1", "done", TODAY.isoformat())
        self.assertEqual(tp.pick_accounts(self.db, 3), [])


class PlanWithAccountsTests(unittest.TestCase):
    def test_a_quarter_of_the_likes_goes_to_accounts_and_new_ones_get_follow_then_like_latest(self):
        tmp = tempfile.TemporaryDirectory()
        db = tp.connect(os.path.join(tmp.name, "pool.sqlite3"))
        try:
            tp.record_posts(db, [(h, f"https://www.threads.com/@{h}/post/{h}", f"{h} 2 h Terminé mi novela de fantasía número {i} y quiero seguir escribiendo libros", "search:x")
                                 for i, h in enumerate("abcdefgh")], TODAY.isoformat())
            tp.record_accounts(db, [(f"lec{i}", "Laura", "Libros de fantasía, novelas y reseñas", "profiles:libros", None) for i in range(4)], TODAY.isoformat())
            plan = tb.build_from_pool(db, likes=8, follows=4, known={}, today=TODAY)
            likes = [a for a in plan if a["kind"] == "like"]
            latest = [a for a in plan if a["kind"] == "like_latest"]
            self.assertEqual(len(latest), 2)               # un cuarto de 8
            self.assertEqual(len(likes), 6)
            follows = [a for a in plan if a["kind"] == "follow"]
            self.assertEqual(len(follows), 4)
            for a in latest:                               # el follow de una cuenta de la reserva va justo antes de su like_latest (el perfil ya esta cargado)
                i = plan.index(a)
                if i and plan[i - 1]["kind"] == "follow":
                    self.assertEqual(plan[i - 1]["handle"], a["handle"])
        finally:
            db.close()
            tmp.cleanup()

    def test_without_accounts_all_likes_come_from_posts(self):
        tmp = tempfile.TemporaryDirectory()
        db = tp.connect(os.path.join(tmp.name, "pool.sqlite3"))
        try:
            tp.record_posts(db, [(h, f"https://www.threads.com/@{h}/post/{h}", f"{h} 2 h Terminé mi novela de fantasía número {i} y quiero seguir escribiendo libros", "search:x")
                                 for i, h in enumerate("abcdefgh")], TODAY.isoformat())
            plan = tb.build_from_pool(db, likes=8, follows=0, known={}, today=TODAY)
            self.assertEqual(len([a for a in plan if a["kind"] == "like"]), 8)
        finally:
            db.close()
            tmp.cleanup()


class ExecutorLikeLatestTests(unittest.TestCase):
    def run_plan(self, like_latest):
        class Dup:
            @staticmethod
            def check(text):
                return []
        rejected = type("ProfileRejected", (RuntimeError,), {})
        t = types.SimpleNamespace(BotWarningDetected=type("B", (RuntimeError,), {}), WrongAccountActive=type("W", (RuntimeError,), {}),
                                  AlreadyCommented=type("A", (RuntimeError,), {}), ProfileRejected=rejected, like_latest=like_latest)
        ns = {"t": t, "dup": Dup(), "_drop_stacked_actions": lambda p: p, "_pause": lambda: None, "_follow_vet": lambda info: None, "ec": __import__("exec_common")}
        return load_function("threads_execute.py", "run_plan", ns)([{"kind": "like_latest", "handle": "lec1", "motivo": "growth:acct"}], prevalidated=True)

    def test_confirmed_like_latest_is_recorded_as_a_normal_like_with_the_post_fragment(self):
        results = self.run_plan(lambda handle, vet=None: ("created", "Terminé mi novela de fantasía"))
        self.assertEqual(results[0]["kind"], "like")
        self.assertEqual(results[0]["text_fragment"], "Terminé mi novela de fantasía")
        self.assertEqual(results[0]["resultado"], "confirmado")

    def test_already_liked_is_skipped(self):
        self.assertEqual(self.run_plan(lambda handle, vet=None: ("already", "x"))[0]["resultado"], "saltado_ya_like")


class LikeButtonTests(unittest.TestCase):
    """06/10: en un hilo el contenedor incluye mas de un post; el primer boton de like (el del post de arriba) decide."""

    def finder(self):
        ns = {}
        return load_function("threads_interact.py", "_find_action_button", ns)

    def container(self, titles):
        class Btn:
            def __init__(self, title):
                self.title = title

            def evaluate(self, js, timeout=None):
                return self.title

        class Loc:
            def __init__(self, items):
                self.items = items

            def count(self):
                return len(self.items)

            def nth(self, i):
                return self.items[i]

        return types.SimpleNamespace(locator=lambda sel: Loc([Btn(t) for t in titles]))

    def test_already_liked_top_post_does_not_click_the_like_of_a_post_below(self):
        find = self.finder()
        c = self.container(["Responder", "Ya no me gusta", "Me gusta"])
        self.assertIsNone(find(c, "Me gusta"))
        self.assertIsNotNone(find(c, "Ya no me gusta"))

    def test_unliked_top_post_returns_its_like_button(self):
        find = self.finder()
        c = self.container(["Me gusta", "Responder", "Ya no me gusta"])
        self.assertIsNotNone(find(c, "Me gusta"))
        self.assertIsNone(find(c, "Ya no me gusta"))
        self.assertIsNotNone(find(c, "Responder"))


class BackfollowTests(unittest.TestCase):
    def test_new_followers_are_read_from_the_activity_text(self):
        ns = {"MY_HANDLE": "davidportodiaz"}
        parse = load_function("threads_interact.py", "parse_new_followers", ns)
        text = chr(10).join(['Actividad', 'Todo', 'bewithlau', ' y 1 más', '4 h', 'hace 4 horas', 'Ahora te sigue(n)', 'Tu respuesta obtuvo más de 50 visualizaciones.', 'giuvivanco_', '1 día', 'Escribir a veces...'])
        self.assertEqual(parse(text, ["bewithlau", "giuvivanco_", "davidportodiaz"]), ["bewithlau"])

    def test_backfollow_accounts_come_first_and_get_a_follow_even_if_already_known(self):
        tmp = tempfile.TemporaryDirectory()
        db = tp.connect(os.path.join(tmp.name, "pool.sqlite3"))
        try:
            tp.record_accounts(db, [("lectora1", "Laura", "Libros de fantasía, novelas y reseñas", "profiles:libros", None),
                                    ("nuevo", "", "", "backfollow", None)], TODAY.isoformat())
            self.assertEqual(tp.pick_accounts(db, 5)[0]["handle"], "nuevo")
            plan = tb.build_from_pool(db, likes=4, follows=2, known={"nuevo": "2026-10-04"}, today=TODAY)
            kinds = [(a["kind"], a["handle"]) for a in plan if a["handle"] == "nuevo"]
            self.assertIn(("follow", "nuevo"), kinds)
            self.assertIn(("like_latest", "nuevo"), kinds)
        finally:
            db.close()
            tmp.cleanup()


class RampTests(unittest.TestCase):
    def test_every_threads_stage_defines_the_new_levers(self):
        for row in vr.stages("threads"):
            self.assertIn("profile_queries", row)
            self.assertIn("seeds", row)

    def test_mastodon_reaches_five_thousand_a_day_and_rounds_never_exceed_ten(self):
        rows = vr.stages("mastodon")
        self.assertGreaterEqual(rows[-1]["daily"], 5000)
        self.assertLessEqual(max(r["rounds"] for r in rows), 10)
        self.assertEqual([r["daily"] for r in rows], sorted(r["daily"] for r in rows))


if __name__ == "__main__":
    unittest.main()
