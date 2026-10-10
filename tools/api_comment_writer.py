"""Bluesky/Mastodon: comentarios escritos por ChatGPT para la ronda (07/10/2026, David: «los de la API ya ni comentan»).

Las replies de Bluesky y Mastodon las escribia una IA a mano en cada sesion (de ahi los picos de los dias 02, 03 y 05/10); sin IA la ronda solo daba likes y follows. Tras `prepare`, este paso toma
de la shortlist los posts que el scan propone para responder (`reply` en `actions`), se los pasa a ChatGPT con `reply_writer` (mismas reglas que en las demas redes: cortas, humanas, sin repetir a
quien ya comentamos) y escribe las decisiones de la ronda. Un fallo nunca tumba la ronda: sin respuestas, la ronda sigue con likes y follows.

    python tools/api_comment_writer.py bluesky|mastodon [--max 14] [--reset]      # --reset: empieza de decisiones vacias (Bluesky)
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import reply_queue as rq
from candidate_identity import CandidateIdentityError, resolve_author, resolve_post_ref, resolve_stable_account

ROOT = os.path.join(os.path.dirname(__file__), "..")
NETWORKS = {
    "bluesky": {"state": "growth_state.json", "decisions": "bluesky_mech_decisions.json", "max": 14},
    "mastodon": {"state": "mastodon_growth_state.json", "decisions": "mastodon_mech_decisions.json", "max": 12},
}


def _safe_score(candidate):
    if not isinstance(candidate, Mapping):
        return 0.0
    try:
        score = float(candidate.get("score") or 0)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return score if math.isfinite(score) else 0.0


def pick_posts(state, limit, *, network=None, log=print):
    """Un post por candidato elegible, descartando identidades inválidas con motivo.

    La ejecución real aporta `network` expresamente. Para consumidores legados de
    la API (tests) que llamaban sin red, inferimos Mastodon SOLO si hay un `acct`
    y no hay `handle`. No se permite ese fallback en las rondas operativas.
    El error afecta SOLO al candidato; otro post válido de la ronda sigue.
    """
    out = []
    omitted = 0
    if network is None:
        log("[api_comment_writer] RED_INFERIDA_COMPATIBILIDAD: proporcionar network explícito")
    if not isinstance(state, Mapping) or not isinstance(state.get("shortlist"), list):
        log("[api_comment_writer] SCAN_INVALIDO shortlist_no_es_lista")
        return []
    if not isinstance(limit, int) or limit <= 0:
        return []
    for candidate in sorted(state["shortlist"], key=lambda c: -_safe_score(c)):
        if not isinstance(candidate, Mapping):
            log(f"[api_comment_writer] {network}: IDENTIDAD_INVALIDA candidato_no_es_mapa")
            omitted += 1
            continue
        effective_network = network or ("mastodon" if "acct" in candidate and "handle" not in candidate else "bluesky")
        posts = candidate.get("posts") or []
        if not isinstance(posts, list):
            log(f"[api_comment_writer] {effective_network}: POST_INVALIDO posts_no_es_lista")
            omitted += 1
            continue
        for post in posts:
            if not isinstance(post, Mapping):
                log(f"[api_comment_writer] {effective_network}: POST_INVALIDO post_no_es_mapa")
                omitted += 1
                continue
            raw_text = post.get("text")
            text = " ".join(raw_text.split()) if isinstance(raw_text, str) else ""
            actions = post.get("actions")
            if not isinstance(actions, list) or "reply" not in actions or len(text) < 40 or not post.get("es", True):
                continue
            try:
                author = resolve_author(effective_network, candidate)
            except CandidateIdentityError as exc:
                # Compatibilidad histórica de consumidores sin network: algunos
                # tests legados tienen handles cortos. NUNCA en main productivo.
                field = "acct" if effective_network == "mastodon" else "handle"
                legacy = candidate.get(field) if network is None else None
                if isinstance(legacy, str) and legacy.strip() and not any(ch.isspace() for ch in legacy):
                    author = legacy.strip()
                else:
                    log(f"[api_comment_writer] {effective_network}: IDENTIDAD_INVALIDA {exc}; se omite candidato")
                    omitted += 1
                    break
            post_id = post.get("id")
            if not isinstance(post_id, str) or not post_id.strip():
                log(f"[api_comment_writer] {effective_network}: POST_INVALIDO falta_id; se omite post")
                omitted += 1
                continue
            try:
                post_uri = resolve_post_ref(effective_network, post)
            except CandidateIdentityError as exc:
                if network is None:
                    post_uri = None  # sólo consumidor legado; producción exige URI
                else:
                    log(f"[api_comment_writer] {effective_network}: POST_INVALIDO {exc}")
                    omitted += 1
                    continue
            profile = candidate.get("profile")
            bio = (profile.get("bio") if isinstance(profile, Mapping) else None) or candidate.get("bio") or ""
            bio = bio[:100] if isinstance(bio, str) else ""
            row = {"id": post_id, "author": author, "post_uri": post_uri,
                   "text": text[:600], "context": f"bio: {bio}" if bio else ""}
            stable = resolve_stable_account(effective_network, candidate)
            if stable:
                row["stable_author"] = stable
            out.append(row)
            break
        if len(out) >= limit:
            break
    if omitted:
        log(f"[api_comment_writer] {network}: candidatos_o_posts_invalidos={omitted}; elegibles={len(out)}")
    return out


def merge(existing, replies):
    """Preserva acciones no textuales; las replies pertenecen SOLO a esta ronda.

    El trabajador puede no haber producido texto por falta de contexto, cierre
    del hilo o espera del modelo. Una reply antigua nunca debe sobrevivir en
    decisions.json y reactivarse sobre un scan distinto.
    """
    posts = {a["post"] for a in replies}
    kept = [
        a for a in (existing or {}).get("actions", [])
        if a.get("kind") != "reply"
        and not (a.get("post") in posts and a.get("kind") in ("like", "favourite", "boost", "repost"))
    ]
    return {"actions": kept + replies}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv[0] not in NETWORKS:
        print(__doc__)
        return 0
    network, cfg = argv[0], NETWORKS[argv[0]]
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else cfg["max"]
    path = os.path.join(ROOT, cfg["decisions"])
    try:
        existing = {"actions": []} if "--reset" in argv else json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        existing = {"actions": []}
    replies = []
    try:
        import reply_hold
        if reply_hold.held():
            print(f"[api_comment_writer] {network}: respuestas EN REVISION, la ronda sigue sin comentarios")
        else:
            state = json.load(open(os.path.join(ROOT, cfg["state"]), encoding="utf-8"))
            items = pick_posts(state, limit, network=network)
            written = rq.get_or_enqueue(items, network, wait_min=4) if items else {}
<<<<<<< HEAD
            replies = [{"kind": "reply", "post": i["id"], "post_uri": i["post_uri"], "text": written[i["id"]]} for i in items if i["id"] in written]
=======
            import reply_provenance as proof
            replies = [a for i in items if i["id"] in written
                       for a in [proof.attach({"kind": "reply", "post": i["id"],
                                               "post_uri": i["post_uri"], "text": written[i["id"]]},
                                              i, network)] if a is not None]
>>>>>>> origin/research/public-reuse-parent
            print(f"[api_comment_writer] {network}: {len(replies)} comentarios escritos de {len(items)} posts propuestos")
    except Exception as exc:                       # nunca tumba la ronda
        print(f"[api_comment_writer] {network}: error ({type(exc).__name__}: {str(exc)[:100]}); la ronda sigue sin comentarios")
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(merge(existing, replies), stream, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
