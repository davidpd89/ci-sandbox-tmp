"""PR54: campañas entre cuentas y cohortes Threads, sin cuentas ni navegador."""
import pathlib
import sqlite3
import sys
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import threads_discovery_quality as dq
import threads_build_plan as builder
import threads_pool as pool

GOOD = "Hoy terminé de leer una novela de fantasía juvenil y quiero compartir tres recomendaciones"
BAIT = "Busco un hablante nativo de español para trabajar conmigo. Presupuesto: $1,500 por semana"
TEMPLATE = "Buscamos personas para colaborar en un proyecto nuevo de lectura, escribid por mensaje si os interesa mucho participar"


class SpamPolicyTests(unittest.TestCase):
    def test_job_bait_rejected_despite_accents_currency_or_amount(self):
        self.assertTrue(dq.job_bait(BAIT))
        self.assertTrue(dq.job_bait(
            "BUSCO hablante nativo de espanol, salario 1500 euros"))
        self.assertFalse(dq.job_bait(GOOD))

    def test_different_authors_repeating_solicitation_are_quarantined(self):
        rows = [
            {"handle": "a", "text": TEMPLATE},
            {"handle": "b", "text": TEMPLATE.replace("proyecto", "proyecto")},
            {"handle": "c", "text": TEMPLATE + " 1500 EUR"},
        ]
        # Igualar importes no basta: la plantilla completa debe coincidir.
        self.assertNotIn("c", dq.blocked_handles(rows))
        rows[2]["text"] = TEMPLATE
        self.assertEqual(dq.blocked_handles(rows), {"a", "b", "c"})

    def test_same_account_reposting_does_not_create_false_campaign(self):
        rows = [{"handle": "a", "text": TEMPLATE} for _ in range(20)]
        self.assertEqual(dq.blocked_handles(rows), set())

    def test_literal_job_scam_blocked_even_if_only_one_account(self):
        self.assertEqual(dq.blocked_handles([
            ("scammer", "https://example.test/1", BAIT, "search:libros")
        ]), {"scammer"})

    def test_identical_genuine_book_posts_are_not_automatically_banned(self):
        rows = [{"handle": h, "text": GOOD} for h in ("a", "b", "c", "d")]
        self.assertEqual(dq.blocked_handles(rows), set())

    def test_currency_symbols_and_verb_forms_cannot_avoid_job_guard(self):
        self.assertTrue(dq.job_bait("Busco traductora española $2500"))
        self.assertTrue(dq.job_bait("Contratamos hablantes nativos de español por 800 €"))
        self.assertFalse(dq.job_bait("Busco libros de fantasía para mi siguiente lectura"))

    def test_threads_account_ingest_rejects_campaign_before_persisting(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = pool.connect(str(pathlib.Path(tmp) / "pool.sqlite3"))
            try:
                rows = [
                    ("fraude1", "Autora", BAIT + " novela", "profiles:libros", None),
                    ("fraude2", "Autora", BAIT + " novela", "profiles:libros", None),
                    ("lectora", "Lectura", "Leo fantasía y escribo novelas",
                     "profiles:libros", None),
                ]
                added = pool.record_accounts(db, rows)
                handles = {row[0] for row in db.execute("SELECT handle FROM accounts")}
                self.assertEqual(handles, {"lectora"})
                self.assertEqual(added, 1)
                self.assertEqual(db.execute("SELECT count(*) FROM accounts").fetchone()[0], 1)
            finally:
                db.close()

    def test_multi_account_profile_solicitation_is_filtered_by_adapter(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = pool.connect(str(pathlib.Path(tmp) / "pool.sqlite3"))
            try:
                campaign = [(h, "Autor", TEMPLATE, "profiles:libros", None)
                            for h in ("camp1", "camp2", "camp3")]
                self.assertEqual(pool.record_accounts(db, campaign), 0)
                self.assertEqual(db.execute("SELECT count(*) FROM accounts").fetchone()[0], 0)
            finally:
                db.close()

    def test_pool_direct_ingest_cannot_bypass_quarantine(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = pool.connect(str(pathlib.Path(tmp) / "pool.sqlite3"))
            try:
                rows = [
                    ("scam", "https://www.threads.com/@scam/post/1", BAIT,
                     "recent:libros"),
                    ("lectora", "https://www.threads.com/@lectora/post/2",
                     GOOD, "feed"),
                ]
                added = pool.record_posts(db, rows, today="2026-10-09")
                self.assertEqual(added, 1)
                self.assertEqual(db.execute(
                    "SELECT handle FROM posts").fetchall(), [("lectora",)])
                self.assertIn("scam", dq.quarantined_pool_handles(db))
                # La siguiente pasada no puede reintroducir el mismo actor
                # con un mensaje literario aparentemente inocuo.
                self.assertEqual(pool.record_posts(db, [
                    ("scam", "https://www.threads.com/@scam/post/3", GOOD,
                     "feed")], today="2026-10-10"), 0)
            finally:
                db.close()

    def test_quarantine_persists_after_reopen_and_stops_profile_reentry(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "pool.sqlite3")
            db = pool.connect(path)
            try:
                self.assertEqual(pool.record_accounts(db, [
                    ("bloqueada", "Autora de novela", BAIT, "profiles:libros", None)
                ]), 0)
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM thread_discovery_quarantine"
                ).fetchone()[0], 1)
            finally:
                db.close()
            db = pool.connect(path)
            try:
                self.assertIn("bloqueada", dq.quarantined_pool_handles(db))
                self.assertEqual(pool.record_accounts(db, [
                    ("bloqueada", "Autora de fantasía", GOOD, "profiles:libros", None)
                ]), 0)
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM accounts").fetchone()[0], 0)
            finally:
                db.close()

    def test_legacy_sqlite_includes_acted_posts_and_stored_bios(self):
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE posts (handle TEXT, text TEXT, status TEXT)")
            db.execute("CREATE TABLE accounts (handle TEXT, display TEXT, bio TEXT)")
            db.execute("INSERT INTO posts VALUES (?, ?, ?)",
                       ("fraude", BAIT, "liked"))
            db.execute("INSERT INTO accounts VALUES (?, ?, ?)",
                       ("perfil", "Lectora", "Busco traductora española $1500"))
            db.execute("INSERT INTO accounts VALUES (?, ?, ?)",
                       ("legitima", "Lectora", GOOD))
            before = db.total_changes
            self.assertEqual(dq.quarantined_pool_handles(db), {"fraude", "perfil"})
            self.assertEqual(db.total_changes, before)
        finally:
            db.close()

    def test_profile_source_and_handles_never_leave_aggregate_report(self):
        rows = [
            {"handle": "@autora", "source": "search:romantasy"},
            {"handle": "AUTORA", "source": "feed"},
            {"handle": "lector", "source": "followers:semilla"},
            {"handle": "sinfuente", "source": "profiles:libros"},
        ]
        first = {"autora": "feed", "lector": "followers:semilla"}
        report = dq.cohort_counts(rows, first_touch=first)
        self.assertEqual(report["candidatos_unicos"], {
            "feed": 1, "followers": 1, "unknown": 1})
        self.assertEqual(report["origen_estable_verificado"], 2)
        self.assertEqual(report["sin_origen_estable"], 1)
        self.assertIsNone(report["visitas_atribuidas"])
        self.assertIsNone(report["seguidores_atribuidos"])
        self.assertNotIn("semilla", str(report))
        self.assertNotIn("romantasy", str(report))


class BuilderGuardTests(unittest.TestCase):
    def test_snapshot_fallback_never_likes_or_follows_job_bait(self):
        candidates = [
            {"handle": "fraude", "text": BAIT + " libro", "source": "search:libros"},
            {"handle": "lectora", "text": GOOD, "source": "recent:fantasía"},
        ]
        result = builder.build(candidates, max_follows=2)
        self.assertEqual([row["handle"] for row in result],
                         ["lectora", "lectora"])
        self.assertEqual(result[0]["motivo"], "growth:candidate:src=recent")
        self.assertEqual(result[1]["kind"], "follow")

    def test_repeated_campaign_never_likes_or_follows_any_account(self):
        candidates = [{"handle": h, "text": TEMPLATE + " libro", "source": "search:books"}
                      for h in ("a", "b", "c")]
        self.assertEqual(builder.build(candidates, max_follows=3), [])

    def test_legacy_sqlite_candidates_are_checked_at_plan_time(self):
        records = [
            {"handle": "fraude", "text": BAIT + " novela", "source": "search:libro",
             "permalink": "https://example.test/fraud", "score": 12},
            {"handle": "lectora", "text": GOOD, "source": "feed",
             "permalink": "https://example.test/good", "score": 10},
        ]
        with mock.patch.object(pool, "pick", return_value=records), \
             mock.patch.object(pool, "pick_accounts", return_value=[]), \
             mock.patch.object(dq, "quarantined_pool_handles", return_value=set()):
            plan = builder.build_from_pool(object(), likes=2, follows=2,
                                           known={}, candidates=[])
        self.assertEqual({row["handle"] for row in plan}, {"lectora"})
        self.assertTrue(any(row["kind"] == "follow" for row in plan))

    def test_persisted_scam_profile_is_never_followed_or_liked(self):
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE posts (handle TEXT, text TEXT, status TEXT)")
            db.execute("CREATE TABLE accounts (handle TEXT, display TEXT, bio TEXT)")
            db.execute("INSERT INTO accounts VALUES (?, ?, ?)",
                       ("estafadora", "Autora de novelas", BAIT))
            genuine = {"handle": "lectora", "permalink": "https://example.test/ok",
                       "text": GOOD, "source": "feed", "score": 8}
            bad = {"handle": "estafadora", "permalink": "https://example.test/bad",
                   "text": GOOD, "source": "search:libros", "score": 12}
            account = {"handle": "estafadora", "display": "Autora", "bio": BAIT,
                       "source": "backfollow", "score": 50}
            with mock.patch.object(pool, "pick", return_value=[bad, genuine]), \
                 mock.patch.object(pool, "pick_accounts", return_value=[account]):
                plan = builder.build_from_pool(
                    db, likes=3, follows=2, candidates=[
                        {"handle": "estafadora", "text": GOOD,
                         "source": "recent:fantasia"}])
            self.assertEqual({i["handle"] for i in plan}, {"lectora"})
            self.assertTrue(any(i["kind"] == "follow" for i in plan))
        finally:
            db.close()

    def test_spam_never_arrives_at_reply_writer(self):
        records = [
            {"handle": "fraude", "text": BAIT + " libro", "permalink": "https://example.test/a"},
            {"handle": "lectora", "text": GOOD, "permalink": "https://example.test/b"},
        ]
        def writer(rows, **kwargs):
            self.assertEqual([r["handle"] for r in rows], ["lectora"])
            return []
        with mock.patch.object(pool, "pick", return_value=records), \
             mock.patch.object(dq, "quarantined_pool_handles", return_value=set()), \
             mock.patch.object(builder, "_done_fragments", return_value=set()), \
             mock.patch("x_replies.recent_phrases", return_value=set()), \
             mock.patch("x_replies.replies_per_round", return_value=3), \
             mock.patch("x_replies.build_replies", side_effect=writer):
            self.assertEqual(builder.build_replies(object(), 1, "NO_REAL.csv"), [])


if __name__ == "__main__":
    unittest.main()
