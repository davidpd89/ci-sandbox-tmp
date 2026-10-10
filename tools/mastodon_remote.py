"""Mastodon: posts en espanol de las instancias hispanohablantes, leidos de su API publica SIN gastar nuestro cupo (06/10/2026).

David pidio que Mastodon llegue al nivel de Bluesky («mas sitios, mas formas»). La medicion del embudo (700 perfiles de la shortlist -> solo 155 oportunidades de favorito; el 48 %
de los perfiles sin ningun estado) mostro que el techo es la OFERTA de posts concretos y que cada perfil sin estados cuesta una lectura de nuestra cuota (300 peticiones/5 min,
compartida con las escrituras). Las instancias en espanol (masto.es, mast.lat, tkz.one, mastodon.cl, mastodon.cr, neopaquita.es, mastorol.es, tuiter.rocks...) publican su linea
temporal local por la API sin autenticacion (probado el 06/10: 40 estados por peticion, 37-40 en espanol) y cada instancia tiene SU propio limite: leerlas no gasta nada nuestro.
Aqui se guardan en la reserva (`remote_posts`) los que son del nicho, recientes, en espanol y sin politica/ligue; el scan resuelve cada uno a un estado local con UNA lectura
(`search?resolve=true`, que ya devuelve estado y autor con sus ids locales) y de ahi sigue el flujo normal (favorito, follow, vetado...). Fuente first-touch: `remote_timeline`.

    python tools/mastodon_remote.py mine [--pages 3]      # lee las lineas temporales (publica y por etiqueta) de las instancias
    python tools/mastodon_remote.py stats | top [--n 20]
"""
from __future__ import annotations

import datetime
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
import text_common as bp
import mastodon_pool as mp
import scan_common as sc

HOSTS = ["masto.es", "mast.lat", "tkz.one", "mastodon.cl", "mastodon.cr", "neopaquita.es", "mastorol.es", "tuiter.rocks", "mastodon.gal",
         "mstdn.mx", "frikiverse.zone", "mastodon.social", "mastodon.online", "mas.to", "mastodon.world"]      # 07/10 (David: «faltan muchisimos sitios»): + instancias mexicanas y generalistas con etiquetas en espanol
TAGS = ["libros", "lectura", "fantasia", "escritura", "novela", "literatura", "bookstodon", "leyendo", "escritores", "clubdelectura", "autopublicacion", "rol", "worldbuilding", "microrrelatos",
        # 07/10: consulta M a GPT (RESPUESTA_M_descubrimiento.md): presentaciones y cultura de apoyo entre autores/lectores
        "presentacion", "introduccion", "nuevoenmastodon", "apoyomutuo", "apoyoescritores", "autoresindie", "autoresnoveles", "escritoresnoveles", "escrituracreativa", "booktok",
        "booktokespanol", "lectoresespanoles", "librosrecomendados", "resenasdelibros", "amantesdeloslibros", "autoresespanoles", "escritoresespanoles", "fantasiajuvenil", "romantasy", "letras"]
MAX_AGE_DAYS = 14
PAUSE = 0.4
TIMEOUT = 15
HTML = re.compile(r"<[^>]+>")


def ensure(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS remote_posts (
            url TEXT PRIMARY KEY, host TEXT NOT NULL, acct TEXT NOT NULL, text TEXT NOT NULL, language TEXT, created_at TEXT, niche INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', seen_count INTEGER NOT NULL DEFAULT 1
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_remote_pick ON remote_posts(status, created_at)")
    db.commit()


def plain(html):
    return re.sub(r"\s+", " ", HTML.sub(" ", str(html or ""))).strip()


def _age_days(created_at, today):
    try:
        return (today - datetime.date.fromisoformat(str(created_at)[:10])).days
    except ValueError:
        return None


def keep(status, today=None):
    """(texto, nicho) si el estado vale como oportunidad (publico, en espanol, del nicho, reciente, no respuesta, sin politica/ligue/spam); None si no."""
    today = today or datetime.date.today()
    if not isinstance(status, dict) or status.get("reblog") or status.get("in_reply_to_id"):
        return None
    if status.get("visibility") != "public" or status.get("sensitive") or status.get("spoiler_text"):
        return None
    account = status.get("account") or {}
    if account.get("bot") or account.get("group") or sc.is_feed_bridge(str(account.get("acct") or "")):
        return None
    text = plain(status.get("content"))
    if len(text) < 30 or sc.is_political(text) or sc.looks_activist(text) or bp.SPAM.search(text):
        return None
    language = (status.get("language") or "").casefold()
    if language:
        if not (language == "es" or language.startswith("es-")):
            return None
    elif not bp.looks_spanish(text):
        return None
    age = _age_days(status.get("created_at"), today)
    if age is None or age > MAX_AGE_DAYS:
        return None
    tags = " ".join(str(t.get("name") or "") for t in status.get("tags", []) if isinstance(t, dict))
    niche = bp.niche_hits(f"{text} {tags}")
    if niche < 1:
        return None
    return text, niche


def _get(url, params):
<<<<<<< HEAD
    response = requests.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent": "RRSS-AutoraDemo/1.0 (lectura publica; contacto autorademodiaz.com)"})
=======
    response = requests.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent": "RRSS-DavidPorto/1.0 (lectura publica; contacto davidportodiaz.com)"})
>>>>>>> origin/research/public-reuse-parent
    if response.status_code != 200:
        raise RuntimeError(f"{response.status_code}")
    return response.json()


def fetch_timeline(host, tag=None, pages=3, sleep=time.sleep, getter=_get):
    """Estados de la linea temporal publica local de `host` (o de una etiqueta), `pages` paginas de 40 con `max_id`."""
    path = f"timelines/tag/{tag}" if tag else "timelines/public"
    params = {"limit": 40} if tag else {"limit": 40, "local": "true"}
    out, max_id = [], None
    for _ in range(pages):
        if max_id:
            params["max_id"] = max_id
        rows = getter(f"https://{host}/api/v1/{path}", dict(params))
        if not isinstance(rows, list) or not rows:
            break
        out.extend(rows)
        max_id = rows[-1].get("id")
        if not max_id:
            break
        sleep(PAUSE)
    return out


def record(db, host, statuses, today=None):
    """Guarda lo que vale; devuelve cuantos eran nuevos. La URL es la clave (la misma publicacion llega por varias instancias)."""
    today = today or datetime.date.today()
    new = 0
    for status in statuses:
        kept = keep(status, today)
        url = str(status.get("url") or status.get("uri") or "").strip()
        if not kept or not url.startswith("https://"):
            continue
        text, niche = kept
        acct = str((status.get("account") or {}).get("acct") or "").casefold()
        if "@" not in acct:
            acct = f"{acct}@{host}"
        if db.execute("SELECT 1 FROM remote_posts WHERE url = ?", (url,)).fetchone():
            db.execute("UPDATE remote_posts SET seen_count = seen_count + 1 WHERE url = ?", (url,))
            continue
        db.execute("INSERT INTO remote_posts(url, host, acct, text, language, created_at, niche, first_seen) VALUES(?,?,?,?,?,?,?,?)",
                   (url, host, acct, text[:400], status.get("language") or "", str(status.get("created_at") or "")[:19], niche, today.isoformat()))
        new += 1
    db.commit()
    return new


DIRECTORY_HOSTS = ["masto.es", "mast.lat", "tkz.one", "mastodon.cr", "neopaquita.es", "mastorol.es", "frikiverse.zone", "mastodon.gal", "tuiter.rocks", "mstdn.mx", "mastodon.cl"]
DIRECTORY_PAGE = 80
DIRECTORY_PAGES_CYCLE = 24         # el directorio «activos» se recorre por paginas que rotan por dia (80 cuentas por pagina; 07/10: 6 -> 24 paginas)


def directory_accounts(host, offset, getter=_get):
    """Cuentas activas del directorio de perfiles de `host` (las que se apuntaron a ser descubiertas), `DIRECTORY_PAGE` desde `offset`."""
    rows = getter(f"https://{host}/api/v1/directory", {"local": "true", "order": "active", "limit": DIRECTORY_PAGE, "offset": offset})
    return rows if isinstance(rows, list) else []


def mine_directory(db, hosts=DIRECTORY_HOSTS, today=None, max_accounts=60, sleep=time.sleep, getter=_get):
    """Directorios de perfiles de las instancias: de cada cuenta activa con biografia del nicho, sin politica/bot/spam, se leen sus ultimos estados DE SU PROPIA INSTANCIA
    (gratis para nuestro cupo) y se guardan los que valen. Es la forma de convertir cuentas de lectores/autores en posts concretos sin gastar lecturas propias (cada perfil
    sin estados cuesta una en mastodon.social). Devuelve {host: nuevos}."""
    today = today or datetime.date.today()
    ensure(db)
    result = {}
    for index, host in enumerate(hosts):
        found = 0
        offset = ((today.toordinal() + index) % DIRECTORY_PAGES_CYCLE) * DIRECTORY_PAGE
        try:
            accounts = directory_accounts(host, offset, getter)
        except Exception as exc:
            result.setdefault("_errores", []).append(f"{host} directorio: {str(exc)[:50]}")
            result[host] = 0
            continue
        picked = 0
        for account in accounts:
            if picked >= max_accounts:
                break
            reject, hits, spanish, followers = mp.classify(account)
            if reject or hits < 1:
                continue
            picked += 1
            try:
                found += record(db, host, getter(f"https://{host}/api/v1/accounts/{account.get('id')}/statuses",
                                                 {"limit": 5, "exclude_replies": "true", "exclude_reblogs": "true"}), today)
            except Exception:
                continue
            sleep(PAUSE)
        result[host] = found
    return result


def mine(db, hosts=HOSTS, pages=3, tags_per_host=8, tag_pages=3, today=None, sleep=time.sleep, getter=_get):
    """Lee la linea publica local de cada instancia y unas pocas etiquetas (rotan por dia). Un fallo de una instancia no para a las demas. Devuelve {host: nuevos}."""
    today = today or datetime.date.today()
    ensure(db)
    result = {}
    for index, host in enumerate(hosts):
        found = 0
        start = (today.toordinal() + index) * tags_per_host
        wanted = [None] + [TAGS[(start + i) % len(TAGS)] for i in range(tags_per_host)]
        for tag in wanted:
            try:
                found += record(db, host, fetch_timeline(host, tag, pages if tag is None else tag_pages, sleep, getter), today)
            except Exception as exc:       # 422 = linea temporal publica cerrada; tiempo agotado; instancia caida
                result.setdefault("_errores", []).append(f"{host}{'#' + tag if tag else ''}: {str(exc)[:50]}")
                if tag is None:
                    break
        result[host] = found
    return result


def pick(db, n, *, exclude_accts=frozenset(), exclude_bare=frozenset(), today=None):
    """Los mejores posts aun sin resolver: mas terminos del nicho, mas recientes; uno por cuenta y sin cuentas de `exclude_accts`. `exclude_bare`: el registro guarda las cuentas
    de otras instancias SIN el host (`ana`, no `ana@masto.es`), asi que se compara tambien el nombre sin host (algun falso positivo con homonimos es preferible a repetir cuenta)."""
    today = today or datetime.date.today()
    ensure(db)
    rows = db.execute("SELECT url, host, acct, text, language, created_at, niche, seen_count FROM remote_posts WHERE status = 'new'").fetchall()
    scored = []
    for url, host, acct, text, language, created_at, niche, seen in rows:
        age = _age_days(created_at, today)
        if age is None or age > MAX_AGE_DAYS or acct in exclude_accts or acct.split("@")[0] in exclude_bare:
            continue
        score = 3 * min(niche, 3) + max(0.0, 4 - age / 2) + (1 if sc.invites_conversation(text) else 0) + min(seen, 3) * 0.2
        scored.append((score, {"url": url, "host": host, "acct": acct, "text": text, "niche": niche, "score": round(score, 2)}))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["url"]))
    out, used = [], set()
    for _, row in scored:
        if row["acct"] in used:
            continue
        used.add(row["acct"])
        out.append(row)
        if len(out) >= n:
            break
    return out


def mark(db, url, status="done"):
    db.execute("UPDATE remote_posts SET status = ? WHERE url = ?", (status, url))
    db.commit()


def stats(db, today=None):
    today = today or datetime.date.today()
    ensure(db)
    total = db.execute("SELECT COUNT(*) FROM remote_posts").fetchone()[0]
    return {"remote_posts": total, "available": len(pick(db, 10_000, today=today)),
            "resolved": db.execute("SELECT COUNT(*) FROM remote_posts WHERE status != 'new'").fetchone()[0],
            "by_host": dict(db.execute("SELECT host, COUNT(*) FROM remote_posts GROUP BY host ORDER BY 2 DESC").fetchall())}


def main(argv=None):
    import json
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    db = mp.connect()
    try:
        ensure(db)
        if argv and argv[0] == "mine":
            pages = int(argv[argv.index("--pages") + 1]) if "--pages" in argv else 3
            print(json.dumps(mine(db, pages=pages), ensure_ascii=False))
            print(json.dumps({"directorio": mine_directory(db)}, ensure_ascii=False))
        elif argv and argv[0] == "top":
            n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 20
            for row in pick(db, n):
                print(f"{row['score']:>5} {row['acct']:<34} {row['text'][:90]!r}")
        print(json.dumps(stats(db), ensure_ascii=False))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
