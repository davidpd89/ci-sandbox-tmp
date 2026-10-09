"""Oleada de follows con alta probabilidad de follow-back (02/10).

El `auto_plan` del growth scan solo sigue por encima de un umbral de score
(9 de 119 oportunidades el 02/10). Aqui se elige por probabilidad de que la
cuenta nos siga de vuelta: bio afin al nicho (señal del propio engine),
sigue a bastante gente (>=80) y no mucho menos de lo que le siguen (>=0.6 x
seguidores), y no es una cuenta enorme. Excluye contenido politico.

Uso:
    python tools/bluesky_followback_wave.py [growth_state.json] [salida.json]
    python tools/bluesky_execute.py bluesky_follow_wave.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

MIN_FOLLOWING = 80
MAX_FOLLOWERS = 15000
MIN_FOLLOWING_RATIO = 0.6


MAX_FOLLOW_RATIO = 5.0


def _follow_ratio():
    """siguiendo/seguidores de la ultima fila de metricas.csv (None si no se puede leer)."""
    import csv
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY", "metricas.csv"), encoding="utf-8", newline="") as stream:
            last = list(csv.DictReader(stream))[-1]
        return int(last["siguiendo"]) / max(int(last["seguidores"]), 1)
    except (OSError, ValueError, IndexError, KeyError):
        return None


def follows_allowed_today(today=None):
    """Follows que aun caben hoy: <=15 % del objetivo diario de la rampa y <=400 en total (GPT 05/10: con 8.000 acciones, 1.200 follows serian mala senal;
    la mezcla sana es ~70 % likes, 10-18 % follows). Cuenta los follows confirmados hoy en el registro."""
    import csv
    import datetime
    try:
        import volume_ramp
        cap = min(int(0.15 * volume_ramp.daily_target()), 400)
    except Exception:
        cap = 150
    done = 0
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY", "registro_interacciones.csv"), encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("fecha") == (today or datetime.date.today()).isoformat() and row.get("resultado") == "confirmado"                         and "follow" in (row.get("tipo") or "").split("+") and row.get("tipo") != "unfollow":
                    done += 1
    except OSError:
        pass
    return max(0, cap - done)


def select(state, already_following=frozenset()):
    chosen = []
    for cand in state.get("shortlist") or []:
        if "follow" not in (cand.get("actions") or []):
            continue
        if cand.get("handle") in already_following:
            continue
        profile = cand.get("profile") or {}
        bio = profile.get("bio") or ""
        signals = " ".join(cand.get("signals") or [])
        followers = profile.get("followers") or 0
        following = profile.get("following") or 0
        if "afín al nicho" not in signals:
            continue
        if sc.is_political(bio) or sc.looks_activist(bio):
            continue
        if following < MIN_FOLLOWING or followers > MAX_FOLLOWERS:
            continue
        if following < MIN_FOLLOWING_RATIO * followers:
            continue
        chosen.append({
            "handle": cand["handle"],
            "kind": "follow",
            "lane": cand.get("lane"),
            "motivo": "growth:followback_wave:bio_nicho+following>=0.6*followers",
        })
    return chosen


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    positional = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--max")]
    state_path = positional[0] if positional else "growth_state.json"
    out_path = positional[1] if len(positional) > 1 else "bluesky_follow_wave.json"
    with open(state_path, encoding="utf-8") as stream:
        state = json.load(stream)
    already = {
        row["handle"]
        for row in state.get("auto_plan") or []
        if row.get("kind") == "follow"
    }
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else None
    plan = select(state, already)
    ratio = _follow_ratio()
    if ratio is not None and ratio > MAX_FOLLOW_RATIO:
        limit = min(limit or 10**6, 20)   # siguiendo/seguidores ya alto: solo un goteo hasta que los follow-backs lo equilibren
        print(f"siguiendo/seguidores = {ratio:.1f} > {MAX_FOLLOW_RATIO}: oleada limitada a {limit}")
    room = follows_allowed_today()
    limit = min(limit or 10**6, room)
    print(f"follows permitidos hoy: {room} (tope diario 15 % del objetivo, max 400)")
    plan = plan[:limit]   # ya vienen en el orden del shortlist (mejor score primero). 05/10: con `if limit:` un tope de 0 (cupo diario agotado) NO recortaba y salieron 105 follows de mas
    with open(out_path, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=1)
    print(f"{out_path}: {len(plan)} follows (excluye {len(already)} ya en auto_plan)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
