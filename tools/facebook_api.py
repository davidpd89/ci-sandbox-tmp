"""API oficial de Facebook Pages (03/10/2026) para la Pagina de autor. Solo lectura por defecto.

App de Meta `Autora Demo Escritor Redes` (modo desarrollo; David es administrador de la app y de la
Pagina, asi que no hace falta App Review). El token de PAGINA obtenido de un token de usuario de larga
duracion NO caduca: no hay que renovarlo. Variables en `.env`: FB_PAGE_ID, FB_PAGE_TOKEN.

    python tools/facebook_api.py me                 # comprueba el token y la Pagina
    python tools/facebook_api.py comments           # comentarios con pregunta sin contestar en los ultimos posts
    python tools/facebook_api.py reply ID "texto"   # contesta a un comentario (una vez, sin devolver pregunta)
    python tools/facebook_api.py likes [--dry]      # da like como Pagina a los comentarios ajenos de nuestros posts (04/10)
    python tools/facebook_api.py publish "texto" --approved   # publica en la Pagina SOLO con --approved

Publicar contenido propio exige aprobacion explicita de David (AGENTS.md): sin `--approved` se niega.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import meta_common as mc

BASE = "https://graph.facebook.com/v26.0/"
COMMENT_MAX = 8000


class FacebookPaginationError(RuntimeError):
    """Lectura incompleta: no convertirla en sugerencias de respuesta."""


def _paged_rows(token, path, *, max_pages=10, budget=None, **params):
    """Recorre cursores Graph sin seguir URLs `paging.next` con tokens incluidos.

    Un error o paginacion incompleta aborta la lectura completa; no se devuelven
    pendientes parciales. Limite finito para evitar loops y consumo inesperado.
    """
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        raise ValueError("max_pages debe ser positivo")
    seen, after = set(), None
    for _ in range(max_pages):
        if budget is not None:
            if budget[0] <= 0:
                raise FacebookPaginationError("limite global de lecturas Graph agotado")
            budget[0] -= 1
        query = dict(params)
        if after is not None:
            query["after"] = after
        response = mc.graph_get(BASE, path, token, **query)
        if not isinstance(response, dict) or "error" in response or not isinstance(response.get("data"), list):
            raise FacebookPaginationError("Graph devolvio una pagina invalida o un error")
        for row in response["data"]:
            if not isinstance(row, dict):
                raise FacebookPaginationError("Graph devolvio un elemento invalido")
            yield row
        paging = response.get("paging") or {}
        if not isinstance(paging, dict):
            raise FacebookPaginationError("Graph devolvio paginacion invalida")
        if not paging.get("next"):
            return
        cursors = paging.get("cursors") or {}
        after = cursors.get("after") if isinstance(cursors, dict) else None
        if not isinstance(after, str) or not after or len(after) > 1024:
            raise FacebookPaginationError("Graph indica otra pagina sin cursor after valido")
        if after in seen:
            raise FacebookPaginationError("Graph repitio un cursor de paginacion")
        seen.add(after)
    raise FacebookPaginationError("Graph excedio el limite de paginas: lectura incompleta")


def comments_pending(token, page_id, posts_limit=10):
    """Preguntas externas realmente sin respuesta; fallo cerrado si Graph no permite verificar."""
    posts = mc.graph_get(BASE, f"{page_id}/posts", token, fields="id,message,created_time", limit=posts_limit)
    if not isinstance(posts, dict) or "error" in posts or not isinstance(posts.get("data"), list):
        raise FacebookPaginationError("Graph devolvio posts invalidos")
    pending, seen_ids = [], set()
    budget = [99]  # una lectura de posts + hasta 99 lecturas de comentarios/respuestas
    for post in posts["data"]:
        for comment in _paged_rows(token, f"{post['id']}/comments",
                                   fields="id,message,from,created_time,comment_count",
                                   filter="toplevel", limit=50, budget=budget):
            cid = comment.get("id")
            author = comment.get("from") or {}
            if not cid or cid in seen_ids or not isinstance(author, dict) or not author.get("id"):
                continue
            seen_ids.add(cid)
            if author.get("id") == page_id or "?" not in (comment.get("message") or ""):
                continue
            # Si Graph omite comment_count, tampoco se asume que no hay respuestas.
            if comment.get("comment_count") != 0:
                answered = False
                for reply in _paged_rows(token, f"{cid}/comments", fields="id,from", limit=50, budget=budget):
                    reply_author = reply.get("from")
                    if not isinstance(reply_author, dict) or not reply_author.get("id"):
                        raise FacebookPaginationError("Graph omitio la identidad de una respuesta")
                    if reply_author["id"] == page_id:
                        answered = True
                if answered:
                    continue
            pending.append({"id": cid, "text": comment.get("message", ""),
                            "username": author.get("name", ""),
                            "timestamp": comment.get("created_time", ""),
                            "post": (post.get("message") or "")[:80]})
    return mc.unanswered(pending, [], ())

def comments_to_like(token, page_id, posts_limit=10):
    """Comentarios ajenos (de otras personas) en nuestros posts que la Pagina aun no ha marcado con me gusta."""
    posts = mc.graph_get(BASE, f"{page_id}/posts", token, fields="id", limit=posts_limit)
    out = []
    for post in posts.get("data", []):
        data = mc.graph_get(BASE, f"{post['id']}/comments", token,
                            fields="id,message,from,user_likes,can_like", filter="stream", limit=100)
        for comment in data.get("data", []):
            author = (comment.get("from") or {}).get("id")
            if author == page_id or comment.get("user_likes") or comment.get("can_like") is False:
                continue
            out.append(comment["id"])
    return out


def like_comments(token, page_id, dry=False, posts_limit=10):
    """Like como Pagina a cada comentario recibido: gesto barato y gratuito de la API oficial (mismo papel que
    `conversation_followups --like` en Bluesky/Mastodon). Devuelve (dados, fallidos)."""
    done = failed = 0
    for comment_id in comments_to_like(token, page_id, posts_limit):
        if dry:
            done += 1
            continue
        try:
            mc.graph_post(BASE, f"{comment_id}/likes", token)
            done += 1
        except RuntimeError as exc:
            failed += 1
            print(f"  fallo like {comment_id}: {exc}")
    return done, failed


def reply_comment(token, comment_id, text, allow_question=False):
    text = mc.reject_returned_question(mc.check_text(text, COMMENT_MAX), allow_question)
    return mc.graph_post(BASE, f"{comment_id}/comments", token, message=text)["id"]


def publish(token, page_id, text, approved=False):
    if not approved:
        raise PermissionError("publicar en la Pagina exige aprobacion explicita de David (--approved)")
    return mc.graph_post(BASE, f"{page_id}/feed", token, message=mc.check_text(text, 63000))["id"]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    env = mc.read_env()
    token, page = env.get("FB_PAGE_TOKEN"), env.get("FB_PAGE_ID")
    if not (token and page) or not argv:
        print(__doc__)
        return 2
    if argv[0] == "me":
        info = mc.graph_get(BASE, page, token, fields="name,fan_count,followers_count")
        print(f"Pagina {info.get('name')}: {info.get('followers_count', info.get('fan_count'))} seguidores")
        return 0
    if argv[0] == "comments":
        pending = comments_pending(token, page)
        print(f"{len(pending)} comentarios con pregunta sin contestar")
        for item in pending:
            print(f"{item['id']} {item['username']} ({item['timestamp'][:10]}): {item['text'][:200]}")
            print(f"    en: {item['post']}")
        return 0
    if argv[0] == "likes":
        done, failed = like_comments(token, page, dry="--dry" in argv)
        print(f"likes a comentarios recibidos: {done}" + (" (dry)" if "--dry" in argv else "") + f", fallidos: {failed}")
        return 1 if failed and not done else 0
    if argv[0] == "reply" and len(argv) >= 3:
        print("respondido:", reply_comment(token, argv[1], argv[2]))
        return 0
    if argv[0] == "publish" and len(argv) >= 2:
        print("publicado:", publish(token, page, argv[1], approved="--approved" in argv))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
