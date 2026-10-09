"""Metricool permanece retirado y fail-closed en la capa operativa."""
import importlib
import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))


class MetricoolRetiredTests(unittest.TestCase):
    def test_auth_refuses_before_oauth(self):
        auth = importlib.import_module("metricool_auth")
        with self.assertRaises(auth.MetricoolRetired):
            auth.get_valid_token()
        source = (TOOLS / "metricool_auth.py").read_text(encoding="utf-8")
        self.assertNotIn("webbrowser", source)
        self.assertNotIn("urlopen", source)

    def test_client_refuses_all_remote_calls(self):
        client = importlib.import_module("metricool_client")
        with self.assertRaises(client.MetricoolRetired):
            client.call_tool("createScheduledPost", {})
        with self.assertRaises(client.MetricoolRetired):
            client.list_tools()
        source = (TOOLS / "metricool_client.py").read_text(encoding="utf-8")
        self.assertNotIn("urlopen", source)
        self.assertNotIn("Authorization", source)

    def test_common_publisher_refuses_before_media(self):
        path = (
            ROOT
            / "00_OPERATIVO"
            / "HERRAMIENTAS"
            / "scripts_comunes"
            / "metricool_publicador.py"
        )
        spec = importlib.util.spec_from_file_location("metricool_publicador_retired", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in (
            "publicar_y_programar",
            "publicar_video_multired",
            "publicar_carousel_multired",
        ):
            with self.subTest(name=name):
                with self.assertRaises(module.MetricoolPublicationRetired):
                    getattr(module, name)()
        source = path.read_text(encoding="utf-8")
        self.assertNotIn("createScheduledPost", source)
        self.assertNotIn("subprocess", source)

    def test_operational_entrypoints_mark_metricool_retired(self):
        readme = (ROOT / "00_OPERATIVO" / "README.md").read_text(encoding="utf-8")
        flow = (
            ROOT / "00_OPERATIVO" / "02_FLUJOS" / "metricool.md"
        ).read_text(encoding="utf-8")
        context = (
            ROOT / "00_OPERATIVO" / "01_CONTEXTO_UNICO.md"
        ).read_text(encoding="utf-8")
        self.assertIn("manual/nativamente", readme)
        self.assertIn("cancelado", flow.casefold())
        self.assertIn("cancelado", context.casefold())
        self.assertNotIn(
            "Programar/publicar: `02_FLUJOS/metricool.md`.",
            readme,
        )


if __name__ == "__main__":
    unittest.main()
