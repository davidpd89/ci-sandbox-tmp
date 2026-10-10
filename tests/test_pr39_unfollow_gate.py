"""PR39: la ruta heredada de unfollow nunca debe llegar a interfaz móvil."""
import ast
import csv
import json
from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))


def test_direct_legacy_unfollow_is_hard_disabled(monkeypatch):
    import tiktok_following_audit as legacy
    # Un bloqueador incluso si alguien importa y llama directamente a la función.
    with pytest.raises(PermissionError, match="bloqueado"):
        legacy.unfollow(max_n=1)


def test_cli_dispatcher_has_no_legacy_unfollow_call():
    tree = ast.parse((TOOLS / "tiktok_following_audit.py").read_text(encoding="utf-8"))
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    assert len(funcs) == 1
    code = ast.unparse(funcs[0])
    assert 'command == "relations"' in code or "command == 'relations'" in code
    assert "unfollow(max_n or 30)" not in code


def test_cli_offline_summary_excludes_handles(tmp_path, capsys):
    import tiktok_relation_report as rr
    following = tmp_path / "following.json"
    registro = tmp_path / "registro.csv"
    inbound = tmp_path / "inbound.csv"
    following.write_text(json.dumps([{"handle": "private_reader", "status": "Siguiendo"}]), encoding="utf-8")
    with registro.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["fecha", "cuenta", "tipo", "resultado"])
        writer.writerow(["2026-09-01", "@private_reader", "follow", "confirmado"])
    inbound.write_text("fecha,red,handle,tipo\n", encoding="utf-8")
    # No depende de URL, .env, móvil, Edge ni CSV real.
    assert rr.main(["--following", str(following), "--registro", str(registro),
                    "--inbound", str(inbound), "--observed-on", "2026-10-09",
                    "--today", "2026-10-09"]) == 0
    output = capsys.readouterr().out
    assert "private_reader" not in output
    assert json.loads(output)["totales"] == {"revision_21_mas": 1}
