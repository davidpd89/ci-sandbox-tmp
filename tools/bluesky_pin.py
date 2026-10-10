"""Bluesky: publica el post de presentacion (con foto) y lo fija en el perfil (06/10/2026, David: «apruebo todo lo que veas bien… cambia el de Bluesky»).

El perfil de Bluesky guarda el post fijado en su registro `app.bsky.actor.profile/self` (campo `pinnedPost` = {uri, cid}); se cambia con `com.atproto.repo.putRecord` conservando el resto
del registro (nombre, bio, avatar, banner) y con `swapRecord` para no pisar un cambio simultaneo. Idempotente: si el fijado ya empieza por el texto de la presentacion no hace nada.

    python tools/bluesky_pin.py --dry-run     # muestra textos y comprueba longitudes
    python tools/bluesky_pin.py               # publica presentacion + respuesta con enlaces y la fija
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bluesky_interact as b

ROOT = os.path.join(os.path.dirname(__file__), "..")
PHOTO = os.path.join(ROOT, "00_OPERATIVO", "RECURSOS", "assets", "perfil", "david-porto-retrato-bn.jpg")
<<<<<<< HEAD
ALT = "Retrato en blanco y negro de Autora Demo Díaz, escritor, sentado con la cabeza apoyada en una mano y un jersey de punto."

INTRO = ("Hola, soy Autora Demo, escritor gallego en Madrid. Escribo fantasía y novelas que dejan poso: «Samuel entre mundos» y «Las manecillas del recuerdo».\n\n"
         "¿Hablamos de libros, webs, escritura o de lo que os apetezca? Contadme qué estáis leyendo 👇\n\n"
         "https://autorademodiaz.com")
LINKS = ("Los libros, por si queréis echarles un ojo:\n"
         "📖 Samuel entre mundos (fantasía juvenil): https://www.amazon.es/dp/B0GB6LGQFH?tag=autorademo-21\n"
=======
ALT = "Retrato en blanco y negro de David Porto Díaz, escritor, sentado con la cabeza apoyada en una mano y un jersey de punto."

INTRO = ("Hola, soy David Porto, escritor gallego en Madrid. Escribo fantasía y novelas que dejan poso: «Samuel entre mundos» y «Las manecillas del recuerdo».\n\n"
         "¿Hablamos de libros, webs, escritura o de lo que os apetezca? Contadme qué estáis leyendo 👇\n\n"
         "https://davidportodiaz.com")
LINKS = ("Los libros, por si queréis echarles un ojo:\n"
         "📖 Samuel entre mundos (fantasía juvenil): https://www.amazon.es/dp/B0GB6LGQFH?tag=davidporto-21\n"
>>>>>>> origin/research/public-reuse-parent
         "📖 Las manecillas del recuerdo (novela coral): https://amzn.to/4zW6Yeu")


def _current_pinned_text(did):
    profile = b._get(b.PUBLIC_BASE, "app.bsky.actor.getProfile", {"actor": did}, auth=False)
    uri = ((profile or {}).get("pinnedPost") or {}).get("uri")
    if not uri:
        return None
    rec = b._get_post_record(uri)
    return (rec or {}).get("text") if isinstance(rec, dict) else None


def publish():
    sess = b._session()
    did = sess["did"]
    record = b._add_richtext({"$type": "app.bsky.feed.post", "text": INTRO, "createdAt": b._now(), "langs": ["es"]})
    record["embed"] = b._upload_image(PHOTO, ALT)
    root = b._require_created_record(b._post_xrpc("com.atproto.repo.createRecord", {"repo": did, "collection": "app.bsky.feed.post", "record": record}), "app.bsky.feed.post")
    reply = b._add_richtext({"$type": "app.bsky.feed.post", "text": LINKS, "createdAt": b._now(), "langs": ["es"],
                             "reply": {"root": {"uri": root["uri"], "cid": root["cid"]}, "parent": {"uri": root["uri"], "cid": root["cid"]}}})
    b._require_created_record(b._post_xrpc("com.atproto.repo.createRecord", {"repo": did, "collection": "app.bsky.feed.post", "record": reply}), "app.bsky.feed.post")
    return did, root


def pin(did, uri, cid):
    current = b._get(b.AUTH_BASE, "com.atproto.repo.getRecord", {"repo": did, "collection": "app.bsky.actor.profile", "rkey": "self"})
    value = dict(current["value"])
    value["pinnedPost"] = {"uri": uri, "cid": cid}
    return b._post_xrpc("com.atproto.repo.putRecord", {"repo": did, "collection": "app.bsky.actor.profile", "rkey": "self", "record": value, "swapRecord": current["cid"]})


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    b._check_length(INTRO)
    b._check_length(LINKS)
    b._check_spanish_orthography(INTRO)
    b._check_spanish_orthography(LINKS)
    if "--dry-run" in argv:
        print(f"INTRO ({len(INTRO)}):\n{INTRO}\n\nLINKS ({len(LINKS)}):\n{LINKS}\n\nfoto: {os.path.getsize(PHOTO)} bytes")
        return 0
    b._require_credentials()
    did = b._session()["did"]
    existing = _current_pinned_text(did)
<<<<<<< HEAD
    if existing and existing.startswith("Hola, soy Autora Demo"):
        print("el fijado ya es la presentacion; sin cambios")
        return 0
    did, root = publish()
=======
    if existing and existing.startswith("Hola, soy David Porto"):
        print("el fijado ya es la presentacion; sin cambios")
        return 0
    import circuit_breaker as cb
    allowed, reason = cb.write_preflight("bluesky")
    if not allowed:
        print(f"[bluesky] cortacircuitos ABIERTO: {reason}; no publicar")
        return 0
    did, root = publish()
    allowed, reason = cb.write_preflight("bluesky")
    if not allowed:
        print(f"[bluesky] post creado, fijado pendiente por cuarentena: {reason}")
        return 2
>>>>>>> origin/research/public-reuse-parent
    pin(did, root["uri"], root["cid"])
    print(f"publicado y fijado: {root['uri']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
