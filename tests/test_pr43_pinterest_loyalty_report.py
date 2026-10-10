"""Prueba hermética del informe de fidelización: no abre CSV ni cuentas."""
import pathlib
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import loyalty


class LoyaltyPinterestCoverageTests(unittest.TestCase):
    def test_pinterest_is_nd_and_other_networks_still_count(self):
        requested = []

        def accounts(network):
            requested.append(network)
            return {"lectora": {"comment": 1}} if network == "bluesky" else {}

        fake_rp = types.SimpleNamespace(
            OK_RESULTS=("confirmado", "publicado"),
            COMMENT_KINDS=("reply", "comment"),
            _rows=lambda path: [], norm=lambda handle: str(handle).casefold(),
        )
        with mock.patch.object(loyalty, "rp", fake_rp, create=True), \
             mock.patch.object(loyalty, "loyal_accounts", side_effect=accounts, create=True), \
             mock.patch.object(loyalty, "_registro", return_value="unused", create=True):
            lines = loyalty.report().splitlines()
        self.assertIn("| pinterest | ND | ND | ND | ND | ND | ND | ND |", lines)
        self.assertIn("| bluesky | 1 | 0 | 1 | 0 | 0 | 0 | 0 |", lines)
        self.assertNotIn("pinterest", requested)
        self.assertEqual(len(lines), 10)


if __name__ == "__main__":
    unittest.main()
