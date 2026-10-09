import pathlib
import tempfile
import sys
import unittest
from unittest.mock import MagicMock, patch

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import mobile_client as mc
import mobile_runtime as mr


class MobileRuntimeTests(unittest.TestCase):
    def test_existing_server_with_missing_device_does_not_spawn_second_server(self):
        fake = MagicMock()
        fake.server_info.return_value = {"name": "mobilecli", "version": "1.0.17"}
        fake.select_device.side_effect = mc.MobileDeviceSelectionError("sin Xiaomi")
        with patch.object(mr, "MobileCliClient", return_value=fake),              patch.object(mr.subprocess, "Popen") as popen:
            with self.assertRaises(mc.MobileDeviceSelectionError):
                mr.ensure_server()
        popen.assert_not_called()

    def test_wrong_running_server_version_fails_without_spawn(self):
        fake = MagicMock()
        fake.server_info.return_value = {"name": "mobilecli", "version": "9.9.9"}
        with patch.object(mr, "MobileCliClient", return_value=fake),              patch.object(mr.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(mr.MobileRuntimeError, "inesperado"):
                mr.ensure_server()
        popen.assert_not_called()

    def test_windows_cmd_shim_uses_comspec(self):
        with patch.object(mr.os, "name", "nt"),              patch.dict(mr.os.environ, {"COMSPEC": "C:\\Windows\\System32\\cmd.exe"}):
            argv = mr._argv("C:\\npm\\mobilecli.cmd", "--version")
        self.assertEqual(argv[1:4], ["/d", "/s", "/c"])
        self.assertTrue(argv[4].endswith("mobilecli.cmd"))


    def test_mobile_session_lock_blocks_parallel_repo_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "mobile.lock")
            with mr.mobile_session_lock(path):
                with self.assertRaises(mr.MobileSessionBusy):
                    with mr.mobile_session_lock(path):
                        pass
            self.assertFalse(pathlib.Path(path).exists())
if __name__ == "__main__":
    unittest.main()


class StaleMobileLockTests(unittest.TestCase):
    def test_lock_of_dead_process_is_reclaimed_but_live_one_is_not(self):
        import os
        import tempfile
        import mobile_runtime as mr
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mobile.lock")
            with open(path, "w", encoding="ascii") as stream:
                stream.write("99999999:123")           # PID que no existe
            with mr.mobile_session_lock(path):
                pass
            with open(path, "w", encoding="ascii") as stream:
                stream.write(f"{os.getpid()}:123")     # proceso vivo: este mismo
            with self.assertRaises(mr.MobileSessionBusy):
                with mr.mobile_session_lock(path):
                    pass
