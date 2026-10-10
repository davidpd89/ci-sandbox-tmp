"""Fidelizacion comun (07/10/2026, David: «ir mirando quien nos da like, darselo, comentarios... premiar a la comunidad y llevar ese tracking»).

Ciclo UNICO para cada red:
  1. COSECHA: lee las notificaciones (quien nos da like, reposta, sigue o nos comenta) y lo anota en `00_OPERATIVO/inbound_interacciones.csv` (sin duplicar).
  2. PREMIO: a cada cuenta que hizo algo por nosotros en los ultimos 14 dias:
       * like en su ultimo post original (en espanol, sin politica);
       * follow de vuelta si no la seguimos;
       * respuesta a su comentario (escrita por ChatGPT, `reply_writer`; `reply_to_us`), con la regla de `relationship_policy` (uno por cada comentario suyo);
       * a quien solo nos dio like/repost y nunca le comentamos: UN comentario de primer paso en su ultimo post.
  3. TRACKING: `python tools/loyalty.py report` dice, por red, cuantos nos han dado algo y cuantos han recibido premio.

    python tools/loyalty.py bluesky|mastodon          # cosecha + plan `<red>_loyalty_plan.json` (se ejecuta con <red>_execute.py)
    python tools/loyalty.py report
Un fallo nunca tumba la ronda (sale siempre con 0).
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import relationship_policy as rp
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..")
WINDOW_DAYS = 14
MAX_LIKES, MAX_FOLLOWS, MAX_REPLIES, MAX_FIRST_STEP = 40, 30, 12, 8
SPANISH_HINT = {"de", "la", "el", "que", "y", "en", "un", "una", "los", "las", "por", "con", "para", "es", "se", "lo", "mi", "muy", "pero", "como", "no", "me", "su", "al"}
KIND_MAP = {"like": "like", "favourite": "like", "repost": "repost", "reblog": "repost", "follow": "follow", "reply": "comment", "mention": "comment", "quote": "comment"}


def _spanish(text):
    words = set(re.findall(r"[a-záéíóúñ]+", (text or "").casefold()))
    return len(words & SPANISH_HINT) >= 2


def _clean(text):
    return " ".join(re.sub(r"(https?://\S+|#\w+|@\S+)", " ", text or "").split())


def _plan_dir(network):
    return os.path.join(ROOT, f"SISTEMA_DIARIO_{network.upper()}")


def _registro(network):
    return os.path.join(_plan_dir(network), "registro_interacciones.csv")


# ------------------------------------------------------------- cosecha
def harvest_bluesky(max_pages=3):
    import bluesky_interact as b
    did = b._session()["did"]
    out, cursor = [], None
    cutoff = (datetime.date.today() - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    for _ in range(max_pages):
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = b._get(b.AUTH_BASE, "app.bsky.notification.listNotifications", params, auth=True)
        batch = page.get("notifications") or []
        for n in batch:
            author = n.get("author") or {}
            kind = KIND_MAP.get(n.get("reason"))
            if not kind or author.get("did") == did or (n.get("indexedAt") or "")[:10] < cutoff:
                continue
            rkey = (n.get("uri") or "").rsplit("/", 1)[-1]
            out.append({"handle": author.get("handle", ""), "kind": kind, "date": (n.get("indexedAt") or "")[:10],
                        "url": f"https://bsky.app/profile/{author.get('handle')}/post/{rkey}" if kind == "comment" else "",
<<<<<<< HEAD
                        "text": (n.get("record") or {}).get("text", "") if kind == "comment" else "", "ref": n.get("uri", ""), "subject": n.get("reasonSubject", "")})
=======
                        "text": (n.get("record") or {}).get("text", "") if kind == "comment" else "", "ref": n.get("uri", ""), "subject": n.get("reasonSubject", ""),
                        "post_created_at": (n.get("record") or {}).get("createdAt") or ""})
>>>>>>> origin/research/public-reuse-parent
        cursor = page.get("cursor")
        if not cursor or not batch or (batch[-1].get("indexedAt") or "")[:10] < cutoff:
            break
    return out


def harvest_mastodon(max_pages=3):
    import mastodon_interact as m
    out = []
    cutoff = (datetime.date.today() - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    for n in m.notifications(40, max_pages=max_pages):
        kind = KIND_MAP.get(n.get("type"))
        account = n.get("account") or {}
        if not kind or (n.get("created_at") or "")[:10] < cutoff:
            continue
        status = n.get("status") or {}
        out.append({"handle": account.get("acct", ""), "account_id": account.get("id"), "kind": kind, "date": (n.get("created_at") or "")[:10],
<<<<<<< HEAD
                    "url": status.get("url") or "" if kind == "comment" else "", "text": m._plain_text(status.get("content")) if kind == "comment" else "", "ref": str(status.get("id") or "")})
=======
                    "url": status.get("url") or "" if kind == "comment" else "", "text": m._plain_text(status.get("content")) if kind == "comment" else "", "ref": str(status.get("id") or ""),
                    "post_created_at": status.get("created_at") or ""})
>>>>>>> origin/research/public-reuse-parent
    return out


HARVEST = {"bluesky": harvest_bluesky, "mastodon": harvest_mastodon}


def record(network, events):
    """Anota los eventos en el registro de entradas. Devuelve cuantos eran nuevos."""
    new = 0
    for event in events:
        day = datetime.date.fromisoformat(event["date"]) if event.get("date") else None
        if rp.log_inbound(network, event["handle"], event["kind"], today=day):
            new += 1
    return new


# ------------------------------------------------------------- premio
def loyal_accounts(network, days=WINDOW_DAYS, today=None):
    """{handle: {'like': n, 'repost': n, 'follow': n, 'comment': n}} de los ultimos `days` dias."""
    today = today or datetime.date.today()
    cutoff = (today - datetime.timedelta(days=days)).isoformat()
    out = {}
    for row in rp._rows(rp.INBOUND):
        if row.get("red") == network and (row.get("fecha") or "") >= cutoff:
            entry = out.setdefault(rp.norm(row["handle"]), {})
            entry[row["tipo"]] = entry.get(row["tipo"], 0) + 1
    return out


def loyal_handles(network, limit=20):
    """Cuentas fieles ordenadas por lo que hicieron por nosotros (comentar pesa mas que un like): los scans de las redes web las meten como candidatas prioritarias."""
    weight = {"comment": 3, "repost": 2, "follow": 2, "like": 1}
    ranked = sorted(loyal_accounts(network).items(), key=lambda kv: -sum(weight.get(k, 1) * n for k, n in kv[1].items()))
    return [h for h, _ in ranked if not sc.is_feed_bridge(h)][:limit]


def _done(network):
    """({cuenta: veces que ya la seguimos}, {cuenta: likes dados}, {urls con like nuestro}) del registro de la red."""
    followed, liked_urls = set(), set()
    for row in rp._rows(_registro(network)):
        if row.get("resultado") not in rp.OK_RESULTS + ("saltado_ya_seguido", "saltado_ya_reaccionado"):
            continue
        kind = (row.get("tipo") or "").strip().casefold()
        if kind == "follow":
            followed.add(rp.norm(row.get("cuenta")))
        elif kind in ("like", "favourite"):
            liked_urls.add(row.get("post_resumen") or "")
    return followed, liked_urls


def _latest_post_bluesky(handle):
    import bluesky_interact as b
    data = b._get(b.AUTH_BASE, "app.bsky.feed.getAuthorFeed", {"actor": handle, "filter": "posts_no_replies", "limit": 8}, auth=True)
    for item in (data or {}).get("feed") or []:
        if not isinstance(item, dict):
            continue
        post = item.get("post") if isinstance(item.get("post"), dict) else {}
        if item.get("reason") or (post.get("viewer") or {}).get("like"):
            continue
        record = post.get("record") if isinstance(post.get("record"), dict) else {}
        text = _clean(record.get("text"))
        import like_context_policy as lcp
        if not lcp.can_like(text, media_present=lcp.bluesky_has_visual(post), sensitive=lcp.bluesky_sensitive(post))[0]:
            continue
        if len(text) < 25 or not _spanish(text) or sc.is_political(text) or sc.looks_activist(text):
            continue
<<<<<<< HEAD
        return {"url": f"https://bsky.app/profile/{handle}/post/{post['uri'].rsplit('/', 1)[-1]}", "text": text}
=======
        return {"url": f"https://bsky.app/profile/{handle}/post/{post['uri'].rsplit('/', 1)[-1]}",
                "post_uri": post["uri"], "text": text,
                "post_created_at": record.get("createdAt") or ""}
>>>>>>> origin/research/public-reuse-parent
    return None


def _latest_post_mastodon(handle, account_id):
    import mastodon_interact as m
    try:
        account_id = account_id or m._resolve_account_id(handle.lstrip("@"))
        rows = m._get(f"accounts/{account_id}/statuses", {"limit": 8, "exclude_replies": "true", "exclude_reblogs": "true"})
    except Exception:
        return None
    for status in rows or []:
        if not isinstance(status, dict):
            continue
        text = _clean(m._plain_text(status.get("content")))
        import like_context_policy as lcp
        if not lcp.can_like(text, media_present=lcp.mastodon_has_visual(status), sensitive=(status.get("sensitive") is True or bool(status.get("spoiler_text"))))[0]:
            continue
        if status.get("favourited") or len(text) < 25 or not _spanish(text) or sc.is_political(text) or sc.looks_activist(text):
            continue
<<<<<<< HEAD
        return {"url": status.get("url"), "status_id": str(status["id"]), "text": text}
=======
        return {"url": status.get("url"), "status_id": str(status["id"]), "text": text,
                "post_created_at": status.get("created_at") or ""}
>>>>>>> origin/research/public-reuse-parent
    return None


LATEST = {"bluesky": lambda h, e: _latest_post_bluesky(h), "mastodon": lambda h, e: _latest_post_mastodon(h, (e or {}).get("account_id"))}


def unanswered_comments(network, events):
    """Comentarios recibidos: responder solo a preguntas con hilo verificable."""
    import conversation_followups as cf
    import conversation_turn_policy as ctp
    try:
        rows = [r for r in cf.ALL_SOURCES[network][0]() if not r["answered"]]
    except Exception as exc:
        print(f"[loyalty] {network}: no se pudo leer los comentarios sin contestar ({type(exc).__name__}: {str(exc)[:80]})")
        return []
    sent = cf.replies_sent(network)
    items, seen = [], set()
    for row in cf._recent_first(rows):
        key = rp.norm(row["handle"])
        text = _clean(row["text"])
        if key in seen or sc.is_feed_bridge(row["handle"]) or len(text) < 8 or sc.is_conversation_closer(text) or sc.is_political(text) or not _spanish(text) and "?" not in text:
            continue
        if sent.get(key, 0) >= cf.MAX_REPLIES_PER_ACCOUNT or not rp.comment_allowed(network, row["handle"], _registro(network)):
            continue
        # Solo cierres inequívocos se descartan automáticamente. Opiniones
        # sustantivas como «Me encantó tu libro» deben llegar a GPT.
        if ctp.is_closed_turn(text):
            continue
        turns = ctp.fetch_verified_thread(network, row)
        if turns and turns[-1]["post_id"] != str(row.get("ref")):
            turns = []  # la respuesta API no corresponde al destino solicitado
        if turns:
            decision, _ = ctp.decide_next_turn(
                text, replying_to_us=True,
                earlier_own_turns=sum(t["role"] == "ours" for t in turns[:-1]),
                thread_complete=True,
            )
            if decision == "NO_REPLY":
                continue
            context = ctp.render_thread(turns)
            quality = "complete"
        else:
            # Si la red no expone el hilo, aportar lo que SÍ se conoce,
            # indicando que la conversación podría tener turnos ausentes.
            mine = _clean(row.get("mine") or "")
            context = (
                "CONTEXTO PARCIAL (no se pudieron leer todos los padres). "
                "Última intervención nuestra conocida: " + (mine or "[no disponible]") +
                ". La otra persona acaba de decir: " + text +
                ". No inventes turnos anteriores y devuelve null si no procede responder."
            )
            quality = "partial"
        seen.add(key)
        items.append(row | {"text": text, "thread_turns": turns, "conversation_context": context, "context_quality": quality})
    return items


def build_plan(network, events, *, write=True, replies=True, log=print):
    import conversation_turn_policy as ctp
    loyal = loyal_accounts(network)
    followed, _ = _done(network)
    by_handle = {}
    for event in events:
        by_handle.setdefault(rp.norm(event["handle"]), event)
    plan, likes, follows, firsts = [], 0, 0, 0
    # comentarios recibidos -> respuesta escrita por ChatGPT (comment-for-comment)
    reply_items = []
    if replies:
        for n, row in enumerate(unanswered_comments(network, events)[:MAX_REPLIES]):
            reply_items.append({"id": f"c{n + 1}", "network": network, "author": row["handle"], "text": row["text"], "reply_to_us": True,
<<<<<<< HEAD
                                "context": row.get("conversation_context") or "CONTEXTO PARCIAL. Evalúa si responder; puedes devolver null.", "row": row})
=======
                                "context": row.get("conversation_context") or "CONTEXTO PARCIAL. Evalúa si responder; puedes devolver null.",
                                "url": row.get("url"), "post_uri": row.get("ref") if network == "bluesky" else None,
                                "status_id": row.get("ref") if network == "mastodon" else None,
                                "post_created_at": row.get("post_created_at") or "", "row": row})
>>>>>>> origin/research/public-reuse-parent
    written = {}
    if reply_items:
        import reply_hold
        import reply_writer as rw
        if reply_hold.held():
            log("[loyalty] respuestas en revision: no se responde a comentarios")
        else:
            import reply_queue as rq
            written = rq.get_or_enqueue([{k: v for k, v in i.items() if k != "row"} for i in reply_items], network, wait_min=3)
    for item in reply_items:
        text = written.get(item["id"])
        if text:
            row = item["row"]
            entry = {"handle": row["handle"], "kind": "reply", "lane": "community", "url": row["url"], "text": text, "post_text": row["text"],
<<<<<<< HEAD
                     "motivo": "fidelizacion:contestar_a_su_comentario", "thread_turns": row.get("thread_turns", []), "context_quality": row.get("context_quality", "partial"), "reply_to_us": True}
            if network == "mastodon":
                entry = {"kind": "reply", "handle": row["handle"], "status_id": row["ref"], "text": text, "post_text": row["text"], "lane": "community",
                         "motivo": "fidelizacion:contestar_a_su_comentario", "thread_turns": row.get("thread_turns", []), "reply_to_us": True}
            plan.append(entry)
=======
                     "motivo": "fidelizacion:contestar_a_su_comentario", "thread_turns": row.get("thread_turns", []), "context_quality": row.get("context_quality", "partial"), "reply_to_us": True,
                     "post_created_at": row.get("post_created_at") or ""}
            if network == "mastodon":
                entry = {"kind": "reply", "handle": row["handle"], "status_id": row["ref"], "text": text, "post_text": row["text"], "lane": "community",
                         "motivo": "fidelizacion:contestar_a_su_comentario", "thread_turns": row.get("thread_turns", []), "reply_to_us": True,
                         "post_created_at": row.get("post_created_at") or ""}
            if network == "bluesky" and row.get("ref"):
                entry["post_uri"] = row["ref"]
            import reply_provenance as proof
            entry = proof.attach(entry, item, network)
            if entry:
                plan.append(entry)
>>>>>>> origin/research/public-reuse-parent
    answered = {rp.norm(i["author"]) for i in reply_items if written.get(i["id"])}
    # premio por cuenta: like en su ultimo post, follow de vuelta y, a quien solo nos dio like/repost, un comentario de primer paso
    first_items, latests = [], {}
    for handle, counts in sorted(loyal.items(), key=lambda kv: -sum(kv[1].values())):
        if sc.is_feed_bridge(handle) or handle in answered:
            continue
        event = by_handle.get(handle) or {}
        if handle not in followed and follows < MAX_FOLLOWS:
            plan.append({"handle": handle, "kind": "follow", "lane": "community", "motivo": "fidelizacion:follow_de_vuelta", **({"account_id": event["account_id"]} if event.get("account_id") else {})})
            follows += 1
        if likes < MAX_LIKES:
            try:
                latest = LATEST[network](handle, event)
            except Exception as exc:
                latest = None
                log(f"[loyalty] {handle}: sin ultimo post ({type(exc).__name__}: {str(exc)[:60]})")
            if latest:
                latests[handle] = (latest, counts)
                if network == "mastodon":
<<<<<<< HEAD
                    plan.append({"handle": handle, "kind": "favourite", "status_id": latest["status_id"], "lane": "community", "motivo": "fidelizacion:like_a_quien_nos_da"})
                else:
                    plan.append({"handle": handle, "kind": "like", "url": latest["url"], "lane": "community", "motivo": "fidelizacion:like_a_quien_nos_da"})
                likes += 1
                if (counts.get("like") or counts.get("repost")) and not counts.get("comment") and firsts + len(first_items) < MAX_FIRST_STEP \
                        and rp.outbound_comments(_registro(network), handle) == 0:
                    first_items.append({"id": f"f{len(first_items) + 1}", "network": network, "author": handle, "text": latest["text"], "context": "le gustó un post nuestro; le comentamos en su último post", "latest": latest})
=======
                    plan.append({"handle": handle, "kind": "favourite", "status_id": latest["status_id"], "lane": "community", "motivo": "fidelizacion:like_a_quien_nos_da", "post_created_at": latest.get("post_created_at") or ""})
                else:
                    plan.append({"handle": handle, "kind": "like", "url": latest["url"], "lane": "community", "motivo": "fidelizacion:like_a_quien_nos_da", "post_created_at": latest.get("post_created_at") or ""})
                likes += 1
                if (counts.get("like") or counts.get("repost")) and not counts.get("comment") and firsts + len(first_items) < MAX_FIRST_STEP \
                        and rp.outbound_comments(_registro(network), handle) == 0:
                    first_items.append({"id": f"f{len(first_items) + 1}", "network": network, "author": handle, "text": latest["text"], "context": "le gustó un post nuestro; le comentamos en su último post",
                                        "url": latest.get("url"), "post_uri": latest.get("post_uri"),
                                        "status_id": latest.get("status_id"), "latest": latest})
>>>>>>> origin/research/public-reuse-parent
    # reposts CURADOS (norma de David: max 3/dia y solo comunidad fiel con post de nicho): quien nos comenta o nos reposta y escribe sobre libros/escritura/fantasia
    import repost_policy
    import text_common as tc
    room = max(0, repost_policy.MAX_PER_DAY - repost_policy.done_today(_registro(network)))
    share_kind = "boost" if network == "mastodon" else "repost"
    for handle, (latest, counts) in latests.items():
        if room <= 0:
            break
        if (counts.get("comment") or counts.get("repost")) and len(latest["text"]) >= 60 and tc.niche_hits(latest["text"]) >= 1:
            key = latest.get("status_id") if network == "mastodon" else latest["url"]
            plan[:] = [p for p in plan if not (p["kind"] in ("like", "favourite") and (p.get("status_id") or p.get("url")) == key)]
<<<<<<< HEAD
            plan.append({"handle": handle, "kind": share_kind, "curated": True, "lane": "community", "motivo": "fidelizacion:repost_curado",
=======
            plan.append({"handle": handle, "kind": share_kind, "curated": True, "lane": "community", "motivo": "fidelizacion:repost_curado", "post_created_at": latest.get("post_created_at") or "",
>>>>>>> origin/research/public-reuse-parent
                         **({"status_id": latest["status_id"]} if network == "mastodon" else {"url": latest["url"]})})
            room -= 1
    if first_items and replies:
        import reply_hold
        import reply_writer as rw
        if not reply_hold.held():
            import reply_queue as rq
            texts = rq.get_or_enqueue([{k: v for k, v in i.items() if k != "latest"} for i in first_items], network, wait_min=3)
            for item in first_items:
                text = texts.get(item["id"])
                if not text:
                    continue
                latest = item["latest"]
<<<<<<< HEAD
                base = {"handle": item["author"], "kind": "reply", "lane": "community", "text": text, "post_text": latest["text"], "motivo": "fidelizacion:comentario_a_quien_nos_dio_like"}
                plan.append(base | ({"status_id": latest["status_id"]} if network == "mastodon" else {"url": latest["url"]}))
=======
                base = {"handle": item["author"], "kind": "reply", "lane": "community", "text": text, "post_text": latest["text"], "motivo": "fidelizacion:comentario_a_quien_nos_dio_like",
                        "post_created_at": latest.get("post_created_at") or ""}
                import reply_provenance as proof
                entry = proof.attach(base | ({"status_id": latest["status_id"]} if network == "mastodon"
                                             else {"url": latest["url"], "post_uri": latest.get("post_uri")}),
                                     item, network)
                if not entry:
                    continue
                plan.append(entry)
>>>>>>> origin/research/public-reuse-parent
                firsts += 1
                # un like y un comentario sobre el mismo post se pisan: el comentario sustituye al like
                key = latest.get("status_id") if network == "mastodon" else latest["url"]
                plan[:] = [p for p in plan if not (p["kind"] in ("like", "favourite") and (p.get("status_id") or p.get("url")) == key)]
    if write:
        path = os.path.join(_plan_dir(network), f"{network}_loyalty_plan.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=1)
    return plan


def report():
    """Por red: cuentas que han hecho algo por nosotros (14 dias) y cuantas han recibido premio (like/comentario/follow nuestros en el registro)."""
    lines = ["| Red | Cuentas que nos dan algo (14 d) | likes/reposts | comentarios | follows | premiadas con like | con comentario | seguidas |", "|---|---|---|---|---|---|---|---|"]
    for network in ("bluesky", "mastodon", "x", "threads", "facebook", "pinterest", "reddit", "tiktok"):
<<<<<<< HEAD
=======
        if network == "pinterest":
            # Sin cosecha individual verificada: 0 en CSV no acredita que
            # no recibimos likes, comentarios o follows en Pinterest.
            lines.append("| pinterest | ND | ND | ND | ND | ND | ND | ND |")
            continue
>>>>>>> origin/research/public-reuse-parent
        loyal = loyal_accounts(network)
        likes = sum(c.get("like", 0) + c.get("repost", 0) for c in loyal.values())
        comments = sum(c.get("comment", 0) for c in loyal.values())
        follows = sum(c.get("follow", 0) for c in loyal.values())
        done = {"like": set(), "reply": set(), "follow": set()}
        for row in rp._rows(_registro(network)):
            if row.get("resultado") not in rp.OK_RESULTS + ("saltado_ya_seguido", "saltado_ya_reaccionado"):
                continue
            kind = (row.get("tipo") or "").strip().casefold()
            who = rp.norm(row.get("cuenta"))
            if who in loyal:
                key = "like" if kind in ("like", "favourite", "react", "like_external") else "reply" if kind in rp.COMMENT_KINDS else "follow" if kind == "follow" else None
                if key:
                    done[key].add(who)
        lines.append(f"| {network} | {len(loyal)} | {likes} | {comments} | {follows} | {len(done['like'])} | {len(done['reply'])} | {len(done['follow'])} |")
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
<<<<<<< HEAD
=======
    if argv and argv[0] == "verified-threads":
        # Acción OPT-IN de solo lectura remota + escritura local opcional.
        # No produce planes, ni habilita premios o respuestas.
        import loyalty_events
        try:
            import threads_api
            token = threads_api._env().get("THREADS_ACCESS_TOKEN")
            if not token:
                print("[loyalty] falta permiso/token Threads; no se importan eventos")
                return 2
            me = threads_api.api_get("me", token, fields="username")
            if not isinstance(me, dict) or not me.get("username"):
                raise ValueError("Threads: cuenta autenticada no verificable")
            events = loyalty_events.read_threads_api(
                threads_api.api_get, token, me["username"])
            if "--record" in argv:
                added = loyalty_events.record(events)
                print(f"[loyalty] threads: {len(events)} replies con ID; {added} nuevas en registro local aislado")
            else:
                print(f"[loyalty] threads: {len(events)} replies con ID (vista previa, sin escrituras)")
            return 0
        except Exception as exc:
            print(f"[loyalty] lectura Threads no certificada: {type(exc).__name__}; sin premios")
            return 2
>>>>>>> origin/research/public-reuse-parent
    if argv and argv[0] == "report":
        print(report())
        return 0
    if not argv or argv[0] not in HARVEST:
        print(__doc__)
        return 0
    network = argv[0]
    try:
        events = HARVEST[network]()
        new = record(network, events)
        print(f"[loyalty] {network}: {len(events)} interacciones recibidas ({new} nuevas); {len(loyal_accounts(network))} cuentas fieles")
        plan = build_plan(network, events, replies="--no-replies" not in argv)
        kinds = {}
        for item in plan:
            kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
        print(f"[loyalty] {network}: plan de premio {kinds}")
    except Exception as exc:                      # nunca tumba la ronda
        print(f"[loyalty] {network}: error ({type(exc).__name__}: {str(exc)[:120]}); sin plan de fidelizacion esta ronda")
        path = os.path.join(_plan_dir(network), f"{network}_loyalty_plan.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump([], stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
