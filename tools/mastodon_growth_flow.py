"""Orquesta el scan de crecimiento Mastodon y construye planes por IDs."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mastodon_build_plan as builder
import mastodon_growth_scan as growth

DEFAULT_STATE = "mastodon_growth_state.json"
DEFAULT_AI = "mastodon_growth_ai.json"
DEFAULT_REPORT = "mastodon_growth_report.json"
DEFAULT_PLAN = "mastodon_plan.json"


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _run_deep_listener(minutes, config_path):
    command = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "mastodon_stream_collect.py"),
        "--config", config_path,
        "--minutes", str(float(minutes)),
    ]
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        return {
            "error": (process.stderr or process.stdout or "listener failed").strip()[-1000:],
            "returncode": process.returncode,
        }
    try:
        return json.loads((process.stdout or "{}").strip())
    except json.JSONDecodeError:
        return {"stdout": (process.stdout or "").strip()[-1000:]}


def _report(result):
    totals = result.get("totals") or {}
    coverage = result.get("coverage") or {}
    opportunities = {kind: 0 for kind in ("follow", "reply", "favourite", "boost")}
    for candidate in result.get("shortlist") or []:
        for kind in candidate.get("actions") or []:
            opportunities[kind] = opportunities.get(kind, 0) + 1
        for post in candidate.get("posts") or []:
            for kind in post.get("actions") or []:
                opportunities[kind] = opportunities.get(kind, 0) + 1
    opportunities["follow_pool"] = len(result.get("follow_pool") or [])
    return {
        "run_id": result.get("run_id"),
        "discovery_attribution": __import__("discovery_attribution").safe_state_summary(
            "mastodon", result, hmac_key=os.environ.get("RRSS_DISCOVERY_HMAC_KEY", "").encode("utf-8")),
        "coverage_complete": not bool(coverage.get("missing")),
        "coverage_missing": coverage.get("missing") or [],
        "budget": result.get("budget") or {},
        "totals": totals,
        "opportunities": opportunities,
        "issues": result.get("issues") or [],
        "stopped": bool(result.get("stopped")),
    }


def prepare(args):
    collector = None
    if args.deep and float(args.deep) > 0:
        collector = _run_deep_listener(float(args.deep), args.config)
    result = growth.run(
        config_path=args.config,
        write_metrics=not args.no_metrics,
    )
    ai = growth.compact_ai_view(result)
    report = _report(result)
    report["stream_collector"] = collector
    _write_json(args.state, result)
    _write_json(args.ai, ai)
    _write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if args.strict and (
        not report["coverage_complete"] or report["stopped"]
    ) else 0


def build(args):
    with open(args.state, encoding="utf-8") as stream:
        state = json.load(stream)
    with open(args.decisions, encoding="utf-8") as stream:
        decisions = json.load(stream)
    plan = builder.build(state, decisions)
    import scan_common as _sc
    for note in _sc.reply_style_report([r.get("text") for r in plan if r.get("kind") == "reply"]):
        print(f"ESTILO: {note}", file=sys.stderr)
    _write_json(args.plan, plan)
    print(json.dumps({"plan": args.plan, "actions": len(plan)}, ensure_ascii=False, indent=2))
    return 0


def make_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--config", default=growth.CONFIG_PATH)
    prep.add_argument("--state", default=DEFAULT_STATE)
    prep.add_argument("--ai", default=DEFAULT_AI)
    prep.add_argument("--report", default=DEFAULT_REPORT)
    prep.add_argument("--strict", action="store_true")
    prep.add_argument("--no-metrics", action="store_true")
    prep.add_argument(
        "--deep",
        nargs="?",
        const=20.0,
        type=float,
        default=0.0,
        metavar="MINUTES",
        help="escucha Mastodon Streaming API antes del scan (20 min por defecto)",
    )
    prep.set_defaults(func=prepare)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("decisions")
    build_parser.add_argument("--state", default=DEFAULT_STATE)
    build_parser.add_argument("--plan", default=DEFAULT_PLAN)
    build_parser.set_defaults(func=build)
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
