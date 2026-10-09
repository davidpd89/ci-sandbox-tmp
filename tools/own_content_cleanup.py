"""Limpieza de huella propia con mas de N dias (02/10) - pedido de David: los
mensajes de crecimiento (replies, citas, reposts) solo importan en el momento;
pasado un mes se borran red por red para no dejar un registro infinito que
dentro de unos anos pueda resultar inapropiado o repetitivo.

A diferencia de los *_cleanup_ttl.py (que solo retiran lo que el ejecutor
programo en su CSV), este barrido lee el estado REAL de la cuenta, asi que
tambien limpia lo anterior a los TTL y lo que se hizo a mano.

Alcance por defecto: reply, quote, repost. NUNCA toca publicaciones originales
(salvo --kinds ...,post), ni respuestas a un hilo propio (son parte de una
publicacion propia), ni el post fijado en Mastodon. Es dry-run salvo --apply.

    python tools/own_content_cleanup.py bluesky            # dry-run
    python tools/own_content_cleanup.py mastodon --apply   # borra de verdad
    python tools/own_content_cleanup.py bluesky --days 45 --max 100 --apply

Cada borrado se anota en SISTEMA_DIARIO_<RED>/limpieza_log.csv. Un rate limit
detiene el lote (lo que quede se borra en la siguiente ejecucion).
X y Threads necesitan navegador (CDP 9223) y no estan cubiertos aun.
"""
import csv
import datetime
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

DEFAULT_DAYS = 30
DEFAULT_KINDS = ("reply", "quote", "repost")
KNOWN_KINDS = DEFAULT_KINDS + ("post",)
DEFAULT_MAX = 200
LOG_FIELDS = ["fecha", "kind", "ref", "creado", "extracto", "estado"]
ROOT = os.path.join(os.path.dirname(__file__), "..")


class StopBatch(RuntimeError):
    """Rate limit u otra parada que debe cortar el lote sin marcarlo fallido."""


def _parse_date(value):
    try:
        return datetime.date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def select_expired(items, today, days=DEFAULT_DAYS, kinds=DEFAULT_KINDS):
    """Items: dicts con ref, kind, created (YYYY-MM-DD...), text, protected."""
    cutoff = today - datetime.timedelta(days=days)
    out = []
    for item in items:
        created = _parse_date(item.get("created"))
        if created is None or created > cutoff:
            continue
        if item.get("protected") or item.get("kind") not in kinds:
            continue
        out.append(item)
    out.sort(key=lambda it: it["created"])
    return out


def _log(path, row):
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=LOG_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)


def run(adapter, *, today=None, days=DEFAULT_DAYS, kinds=DEFAULT_KINDS,
        apply=False, limit=DEFAULT_MAX, log_path=None, pause=None, out=print):
    today = today or datetime.date.today()
    items = adapter["list"]()
    due = select_expired(items, today, days, kinds)
    verify = adapter.get("verify")
    if verify:
        due = [item for item in due if verify(item)]
    by_kind = {}
    for item in due:
        by_kind[item["kind"]] = by_kind.get(item["kind"], 0) + 1
    out(f"{len(items)} elementos propios leidos; {len(due)} con mas de {days} dias "
        f"({', '.join(f'{k}={v}' for k, v in sorted(by_kind.items())) or 'nada'}).")
    batch = due[:limit]
    if len(due) > len(batch):
        out(f"Limite por ejecucion: {limit}; quedan {len(due) - len(batch)} para la siguiente.")
    if not apply:
        for item in batch[:15]:
            out(f"  [dry-run] {item['kind']} {item['created'][:10]} {item['text'][:70]!r}")
        if len(batch) > 15:
            out(f"  ... y {len(batch) - 15} mas. Usa --apply para borrar.")
        return {"due": len(due), "deleted": 0, "failed": 0, "stopped": False}

    deleted = failed = 0
    stopped = False
    for index, item in enumerate(batch):
        try:
            adapter["delete"](item)
            estado = "borrado"
            deleted += 1
        except StopBatch as exc:
            out(f"PARADA: {exc}. El resto queda para la proxima ejecucion.")
            stopped = True
            break
        except Exception as exc:
            estado = f"fallo:{type(exc).__name__}:{exc}"[:200]
            failed += 1
            out(f"FALLO {item['ref']}: {exc}")
        if log_path:
            _log(log_path, {
                "fecha": today.isoformat(), "kind": item["kind"], "ref": item["ref"],
                "creado": item["created"][:10], "extracto": item["text"][:60], "estado": estado,
            })
        if pause and index < len(batch) - 1:
            pause()
    out(f"{deleted} borrados, {failed} fallidos" + (" (parado por rate limit)" if stopped else "") + ".")
    return {"due": len(due), "deleted": deleted, "failed": failed, "stopped": stopped}


# ---------------------------------------------------------------- Bluesky
def _embedded_post_uri(value):
    """AT-URI del post embebido (cita), o "" si el embed no es un post (starter pack,
    lista, feed...). Soporta embed.record y embed.recordWithMedia."""
    embed = value.get("embed") or {}
    record = embed.get("record")
    if isinstance(record, dict) and isinstance(record.get("record"), dict):  # recordWithMedia
        record = record["record"]
    uri = record.get("uri") if isinstance(record, dict) else ""
    return uri if isinstance(uri, str) and "/app.bsky.feed.post/" in uri else ""


def classify_bluesky(record, own_did, pinned_uri=None):
    """record: item de listRecords (uri + value). Devuelve el item normalizado.

    Protegidos: el post fijado del perfil y toda respuesta dentro de un hilo propio
    (la RAIZ es nuestra: incluye contestar a quien comenta nuestros originales). Una
    cita solo lo es si embebe un post AJENO; citar un post propio o embeber un starter
    pack/lista/feed es contenido propio ("post"), no se toca."""
    value = record.get("value") or {}
    own_prefix = f"at://{own_did}/"
    kind, protected = "post", record.get("uri") == pinned_uri
    reply = value.get("reply")
    if isinstance(reply, dict):
        root = (reply.get("root") or {}).get("uri") or ""
        kind = "reply"
        protected = protected or root.startswith(own_prefix)
    else:
        embedded = _embedded_post_uri(value)
        if embedded and not embedded.startswith(own_prefix):
            kind = "quote"
    return {"ref": record["uri"], "kind": kind, "created": value.get("createdAt") or "",
            "text": value.get("text") or "", "protected": protected}


def _bluesky_records(b, collection):
    sess = b._session()
    cursor, seen = None, set()
    while True:
        params = {"repo": sess["did"], "collection": collection, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        data = b._get(b.AUTH_BASE, "com.atproto.repo.listRecords", params, auth=True)
        records = data.get("records")
        if not isinstance(records, list):
            raise RuntimeError(f"listRecords {collection} no devolvio una lista")
        yield from records
        cursor = data.get("cursor")
        if not cursor:
            return
        if cursor in seen:
            raise RuntimeError("Paginacion listRecords repetida; abortando lectura")
        seen.add(cursor)


def bluesky_adapter():
    import bluesky_interact as b
    import scan_common as sc  # noqa: F401  (pausa comun)
    did = b._session()["did"]
    profile = b._get(b.AUTH_BASE, "com.atproto.repo.getRecord",
                     {"repo": did, "collection": "app.bsky.actor.profile", "rkey": "self"}, auth=True)
    pinned_uri = ((profile.get("value") or {}).get("pinnedPost") or {}).get("uri")

    def list_items():
        items = [classify_bluesky(r, did, pinned_uri) for r in _bluesky_records(b, "app.bsky.feed.post")]
        for r in _bluesky_records(b, "app.bsky.feed.repost"):
            value = r.get("value") or {}
            items.append({"ref": r["uri"], "kind": "repost", "created": value.get("createdAt") or "",
                          "text": (value.get("subject") or {}).get("uri", ""), "protected": False})
        return items

    def delete(item):
        try:
            b.delete_own_record(item["ref"])
        except b.RateLimitExceeded as exc:
            raise StopBatch(str(exc)) from exc

    return {"list": list_items, "delete": delete, "log": os.path.join(ROOT, "SISTEMA_DIARIO_BLUESKY", "limpieza_log.csv")}


# --------------------------------------------------------------- Mastodon
def classify_mastodon(status, own_id):
    """status: dict de la API de Mastodon. Devuelve el item normalizado."""
    text =" ".join(html.unescape(re.sub(r"<[^>]+>", " ", status.get("content") or "")).split())
    reblog = status.get("reblog")
    if isinstance(reblog, dict):
        # el boost se retira sobre el status ORIGINAL (unreblog), no sobre el envoltorio
        return {"ref": str(reblog["id"]), "kind": "repost", "created": status.get("created_at") or "",
                "text": (reblog.get("url") or ""), "protected": False}
    kind, protected = "post", bool(status.get("pinned"))
    if status.get("in_reply_to_id"):
        kind = "reply"
        # fijado O parte de un hilo propio (respondemos a nosotros mismos)
        protected = protected or str(status.get("in_reply_to_account_id")) == str(own_id)
    return {"ref": str(status["id"]), "kind": kind, "created": status.get("created_at") or "",
            "text": text, "protected": protected, "parent_id": str(status.get("in_reply_to_id") or "")}


def mastodon_adapter(max_pages=60):
    import mastodon_interact as m
    me = m._get("accounts/verify_credentials")
    own_id = str(me["id"])

    def list_items():
        rows = m._get_paginated(f"accounts/{own_id}/statuses", {"limit": 40}, max_pages=max_pages)
        return [classify_mastodon(s, own_id) for s in rows]

    def verify(item):
        """Solo para lo que ya venceria: una reply nuestra a alguien que a su vez
        comentaba un post NUESTRO forma parte de un hilo propio y se conserva."""
        if item["kind"] != "reply" or not item.get("parent_id"):
            return True
        try:
            parent = m._get(f"statuses/{item['parent_id']}")
        except Exception:
            return False  # sin poder comprobarlo, no se borra
        return str(parent.get("in_reply_to_account_id")) != own_id and str(parent["account"]["id"]) != own_id

    def delete(item):
        try:
            if item["kind"] == "repost":
                m.unboost(item["ref"])
            else:
                m.delete_post(item["ref"])
        except m.MastodonRateLimitExceeded as exc:
            raise StopBatch(str(exc)) from exc
        except RuntimeError as exc:
            if "(429)" in str(exc):
                raise StopBatch(str(exc)) from exc
            raise

    return {"list": list_items, "delete": delete, "verify": verify,
            "log": os.path.join(ROOT, "SISTEMA_DIARIO_MASTODON", "limpieza_log.csv")}


ADAPTERS = {"bluesky": bluesky_adapter, "mastodon": mastodon_adapter}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("network", choices=sorted(ADAPTERS))
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--kinds", default=",".join(DEFAULT_KINDS))
    parser.add_argument("--max", type=int, default=DEFAULT_MAX, dest="limit")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    unknown = set(kinds) - set(KNOWN_KINDS)
    if unknown or not kinds:
        parser.error(f"--kinds invalido {sorted(unknown) or ''}; validos: {', '.join(KNOWN_KINDS)}")
    adapter = ADAPTERS[args.network]()
    import scan_common as sc
    run(adapter, days=args.days, kinds=kinds, apply=args.apply, limit=args.limit,
        log_path=adapter["log"], pause=lambda: sc.pause(2, 5))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
