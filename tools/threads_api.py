"""API oficial de Threads (03/10/2026), SOLO LECTURA: respuestas recibidas sin contestar.

App `Autora Demo Escritor Tools` en modo desarrollo, token de larga duracion en `.env`
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
    """Fallo antes de crear un contenedor, sin llamada de publicacion."""


class ReplyPublishUncertain(RuntimeError):
    """Hubo intento de publicar; no se sabe si Threads acepto la respuesta."""


def check_reply_text(text):
    text = (text or "").strip()
    if not text:
        raise ValueError("respuesta vacia")
    if len(text) > REPLY_MAX:
        raise ValueError(f"{len(text)} caracteres (max {REPLY_MAX})")
    return text


def publish_reply(token, user_id, reply_to_id, text):
    """Crea un contenedor sin autopublicarlo; el segundo POST puede quedar incierto.

    Esta variante del mirror no incorpora los certificados y el ledger de la
    rama privada operativa. No sustituir alli el publicador protegido.
    """
    text = check_reply_text(text)
    try:
        container = api_post(
            f"{user_id}/threads", token, media_type="TEXT", text=text,
            reply_to_id=reply_to_id, auto_publish_text="false",
        )
    except Exception as exc:
        raise ReplyNotCreated("Threads: no se creo contenedor (autopublicacion desactivada)") from exc
    if (not isinstance(container, dict) or not isinstance(container.get("id"), str)
            or not container["id"].strip()):
        raise ReplyNotCreated("Threads no devolvio id de contenedor valido")
    try:
        published = api_post(f"{user_id}/threads_publish", token, creation_id=container["id"])
    except Exception as exc:
        raise ReplyPublishUncertain("publicacion sin confirmacion; reconciliar antes de reintentar") from exc
    if (not isinstance(published, dict) or not isinstance(published.get("id"), str)
            or not published["id"].strip()):
        raise ReplyPublishUncertain("Threads acepto la peticion sin id confirmado; reconciliar")
    return published["id"]


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
        plan.append({"handle": item["username"], "kind": "reply", "text": text, "reply_to_id": item["id"],
                     "post_text": item.get("text", ""), "motivo": "followup API Threads"})
    return plan


def followups(token, my_username, limit_posts=25):
    """Reconciliacion solo lectura: nunca confundir primera pagina con historial completo."""
    posts = paginated("me/threads", token, fields="id,text,timestamp,is_reply,has_replies", limit=limit_posts)
    own_replies = paginated("me/replies", token, fields="id,replied_to", limit=100)
    answered = {
        str(parent["id"]) for item in own_replies
        for parent in [item.get("replied_to")]
        if isinstance(parent, dict) and parent.get("id")
    }
    pending, seen = [], set()
    for post in posts:
        if post.get("is_reply") or not post.get("has_replies"):
            continue
        replies = paginated(
            f"{post['id']}/replies", token,
            fields="id,text,username,timestamp,permalink,replied_to", limit=100
        )
        for reply in unanswered(replies, my_username, answered):
            if reply["id"] in seen:
                continue
            seen.add(reply["id"])
            reply["a_nuestro"] = (post.get("text") or "")[:100]
            pending.append(reply)
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
