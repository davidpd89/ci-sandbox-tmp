"""Orquestador del flujo diario de crecimiento Bluesky.

Prepara en una sola orden el estado completo y la vista compacta para IA. El modo
--deep añade una ventana Jetstream antes del scan. La ejecución de escrituras sigue
separada y exige el plan aprobado.

Uso:
    python tools/bluesky_growth_flow.py prepare
    python tools/bluesky_growth_flow.py prepare --deep 20
    python tools/bluesky_growth_flow.py prepare --strict
    python tools/bluesky_growth_flow.py build decisions.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

DEFAULT_CONFIG = os.path.join(
    os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY", "growth_config.json"
)
DEFAULT_STATE = "growth_state.json"
DEFAULT_AI = "growth_ai.json"
DEFAULT_PLAN = "plan.json"


def _growth_module():
    import bluesky_growth_scan
    return bluesky_growth_scan


def _builder_module():
    import bluesky_build_plan
    return bluesky_build_plan


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _collector_command(script, minutes, extra=()):
    return [
        sys.executable,
        os.path.join(os.path.dirname(__file__), script),
        *extra,
        "--minutes",
        str(float(minutes)),
    ]


def _run_deep_collectors(minutes, previous_state):
    """Escucha general y taste en serie sobre la SQLite compartida.

    Ambos collectors escriben en el mismo fichero. Serializarlos evita locks y
    carreras de inicialización sin exigir WAL ni coordinación entre procesos.
    """
    commands = [
        _collector_command("bluesky_jetstream_collect.py", minutes),
    ]
    if os.path.exists(previous_state):
        commands.append(_collector_command(
            "bluesky_taste_collect.py",
            min(float(minutes), 5.0),
            ("--state", previous_state),
        ))

    results = []
    for command in commands:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"collector falló ({os.path.basename(command[1])}): "
                f"{process.stderr.strip() or process.stdout.strip()}"
            )
        try:
            payload = json.loads((process.stdout or "").strip() or "{}")
        except json.JSONDecodeError:
            payload = {"stdout": (process.stdout or "").strip()}
        results.append({
            "collector": os.path.basename(command[1]),
            "result": payload,
        })
    return results


def _report(result):
    readiness = result.get("readiness") or {}
    coverage = result.get("coverage") or {}
    totals = result.get("totals") or {}
    budget = result.get("budget") or {}
    source_metrics = result.get("source_metrics") or {}

    branches = []
    for key, metric in source_metrics.items():
        if not str(key).startswith("second_wave:d"):
            continue
        prefix = str(key).split(":", 2)[1]
        try:
            depth = int(prefix.lstrip("d"))
        except ValueError:
            depth = 0
        branches.append({
            "depth": depth,
            "new_handles": int((metric or {}).get("new_handles") or 0),
        })
    frontier_new = sum(row["new_handles"] for row in branches)
    frontier = {
        "depth_reached": max((row["depth"] for row in branches), default=0),
        "branches_opened": len(branches),
        "productive_branches": sum(
            1 for row in branches if row["new_handles"] > 0
        ),
        "new_handles": frontier_new,
        "new_handles_per_branch": (
            round(frontier_new / len(branches), 2) if branches else 0.0
        ),
    }

    return {
        "run_id": result.get("run_id"),
        "coverage_complete": not bool(coverage.get("missing")),
        "coverage_missing": coverage.get("missing") or [],
        "optional_missing": coverage.get("optional_missing") or [],
        "budget_used": budget.get("used"),
        "budget_remaining": budget.get("remaining"),
        "profiles_seen": totals.get("profiles_seen"),
        "shortlist": totals.get("shortlist"),
        "community": totals.get("community"),
        "acquisition": totals.get("acquisition"),
        "fresh_acquisition": totals.get("fresh_acquisition"),
        "fresh_target": readiness.get("acquisition_target"),
        "fresh_target_met": bool(readiness.get("fresh_target_met")),
        "opportunities": readiness.get("opportunities") or {},
        "frontier": frontier,
        "issues": result.get("issues") or [],
    }


def prepare(args):
    growth = _growth_module()
    collectors = []
    if args.deep and float(args.deep) > 0:
        collectors = _run_deep_collectors(float(args.deep), args.state)

    result = growth.run(
        config_path=args.config,
        write_metrics=not args.no_metrics,
    )
    _write_json(args.state, result)
    _write_json(args.ai, growth.compact_ai_view(result))
    report = _report(result)
    report["collectors"] = collectors
    _write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.strict and (
        not report["coverage_complete"]
        or not report["fresh_target_met"]
    ):
        return 2
    return 0


def build(args):
    builder = _builder_module()
    with open(args.state, encoding="utf-8") as stream:
        state = json.load(stream)
    with open(args.decisions, encoding="utf-8") as stream:
        decisions = json.load(stream)
    plan = builder.build(state, decisions)
    import scan_common as _sc
    for note in _sc.reply_style_report([r.get("text") for r in plan if r.get("kind") == "reply"]):
        print(f"ESTILO: {note}", file=sys.stderr)
    _write_json(args.plan, plan)
    print(json.dumps({
        "plan": args.plan,
        "actions": len(plan),
        "next": f"{sys.executable} tools/bluesky_execute.py {args.plan}",
    }, ensure_ascii=False, indent=2))
    return 0


def make_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--config", default=DEFAULT_CONFIG)
    prep.add_argument("--state", default=DEFAULT_STATE)
    prep.add_argument("--ai", default=DEFAULT_AI)
    prep.add_argument("--report", default="growth_report.json")
    prep.add_argument(
        "--deep",
        nargs="?",
        const=20.0,
        type=float,
        default=0.0,
        metavar="MINUTES",
        help="escucha Jetstream antes del scan; 20 min si no se indica valor",
    )
    prep.add_argument("--strict", action="store_true")
    prep.add_argument("--no-metrics", action="store_true")
    prep.set_defaults(func=prepare)

    plan = sub.add_parser("build")
    plan.add_argument("decisions")
    plan.add_argument("--state", default=DEFAULT_STATE)
    plan.add_argument("--plan", default=DEFAULT_PLAN)
    plan.set_defaults(func=build)
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
