"""Pinterest scan remoto retirado tras cancelar Metricool."""
import importlib
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))


class PinterestRetiredScanTests(unittest.TestCase):
    def test_import_does_not_require_metricool_client(self):
        sys.modules.pop("pinterest_scan", None)
        sys.modules.pop("metricool_client", None)
        module = importlib.import_module("pinterest_scan")
        self.assertNotIn("metricool_client", sys.modules)
        self.assertTrue(hasattr(module, "RetiredPinterestAudit"))

    def test_scan_always_refuses_remote_audit(self):
        import pinterest_scan as scan

        with self.assertRaisesRegex(
            scan.RetiredPinterestAudit,
            "Metricool ya no forma parte del flujo",
        ):
            scan.scan()

    def test_retired_module_has_no_remote_fetch_helpers(self):
        import pinterest_scan as scan

        self.assertFalse(hasattr(scan, "_fetch_window"))
        self.assertFalse(hasattr(scan, "_fetch_scheduled"))


if __name__ == "__main__":
    unittest.main()
