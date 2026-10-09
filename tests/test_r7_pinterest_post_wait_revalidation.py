"""R7 Pinterest: no superar cupo diario ni duplicar página tras esperar Edge.

Sin navegador, red, imagen real ni CSV operativo: todos los adaptadores son
inyectados por mocks. Se ejecuta el main auténtico con los límites originales.
"""
import contextlib
import csv
import datetime
import os
import tempfile
import sys
import pathlib
import types
import unittest
from unittest import mock
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import pinterest_daily_pins as pins
import action_ledger
import circuit_breaker

A = "https://autorademodiaz.com/recursos/uno"
B = "https://autorademodiaz.com/recursos/dos"


class PinterestWaitTests(unittest.TestCase):
    def scenario(self, *, after_count=0, after_used=(), holdoffs=None, error=None, apply=True):
        events = []
        state = {"locked": False, "published": 0}
        published = []
        fake = types.ModuleType("pinterest_publish")

        def publish(image, title, description, url, alt, board, apply=False, before_submit=None):
            self.assertTrue(state["locked"])
            events.append("publish")
            if error:
                raise RuntimeError(error)
            if before_submit is not None:
                before_submit()
            published.append(url)
            return f"https://pinterest.com/pin/{len(published)}"

        fake.publish_pin = publish

        @contextlib.contextmanager
        def exclusive(*args, **kwargs):
            state["locked"] = True
            events.append("enter")
            try:
                yield
            finally:
                state["locked"] = False
                events.append("exit")

        def count(today=None):
            return (after_count if state["locked"] else 0) + state["published"]

        def used():
            return set(after_used if state["locked"] else ()) | set(published)

        def prepare(url):
            return {"url": url, "title": "Título real de prueba", "board": "Recursos para escritores",
                    "description": "Una descripción de prueba", "alt": "Texto ALT de prueba"}

        def fake_sleep(seconds):
            self.assertFalse(state["locked"], "la espera no debe ocupar el Edge")
            events.append("sleep")

        def append(row):
            self.assertTrue(state["locked"])
            if row[-1] == "publicado":
                state["published"] += 1
                events.append("record")
            elif row[-1] == "pendiente_verificacion":
                events.append("intent")
            else:
                events.append("error")

        with mock.patch.dict(sys.modules, {"pinterest_publish": fake}), \
             mock.patch.object(action_ledger, "browser_session", side_effect=exclusive), \
             mock.patch.object(pins, "sitemap_urls", return_value=[A, B]), \
             mock.patch.object(pins, "used_links", side_effect=used), \
             mock.patch.object(pins, "today_count", side_effect=count), \
             mock.patch.object(pins, "failed_cooldowns", return_value=holdoffs or {}), \
             mock.patch.object(pins, "prepare", side_effect=prepare), \
             mock.patch.object(pins, "render", return_value="ficticia.png"), \
             mock.patch.object(pins, "_append", side_effect=append), \
             mock.patch.object(circuit_breaker, "check", return_value=(True, "")), \
             mock.patch.object(circuit_breaker, "record"), \
             mock.patch("time.sleep", side_effect=fake_sleep):
            argv = ["--max", "2"]
            if apply:
                argv.insert(0, "--apply")
                for url in (A, B):
                    item = prepare(url)
                    argv.extend(["--approve-pin", url, pins.approval_token(item)])
            result = pins.main(argv)
        return result, published, events

    def test_quota_filled_during_wait_never_publishes(self):
        result, published, events = self.scenario(after_count=5)
        self.assertEqual(result, 0)
        self.assertEqual(published, [])

    def test_one_place_left_after_wait_publishes_only_one(self):
        result, published, events = self.scenario(after_count=4)
        self.assertEqual(result, 0)
        self.assertEqual(len(published), 1)
        self.assertEqual(events.count("record"), 1)

    def test_link_used_during_wait_is_skipped_without_stopping_others(self):
        result, published, events = self.scenario(after_used={A})
        self.assertEqual(result, 0)
        self.assertEqual(published, [B])
        self.assertLess(events.index("record"), len(events) - 1)
        self.assertEqual(events[-1], "exit")

    def test_pause_between_two_pins_is_outside_edge_lock(self):
        result, published, events = self.scenario()
        self.assertEqual(result, 0)
        self.assertCountEqual(published, [A, B])
        self.assertEqual(events.count("sleep"), 1)
        self.assertEqual(events[:6], ["enter", "publish", "intent", "record", "exit", "sleep"])
        self.assertEqual(events[6:], ["enter", "publish", "intent", "record", "exit"])

    def test_three_fails_in_24h_pause_only_that_page(self):
        now = datetime.datetime(2026, 10, 8, 18, 0)
        with tempfile.TemporaryDirectory() as folder:
            csv_file = os.path.join(folder, "pins_auto.csv")
            with open(csv_file, "w", newline="", encoding="utf-8") as stream:
                w = csv.writer(stream)
                w.writerow(["fecha_hora", "pagina", "titulo", "tablero", "pin_url", "resultado"])
                for minute in (3, 6, 9):
                    w.writerow([(now - datetime.timedelta(minutes=minute)).isoformat(timespec="minutes"),
                                A, "Prueba", "Tablero", "", "fallo:TimeoutError:sin respuesta"])
                w.writerow([(now - datetime.timedelta(minutes=6)).isoformat(timespec="minutes"),
                            B, "Otra página", "Tablero", "", "fallo:TimeoutError:sin respuesta"])
            held = pins.failed_cooldowns(now=now, path=csv_file)
            self.assertIn(A, held)
            self.assertNotIn(B, held)
            self.assertGreater(held[A], now)

    def test_holdoff_page_is_skipped_without_stopping_other_page(self):
        result, published, _ = self.scenario(holdoffs={A: datetime.datetime.now()})
        self.assertEqual(result, 0)
        self.assertEqual(published, [B])

    def test_auth_or_rate_signal_stops_batch_and_releases_edge(self):
        for message in ("HTTP 429: Too Many Requests", "captcha obligatorio"):
            with self.subTest(message=message):
                result, published, events = self.scenario(error=message)
                self.assertEqual(result, 0)
                self.assertEqual(published, [])
                self.assertEqual(events.count("publish"), 1)
                self.assertIn("exit", events)

    def test_preview_has_no_publication_or_browser_turn(self):
        result, published, events = self.scenario(apply=False)
        self.assertEqual(result, 0)
        self.assertEqual(published, [])
        self.assertNotIn("enter", events)



class PinterestDurabilityTests(unittest.TestCase):
    """Flujo real scan->plan->preflight->registro, sin red ni navegador."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = os.path.join(self.temp.name, "pins_auto.csv")

    def run_batch(self, publish, urls=(A,), *, approved_urls=None, breaker_open=False, busy=False):
        fake = types.ModuleType("pinterest_publish")
        fake.publish_pin = publish

        @contextlib.contextmanager
        def turn(*args, **kwargs):
            if busy:
                raise action_ledger.RoundBusy("Edge usado por otro proceso")
            yield

        def prepare(url):
            return {"url": url, "title": "Título de prueba",
                    "board": "Recursos para escritores",
                    "description": "Descripción de prueba", "alt": "Texto alternativo"}

        with mock.patch.dict(sys.modules, {"pinterest_publish": fake}), \
             mock.patch.object(pins, "LOG", self.log), \
             mock.patch.object(pins, "PUBLISH_LOG", os.path.join(self.temp.name, "external.csv")), \
             mock.patch.object(pins, "NETWORK_DIR", self.temp.name), \
             mock.patch.object(action_ledger, "browser_session", side_effect=turn), \
             mock.patch.object(pins, "sitemap_urls", return_value=list(urls)), \
             mock.patch.object(pins, "prepare", side_effect=prepare), \
             mock.patch.object(pins, "render", return_value="ficticia.png"), \
             mock.patch.object(pins.glob, "glob", return_value=[]), \
             mock.patch.object(circuit_breaker, "check",
                               return_value=(not breaker_open, "rate" if breaker_open else "")), \
             mock.patch.object(circuit_breaker, "record") as record, \
             mock.patch("time.sleep"):
            argv = ["--apply", "--max", "2"]
            for url in (approved_urls if approved_urls is not None else urls):
                argv.extend(["--approve-pin", url, pins.approval_token(prepare(url))])
            result = pins.main(argv)
        return result, record

    def test_timeout_after_click_preserves_intent_and_never_reposts(self):
        attempts = []

        def publisher(image, title, desc, url, alt, board, apply=False, before_submit=None):
            before_submit()
            attempts.append(url)
            raise TimeoutError("confirmación remota no recibida")

        result, _ = self.run_batch(publisher)
        self.assertEqual(result, 2)
        self.assertEqual(attempts, [A])
        with mock.patch.object(pins, "LOG", self.log), \
             mock.patch.object(pins, "PUBLISH_LOG", os.path.join(self.temp.name, "external.csv")), \
             mock.patch.object(pins.glob, "glob", return_value=[]):
            self.assertEqual(pins.today_count(), 1)
            self.assertIn(A, pins.used_links())
        result, _ = self.run_batch(publisher)
        self.assertEqual(result, 0)
        self.assertEqual(attempts, [A])

    def test_preflight_rejects_without_poisoning_url(self):
        attempts = []

        def publisher(image, title, desc, url, alt, board, apply=False, before_submit=None):
            attempts.append(url)
            if len(attempts) == 1:
                raise ValueError("campo obligatorio no válido antes del clic")
            before_submit()
            return "https://es.pinterest.com/pin/123"

        result, _ = self.run_batch(publisher)
        self.assertEqual(result, 0)
        result, _ = self.run_batch(publisher)
        self.assertEqual(result, 0)
        self.assertEqual(attempts, [A, A])
        with mock.patch.object(pins, "LOG", self.log), \
             mock.patch.object(pins, "PUBLISH_LOG", os.path.join(self.temp.name, "external.csv")):
            self.assertEqual(pins.today_count(), 1)
            rows = pins._log_rows()
        self.assertEqual([r["resultado"] for r in rows],
                         ["fallo:ValueError:campo obligatorio no válido antes del clic",
                          "pendiente_verificacion", "publicado"])

    def test_csv_failure_after_remote_success_does_not_allow_resend(self):
        real_append = pins._append
        attempts = []

        def flaky_append(row):
            if row[-1] == "publicado":
                raise PermissionError("Excel tiene el CSV abierto")
            real_append(row)

        def publisher(image, title, desc, url, alt, board, apply=False, before_submit=None):
            before_submit()
            attempts.append(url)
            return "https://es.pinterest.com/pin/123"

        with mock.patch.object(pins, "_append", side_effect=flaky_append):
            result, _ = self.run_batch(publisher)
        self.assertEqual(result, 2)
        result, _ = self.run_batch(publisher)
        self.assertEqual(result, 0)
        self.assertEqual(attempts, [A])

    def test_invalid_header_and_truncated_record_fail_closed(self):
        called = []

        def publisher(*args, **kwargs):
            called.append(True)
            return "https://es.pinterest.com/pin/123"

        for content in ("mal,cabecera\n2026-10-08,x\n",
                        "fecha_hora,pagina,titulo,tablero,pin_url,resultado\n"
                        "2026-10-08T10:00,x,a,b,,publicado,extra\n"):
            with self.subTest(content=content[:20]):
                with open(self.log, "w", encoding="utf-8") as stream:
                    stream.write(content)
                with self.assertRaises(ValueError):
                    self.run_batch(publisher)
        self.assertEqual(called, [])

    def test_permission_error_does_not_mean_empty_quota(self):
        def publisher(*args, **kwargs):
            self.fail("no se debe publicar al perder la fuente de verdad")
        with mock.patch.object(pins, "_log_rows", side_effect=PermissionError("CSV bloqueado")):
            with self.assertRaises(PermissionError):
                self.run_batch(publisher)

    def test_pending_and_published_one_url_count_once(self):
        date = datetime.date.today().isoformat()
        with open(self.log, "w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(pins.LOG_HEADER)
            for status in ("pendiente_verificacion", "publicado"):
                writer.writerow([date + "T10:00", A, "Título", "Tablero", "", status])
        with mock.patch.object(pins, "LOG", self.log), \
             mock.patch.object(pins, "PUBLISH_LOG", os.path.join(self.temp.name, "external.csv")):
            self.assertEqual(pins.today_count(), 1)

    def test_rate_signal_opens_persistent_breaker_and_releases_turn(self):
        def publisher(*args, **kwargs):
            raise RuntimeError("HTTP 429 Too Many Requests")
        result, record = self.run_batch(publisher)
        self.assertEqual(result, 0)
        record.assert_called_once()
        self.assertEqual(record.call_args.kwargs["signal"], "rate")

    def test_open_breaker_prevents_submission(self):
        def publisher(*args, **kwargs):
            self.fail("no se puede publicar con breaker abierto")
        result, _ = self.run_batch(publisher, breaker_open=True)
        self.assertEqual(result, 0)

    def test_edge_busy_exits_without_submitting(self):
        def publisher(*args, **kwargs):
            self.fail("Edge no estaba disponible")
        result, _ = self.run_batch(publisher, busy=True)
        self.assertEqual(result, 0)

    def test_ttl_expires_after_oldest_failure_leaves_window(self):
        now = datetime.datetime(2026, 10, 8, 18, 0)
        with open(self.log, "w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(pins.LOG_HEADER)
            for hours in (23, 12, 1):
                writer.writerow([(now - datetime.timedelta(hours=hours)).isoformat(),
                                 A, "Título", "Tablero", "", "fallo:TimeoutError"])
        self.assertIn(A, pins.failed_cooldowns(now=now, path=self.log))
        # El primer fallo ya salió de las 24h recientes, pero la sanción
        # activada sigue vigente hasta 24h desde el tercer fallo.
        still_held = pins.failed_cooldowns(
            now=now + datetime.timedelta(hours=2), path=self.log)
        self.assertIn(A, still_held)
        self.assertEqual(still_held[A], now + datetime.timedelta(hours=23))
        self.assertNotIn(A, pins.failed_cooldowns(
            now=now + datetime.timedelta(hours=23), path=self.log))


    def test_cooldown_requires_three_failures_in_same_24h(self):
        now = datetime.datetime(2026, 10, 8, 18, 0)
        with open(self.log, "w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(pins.LOG_HEADER)
            for hours in (46, 24, 1):
                writer.writerow([(now - datetime.timedelta(hours=hours)).isoformat(),
                                 A, "T", "Board", "", "fallo:TimeoutError"])
        self.assertNotIn(A, pins.failed_cooldowns(now=now, path=self.log))

    def test_cooldown_boundary_24h_exact_is_not_active(self):
        now = datetime.datetime(2026, 10, 8, 18, 0)
        third = now - datetime.timedelta(hours=24)
        with open(self.log, "w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(pins.LOG_HEADER)
            for minutes in (2, 1, 0):
                writer.writerow([(third - datetime.timedelta(minutes=minutes)).isoformat(),
                                 A, "T", "Board", "", "fallo:TimeoutError"])
        self.assertNotIn(A, pins.failed_cooldowns(now=now, path=self.log))

    def test_invalid_quoted_csv_fails_closed(self):
        with open(self.log, "w", encoding="utf-8") as stream:
            stream.write(",".join(pins.LOG_HEADER) + "\n")
            stream.write('2026-10-08T10:00,https://example.com,"unclosed')
        with mock.patch.object(pins, "LOG", self.log):
            with self.assertRaises(ValueError):
                pins._log_rows()

    def test_missing_middle_field_and_duplicate_header_fail_closed(self):
        with open(self.log, "w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(pins.LOG_HEADER)
            writer.writerow(["2026-10-08T10:00", A, "T", "Board", "publicado"])
        with mock.patch.object(pins, "LOG", self.log):
            with self.assertRaises(ValueError):
                pins._log_rows()
        with open(self.log, "w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(list(pins.LOG_HEADER) + ["resultado"])
            writer.writerow(["2026-10-08T10:00", A, "T", "Board", "",
                             "publicado", "publicado"])
        with mock.patch.object(pins, "LOG", self.log):
            with self.assertRaises(ValueError):
                pins._log_rows()

    def test_timezone_iso_failure_stays_comparable(self):
        now = datetime.datetime(2026, 10, 8, 18, 0)
        with open(self.log, "w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(pins.LOG_HEADER)
            for minutes in (1, 2, 3):
                at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes)
                writer.writerow([at.isoformat(), A, "T", "Board", "",
                                 "fallo:TimeoutError"])
        # Se comprueba que no haya TypeError al comparar fechas aware/naive.
        self.assertIsInstance(pins.failed_cooldowns(path=self.log), dict)


def _synthetic_pin_image(case):
    """Fixture real para el contrato de subida: no simular solo os.path.exists."""
    temp = tempfile.TemporaryDirectory()
    case.addCleanup(temp.cleanup)
    filename = os.path.join(temp.name, "pin.png")
    Image.new("RGB", (100, 150)).save(filename, format="PNG")
    return filename


class PinterestActionabilityTests(unittest.TestCase):
    """Un botón no accionable no debe bloquear la URL por falso envío."""

    def test_click_trial_rejects_before_durable_intent(self):
        import pinterest_publish as publisher
        image = _synthetic_pin_image(self)
        page = mock.MagicMock()
        button = page.get_by_role.return_value.first
        button.click.side_effect = RuntimeError("botón deshabilitado")
        browser = mock.MagicMock()
        browser.contexts = [mock.MagicMock(new_page=lambda: page)]
        session = mock.MagicMock()
        session.chromium.connect_over_cdp.return_value = browser
        client = mock.MagicMock()
        client.start.return_value = session
        before = mock.Mock()
        with mock.patch.object(publisher, "sync_playwright", return_value=client), \
             mock.patch.object(publisher, "_check"), \
             mock.patch.object(publisher, "_assert_account"), \
             mock.patch.object(publisher, "_fill"), \
             mock.patch.object(publisher, "_verify", return_value=[]), \
             mock.patch.object(publisher, "delete_drafts"):
            with self.assertRaisesRegex(RuntimeError, "deshabilitado"):
                publisher.publish_pin(
                    image, "Título", "Descripción", A, "Alt",
                    "Recursos para escritores", apply=True,
                    before_submit=before)
        before.assert_not_called()
        button.click.assert_called_once_with(trial=True)


class PinterestExplicitApprovalTests(unittest.TestCase):
    def test_auto_apply_without_individual_review_never_scans_or_publishes(self):
        with mock.patch.object(pins, "sitemap_urls") as fetch, \
             mock.patch.object(pins, "render") as render, \
             mock.patch.object(pins, "today_count") as counter:
            result = pins.main(["--apply", "--max", "2"])
        self.assertEqual(result, 2)
        fetch.assert_not_called()
        render.assert_not_called()
        counter.assert_not_called()

    def test_approval_changes_with_title_or_description(self):
        item = dict(url=A, title="Título", description="Texto",
                    board="Recursos para escritores", alt="Alt")
        first = pins.approval_token(item)
        self.assertEqual(len(first), 16)
        self.assertEqual(first, pins.approval_token(dict(item)))
        self.assertNotEqual(first, pins.approval_token({**item, "title": "Título nuevo"}))
        self.assertNotEqual(first, pins.approval_token({**item, "description": "Texto nuevo"}))
        self.assertNotEqual(first, pins.approval_token({**item, "board": "Otro tablero"}))

    def test_approval_only_accepts_https_from_own_site(self):
        for url in ("http://autorademodiaz.com/recursos/uno",
                    "https://autorademodiaz.com.evil.example/recursos/uno",
                    "https://other.example/recursos/uno",
                    "https://autorademodiaz.com/recursos/uno?tracking=123"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                pins.selected_pin_approvals(["--approve-pin", url, "a" * 16])

    def test_only_explicitly_selected_candidate_can_be_published(self):
        case = PinterestDurabilityTests(methodName="runTest")
        case.setUp()
        self.addCleanup(case.tearDown)
        calls = []
        def publisher(image, title, description, url, alt, board,
                      apply=False, before_submit=None):
            before_submit()
            calls.append(url)
            return "https://es.pinterest.com/pin/123"
        result, _ = case.run_batch(publisher, urls=(A, B), approved_urls=(A,))
        self.assertEqual(result, 0)
        self.assertEqual(calls, [A])

    def test_approved_url_but_changed_text_is_not_published(self):
        fake = types.ModuleType("pinterest_publish")
        fake.publish_pin = mock.Mock(side_effect=AssertionError("nunca publicar"))
        reviewed = {"url": A, "title": "Título antiguo",
                    "description": "Texto antiguo", "board": "Recursos para escritores",
                    "alt": "Alt antiguo"}
        actual = dict(reviewed, title="Título diferente")
        with mock.patch.dict(sys.modules, {"pinterest_publish": fake}), \
             mock.patch.object(pins, "today_count", return_value=0), \
             mock.patch.object(pins, "failed_cooldowns", return_value={}), \
             mock.patch.object(pins, "used_links", return_value=set()), \
             mock.patch.object(pins, "sitemap_urls", return_value=[A]), \
             mock.patch.object(pins, "prepare", return_value=actual), \
             mock.patch.object(pins, "render") as render:
            result = pins.main(["--apply", "--approve-pin", A,
                                pins.approval_token(reviewed)])
        self.assertEqual(result, 0)
        render.assert_not_called()
        fake.publish_pin.assert_not_called()


class PinterestNoDestructiveDraftTests(unittest.TestCase):
    """Un clic incierto nunca puede borrar borradores preexistentes."""

    def _call(self, *, apply, click_error=False):
        import pinterest_publish as publisher
        image = _synthetic_pin_image(self)
        pg = mock.MagicMock()
        button = pg.get_by_role.return_value.first
        if click_error:
            def click(*args, **kwargs):
                if kwargs.get("trial"):
                    return None
                raise TimeoutError("navigation after click failed")
            button.click.side_effect = click
        browser = mock.MagicMock()
        browser.contexts = [mock.Mock(new_page=lambda: pg)]
        client = mock.MagicMock()
        client.start.return_value = mock.Mock(chromium=mock.Mock(
            connect_over_cdp=lambda *_: browser), stop=mock.Mock())
        before = mock.Mock()
        with mock.patch.object(publisher, "sync_playwright", return_value=client), \
             mock.patch.object(publisher.os.path, "exists", return_value=True), \
             mock.patch.object(publisher, "_check"), \
             mock.patch.object(publisher, "_assert_account"), \
             mock.patch.object(publisher, "_fill"), \
             mock.patch.object(publisher, "_verify", return_value=[]), \
             mock.patch.object(publisher, "delete_drafts") as cleanup:
            if click_error:
                with self.assertRaisesRegex(TimeoutError, "navigation after click failed"):
                    publisher.publish_pin(image, "Título", "Descripción", A, "ALT",
                                          "Recursos para escritores", apply=apply,
                                          before_submit=before)
            else:
                self.assertEqual(publisher.publish_pin(
                    image, "Título", "Descripción", A, "ALT",
                    "Recursos para escritores", apply=apply,
                    before_submit=before), "ensayo")
        return pg, cleanup, client, before

    def test_preview_is_offline_and_never_creates_or_deletes_drafts(self):
        pg, cleanup, client, before = self._call(apply=False)
        client.start.assert_not_called()
        pg.set_input_files.assert_not_called()
        cleanup.assert_not_called()
        before.assert_not_called()

    def test_timeout_after_click_preserves_drafts_and_intent(self):
        pg, cleanup, client, before = self._call(apply=True, click_error=True)
        before.assert_called_once()
        pg.get_by_role.return_value.first.click.assert_any_call()
        cleanup.assert_not_called()
        pg.close.assert_called_once()

    def test_never_cleans_old_drafts_before_upload(self):
        import pinterest_publish as publisher
        image = _synthetic_pin_image(self)
        pg = mock.MagicMock()
        button = pg.get_by_role.return_value.first
        button.click.side_effect = lambda *a, **kw: (
            None if kw.get("trial") else (_ for _ in ()).throw(TimeoutError("click uncertain")))
        client = mock.MagicMock()
        session = mock.MagicMock()
        client.start.return_value = session
        session.chromium.connect_over_cdp.return_value.contexts = [
            mock.Mock(new_page=lambda: pg)]
        with mock.patch.object(publisher, "sync_playwright", return_value=client), \
             mock.patch.object(publisher.os.path, "exists", return_value=True), \
             mock.patch.object(publisher, "_check"), \
             mock.patch.object(publisher, "_assert_account"), \
             mock.patch.object(publisher, "_fill"), \
             mock.patch.object(publisher, "_verify", return_value=[]), \
             mock.patch.object(publisher, "delete_drafts") as cleanup:
            with self.assertRaises(TimeoutError):
                publisher.publish_pin(image, "Título", "Descripción", A, "Alt",
                                      "Recursos para escritores", apply=True)
        cleanup.assert_not_called()


class PinterestCrossQuotaTests(unittest.TestCase):
    def test_scheduled_pins_consume_same_daily_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "daily.csv")
            scheduled = os.path.join(folder, "external.csv")
            day = datetime.date.today().isoformat()
            with open(scheduled, "w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["fecha_hora", "red", "ficha", "programada", "url"])
                for network in ("pinterest", "pinterest", "bluesky"):
                    writer.writerow([day + "T12:00", network, "ficha", day + " 11:00",
                                     "https://es.pinterest.com/pin/1"])
            with mock.patch.object(pins, "LOG", source), \
                 mock.patch.object(pins, "PUBLISH_LOG", scheduled):
                self.assertEqual(pins.today_count(), 2)

    def test_corrupt_scheduled_csv_cannot_be_treated_as_empty_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            scheduled = os.path.join(folder, "external.csv")
            with open(scheduled, "w", encoding="utf-8") as stream:
                stream.write("fecha_hora,red,ficha,programada,url\n")
                stream.write('2026-10-08,pinterest,"sin cerrar')
            with mock.patch.object(pins, "LOG", os.path.join(folder, "empty.csv")), \
                 mock.patch.object(pins, "PUBLISH_LOG", scheduled):
                with self.assertRaises(ValueError):
                    pins.today_count()


class PinterestDescriptionPreflightTests(unittest.TestCase):
    def test_form_description_mismatch_is_reported(self):
        import pinterest_publish as publisher
        page = mock.MagicMock()
        def locate(selector):
            field = mock.MagicMock()
            if selector == "#storyboard-selector-title":
                field.input_value.return_value = "Título"
            elif selector == "#WebsiteField":
                field.input_value.return_value = A
            elif selector.startswith('[role="combobox"]'):
                field.first.inner_text.return_value = "Otra descripción"
            elif selector.startswith('[data-test-id="board-dropdown'):
                field.first.inner_text.return_value = "Recursos para escritores"
            return field
        page.locator.side_effect = locate
        page.get_by_placeholder.return_value.input_value.return_value = "Texto alternativo"
        problems = publisher._verify(page, "Título", "Descripción correcta", A,
                                      "Texto alternativo", "Recursos para escritores")
        self.assertIn("descripcion", problems)
        self.assertNotIn("titulo", problems)

    def test_changed_form_after_trial_never_marks_remote_intent(self):
        import pinterest_publish as publisher
        image = _synthetic_pin_image(self)
        pg = mock.MagicMock()
        button = pg.get_by_role.return_value.first
        before = mock.Mock()
        session = mock.MagicMock()
        session.chromium.connect_over_cdp.return_value.contexts = [
            mock.Mock(new_page=lambda: pg)]
        api = mock.MagicMock()
        api.start.return_value = session
        with mock.patch.object(publisher, "sync_playwright", return_value=api), \
             mock.patch.object(publisher.os.path, "exists", return_value=True), \
             mock.patch.object(publisher, "_check"), \
             mock.patch.object(publisher, "_assert_account"), \
             mock.patch.object(publisher, "_fill"), \
             mock.patch.object(publisher, "_verify",
                               side_effect=[[], ["descripcion"]]), \
             mock.patch.object(publisher, "delete_drafts") as cleanup:
            with self.assertRaisesRegex(publisher.PinterestPublishError,
                                        "cambió durante el preflight"):
                publisher.publish_pin(image, "Título", "Descripción", A,
                                      "ALT", "Recursos para escritores",
                                      apply=True, before_submit=before)
        before.assert_not_called()
        button.click.assert_called_once_with(trial=True)
        cleanup.assert_not_called()

if __name__ == "__main__":
    unittest.main()
