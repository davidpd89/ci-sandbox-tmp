"""Puesta a punto del perfil propio en Bluesky y Mastodon (02/10).

El perfil es donde aterriza quien llega desde una reply: sin bio con nicho, ni
post fijado ni hashtags destacados, la reply no convierte en seguidor. Edita
SOLO bio, post fijado, campos y hashtags destacados; nunca publica posts.
Dry-run por defecto, `--apply` escribe. Cada paso es idempotente.

    python tools/profile_tune.py bluesky [--apply]
    python tools/profile_tune.py mastodon [--apply]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

BLUESKY_BIO = (
    "Escritor gallego en Madrid. Fantasía, identidad y memoria. "      # texto que David dejo a mano en Bluesky; no se pisa
    "Autor de Las manecillas del recuerdo y Samuel entre mundos. autorademodiaz.com · "
    "Mastodon: @autorademodiaz@mastodon.social"
)
BLUESKY_BIO_MAX = 256
# Post de presentacion (26/06): dice a quien llega que se busca gente real que
# hable de fantasia juvenil en espanol.
BLUESKY_PINNED_RKEY = "3mx6sir4bw72l"   # 06/10: presentacion con foto (tools/bluesky_pin.py); el anterior era 3mp74envaml2q

MASTODON_BIO = (
    "Escritor gallego en Madrid. Fantasía, memoria y libros que dejan poso. "
    "Autor de Las manecillas del recuerdo (Monza Ediciones, 2026) y "
    "Samuel entre mundos (Libros Indie, 2025). "
    "#Fantasía #Libros #Escritura #Bookstodon"
)
MASTODON_BIO_MAX = 500
MASTODON_FIELDS = [
    ("Web", "https://autorademodiaz.com"),
    ("Libros", "Las manecillas del recuerdo · Samuel entre mundos"),
    ("Bluesky", "https://bsky.app/profile/autorademoescritor.bsky.social"),   # 06/10: un usuario dudo de si ambas cuentas eran nuestras; las dos se enlazan entre si
]
MASTODON_FEATURED_TAGS = ["Fantasía", "Libros", "Escritura", "Bookstodon"]
MASTODON_PINNED_ID = "117316683770550793"  # presentacion del 22/09


def _flat(html_or_text):
    """Compara bio/campos sin depender de como Mastodon renderiza hashtags y
    enlaces ('# Fantasia', 'https:// web') al quitar el HTML."""
    import re
    import mastodon_interact as m
    return re.sub(r"\s+", "", m._plain_text(html_or_text))


def check_texts():
    assert len(BLUESKY_BIO) <= BLUESKY_BIO_MAX, len(BLUESKY_BIO)
    assert len(MASTODON_BIO) <= MASTODON_BIO_MAX, len(MASTODON_BIO)


def bluesky(apply):
    import bluesky_interact as b
    sess = b._session()
    did = sess["did"]
    got = b._get(b.AUTH_BASE, "com.atproto.repo.getRecord",
                 {"repo": did, "collection": "app.bsky.actor.profile", "rkey": "self"}, auth=True)
    record = dict(got["value"])
    cid = got.get("cid")
    pinned_uri = f"at://{did}/app.bsky.feed.post/{BLUESKY_PINNED_RKEY}"
    post = b._get(b.AUTH_BASE, "com.atproto.repo.getRecord",
                  {"repo": did, "collection": "app.bsky.feed.post", "rkey": BLUESKY_PINNED_RKEY}, auth=True)
    pinned_cid = post["cid"]
    changes = []
    if record.get("description") != BLUESKY_BIO:
        changes.append(("bio", record.get("description"), BLUESKY_BIO))
        record["description"] = BLUESKY_BIO
    current_pin = (record.get("pinnedPost") or {}).get("uri")
    if current_pin != pinned_uri:
        changes.append(("post fijado", current_pin, pinned_uri))
        record["pinnedPost"] = {"uri": pinned_uri, "cid": pinned_cid}
    if not changes:
        print("bluesky: perfil ya al dia")
        return
    for name, old, new in changes:
        print(f"bluesky {name}: {old!r} -> {new!r}")
    if not apply:
        print("(dry-run) usa --apply para escribir")
        return
    record["$type"] = "app.bsky.actor.profile"
    b._post_xrpc("com.atproto.repo.putRecord", {
        "repo": did, "collection": "app.bsky.actor.profile", "rkey": "self",
        "record": record, "swapRecord": cid,
    })
    print("bluesky: perfil actualizado (avatar y banner conservados)")


def mastodon(apply):
    import requests
    import mastodon_interact as m
    me = m._get("accounts/verify_credentials")
    current_fields = [(f["name"], _flat(f["value"])) for f in me.get("fields", [])]
    featured = {t["name"].casefold() for t in m._get(f"accounts/{me['id']}/featured_tags")}
    pinned = [s["id"] for s in m._get(f"accounts/{me['id']}/statuses", {"pinned": "true"})]
    plan = []
    if _flat(me.get("note")) != _flat(MASTODON_BIO):
        plan.append("bio")
    if current_fields != [(n, _flat(v)) for n, v in MASTODON_FIELDS]:
        plan.append("campos")
    missing_tags = [t for t in MASTODON_FEATURED_TAGS if t.casefold() not in featured]
    if missing_tags:
        plan.append(f"hashtags destacados {missing_tags}")
    if MASTODON_PINNED_ID not in pinned:
        plan.append("post fijado")
    if not plan:
        print("mastodon: perfil ya al dia")
        return
    print("mastodon: cambios pendientes:", ", ".join(plan))
    if not apply:
        print("(dry-run) usa --apply para escribir")
        return
    m._assert_expected_account()
    headers = m._headers()
    if "bio" in plan or "campos" in plan:
        data = {"note": MASTODON_BIO}
        for i, (name, value) in enumerate(MASTODON_FIELDS):
            data[f"fields_attributes[{i}][name]"] = name
            data[f"fields_attributes[{i}][value]"] = value
        r = requests.patch(f"{m.API}/accounts/update_credentials", data=data, headers=headers, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"update_credentials fallo ({r.status_code}): {r.text[:200]}")
        print("mastodon: bio y campos actualizados")
    for tag in missing_tags:
        r = requests.post(f"{m.API}/featured_tags", data={"name": tag}, headers=headers, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"featured_tags {tag} fallo ({r.status_code}): {r.text[:200]}")
        print(f"mastodon: hashtag destacado {tag}")
    if "post fijado" in plan:
        r = requests.post(f"{m.API}/statuses/{MASTODON_PINNED_ID}/pin", headers=headers, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"pin fallo ({r.status_code}): {r.text[:200]}")
        print("mastodon: post de presentacion fijado")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("bluesky", "mastodon"):
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    check_texts()
    if argv[0] == "mastodon":
        import mastodon_interact as m
        m.patient(lambda: mastodon("--apply" in argv))       # el cupo de la API lo agotan los scans: un 429 espera y reintenta, no tira el trabajo
    else:
        bluesky("--apply" in argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
