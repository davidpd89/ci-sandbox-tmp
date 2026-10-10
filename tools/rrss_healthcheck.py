from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    name: str
    status: str
    detail: str


REQUIRED_INTERNAL = [
    "nuevo_flujo/AGENTS.md",
    "nuevo_flujo/kb/cheatsheet.md",
    "nuevo_flujo/kb/contexto-activo.md",
    "nuevo_flujo/kb/estado-sesion.md",
    "nuevo_flujo/kb/contratos-salida.md",
    "nuevo_flujo/kb/patrones-ganadores-y-fallos.md",
    "nuevo_flujo/kb/voz-marca.md",
    "nuevo_flujo/kb/tool-registry.md",
    "nuevo_flujo/kb/montage-presets.md",
    "nuevo_flujo/skills/pipeline-contenido.md",
    "nuevo_flujo/skills/crear-lote.md",
    "nuevo_flujo/skills/auditoria-calidad.md",
    "nuevo_flujo/skills/texto-humano.md",
    "nuevo_flujo/skills/montaje-estable.md",
    "nuevo_flujo/skills/video-router.md",
    "nuevo_flujo/skills/imagen-assets.md",
    "nuevo_flujo/skills/subtitulos-captions.md",
    "nuevo_flujo/skills/video-clipping-largo.md",
]

WARN_ONLY = [
    "content_index.jsonl",
    "assets_registry.csv",
    "NO_PUBLICAR.md",
    "DEPENDENCIAS_EXTERNAS.md",
    "00_Contexto/START_HERE.md",
    "06_Seguimiento/seguimiento_activo.md",
    "06_Seguimiento/tracking_formatos_tecnicas_temas.md",
    "04_Assets/contenido_real_descubierto.md",
    "04_Assets/sistema_carrusel_instagram.md",
    "04_Assets/sistema_reel_instagram.md",
    "05_Integraciones/metricool-mcp.md",
    "12_Metodo_y_recursos_IA/01_laboratorio_humano",
    "tools/reel_template",
    "tools/quote_card_template",
    "tools/reel_template/generar_ass_karaoke.py",
    "tools/reel_template/render_text_pngs.py",
    "tools/quote_card_template/render_quote.py",
]

SCRIPT_CHECKS = [
    "tools/score_hook.py",
    "tools/validate_contracts.py",
    "tools/audit_lote.py",
    "tools/validate_content_index.py",
    "tools/validate_assets_registry.py",
]


def path_size(path: Path) -> int:
    if path.is_dir():
        return sum(1 for _ in path.rglob("*"))
    if path.exists():
        return path.stat().st_size
    return 0


def check_paths(paths: list[str], missing_status: str, empty_status: str) -> list[Check]:
    checks: list[Check] = []
    for rel in paths:
        path = ROOT / rel
        if not path.exists():
            checks.append(Check(rel, missing_status, "missing"))
            continue
        size = path_size(path)
        if size == 0:
            checks.append(Check(rel, empty_status, "exists but is empty"))
        else:
            checks.append(Check(rel, "PASS", f"exists, size/items={size}"))
    return checks


def check_structured_data() -> list[Check]:
    checks: list[Check] = []
    index = ROOT / "content_index.jsonl"
    if not index.exists():
        checks.append(Check("content_index.jsonl", "WARN", "missing; repetition checks are weak"))
    else:
        rows = [line for line in index.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        if not rows:
            checks.append(Check("content_index.jsonl", "WARN", "exists but has no records"))
        else:
            checks.append(Check("content_index.jsonl", "PASS", f"{len(rows)} record(s)"))

    assets = ROOT / "assets_registry.csv"
    if not assets.exists():
        checks.append(Check("assets_registry.csv", "WARN", "missing; asset repetition checks are weak"))
    else:
        rows = [line for line in assets.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        if len(rows) <= 1:
            checks.append(Check("assets_registry.csv", "WARN", "exists but has no asset rows"))
        else:
            checks.append(Check("assets_registry.csv", "PASS", f"{len(rows) - 1} asset row(s)"))
    return checks


def check_session_update() -> Check:
    path = ROOT / "nuevo_flujo/kb/estado-sesion.md"
    if not path.exists():
        return Check("SESSION_UPDATE", "FAIL", "estado-sesion.md missing")
    text = path.read_text(encoding="utf-8", errors="replace")
    count = text.count("[SESSION_UPDATE]")
    if count == 0:
        return Check("SESSION_UPDATE", "FAIL", "no session update blocks found")
    return Check("SESSION_UPDATE", "PASS", f"{count} block(s) found")


def run_checks() -> list[Check]:
    checks: list[Check] = []
    checks.extend(check_paths(REQUIRED_INTERNAL, "FAIL", "FAIL"))
    checks.extend(check_paths(SCRIPT_CHECKS, "FAIL", "FAIL"))
    checks.extend(check_paths([p for p in WARN_ONLY if p not in {"content_index.jsonl", "assets_registry.csv"}], "WARN", "WARN"))
    checks.extend(check_structured_data())
    checks.append(check_session_update())
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="RRSS David Porto flow healthcheck")
    parser.add_argument("--json", action="store_true", help="print JSON output")
    args = parser.parse_args()

    checks = run_checks()
    status = "FAIL" if any(c.status == "FAIL" for c in checks) else "PASS"
    warnings = sum(1 for c in checks if c.status == "WARN")

    payload = {
        "status": status,
        "warnings": warnings,
        "root": str(ROOT),
        "checks": [asdict(c) for c in checks],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"RRSS_HEALTHCHECK: {status} ({warnings} warning(s))")
        print(f"Root: {ROOT}")
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")

    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
