"""Construye decisions.json mecanicamente para follow/favourite/boost (02/10).

Motivo (David, 02/10: "mayor interaccion, menor coste"): el motor de
crecimiento (`mastodon_growth_scan.py`) ya calcula que acciones son validas
por candidato/post (bot/locked/politica/ya-interactuado filtrados, viewer
state real via relationships/cached_status_actionability) - decidir
follow/favourite uno a uno no anade criterio editorial real, solo repite lo
que el scan ya concluyo.

Reply y boost quedan fuera del lote mecanico, por motivos distintos:
- reply necesita texto con voz real (ortografia, anti-IA, nunca en bloque).
- boost es el equivalente de un repost/cita - mismo precedente ya fijado en
  REGLAS.md de X/Bluesky ("checklist de aporta algo", nunca mecanico) y, a
  nivel tecnico, `mastodon_build_plan.py` solo admite UNA accion por
  status_id (favourite y boost sobre el mismo post chocan como duplicado) -
  asi que hay que elegir, y esa eleccion es editorial, no mecanica.

Uso:
    python tools/mastodon_auto_decide.py
    -> lee mastodon_growth_state.json, escribe mastodon_decisions.json
       (solo follow+favourite, listo para 'growth_flow build'),
       mastodon_reply_candidates.json y mastodon_boost_candidates.json
       (ambos pendientes de criterio editorial, ordenados por score).
    --max-pool-follows N limita los follows del pool por ejecucion (la ronda
    diaria programada usa 30 para no disparar la relacion seguidos/seguidores).
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON")
STATE_IN = os.path.join(ROOT, "..", "mastodon_growth_state.json")
DECISIONS_OUT = os.path.join(ROOT, "..", "mastodon_decisions.json")
REPLY_OUT = os.path.join(ROOT, "..", "mastodon_reply_candidates.json")
BOOST_OUT = os.path.join(ROOT, "..", "mastodon_boost_candidates.json")
# Follows: solo comunidad (ya nos conocen) o cuentas del follow_pool (alta
# probabilidad de follow-back, ver mastodon_growth_scan._follow_pool). Los
# follows en frio fuera del pool convierten ~6% frente a ~43% (medido 02/10).
MAX_POOL_FOLLOWS = 120


def _boost_worthy(candidate, post, today):
    """Criterio comun a todas las redes (`scan_common.share_worthy`); aqui los datos propios de Mastodon (campo `language`, seguidores de la cuenta, edad del estado)."""
    import text_common as tc
    language = (post.get("language") or "").casefold()
    text = post.get("text") or ""
    spanish = (language == "es" or language.startswith("es-")) if language else (tc.looks_spanish(text) or None)
    try:
        age = (today - datetime.date.fromisoformat(str(post.get("created_at") or "")[:10])).days
    except ValueError:
        age = None
    return sc.share_worthy(text, spanish=spanish, niche_hits=tc.niche_hits(text), followers=candidate.get("followers"), age_days=age)


def default_max_boosts():
    """Boosts automaticos por ronda: 1 + etapa de la rampa, hasta 8 (~1,5 % del volumen, como los reposts de Bluesky; 06/10: paridad entre redes)."""
    try:
        import volume_ramp
        return min(8, 1 + volume_ramp.load(network="mastodon")["stage"])
    except Exception:
        return 2


def build(state, max_pool_follows=MAX_POOL_FOLLOWS, max_boosts=0, today=None):
    today = today or datetime.date.today()
    actions = []
    reply_candidates = []
    boost_candidates = []
    worthy = []        # (puntuacion, post) que pasan el criterio de compartir
    pool = {
        str(row.get("acct") or "").casefold(): row
        for row in state.get("follow_pool") or []
        if row.get("acct")
    }
    followed = set()
    pool_follows = 0  # el tope cuenta TODOS los follows de pool, vengan del shortlist o del resto
    for candidate in state.get("shortlist") or []:
        cid = candidate.get("id")
        acct = str(candidate.get("acct") or "").casefold()
        if "follow" in (candidate.get("actions") or []):
            if candidate.get("lane") == "community":
                actions.append({"candidate": cid, "kind": "follow"})
                followed.add(acct)
            elif acct in pool and pool_follows < max_pool_follows:
                actions.append({"candidate": cid, "kind": "follow"})
                followed.add(acct)
                pool_follows += 1
        for post in candidate.get("posts") or []:
            pid = post.get("id")
            post_actions = post.get("actions") or []
            row = {
                "post": pid,
                "acct": candidate.get("acct"),
                "lane": candidate.get("lane"),
                "score": candidate.get("score"),
                "url": post.get("url"),
                "text": post.get("text"),
            }
            if "favourite" in post_actions:
                actions.append({"post": pid, "kind": "favourite"})
            if "boost" in post_actions:
                boost_candidates.append(row)
                if max_boosts and _boost_worthy(candidate, post, today):
                    worthy.append((float(candidate.get("score") or 0), pid, str(candidate.get("acct") or "").casefold()))
            if "reply" in post_actions:
                reply_candidates.append(row)
    for acct, row in pool.items():
        if pool_follows >= max_pool_follows:
            break
        if acct in followed:
            continue
        actions.append({"account": row["acct"], "kind": "follow"})
        followed.add(acct)
        pool_follows += 1
    # boosts automaticos (06/10): los mejores posts que pasan el criterio; un boost REEMPLAZA al favorito del mismo estado (los dos sobre el mismo post chocan como duplicado)
    chosen, accounts_boosted = set(), set()
    for _, pid, acct in sorted(worthy, key=lambda row: -row[0]):             # uno por cuenta: dos boosts seguidos de la misma persona es spam
        if max_boosts and len(chosen) < max_boosts and acct not in accounts_boosted:
            chosen.add(pid)
            accounts_boosted.add(acct)
    if chosen:
        actions = [a for a in actions if not (a.get("kind") == "favourite" and a.get("post") in chosen)]
        actions += [{"post": pid, "kind": "boost"} for pid in sorted(chosen)]
    reply_candidates.sort(key=lambda row: -(row.get("score") or 0))
    boost_candidates.sort(key=lambda row: -(row.get("score") or 0))
    return actions, reply_candidates, boost_candidates


def main():
    if not os.path.exists(STATE_IN):
        print(f"No existe {STATE_IN} - ejecutar 'mastodon_growth_flow.py prepare' primero.")
        return 1
    with open(STATE_IN, encoding="utf-8") as stream:
        state = json.load(stream)

    max_follows = MAX_POOL_FOLLOWS
    if "--max-pool-follows" in sys.argv:
        max_follows = int(sys.argv[sys.argv.index("--max-pool-follows") + 1])
    max_boosts = int(sys.argv[sys.argv.index("--max-boosts") + 1]) if "--max-boosts" in sys.argv else default_max_boosts()
    actions, reply_candidates, boost_candidates = build(state, max_follows, max_boosts)

    decisions_out = DECISIONS_OUT
    if "--out" in sys.argv:
        # la ronda mecanica usa su propio fichero para no pisar el mastodon_decisions.json
        # que se edita a mano con replies/boosts (PROCESO.md)
        decisions_out = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
    with open(decisions_out, "w", encoding="utf-8") as stream:
        json.dump({"actions": actions}, stream, ensure_ascii=False, indent=2)
    with open(REPLY_OUT, "w", encoding="utf-8") as stream:
        json.dump(reply_candidates, stream, ensure_ascii=False, indent=2)
    with open(BOOST_OUT, "w", encoding="utf-8") as stream:
        json.dump(boost_candidates, stream, ensure_ascii=False, indent=2)

    by_kind = {}
    for row in actions:
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
    print(f"{decisions_out}: {len(actions)} acciones mecanicas ({by_kind}).")
    print(
        f"{REPLY_OUT}: {len(reply_candidates)} oportunidades de reply y "
        f"{BOOST_OUT}: {len(boost_candidates)} de boost, ambas pendientes de "
        "criterio editorial - anadir a mano a las actions de decisions.json "
        "antes de 'build' (reply con texto real, boost solo si pasa el "
        "checklist de 'aporta algo' de REGLAS.md)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
