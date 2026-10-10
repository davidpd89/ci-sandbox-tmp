"""08/10: Edge dedicado a ChatGPT (9224) con su propio turno, para que el trabajador de respuestas no espere a las rondas web que ocupan el 9223."""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import chatgpt_consult as cc
import chatgpt_edge as ce


class BrowserTargetTests(unittest.TestCase):
    def test_uses_dedicated_edge_and_its_own_turn_when_up(self):
        with mock.patch.object(ce, "port_open", return_value=True):
            self.assertEqual(cc.browser_target(), (ce.PORT, "chatgpt_browser"))

    def test_falls_back_to_shared_edge_when_dedicated_is_down(self):
        with mock.patch.object(ce, "port_open", return_value=False):
            self.assertEqual(cc.browser_target(), (9223, "edge_browser"))

    def test_dedicated_edge_never_collides_with_the_web_rounds_port(self):
        self.assertNotEqual(ce.PORT, ce.SOURCE_PORT)
        self.assertEqual(ce.SOURCE_PORT, 9223)


class EdgeLaunchTests(unittest.TestCase):
    def test_arguments_use_own_profile_and_port(self):
<<<<<<< HEAD
        args = ce.edge_args(9224, r"C:\Temp\rrss-autorademo-chatgpt")
        self.assertIn("--remote-debugging-port=9224", args)
        self.assertIn(r"--user-data-dir=C:\Temp\rrss-autorademo-chatgpt", args)
        self.assertFalse(any("rrss-autorademo-edge" in a for a in args))      # nunca el perfil de las redes
=======
        args = ce.edge_args(9224, r"C:\Temp\rrss-davidporto-chatgpt")
        self.assertIn("--remote-debugging-port=9224", args)
        self.assertIn(r"--user-data-dir=C:\Temp\rrss-davidporto-chatgpt", args)
        self.assertFalse(any("rrss-davidporto-edge" in a for a in args))      # nunca el perfil de las redes
>>>>>>> origin/research/public-reuse-parent
        self.assertEqual(args[-1], "https://chatgpt.com/")

    def test_start_does_nothing_if_already_up(self):
        with mock.patch.object(ce, "port_open", return_value=True), mock.patch.object(ce.subprocess, "Popen") as popen:
            self.assertTrue(ce.start())
        popen.assert_not_called()

    def test_start_launches_edge_when_down_and_reports_failure(self):
        with mock.patch.object(ce, "port_open", return_value=False), mock.patch.object(ce.os.path, "exists", return_value=True), \
             mock.patch.object(ce.os, "makedirs"), mock.patch.object(ce.subprocess, "Popen") as popen, mock.patch.object(ce.time, "sleep"):
            self.assertFalse(ce.start(wait_seconds=0))
        self.assertTrue(popen.called)
        self.assertIn("--remote-debugging-port=9224", popen.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
