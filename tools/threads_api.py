"""API oficial de Threads: lectura de conversaciones y replies por API con guardias #73.

App `David Porto Escritor Tools` en modo desarrollo, token de larga duracion en `.env`
(THREADS_ACCESS_TOKEN). Meta no ofrece tokens que no caduquen (60 dias): se renuevan solos con la
tarea programada `RRSS_threads_token` (`refresh --if-due`). Permisos (David, 03/10): threads_basic,
threads_read_replies, threads_manage_replies, threads_content_publish y estadisticas.
Contestar por API solo es posible con IDs de la propia API (respuestas a nuestros hilos): los
permalinks del navegador NO se pueden convertir en ID de API (comprobado 03/10) y
`threads_keyword_search` sin la revision de Meta solo busca posts propios, asi que el descubrimiento
y las respuestas a posts ajenos siguen por navegador.

    python tools/threads_api.py me            # comprueba el token y los dias que le quedan
    python tools/threads_api.py followups     # respuestas a nuestros hilos que no hemos contestado
    python tools/threads_api.py refresh [--if-due]   # renueva el token (con --if-due solo si quedan <= 30 dias)
    python tools/threads_api.py build decisions.json plan.json   # decisions: {"actions":[{"id","text"}]}

Misma politica que Bluesky/Mastodon (03/10): una conversacion se contesta una vez; despues solo si
nos preguntan algo, asi que el listado solo incluye respuestas con pregunta.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import meta_common as mc
ROOT = os.path.join(os.path.dirname(__file__), "..")
BASE = "https://graph.threads.net/v1.0/"
TOKEN_DAYS = 60
REFRESH_WHEN_LEFT = 30


def _env():
    return mc.read_env(ROOT)


def api_get(path, token, **params):
    return mc.graph_get(BASE, path, token, **params)


def paginated(path, token, *, fields, limit=50, max_pages=5):
    """Itera paginas de Graph Threads sin abrir URLs devueltas por el servidor.

    'paging.next' solo indica que hay otra pagina: se pasa su cursor 'after' al
    endpoint original. Ante truncado/error se aborta antes de producir un plan parcial.
    """
    if (type(limit) is not int or type(max_pages) is not int
            or not 1 <= limit <= 100 or max_pages < 1):
        raise ValueError("limite de paginacion invalido")
    items, seen_cursors, seen_ids = [], set(), set()
    cursor = None
    for _ in range(max_pages):
        params = {"fields": fields, "limit": limit}
        if cursor is not None:
            params["after"] = cursor
        response = api_get(path, token, **params)
        if not isinstance(response, dict) or not isinstance(response.get("data"), list):
            raise RuntimeError("respuesta paginada Threads sin data valida")
        for item in response["data"]:
            if not isinstance(item, dict) or not item.get("id"):
                raise RuntimeError("elemento Threads sin id")
            if str(item["id"]) not in seen_ids:
                items.append(item)
                seen_ids.add(str(item["id"]))
        paging = response.get("paging") or {}
        if not isinstance(paging, dict):
            raise RuntimeError("paging Threads invalido")
        cursors = paging.get("cursors") or {}
        if not isinstance(cursors, dict):
            raise RuntimeError("cursores Threads invalidos")
        next_cursor = cursors.get("after")
        # Meta tambien documenta respuestas con solo paging.cursors, sin
        # paging.next. Una pagina llena puede ocultar mas elementos.
        has_next = bool(paging.get("next"))
        full_page = len(response["data"]) >= limit
        if not has_next and not full_page:
            return items
        if not isinstance(next_cursor, str) or not next_cursor:
            raise RuntimeError("cursor Threads ausente: paginacion potencialmente incompleta")
        if next_cursor in seen_cursors:
            raise RuntimeError("cursor Threads repetido")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    raise RuntimeError("Threads: paginacion incompleta, revisar limite antes de generar acciones")


def token_days_left(env, today=None):
    today = today or datetime.date.today()
    try:
        created = datetime.date.fromisoformat(env.get("THREADS_TOKEN_CREATED", ""))
    except ValueError:
        return None
    return TOKEN_DAYS - (today - created).days


def unanswered(replies, my_username, answered_ids=()):
    """Respuestas ajenas con pregunta y sin respuesta nuestra (logica comun en meta_common)."""
    return mc.unanswered(replies, [my_username], answered_ids)


def _write_env(updates):
    mc.write_env(updates, root=ROOT)


def refresh(env, today=None, if_due=False):
    """Renueva el token (valido 60 dias, renovable pasadas 24 h). Devuelve (renovado, mensaje)."""
    today = today or datetime.date.today()
    left = token_days_left(env, today)
    if if_due and left is not None and left > REFRESH_WHEN_LEFT:
        return False, f"no toca (quedan {left} dias)"
    data = api_get("refresh_access_token", env["THREADS_ACCESS_TOKEN"], grant_type="th_refresh_token")
    _write_env({"THREADS_ACCESS_TOKEN": data["access_token"], "THREADS_TOKEN_CREATED": today.isoformat()})
    return True, f"renovado (expira en {data.get('expires_in')} s)"


REPLY_MAX = 500


def api_post(path, token, **params):
    return mc.graph_post(BASE, path, token, **params)


class ReplyNotCreated(RuntimeError):
    """Fallo ANTES de publicar: no hay respuesta en Threads, se puede reintentar o usar el navegador."""


def check_reply_text(text):
    if not isinstance(text, str):
        raise ValueError("respuesta debe ser texto")
    text = text.strip()
    if not text:
        raise ValueError("respuesta vacia")
    if len(text) > REPLY_MAX:
        raise ValueError(f"{len(text)} caracteres (max {REPLY_MAX})")
    return text


def _verify_reply_destination(token, reply_to_id, text, proof_action, proof_path=None):
    """Comprueba firma EXISTENTE #79 y destino real antes de publicar.

    El ID numerico de Threads no esta ligado por la firma #79 al permalink:
    consultar la API y cotejar ID, permalink y texto. Sin lectura fiable, denegar.
    No crea un segundo registro, hash o mecanismo de autorizacion.
    """
    import reply_provenance as proof
    if (not isinstance(proof_action, dict)
            or proof_action.get("kind") != "reply"
            or str(proof_action.get("reply_to_id") or "") != str(reply_to_id)
            or proof_action.get("text") != text
            or not proof.verify(proof_action, "threads", path=proof_path)):
        raise PermissionError("Threads API: respuesta sin certificado contextual valido")
    source_text = proof.compact(proof_action.get("post_text"))
    if not source_text:
        raise PermissionError("Threads API: falta texto certificado del destinatario")
    try:
        target = api_get(str(reply_to_id), token, fields="id,permalink,text")
    except Exception as exc:
        raise PermissionError("Threads API: no se pudo verificar el post de destino") from exc
    if (not isinstance(target, dict)
            or str(target.get("id")) != str(reply_to_id)
            or not proof.canonical("threads", {"url": target.get("permalink")})
            or proof.canonical("threads", proof_action)
               != proof.canonical("threads", {"url": target.get("permalink")})
            or source_text != proof.compact(target.get("text"))):
        raise PermissionError("Threads API: ID, permalink o contexto no coinciden")


def publish_reply(token, user_id, reply_to_id, text, *, proof_action=None, proof_path=None):
    """Publica solo una respuesta #79 verificada contra el post real de Threads.

    Tras crear contenedor, un fallo en el segundo POST es incierto: no reintentar
    automaticamente. El fallback por UI debe hacerse tras confirmar estado.
    """
    text = check_reply_text(text)
    _verify_reply_destination(token, reply_to_id, text, proof_action, proof_path)
    # La ruta API directa debe respetar la misma decisión conversacional que
    # threads_execute.run_plan: prueba de origen no autoriza sobrecontestar.
    import conversation_turn_policy as ctp
    allowed, reason = ctp.check_execution("threads", proof_action)
    if not allowed:
        raise PermissionError(f"Threads API: respuesta descartada por {reason}")
    # El bloqueo no puede vivir solo en el ejecutor: este método también
    # recibe llamadas directas de API. Reutiliza el ledger COMÚN, de manera
    # atómica, antes de cruzar el primer POST (sin añadir un segundo estado).
    import action_ledger as al
    import exec_common as ec
    pool_path = os.environ.get("RRSS_THREADS_POOL_PATH")
    fallback = (os.path.join(os.path.dirname(os.path.abspath(pool_path)),
                             "action_ledger.sqlite")
                if pool_path else os.path.join(
                    ROOT, "SISTEMA_DIARIO_THREADS", "cache",
                    "action_ledger.sqlite"))
    ledger_path = os.environ.get("RRSS_THREADS_ACTION_LEDGER_PATH") or fallback
    ledger = al.ActionLedger(ledger_path, stale_after=365 * 86400)
    target_key = "threads:reply_to:" + str(reply_to_id)
    verdict = ledger.reserve("reply", target_key)
    if verdict != "ok":
        raise PermissionError("Threads API: respuesta ya reservada o enviada; no repetir")
    try:
        container = api_post(f"{user_id}/threads", token, media_type="TEXT",
                             text=text, reply_to_id=reply_to_id)
    except Exception as exc:
        # Sin segundo POST no se ha publicado; una futura relectura puede
        # permitir un nuevo contenedor, nunca dar por confirmado el primero.
        ledger.settle("reply", target_key, al.FAILED, "sin_contenedor_publicado")
        raise ReplyNotCreated("Threads: no se creó contenedor") from exc
    container_id = container.get("id") if isinstance(container, dict) else None
    if not isinstance(container_id, str) or not container_id.strip():
        ledger.settle("reply", target_key, al.FAILED, "contenedor_sin_id")
        raise ReplyNotCreated("Threads: contenedor sin ID válido; no se ha publicado")
    # El segundo POST puede haber publicado aunque no llegue ACK.
    try:
        published = api_post(f"{user_id}/threads_publish", token,
                             creation_id=container_id)
        published_id = published.get("id") if isinstance(published, dict) else None
        if not isinstance(published_id, str) or not published_id.strip():
            raise ValueError("ACK de Threads sin ID válido")
    except Exception as exc:
        ledger.settle("reply", target_key, al.UNCERTAIN, "pendiente_verificacion")
        raise ec.WriteOutcomeUnknown(
            "Threads: publicación iniciada sin ACK verificable") from exc
    ledger.settle("reply", target_key, al.CONFIRMED, "confirmado")
    return published_id


def build_plan(items, decisions):
    by_id = {item["id"]: item for item in items}
    plan = []
    for index, decision in enumerate(decisions.get("actions", [])):
        item = by_id.get(decision.get("id"))
        if not item:
            raise ValueError(f"decision {index}: id desconocido {decision.get('id')!r}")
        text = check_reply_text(decision.get("text"))
        if "?" in text and not decision.get("allow_question"):
            raise ValueError(f"decision {index}: un seguimiento no termina con pregunta (se alargaria el hilo)")
        # El constructor de followups debe transmitir la MISMA prueba #79
        # creada por el escritor, no generar prueba por el hecho de estar en CLI.
        action = {"handle": item["username"], "kind": "reply", "text": text,
                  "reply_to_id": item["id"],
                  "url": item.get("permalink") or item.get("url"),
                  "post_text": item.get("text", ""),
                  "target_created_at": item.get("timestamp"),
                  "thread_turns": item.get("thread_turns", []),
                  "reply_to_us": True, "motivo": "followup API Threads"}
        import reply_provenance as proof
        carried = proof.carry_decision_proof(
            action, decision, "threads", scanned_text=item.get("text", ""))
        if carried is not None:
            plan.append(carried)
    return plan


def _reply_parent_id(item):
    """Read the Graph parent reference; a missing one cannot prove ancestry."""
    parent = item.get("replied_to")
    if not isinstance(parent, dict):
        return None
    value = parent.get("id")
    return str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip() else None


def _thread_path(nodes, root_id, reply_id, owned_ids, *, max_turns=20):
    """Reconstruct an exact root-to-reply path without inventing missing turns."""
    path, seen, current_id = [], set(), str(reply_id)
    while current_id not in seen and len(path) < max_turns:
        seen.add(current_id)
        node = nodes.get(current_id)
        if not isinstance(node, dict) or not isinstance(node.get("text"), str) or not node["text"].strip():
            return []
        path.append({
            "role": "ours" if current_id in owned_ids else "theirs",
            "text": node["text"], "post_id": current_id,
        })
        if current_id == root_id:
            return list(reversed(path))
        current_id = _reply_parent_id(node)
        if not current_id:
            return []
    return []


def followups(token, my_username, limit_posts=25):
    """Read complete root conversations and select fresh questions addressed to us.

    Only replies to an owned post/reply qualify. Never interpret a missing
    ancestor or incomplete pagination as proof that a question was unanswered.
    """
    posts = paginated("me/threads", token, fields="id,text,timestamp,is_reply,has_replies", limit=limit_posts)
    own_replies = paginated("me/replies", token, fields="id,replied_to", limit=100)
    answered = set()
    own_ids = set()
    for own in own_replies:
        parent = _reply_parent_id(own)
        if parent is None:
            raise RuntimeError("Threads: una respuesta propia carece de replied_to; no se puede reconciliar")
        own_ids.add(str(own["id"]))
        answered.add(parent)

    mine = str(my_username).casefold().lstrip("@")
    pending, seen = [], set()
    for post in posts:
        if post.get("is_reply") or not post.get("has_replies"):
            continue
        root_id = str(post["id"])
        conversation = paginated(
            f"{root_id}/conversation", token,
            fields="id,text,username,timestamp,permalink,replied_to,is_reply_owned_by_me,root_post",
            limit=100,
        )
        nodes = {root_id: post}
        for reply in conversation:
            rid = str(reply["id"])
            if rid != root_id:
                nodes[rid] = reply
        visible_owned_replies = {
            str(reply["id"]) for reply in conversation
            if str(reply["id"]) != root_id and (
                reply.get("is_reply_owned_by_me") is True
                or str(reply.get("username") or "").casefold().lstrip("@") == mine
            )
        }
        # An own reply may be visible in /conversation before /me/replies:
        # either source can prove that its immediate parent was answered.
        for reply in conversation:
            if str(reply["id"]) in visible_owned_replies:
                parent_id = _reply_parent_id(reply)
                if parent_id is None:
                    raise RuntimeError("Threads: respuesta propia en conversacion sin replied_to")
                answered.add(parent_id)
        owned = {root_id} | own_ids | visible_owned_replies
        for reply in unanswered(conversation, my_username, answered):
            rid = str(reply["id"])
            if (rid == root_id or rid in seen or rid in own_ids
                    or reply.get("is_reply_owned_by_me") is True):
                continue
            # Conversations include user-to-user debates: only reply when
            # the immediate recipient is one of our own posts or replies.
            parent_id = _reply_parent_id(reply)
            if parent_id is None:
                raise RuntimeError("Threads: respuesta recibida sin replied_to; no se puede validar destino")
            if parent_id not in owned:
                continue
            turns = _thread_path(nodes, root_id, rid, owned)
            if not turns:
                raise RuntimeError("Threads: cadena de respuestas incompleta; no ofrecer un contexto inventado")
            seen.add(rid)
            candidate = dict(reply)
            candidate["id"] = rid
            candidate["a_nuestro"] = nodes[parent_id]["text"][:100]
            candidate["thread_turns"] = turns
            candidate["reply_to_us"] = True
            pending.append(candidate)
    return sorted(pending, key=lambda x: x.get("timestamp") or "", reverse=True)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    env = _env()
    token = env.get("THREADS_ACCESS_TOKEN")
    if not token or not argv:
        print(__doc__)
        return 2
    if argv[0] == "me":
        me = api_get("me", token, fields="id,username")
        print(f"token valido para @{me['username']}; dias restantes: {token_days_left(env)}")
        return 0
    if argv[0] == "refresh":
        done, message = refresh(env, if_due="--if-due" in argv)
        print(message)
        return 0
    if argv[0] == "build" and len(argv) >= 3:
        with open(os.path.join(ROOT, "threads_api_followups.json"), encoding="utf-8") as stream:
            items = json.load(stream)
        with open(argv[1], encoding="utf-8") as stream:
            decisions = json.load(stream)
        plan = build_plan(items, decisions)
        with open(argv[2], "w", encoding="utf-8") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=1)
        print(f"{argv[2]}: {len(plan)} respuestas (ejecutar con tools/threads_execute.py)")
        return 0
    if argv[0] == "followups":
        me = api_get("me", token, fields="username")
        pending = followups(token, me["username"])
        with open(os.path.join(ROOT, "threads_api_followups.json"), "w", encoding="utf-8") as stream:
            json.dump(pending, stream, ensure_ascii=False, indent=1)
        print(f"{len(pending)} respuestas con pregunta sin contestar")
        for item in pending:
            print(f"@{item['username']} ({item['timestamp'][:10]}): {item['text'][:200]}\n    a: {item['a_nuestro']}\n    {item.get('permalink','')}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
