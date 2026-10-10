"""API oficial de Instagram (Instagram Login, 03/10/2026) para @autorademodiaz.

Instagram sigue siendo SOLO PUBLICACION (David, 03/10): esta herramienta nunca interactua con cuentas
ajenas (la API tampoco lo permite). Sirve para (1) contestar comentarios de nuestros propios posts
(una vez, solo si preguntan) y (2) publicar piezas ya aprobadas por David. Variables en `.env`:
IG_USER_ID, IG_ACCESS_TOKEN, IG_TOKEN_CREATED (token de larga duracion de 60 dias; se renueva con
`refresh --if-due`, tarea programada `RRSS_meta_tokens`).

    python tools/instagram_api.py me
    python tools/instagram_api.py comments            # comentarios con pregunta sin contestar
    python tools/instagram_api.py reply ID "texto"
    python tools/instagram_api.py publish IMAGE_URL "caption" --approved   # imagen en URL publica
    python tools/instagram_api.py refresh [--if-due]
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import meta_common as mc

BASE = "https://graph.instagram.com/v26.0/"
CAPTION_MAX = 2200
COMMENT_MAX = 2200
TOKEN_DAYS, REFRESH_WHEN_LEFT = 60, 30


def token_days_left(env, today=None):
    today = today or datetime.date.today()
    try:
        return TOKEN_DAYS - (today - datetime.date.fromisoformat(env.get("IG_TOKEN_CREATED", ""))).days
    except ValueError:
        return None


def refresh(env, today=None, if_due=False):
    today = today or datetime.date.today()
    left = token_days_left(env, today)
    if if_due and left is not None and left > REFRESH_WHEN_LEFT:
        return False, f"no toca (quedan {left} dias)"
    data = mc.graph_get("https://graph.instagram.com/", "refresh_access_token", env["IG_ACCESS_TOKEN"],
                        grant_type="ig_refresh_token")
    mc.write_env({"IG_ACCESS_TOKEN": data["access_token"], "IG_TOKEN_CREATED": today.isoformat()})
    return True, f"renovado (expira en {data.get('expires_in')} s)"


def comments_pending(token, user_id, me_username, media_limit=10):
    media = mc.graph_get(BASE, f"{user_id}/media", token, fields="id,caption,timestamp", limit=media_limit)
    pending = []
    for item in media.get("data", []):
        data = mc.graph_get(BASE, f"{item['id']}/comments", token,
                            fields="id,text,username,timestamp,replies{username}")
        answered = {c["id"] for c in data.get("data", [])
                    if any((r.get("username") or "").casefold() == me_username.casefold()
                           for r in (c.get("replies") or {}).get("data", []))}
        rows = [dict(c, post=(item.get("caption") or "")[:80]) for c in data.get("data", [])]
        pending += mc.unanswered(rows, [me_username], answered)
    return pending


def reply_comment(token, comment_id, text, allow_question=False):
    text = mc.reject_returned_question(mc.check_text(text, COMMENT_MAX), allow_question)
    return mc.graph_post(BASE, f"{comment_id}/replies", token, message=text)["id"]


def publish_image(token, user_id, image_url, caption, approved=False):
    if not approved:
        raise PermissionError("publicar en Instagram exige aprobacion explicita de David (--approved)")
    container = mc.graph_post(BASE, f"{user_id}/media", token, image_url=image_url,
                              caption=mc.check_text(caption, CAPTION_MAX))
    return mc.graph_post(BASE, f"{user_id}/media_publish", token, creation_id=container["id"])["id"]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    env = mc.read_env()
    token, uid = env.get("IG_ACCESS_TOKEN"), env.get("IG_USER_ID")
    if not (token and uid) or not argv:
        print(__doc__)
        return 2
    if argv[0] == "me":
        info = mc.graph_get(BASE, "me", token, fields="username,followers_count,media_count")
        print(f"@{info.get('username')}: {info.get('followers_count')} seguidores, {info.get('media_count')} posts; "
              f"token: {token_days_left(env)} dias")
        return 0
    if argv[0] == "refresh":
        print(refresh(env, if_due="--if-due" in argv)[1])
        return 0
    if argv[0] == "comments":
        me = mc.graph_get(BASE, "me", token, fields="username")["username"]
        pending = comments_pending(token, uid, me)
        print(f"{len(pending)} comentarios con pregunta sin contestar")
        for item in pending:
            print(f"{item['id']} @{item['username']}: {item['text'][:200]}")
            print(f"    en: {item['post']}")
        return 0
    if argv[0] == "reply" and len(argv) >= 3:
        print("respondido:", reply_comment(token, argv[1], argv[2]))
        return 0
    if argv[0] == "publish" and len(argv) >= 3:
        print("publicado:", publish_image(token, uid, argv[1], argv[2], approved="--approved" in argv))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
