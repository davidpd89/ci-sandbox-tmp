"""Preflight manual de Pinterest: cero llamadas remotas."""
import importlib
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

dup = types.ModuleType("check_duplicate_phrase")
dup.check = lambda text: []
x = types.ModuleType("x_interact")
x._check_spanish_orthography = lambda text: None

with patch.dict(
    sys.modules,
    {"check_duplicate_phrase": dup, "x_interact": x},
):
    pe = importlib.import_module("pinterest_execute")


def valid_item():
    return {
        "kind": "manual_pin",
        "text": "Una lectura",
        "media": ["imagen-local.png"],
        "media_alt_text": ["Libro sobre una mesa de madera"],
        "board_name": "Fantasía juvenil",
        "pin_title": "Una lectura entre mundos",
        "pin_link": "https://autorademodiaz.com/cuaderno/una-lectura/",
    }


class PinterestManualPreflightTests(unittest.TestCase):
    def test_module_has_no_metricool_dependency_or_remote_call(self):
        source = (TOOLS / "pinterest_execute.py").read_text(encoding="utf-8")
        self.assertNotIn("metricool_client", source)
        self.assertNotIn("call_tool(", source)
        self.assertNotIn("createScheduledPost", source)
        self.assertNotIn("metricool_client", sys.modules)

    def test_valid_manual_pin_is_ready_but_not_published(self):
        result = pe.run_plan([valid_item()])
        self.assertEqual(
            result[0]["resultado"],
            "listo_para_publicacion_manual",
        )

    def test_legacy_schedule_pin_is_explicitly_rejected(self):
        item = valid_item()
        item["kind"] = "schedule_pin"
        errors = pe._validate(item)
        self.assertTrue(any("retirado" in error for error in errors))
        self.assertTrue(any("manual_pin" in error for error in errors))

    def test_wrong_kind_is_rejected(self):
        item = valid_item()
        item["kind"] = "publish_now"
        self.assertTrue(any("manual_pin" in e for e in pe._validate(item)))

    def test_media_alt_and_board_are_required(self):
        item = valid_item()
        item["media"] = []
        item["media_alt_text"] = []
        item["board_name"] = ""
        errors = pe._validate(item)
        self.assertTrue(any("media debe" in e for e in errors))
        self.assertTrue(any("media_alt_text" in e for e in errors))
        self.assertTrue(any("board_name" in e for e in errors))

    def test_alt_count_must_match_media_count(self):
        item = valid_item()
        item["media"] = ["uno.png", "dos.png"]
        item["media_alt_text"] = ["Solo uno"]
        self.assertTrue(
            any("tantas entradas" in e for e in pe._validate(item))
        )

    def test_title_and_internal_id_are_validated(self):
        item = valid_item()
        item["pin_title"] = ""
        self.assertTrue(any("pin_title" in e for e in pe._validate(item)))

        item["pin_title"] = "IG-02-08 — Promesa narrativa"
        self.assertTrue(
            any("ID interno" in e for e in pe._validate(item))
        )

    def test_destination_requires_exact_https_url(self):
        bad = (
            "http://autorademodiaz.com/cuaderno/",
            "https://user:pass@autorademodiaz.com/cuaderno/",
            "https://autorademodiaz.com:444/cuaderno/",
            "https://autorademodiaz.com:puerto/cuaderno/",
            "https://[host-malformado/cuaderno/",
        )
        for value in bad:
            with self.subTest(value=value):
                item = valid_item()
                item["pin_link"] = value
                self.assertTrue(
                    any("HTTPS válida" in e for e in pe._validate(item))
                )

    def test_home_with_query_is_not_specific_destination(self):
        item = valid_item()
        item["pin_link"] = (
            "https://autorademodiaz.com/?utm_source=pinterest"
        )
        self.assertTrue(any("home" in e for e in pe._validate(item)))

    def test_invalid_elements_do_not_crash_entire_plan(self):
        result = pe.run_plan([None, valid_item()])
        self.assertTrue(result[0]["resultado"].startswith("invalido:"))
        self.assertEqual(
            result[1]["resultado"],
            "listo_para_publicacion_manual",
        )

    def test_plan_must_be_list(self):
        with self.assertRaisesRegex(ValueError, "lista JSON"):
            pe.run_plan({"kind": "manual_pin"})


if __name__ == "__main__":
    unittest.main()
