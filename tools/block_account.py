"""Bloquear una cuenta y retirar lo que hicimos sobre ella, comun a Bluesky y Mastodon (06/10/2026, David: «bloquearemos a esta persona y borraremos lo relacionado»).

Para cada cuenta: deshace nuestros likes/favoritos y reposts/boosts sobre sus publicaciones, deja de seguirla y la bloquea. Queda una fila `block` en el registro de la red:
`scan_common.discarded_handles` la excluye para siempre de los scans (como un unfollow). Sin `--apply` solo informa.

    python tools/block_account.py bluesky souly79.bsky.social [--apply]
    python tools/block_account.py mastodon Schurke@nrw.social [--apply]
    python tools/block_account.py mastodon DanaS@literatur.social --no-block [--apply]      # solo dejar de seguir y retirar favoritos
"""
import csv
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.join(os.path.dirname(__file__), "..")


def _registro(net, account, motivo, tipo="block"):
    path = os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "registro_interacciones.csv")
    with open(path, "a", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerow([datetime.date.today().isoformat(), "@" + account.lstrip("@"), tipo, "", "", "confirmado", motivo])


def bluesky(handles, apply):
    import bluesky_interact as b
    sess = b._session()
    did = sess["did"]
    for handle in handles:
        profile = b._get(b.PUBLIC_BASE, "app.bsky.actor.getProfile", {"actor": handle}, auth=False)
        target = profile["did"]
        print(f"{handle} -> {target}")
        undone = 0
        for collection in ("app.bsky.feed.like", "app.bsky.feed.repost"):
            cursor = None
            for _ in range(10):
                params = {"repo": did, "collection": collection, "limit": 100}
                if cursor:
                    params["cursor"] = cursor
                data = b._get(b.AUTH_BASE, "com.atproto.repo.listRecords", params)
                for rec in data.get("records", []):
                    subject = ((rec.get("value") or {}).get("subject") or {}).get("uri", "")
                    if subject.startswith(f"at://{target}/"):
                        print(f"  retira {collection.split('.')[-1]}: {subject}")
                        undone += 1
                        if apply:
                            b._post_xrpc("com.atproto.repo.deleteRecord", {"repo": did, "collection": collection, "rkey": rec["uri"].rsplit("/", 1)[-1]})
                cursor = data.get("cursor")
                if not cursor or not data.get("records"):
                    break
        if (profile.get("viewer") or {}).get("following") and apply:
            b.unfollow(handle)
        already = (profile.get("viewer") or {}).get("blocking")
        print(f"  likes/reposts retirados: {undone}; bloqueo previo: {bool(already)}")
        if apply and not already:
            b._post_xrpc("com.atproto.repo.createRecord", {"repo": did, "collection": "app.bsky.graph.block",
                                                          "record": {"$type": "app.bsky.graph.block", "subject": target, "createdAt": b._now()}})
            print("  bloqueada")
        if apply:
            _registro("bluesky", handle, "block:pregunta por cuentas falsas; fuera de nuestro publico")


def mastodon(handles, apply, block=True):
    import mastodon_interact as m
    for handle in handles:
        found = m.search(handle, "accounts", limit=3, resolve=True).get("accounts", [])
        account = next((a for a in found if a["acct"].casefold() == handle.casefold().lstrip("@")), None)
        if not account:
            print(f"{handle}: no se encuentra")
            continue
        aid = account["id"]
        rel = m._get("accounts/relationships", {"id[]": aid})[0]
        print(f"{handle} -> {aid}; seguimos={rel.get('following')} bloqueada={rel.get('blocking')}")
        undone = 0
        for st in m._get_paginated("favourites", {"limit": 40}, max_pages=10):         # la paginacion de favoritos va por el enlace «next» (sus ids no son los de los estados)
            if (st.get("account") or {}).get("id") == aid:
                print(f"  retira favorito: {st.get('url')}")
                undone += 1
                if apply:
                    m._post(f"statuses/{st['id']}/unfavourite")
        if apply and rel.get("following"):
            m.unfollow(handle, aid)
        if apply and block and not rel.get("blocking"):
            m._post(f"accounts/{aid}/block")
            print("  bloqueada")
        print(f"  favoritos retirados: {undone}")
        if apply:
            _registro("mastodon", handle, "block:pregunta por cuentas falsas; fuera de nuestro publico" if block else "unfollow:fuera de nuestro publico (aleman)", "block" if block else "unfollow")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) < 2 or argv[0] not in ("bluesky", "mastodon"):
        print(__doc__)
        return 2
    apply = "--apply" in argv
    handles = [a for a in argv[1:] if not a.startswith("--")]
    if argv[0] == "bluesky":
        bluesky(handles, apply)
    else:
        mastodon(handles, apply, block="--no-block" not in argv)
    if not apply:
        print("(informe) usa --apply para ejecutar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
