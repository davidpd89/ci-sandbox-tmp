"""Regresiones de identidad, trials y cooldown del descubrimiento de X."""
import contextlib
import csv
import importlib
import io
import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

x = types.ModuleType("x_interact")
x.DAILY_LISTS = []
x.BotWarningDetected = type("BotWarningDetected", (RuntimeError,), {})
x.WrongAccountActive = type("WrongAccountActive", (RuntimeError,), {})
with patch.dict(sys.modules, {"x_interact": x}):
    scanner = importlib.import_module("x_scan")


class FakePage:
    def wait_for_timeout(self, *args, **kwargs):
        return None


class XDiscoveryTests(unittest.TestCase):
    def test_canonical_permalink_author_comes_from_url_not_mention(self):
        self.assertEqual(
            scanner._author_from_post_url(
                "https://x.com/AutoraReal/status/123456"
            ),
            "AutoraReal",
        )
        self.assertEqual(
            scanner._handle_from_text("Gracias @Mencionada por leerme"),
            "Mencionada",
        )

    def test_status_url_canonicalizes_domain_query_fragment_and_twitter(self):
        expected = "https://x.com/Lector_1/status/12345"
        for url in (
            "https://twitter.com/Lector_1/status/12345?utm_source=x#fragment",
            "https://www.twitter.com/Lector_1/status/12345",
            "https://www.x.com/Lector_1/status/12345",
            "https://x.com/Lector_1/status/12345/photo/1",
        ):
            with self.subTest(url=url):
                self.assertEqual(scanner._canonical_post_url(url), expected)

    def test_noncanonical_urls_cannot_prove_author(self):
        for url in (
            "http://x.com/AutoraReal/status/12345",
            "https://x.com/i/status/12345",
            "https://x.com/search?q=libros",
            "https://x.com.ejemplo.org/AutoraReal/status/12345",
            "https://user:pass@x.com/AutoraReal/status/12345",
            "https://x.com/AutoraReal",
            "https://x.com/AutoraReal/status/no-es-un-id",
        ):
            with self.subTest(url=url):
                self.assertIsNone(scanner._author_from_post_url(url))
                self.assertIsNone(scanner._canonical_post_url(url))

    def test_historical_twitter_url_is_same_dedupe_key(self):
        self.assertEqual(
            scanner._canonical_post_url(
                "https://twitter.com/Lectora/status/123?ref_src=twsrc%5Etfw"
            ),
            scanner._canonical_post_url(
                "https://x.com/Lectora/status/123"
            ),
        )

    def test_eligible_discovery_rejects_empty_self_excluded_and_political(self):
        with patch.object(
            scanner.sc,
            "is_political",
            side_effect=lambda text: "elecciones" in text.casefold(),
        ):
            self.assertTrue(
                scanner._eligible_discovery(
                    "https://x.com/Lectora/status/123",
                    "Busco fantasía nueva",
                    set(),
                )
            )
            self.assertFalse(
                scanner._eligible_discovery(
                    "https://x.com/Lectora/status/123",
                    "",
                    set(),
                )
            )
            self.assertFalse(
                scanner._eligible_discovery(
                    "https://x.com/DAVIDPORTODIAZ/status/123",
                    "Mi post",
                    set(),
                )
            )
            self.assertFalse(
                scanner._eligible_discovery(
                    "https://x.com/Descartada/status/123",
                    "Fantasía",
                    {"descartada"},
                )
            )
            self.assertFalse(
                scanner._eligible_discovery(
                    "https://x.com/Lectora/status/123",
                    "Hablemos de elecciones",
                    set(),
                )
            )

    def test_parse_dump_output_never_mixes_adjacent_urls_without_separator(self):
        rows = scanner._parse_dump_output(
            "URL: https://x.com/Uno/status/1\n"
            "Texto uno\n"
            "URL: https://x.com/Dos/status/2\n"
            "Texto dos\n---\n"
        )
        self.assertEqual(
            rows,
            [
                ("https://x.com/Uno/status/1", "Texto uno"),
                ("https://x.com/Dos/status/2", "Texto dos"),
            ],
        )

    def test_trial_measurement_never_calls_emit(self):
        calls = []

        def forbidden_emit(*args):
            calls.append(args)
            raise AssertionError("Una trial no debe emitir candidatos")

        result = scanner._process_discovery_rows(
            [
                ("https://x.com/Lectora/status/1", "Busco fantasía"),
                ("https://x.com/DavidPortoDiaz/status/2", "Mi post"),
            ],
            excluded=set(),
            operational=False,
            emit=forbidden_emit,
        )
        self.assertEqual(result["discovered"], 2)
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["novel"], 0)
        self.assertEqual(calls, [])

    def test_operational_rows_emit_only_eligible(self):
        emitted = []

        def emit(url, text):
            emitted.append((url, text))
            return True

        with patch.object(
            scanner.sc,
            "is_political",
            side_effect=lambda text: "elecciones" in text.casefold(),
        ):
            result = scanner._process_discovery_rows(
                [
                    ("https://x.com/Lectora/status/1", "Busco fantasía"),
                    ("https://x.com/Otra/status/2", "Elecciones"),
                    ("https://x.com/i/status/3", "Fantasía"),
                ],
                excluded=set(),
                operational=True,
                emit=emit,
            )
        self.assertEqual(result["discovered"], 3)
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["novel"], 1)
        self.assertEqual(
            emitted,
            [("https://x.com/Lectora/status/1", "Busco fantasía")],
        )

    def test_operational_rows_require_emit(self):
        with self.assertRaises(ValueError):
            scanner._process_discovery_rows(
                [("https://x.com/Lectora/status/1", "Fantasía")],
                excluded=set(),
                operational=True,
            )

    def test_trial_summary_latest_per_valid_day_and_legacy_header(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "trials.csv"
            scanner._record_trial_result(
                path, "busco un libro", 10, 3, date="2026-09-25"
            )
            scanner._record_trial_result(
                path, "busco un libro", 8, 4, date="2026-09-25"
            )
            scanner._record_trial_result(
                path, "busco un libro", 5, 2, date="2026-09-26"
            )
            self.assertEqual(
                scanner._trial_summary(path, "busco un libro"),
                {"days": 2, "discovered": 13, "eligible": 6},
            )

            legacy = pathlib.Path(td) / "legacy.csv"
            with open(legacy, "w", newline="", encoding="utf-8") as stream:
                w = csv.writer(stream)
                w.writerow(["fecha", "query", "descubiertos", "aceptados"])
                w.writerow(["2026-09-27", "busco un libro", "4", "3"])
                w.writerow(["fecha-mala", "busco un libro", "99", "99"])
            self.assertEqual(
                scanner._trial_summary(legacy, "busco un libro"),
                {"days": 1, "discovered": 4, "eligible": 3},
            )

    def test_record_trial_rejects_bad_identity_and_clamps_counts(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "trials.csv"
            with self.assertRaises(ValueError):
                scanner._record_trial_result(
                    path, "", 1, 1, date="2026-09-25"
                )
            with self.assertRaises(ValueError):
                scanner._record_trial_result(
                    path, "fantasía", 1, 1, date="25/09/2026"
                )
            scanner._record_trial_result(
                path, "fantasía", 2, 99, date="2026-09-25"
            )
            self.assertEqual(
                scanner._trial_summary(path, "fantasía")["eligible"],
                2,
            )

    def test_pick_seed_does_not_write_cooldown_and_skips_recent(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "seeds.csv"
            with open(path, "w", newline="", encoding="utf-8") as stream:
                w = csv.writer(stream)
                w.writerow(["fecha", "post_url"])
                w.writerow([
                    __import__("datetime").date.today().isoformat(),
                    "https://twitter.com/Reciente/status/1",
                ])

            before = path.read_text(encoding="utf-8")
            with patch.object(scanner, "SEEDS_CSV", str(path)):
                picked = scanner._pick_seed_urls(
                    [
                        "https://x.com/Reciente/status/1",
                        "https://x.com/Nueva/status/2",
                    ],
                    n=1,
                )
            self.assertEqual(picked, ["https://x.com/Nueva/status/2"])
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_successful_seed_record_is_canonical_and_idempotent_per_day(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "seeds.csv"
            first = scanner._record_successful_seed(
                path,
                "https://twitter.com/Lectora/status/123?ref=x",
                date="2026-09-28",
            )
            second = scanner._record_successful_seed(
                path,
                "https://x.com/Lectora/status/123",
                date="2026-09-28",
            )
            self.assertTrue(first)
            self.assertFalse(second)
            with open(path, encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(
                rows,
                [{
                    "fecha": "2026-09-28",
                    "post_url": "https://x.com/Lectora/status/123",
                }],
            )

    def _configure_scan_stubs(self, *, notifications=None, article_rows=None):
        x._connect = lambda: (
            types.SimpleNamespace(stop=lambda: None),
            FakePage(),
        )
        x._health_check = lambda pg: (True, "OK")
        x._notification_candidates = lambda pg: notifications or []
        x._dump_following_feed = lambda pg: None
        x._dump_list_feed = lambda *args: None
        x._dump_search = lambda *args: None
        x._dump_explore = lambda pg: None
        x._goto_status = lambda pg, url: None
        x._extract_articles = lambda pg, limit=10: article_rows or []
        # 06/10: el scan lee mas superficies (busqueda con scroll, personas, seguidores de semillas) y guarda en la reserva; aqui no hay navegador ni reserva real
        x.start_watchdog = lambda limit=300: None
        x.open_search = lambda pg, query, mode="live": None
        x.collect_posts_scrolling = lambda pg, passes=3, limit=60: []
        x.collect_account_rows = lambda pg, passes=3, limit=120: []
        x.collect_followers = lambda pg, handle, passes=4, limit=120, kind="seguidores": ({}, [])
        os.environ["RRSS_X_POOL_PATH"] = os.path.join(tempfile.mkdtemp(), "pool.sqlite3")

    def test_notification_url_is_not_attributed_to_other_avatar(self):
        self._configure_scan_stubs(
            notifications=[{
                "url": "https://x.com/AutoraReal/status/123",
                "handles": ["OtraCuenta"],
                "kind_hint": "reply_recibido",
                "text": "Respuesta",
            }]
        )
        with tempfile.TemporaryDirectory() as td, \
             patch.object(scanner, "QUERY_TRIALS_CSV", os.path.join(td, "trials.csv")), \
             patch.object(scanner, "CANDIDATES_JSON", (os.path.join(td, "trials.csv")) + ".cands.json"), \
             patch.object(scanner, "SEEDS_CSV", os.path.join(td, "seeds.csv")), \
             patch.object(scanner.sc, "known_accounts", return_value={}), \
             patch.object(scanner.sc, "already_interacted_urls", return_value=set()), \
             patch.object(scanner.sc, "discarded_handles", return_value=set()), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            scanner.scan()
        self.assertNotIn("@otracuenta", output.getvalue())
        self.assertNotIn("@autorareal", output.getvalue())

    def test_own_post_in_notifications_is_not_suggested(self):
        self._configure_scan_stubs(
            notifications=[
                {
                    "url": "https://x.com/DAVIDPORTODIAZ/status/123",
                    "handles": ["DAVIDPORTODIAZ"],
                    "kind_hint": "reply_recibido",
                    "text": "Respuesta propia",
                },
                {
                    "url": "https://x.com/Lectora/status/456",
                    "handles": ["Lectora"],
                    "kind_hint": "reply_recibido",
                    "text": "Un libro",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as td, \
             patch.object(scanner, "QUERY_TRIALS_CSV", os.path.join(td, "trials.csv")), \
             patch.object(scanner, "CANDIDATES_JSON", (os.path.join(td, "trials.csv")) + ".cands.json"), \
             patch.object(scanner, "SEEDS_CSV", os.path.join(td, "seeds.csv")), \
             patch.object(scanner.sc, "known_accounts", return_value={}), \
             patch.object(scanner.sc, "already_interacted_urls", return_value=set()), \
             patch.object(scanner.sc, "discarded_handles", return_value=set()), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            scanner.scan()
        lines = output.getvalue()
        self.assertIn("sugerido=reply | @lectora", lines)
        self.assertNotIn("sugerido=reply | @davidportodiaz", lines)

    def test_failed_seed_thread_does_not_consume_cooldown(self):
        self._configure_scan_stubs(article_rows=[])

        def feed(pg):
            print("URL: https://x.com/Autora/status/10")
            print("Fantasía")
            print("---")

        x._dump_following_feed = feed

        with tempfile.TemporaryDirectory() as td:
            seeds = os.path.join(td, "seeds.csv")
            trials = os.path.join(td, "trials.csv")
            with patch.object(scanner, "SEEDS_CSV", seeds), \
                 patch.object(scanner, "QUERY_TRIALS_CSV", trials), \
                 patch.object(scanner, "CANDIDATES_JSON", (trials) + ".cands.json"), \
                 patch.object(scanner.sc, "known_accounts", return_value={}), \
                 patch.object(scanner.sc, "already_interacted_urls", return_value=set()), \
                 patch.object(scanner.sc, "discarded_handles", return_value=set()), \
                 contextlib.redirect_stdout(io.StringIO()):
                scanner.scan()
            self.assertFalse(os.path.exists(seeds))

    def test_verified_seed_thread_consumes_cooldown_once(self):
        self._configure_scan_stubs(
            article_rows=[
                ("/Comentarista/status/20", "¿Qué fantasía recomiendas?")
            ]
        )

        def feed(pg):
            print("URL: https://x.com/Autora/status/10")
            print("Fantasía")
            print("---")

        x._dump_following_feed = feed
        x.collect_posts_scrolling = lambda pg, passes=3, limit=60: [
            {"handle": "Autora", "url": "https://x.com/Autora/status/10", "text": "Fantasía y novela juvenil", "lang": "es", "age_hours": 2.0, "repost": False, "pinned": False}]

        with tempfile.TemporaryDirectory() as td:
            seeds = os.path.join(td, "seeds.csv")
            trials = os.path.join(td, "trials.csv")
            with patch.object(scanner, "SEEDS_CSV", seeds), \
                 patch.object(scanner, "QUERY_TRIALS_CSV", trials), \
                 patch.object(scanner, "CANDIDATES_JSON", (trials) + ".cands.json"), \
                 patch.object(scanner.sc, "known_accounts", return_value={}), \
                 patch.object(scanner.sc, "already_interacted_urls", return_value=set()), \
                 patch.object(scanner.sc, "discarded_handles", return_value=set()), \
                 contextlib.redirect_stdout(io.StringIO()):
                scanner.scan()
            with open(seeds, encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                rows[0]["post_url"],
                "https://x.com/Autora/status/10",
            )


if __name__ == "__main__":
    unittest.main()
