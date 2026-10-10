"""Respuestas sin contestar a NUESTRAS replies (02/10).

Medido: 15 de 20 personas que contestaron a una reply nuestra en Bluesky se
quedaron sin respuesta. Son los contactos mas calientes (ya hablaron contigo),
mantener la conversacion es el gesto mas barato para ganar un seguidor y no
exige scan. Esta herramienta los lista en compacto y construye el plan.

    python tools/conversation_followups.py bluesky              # lista F01.. y guarda <red>_followups.json
    python tools/conversation_followups.py mastodon
    python tools/conversation_followups.py bluesky --build decisions.json [plan.json]

decisions.json: {"actions": [{"id": "F01", "text": "..."}]}. El plan resultante
se ejecuta con bluesky_execute.py / mastodon_execute.py (preflight normal).
Solo se listan respuestas en espanol, de otras personas y sin contestar; se
descartan cierres de conversacion (es_closer) y cuentas puente.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc
import like_context_policy as lcp

ROOT = os.path.join(os.path.dirname(__file__), "..")
URL_OR_TAG = re.compile(r"(https?://\S+|#\w+|@\S+)")
SPANISH_HINT = {"de", "la", "el", "que", "y", "en", "un", "una", "los", "las", "por",
                "con", "para", "es", "se", "lo", "mi", "muy", "pero", "como", "no", "me"}


MAX_REPLIES_PER_ACCOUNT = 3   # tope duro de replies nuestras a la misma cuenta (registro historico)


def worth_answering(text, handle, answers_question=False):
    """Politica de David (03/10): una conversacion se contesta UNA vez; despues solo se responde
    si la persona nos PREGUNTA algo (el hilo de 5 replies seguidas sobre una lectura conjunta se
    hacia pesado). Una respuesta a nuestra pregunta, un 'gracias' o una opinion sin pregunta se
    queda en like (ya lo da `like_all`). `answers_question` se conserva por compatibilidad y ya
    no abre la puerta: contestar a quien contesta es lo que alargaba los hilos."""
    plain = " ".join(URL_OR_TAG.sub(" ", text or "").split())
    if sc.is_feed_bridge(handle) or sc.asks_for_opinion(plain):
        return False
    if "?" not in plain or len(plain) < 12:
        return False
    return not (sc.is_political(plain) or sc.looks_activist(plain))


MAX_AGE_DAYS = 14


def _recent_first(rows, today=None, max_age_days=MAX_AGE_DAYS):
    """Orden por fecha descendente (la respuesta mas reciente de cada persona es la
    que se contesta) y descarte de lo muy antiguo. Filas sin fecha se conservan al final."""
    import datetime
    today = today or datetime.date.today()
    cutoff = today - datetime.timedelta(days=max_age_days)

    def when(row):
        try:
            return datetime.date.fromisoformat((row.get("created") or "")[:10])
        except ValueError:
            return None
    dated = sorted((r for r in rows if when(r) is not None), key=lambda r: r["created"], reverse=True)
    return [r for r in dated if when(r) >= cutoff] + [r for r in rows if when(r) is None]


def make_items(rows, today=None, replies_sent=None, *, network=None, verify_threads=False):
    """rows: dicts {handle,text,url,mine,created}. Devuelve items F01.. de uno por
    cuenta, la respuesta mas reciente de cada una y con un maximo de 14 dias.
    `replies_sent` = {handle: replies nuestras ya enviadas}: con MAX_REPLIES_PER_ACCOUNT no se insiste."""
    items, seen = [], set()
    replies_sent = replies_sent or {}
    for row in _recent_first(rows, today):
        key = row["handle"].casefold()
        if key in seen or replies_sent.get(key, 0) >= MAX_REPLIES_PER_ACCOUNT                 or not worth_answering(row["text"], row["handle"]):
            continue
        context, turns = "", []
        if verify_threads:
            import conversation_turn_policy as ctp
            if ctp.is_closed_turn(row["text"]):
                continue
            if network in ("bluesky", "mastodon"):
                turns = ctp.fetch_verified_thread(network, row)
                if turns and turns[-1]["post_id"] != str(row.get("ref")):
                    turns = []
            if turns:
                context = ctp.render_thread(turns)
            else:
                # No fingir lectura completa del hilo. GPT conserva la
                # decisión de null ante invitaciones vagas o contexto pobre.
                context = (
                    "CONTEXTO PARCIAL: no se recuperó todo el hilo. "
                    "Nuestra intervención conocida: " +
                    str(row.get("mine") or "[no disponible]") +
                    ". Última respuesta recibida: " + str(row["text"]) +
                    ". Evita suponer antecedentes; puedes devolver null."
                )
        seen.add(key)
        items.append({"id": f"F{len(items) + 1:02d}", "handle": row["handle"],
                      "text": " ".join(URL_OR_TAG.sub(" ", row["text"]).split()),
                      "url": row["url"], "mine": row.get("mine", ""),
                      "post_created_at": row.get("created") or "",
                      **({"context": context, "thread_turns": turns, "context_quality": "complete" if turns else "partial", "reply_to_us": True} if context else {})})
    return items


def build_plan(items, decisions, kind="reply"):
    by_id = {item["id"]: item for item in items}
    plan = []
    for index, decision in enumerate(decisions.get("actions", [])):
        item = by_id.get(decision.get("id"))
        if not item:
            raise ValueError(f"decision {index}: id desconocido {decision.get('id')!r}")
        text = (decision.get("text") or "").strip()
        if not text:
            raise ValueError(f"decision {index}: falta text")
        if "?" in text and not decision.get("allow_question"):
            raise ValueError(f"decision {index}: un seguimiento no termina con pregunta (se alargaria el hilo); "
                             "contesta lo que preguntan sin devolver otra, o pon allow_question")
        plan.append({"handle": item["handle"], "kind": kind, "lane": "community",
                     "url": item["url"], "text": text, "post_text": item["text"],
                     "post_created_at": item.get("post_created_at") or "",
                     "motivo": f"followup:{item['id']}:respuesta a nuestra reply",
                     "thread_turns": item.get("thread_turns", []), "context_quality": item.get("context_quality", "partial"), "reply_to_us": True})
    return plan


# ---------------------------------------------------------------- Bluesky
def bluesky_all_notifications(b, did, today=None, max_age_days=MAX_AGE_DAYS * 2, max_pages=8):
    """Respuestas recibidas via listNotifications (paginado, 1-8 llamadas) en vez de recorrer
    hilo a hilo (~40 llamadas): mas barato, mas robusto ante posts borrados/bloqueados y
    cubre tambien menciones. `answered` sale de los padres a los que ya respondimos."""
    import datetime
    today = today or datetime.date.today()
    cutoff = today - datetime.timedelta(days=max_age_days)
    notes, cursor = [], None
    for _ in range(max_pages):
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = b._get(b.AUTH_BASE, "app.bsky.notification.listNotifications", params, auth=True)
        batch = page.get("notifications") or []
        notes += [n for n in batch if isinstance(n, dict) and n.get("reason") in ("reply", "mention")]
        cursor = page.get("cursor")
        oldest = (next((n.get("indexedAt") for n in reversed(batch)
                        if isinstance(n, dict) and n.get("indexedAt")), "") or "")[:10]
        if not cursor or not batch or (oldest and oldest < cutoff.isoformat()):
            break
    notes = [n for n in notes if (n.get("author") or {}).get("did") != did
             and (n.get("indexedAt") or "")[:10] >= cutoff.isoformat()]
    answered_parents = b._own_reply_parent_uris()
    uris = [n["uri"] for n in notes]
    liked, fetched = {}, {}
    for i in range(0, len(uris), 25):
        data = b._get(b.AUTH_BASE, "app.bsky.feed.getPosts", {"uris": uris[i:i + 25]}, auth=True)
        for post in data.get("posts", []):
            liked[post["uri"]] = bool((post.get("viewer") or {}).get("like"))
            fetched[post["uri"]] = post
    subjects = sorted({n.get("reasonSubject") for n in notes if n.get("reasonSubject")})
    mine = {}
    for i in range(0, len(subjects), 25):
        data = b._get(b.PUBLIC_BASE, "app.bsky.feed.getPosts", {"uris": subjects[i:i + 25]}, auth=False)
        for post in data.get("posts", []):
            mine[post["uri"]] = (post.get("record") or {}).get("text", "")
    rows = []
    for n in notes:
        handle = n["author"]["handle"]
        target = fetched.get(n["uri"]) or {}
        note_record = n.get("record") if isinstance(n.get("record"), dict) else None
        target_record = target.get("record") if isinstance(target.get("record"), dict) else None
        record = target_record or note_record or {}
        media = (lcp.bluesky_has_visual(n) or lcp.bluesky_has_visual(target)
                 if note_record is not None or target_record is not None else None)
        rows.append({
            "handle": handle, "text": record.get("text", ""),
            "url": f"https://bsky.app/profile/{handle}/post/{n['uri'].rsplit('/', 1)[-1]}",
            "mine": mine.get(n.get("reasonSubject"), ""), "ref": n["uri"],
            "created": record.get("createdAt") or "",
            "answered": n["uri"] in answered_parents, "liked": liked.get(n["uri"], False),
            "media_present": media,
            "sensitive": lcp.bluesky_sensitive(n) or lcp.bluesky_sensitive(target),
        })
    return rows


def bluesky_all():
    """Respuestas de otros a nuestros posts: por notificaciones (barato) y, si falla,
    recorriendo hilos como antes."""
    import bluesky_interact as b
    did = b._session()["did"]
    try:
        return bluesky_all_notifications(b, did)
    except Exception as exc:
        print(f"aviso: listNotifications fallo ({exc}); se recorren los hilos", file=sys.stderr)
        return bluesky_all_threads(b, did)


def bluesky_all_threads(b, did):
    """Todas las respuestas de otros a NUESTROS posts (replies y originales),
    con `answered` (ya contestamos debajo) y `liked` (ya tiene nuestro like)."""
    mine = [(r["uri"], r["value"].get("text", ""), bool(r["value"].get("reply")))
            for r in b._iter_own_posts()]
    roots = []
    for i in range(0, len(mine), 25):
        chunk = mine[i:i + 25]
        data = b._get(b.PUBLIC_BASE, "app.bsky.feed.getPosts",
                      {"uris": [u for u, _, _ in chunk]}, auth=False)
        texts = {u: t for u, t, _ in chunk}
        roots += [(p["uri"], texts.get(p["uri"], "")) for p in data["posts"] if p.get("replyCount", 0) > 0]
    rows = []
    for uri, own_text in roots:
        thread = b._get(b.AUTH_BASE, "app.bsky.feed.getPostThread",
                        {"uri": uri, "depth": 2}, auth=True)["thread"]
        for kid in thread.get("replies", []):
            if kid.get("$type", "app.bsky.feed.defs#threadViewPost") != "app.bsky.feed.defs#threadViewPost":
                continue  # #blockedPost / #notFoundPost no traen "post"
            post = kid.get("post")
            if not isinstance(post, dict) or (post.get("author") or {}).get("did") == did:
                continue
            answered = any(((g.get("post") or {}).get("author") or {}).get("did") == did
                           for g in (kid.get("replies") or []) if isinstance(g, dict))
            handle = post["author"]["handle"]
            url = f"https://bsky.app/profile/{handle}/post/{post['uri'].rsplit('/', 1)[-1]}"
            record = post.get("record") if isinstance(post.get("record"), dict) else {}
            rows.append({"handle": handle, "text": record.get("text", ""), "url": url,
                         "mine": own_text, "ref": post["uri"], "answered": answered,
                         "created": record.get("createdAt", ""),
                         "liked": bool((post.get("viewer") or {}).get("like")),
                         "media_present": lcp.bluesky_has_visual(post) if record else None,
                         "sensitive": lcp.bluesky_sensitive(post)})
    return rows


def bluesky_like(row):
    import bluesky_interact as b
    return b.like(row["ref"])


# --------------------------------------------------------------- Mastodon
def mastodon_all():
    """Todas las menciones/respuestas de otros, con `answered` y `liked`."""
    import mastodon_interact as m
    me = m._get("accounts/verify_credentials")
    own_id = str(me["id"])
    # 06/10: `include_filtered` trae tambien las menciones que Mastodon aparta en «Notificaciones filtradas» (la bienvenida de @rober@masto.es estaba ahi y ningun script la leia)
    notes = m._get_paginated("notifications", {"types[]": "mention", "limit": 40, "include_filtered": "true"}, max_pages=3)
    rows = []
    for note in notes:
        status = note.get("status") or {}
        account = note.get("account") or {}
        if not status or str(account.get("id")) == own_id:
            continue
        context = m._get(f"statuses/{status['id']}/context")
        answered = any(str(d.get("account", {}).get("id")) == own_id
                       and str(d.get("in_reply_to_id")) == str(status["id"])
                       for d in context.get("descendants", []))
        rows.append({"handle": account["acct"], "text": m._plain_text(status.get("content")),
                     "url": status.get("url") or status.get("uri", ""), "mine": "",
                     "ref": str(status["id"]), "answered": answered,
                     "created": status.get("created_at") or "",
                     "liked": bool(status.get("favourited")),
                     "media_present": lcp.mastodon_has_visual(status),
                     "sensitive": status.get("sensitive") is True or bool(status.get("spoiler_text"))})
    return rows


def mastodon_like(row):
    import mastodon_interact as m
    return m.favourite(row["ref"])


def likeable_text(text):
    """Compatibilidad con #83, delegando en la política editorial compartida."""
    return lcp.can_like(text, media_present=False)[0]


def like_all(rows, liker, out=print, pause=None, *, network=None):
    """Da like/favourite a toda respuesta de otra persona que aun no lo tenga
    (gesto barato y muy valorado: la persona ve que alguien leyo su respuesta).
    Devuelve (hechos, fallos). Un fallo no detiene el resto salvo 429."""
    done = failed = 0
    seen = set()
    for row in rows:
        if row["liked"] or row["ref"] in seen or sc.is_feed_bridge(row["handle"]):
            continue
        allowed, reason = lcp.can_like(
            row.get("text"), media_present=row.get("media_present", False),
            sensitive=row.get("sensitive") is True,
        )
        if not allowed:
            out(f"OMITIDO like {row['handle']}: {reason}")
            continue
        seen.add(row["ref"])
        if network is not None:
            import circuit_breaker as cb
            allowed, reason = cb.write_preflight(network)
            if not allowed:
                out(f"[{network}] cortacircuitos ABIERTO: {reason}; dejar likes restantes")
                break
        try:
            liker(row)
            done += 1
        except Exception as exc:
            failed += 1
            out(f"FALLO like {row['handle']}: {exc}")
            if "429" in str(exc) or "RateLimit" in type(exc).__name__:
                break
        if pause:
            pause()
    return done, failed


def replies_sent(net):
    """{handle: replies nuestras confirmadas} del registro historico de la red."""
    import csv
    path = os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "registro_interacciones.csv")
    counts = {}
    try:
        with open(path, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("resultado") == "confirmado" and "reply" in (row.get("tipo") or "").split("+"):
                    handle = (row.get("cuenta") or "").lstrip("@").casefold()
                    if handle and not handle.startswith("http"):
                        counts[handle] = counts.get(handle, 0) + 1
    except OSError:
        pass
    return counts


def _unanswered(rows):
    return [row for row in rows if not row["answered"]]


ALL_SOURCES = {"bluesky": (bluesky_all, bluesky_like), "mastodon": (mastodon_all, mastodon_like)}
SOURCES = {name: (lambda f=src[0]: _unanswered(f())) for name, src in ALL_SOURCES.items()}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in SOURCES:
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    net = argv[0]
    cache = os.path.join(ROOT, f"{net}_followups.json")
    if "--like" in argv:
        rows = ALL_SOURCES[net][0]()
        done, failed = like_all(rows, ALL_SOURCES[net][1], pause=lambda: sc.pause(1, 3), network=net)
        print(f"[{net}] {done} likes a respuestas recibidas ({failed} fallos); "
              f"{sum(1 for r in rows if not r['answered'])} sin contestar")
        return 0
    if "--build" in argv:
        pos = argv.index("--build")
        with open(argv[pos + 1], encoding="utf-8") as stream:
            decisions = json.load(stream)
        with open(cache, encoding="utf-8") as stream:
            items = json.load(stream)
        out = argv[pos + 2] if len(argv) > pos + 2 else os.path.join(ROOT, f"{net}_followups_plan.json")
        plan = build_plan(items, decisions)
        with open(out, "w", encoding="utf-8") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=1)
        for note in sc.reply_style_report([row["text"] for row in plan]):
            print(f"ESTILO: {note}", file=sys.stderr)
        print(f"{out}: {len(plan)} replies")
        return 0
    items = make_items(SOURCES[net](), replies_sent=replies_sent(net), network=net, verify_threads=True)
    with open(cache, "w", encoding="utf-8") as stream:
        json.dump(items, stream, ensure_ascii=False, indent=1)
    print(f"{len(items)} respuestas sin contestar ({net}):")
    for item in items:
        print(f"{item['id']} @{item['handle']}: {item['text'][:220]}")
        if item["mine"]:
            print(f"      (tu reply: {item['mine'][:110]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
