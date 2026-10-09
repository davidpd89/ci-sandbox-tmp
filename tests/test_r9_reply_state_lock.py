"""Regresiones del guard JSON independiente del singleton del trabajador."""
import pathlib
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from reply_state_lock import state_guard


class ReplyStateLockTests(unittest.TestCase):
    def test_serializes_threads_and_leaves_permanent_guard(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "pending.json"
            first = threading.Event()
            release = threading.Event()
            order = []
            def one():
                with state_guard(str(path)):
                    order.append("one")
                    first.set()
                    release.wait(3)
            def two():
                first.wait(3)
                with state_guard(str(path)):
                    order.append("two")
            a, b = threading.Thread(target=one), threading.Thread(target=two)
            a.start()
            b.start()
            self.assertTrue(first.wait(3))
            self.assertEqual(order, ["one"])
            release.set()
            a.join(3)
            b.join(3)
            self.assertFalse(a.is_alive())
            self.assertFalse(b.is_alive())
            self.assertEqual(order, ["one", "two"])
            self.assertTrue((path.parent / "reply_state.lock").exists())

    def test_reacquire_after_exception(self):
        with tempfile.TemporaryDirectory() as root:
            path = str(pathlib.Path(root) / "pending.json")
            with self.assertRaisesRegex(RuntimeError, "fallo"):
                with state_guard(path):
                    raise RuntimeError("fallo")
            with state_guard(path):
                pass


    def test_cross_process_exclusion_and_kill_recovers(self):
        import subprocess
        import time
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "pending.json"
            marker = pathlib.Path(root) / "owned"
            script = ("from reply_state_lock import state_guard\n"
                      "import sys,pathlib,time\n"
                      "with state_guard(sys.argv[1]):\n"
                      "    pathlib.Path(sys.argv[2]).write_text('ready')\n"
                      "    time.sleep(30)\n")
            child = subprocess.Popen(
                [sys.executable, "-c", script, str(path), str(marker)],
                env={**__import__("os").environ,
                     "PYTHONPATH": str(pathlib.Path(__file__).resolve().parents[1] / "tools")},
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            try:
                for _ in range(150):
                    if marker.exists() or child.poll() is not None:
                        break
                    time.sleep(0.02)
                self.assertTrue(marker.exists(), "el proceso hijo no adquirió el lock")
                with self.assertRaises(TimeoutError):
                    with state_guard(str(path), timeout=0.05):
                        self.fail("dos procesos poseen a la vez el guard")
            finally:
                child.kill() if child.poll() is None else None
                child.communicate(timeout=5)
            with state_guard(str(path), timeout=1):
                self.assertTrue((path.parent / "reply_state.lock").exists())


    def test_nested_guard_is_reentrant_in_same_thread(self):
        with tempfile.TemporaryDirectory() as root:
            path = str(pathlib.Path(root) / "pending.json")
            with state_guard(path):
                with state_guard(path, timeout=0.01):
                    self.assertTrue((pathlib.Path(root) / "reply_state.lock").exists())
            with state_guard(path, timeout=0.1):
                pass

if __name__ == "__main__":
    unittest.main()
