"""Regresiones offline: una medición desconocida no borra un dato confirmado.

Comprueba la norma común mediante ESTADO.md temporal y sin cuentas/red.
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import exec_common as ec


TEMPLATE = """# Red

## Última sesión

2026-10-09. 2 follow.

## Métricas actuales (de metricas.csv, última fila)

Seguidores: 1.234. Siguiendo: 80. Posts: 3.

## Próximos pasos

Continuar.
"""


class EstadoUnknownMetricsTests(unittest.TestCase):
    def test_unknown_follower_preserves_value_and_updates_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ESTADO.md")
            Path(path).write_text(TEMPLATE, encoding="utf-8")
            ec.update_estado(path, [{"kind": "reply", "resultado": "confirmado"}],
                             {"followers": "?", "following": 81, "posts": None})
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn("1 reply", text)
            self.assertNotIn("2 follow", text)
            self.assertIn("Seguidores: 1.234.", text)
            self.assertIn("Siguiendo: 81.", text)
            self.assertIn("Posts: 3.", text)
            self.assertIn("## Próximos pasos\n\nContinuar.", text)
            self.assertNotIn("Seguidores: ?.", text)

    def test_verified_zero_replaces_old_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ESTADO.md")
            Path(path).write_text(TEMPLATE, encoding="utf-8")
            ec.update_estado(path, [], {"followers": 0},
                             fields=(("Seguidores", "followers"),))
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn("Seguidores: 0.", text)
            self.assertNotIn("Seguidores: 1.234.", text)
            self.assertIn("sin acciones confirmadas", text)

    def test_all_unknown_does_not_erase_previous_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ESTADO.md")
            Path(path).write_text(TEMPLATE, encoding="utf-8")
            ec.update_estado(path, [{"kind": "follow", "resultado": "confirmado"}],
                             {"followers": "?", "following": "N/A", "posts": None})
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn("1 follow", text)
            self.assertIn("Seguidores: 1.234.", text)
            self.assertIn("Siguiendo: 80.", text)
            self.assertIn("Posts: 3.", text)

    def test_missing_document_keeps_noop_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ESTADO.md")
            ec.update_estado(path, [], {"followers": "?"})
            self.assertFalse(Path(path).exists())


if __name__ == "__main__":
    unittest.main()
