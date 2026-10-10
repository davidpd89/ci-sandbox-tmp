"""
Herramienta unica para el dia a dia de Mastodon - reescrita el 24/09 para
usar la API REST oficial (docs.joinmastodon.org) en vez de automatizar un
navegador via CDP. A peticion explicita de David ("de mastodon yo creo que
tiene API tambien, no?"): mastodon.social tiene una API publica pensada
exactamente para esto (igual que Bluesky/AT Protocol), asi que este modulo
sigue ahora el mismo patron que bluesky_interact.py - nada de Playwright,
solo HTTP/JSON con un token de aplicacion.

Esto elimina de raiz TODA la clase de bugs reales encontrados el 24/09 en la
version por navegador (mencion partida a mitad por un click mal posicionado,
boton "Mas"/"Responder" cogiendo el del post equivocado en un hilo, deteccion
de "ya comentado" confundiendo antepasados con respuestas reales) - la API
da directamente los IDs correctos (in_reply_to_id, context con ancestors/
descendants) sin necesidad de adivinar nada del DOM. Tambien es mucho mas
barato en tokens/tiempo: una llamada HTTP en vez de abrir Edge, navegar y
esperar renders.

Autenticacion: token de aplicacion en `tools/mastodon_tokens.json` (no se
versiona, ver .gitignore) - generado una vez el 24/09 desde
Preferencias > Desarrollo > Nueva aplicacion en mastodon.social, con permisos
read+write+follow. Si hace falta regenerarlo: misma pantalla, "Regenerar
token de acceso".

Uso:
    python tools/mastodon_interact.py health
    python tools/mastodon_interact.py notifications
    python tools/mastodon_interact.py hashtag <tag>
    python tools/mastodon_interact.py search "consulta" [accounts|hashtags|statuses]
    python tools/mastodon_interact.py local
    python tools/mastodon_interact.py tag-info <tag>
    python tools/mastodon_interact.py followed-tags
    python tools/mastodon_interact.py follow-tag <tag>
    python tools/mastodon_interact.py lists
    python tools/mastodon_interact.py list <list_id>
    python tools/mastodon_interact.py featured-tags
    python tools/mastodon_interact.py tag-suggestions
    python tools/mastodon_interact.py scheduled
    python tools/mastodon_interact.py profile [handle]
    python tools/mastodon_interact.py reply <url_o_id> "texto"
    python tools/mastodon_interact.py follow <handle>
    python tools/mastodon_interact.py favourite <url_o_id>
    python tools/mastodon_interact.py boost <url_o_id>
    python tools/mastodon_interact.py delete <url_o_id>
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
from urllib.parse import quote as urlquote, urlsplit

import requests
from http_retry import get_with_retry

sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scan_common import AlreadyCommented, check_length  # compartido entre redes
import mastodon_budget as _budget  # cupo de peticiones compartido entre procesos (06/10)
from x_interact import _check_spanish_orthography  # reutilizado, no duplicado

BASE = "https://mastodon.social"
API = f"{BASE}/api/v1"
API_V2 = f"{BASE}/api/v2"
<<<<<<< HEAD
HANDLE = "autorademodiaz"
=======
HANDLE = "davidportodiaz"
>>>>>>> origin/research/public-reuse-parent

_TOKENS_PATH = os.path.join(os.path.dirname(__file__), "mastodon_tokens.json")


class BotWarningDetected(Exception):
    pass


class WrongAccountActive(Exception):
    pass


class OwnPublicationDisabled(RuntimeError):
    pass


class MastodonAPIError(RuntimeError):
    def __init__(self, method, status_code, message, *, retry_after=None):
        super().__init__(f"{method} falló ({status_code}): {message}")
        self.method = method
        self.status_code = int(status_code)
        self.retry_after = retry_after


class MastodonRateLimitExceeded(MastodonAPIError):
    pass


_IDENTITY_VERIFIED = False
_REQUEST_HOOK = None
_RATE_LIMIT = {"remaining": None, "limit": None, "reset": None}
_PRIORITY = "normal"           # margen de cupo que deja este proceso a los demas: scan (90) < normal (25) < priority (3); ver mastodon_budget.py


def set_priority(name):
    """Prioridad de este proceso frente al cupo compartido (los scans usan 'scan' y dejan siempre margen a ejecutores y herramientas). Devuelve la anterior."""
    global _PRIORITY
    previous = _PRIORITY
    _PRIORITY = name if name in _budget.RESERVES else "normal"
    return previous


def _wait_for_budget():
    _budget.wait_for_budget(_PRIORITY, own=_RATE_LIMIT)


def _set_request_hook(hook):
    """Gancho temporal para contabilizar cada GET paginado en los scans."""
    global _REQUEST_HOOK
    previous = _REQUEST_HOOK
    _REQUEST_HOOK = hook
    return previous


def _record_rate_limit(response):
    """Guarda la cuota REAL que devuelve mastodon.social en cada respuesta
    (cabeceras X-RateLimit-*, 300 peticiones/5min de serie) - a partir del
    29/09 el scan usa esto para pausar antes de agotarla, en vez de solo
    reaccionar a un 429 ya disparado."""
    headers = getattr(response, "headers", None) or {}
    remaining = headers.get("x-ratelimit-remaining")
    limit = headers.get("x-ratelimit-limit")
    reset = headers.get("x-ratelimit-reset")
    if remaining is not None:
        try:
            _RATE_LIMIT["remaining"] = int(remaining)
        except ValueError:
            pass
    if limit is not None:
        try:
            _RATE_LIMIT["limit"] = int(limit)
        except ValueError:
            pass
    if reset:
        try:
            _RATE_LIMIT["reset"] = dt.datetime.fromisoformat(reset.replace("Z", "+00:00"))
        except ValueError:
            pass
    _budget.publish(_RATE_LIMIT["remaining"], _RATE_LIMIT["limit"], _RATE_LIMIT["reset"])


def rate_limit_snapshot():
    """Copia de la ultima cuota real conocida - None en los tres campos si
    todavia no se ha hecho ninguna peticion en este proceso."""
    return dict(_RATE_LIMIT)


def _load_token():
    if not os.path.exists(_TOKENS_PATH):
        raise RuntimeError(
            f"falta {_TOKENS_PATH} - crear una aplicacion en "
            f"{BASE}/settings/applications/new (scopes read+write+follow) y "
            "guardar el 'Tu token de acceso' ahi (ver docstring del modulo)."
        )
    with open(_TOKENS_PATH, encoding="utf-8") as f:
        return json.load(f)["access_token"]


_TOKEN = None


def _headers():
    global _TOKEN
    if _TOKEN is None:
<<<<<<< HEAD
        _TOKEN = _load_token()
=======
        value = _load_token()
        _TOKEN = value
>>>>>>> origin/research/public-reuse-parent
    return {"Authorization": f"Bearer {_TOKEN}"}


def _assert_expected_account():
    """Toda escritura debe confirmar primero la cuenta exacta del token."""
    global _IDENTITY_VERIFIED
    if _IDENTITY_VERIFIED:
        return
    try:
        me = _get("accounts/verify_credentials")
    except Exception as exc:
        raise WrongAccountActive(
            "no se pudo verificar la identidad del token Mastodon; "
            "parar antes de escribir"
        ) from exc
    if not isinstance(me, dict):
        raise WrongAccountActive(
            "Mastodon devolvió identidad no estructurada; parar antes de escribir"
        )
    username = str(me.get("username") or "").casefold()
    acct = str(me.get("acct") or "").casefold()
    account_url = str(me.get("url") or "")
    parsed = urlsplit(account_url) if account_url else None
    if (
        username != HANDLE.casefold()
        or acct not in {HANDLE.casefold(), f"{HANDLE}@mastodon.social".casefold()}
        or not parsed
        or parsed.scheme != "https"
        or parsed.hostname != "mastodon.social"
    ):
        raise WrongAccountActive(
            f"token Mastodon no pertenece a @{HANDLE}@mastodon.social; "
            "parar antes de escribir"
        )
    _IDENTITY_VERIFIED = True


def _encoded_segment(value, label):
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} vacío")
    return urlquote(text, safe="")


def _refuse_own_publication():
    raise OwnPublicationDisabled(
        "Publicación propia Mastodon desactivada en scripts: "
        "desde 28/09/2026 se publica/programa manualmente en la interfaz nativa."
    )


def _response_error(method, path, response):
    if response.status_code == 429:
        raise MastodonRateLimitExceeded(
            f"{method} {path}", 429, (response.text or "")[:300],
            retry_after=(getattr(response, "headers", {}) or {}).get("Retry-After"),
        )
    if not 200 <= response.status_code < 300:
        raise MastodonAPIError(
            f"{method} {path}", response.status_code,
            (response.text or "")[:300],
            retry_after=(getattr(response, "headers", {}) or {}).get("Retry-After"),
        )


def _get_response(url, params=None):
    if _REQUEST_HOOK is not None:
        _REQUEST_HOOK(url)
    _wait_for_budget()
    response = get_with_retry(url, params=params or {}, headers=_headers(), timeout=20)
    _record_rate_limit(response)
    _response_error("GET", urlsplit(url).path, response)
    return response


def _get(path, params=None):
    response = _get_response(f"{API}/{path}", params)
    return response.json()


def _post(path, data=None, extra_headers=None):
    _assert_expected_account()
    headers = _headers()
    if extra_headers:
        headers.update(extra_headers)
    _wait_for_budget()
<<<<<<< HEAD
    response = requests.post(
        f"{API}/{path}", json=data or {}, headers=headers, timeout=20
    )
    _record_rate_limit(response)
    _response_error("POST", path, response)
    return response.json()
=======
    # Solo la escritura de status (no follows/favourites ni comprobaciones
    # de cuenta) necesita un ACK inequívoco antes de poderse repetir.
    is_status_write = path == "statuses"
    try:
        response = requests.post(
            f"{API}/{path}", json=data or {}, headers=headers, timeout=20
        )
    except Exception as exc:
        if is_status_write:
            import exec_common as ec
            if ec.uncertain_transport_error(exc):
                raise ec.WriteOutcomeUnknown("mastodon:POST_sin_respuesta") from exc
        raise
    try:
        _record_rate_limit(response)
    except Exception as exc:
        if is_status_write:
            # Una excepción del registro LOCAL de cuota después de POST
            # no prueba que el servidor haya rechazado la publicación.
            # Conservar el rechazo 4xx explícito si está presente.
            if 400 <= response.status_code < 500:
                _response_error("POST", path, response)
            import exec_common as ec
            raise ec.WriteOutcomeUnknown(
                "mastodon:POST_cuota_no_registrada", status_code=response.status_code
            ) from exc
        raise
    try:
        _response_error("POST", path, response)
    except MastodonAPIError as exc:
        if is_status_write and 500 <= exc.status_code < 600:
            import exec_common as ec
            raise ec.WriteOutcomeUnknown("mastodon:POST_5xx_sin_confirmacion", status_code=exc.status_code) from exc
        raise
    try:
        return response.json()
    except ValueError as exc:
        if is_status_write:
            import exec_common as ec
            raise ec.WriteOutcomeUnknown("mastodon:POST_respuesta_no_json") from exc
        raise
>>>>>>> origin/research/public-reuse-parent


def _get_v2(path, params=None):
    response = _get_response(f"{API_V2}/{path}", params)
    return response.json()


_NEXT_LINK_RE = re.compile(r'<([^>]+)>\s*;\s*rel="?next"?', re.IGNORECASE)


def _next_link(response, *, api_prefix):
    headers = getattr(response, "headers", {}) or {}
    link_header = headers.get("Link") or headers.get("link") or ""
    match = _NEXT_LINK_RE.search(str(link_header))
    if not match:
        return None
    url = urlsplit(match.group(1))
    base = urlsplit(BASE)
    if (
        url.scheme != "https"
        or url.hostname != base.hostname
        or url.port is not None
        or not url.path.startswith(api_prefix + "/")
        or url.username
        or url.password
    ):
        raise RuntimeError("Mastodon devolvió un Link next fuera de la API local")
    return match.group(1)


def _get_paginated(path, params=None, *, max_pages=3, max_items=None):
    """Lee páginas siguientes del Link oficial, sin confiar en IDs remotos."""
    pages = max(1, int(max_pages))
    url = f"{API}/{path}"
    query = dict(params or {})
    rows = []
    seen_urls = set()
    for _ in range(pages):
        if url in seen_urls:
            raise RuntimeError("Paginación Mastodon repitió una URL")
        seen_urls.add(url)
        response = _get_response(url, query)
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError(f"GET {path} paginado no devolvió una lista")
        rows.extend(payload)
        if max_items is not None and len(rows) >= int(max_items):
            return rows[:int(max_items)]
        next_url = _next_link(response, api_prefix="/api/v1")
        if not next_url:
            break
        url, query = next_url, {}
    return rows


def _search_statuses_pages(query, *, limit=40, max_pages=3, resolve=False):
    """Paginación de statuses via search v2, tolera backends de índice ausentes."""
    params = {"q": query, "type": "statuses", "limit": max(1, min(int(limit), 40))}
    if resolve:
        params["resolve"] = "true"
    rows = []
    url = f"{API_V2}/search"
    query_params = params
    seen_urls = set()
    for _ in range(max(1, int(max_pages))):
        if url in seen_urls:
            raise RuntimeError("Paginación search Mastodon repitió una URL")
        seen_urls.add(url)
        response = _get_response(url, query_params)
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("statuses"), list):
            raise RuntimeError("Search Mastodon no devolvió statuses[]")
        page = payload["statuses"]
        rows.extend(page)
        if not page:
            break
        next_url = _next_link(response, api_prefix="/api/v2")
        if not next_url:
            break
        url, query_params = next_url, {}
    return rows


def _plain_text(content):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", content or "")).split())


def _delete(path):
    _assert_expected_account()
    r = requests.delete(f"{API}/{path}", headers=_headers(), timeout=15)
    _record_rate_limit(r)
    if r.status_code != 200:
        raise RuntimeError(f"DELETE {path} fallo ({r.status_code}): {r.text[:300]}")
    return r.json()


def search(query, kind=None, limit=20, *, resolve=False, following=False,
           account_id=None, offset=None):
    """Buscar cuentas, hashtags o statuses mediante /api/v2/search."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Mastodon search exige q no vacio")
    if kind not in (None, "accounts", "hashtags", "statuses"):
        raise ValueError("kind debe ser accounts, hashtags, statuses o None")
    params = {"q": query.strip(), "limit": max(1, min(int(limit), 40))}
    if kind:
        params["type"] = kind
    if resolve:
        params["resolve"] = "true"
    if following:
        params["following"] = "true"
    if account_id:
        params["account_id"] = str(account_id)
    if offset is not None:
        params["offset"] = max(0, int(offset))
    return _get_v2("search", params)


def search_statuses(query, *, limit=40, max_pages=3):
    return _search_statuses_pages(query, limit=limit, max_pages=max_pages)


def search_accounts_pages(query, *, limit=40, max_pages=2):
<<<<<<< HEAD
    rows = []
    page_size = max(1, min(int(limit), 80))
    for page in range(max(1, int(max_pages))):
        data = search(query, "accounts", page_size, offset=page * page_size)
        accounts = data.get("accounts") or []
        rows.extend(accounts)
        if len(accounts) < page_size:
=======
    """Recorrer resultados v2 sin saltos ni cuentas repetidas.

    /api/v2/search acepta como máximo 40 por tipo; usar 80 como stride
    perdía la mitad de las cuentas aunque el servidor respondiera 40.
    Los IDs son locales a la instancia consultada, no IDs federados.
    """
    rows = []
    page_size = max(1, min(int(limit), 40))
    seen_local_ids = set()
    for page in range(max(1, int(max_pages))):
        data = search(query, "accounts", page_size, offset=page * page_size)
        accounts = data.get("accounts") if isinstance(data, dict) else None
        if not isinstance(accounts, list):
            raise RuntimeError("Search Mastodon no devolvió accounts[]")
        new_count = 0
        for account in accounts:
            raw_id = account.get("id") if isinstance(account, dict) else None
            if (isinstance(raw_id, bool) or not isinstance(raw_id, (str, int))
                    or not str(raw_id).strip()):
                raise RuntimeError("Search Mastodon devolvió una cuenta sin ID local válido")
            local_id = str(raw_id)
            if local_id in seen_local_ids:
                continue
            seen_local_ids.add(local_id)
            rows.append(account)
            new_count += 1
        if len(accounts) < page_size or new_count == 0:
>>>>>>> origin/research/public-reuse-parent
            break
    return rows


def dump_search(query, kind=None, limit=20, resolve=False):
    data = search(query, kind, limit, resolve=resolve)
    if kind in (None, "accounts"):
        for account in data.get("accounts", []):
            print("--- CUENTA")
            print("@" + account.get("acct", ""))
            print(account.get("display_name", ""))
            print(_plain_text(account.get("note", ""))[:300])
    if kind in (None, "hashtags"):
        for tag in data.get("hashtags", []):
            print("--- HASHTAG")
            print("#" + tag.get("name", ""))
            if tag.get("url"):
                print(tag["url"])
    if kind in (None, "statuses"):
        for status in data.get("statuses", []):
            print("--- STATUS")
            print(status.get("url") or status.get("uri") or status.get("id"))
            print("@" + (status.get("account") or {}).get("acct", ""))
            print(_plain_text(status.get("content", ""))[:400])
    return data


def _status_id(url_or_id):
    """Resolver el ID local de mastodon.social sin reutilizar IDs remotos."""
    value = str(url_or_id).strip()
    if re.fullmatch(r"\d+", value):
        return value
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.port):
        raise ValueError("status debe ser ID local o URL HTTPS valida")
    host = parsed.hostname.casefold()
    local_host = urlsplit(BASE).hostname.casefold()
    local = re.fullmatch(r"/@[^/]+/(\d+)/?", parsed.path)
    if host == local_host and local and not parsed.query and not parsed.fragment:
        return local.group(1)
    result = search(value, "statuses", limit=5, resolve=True)
    normalized = value.rstrip("/")
    matches = [
        st for st in result.get("statuses", [])
        if str(st.get("url") or "").rstrip("/") == normalized
        or str(st.get("uri") or "").rstrip("/") == normalized
    ]
    if len(matches) != 1 or not str(matches[0].get("id", "")).isdigit():
        raise RuntimeError(
            "No se pudo resolver de forma univoca la URL remota a un status local"
        )
    return str(matches[0]["id"])



def _check_length(text):
    check_length(text, 500)



_INSTANCE_CACHE = None


def instance_info():
    global _INSTANCE_CACHE
    if _INSTANCE_CACHE is None:
        data = _get_v2("instance")
        if not isinstance(data, dict) or not isinstance(data.get("configuration"), dict):
            raise RuntimeError("Mastodon no devolvio configuracion de instancia verificable")
        _INSTANCE_CACHE = data
    return _INSTANCE_CACHE



def health():
    global _IDENTITY_VERIFIED
    _IDENTITY_VERIFIED = False
    _assert_expected_account()
    me = _get("accounts/verify_credentials")
    print(
        f"OK: sesión API válida como @{me['acct']}. "
        f"Seguidores: {me['followers_count']} Siguiendo: {me['following_count']} "
        f"Publicaciones: {me['statuses_count']}"
    )
    return me


def profile(handle=None):
    handle = handle or HANDLE
    acct = _get("accounts/lookup", {"acct": handle})
    print(json.dumps(acct, ensure_ascii=False, indent=2)[:2000])
    return acct


def notifications(limit=80, *, max_pages=2, types=None):
    params = {"limit": max(1, min(int(limit), 80))}
    if types:
        params["types[]"] = list(types)
    return _get_paginated(
        "notifications", params, max_pages=max_pages,
    )


def get_notifications_data(*, max_pages=2):
    """Notificaciones CON contenido (respuesta/favorito/boost sobre algo
    nuestro) - devuelve tuplas (url, texto, handle_autor). Mucho mas simple
    que la version por navegador: la API ya da el status completo y el
    account.acct del autor, no hace falta adivinar nada del DOM."""
    out = []
    for n in notifications(max_pages=max_pages):
        status = n.get("status")
        if not status:
            continue
        author = n["account"]["acct"]
        url = status.get("url") or f"{BASE}/@{status['account']['acct']}/{status['id']}"
        text = _plain_text(status.get("content", ""))
        out.append((url, text, author, n["type"]))
    return out


def get_follow_notifications_data(*, max_pages=2):
    """Notificaciones de tipo 'follow' (sin contenido, "X te siguio") -
    antes invisibles para el scan por navegador (ver ESTADO.md 24/09), la
    API las da directo sin ningun truco de DOM."""
    handles = []
    for n in notifications(max_pages=max_pages):
        if n["type"] == "follow":
            acct = n["account"]["acct"]
            if acct not in handles:
                handles.append(acct)
    return handles


def get_hashtag_statuses(tag, limit=40, *, any_tags=None, all_tags=None,
                         none_tags=None, local=False, remote=False,
                         only_media=False, max_pages=1):
    tag = str(tag).lstrip("#")
    if not tag:
        raise ValueError("hashtag vacio")
    params = {"limit": max(1, min(int(limit), 40))}
    if any_tags:
        params["any[]"] = [str(x).lstrip("#") for x in any_tags]
    if all_tags:
        params["all[]"] = [str(x).lstrip("#") for x in all_tags]
    if none_tags:
        params["none[]"] = [str(x).lstrip("#") for x in none_tags]
    if local:
        params["local"] = "true"
    if remote:
        params["remote"] = "true"
    if only_media:
        params["only_media"] = "true"
    return _get_paginated(
        f"timelines/tag/{_encoded_segment(tag, 'hashtag')}",
        params,
        max_pages=max_pages,
    )


def hashtag_page(tag, *, limit=40, max_id=None, min_id=None):
    """Una pagina del timeline de un hashtag con cursores explicitos (05/10): devuelve (estados, max_id_siguiente). Permite recorrer HACIA ATRAS
    (`max_id` = el mas antiguo ya leido) en lugar de releer cada ronda la cabeza del timeline (los mismos ~120 estados, ya favoriteados)."""
    tag = str(tag).lstrip("#")
    if not tag:
        raise ValueError("hashtag vacio")
    params = {"limit": max(1, min(int(limit), 40))}
    if max_id:
        params["max_id"] = str(max_id)
    if min_id:
        params["min_id"] = str(min_id)
    response = _get_response(f"{API}/timelines/tag/{_encoded_segment(tag, 'hashtag')}", params)
    rows = response.json()
    if not isinstance(rows, list):
        raise RuntimeError("timeline de hashtag no devolvio una lista")
    next_url = _next_link(response, api_prefix="/api/v1")
    match = re.search(r"max_id=(\d+)", next_url or "")
    return rows, (match.group(1) if match else None)


def get_hashtag_data(tag, limit=15, **filters):
    out = []
    for status in get_hashtag_statuses(tag, limit, **filters):
        url = status.get("url") or f"{BASE}/@{status['account']['acct']}/{status['id']}"
        out.append((url, _plain_text(status.get("content", ""))))
    return out


def hashtag(tag, **filters):
    for url, text in get_hashtag_data(tag, **filters):
        print("---")
        print("URL:", url)
        print(text[:250])


def public_timeline(limit=40, *, local=False, remote=False, only_media=False,
                    max_pages=1):
    params = {"limit": max(1, min(int(limit), 40))}
    if local:
        params["local"] = "true"
    if remote:
        params["remote"] = "true"
    if only_media:
        params["only_media"] = "true"
    return _get_paginated("timelines/public", params, max_pages=max_pages)


def home_timeline(limit=40, *, max_pages=1):
    return _get_paginated(
        "timelines/home",
        {"limit": max(1, min(int(limit), 40))},
        max_pages=max_pages,
    )




def trending_tags(limit=20, offset=0):
    return _get(
        "trends/tags",
        {"limit": max(1, min(int(limit), 20)), "offset": max(0, int(offset))},
    )


def trending_statuses(limit=20, offset=0):
    return _get(
        "trends/statuses",
        {"limit": max(1, min(int(limit), 40)), "offset": max(0, int(offset))},
    )


def trending_links(limit=20, offset=0):
    return _get(
        "trends/links",
        {"limit": max(1, min(int(limit), 20)), "offset": max(0, int(offset))},
    )


def supports_status_quotes():
    """Mastodon quote-engager endpoint se añadió con API 7 / Mastodon 4.5."""
    version = str((instance_info() or {}).get("version") or "")
    match = re.match(r"\s*(\d+)\.(\d+)", version)
    return bool(match and (int(match.group(1)), int(match.group(2))) >= (4, 5))


def link_timeline(url, limit=40, *, max_pages=1):
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("link timeline requiere URL HTTPS")
    return _get_paginated(
        "timelines/link",
        {"url": url, "limit": max(1, min(int(limit), 40))},
        max_pages=max_pages,
    )


def account_statuses(account_id, limit=40, *, max_pages=2, tagged=None):
    params = {
        "limit": max(1, min(int(limit), 40)),
        "exclude_replies": "true",
        "exclude_reblogs": "true",
    }
    if tagged:
        params["tagged"] = str(tagged).lstrip("#")
    return _get_paginated(
        f"accounts/{_encoded_segment(account_id, 'account_id')}/statuses",
        params,
        max_pages=max_pages,
    )


def account_neighbors(account_id, kind, *, limit=40, max_pages=1):
    if kind not in {"followers", "following"}:
        raise ValueError("kind debe ser followers o following")
    return _get_paginated(
        f"accounts/{_encoded_segment(account_id, 'account_id')}/{kind}",
        {"limit": max(1, min(int(limit), 80))},
        max_pages=max_pages,
    )


def status_context(status_id):
    return _get(f"statuses/{_encoded_segment(status_id, 'status_id')}/context")


def status_engagers(status_id, kind, *, limit=80, max_pages=1):
    endpoint = {
        "favourites": "favourited_by",
        "boosts": "reblogged_by",
        "quotes": "quotes",
    }.get(kind)
    if endpoint is None:
        raise ValueError("kind debe ser favourites, boosts o quotes")
    return _get_paginated(
        f"statuses/{_encoded_segment(status_id, 'status_id')}/{endpoint}",
        {"limit": max(1, min(int(limit), 80 if kind != "quotes" else 40))},
        max_pages=max_pages,
    )



def tag_info(tag):
    name = str(tag).lstrip("#")
    if not name:
        raise ValueError("hashtag vacio")
    return _get(f"tags/{_encoded_segment(name, 'hashtag')}")


def followed_tags(limit=100):
    return _get("followed_tags", {"limit": max(1, min(int(limit), 200))})


def follow_tag(tag):
    name = str(tag).lstrip("#")
    current = tag_info(name)
    if current.get("following"):
        print(f"#{name}: ya se seguia")
        return "already"
    result = _post(f"tags/{_encoded_segment(name, 'hashtag')}/follow")
    if not isinstance(result, dict) or not result.get("following"):
        raise RuntimeError("Mastodon no confirmo following=true para el hashtag")
    print(f"#{name}: hashtag seguido")
    return "followed"


def lists():
    return _get("lists")


def list_timeline(list_id, limit=20):
    return _get(
        f"timelines/list/{_encoded_segment(list_id, 'list_id')}",
        {"limit": max(1, min(int(limit), 40))},
    )



def featured_tags():
    return _get("featured_tags")


def featured_tag_suggestions():
    return _get("featured_tags/suggestions")


def scheduled_statuses(limit=20):
    return _get("scheduled_statuses", {"limit": max(1, min(int(limit), 40))})



def _already_commented(status_id):
    """Comprobar solo respuestas DIRECTAS nuestras al status objetivo.

    /context devuelve todo el subárbol de descendants, también replies a
    otros lectores. Contar cualquier descendiente propio producía falsos
    positivos y bloqueaba una respuesta legítima al padre.
    """
    ctx = _get(f"statuses/{status_id}/context")
    descendants = ctx.get("descendants")
    if not isinstance(descendants, list):
        raise RuntimeError("Mastodon no devolvió descendants verificables")
    for descendant in descendants:
        account = descendant.get("account") or {}
        if (str(account.get("username") or "").casefold() == HANDLE.casefold()
                and str(descendant.get("in_reply_to_id") or "") == str(status_id)):
            return True
    return False


def _status_idempotency_key(payload):
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
<<<<<<< HEAD
    return "autorademo-" + hashlib.sha256(encoded).hexdigest()[:48]


def _create_status(body, semantic_key):
    """Único creador de status usado operativamente: replies editoriales."""
=======
    return "davidporto-" + hashlib.sha256(encoded).hexdigest()[:48]


def _create_status(body, semantic_key):
    """Crea un estado con idempotencia; la frontera HTTP clasifica el ACK.

    La preparación de sesión/cuenta se realiza antes del POST y, si falla,
    NO se marca como escritura incierta.
    """
    import exec_common as ec

>>>>>>> origin/research/public-reuse-parent
    result = _post(
        "statuses",
        body,
        {"Idempotency-Key": _status_idempotency_key(semantic_key)},
    )
    if not isinstance(result, dict) or not result.get("id"):
<<<<<<< HEAD
        raise RuntimeError(
            "Mastodon no confirmó ID del status; revisar antes de reintentar"
        )
=======
        raise ec.WriteOutcomeUnknown("mastodon:status_sin_id")
>>>>>>> origin/research/public-reuse-parent
    return result


def publish_own(text, image_path=None, alt=""):
    """Publicacion PROPIA autorizada por David el 06/10 («cada dia un script revise las carpetas de cada red y publique lo que corresponda»). Unico punto de entrada, usado por
    `content_publisher.py`: sube la imagen con su ALT (`/api/v2/media`) y crea el estado publico en espanol. `post()` sigue desactivado para cualquier otro script."""
    _check_spanish_orthography(text)
    _check_length(text)
    body = {"status": text, "visibility": "public", "language": "es"}
    if image_path:
        if not isinstance(alt, str) or not alt.strip():
            raise ValueError("Una imagen de Mastodon exige ALT no vacio")
        _assert_expected_account()
        with open(image_path, "rb") as stream:
            response = requests.post(f"{API_V2}/media", headers=_headers(), files={"file": (os.path.basename(image_path), stream)}, data={"description": alt.strip()}, timeout=60)
        _record_rate_limit(response)
        _response_error("POST", "media", response)
        media = response.json()
        if not isinstance(media, dict) or not media.get("id"):
            raise RuntimeError("Mastodon no confirmo la subida de la imagen")
        body["media_ids"] = [media["id"]]
    result = _create_status(body, semantic_key={"publish_own": text, "image": os.path.basename(image_path or "")})
    print(f"Publicado: {result.get('url') or result['id']}")
    return result


def reply_to(url_or_id, text):
    """A diferencia de la version por navegador, la API NO precarga ninguna
    mencion en el cuadro - hay que incluirla nosotros en `text` si se quiere
    (normalmente ya viene incluida en el texto que decide Claude, con
    "@handle " al principio, igual que en X/Bluesky). in_reply_to_id fija el
    padre exacto sin ambiguedad posible."""
    _check_spanish_orthography(text)
    status_id = _status_id(url_or_id)
    if _already_commented(status_id):
        raise AlreadyCommented(f"Ya hay una respuesta nuestra a {url_or_id} - no se envia otra.")
    parent = _get(f"statuses/{status_id}")
    visibility = parent.get("visibility")
    if visibility not in ("public", "unlisted"):
        raise RuntimeError(
            "Respuesta automática solo permitida a posts public/unlisted; "
            f"visibilidad recibida={visibility!r}"
        )
    mention = f"@{parent['account']['acct']} "
    full_text = text if text.lstrip().startswith("@") else mention + text
    _check_length(full_text)
    result = _create_status(
        {"status": full_text, "in_reply_to_id": status_id,
         "visibility": visibility, "language": "es"},
        semantic_key={
            "reply_to": status_id,
            "status": full_text,
            "visibility": visibility,
        },
    )
    print(f"Respuesta publicada: {BASE}/@{HANDLE}/{result['id']}")
    return result


def post(*_args, **_kwargs):
    _refuse_own_publication()


def quote(*_args, **_kwargs):
    _refuse_own_publication()


def poll(*_args, **_kwargs):
    _refuse_own_publication()


def delete_post(url_or_id):
    status_id = _status_id(url_or_id)
    _delete(f"statuses/{status_id}")
    print("Publicacion eliminada.")


# Precarga en lote (05/10, como en Bluesky): cada favorito hacia 2 peticiones (GET del estado + POST) y cada follow 3 (lookup + relationships + POST), y las lecturas
# comparten con las escrituras el cupo de 300 peticiones/5 min de mastodon.social. `GET /statuses?id[]=` (hasta 20) y `GET /accounts/relationships?id[]=` (hasta 40)
# traen el estado de muchos objetivos en una peticion; cada accion queda en 1 peticion de escritura. Caduca a los 30 min y se consume al usarlo; un fallo no rompe nada.
import time as _time

_PREFETCH = {}
PREFETCH_TTL = 1800


def prefetch(status_ids=(), account_ids=()):
    now = _time.time()
    status_ids = [str(i) for i in dict.fromkeys(status_ids) if i]
    account_ids = [str(i) for i in dict.fromkeys(account_ids) if i]
    for start in range(0, len(status_ids), 20):
        chunk = status_ids[start:start + 20]
        try:
            rows = _get("statuses", {"id[]": chunk})
        except MastodonRateLimitExceeded:
            raise
        except Exception:
            continue
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and row.get("id") is not None:
                _PREFETCH[("status", str(row["id"]))] = {"favourited": bool(row.get("favourited")), "reblogged": bool(row.get("reblogged")), "t": now}
    for start in range(0, len(account_ids), 40):
        chunk = account_ids[start:start + 40]
        try:
            rows = _get("accounts/relationships", {"id[]": chunk})
        except MastodonRateLimitExceeded:
            raise
        except Exception:
            continue
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and row.get("id") is not None:
                _PREFETCH[("account", str(row["id"]))] = {"following": bool(row.get("following")), "requested": bool(row.get("requested")), "t": now}


def _prefetched(key):
    entry = _PREFETCH.pop(key, None)
    if entry and _time.time() - entry["t"] <= PREFETCH_TTL:
        return entry
    return None


def _resolve_account_id(handle):
    acct = _get("accounts/lookup", {"acct": handle.lstrip("@")})
    return acct["id"]


def follow(handle, account_id=None):
    """Seguir solo si es una relación nueva y devolver estado explícito. Con `account_id` (lo trae el plan) y la relacion precargada no hace
    ninguna lectura: solo el POST."""
    handle = handle.lstrip("@")
    cached = _prefetched(("account", str(account_id))) if account_id else None
    if cached is not None:
        if cached["following"] or cached["requested"]:
            print(f"{handle}: ya se seguia")
            return "already"
    else:
        account_id = account_id or _resolve_account_id(handle)
        rels = _get("accounts/relationships", {"id[]": account_id})
        if not isinstance(rels, list) or len(rels) != 1:
            raise RuntimeError("No se pudo verificar la relación antes de follow")
        if rels[0].get("following"):
            print(f"{handle}: ya se seguia")
            return "already"
    result = _post(f"accounts/{account_id}/follow")
    if not isinstance(result, dict) or not result.get("following"):
        raise RuntimeError("Mastodon no confirmó following=true; revisar antes de reintentar")
    print(f"Follow aplicado a @{handle}.")
    return "followed"


def patient(call, *, waits=3, sleep=None, log=print, priority="priority"):
    """Ejecuta `call()` y, si Mastodon contesta 429 (el cupo de 300 peticiones/5 min lo comparten los scans y las escrituras), espera a que la ventana se renueve y reintenta hasta `waits`
    veces. Para herramientas sueltas (perfil, bloqueos, limpiezas, informes): un 429 no debe tirar el trabajo, solo esperar."""
    sleep = sleep or _time.sleep
    previous = set_priority(priority)           # una herramienta suelta usa lo que quede del cupo (los scans dejan siempre margen)
    try:
        return _patient_attempts(call, waits, sleep, log)
    finally:
        set_priority(previous)


def _patient_attempts(call, waits, sleep, log):
    for attempt in range(waits + 1):
        try:
            return call()
        except MastodonRateLimitExceeded as exc:
            if attempt >= waits:
                raise
            reset = _RATE_LIMIT.get("reset")
            wait = 60.0
            if reset is not None:
                wait = max(5.0, (reset - dt.datetime.now(dt.timezone.utc)).total_seconds())
            elif exc.retry_after:
                try:
                    wait = float(exc.retry_after)
                except ValueError:
                    pass
            wait = min(wait, 330.0) + 2
            log(f"  429 de Mastodon: espero {wait:.0f} s a que se renueve el cupo y reintento ({attempt + 1}/{waits})")
            sleep(wait)


def unfollow(handle, account_id=None):
    """Dejar de seguir (idempotente): comprueba la relacion antes y despues; devuelve 'unfollowed' o 'already'."""
    handle = handle.lstrip("@")
    account_id = account_id or _resolve_account_id(handle)
    rels = _get("accounts/relationships", {"id[]": account_id})
    if not isinstance(rels, list) or len(rels) != 1:
        raise RuntimeError("No se pudo verificar la relación antes de unfollow")
    if not (rels[0].get("following") or rels[0].get("requested")):
        print(f"{handle}: ya no se seguia")
        return "already"
    result = _post(f"accounts/{account_id}/unfollow")
    if not isinstance(result, dict) or result.get("following") or result.get("requested"):
        raise RuntimeError("Mastodon no confirmó following=false; revisar antes de reintentar")
    print(f"Unfollow aplicado a @{handle}.")
    return "unfollowed"


def favourite(url_or_id):
    """Favorito idempotente, pero distinguir nuevo de ya existente."""
    status_id = _status_id(url_or_id)
    current = _prefetched(("status", str(status_id))) or _get(f"statuses/{status_id}")
    if current.get("favourited"):
        print("Ya estaba marcado como favorito.")
        return "already"
    result = _post(f"statuses/{status_id}/favourite")
    if not isinstance(result, dict) or not result.get("favourited"):
        raise RuntimeError("Mastodon no confirmó favourited=true")
    print("Favorito aplicado.")
    return "favourited"


def boost(url_or_id):
    """Boost idempotente, distinguiendo nuevo de ya existente."""
    status_id = _status_id(url_or_id)
    current = _prefetched(("status", str(status_id))) or _get(f"statuses/{status_id}")
    if current.get("reblogged"):
        print("Ya estaba impulsado.")
        return "already"
    result = _post(f"statuses/{status_id}/reblog")
    if not isinstance(result, dict) or not result.get("reblogged"):
        raise RuntimeError("Mastodon no confirmó reblogged=true")
    print("Boost aplicado.")
    return "boosted"


def unboost(url_or_id):
    """Retira un boost propio (29/09, limpieza TTL de boosts - mismo
    patron que unrepost() en X y delete_own_record() en Bluesky: el impacto
    a corto plazo no exige que el boost quede fijado para siempre en el
    perfil). Idempotente: si ya no estaba impulsado, no falla."""
    status_id = _status_id(url_or_id)
    current = _get(f"statuses/{status_id}")
    if not current.get("reblogged"):
        print("Ya no estaba impulsado.")
        return "already"
    result = _post(f"statuses/{status_id}/unreblog")
    if not isinstance(result, dict) or result.get("reblogged"):
        raise RuntimeError("Mastodon no confirmó reblogged=false")
    print("Boost retirado.")
    return "unboosted"


def _dispatch():
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "health":
        health()
    elif cmd == "instance":
        data = instance_info()
        print(json.dumps({
            "version": data.get("version"),
            "configuration": data.get("configuration", {}),
        }, ensure_ascii=False, indent=2)[:12000])
    elif cmd == "notifications":
        for url, text, author, typ in get_notifications_data():
            print("---", typ, "por", author)
            print("URL:", url)
            print(text[:250])
        print("\nFollows sin contenido:", get_follow_notifications_data())
    elif cmd == "hashtag":
        hashtag(sys.argv[2])
    elif cmd == "search":
        dump_search(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "local":
        for status in public_timeline(local=True):
            print(status.get("url") or status.get("uri"))
            print(_plain_text(status.get("content", ""))[:300])
    elif cmd == "trending-tags":
        print(json.dumps(trending_tags(), ensure_ascii=False, indent=2))
    elif cmd == "tag-info":
        print(json.dumps(tag_info(sys.argv[2]), ensure_ascii=False, indent=2))
    elif cmd == "followed-tags":
        print(json.dumps(followed_tags(), ensure_ascii=False, indent=2))
    elif cmd == "follow-tag":
        follow_tag(sys.argv[2])
    elif cmd == "lists":
        print(json.dumps(lists(), ensure_ascii=False, indent=2))
    elif cmd == "list":
        for status in list_timeline(sys.argv[2]):
            print(status.get("url") or status.get("uri"))
            print(_plain_text(status.get("content", ""))[:300])
    elif cmd == "featured-tags":
        print(json.dumps(featured_tags(), ensure_ascii=False, indent=2))
    elif cmd == "tag-suggestions":
        print(json.dumps(featured_tag_suggestions(), ensure_ascii=False, indent=2))
    elif cmd == "scheduled":
        print(json.dumps(scheduled_statuses(), ensure_ascii=False, indent=2)[:8000])
    elif cmd == "profile":
        profile(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "reply":
        reply_to(sys.argv[2], sys.argv[3])
    elif cmd == "follow":
        follow(sys.argv[2])
    elif cmd == "favourite":
        favourite(sys.argv[2])
    elif cmd == "boost":
        boost(sys.argv[2])
    elif cmd == "unboost":
        unboost(sys.argv[2])
    elif cmd == "delete":
        delete_post(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    _dispatch()
