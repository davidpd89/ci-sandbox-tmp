"""Construye plan.json mecanicamente a partir de x_candidates.json (02/10).

Motivo (David, 02/10: "mayor interaccion, menor coste"): x_scan.py ya decide
el 'kind' de cada candidato desde el 23/09 (_suggest_kind) - transcribirlo a
mano uno a uno es trabajo caro que no anade criterio real, solo repite lo que
el propio scan ya concluyo. Este script toma TODOS los candidatos follow/like
elegibles (no un subconjunto curado) y los escribe directo a plan.json; el
unico filtrado real que queda para un humano/Claude son las 'reply', porque
ahi si hace falta redactar texto con voz real (ver REGLAS.md, "Ortografia
real" - nunca generar texto de respuesta en bloque sin revisión editorial).

Uso:
    python tools/x_build_plan.py
    -> escribe x_plan.json (follow+like, listo para x_execute.py) y
       x_reply_candidates.json (pendientes de redactar a mano, texto=None)
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_X")
CANDIDATES_JSON = os.path.join(ROOT, "x_candidates.json")
PLAN_OUT = os.path.join(ROOT, "x_plan.json")
REPLY_OUT = os.path.join(ROOT, "x_reply_candidates.json")


def _repostable(item):
    """Checklist de REGLAS.md para un repost sin comentario: pieza de una lista curada del nicho
    (editoriales/autores, no hashtag a ciegas), con contenido propio y sin politica ni peticion de opinion."""
    text = item.get("text") or ""
    return (str(item.get("source", "")).startswith("lista:") and len(text) >= 50
            and not sc.is_political(text) and not sc.asks_for_opinion(text))


def build(candidates, max_follows=12, max_reposts=3, max_likes=None):
    """Mezcla diaria completa: likes sin tope (la ronda lo recorta por presupuesto), hasta `max_follows`
    follows nuevos (X castiga el seguimiento masivo), `max_reposts` reposts (REGLAS: 2-3/dia, solo si aporta)
    y las replies quedan pendientes para redactarlas con voz real (citas y respuestas las escribe Claude)."""
    plan = []
    follows = 0
    reposts = 0
    likes = 0
    seen_handles = set()
    seen_urls = set()
    pending_replies = []
    for item in candidates:
        kind = item.get("kind")
        handle = item.get("handle")
        url = item.get("url")
        if kind == "follow":
            if not handle or handle in seen_handles or follows >= max_follows:
                continue
            seen_handles.add(handle)
            follows += 1
            plan.append({"kind": "follow", "handle": handle})
        elif kind == "like":
            if not url or url in seen_urls or (max_likes is not None and likes >= max_likes):
                continue
            seen_urls.add(url)
            if reposts < max_reposts and _repostable(item):
                reposts += 1
                plan.append({"kind": "repost", "url": url, "handle": handle})
            else:
                likes += 1
                plan.append({"kind": "like", "url": url})
        elif kind == "reply":
            if item.get("ya_comentado"):
                continue
            # "lee mi texto" / "que os parece mi relato": se ignora (03/10)
            if sc.asks_for_opinion(item.get("text") or item.get("post_text") or ""):
                continue
            pending_replies.append(item)
        # cualquier otro kind futuro se ignora aqui a proposito - que falle
        # de forma visible (ausente del plan) en vez de adivinar que hacer.
    return plan, pending_replies


def _recent_handles(known, exclude_days, today):
    out = set()
    for handle, when in (known or {}).items():
        try:
            if (today - datetime.date.fromisoformat(str(when)[:10])).days <= exclude_days:
                out.add(str(handle).lstrip("@").casefold())
        except ValueError:
            continue
    return out


def build_from_pool(db, *, likes, follows, known=None, done_urls=frozenset(), exclude_days=5, today=None, now=None):
    """Plan desde la RESERVA (06/10, como Threads): los mejores posts acumulados por todos los scans recientes —no solo lo que mostro la pantalla en esta ronda—.
    Un like por cuenta (abriendo el permalink) y follow solo a cuentas NUEVAS de las que se da like; al menos un cuarto de los likes va a CUENTAS de la reserva
    (pestana Personas, seguidores de las semillas, quien acaba de seguirnos): like al ultimo post propio y reciente (`like_latest`) y follow. Sin cuentas tocadas en los
    ultimos `exclude_days` dias ni posts ya tratados."""
    import x_pool as pool
    today = today or datetime.date.today()
    known = known or {}
    known_cf = {str(h).lstrip("@").casefold() for h in known}
    recent = _recent_handles(known, exclude_days, today)
    accounts = pool.pick_accounts(db, max(likes // 4, 0), exclude_handles=frozenset(recent))
    taken = frozenset(recent) | {row["handle"].casefold() for row in accounts}
    picked = [row for row in pool.pick(db, max(0, likes - len(accounts)) + 20, exclude_handles=taken, now=now) if row["permalink"] not in done_urls][:max(0, likes - len(accounts))]
    plan, nfollows = [], 0
    post_follow_budget = follows - min(follows // 2, len(accounts))       # la mitad de los follows para cuentas de la reserva si las hay; si no, todos a autores de posts
    for row in picked:
        plan.append({"kind": "like", "url": row["permalink"], "handle": row["handle"], "motivo": f"growth:pool:score={row['score']}:src={row['source']}"})
        if nfollows < post_follow_budget and row["handle"].casefold() not in known_cf:
            plan.append({"kind": "follow", "handle": row["handle"], "motivo": f"growth:pool:autor/lector del nicho:src={row['source']}"})
            nfollows += 1
    for row in accounts:
        if nfollows < follows and (row["source"] == "backfollow" or row["handle"].casefold() not in known_cf):      # a quien nos sigue se le devuelve el follow aunque lo conozcamos
            plan.append({"kind": "follow", "handle": row["handle"], "motivo": f"growth:acct:score={row['score']}:src={row['source']}"})
            nfollows += 1
        plan.append({"kind": "like_latest", "handle": row["handle"], "motivo": f"growth:acct:score={row['score']}:src={row['source']}"})
    return plan


def done_urls(registro_csv):
    """URLs de posts ya tratados (like, repost, reply, cita) con resultado confirmado/publicado: el registro guarda el permalink en `post_resumen`."""
    import csv
    out = set()
    try:
        with open(registro_csv, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                url = (row.get("post_resumen") or "").strip()
                if url.startswith("https://") and row.get("resultado") in ("confirmado", "publicado"):
                    out.add(url.rstrip("/"))
    except OSError:
        pass
    return out


def merge(first, second):
    """Une dos planes sin repetir acciones: un follow por cuenta, un like por URL y a lo sumo un like_latest por cuenta."""
    out, handles_follow, urls, latest = [], set(), set(), set()
    for item in list(first) + list(second):
        kind = item["kind"]
        if kind == "follow":
            key = item["handle"].casefold()
            if key in handles_follow:
                continue
            handles_follow.add(key)
        elif kind == "like_latest":
            key = item["handle"].casefold()
            if key in latest:
                continue
            latest.add(key)
        else:
            if item["url"] in urls:
                continue
            urls.add(item["url"])
        out.append(item)
    return out


def is_fresh(path, today=None):
    """Solo se construye plan desde un volcado generado hoy."""
    today = today or datetime.date.today()
    return datetime.date.fromtimestamp(os.path.getmtime(path)) == today


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not os.path.exists(CANDIDATES_JSON):
        print(f"No existe {CANDIDATES_JSON} - ejecutar x_scan.py primero.")
        return 1
    if not is_fresh(CANDIDATES_JSON):
        print(f"{CANDIDATES_JSON} no es de hoy - ejecutar x_scan.py de nuevo.")
        return 1
    with open(CANDIDATES_JSON, encoding="utf-8") as stream:
        candidates = json.load(stream)
    try:
        import volume_ramp
        stage = volume_ramp.current(network="x")
        likes, follows = stage["likes"], stage["follows"]
        stage_number = stage.get("stage", 1)
    except Exception:
        likes, follows, stage_number = 40, 8, 1
    likes = int(argv[argv.index("--max-likes") + 1]) if "--max-likes" in argv else likes
    follows = int(argv[argv.index("--max-follows") + 1]) if "--max-follows" in argv else follows

    # candidatos del scan (reciprocidad: notificaciones, listas curadas, comentaristas): follows hasta el tope de la etapa y reposts de listas curadas
    plan, pending_replies = build(candidates, max_follows=follows, max_reposts=2 + 2 * stage_number, max_likes=max(likes // 2, 10))   # la otra mitad la elige la reserva (mejor puntuada)
    try:
        import x_pool as pool
        registro = os.path.join(ROOT, "registro_interacciones.csv")
        db = pool.connect()
        try:
            used_follows = sum(1 for a in plan if a["kind"] == "follow")
            known = sc.known_accounts(registro)
            done = done_urls(registro)
            from_pool = build_from_pool(db, likes=likes, follows=max(0, follows - used_follows), known=known, done_urls=done)
            # 06/10 (GPT + pesos del algoritmo de X): las replies por intencion van PRIMERO (el reply gana a un like sobre la misma URL en `merge`)
            import x_replies
            replies = x_replies.build_replies(
                pool.pick(db, 400, exclude_handles=frozenset(_recent_handles(known, 3, datetime.date.today()))), max_replies=x_replies.replies_per_round(stage_number),
                used=x_replies.recent_phrases(registro), done_urls=done, recent_handles=x_replies.replied_handles(registro),
                allow=__import__("relationship_policy").comment_filter("x", registro))
        finally:
            db.close()
        plan = merge(replies, merge(plan, from_pool))
        print(f"replies por intencion: {len(replies)} ({', '.join(r['motivo'].split(':')[2] for r in replies)})")
    except Exception as exc:
        print(f"(reserva no disponible: {type(exc).__name__}: {exc}; solo el volcado del scan)")

    with open(PLAN_OUT, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
    with open(REPLY_OUT, "w", encoding="utf-8") as stream:
        json.dump(pending_replies, stream, ensure_ascii=False, indent=2)

    by_kind = {}
    for row in plan:
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
    print(f"{PLAN_OUT}: {len(plan)} acciones mecanicas ({by_kind}).")
    print(
        f"{REPLY_OUT}: {len(pending_replies)} candidatos a reply pendientes "
        "de redactar texto real (revisar tildes/ene antes de anadirlos a "
        f"{PLAN_OUT} o a un plan aparte)."
    )
    print(json.dumps({"plan": os.path.relpath(PLAN_OUT, os.path.join(ROOT, "..")).replace(os.sep, "/"), "actions": len(plan)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
