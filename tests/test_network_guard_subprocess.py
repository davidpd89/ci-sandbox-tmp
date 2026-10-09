"""Python hijo del test debe heredar el mismo bloqueo; sin red real."""
import os
import subprocess
import sys
import unittest


CHILD = (
    "from test_network_guard import _INSTALLED;"
    "assert _INSTALLED, 'child_without_guard';"
    "import socket;"
    "sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
    "sock.connect(('203.0.113.23',443))"
)
CHILD_DNS = (
    "from test_network_guard import _INSTALLED;"
    "assert _INSTALLED, 'child_without_guard';"
    "import socket;"
    "socket.getaddrinfo('mastodon.social',443)"
)


class OfflineSubprocessTests(unittest.TestCase):
    def run_child(self, code):
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )

    def test_child_blocks_external_tcp(self):
        child = self.run_child(CHILD)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn("RRSS_TEST_RED_EXTERNA_BLOQUEADA:conexion", child.stderr)

    def test_child_blocks_dns_before_resolution(self):
        child = self.run_child(CHILD_DNS)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn("RRSS_TEST_RED_EXTERNA_BLOQUEADA:dns", child.stderr)

    def test_proxy_environment_is_cleared_for_parent_and_child(self):
        keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                "http_proxy", "https_proxy", "all_proxy", "no_proxy")
        self.assertTrue(all(key not in os.environ for key in keys))
        child = self.run_child(
            "import os; print(int(not any(k in os.environ for k in " + repr(keys) + ")))"
        )
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(child.stdout.strip(), "1")


if __name__ == "__main__":
    unittest.main()
