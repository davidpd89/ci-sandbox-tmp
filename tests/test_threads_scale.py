"""Threads a escala (05/10): reserva de posts, plan desde la reserva, like por permalink, filtro de perfil, registro accion a accion, sesion compartida."""
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

NOW = datetime.datetime(2026, 10, 5, 22, 0, 0)
TODAY = NOW.date()


def load_function(filename, name, namespace):
    source = ROOT / "tools" / filename
    node = next(n for n in ast.parse(source.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


def post(handle, body, age="2 h", code=None):
    return (handle, f"https://www.threads.com/@{handle}/post/{code or handle}", f"{handle} {age} {body}", "search:Book Threads")


class AgeTests(unittest.TestCase):
    def test_age_from_the_header(self):
        self.assertAlmostEqual(tp.parse_age_hours("ana Book Threads 3 h Hola"), 3)
        self.assertAlmostEqual(tp.parse_age_hours("ana 30 min Hola"), 0.5)
        self.assertEqual(tp.parse_age_hours("ana 2 d Hola"), 48)
        self.assertEqual(tp.parse_age_hours("ana 1 sem Hola"), 168)
        self.assertEqual(tp.parse_age_hours("ana 3 días Hola"), 72)          # 06/10: «días»/«semanas»/«horas» en palabras completas
        self.assertEqual(tp.parse_age_hours("ana Book Threads 2 semanas Hola"), 336)
        self.assertEqual(tp.parse_age_hours("ana 5 horas Hola"), 5)
        self.assertEqual(tp.body_of("ana 3 días Hola que tal"), "Hola que tal")
        self.assertGreater(tp.parse_age_hours("ana 23/09/2026 Hola", now=NOW), 300)
        self.assertIsNone(tp.parse_age_hours("sin cabecera de edad"))

    def test_body_drops_header_and_counters(self):
        self.assertEqual(tp.body_of("ana Book Threads 3 h Terminé mi novela de fantasía 24"), "Terminé mi novela de fantasía")


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = tp.connect(os.path.join(self.tmp.name, "pool.sqlite3"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def record(self, rows):
        return tp.record_posts(self.db, rows, TODAY.isoformat())

    def test_posts_accumulate_without_duplicates_and_first_touch_is_kept(self):
        rows = [post("ana", "Terminé mi novela de fantasía por fin y tengo ganas de escribir más"), post("luis", "Hoy toca leer un libro de poesía antes de dormir con calma")]
        self.assertEqual(self.record(rows), 2)
        self.assertEqual(self.record(rows + [("ana", rows[0][1], rows[0][2], "feed")]), 0)         # repetidos: no entran de nuevo
        again = [("ana", "https://www.threads.com/@ana/post/otro", "ana 1 h Otro libro de fantasía que he leído esta semana con mucho gusto", "feed")]
        self.record(again)
        self.assertEqual(tp.first_touch(self.db, ["ana", "luis"]), {"ana": "search:Book Threads", "luis": "search:Book Threads"})

    def test_junk_is_never_stored(self):
        rows = [post("pol", "El gobierno y el partido votan hoy la reforma en el congreso de los diputados"),
                post("spam", "Descargar gratis libros pdf drive.google.com/abc para todos nuestros amigos lectores")]
        self.assertEqual(self.record(rows), 0)

    def test_pick_keeps_niche_spanish_recent_one_per_account_and_skips_excluded(self):
        self.record([
            post("ana", "Terminé mi novela de fantasía por fin y tengo ganas de escribir más libros", code="a1"),
            post("ana", "Otro libro de fantasía que estoy leyendo ahora mismo y me encanta", code="a2"),
            post("bea", "Reading a fantasy book tonight and writing my novel with the new chapter ready", code="b1"),
            post("cris", "Hoy hace sol y me voy a la playa con mis amigos toda la tarde", code="c1"),
            post("dani", "Recomendadme una novela de fantasía juvenil para este otoño, ¿alguna idea?", code="d1"),
            post("eli", "Escribir cada mañana un poco de mi novela me cambia el día entero", age="5 d", code="e1"),
            post("fran", "Mi libro de relatos ya está terminado y estoy muy contento con él", code="f1"),
        ])
        picked = tp.pick(self.db, 10, exclude_handles=frozenset({"fran"}), now=NOW)
        handles = [row["handle"] for row in picked]
        self.assertEqual(sorted(handles), ["ana", "dani"])        # bea (ingles), cris (sin nicho), eli (5 dias), fran (excluida); ana una sola vez

    def test_acted_posts_are_not_picked_again(self):
        self.record([post("ana", "Terminé mi novela de fantasía por fin y tengo ganas de escribir más libros", code="a1")])
        tp.mark(self.db, "https://www.threads.com/@ana/post/a1", "done", TODAY.isoformat())
        self.assertEqual(tp.pick(self.db, 5, now=NOW), [])
        self.assertEqual(tp.stats(self.db, NOW)["acted"], 1)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = tp.connect(os.path.join(self.tmp.name, "pool.sqlite3"))
        tp.record_posts(self.db, [post(h, f"Terminé mi novela de fantasía número {i} y quiero seguir escribiendo libros", code=h) for i, h in enumerate("abcdef")],
                        TODAY.isoformat())

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_likes_use_the_permalink_and_follows_go_only_to_new_accounts_with_a_cap(self):
        plan = tb.build_from_pool(self.db, likes=4, follows=2, known={"a": "2026-01-01"}, today=TODAY)
        likes = [a for a in plan if a["kind"] == "like"]
        follows = [a for a in plan if a["kind"] == "follow"]
        self.assertEqual(len(likes), 4)
        self.assertTrue(all(a["permalink"].startswith("https://www.threads.com/@") and ":src=" in a["motivo"] for a in likes))
        self.assertEqual(len(follows), 2)
        self.assertNotIn("a", {f["handle"] for f in follows})              # ya conocida: like si, follow no

    def test_recently_touched_accounts_are_left_alone(self):
        plan = tb.build_from_pool(self.db, likes=6, follows=0, known={"a": TODAY.isoformat(), "b": (TODAY - datetime.timedelta(days=9)).isoformat()}, today=TODAY)
        handles = {a["handle"] for a in plan}
        self.assertNotIn("a", handles)       # tocada hoy
        self.assertIn("b", handles)          # hace 9 dias: vuelve a ser elegible


class AlreadyLikedTests(unittest.TestCase):
    def test_posts_already_registered_by_fragment_are_not_picked_again(self):
        tmp = tempfile.TemporaryDirectory()
        db = tp.connect(os.path.join(tmp.name, "pool.sqlite3"))
        try:
            tp.record_posts(db, [post("ana", "Terminé mi novela de fantasía por fin y tengo ganas de escribir más libros", code="a1"),
                                 post("bea", "Otro libro de fantasía que estoy leyendo ahora mismo y me encanta mucho", code="b1")], TODAY.isoformat())
            done = {tp.fragment_key("@ana", "Terminé mi novela de fantasía por fin")}
            plan = tb.build_from_pool(db, likes=5, follows=0, today=TODAY, done_fragments=done)
            self.assertEqual([a["handle"] for a in plan], ["bea"])
        finally:
            db.close()
            tmp.cleanup()


class ExecutorTests(unittest.TestCase):
    def namespace(self, t, **extra):
        class Dup:
            @staticmethod
            def check(text):
                return []
        ns = {"t": t, "dup": Dup(), "_drop_stacked_actions": lambda p: p, "_pause": lambda: None, "ec": __import__("exec_common")}
        ns.update(extra)
        return ns

    def fake_t(self, **overrides):
        stop = type("BotWarningDetected", (RuntimeError,), {})
        wrong = type("WrongAccountActive", (RuntimeError,), {})
        already = type("AlreadyCommented", (RuntimeError,), {})
        rejected = type("ProfileRejected", (RuntimeError,), {})
        base = dict(BotWarningDetected=stop, WrongAccountActive=wrong, AlreadyCommented=already, ProfileRejected=rejected,
                    follow=lambda h, vet=None: "followed", like_in_feed=lambda *a: "created", like_post=lambda link, handle: "created", reply_to=lambda *a: "created")
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def test_like_with_permalink_uses_it_and_falls_back_to_the_fragment(self):
        calls = []
        t = self.fake_t(like_post=lambda link, handle: calls.append(("permalink", link)) or "created",
                        like_in_feed=lambda *a: calls.append(("fragmento", a[0])) or "created")
        run = load_function("threads_execute.py", "run_plan", self.namespace(t))
        run([{"kind": "like", "handle": "ana", "permalink": "https://www.threads.com/@ana/post/x1", "text_fragment": "hola"},
             {"kind": "like", "handle": "bea", "text_fragment": "adios"}], prevalidated=True)
        self.assertEqual(calls, [("permalink", "https://www.threads.com/@ana/post/x1"), ("fragmento", "adios")])

    def test_rejected_profile_is_skipped_with_a_reason_not_failed(self):
        t = self.fake_t()

        def follow(handle, vet=None):
            raise t.ProfileRejected("cuenta enorme (90000 seguidores)")
        t.follow = follow
        run = load_function("threads_execute.py", "run_plan", self.namespace(t, _follow_vet=lambda info: None))
        result = run([{"kind": "follow", "handle": "gigante"}], prevalidated=True)
        self.assertTrue(result[0]["resultado"].startswith("saltado_perfil:"))

    def test_each_result_is_reported_as_it_happens(self):
        seen = []
        t = self.fake_t(like_post=lambda link, handle: (_ for _ in ()).throw(RuntimeError("boom")) if handle == "b" else "created")
        run = load_function("threads_execute.py", "run_plan", self.namespace(t))
        run([{"kind": "like", "handle": h, "permalink": f"https://www.threads.com/@{h}/post/1", "text_fragment": "x"} for h in "abc"],
            prevalidated=True, on_result=lambda r: seen.append((r["handle"], r["resultado"].split(":")[0])))
        self.assertEqual(seen, [("a", "confirmado"), ("b", "fallo"), ("c", "confirmado")])

    def test_preflight_keeps_only_canonical_permalinks_of_the_same_author(self):
        pre = load_function("threads_execute.py", "_preflight_plan", self.namespace(self.fake_t(), _VALID_KINDS={"follow", "like", "reply"},
                                                                                     sc=types.SimpleNamespace(drop_stacked_actions=lambda p, **k: p, report_plan_style=lambda p: None)))
        plan = pre([
            {"kind": "like", "handle": "ana", "text_fragment": "a", "permalink": "https://www.threads.com/@ana/post/AAA/"},
            {"kind": "like", "handle": "bea", "text_fragment": "b", "permalink": "https://www.threads.com/@otra/post/BBB"},
            {"kind": "like", "handle": "cris", "text_fragment": "c", "permalink": "https://evil.example/@cris/post/CCC"},
        ])
        self.assertEqual([item.get("permalink") for item in plan], ["https://www.threads.com/@ana/post/AAA", None, None])

    def test_follow_vet_rejects_giants_politics_and_english_bios(self):
        import threads_execute as te
        self.assertIsNone(te._follow_vet({"followers": 300, "bio": "Escribo novelas de fantasía y leo mucho"}))
        self.assertIn("enorme", te._follow_vet({"followers": 90000, "bio": "Escritora de fantasía"}))
        self.assertIn("politica", te._follow_vet({"followers": 300, "bio": "Libros y activismo, luchando contra el fascismo y el genocidio"}))
        self.assertIn("ingles", te._follow_vet({"followers": 300, "bio": "Fantasy writer and book reader, my new book is out today"}))


class InteractTests(unittest.TestCase):
    def test_follower_counts_and_profile_info(self):
        import threads_interact as ti
        self.assertEqual([ti._count_text(*x) for x in [("1.234", None), ("1,2", "mil"), ("1.2", "K"), ("3", "M"), ("33", None)]], [1234, 1200, 1200, 3000000, 33])

        class Page:
            def __init__(self, body):
                self.body = body

            def inner_text(self, selector):
                return self.body

        real = ("Para ti\nNuevo hilo\nBuscar\nMensajes\nActividad\nPerfil\nEstadísticas\nOtros feeds\nEditar\nSeguidos\nGuardado\nTe gusta\nPublicaciones temporales\nArchivo\n"
                "mjaoruizamorocho\nReux Demian\nmjaoruizamorocho\nTe sigue\ncazador de libros raros, lector empedernido.\nlibros\nmúsica\n125 seguidores\nSiguiendo\nMensaje\nHilos")
        info = ti.profile_info(Page(real))
        self.assertEqual(info["followers"], 125)
        self.assertTrue(info["follows_me"])                                         # «Te sigue»: seguirla es devolver el follow
        self.assertEqual(info["bio"], "cazador de libros raros, lector empedernido. libros música")
        self.assertNotIn("Perfil", info["bio"])
        plain = ti.profile_info(Page("Para ti\nArchivo\nana\nAna\nana\nEscribo fantasía\n1,2 mil seguidores\nSeguir"))
        self.assertEqual((plain["followers"], plain["follows_me"], plain["bio"]), (1200, False, "Escribo fantasía"))

    def test_scrolling_collector_dedupes_and_stops_when_nothing_new_loads(self):
        import threads_interact as ti
        pages = [[("a", "https://t/@a/post/1", "x")], [("a", "https://t/@a/post/1", "x"), ("b", "https://t/@b/post/2", "y")], [("a", "https://t/@a/post/1", "x"), ("b", "https://t/@b/post/2", "y")]]
        state = {"i": 0}
        pg = types.SimpleNamespace(mouse=types.SimpleNamespace(wheel=lambda *a: state.update(i=state["i"] + 1)), wait_for_timeout=lambda ms: None)
        original_extract, original_check = ti._extract_posts, ti._check_bot_warning
        ti._extract_posts = lambda pg, limit=15: pages[min(state["i"], len(pages) - 1)]
        ti._check_bot_warning = lambda pg: None
        try:
            out = ti.collect_posts_scrolling(pg, passes=5, limit=60)
        finally:
            ti._extract_posts, ti._check_bot_warning = original_extract, original_check
        self.assertEqual([h for h, _, _ in out], ["a", "b"])
        self.assertLessEqual(state["i"], 3)         # corto el scroll en cuanto dejo de cargar cosas nuevas


if __name__ == "__main__":
    unittest.main()


class ReplyQueueTests(unittest.TestCase):
    def setUp(self):
        import threads_reply_queue as rq
        self.rq = rq
        self.tmp = tempfile.TemporaryDirectory()
        self.db = tp.connect(os.path.join(self.tmp.name, "pool.sqlite3"))
        tp.record_posts(self.db, [
            post("ana", "¿Qué novela de fantasía me recomendáis para este otoño? Acabo de terminar una saga larga", code="a1"),
            post("bea", "Terminé mi novela de fantasía por fin y tengo ganas de escribir más libros ahora", code="b1"),
            post("cris", "¿Qué libro de fantasía estáis leyendo ahora mismo? Necesito recomendaciones nuevas", code="c1", age="3 d"),
        ], TODAY.isoformat())

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_only_recent_conversational_posts_of_accounts_not_replied_to(self):
        rows = self.rq.candidates(self.db, n=5, now=NOW)
        self.assertEqual([r["handle"] for r in rows], ["ana"])                 # bea no invita a conversar; cris tiene 3 dias
        self.assertEqual(self.rq.candidates(self.db, n=5, replied=frozenset({"ana"}), now=NOW), [])

    def test_plan_is_built_from_permalinks_in_the_pool(self):
        plan = self.rq.build_plan(self.db, {"replies": [{"permalink": "https://www.threads.com/@ana/post/a1/", "text": "¿Autoconclusiva o saga?"}]})
        self.assertEqual((plan[0]["handle"], plan[0]["kind"], plan[0]["text"]), ("ana", "reply", "¿Autoconclusiva o saga?"))
        with self.assertRaises(ValueError):
            self.rq.build_plan(self.db, {"replies": [{"permalink": "https://www.threads.com/@x/post/zz", "text": "hola"}]})
