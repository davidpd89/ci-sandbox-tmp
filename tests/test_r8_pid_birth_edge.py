"""R8: PID vivo no implica propietario vivo tras reciclar identificador."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import action_ledger as al
import mechanical_round as mr
from process_identity import creation_token, valid_token


A = "w11111111111111111"
B = "w22222222222222222"


class ProcessBirthLockTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "rrss_lock_edge_browser.lock"

    def owner(self, birth=A):
        self.path.write_text(f"{os.getpid()} 1 {birth}", encoding="ascii")

    @unittest.skipUnless(os.name == "nt" or sys.platform.startswith("linux"),
                         "identidad nativa solo Windows/Linux")
    def test_current_process_has_birth_token(self):
        actual = creation_token(os.getpid())
        self.assertTrue(valid_token(actual), actual)
        self.assertEqual(creation_token(os.getpid()), actual)

    def test_recycled_pid_is_reclaimed_under_os_guard(self):
        self.owner()
        with mock.patch.object(al, "_pid_alive", return_value=True), \
             mock.patch.object(al, "creation_token", return_value=B):
            with al.exclusive("edge_browser", directory=self.folder.name):
                self.assertTrue(self.path.read_text().endswith(B))
        self.assertFalse(self.path.exists())

    def test_same_pid_same_birth_never_stolen(self):
        self.owner()
        with mock.patch.object(al, "_pid_alive", return_value=True), \
             mock.patch.object(al, "creation_token", return_value=A):
            with self.assertRaises(al.RoundBusy):
                with al.exclusive("edge_browser", directory=self.folder.name):
                    self.fail("lock válido robado")

    def test_uncertain_birth_fails_closed(self):
        self.owner()
        with mock.patch.object(al, "_pid_alive", return_value=True), \
             mock.patch.object(al, "creation_token", return_value=None):
            with self.assertRaises(al.RoundBusy):
                with al.exclusive("edge_browser", directory=self.folder.name):
                    self.fail("lock de identidad indeterminada robado")

    def test_legacy_owner_and_corrupt_birth_fail_closed(self):
        for owner in (f"{os.getpid()} 1", f"{os.getpid()} 1 no-es-token"):
            with self.subTest(owner=owner):
                self.path.write_text(owner, encoding="ascii")
                with mock.patch.object(al, "_pid_alive", return_value=True), \
                     mock.patch.object(al, "creation_token", return_value=B):
                    with self.assertRaises(al.RoundBusy):
                        with al.exclusive("edge_browser", directory=self.folder.name):
                            self.fail("PID legado/corrupto robado")

    @unittest.skipUnless(os.name == "nt" or sys.platform.startswith("linux"),
                         "identidad delegada requiere proceso nativo")
    def test_delegated_child_needs_matching_parent_birth(self):
        actual = creation_token(os.getpid())
        self.assertTrue(valid_token(actual), actual)
        cmd = [
            sys.executable, "-c",
            "import sys; sys.path.insert(0,sys.argv[1]);"
            "from action_ledger import _delegated_browser_owner as verify;"
            "print(verify('edge_browser',sys.argv[2]))",
            str(Path(al.__file__).parent), self.folder.name,
        ]
        with al.exclusive("edge_browser", directory=self.folder.name):
            for birth, expected in ((actual, "True"), (B, "False"), ("", "False")):
                with self.subTest(birth=birth):
                    env = {**os.environ,
                           "RRSS_BROWSER_LOCK_HELD": "edge_browser",
                           "RRSS_BROWSER_LOCK_OWNER_PID": str(os.getpid()),
                           "RRSS_BROWSER_LOCK_OWNER_BIRTH": birth}
                    child = subprocess.run(
                        cmd, env=env, capture_output=True, text=True, timeout=12,
                    )
                    self.assertEqual(child.returncode, 0, child.stderr)
                    self.assertEqual(child.stdout.strip(), expected)

    def test_default_runner_does_not_inherit_unowned_edge_markers(self):
        marker = {"RRSS_BROWSER_LOCK_HELD": "edge_browser",
                  "RRSS_BROWSER_LOCK_OWNER_PID": "12345",
                  "RRSS_BROWSER_LOCK_OWNER_BIRTH": A}
        with mock.patch.dict(os.environ, marker), \
             mock.patch.object(mr.subprocess, "run") as runner:
            token = mr._BROWSER_OWNER_PID.set(None)
            try:
                mr.default_runner([sys.executable, "-V"])
            finally:
                mr._BROWSER_OWNER_PID.reset(token)
        child_env = runner.call_args.kwargs["env"]
        self.assertFalse(any(key in child_env for key in marker))


if __name__ == "__main__":
    unittest.main()
