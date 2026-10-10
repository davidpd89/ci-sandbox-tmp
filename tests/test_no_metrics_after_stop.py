"""Una señal de bloqueo detiene TAMBIÉN la navegación de métricas posterior."""
import ast
import contextlib
import datetime
import io
import json
import os
import pathlib
import sys
import pathlib as _p0
sys.path.insert(0, str(_p0.Path(__file__).resolve().parents[1] / "tools"))
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1] / "tools"
EXECUTORS = {
    "x_execute.py": "x",
    "threads_execute.py": "t",
    "instagram_execute.py": "ig",
    "tiktok_execute.py": "tt",
    "facebook_execute.py": "fb",
    "mastodon_execute.py": "m",
}


class StopIsTerminalTests(unittest.TestCase):
    def test_no_browser_metrics_after_warning(self):
        for filename, alias in EXECUTORS.items():
            with self.subTest(executor=filename):
                source = ROOT / filename
                tree = ast.parse(source.read_text(encoding="utf-8"))
                block = next(
                    node for node in tree.body if isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and isinstance(node.test.left, ast.Name)
                    and node.test.left.id == "__name__"
                )
                with tempfile.TemporaryDirectory() as folder:
                    plan_path = pathlib.Path(folder) / "plan.json"
<<<<<<< HEAD
                    plan_path.write_text("[]", encoding="utf-8")
=======
                    plan_path.write_text('[{"kind": "follow", "handle": "lector"}]', encoding="utf-8")
>>>>>>> origin/research/public-reuse-parent
                    writes = []
                    result = {"kind": "follow", "handle": "lector",
                              "resultado": "parada:CAPTCHA"}
                    fake_network = types.SimpleNamespace(
                        ensure_browser=lambda: None,
                        # Este test valida el cierre tras una parada ya producida;
                        # la pausa global de TikTok se prueba por separado.
                        _refuse_if_paused=lambda: None,
                        session=contextlib.nullcontext,      # Threads abre una sola conexion para todo el plan
                    )
<<<<<<< HEAD
=======
                    registro_csv = str(pathlib.Path(folder) / "registro.csv")
                    pathlib.Path(registro_csv).write_text(
                        "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n", encoding="utf-8")
>>>>>>> origin/research/public-reuse-parent
                    ns = {
                        "sc": __import__("types").SimpleNamespace(report_plan_style=lambda plan: None, guard_plan_item=lambda *a, **k: None, drop_stacked_actions=lambda plan, **k: plan),
                        "__name__": "__main__", "sys": sys, "json": json,
                        # el bloque principal ahora usa el ledger/bloqueo (03/10)
                        "os": __import__("os"),
<<<<<<< HEAD
                        "REGISTRO_CSV": str(pathlib.Path(__import__("tempfile").mkdtemp()) / "registro.csv"),
                        "datetime": datetime, alias: fake_network,
=======
                        "REGISTRO_CSV": registro_csv,
                        "datetime": datetime, alias: fake_network, "BACKEND": "web",
>>>>>>> origin/research/public-reuse-parent
                        "_preflight_plan": lambda plan: plan,
                        "_ultima_fila_metricas": lambda: None,
                        "_apply_warmup_gate": lambda plan, dias: (
                            plan, [], {"like": 0, "follow": 0, "comment": 0}),
                        "_drop_stacked_actions": lambda plan: plan,
                        "_puede_ejecutar_hoy": lambda *args: (True, None),
                        "run_plan": lambda plan, **kwargs: [result],
                        "_append_registro": lambda rows: writes.append(rows),
                        "_append_boost_ttl": lambda rows: None,
                        "_append_repost_ttl": lambda rows: None,
                        "_fetch_metrics": lambda: self.fail(
                            "Se navegó para métricas DESPUÉS de una parada"),
                        "_append_metricas": lambda *a: self.fail(
                            "Se registraron métricas después de una parada"),
                        "_update_estado": lambda *a: self.fail(
                            "Se actualizó ESTADO tras una parada"),
                    }
                    executable = compile(
                        ast.Module(body=[block], type_ignores=[]), str(source), "exec"
                    )
                    with patch.dict(os.environ, {"RRSS_LOCK_DIR": tempfile.mkdtemp()}), \
                         patch.object(sys, "argv", [str(source), str(plan_path)]), \
                         contextlib.redirect_stdout(io.StringIO()), \
                         self.assertRaises(SystemExit) as stopped:
                        exec(executable, ns)
                    self.assertEqual(stopped.exception.code, 5)
                    self.assertEqual(writes, [[result]])


if __name__ == "__main__":
    unittest.main()
