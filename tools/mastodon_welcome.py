"""Mastodon: bienvenida a quien acaba de llegar y se presenta en espanol (06/10/2026, David: «aprender de las menciones de bienvenida y hacerlas nosotros»).

Aprendido de la mencion que nos mando @rober@masto.es el 22/09 (administrador de masto.es): felicita por la llegada, recomienda presentarse con #presentacion y comparte una Coleccion de
cuentas interesantes para seguir. Es cultura del Fediverso y funciona porque los recien llegados quieren conversar: quien se presenta hoy responde y sigue de vuelta mas que nadie.

Aqui se hace lo mismo con quien nos interesa: cuentas CREADAS hace <=30 dias, con una presentacion (#presentacion, #introduccion…) en espanol, con interes por libros/lectura/escritura/fantasia,
sin bot, pocas decenas o centenares de seguidores y con las que no hemos hablado. Para cada una se prepara una RESPUESTA publica corta (no un mensaje privado: es lo habitual y evita parecer un
DM no pedido; se cambia con `VISIBILITY` en `mastodon_reply_to`) y un follow. La respuesta se compone de piezas intercambiables (apertura + tema + pregunta + a veces nuestra Coleccion de
cuentas en espanol) para que no haya dos iguales; nunca habla del libro ni de la web de David. Descubrimiento sin gastar cupo propio: las lineas de etiqueta de las instancias en espanol
(`mastodon_remote.fetch_timeline`). Genera un plan para `mastodon_execute.py` (que aplica los filtros de ortografia, duplicados y estilo).

    python tools/mastodon_welcome.py [--max 4] [--out mastodon_welcome_plan.json]
"""
import datetime
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mastodon_remote as mr
import scan_common as sc
import text_common as tc

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "mastodon_welcome_plan.json")
HOSTS = ["masto.es", "mast.lat", "tkz.one", "mastodon.cl", "mastodon.cr", "neopaquita.es", "mastorol.es", "mastodon.gal"]
TAGS = ["presentacion", "presentación", "introduccion", "introducción", "nuevoenmastodon", "nuevaenmastodon", "holamastodon"]
MAX_ACCOUNT_AGE_DAYS = 30
MAX_FOLLOWERS = 300
COLLECTION_URL = "https://mastodon.social/collections/117375413405403414"       # «Fantasía y literatura en español» (mastodon_collection.py)
COLLECTION_SHARE = 0.4

PENDING_TEXT = "(pendiente de ChatGPT)"      # 08/10: la bienvenida ya no se compone de piezas fijas; la escribe ChatGPT con el texto de la presentacion (reply_queue)


def topic_of(text):
    value = tc.niche_hits(text)
    folded = " ".join(str(text or "").casefold().split())
    if re.search(r"escrib|autor|novela|relato", folded):
        return "escritura"
    if re.search(r"fantas|ciencia ficci|sci-?fi|rol\b", folded):
        return "fantasia"
    if value:
        return "libros"
    return "general"


def discover(today=None, getter=None, hosts=HOSTS, tags=TAGS):
    """{acct: {url, text, created, followers, host}} de presentaciones recientes en espanol de cuentas nuevas (>0 terminos del nicho)."""
    today = today or datetime.date.today()
    found = {}
    for host in hosts:
        for tag in tags:
            try:
                rows = mr.fetch_timeline(host, tag, pages=1, **({"getter": getter} if getter else {}))
            except Exception:
                continue
            for status in rows:
                account = status.get("account") or {}
                acct = str(account.get("acct") or "").casefold()
                if not acct:
                    continue
                if "@" not in acct:
                    acct = f"{acct}@{host}"
                try:
                    age = (today - datetime.date.fromisoformat(str(account.get("created_at"))[:10])).days
                except ValueError:
                    continue
                text = mr.plain(status.get("content"))
                url = str(status.get("url") or "")
                if (age > MAX_ACCOUNT_AGE_DAYS or account.get("bot") or account.get("group") or status.get("in_reply_to_id") or status.get("reblog")
                        or status.get("visibility") != "public" or int(account.get("followers_count") or 0) > MAX_FOLLOWERS or not url.startswith("https://")):
                    continue
                language = (status.get("language") or "").casefold()
                if not ((language == "es" or language.startswith("es-")) if language else tc.looks_spanish(text)):
                    continue
                if tc.foreign_language(text) or sc.is_political(text) or sc.looks_activist(text) or len(text) < 40:
                    continue
                if tc.niche_hits(text) < 1:
                    continue
                found.setdefault(acct, {"url": url, "text": text, "created": age, "followers": int(account.get("followers_count") or 0), "host": host})
    return found


def build(found, known, rng=None, limit=4, dup_check=None):
    """Plan (reply + follow por cuenta) para las mejores presentaciones: nicho primero, mas nuevas primero; sin cuentas ya conocidas."""
    ranked = sorted(found.items(), key=lambda kv: (-tc.niche_hits(kv[1]["text"]), kv[1]["created"], kv[0]))
    plan, used = [], set()
    for acct, info in ranked:
        if len(plan) >= limit * 2:
            break
        bare = acct.split("@")[0]
        if acct in known or bare in known:
            continue
        text = PENDING_TEXT
        used.add(acct)
        plan.append({"handle": acct, "kind": "reply", "url": info["url"], "text": text, "post_text": info["text"], "motivo": f"welcome:presentacion:cuenta_nueva={info['created']}d:src={info['host']}"})
        plan.append({"handle": acct, "kind": "follow", "motivo": "welcome:presentacion"})
    return plan


def write_texts(plan, log=print):
    """Sustituye el texto pendiente de cada bienvenida por el que escribe ChatGPT (cola de respuestas, sin esperar el navegador). Sin texto escrito todavia la bienvenida se omite (el follow se mantiene)."""
    replies = [a for a in plan if a["kind"] == "reply"]
    if not replies:
        return plan
    try:
        import reply_hold
        import reply_queue
        if reply_hold.held():
            got = {}
        else:
            items = [{"id": a["handle"], "network": "mastodon", "author": a["handle"], "text": a.get("post_text") or "", "context": "se acaba de presentar en Mastodon (cuenta nueva): bienvenida breve y cálida, sin enlaces"} for a in replies]
            got = reply_queue.get_or_enqueue(items, "mastodon", log, wait_min=3)
    except Exception as exc:
        log(f"[mastodon_welcome] sin textos de ChatGPT ({type(exc).__name__}: {str(exc)[:60]}): solo follows")
        got = {}
    out = []
    for action in plan:
        if action["kind"] == "reply":
            if not got.get(action["handle"]):
                continue
            action = {**action, "text": got[action["handle"]]}
        out.append(action)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else 4
    out = os.path.abspath(argv[argv.index("--out") + 1]) if "--out" in argv else OUT
    known = {h.casefold() for h in sc.known_accounts(os.path.join(ROOT, "SISTEMA_DIARIO_MASTODON", "registro_interacciones.csv"))}
    known |= {h.casefold() for h in sc.discarded_handles(os.path.join(ROOT, "SISTEMA_DIARIO_MASTODON", "registro_interacciones.csv"))}
    import check_duplicate_phrase as dup
    found = discover()
    plan = build(found, known, random.Random(), limit, dup_check=lambda text: dup.check(text))
    plan = write_texts(plan[:limit * 2])
    with open(out, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
    print(f"bienvenidas: {len(found)} presentaciones candidatas, {sum(1 for a in plan if a['kind'] == 'reply')} respuestas listas, {len(plan)} acciones -> {os.path.relpath(out, ROOT)}")
    for item in plan:
        if item["kind"] == "reply":
            print(f"  @{item['handle']} ({item['motivo']}): {item['text'][:110]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
