"""Plan de Instagram (04/10/2026): hasta 10 follows a los mejores candidatos de `instagram_commenters_scan.py`.

    python tools/instagram_build_plan.py [--max-follows N]   # escribe SISTEMA_DIARIO_INSTAGRAM/instagram_plan.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_INSTAGRAM")
CANDIDATES_JSON = os.path.join(ROOT, "instagram_candidates.json")
PLAN_OUT = os.path.join(ROOT, "instagram_plan.json")


MIN_SCORE = 18   # exige bio/comentario claramente en espanol Y del nicho (libros/escritura): solo cuentas que merezcan la pena


def build(candidates, max_follows=10, min_score=MIN_SCORE):
    plan, seen = [], set()
    for item in sorted(candidates, key=lambda c: -c.get("score", 0)):
        handle = (item.get("handle") or "").lstrip("@")
        if item.get("score", 0) < min_score or not item.get("niche"):
            continue   # bio/comentario del nicho (libros/escritura): un viajero que comento en un post de libros no vale
        if sc.is_political(f"{item.get('bio', '')} {item.get('comment', '')}"):
            continue   # filtro comun: politica, ligue/sexo, chat de citas
        if not handle or handle.casefold() in seen:
            continue
        seen.add(handle.casefold())
        plan.append({"handle": handle, "kind": "follow",
                     "motivo": f"comenta en {item.get('source', 'cuenta de libros')}; {item.get('followers')} seguidores"})
        if len(plan) >= max_follows:
            break
    return plan


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    max_follows = int(argv[argv.index("--max-follows") + 1]) if "--max-follows" in argv else 10
    with open(CANDIDATES_JSON, encoding="utf-8") as stream:
        plan = build(json.load(stream), max_follows)
    with open(PLAN_OUT, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=1)
    print(json.dumps({"plan": "SISTEMA_DIARIO_INSTAGRAM/instagram_plan.json", "actions": len(plan)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
