"""Plan mecanico de Threads (03/10): likes y follows a partir de threads_candidates.json, sin tokens.

Mismo patron que `x_build_plan.py`. Solo like y follow: las respuestas (reply) llevan texto con voz
propia y siguen siendo decision editorial. Una accion barata por cuenta; los follows solo a cuentas
NUEVAS cuyo post habla de escribir/leer (nicho), con tope.

    python tools/threads_build_plan.py [--max-follows N]   # escribe SISTEMA_DIARIO_THREADS/threads_plan.json
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_THREADS")
CANDIDATES_JSON = os.path.join(ROOT, "threads_candidates.json")
PLAN_OUT = os.path.join(ROOT, "threads_plan.json")
NICHE = re.compile(r"\b(novela|novelas|libro|libros|lectur\w*|leer|escrib\w*|escritor\w*|autor\w*|autopublic\w*|"
                   r"fantas\w*|relato\w*|cuento\w*|poesia|poema\w*|manuscrito|capitulo\w*)\b", re.I)
# Cabecera del post en el volcado: "<usuario> [comunidad o etiqueta, hasta 2 palabras] <edad>"; la edad es
# "5 h", "3 min", "1 día" o una fecha "23/09/2026". El perfil del autor no la muestra: hay que quitarla.
SPAM = re.compile(r"drive\.google|pdf (?:gratis|drive)|libros? pdf|descarga(?:r)? gratis|t\.me/|wa\.me/", re.I)
_AGE = re.compile(r"^\S+(?:\s+(?!\d)\S+){0,2}?\s+(?:\d+\s*(?:min|h|d|s|sem|días?|dias?|horas?)\b|\d{1,2}/\d{1,2}/\d{4})\.?\s*", re.I)
# Contadores de likes/respuestas pegados al final ("... manta. 24", "... 1.2K")
_COUNTS = re.compile(r"(?:\s+\d+(?:[.,]\d+)?\s*[KkMm]?)+\s*$")


def fragment(text, size=40):
    """Trozo del post para que la ejecucion lo localice en el listado (sin el 'usuario hace 3 h')."""
    body = _AGE.sub("", " ".join((text or "").split()), count=1)
    body = _COUNTS.sub("", body).strip() or body
    if len(body) <= size:
        return body
    cut = body[:size]
    return cut[:cut.rfind(" ")] if " " in cut[10:] else cut


def build(candidates, max_follows=4):
    plan, handles, follows = [], set(), 0
    for item in candidates:
        handle = (item.get("handle") or "").lstrip("@")
        text = item.get("text") or ""
        if not handle or handle.casefold() in handles or not fragment(text):
            continue
        # 04/10 (David: likes a cuentas de ligue/sexo): solo se toca lo que habla de libros/escritura y nada
        # que el filtro comun (politica + ligue/sexo/chat de citas) rechace.
        if not NICHE.search(text) or sc.is_political(text) or SPAM.search(text):
            continue
        handles.add(handle.casefold())
        plan.append({"handle": handle, "kind": "like", "text_fragment": fragment(text),
                     "post_created_at": item.get("created_at") or item.get("created_time") or ""})
        if follows < max_follows and not item.get("known_date") and NICHE.search(text):
            plan.append({"handle": handle, "kind": "follow", "motivo": "autor/lector del nicho"})
            follows += 1
    return plan


def _done_fragments(registro_csv):
    """{(cuenta, fragmento)} de todos los likes y replies ya registrados: el registro guarda el fragmento del post, no su permalink."""
    import csv
    import threads_pool as pool
    out = set()
    try:
        with open(registro_csv, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if (row.get("tipo") or "").split("+")[0] in ("like", "reply") and row.get("post_resumen"):
                    out.add(pool.fragment_key(row.get("cuenta"), row["post_resumen"]))
    except OSError:
        pass
    return out


def build_from_pool(db, *, likes, follows, known=None, exclude_days=5, today=None, candidates=(), done_fragments=None):
    """Plan desde la RESERVA (05/10): los mejores posts acumulados por todos los scans recientes, no solo lo que mostro la pantalla en esta ronda.
    Un like por cuenta (abriendo el permalink), y follow solo a cuentas NUEVAS (nunca interactuadas) de las que se da like. Sin cuentas tocadas en los ultimos
    `exclude_days` dias. `candidates` (el volcado de este scan) se suma por si la reserva aun esta vacia."""
    import datetime
    import threads_pool as pool
    today = today or datetime.date.today()
    known = known or {}
    recent = set()
    for handle, when in known.items():
        try:
            if (today - datetime.date.fromisoformat(str(when)[:10])).days <= exclude_days:
                recent.add(str(handle).lstrip("@").casefold())
        except ValueError:
            continue
    # 06/10: ademas de posts concretos, la reserva tiene CUENTAS (pestana Perfiles y seguidores de las cuentas del nicho): like al ultimo post (`like_latest`) y follow.
    # Al menos un cuarto de los likes va a cuentas (diversidad y primer contacto de otra fuente); si faltan posts, cubren el hueco.
    account_quota = max(likes // 4, 0)
    accounts = pool.pick_accounts(db, account_quota, exclude_handles=frozenset(recent))
    taken = frozenset(recent) | {row["handle"].casefold() for row in accounts}
    now = datetime.datetime.combine(today, datetime.time(22, 0)) if today != datetime.date.today() else None       # con un `today` explicito (tests, reproducciones) la antiguedad de los posts se mide contra ese dia, no contra el reloj
    picked = pool.pick(db, max(0, likes - len(accounts)), exclude_handles=taken, exclude_fragments=frozenset(done_fragments or ()), now=now)
    plan, nfollows = [], 0
    post_follow_budget = follows - min(follows // 2, len(accounts))       # la mitad de los follows para cuentas de la reserva si las hay; si no, todos a autores de posts
    for row in picked:
        fragment_text = fragment(row["text"])
        item = {"handle": row["handle"], "kind": "like", "permalink": row["permalink"], "text_fragment": fragment_text,
                "post_created_at": row.get("created_at") or "", "motivo": f"growth:pool:score={row['score']}:src={row['source']}"}
        plan.append(item)
        if nfollows < post_follow_budget and row["handle"].casefold() not in {str(h).lstrip("@").casefold() for h in known}:
            plan.append({"handle": row["handle"], "kind": "follow", "motivo": f"growth:pool:autor/lector del nicho:src={row['source']}"})
            nfollows += 1
    for row in accounts:
        if nfollows < follows and (row["source"] == "backfollow" or row["handle"].casefold() not in {str(h).lstrip("@").casefold() for h in known}):   # a quien nos sigue se le devuelve el follow aunque ya lo conozcamos
            plan.append({"handle": row["handle"], "kind": "follow", "motivo": f"growth:acct:score={row['score']}:src={row['source']}"})
            nfollows += 1
        plan.append({"handle": row["handle"], "kind": "like_latest", "motivo": f"growth:acct:score={row['score']}:src={row['source']}"})
    picked = list(picked) + list(accounts)
    if len(picked) < likes and candidates:       # reserva vacia o pobre: lo que vio este scan
        have = {a["handle"].casefold() for a in plan}
        extra = [a for a in build(candidates, max(0, follows - nfollows)) if a["handle"].casefold() not in have]
        plan.extend(extra[:max(0, likes - len(picked)) * 2])
    return plan


def build_replies(db, stage_number, registro, rng=None):
    """Replies cortas por INTENCION (banco de `x_replies.py`, sin repetir en 7 dias) sobre los mejores posts de la reserva: pedir recomendaciones, libro terminado, avance de manuscrito...
    Mismo motor que X: la reply gana a un like sobre el mismo post y se ejecuta con `bank: True` (el banco repite frases a proposito)."""
    import x_replies
    import threads_pool as pool
    rows = pool.pick(db, 300, exclude_handles=frozenset(), exclude_fragments=frozenset(_done_fragments(registro)))
    built = x_replies.build_replies(rows, max_replies=min(8, x_replies.replies_per_round(stage_number)), used=x_replies.recent_phrases(registro), rng=rng, allow=__import__("relationship_policy").comment_filter("threads", registro))
    by_handle = {row["handle"].casefold(): row for row in rows}
    out = []
    for item in built:
        row = by_handle.get(str(item["handle"]).casefold())
        if not row:
            continue
        out.append({"handle": row["handle"], "kind": "reply", "permalink": row["permalink"],
                    "post_created_at": row.get("created_at") or "", "text_fragment": fragment(row["text"]), "text": item["text"], "bank": True, "post_text": (row.get("text") or "")[:500], "motivo": item["motivo"]})
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        import volume_ramp
        stage = volume_ramp.current(network="threads")
        likes, follows = stage["likes"], stage["follows"]
        stage_number = stage.get("stage", 1)
    except Exception:
        likes, follows, stage_number = 24, 4, 1
    max_follows = int(argv[argv.index("--max-follows") + 1]) if "--max-follows" in argv else follows
    max_likes = int(argv[argv.index("--max-likes") + 1]) if "--max-likes" in argv else likes
    try:
        with open(CANDIDATES_JSON, encoding="utf-8") as stream:
            candidates = json.load(stream)
    except (OSError, ValueError):
        candidates = []
    try:
        import threads_pool as pool
        db = pool.connect()
        try:
            plan = build_from_pool(db, likes=max_likes, follows=max_follows, known=sc.known_accounts(os.path.join(ROOT, "registro_interacciones.csv")), candidates=candidates,
                                   done_fragments=_done_fragments(os.path.join(ROOT, "registro_interacciones.csv")))
            replies = build_replies(db, stage_number, os.path.join(ROOT, "registro_interacciones.csv"))
            if replies:       # 07/10: igual que X, la reply por intencion sustituye al like del mismo post (comentar convierte mas que dar like)
                reply_handles = {a["handle"].casefold() for a in replies}
                plan = replies + [a for a in plan if not (a["kind"] in ("like", "like_latest") and a["handle"].casefold() in reply_handles)]
                print(f"replies por intencion: {len(replies)} ({', '.join(a['motivo'].split(':')[2] for a in replies)})")
        finally:
            db.close()
    except Exception as exc:
        print(f"(reserva no disponible: {type(exc).__name__}: {exc}; se usa el volcado del scan)")
        plan = build(candidates, max_follows)
    with open(PLAN_OUT, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=1)
    print(json.dumps({"plan": os.path.relpath(PLAN_OUT, os.path.join(ROOT, "..")).replace(os.sep, "/"), "actions": len(plan)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
