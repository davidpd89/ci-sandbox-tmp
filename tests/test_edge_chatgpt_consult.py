"""PR #58: ChatGPT por CDP con navegador completamente falso, sin cuentas/red."""
import contextlib
import itertools
import pathlib
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import action_ledger
import chatgpt_consult as cc
import playwright.sync_api


class FakeLocator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector
        self.first = self.last = self

    def click(self):
        self.page.sends += 1

    def fill(self, question):
        self.page.question = question

    def count(self):
        if self.selector == cc.ASSISTANT:
            return 1
        return 0

    def inner_text(self):
        return self.page.response


class FakePage:
    def __init__(self, *, fail_goto=False, url=None):
        self.url = cc.PROJECT_URL if url is None else url
        self.fail_goto = fail_goto
        self.closed = False
        self.question = None
        self.sends = 0
        self.response = "Una respuesta comprobada. " * 20
        self.waits = 0

    def goto(self, url, **kw):
        if self.fail_goto:
            raise RuntimeError("Target closed")

    def locator(self, selector):
        return FakeLocator(self, selector)

    def wait_for_timeout(self, ms):
        self.waits += 1

    def close(self):
        self.closed = True


class FakeCtx:
    def __init__(self, page):
        self.page = page

    def new_page(self):
        return self.page

    def grant_permissions(self, permissions):
        raise AssertionError("Nunca modificar permisos del contexto compartido")


class FakeDriver:
    def __init__(self, page):
        self.page = page
        self.stops = 0
        self.urls = []
        self.chromium = self

    def connect_over_cdp(self, url, timeout=None):
        self.urls.append((url, timeout))
        return types.SimpleNamespace(contexts=[FakeCtx(self.page)])

    def stop(self):
        self.stops += 1


class ConsultTests(unittest.TestCase):
    def run_consult(self, page, *, clock=None):
        driver = FakeDriver(page)
        with mock.patch.object(playwright.sync_api, "sync_playwright", return_value=types.SimpleNamespace(start=lambda: driver)), \
             mock.patch.object(cc, "browser_target", return_value=(9224, "chatgpt_browser")), \
             mock.patch.object(action_ledger, "browser_session", return_value=contextlib.nullcontext()), \
             mock.patch.object(cc.time, "monotonic", side_effect=clock or (lambda: next(itertools.count()))):
            try:
                result = cc.consult("¿Cómo mejorar esto?", wait_min=1)
                return result, driver
            except Exception:
                self.assertTrue(page.closed)
                self.assertEqual(driver.stops, 1)
                raise

    def test_success_closes_only_owned_page_and_uses_dedicated_turn(self):
        page = FakePage()
        sequence = itertools.count()
        result, driver = self.run_consult(page, clock=lambda: next(sequence))
        self.assertEqual(result, (page.response, page.url))
        self.assertTrue(page.closed)
        self.assertEqual(driver.stops, 1)
        self.assertEqual(driver.urls, [("http://127.0.0.1:9224", 20000)])
        self.assertEqual(page.question, "¿Cómo mejorar esto?")
        self.assertEqual(page.sends, 1)

    def test_navigation_failure_closes_page(self):
        with self.assertRaisesRegex(RuntimeError, "Target closed"):
            self.run_consult(FakePage(fail_goto=True))

    def test_wrong_project_redirect_never_sends(self):
        page = FakePage(url="https://chatgpt.com/g/otro-proyecto/project")
        with self.assertRaisesRegex(RuntimeError, "proyecto ChatGPT no verificable"):
            self.run_consult(page)
        self.assertEqual(page.sends, 0)
        self.assertIsNone(page.question)

    def test_cross_origin_redirect_never_sends(self):
        page = FakePage(url="https://chatgpt.com.ejemplo.invalid/g/" + cc.PROJECT_ID)
        with self.assertRaisesRegex(RuntimeError, "proyecto ChatGPT no verificable"):
            self.run_consult(page)
        self.assertEqual(page.sends, 0)

    def test_partial_answer_is_not_accepted_after_deadline(self):
        times = iter((0, 120))
        with self.assertRaisesRegex(RuntimeError, "no confirmada"):
            self.run_consult(FakePage(), clock=lambda: next(times))


if __name__ == "__main__":
    unittest.main()
