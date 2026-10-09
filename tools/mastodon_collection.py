"""Collection propia de Mastodon (03/10): hasta 25 perfiles curados, publica y
descubrible (API de Collections de Mastodon 4.6+, api_versions.mastodon >= 10).
Es el equivalente Mastodon del starter pack de Bluesky; los hashtags siguen siendo el
canal de entrada de candidatos, la Collection es un activo de descubrimiento.

    python tools/mastodon_collection.py            # dry-run: resuelve y muestra
    python tools/mastodon_collection.py --apply    # crea la coleccion y anade perfiles

Idempotente: si ya existe una coleccion con ese nombre solo anade los que falten. Cada
perfil se anade por separado y el servidor puede rechazar a quien no acepta ser incluido:
se informa cuales entraron. Autorizado por David el 03/10 ("sigue con las ideas grandes").
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

NAME = "Fantasía y literatura en español"       # max 40
DESCRIPTION = "Gente real que escribe y lee fantasía, ciencia ficción y literatura en español."  # max 100
LANGUAGE = "es"
TAG = "Libros"
ACCOUNTS = """
lobonegro@masto.es MontseMartin@tkz.one juanbauty@masto.es cktodon@mas.to asambleadepalabras
laposadadelcuervolector@masto.es BelenConde@masto.es nacho@frankenwolke.com Kyrylys@frikiverse.zone
Ibnussabel@frikiverse.zone bengo@tkz.one cristinajurado@mastodon.world PalmiraBlum
marcostaracido@mastodon.gal IsaacThornell@tuiter.rocks ccriss92@masto.es runapress
SeverianX@mastodon.la zinniapalas helenawagner
""".split()
MAX_ITEMS = 25


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    import requests
    import mastodon_interact as m
    assert len(NAME) <= 40 and len(DESCRIPTION) <= 100 and len(ACCOUNTS) <= MAX_ITEMS
    apply = "--apply" in argv
    versions = (m._get_v2("instance").get("api_versions") or {}).get("mastodon", 0)
    if int(versions) < 10:
        print(f"el servidor no soporta Collections (api_versions.mastodon={versions})")
        return 1
    me = m._get("accounts/verify_credentials")
    resolved, missing = {}, []
    for acct in ACCOUNTS:
        try:
            info = m._get("accounts/lookup", {"acct": acct})
            if info.get("bot") or info.get("locked"):
                missing.append(f"{acct} (bot/privada)")
                continue
            resolved[acct] = info["id"]
        except Exception as exc:
            missing.append(f"{acct} ({str(exc)[:40]})")
    print(f"{len(resolved)} perfiles resueltos; descartados: {missing}")
    headers = m._headers()
    existing = requests.get(f"{m.API}/accounts/{me['id']}/collections", headers=headers, timeout=20).json()
    collection = next((c for c in existing.get("collections", []) if c.get("name") == NAME), None)
    print("coleccion existente:" if collection else "coleccion nueva:", NAME)
    if not apply:
        print("(dry-run) usa --apply para crear/completar")
        return 0
    m._assert_expected_account()
    if collection is None:
        r = requests.post(f"{m.API}/collections", headers=headers, timeout=30, data={
            "name": NAME, "description": DESCRIPTION, "language": LANGUAGE, "tag_name": TAG,
            "sensitive": "false", "discoverable": "true"})
        if r.status_code != 200:
            raise RuntimeError(f"crear coleccion fallo ({r.status_code}): {r.text[:300]}")
        body = r.json()
        collection = body.get("collection") or body
        print("coleccion creada:", collection.get("id"))
    present = {item.get("account_id") for item in (collection.get("items") or [])}
    added, rejected = [], []
    for acct, account_id in resolved.items():
        if account_id in present:
            continue
        r = requests.post(f"{m.API}/collections/{collection['id']}/items", headers=headers, timeout=30,
                          data={"account_id": account_id})
        (added if r.status_code == 200 else rejected).append(acct if r.status_code == 200 else f"{acct} [{r.status_code}]")
    print(f"anadidos {len(added)}: {added}")
    print(f"rechazados {len(rejected)}: {rejected}")
    print("id de la coleccion:", collection.get("id"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
