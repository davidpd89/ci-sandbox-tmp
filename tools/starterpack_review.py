"""Revision periodica (solo lectura) de los miembros del starter pack de Bluesky (03/10).

Un starter pack estatico se pudre: cuentas que dejan de publicar, borradas o que pasan a
privadas/bloqueadoras restan valor a quien lo usa. Este script lista los miembros inactivos
para que David decida quitarlos (no modifica nada).

    python tools/starterpack_review.py [--days 60]
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def classify_member(profile, last_post, today, days=60):
    """-> (estado, detalle). Estados: ok | inactivo | sin_posts | no_resuelve."""
    if profile is None or str(profile.get("handle", "")).endswith(".invalid"):
        return "no_resuelve", "perfil no resoluble o handle invalido"
    if last_post is None:
        return "sin_posts", "no se ven publicaciones propias"
    try:
        when = datetime.datetime.fromisoformat(last_post.replace("Z", "+00:00")).date()
    except ValueError:
        return "sin_posts", f"fecha ilegible: {last_post}"
    age = (today - when).days
    if age > days:
        return "inactivo", f"ultima publicacion hace {age} dias"
    return "ok", f"ultima publicacion hace {age} dias"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    import bluesky_interact as b
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 60
    did = b._session()["did"]
    packs = b._get(b.AUTH_BASE, "com.atproto.repo.listRecords",
                   {"repo": did, "collection": "app.bsky.graph.starterpack", "limit": 50}).get("records", [])
    if not packs:
        print("no hay starter pack propio")
        return 1
    list_uri = packs[0]["value"]["list"]
    items = b._get(b.PUBLIC_BASE, "app.bsky.graph.getList", {"list": list_uri, "limit": 100},
                   auth=False).get("items", [])
    today = datetime.date.today()
    problems = []
    for item in items:
        profile = item.get("subject") or {}
        if profile.get("did") == did:
            continue
        feed = b._get(b.PUBLIC_BASE, "app.bsky.feed.getAuthorFeed",
                      {"actor": profile.get("did"), "limit": 5, "filter": "posts_with_replies"},
                      auth=False).get("feed", [])
        # Cualquier actividad propia cuenta: posts, respuestas y reposts (hay miembros que solo conversan).
        dates = [(f.get("reason") or {}).get("indexedAt") or f["post"]["record"].get("createdAt") for f in feed]
        dates = [d for d in dates if d]
        last = max(dates) if dates else None
        state, detail = classify_member(profile, last, today, days)
        if state != "ok":
            problems.append((profile.get("handle"), state, detail))
    print(f"{len(items) - 1} miembros revisados; {len(problems)} a revisar (umbral {days} dias)")
    for handle, state, detail in problems:
        print(f"  {handle}: {state} - {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
