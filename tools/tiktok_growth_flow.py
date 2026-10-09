"""Orquestador TikTok (equivalente a bluesky_growth_flow): poco token, mucho script.

    python tools/tiktok_growth_flow.py prepare                 # scan en vivo + auto_plan + vista IA
    python tools/tiktok_growth_flow.py build [decisions.json]  # auto_plan + decisiones de la IA
    python tools/tiktok_growth_flow.py run [--apply]           # preflight; con --apply, sesión humana

`prepare` deja `tiktok_state.json` (estado completo), `tiktok_ai.json` (vista compacta: lo
único que lee la IA) y `tiktok_report.json`. La IA solo decide dudosos y escribe comentarios;
follows de alta puntuación y likes salen del auto_plan. `run` sin --apply no toca el móvil.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import tiktok_build_plan as builder
import tiktok_growth_scan as scan

STATE, AI, REPORT, PLAN = "tiktok_state.json", "tiktok_ai.json", "tiktok_report.json", "tiktok_plan.json"


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def report(state):
    shortlist = state["shortlist"]
    return {
        "fetched_posts": state["fetched_posts"],
        "discovery": state.get("discovery"),
        "shortlist": len(shortlist),
        "acquisition": sum(1 for c in shortlist if c.get("lane") == "acquisition"),
        "community": sum(1 for c in shortlist if c.get("lane") == "community"),
        "auto_plan": {
            kind: sum(1 for r in state["auto_plan"] if r["kind"] == kind) for kind in ("follow", "like")
        },
        "issues": state["issues"],
    }


def reusable(state_path, hours, min_left=25):
    """El scan de TikTok tarda ~90 min (busquedas por el movil) y la ejecucion ~70: con un estado reciente y plan de sobra se salta el scan y la ronda va directa a ejecutar (07/10: la mitad del dia se iba en escanear)."""
    import time
    try:
        if not hours or (time.time() - os.path.getmtime(state_path)) / 3600 > hours:
            return False
        with open(state_path, encoding="utf-8") as stream:
            state = json.load(stream)
        return len(drop_already_done(builder.build(state, {"actions": []}))) >= min_left
    except Exception:
        return False


def prepare(args):
    if reusable(args.state, getattr(args, "reuse_hours", 0)):
        print(f"[tiktok] estado de hace menos de {args.reuse_hours} h con plan de sobra: se reutiliza (sin scan)")
        return 0
    rc = scan.main(["--live-read", "--out", args.state])
    if rc != 0:
        return rc
    with open(args.state, encoding="utf-8") as stream:
        state = json.load(stream)
    _write(args.ai, scan.compact_ai_view(state))
    rep = report(state)
    _write(args.report, rep)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


def drop_already_done(plan):
    """Quita lo ya confirmado en el registro (follows, URLs de like/comentario y textos usados):
    relanzar un plan tras un corte nunca repite ni choca con el dedupe del preflight."""
    import csv
    path = scan.REGISTRO_CSV
    done_follow, done_url, done_text = set(), set(), set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if (row.get("resultado") or "").strip().casefold() != "confirmado":
                    continue
                kind = (row.get("tipo") or "").strip().casefold()
                if kind == "follow":
                    done_follow.add((row.get("cuenta") or "").strip().lstrip("@").casefold())
                else:
                    done_url.add((kind, (row.get("post_resumen") or "").strip()))
                    if kind == "comment":
                        done_text.add(" ".join((row.get("texto_usado") or "").split()).casefold())
    kept = []
    for item in plan:
        if item["kind"] == "follow" and item["handle"].casefold() in done_follow:
            continue
        if item["kind"] != "follow" and (item["kind"], item.get("url", "")) in done_url:
            continue
        if item["kind"] == "comment" and " ".join(item["text"].split()).casefold() in done_text:
            continue
        kept.append(item)
    return kept


def build(args):
    with open(args.state, encoding="utf-8") as stream:
        state = json.load(stream)
    decisions = {"actions": []}
    if args.decisions:
        with open(args.decisions, encoding="utf-8") as stream:
            decisions = json.load(stream)
    plan = drop_already_done(builder.build(state, decisions))
    if getattr(args, "no_follows", False):       # 07/10: TikTok limita los follows (~100-150 al dia en esta cuenta); el cupo se reserva para el seguimiento masivo (follow-back 25 % frente al 10 % del plan automatico)
        plan = [item for item in plan if item.get("kind") != "follow"]
    _write(args.plan, plan)
    print(json.dumps({"plan": args.plan, "actions": len(plan)}, ensure_ascii=False, indent=2))
    return 0


def run(args):
    cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "tiktok_mobile_execute.py"), args.plan]
    if args.apply:
        cmd.append("--apply")
    return subprocess.call(cmd)


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--state", default=STATE)
    prep.add_argument("--ai", default=AI)
    prep.add_argument("--report", default=REPORT)
    prep.add_argument("--reuse-hours", type=float, default=0, help="reutiliza el estado si es mas reciente y quedan acciones por hacer")
    prep.set_defaults(func=prepare)
    bld = sub.add_parser("build")
    bld.add_argument("decisions", nargs="?")
    bld.add_argument("--state", default=STATE)
    bld.add_argument("--plan", default=PLAN)
    bld.add_argument("--no-follows", action="store_true", help="quita los follows del plan (el cupo es del seguimiento masivo)")
    bld.set_defaults(func=build)
    rn = sub.add_parser("run")
    rn.add_argument("--plan", default=PLAN)
    rn.add_argument("--apply", action="store_true")
    rn.set_defaults(func=run)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = make_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
