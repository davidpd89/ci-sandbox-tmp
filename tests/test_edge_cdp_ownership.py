"""PR #58. Fakes de CDP: no arrancar Edge ni acceder a cuentas."""
import pathlib
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import browser_common as bc
import browser_lean
import edge_trim


class FakePage:
    def __init__(self, url="about:blank"):
        self.url = url
        self.routes = []
        self.closed = False
        self.fail_close = False
        self.timeouts = []

    def route(self, pattern, handler):
        self.routes.append((pattern, handler))

    def close(self):
        self.closed = True
        if self.fail_close:
            raise RuntimeError("Target closed")

    def is_closed(self):
        return self.closed

    def set_default_timeout(self, value):
        self.timeouts.append(("action", value))

    def set_default_navigation_timeout(self, value):
        self.timeouts.append(("navigation", value))


class FakeContext:
    def __init__(self, pages=()):
        self.pages = list(pages)
        self.created = []

    def new_page(self):
        pg = FakePage()
        self.created.append(pg)
        self.pages.append(pg)
        return pg


class FakeDriver:
    def __init__(self, contexts):
        self.contexts = contexts
        self.chromium = self
        self.calls = []
        self.fail = False
        self.connect_error = None
        self.stops = 0

    def connect_over_cdp(self, url, timeout=None):
        self.calls.append((url, timeout))
        if self.fail:
            raise RuntimeError("protocol detached")
        if self.connect_error is not None:
            raise self.connect_error
        return self

    def stop(self):
        self.stops += 1


class QuietWatchdog:
    def start(self):
        return None

    def stop(self):
        return None


class TestCDPOwnership(unittest.TestCase):
    def setUp(self):
        self.stranger = FakePage("https://x.com/lector")
        self.same_site = FakePage("https://x.com/home")
        self.ctx = FakeContext((self.stranger, self.same_site))
        self.driver = FakeDriver([self.ctx])
        self.patcher = mock.patch.object(
            bc, "sync_playwright",
            return_value=types.SimpleNamespace(start=lambda: self.driver),
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def new_browser(self):
        return bc.Browser(
            "x", "http://127.0.0.1:9223", {"x.com"}, watchdog=QuietWatchdog()
        )

    def test_session_only_closes_page_created_here(self):
        obj = self.new_browser()
        with obj.session() as own:
            self.assertEqual(own.url, "about:blank")
            self.assertNotIn(own, (self.stranger, self.same_site))
            self.assertEqual(own.timeouts, [("action", 15000), ("navigation", 30000)])
            self.assertEqual(own.routes[0][0], "**/*")
            keep_open, shared = obj.connect()
            self.assertIs(shared, own)
            keep_open.stop()
            self.assertFalse(own.closed)
        self.assertTrue(own.closed)
        self.assertFalse(self.stranger.closed)
        self.assertFalse(self.same_site.closed)
        self.assertEqual(self.driver.stops, 1)
        self.assertEqual(self.driver.calls, [("http://127.0.0.1:9223", 20000)])

    def test_connect_stop_is_idempotent_and_owned(self):
        owner, own = self.new_browser().connect()
        owner.stop()
        owner.stop()
        self.assertTrue(own.closed)
        self.assertFalse(self.same_site.closed)
        self.assertEqual(self.driver.stops, 1)

    def test_closed_target_does_not_block_playwright_stop(self):
        owner, own = self.new_browser().connect()
        own.fail_close = True
        owner.stop()
        self.assertEqual(self.driver.stops, 1)
        self.assertFalse(self.stranger.closed)

    def test_selector_exception_closes_only_own_tab(self):
        with self.assertRaises(ValueError):
            with self.new_browser().session() as own:
                raise ValueError("selector nulo")
        self.assertTrue(own.closed)
        self.assertFalse(self.stranger.closed)

    def test_cdp_detached_releases_driver(self):
        self.driver.fail = True
        with self.assertRaisesRegex(RuntimeError, "protocol detached"):
            self.new_browser().connect()
        self.assertEqual(self.driver.stops, 1)

    def test_cdp_timeout_is_not_retried_or_reported_as_success(self):
        self.driver.connect_error = TimeoutError("CDP sleeping target")
        with self.assertRaisesRegex(TimeoutError, "sleeping target"):
            self.new_browser().connect()
        self.assertEqual(self.driver.stops, 1)
        self.assertEqual(len(self.driver.calls), 1)
        self.assertEqual(len(self.ctx.created), 0)
        self.assertFalse(self.same_site.closed)

    def test_missing_context_refuses_profile_switch(self):
        self.driver.contexts = []
        with self.assertRaisesRegex(RuntimeError, "sin contexto"):
            self.new_browser().connect()
        self.assertEqual(self.driver.stops, 1)

    def test_shared_tab_closed_is_not_silently_reopened(self):
        obj = self.new_browser()
        with obj.session() as own:
            own.close()
            with self.assertRaisesRegex(RuntimeError, "cerrada"):
                obj.connect()
        self.assertEqual(len(self.ctx.created), 1)

    def test_nested_session_rejected_without_closing_stranger(self):
        obj = self.new_browser()
        with obj.session():
            with self.assertRaisesRegex(RuntimeError, "ya abierta"):
                with obj.session():
                    pass
        self.assertFalse(self.same_site.closed)

    def test_page_route_does_not_affect_context_or_personal_tab(self):
        own = FakePage()
        with mock.patch.dict("os.environ", {"RRSS_LEAN_BROWSER": "1"}):
            self.assertTrue(browser_lean.apply(own))
            self.assertTrue(browser_lean.apply(own))
            self.assertFalse(browser_lean.apply(self.ctx))
        self.assertEqual(len(own.routes), 1)
        self.assertEqual(self.stranger.routes, [])

    def test_environment_disables_lean_without_route(self):
        with mock.patch.dict("os.environ", {"RRSS_LEAN_BROWSER": "0"}):
            pg = FakePage()
            self.assertFalse(browser_lean.apply(pg))
            self.assertEqual(pg.routes, [])

    def test_trim_is_inert(self):
        lines = []
        self.assertEqual(edge_trim.trim(log=lines.append), 0)
        self.assertIn("0 pestañas", lines[0])
        self.assertFalse(self.stranger.closed)
        self.assertEqual(self.driver.calls, [])

    def test_watchdog_can_be_stopped_and_restarted(self):
        wd = bc.Watchdog("synthetic")
        with mock.patch.object(bc.threading, "Thread") as fake_thread:
            wd.start(limit=300)
            first = wd._cancel
            self.assertTrue(wd.started)
            wd.stop()
            self.assertFalse(wd.started)
            self.assertTrue(first.is_set())
            wd.start(limit=300)
            second = wd._cancel
            self.assertIsNot(first, second)
            wd.stop()
            self.assertTrue(second.is_set())
        self.assertEqual(fake_thread.return_value.start.call_count, 2)

    def test_watchdog_stop_during_cdp_session_cleanup(self):
        wd = bc.Watchdog("synthetic")
        with mock.patch.object(bc.threading, "Thread"):
            obj = bc.Browser("x", "http://127.0.0.1:9223", {"x.com"}, watchdog=wd)
            with obj.session():
                self.assertTrue(wd.started)
            self.assertFalse(wd.started)

    def test_connection_uses_no_defaults_if_supported(self):
        calls = []
        class ModernChromium:
            def connect_over_cdp(self, url, timeout=None, no_defaults=None):
                calls.append((url, timeout, no_defaults))
                return "connected"
        result = bc.connect_cdp(ModernChromium(), "http://127.0.0.1:9223")
        self.assertEqual(result, "connected")
        self.assertEqual(calls, [("http://127.0.0.1:9223", 20000, True)])

    def test_connection_legacy_does_not_retry(self):
        calls = []
        class LegacyChromium:
            def connect_over_cdp(self, url, timeout=None):
                calls.append((url, timeout))
                raise RuntimeError("CDP protocol detached")
        with self.assertRaisesRegex(RuntimeError, "detached"):
            bc.connect_cdp(LegacyChromium(), "http://127.0.0.1:9223")
        self.assertEqual(calls, [("http://127.0.0.1:9223", 20000)])

    def test_watchdog_clock_is_monotonic(self):
        with mock.patch.object(bc.time, "monotonic", return_value=55):
            wd = bc.Watchdog("test")
            self.assertEqual(wd.last, 55)
            wd.beat()
            self.assertEqual(wd.last, 55)


if __name__ == "__main__":
    unittest.main()
