"""Starter pack propio de Bluesky (03/10): los packs son la mayor palanca de
crecimiento de la plataforma (cada usuario nuevo ve packs sugeridos y "seguir a
todos"). Crea una lista de referencia + el starter pack con cuentas reales de
fantasia/literatura en espanol que ya hemos tratado, incluido el propio David.

    python tools/bluesky_starterpack.py            # dry-run: resuelve y muestra
    python tools/bluesky_starterpack.py --apply    # crea lista + items + pack

Idempotente: si ya existe un pack con el mismo nombre no crea otro.
Autorizado expresamente por David el 03/10 ("crea el starter pack").
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

NAME = "Lectores y escritores de fantasía en español"
DESCRIPTION = (
    "Gente real que lee y escribe fantasía, ciencia ficción, terror y literatura en español: "
    "autoras, autores, editoriales pequeñas y lectores con criterio. Seguirlos a todos es "
    "una forma rápida de llenar el feed de conversación sobre libros."
)
HANDLES = """
marinagolondrina eltransbordador anushkabenari.eurosky.social hendelie cuentosbo blackonion sgaywalker
marcapaginasolv pdmatos sarabelramos juanbauty noradewitt marinaobaghee susanacalvo jsbalsera
tatianaherrero supistaudra meryweasley cristinacarou labibliotekat lordcharlie87 rjrandom
arbarrios20 tenshiscarlet republicalasletras tronorolera txustorres cblancowriter
conhambredelectura triadaliteraria el1as1989 helenawagner opallietch cinedeescritor
thesoufflegirl leonardojimenez lmnieto lauramago revistakorad koldoautor pabellondelectura
miguelrnuno alasondroalegre winterfellmint bibliotecamarsten angelgropero.eurosky.social
""".split()


def full_handle(name):
    return name if "." in name else f"{name}.bsky.social"


def resolve(b, handles):
    """handle -> did, via getProfiles (lotes de 25); descarta invalidos."""
    out = {}
    for i in range(0, len(handles), 25):
        chunk = handles[i:i + 25]
        data = b._get(b.PUBLIC_BASE, "app.bsky.actor.getProfiles", {"actors": chunk}, auth=False)
        for p in data.get("profiles", []):
            if p["handle"].endswith(".invalid"):
                continue
            out[p["handle"]] = p["did"]
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    import bluesky_interact as b
    apply = "--apply" in argv
    sess = b._session()
    did = sess["did"]
    existing = [r for r in b._get(b.AUTH_BASE, "com.atproto.repo.listRecords",
                                  {"repo": did, "collection": "app.bsky.graph.starterpack", "limit": 50},
                                  auth=True).get("records", [])
                if r["value"].get("name") == NAME]
    if existing:
        print("ya existe el starter pack:", existing[0]["uri"])
        return 0
    resolved = resolve(b, [full_handle(h) for h in HANDLES])
    missing = [full_handle(h) for h in HANDLES if full_handle(h) not in resolved]
    print(f"{len(resolved)} cuentas resueltas; sin resolver: {missing}")
    members = list(resolved.values()) + [did]
    print(f"{len(members)} miembros (incluye la cuenta propia); nombre: {NAME!r}")
    if not apply:
        print("(dry-run) usa --apply para crear")
        return 0
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    created = b._post_xrpc("com.atproto.repo.createRecord", {
        "repo": did, "collection": "app.bsky.graph.list",
        "record": {"$type": "app.bsky.graph.list", "purpose": "app.bsky.graph.defs#referencelist",
                   "name": NAME, "description": DESCRIPTION, "createdAt": now},
    })
    list_uri = created["uri"]
    print("lista creada:", list_uri)
    writes = [{"$type": "com.atproto.repo.applyWrites#create", "collection": "app.bsky.graph.listitem",
               "value": {"$type": "app.bsky.graph.listitem", "subject": member, "list": list_uri,
                         "createdAt": now}} for member in members]
    for i in range(0, len(writes), 50):
        b._post_xrpc("com.atproto.repo.applyWrites", {"repo": did, "writes": writes[i:i + 50]})
    print(f"{len(writes)} miembros anadidos a la lista")
    pack = b._post_xrpc("com.atproto.repo.createRecord", {
        "repo": did, "collection": "app.bsky.graph.starterpack",
        "record": {"$type": "app.bsky.graph.starterpack", "name": NAME, "description": DESCRIPTION,
                   "list": list_uri, "createdAt": now},
    })
    rkey = pack["uri"].rsplit("/", 1)[-1]
    print("starter pack creado:", pack["uri"])
    print(f"enlace: https://bsky.app/starter-pack/{b.HANDLE}/{rkey}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
