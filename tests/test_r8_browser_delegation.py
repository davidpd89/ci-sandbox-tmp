"""R8: delegación del turno Edge sin variables de entorno globales entre hilos.

Pruebas offline; no conectan a Edge, cuentas ni dispositivos.
"""
import os
import pathlib
import random
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import mechanical_round as mr


class DelegationContextTests(unittest.TestCase):
    def test_default_runner_passes_owner_only_to_its_child(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(mr.subprocess, "run") as fake:
                fake.return_value.returncode = 0
                fake.return_value.stdout = ""
                fake.return_value.stderr = ""
                token = mr._BROWSER_OWNER_PID.set(os.getpid())
                try:
                    mr.default_runner([sys.executable, "-V"])
                    delegated = fake.call_args.kwargs["env"]
                    self.assertEqual(delegated["RRSS_BROWSER_LOCK_HELD"], "edge_browser")
                    self.assertEqual(delegated["RRSS_BROWSER_LOCK_OWNER_PID"], str(os.getpid()))
                finally:
                    mr._BROWSER_OWNER_PID.reset(token)
                mr.default_runner([sys.executable, "-V"])
                normal = fake.call_args.kwargs["env"]
                self.assertNotIn("RRSS_BROWSER_LOCK_HELD", normal)
                self.assertNotIn("RRSS_BROWSER_LOCK_OWNER_PID", normal)

    def test_sibling_thread_does_not_inherit_execution_delegation(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(mr.subprocess, "run") as fake:
                fake.return_value.returncode = 0
                fake.return_value.stdout = ""
                fake.return_value.stderr = ""
                token = mr._BROWSER_OWNER_PID.set(os.getpid())
                try:
                    worker = threading.Thread(target=lambda: mr.default_runner([sys.executable, "-V"]))
                    worker.start()
                    worker.join(timeout=10)
                    self.assertFalse(worker.is_alive())
                    sibling = fake.call_args.kwargs["env"]
                    self.assertNotIn("RRSS_BROWSER_LOCK_HELD", sibling)
                    mr.default_runner([sys.executable, "-V"])
                    owner = fake.call_args.kwargs["env"]
                    self.assertEqual(owner["RRSS_BROWSER_LOCK_OWNER_PID"], str(os.getpid()))
                finally:
                    mr._BROWSER_OWNER_PID.reset(token)

    def test_round_context_is_set_only_inside_browser_turn(self):
        self.assertIsNone(mr._BROWSER_OWNER_PID.get())
        with tempfile.TemporaryDirectory() as directory:
            observed = []
            def fake_run(*args, **kwargs):
                observed.append(mr._BROWSER_OWNER_PID.get())
                return {"ok": True, "log": None}
            with mock.patch.object(mr, "LOCK_DIR", directory):
                with mock.patch.object(mr, "_run", side_effect=fake_run):
                    result = mr.run("x", dry=True, shape=False,
                                    rng=random.Random(1), out=lambda *_: None)
            self.assertTrue(result["ok"])
            self.assertEqual(observed, [os.getpid()])
            self.assertIsNone(mr._BROWSER_OWNER_PID.get())


if __name__ == "__main__":
    unittest.main()
