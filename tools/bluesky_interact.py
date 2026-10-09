"""Herramienta unica para el dia a dia de Bluesky - hermana de x_interact.py y
threads_interact.py, pero con una diferencia de fondo a proposito: Bluesky
(AT Protocol) tiene una API publica y abierta pensada exactamente para esto,
asi que en vez de automatizar un navegador via CDP (fragil, con deteccion de
bot como en X) esto habla HTTP/JSON directo con el protocolo. Nada de
Playwright ni de perfil de Edge aqui.

Autenticacion: variables BLUESKY_HANDLE y BLUESKY_APP_PASSWORD en el .env de
la raiz del repo. BLUESKY_APP_PASSWORD es una "contrasena de aplicacion"
generada en Configuracion > Privacidad y seguridad > Contrasenas de
aplicacion en bsky.app - NUNCA la contrasena real de la cuenta. Es un secreto revocable separado del login
principal. Ni Claude ni este script piden ni ven la contraseña real de la
cuenta en ningún momento: David genera la contraseña de aplicación y la pega
en el .env él mismo, igual que ya hace con PEXELS_API_KEY/PIXABAY_API_KEY.

Las busquedas y lecturas publicas (search, profile de otra cuenta) funcionan
igual SIN ninguna credencial via public.api.bsky.app - solo las acciones
sobre la cuenta propia (notifications, timeline propio, like, follow, reply,
post) necesitan la sesion autenticada.

Uso:
    python bluesky_interact.py health
    python bluesky_interact.py notifications
    python bluesky_interact.py timeline
    python bluesky_interact.py search "consulta de busqueda" [es|all]
    python bluesky_interact.py tag <hashtag> [es|all]
    python bluesky_interact.py actors "autores fantasia"
    python bluesky_interact.py domain autorademodiaz.com
    python bluesky_interact.py quotes <url_o_uri>
    python bluesky_interact.py likers <url_o_uri>
    python bluesky_interact.py reposters <url_o_uri>
    python bluesky_interact.py profile [handle]
    python bluesky_interact.py thread <url_o_uri>
    python bluesky_interact.py reply <url_o_uri> "texto de la respuesta"
    python bluesky_interact.py like <url_o_uri>
    python bluesky_interact.py repost <url_o_uri>
    python bluesky_interact.py quote <url_o_uri> "texto del comentario"
    python bluesky_interact.py follow <handle>
    python bluesky_interact.py unfollow <handle>
    python bluesky_interact.py post "texto del post" [imagen] [ALT]

La escritura añade facets reales para URLs, hashtags y menciones @handle:
un hashtag deja de ser solo texto y una mención resuelve su DID antes de
publicar. La búsqueda avanzada expone filtros actuales de searchPosts
(tag, author, mentions, domain, url, fechas y sort latest/top).

Cada comando de accion (reply/like/repost/quote/follow/unfollow/post)
ejecuta sobre la cuenta REAL en cuanto se llama - no pide confirmacion el
mismo script. La confirmacion de "esto se va a hacer" pasa siempre antes,
en el chat con David, tal como manda SISTEMA_DIARIO_BLUESKY/REGLAS.md.
"""
import os
import re
import sys
import time
import datetime
import urllib.parse
import requests
from http_retry import get_with_retry

sys.path.insert(0, os.path.dirname(__file__))
from scan_common import AlreadyCommented, check_length  # compartido entre redes, 23/09
from x_interact import _check_spanish_orthography  # reutilizado, no duplicado

if hasattr(sys.stdout, "reconfigure"):
    # BUG REAL visto en vivo el 21/09: la consola de Windows imprimia
    # "D�az"/"Espa�a" en vez de "Díaz"/"España" - los datos que llegan de
    # la API son UTF-8 correcto, es la codificacion por defecto de la
    # consola (cp1252/cp850) la que rompe el print. x_interact.py no lo
    # sufre porque Playwright gestiona su propia salida distinto.
    sys.stdout.reconfigure(encoding="utf-8")

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def _load_env():
    """Carga .env a mano (sin dependencia nueva de python-dotenv) - el
    mismo patron sencillo que ya usan otros scripts de tools/ para
    PEXELS_API_KEY/PIXABAY_API_KEY."""
    if not os.path.exists(_ENV_PATH):
        return
    with open(_ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_env()

PUBLIC_BASE = "https://public.api.bsky.app/xrpc"
AUTH_BASE = "https://bsky.social/xrpc"
HANDLE = os.environ.get("BLUESKY_HANDLE", "")
APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD", "")

_session_cache = {}


class BotWarningDetected(Exception):
    pass


class RateLimitExceeded(RuntimeError):
    """429 de Bluesky: detener la ronda, no encadenar más escrituras."""

    def __init__(self, operation, retry_after=None):
        self.operation = operation
        self.retry_after = retry_after
        suffix = f"; Retry-After={retry_after}s" if retry_after else ""
        super().__init__(f"Bluesky rate limit (429) en {operation}{suffix}")


def _raise_if_rate_limited(response, operation):
    if response.status_code != 429:
        return
    retry_after = response.headers.get("Retry-After")
    raise RateLimitExceeded(operation, retry_after)


def _require_credentials():
    if not HANDLE or not APP_PASSWORD:
        raise RuntimeError(
            "faltan BLUESKY_HANDLE y/o BLUESKY_APP_PASSWORD en .env - "
            "David tiene que generar una contrasena de aplicacion en "
            "bsky.app (Configuracion > Privacidad y seguridad > Contrasenas "
            "de aplicacion) y pegarla en .env. Sin esto solo funcionan los "
            "comandos de lectura publica (search, profile de otra cuenta)."
        )


def _session_dir():
    """Directorio privado del usuario (LOCALAPPDATA en Windows, ~/.cache en el resto), NUNCA
    la carpeta temporal compartida ni el repo: el fichero guarda tokens de la cuenta."""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "rrss")


_SESSION_FILE = os.path.join(_session_dir(), "bsky_session.json")
_SESSION_MARGIN = 120  # segundos de margen antes de que caduque el accessJwt


def _jwt_expiry(token):
    """Caducidad (epoch) de un JWT sin verificar la firma; 0 si no se puede leer."""
    try:
        import base64
        import json as _json
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(_json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except Exception:
        return 0.0


def _read_disk_session():
    try:
        import json as _json
        if os.path.islink(_SESSION_FILE):
            return None  # nunca seguir enlaces simbolicos
        if hasattr(os, "getuid"):  # POSIX: solo si es nuestro y no lo lee nadie mas
            info = os.stat(_SESSION_FILE)
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                return None
        with open(_SESSION_FILE, encoding="utf-8") as stream:
            data = _json.load(stream)
    except (OSError, ValueError):
        return None
    # solo sirve si es de ESTA cuenta (nunca reutilizar el token de otra)
    if not isinstance(data, dict) or str(data.get("handle", "")).casefold() != HANDLE.casefold():
        return None
    return data


def _write_disk_session(data):
    """Escritura atomica con permisos solo-propietario (0o600) en un directorio 0o700."""
    try:
        import json as _json
        directory = os.path.dirname(_SESSION_FILE)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        if os.path.islink(_SESSION_FILE):
            return
        tmp = f"{_SESSION_FILE}.{os.getpid()}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            _json.dump(data, stream)
        os.replace(tmp, _SESSION_FILE)
    except OSError:
        pass  # el cache es una optimizacion: sin el, se vuelve a autenticar


def _session():
    """Sesion autenticada. Cada comando es un proceso Python nuevo y createSession
    esta limitado a 30 por 5 min y 300 por dia (docs de Bluesky), asi que la sesion se
    reutiliza entre procesos: cache en disco -> refreshSession -> createSession."""
    _require_credentials()
    if "accessJwt" in _session_cache:
        return _session_cache
    disk = _read_disk_session()
    now = time.time()
    if disk and _jwt_expiry(disk.get("accessJwt", "")) - now > _SESSION_MARGIN:
        _session_cache.update(disk)
        return _session_cache
    if disk and _jwt_expiry(disk.get("refreshJwt", "")) - now > _SESSION_MARGIN:
        r = requests.post(f"{AUTH_BASE}/com.atproto.server.refreshSession",
                          headers={"Authorization": f"Bearer {disk['refreshJwt']}"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            _session_cache.update(data)
            _write_disk_session({**data, "handle": data.get("handle") or HANDLE})
            return _session_cache
    r = requests.post(
        f"{AUTH_BASE}/com.atproto.server.createSession",
        json={"identifier": HANDLE, "password": APP_PASSWORD},
        timeout=15,
    )
    _raise_if_rate_limited(r, "POST com.atproto.server.createSession")
    if r.status_code != 200:
        raise RuntimeError(f"login fallido ({r.status_code}): {r.text[:300]}")
    data = r.json()
    _session_cache.update(data)
    _write_disk_session({**data, "handle": data.get("handle") or HANDLE})
    return _session_cache


def _headers(auth=True):
    if auth and APP_PASSWORD:
        sess = _session()
        return {"Authorization": f"Bearer {sess['accessJwt']}"}
    return {}


def _get(base, path, params=None, auth=True, extra_headers=None):
    headers = _headers(auth)
    if extra_headers:
        headers.update({
            str(key): str(value)
            for key, value in extra_headers.items()
            if value is not None
        })
    r = get_with_retry(
        f"{base}/{path}",
        params=params or {},
        headers=headers,
        timeout=15,
    )
    _raise_if_rate_limited(r, f"GET {path}")
    if r.status_code == 401 and auth and "accessJwt" in _session_cache:
        # token vencido a mitad de sesion larga - reintentar una vez con sesion nueva
        _session_cache.clear()
        headers = _headers(auth)
        if extra_headers:
            headers.update({
                str(key): str(value)
                for key, value in extra_headers.items()
                if value is not None
            })
        r = get_with_retry(
            f"{base}/{path}",
            params=params or {},
            headers=headers,
            timeout=15,
        )
        _raise_if_rate_limited(r, f"GET {path}")
    if r.status_code != 200:
        raise RuntimeError(f"GET {path} fallo ({r.status_code}): {r.text[:300]}")
    return r.json()


def _post_xrpc(path, body):
    r = requests.post(f"{AUTH_BASE}/{path}", json=body, headers=_headers(auth=True), timeout=15)
    _raise_if_rate_limited(r, f"POST {path}")
    if r.status_code != 200:
        raise RuntimeError(f"POST {path} fallo ({r.status_code}): {r.text[:300]}")
    return r.json()


def _require_created_record(response, collection):
    """Una escritura HTTP 200 sin URI y CID no acredita un post nuevo.

    No reintentar automáticamente si falta confirmación: la escritura pudo
    completarse y perderse la respuesta; comprobar primero el repositorio.
    """
    if (not isinstance(response, dict) or not isinstance(response.get("uri"), str)
            or not response["uri"].startswith("at://")
            or f"/{collection}/" not in response["uri"]
            or not isinstance(response.get("cid"), str) or not response["cid"]):
        raise RuntimeError(
            f"{collection}: la API no confirmó URI/CID del registro creado; "
            "revisar la cuenta antes de reintentar para evitar duplicados"
        )
    return response



def _utf8_slice(text, start, end):
    return {
        "byteStart": len(text[:start].encode("utf-8")),
        "byteEnd": len(text[:end].encode("utf-8")),
    }


def _richtext_facets(text):
    """Facetas mínimas seguras para que URLs y hashtags sean estructurados.

    createRecord no convierte por sí solo '#BookSky' o una URL en facets.
    Se calculan offsets en bytes UTF-8, no índices Python. Las menciones
    requieren resolver handles a DID y se dejan fuera hasta añadir una
    resolución explícita/fail-closed.
    """
    if not isinstance(text, str):
        return []
    spans = []
    facets = []
    url_re = re.compile(r"https?://[^\s<>()]+", re.I)
    for match in url_re.finditer(text):
        end = match.end()
        while end > match.start() and text[end - 1] in ".,;:!?)]}":
            end -= 1
        if end <= match.start():
            continue
        uri = text[match.start():end]
        facets.append({
            "index": _utf8_slice(text, match.start(), end),
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": uri}],
        })
        spans.append((match.start(), end))

    tag_re = re.compile(r"(?<![\w#])#([\w]{1,64})", re.UNICODE)
    for match in tag_re.finditer(text):
        if any(match.start() < end and match.end() > start for start, end in spans):
            continue
        tag = match.group(1)
        if not any(ch.isalpha() for ch in tag):
            continue
        facets.append({
            "index": _utf8_slice(text, match.start(), match.end()),
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}],
        })
    return sorted(facets, key=lambda item: item["index"]["byteStart"])



def _mention_facets(text, occupied):
    facets = []
    mention_re = re.compile(
        r"(?<![\w@])@([A-Za-z0-9](?:[A-Za-z0-9.-]{1,251}[A-Za-z0-9]))"
    )
    for match in mention_re.finditer(text or ""):
        if "." not in match.group(1):
            continue
        if any(match.start() < end and match.end() > start for start, end in occupied):
            continue
        handle = match.group(1).lower()
        try:
            did = _resolve_did(handle)
        except Exception as exc:
            raise RuntimeError(
                f"No se pudo resolver la mencion @{handle}; no publicar como texto plano"
            ) from exc
        facets.append({
            "index": _utf8_slice(text, match.start(), match.end()),
            "features": [{
                "$type": "app.bsky.richtext.facet#mention",
                "did": did,
            }],
        })
    return facets



def _add_richtext(record):
    text = record.get("text", "")
    facets = _richtext_facets(text)
    # Para mentions trabajamos en índices de caracteres y evitamos mezclar
    # intervalos de enlaces/hashtags en caracteres solo para mentions.
    char_occupied = []
    for pattern in (
        re.compile(r"https?://[^\s<>()]+", re.I),
        re.compile(r"(?<![\w#])#([\w]{1,64})", re.UNICODE),
    ):
        char_occupied.extend((m.start(), m.end()) for m in pattern.finditer(text))
    facets.extend(_mention_facets(text, char_occupied))
    if facets:
        record["facets"] = sorted(
            facets, key=lambda item: item["index"]["byteStart"]
        )
    return record



def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _check_length(text, limit=300):
    """Bluesky permite 300 caracteres, NO 280 como X - error real que se
    cometeria facil copiando el limite del hermano de X sin mirar."""
    check_length(text, limit)


# _check_spanish_orthography importada de x_interact.py (23/09, antes un
# shim local que reenviaba a la misma funcion).


_DID_CACHE = {}


def _resolve_did(actor):
    """Convierte un handle en DID. Si ya es un DID (empieza por 'did:'), lo
    devuelve tal cual. Endpoint publico, no necesita sesion.

    05/10: con memoria por proceso. Cada accion resolvia el handle del permalink dos veces (preflight y escritura) y un autor con varios posts, todas las veces:
    ~1 s de red por accion que no aportaba nada (un DID no cambia durante una ronda)."""
    if actor.startswith("did:"):
        return actor
    key = actor.casefold()
    if key in _DID_CACHE:
        return _DID_CACHE[key]
    data = _get(PUBLIC_BASE, "com.atproto.identity.resolveHandle", {"handle": actor}, auth=False)
    _DID_CACHE[key] = data["did"]
    return data["did"]


def warm_dids(handles, workers=8):
    """Resuelve en paralelo los handles del plan antes de validarlo (el preflight serie tardaba minutos con 400-1.000 acciones). Los fallos se ignoran:
    la validacion normal los vuelve a encontrar y decide por objetivo."""
    from concurrent.futures import ThreadPoolExecutor
    todo = [h for h in dict.fromkeys(str(h).lstrip("@") for h in handles) if h and not h.startswith("did:") and h.casefold() not in _DID_CACHE]
    if len(todo) < 2:
        return

    def one(handle):
        try:
            _resolve_did(handle)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
        list(executor.map(one, todo))


def _url_to_uri(url_or_uri):
    """Solo acepta AT-URI de post o permalink HTTPS de bsky.app.

    Un regex sobre la URL completa aceptaba https://evil/bsky.app/profile/...
    y confundía una mención del dominio con un permalink real.
    """
    if not isinstance(url_or_uri, str):
        raise ValueError("Se requiere URL/AT-URI de Bluesky")
    if re.fullmatch(
        r"at://did:(?:plc:[a-z2-7]+|web:[A-Za-z0-9.-]+)/app\.bsky\.feed\.post/[A-Za-z0-9]+",
        url_or_uri,
    ):
        return url_or_uri
    parsed = urllib.parse.urlsplit(url_or_uri)
    if (parsed.scheme != "https" or parsed.hostname not in ("bsky.app", "www.bsky.app")
            or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment):
        raise ValueError("Se requiere permalink HTTPS canónico de bsky.app")
    match = re.fullmatch(r"/profile/([A-Za-z0-9.:%-]+)/post/([A-Za-z0-9]+)/?", parsed.path)
    if not match:
        raise ValueError("URL no es un permalink de post Bluesky")
    actor, rkey = urllib.parse.unquote(match.group(1)), match.group(2)
    if not re.fullmatch(r"(?:did:(?:plc:[a-z2-7]+|web:[A-Za-z0-9.-]+)|[A-Za-z0-9.-]+)", actor):
        raise ValueError("Autor del permalink inválido")
    did = _resolve_did(actor)
    return f"at://{did}/app.bsky.feed.post/{rkey}"


def _get_post_record(uri):
    """Devuelve {uri, cid, text, author_handle, reply_root} de un post via
    getPostThread - hace falta el cid (no solo la uri) para poder dar like,
    citar o responder; a diferencia de X, AT Protocol siempre exige los dos
    juntos para referenciar un registro."""
    data = _get(PUBLIC_BASE, "app.bsky.feed.getPostThread", {"uri": uri, "depth": 0}, auth=False)
    thread = data["thread"]
    if "notFound" in thread or thread.get("$type", "").endswith("notFound"):
        raise RuntimeError(f"post no encontrado: {uri}")
    post = thread["post"]
    record = post["record"]
    root = None
    if isinstance(record, dict) and record.get("reply"):
        root = record["reply"]["root"]
    return {
        "uri": post["uri"],
        "cid": post["cid"],
        "text": record.get("text", ""),
        "author": post["author"]["handle"],
        "root": root,
    }


def _print_post_line(post):
    author = post.get("author", {})
    record = post.get("record", {}) or {}
    print("---")
    print("URI:", post.get("uri"))
    print("URL:", f"https://bsky.app/profile/{author.get('handle')}/post/{post.get('uri', '').rsplit('/', 1)[-1]}")
    print(f"@{author.get('handle')} ({author.get('displayName', '')})")
    print(record.get("text", "")[:280])
    stats = f"likes={post.get('likeCount', 0)} reposts={post.get('repostCount', 0)} replies={post.get('replyCount', 0)}"
    print(stats)


def _health_check():
    """Nucleo de health(), extraido el 22/09 (mismo patron que
    x_interact.py/threads_interact.py/instagram_interact.py) para que
    bluesky_scan.py pueda comprobar la sesion sin imprimir dos veces.
    Devuelve (ok, mensaje, profile_o_None)."""
    try:
        _require_credentials()
        sess = _session()
        profile = _get(PUBLIC_BASE, "app.bsky.actor.getProfile", {"actor": sess["did"]}, auth=False)
    except Exception as e:
        return False, f"PROBLEMA: {e}", None
    msg = (
        f"OK: sesion logueada como @{profile['handle']} ({profile.get('displayName', '')})\n"
        f"Followers: {profile.get('followersCount', 0)} | Following: {profile.get('followsCount', 0)} | Posts: {profile.get('postsCount', 0)}"
    )
    return True, msg, profile


def health():
    ok, msg, profile = _health_check()
    print(msg)


def _get_notifications(limit=25):
    data = _get(AUTH_BASE, "app.bsky.notification.listNotifications", {"limit": limit})
    return data.get("notifications", [])


def notifications(limit=25):
    for n in _get_notifications(limit):
        print("---")
        print(n["reason"], "-", n["indexedAt"])
        author = n["author"]
        print(f"@{author['handle']} ({author.get('displayName', '')})")
        record = n.get("record", {}) or {}
        if record.get("text"):
            print(record["text"][:280])
        print("URI:", n.get("uri"))


def _get_timeline(limit=25):
    data = _get(AUTH_BASE, "app.bsky.feed.getTimeline", {"limit": limit})
    return [item["post"] for item in data.get("feed", [])]


def timeline(limit=25):
    for post in _get_timeline(limit):
        _print_post_line(post)


def _search_posts(query, lang="es", limit=20, *, sort="latest", tag=None,
                  author=None, mentions=None, domain=None, url=None,
                  since=None, until=None, cursor=None):
    """Buscar posts con los filtros que expone searchPosts en 2026.

    El AppView público suele admitir este GET, pero la especificación avisa
    de que algunos proveedores pueden exigir autenticación. Probamos público
    primero y caemos a la sesión propia solo ante 401/403.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("searchPosts exige una consulta q no vacía")
    if sort not in ("latest", "top"):
        raise ValueError("sort debe ser latest o top")
    limit = max(1, min(int(limit), 100))
    params = {"q": query.strip(), "limit": limit, "sort": sort}
    if lang and lang != "all":
        params["lang"] = lang
    if tag:
        params["tag"] = [str(x).lstrip("#") for x in
                         (tag if isinstance(tag, (list, tuple)) else [tag])]
    for key, value in (
        ("author", author), ("mentions", mentions), ("domain", domain),
        ("url", url), ("since", since), ("until", until), ("cursor", cursor),
    ):
        if value:
            params[key] = value

    public = requests.get(
        f"{PUBLIC_BASE}/app.bsky.feed.searchPosts", params=params, timeout=15
    )
    _raise_if_rate_limited(public, "GET app.bsky.feed.searchPosts")
    if public.status_code == 200:
        return public.json().get("posts", [])
    if public.status_code not in (401, 403):
        raise RuntimeError(
            f"searchPosts público falló ({public.status_code}): {public.text[:300]}"
        )
    _require_credentials()
    data = _get(AUTH_BASE, "app.bsky.feed.searchPosts", params, auth=True)
    return data.get("posts", [])


def _search_actors(query, limit=25):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("searchActors exige una consulta no vacía")
    data = _get(
        PUBLIC_BASE, "app.bsky.actor.searchActors",
        {"q": query.strip(), "limit": max(1, min(int(limit), 100))},
        auth=False,
    )
    return data.get("actors", [])


def dump_actors(query, limit=25):
    actors = _search_actors(query, limit)
    if not actors:
        print("sin perfiles")
        return
    for actor in actors:
        print("---")
        print(f"@{actor.get('handle')} ({actor.get('displayName', '')})")
        print(actor.get("description", "")[:300])
        print("followers:", actor.get("followersCount", "?"))


def _post_engagers(url_or_uri, kind, limit=50):
    uri = _url_to_uri(url_or_uri)
    endpoints = {
        "quotes": ("app.bsky.feed.getQuotes", "posts"),
        "likes": ("app.bsky.feed.getLikes", "likes"),
        "reposts": ("app.bsky.feed.getRepostedBy", "repostedBy"),
    }
    if kind not in endpoints:
        raise ValueError("kind de engagement inválido")
    path, field = endpoints[kind]
    data = _get(PUBLIC_BASE, path, {"uri": uri, "limit": max(1, min(int(limit), 100))},
                auth=False)
    return data.get(field, [])


def dump_engagers(url_or_uri, kind, limit=50):
    items = _post_engagers(url_or_uri, kind, limit)
    if not items:
        print("sin resultados")
        return
    for item in items:
        if kind == "quotes":
            _print_post_line(item)
        else:
            actor = item.get("actor") if kind == "likes" else item
            actor = actor or {}
            print(f"@{actor.get('handle')} ({actor.get('displayName', '')})")



def dump_search(query, lang="es", limit=20, **filters):
    posts = _search_posts(query, lang, limit, **filters)
    if not posts:
        print("sin resultados")
        return
    for post in posts:
        _print_post_line(post)


def dump_profile(handle=None):
    actor = handle or HANDLE
    if not actor:
        raise RuntimeError("no hay handle - pasa uno o configura BLUESKY_HANDLE en .env")
    profile = _get(PUBLIC_BASE, "app.bsky.actor.getProfile", {"actor": actor}, auth=False)
    print(f"@{profile['handle']} ({profile.get('displayName', '')})")
    print(profile.get("description", ""))
    print(f"Followers: {profile.get('followersCount', 0)} | Following: {profile.get('followsCount', 0)} | Posts: {profile.get('postsCount', 0)}")
    print("=== posts recientes ===")
    feed = _get(PUBLIC_BASE, "app.bsky.feed.getAuthorFeed", {"actor": actor, "limit": 10}, auth=False)
    for item in feed.get("feed", []):
        _print_post_line(item["post"])


def dump_thread(url_or_uri):
    uri = _url_to_uri(url_or_uri)
    data = _get(PUBLIC_BASE, "app.bsky.feed.getPostThread", {"uri": uri, "depth": 6}, auth=False)
    thread = data["thread"]
    _print_post_line(thread["post"])
    for reply in thread.get("replies", []):
        _print_post_line(reply["post"])


# Precarga en lote (05/10): por cada like/repost se hacian 3 peticiones (getPosts del viewer + getPostThread para el cid + createRecord) y por cada follow 2
# (getProfile + createRecord): ~11 s por accion con las pausas, es decir, ~330 acciones/hora y 8.000/dia serian 24 h. `getPosts`/`getProfiles` con sesion devuelven
# viewer y cid/did de 25 objetivos por peticion, asi que cada accion se reduce al createRecord. El estado precargado caduca a los 30 min y se consume al usarlo.
import time as _time

_PREFETCH = {}
PREFETCH_TTL = 1800


def prefetch(uris=(), handles=()):
    """Precarga viewer + cid de posts y viewer + did de perfiles (en lotes de 25). Un fallo no rompe nada: la accion recurre a las consultas de siempre."""
    now = _time.time()
    uris = [u for u in dict.fromkeys(uris) if u]
    handles = [h for h in dict.fromkeys(str(h).lstrip("@") for h in handles) if h]
    for start in range(0, len(uris), 25):
        chunk = uris[start:start + 25]
        try:
            data = _get(AUTH_BASE, "app.bsky.feed.getPosts", {"uris": chunk}, auth=True)
        except RateLimitExceeded:
            raise
        except Exception:
            continue
        for post in data.get("posts") or []:
            if isinstance(post, dict) and post.get("uri") and post.get("cid") and isinstance(post.get("viewer"), dict):
                _PREFETCH[("post", post["uri"])] = {"cid": post["cid"], "viewer": post["viewer"], "t": now}
    for start in range(0, len(handles), 25):
        chunk = handles[start:start + 25]
        try:
            data = _get(AUTH_BASE, "app.bsky.actor.getProfiles", {"actors": chunk}, auth=True)
        except RateLimitExceeded:
            raise
        except Exception:
            continue
        for profile in data.get("profiles") or []:
            if isinstance(profile, dict) and profile.get("did") and isinstance(profile.get("viewer"), dict):
                entry = {"did": profile["did"], "viewer": profile["viewer"], "t": now}
                _PREFETCH[("profile", str(profile.get("handle") or "").casefold())] = entry
                _PREFETCH[("profile", profile["did"])] = entry


def _prefetched(key):
    entry = _PREFETCH.pop(key, None)       # se consume: un estado usado ya no es fiable
    if entry and _time.time() - entry["t"] <= PREFETCH_TTL:
        return entry
    return None


def _reaction_state(uri, field):
    """Estado de like/repost del usuario autenticado; NO usar endpoint público."""
    if field not in ("like", "repost"):
        raise ValueError("Reacción desconocida")
    data = _get(AUTH_BASE, "app.bsky.feed.getPosts", {"uris": [uri]}, auth=True)
    posts = data.get("posts")
    if not isinstance(posts, list) or len(posts) != 1 or posts[0].get("uri") != uri:
        raise RuntimeError("No se pudo comprobar el post exacto antes de reaccionar")
    viewer = posts[0].get("viewer")
    if not isinstance(viewer, dict):
        raise RuntimeError("Falta viewer autenticado; no asumir ausencia de reacción")
    return bool(viewer.get(field))


def _react_once(url_or_uri, field):
    """Devuelve (estado, uri_propio). uri_propio es None salvo cuando se
    acaba de crear el registro - lo necesita repost() para poder borrarlo
    despues via delete_own_record() (limpieza TTL, 29/09)."""
    _require_credentials()
    uri = _url_to_uri(url_or_uri)
    cached = _prefetched(("post", uri))
    if cached is not None:
        if cached["viewer"].get(field):
            print(f"{field}: ya existía una reacción propia; no duplicar")
            return "already", None
        post = {"uri": uri, "cid": cached["cid"]}
    else:
        if _reaction_state(uri, field):
            print(f"{field}: ya existía una reacción propia; no duplicar")
            return "already", None
        post = _get_post_record(uri)
    sess = _session()
    collection = "app.bsky.feed.like" if field == "like" else "app.bsky.feed.repost"
    result = _post_xrpc("com.atproto.repo.createRecord", {
        "repo": sess["did"],
        "collection": collection,
        "record": {
            "$type": collection,
            "subject": {"uri": post["uri"], "cid": post["cid"]},
            "createdAt": _now(),
        },
    })
    _require_created_record(result, collection)
    print(f"{field}: registro creado por API")
    return "created", result["uri"]


def like(url_or_uri):
    """Reacción única: comprueba viewer.like antes de crear un registro."""
    status, _ = _react_once(url_or_uri, "like")
    return status


def repost(url_or_uri):
    """Repost único: comprueba viewer.repost antes de crear un registro.

    Devuelve (estado, uri_propio) - a diferencia de like()/follow(), el
    llamador (bluesky_execute.py) necesita el URI propio para poder
    programar su borrado (limpieza TTL de reposts/citas, 29/09)."""
    return _react_once(url_or_uri, "repost")


def quote(url_or_uri, text):
    """Cita con comentario propio - en AT Protocol una 'cita' es un post
    normal con un 'embed' de tipo app.bsky.embed.record apuntando al
    original, no una accion separada como el menu Quote de X.

    Devuelve (estado, uri_propio) por el mismo motivo que repost(): permitir
    programar el borrado despues (limpieza TTL, 29/09)."""
    _require_credentials()
    _check_length(text)
    _check_spanish_orthography(text)
    uri = _url_to_uri(url_or_uri)
    if _already_quoted(uri, text):
        print("quote: ya existe una cita idéntica propia; no duplicar")
        return "already", None
    target = _get_post_record(uri)
    sess = _session()
    created = _post_xrpc("com.atproto.repo.createRecord", {
        "repo": sess["did"],
        "collection": "app.bsky.feed.post",
        "record": _add_richtext({
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": _now(),
            "langs": ["es"],
            "embed": {"$type": "app.bsky.embed.record", "record": {"uri": target["uri"], "cid": target["cid"]}},
        }),
    })
    _require_created_record(created, "app.bsky.feed.post")
    print("cita publicada (URI/CID confirmado)")
    return "created", created["uri"]


def delete_own_record(uri):
    """Borrar un registro propio (repost/cita/post/like/follow) por su
    AT-URI. Fuente unica para toda limpieza TTL (29/09) - reutiliza el mismo
    patron ya probado en unfollow(): extraer collection+rkey del URI propio
    y pedir confirmacion explicita a deleteRecord antes de darlo por hecho."""
    _require_credentials()
    sess = _session()
    prefix = f"at://{sess['did']}/"
    if not isinstance(uri, str) or not uri.startswith(prefix):
        raise RuntimeError(
            f"delete_own_record: URI no pertenece al repo propio: {uri!r}"
        )
    rest = uri[len(prefix):]
    if "/" not in rest:
        raise RuntimeError(f"delete_own_record: URI mal formado: {uri!r}")
    collection, rkey = rest.split("/", 1)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", collection) or not re.fullmatch(r"[A-Za-z0-9._-]+", rkey):
        raise RuntimeError(f"delete_own_record: collection/rkey invalidos en {uri!r}")
    result = _post_xrpc("com.atproto.repo.deleteRecord", {
        "repo": sess["did"], "collection": collection, "rkey": rkey,
    })
    if not isinstance(result, dict):
        raise RuntimeError(
            "delete_own_record: la API no confirmó la eliminación"
        )
    print(f"borrado: {uri}")
    return "deleted"


# AlreadyCommented importada de scan_common (23/09, centralizada) - la
# deteccion sigue siendo propia (via getPostThread), solo el tipo de
# excepcion es compartido.


def _iter_own_posts():
    """Itera todos los posts del repo propio sin declarar ausencia si la
    paginación es incoherente. Se usa para guardas de reply/quote."""
    sess = _session()
    cursor = None
    seen_cursors = set()
    while True:
        params = {
            "repo": sess["did"],
            "collection": "app.bsky.feed.post",
            "limit": 100,
            "reverse": True,
        }
        if cursor:
            params["cursor"] = cursor
        data = _get(AUTH_BASE, "com.atproto.repo.listRecords", params, auth=True)
        records = data.get("records")
        if not isinstance(records, list):
            raise RuntimeError("No se puede verificar el historial propio de posts")
        for item in records:
            yield item
        next_cursor = data.get("cursor")
        if not next_cursor:
            return
        if not isinstance(next_cursor, str) or next_cursor in seen_cursors:
            raise RuntimeError("Paginación listRecords inválida; no asumir ausencia")
        seen_cursors.add(next_cursor)
        cursor = next_cursor



def _own_reply_parent_uris():
    """Devuelve en una sola pasada los AT-URI a los que ya respondimos.

    El scan diario necesita saber esto para no volver a proponer conversaciones
    cerradas. Construir el conjunto una vez evita recorrer todo el repo propio
    por cada notificación candidata.
    """
    parents = set()
    for item in _iter_own_posts():
        value = item.get("value") if isinstance(item, dict) else None
        if not isinstance(value, dict):
            continue
        reply = value.get("reply")
        parent = reply.get("parent") if isinstance(reply, dict) else None
        uri = parent.get("uri") if isinstance(parent, dict) else None
        if isinstance(uri, str) and uri.startswith("at://"):
            parents.add(uri)
    return parents


def _already_commented(uri):
    """Comprobar en NUESTRO repo si ya existe una reply directa al objetivo."""
    for item in _iter_own_posts():
        value = item.get("value") if isinstance(item, dict) else None
        if not isinstance(value, dict):
            continue
        reply = value.get("reply")
        parent = reply.get("parent") if isinstance(reply, dict) else None
        if isinstance(parent, dict) and parent.get("uri") == uri:
            return True
    return False


def _already_quoted(uri, text):
    """Evita repetir exactamente la misma cita tras una respuesta perdida.

    Citar dos veces el mismo post con textos distintos sigue permitido; para
    un reintento automático/manual con el mismo payload, el repo propio es la
    fuente autoritativa aunque el createRecord anterior no devolviera URI/CID.
    """
    for item in _iter_own_posts():
        value = item.get("value") if isinstance(item, dict) else None
        if not isinstance(value, dict) or value.get("text") != text:
            continue
        embed = value.get("embed")
        record = embed.get("record") if isinstance(embed, dict) else None
        if (isinstance(record, dict) and record.get("uri") == uri
                and embed.get("$type") == "app.bsky.embed.record"):
            return True
    return False


def reply_to(url_or_uri, text):
    _require_credentials()
    _check_length(text)
    _check_spanish_orthography(text)
    uri = _url_to_uri(url_or_uri)
    if _already_commented(uri):
        raise AlreadyCommented(
            f"Ya hay una respuesta nuestra en el hilo de {url_or_uri} - no se "
            "envia una segunda."
        )
    parent = _get_post_record(uri)
    root = parent["root"] if parent["root"] else {"uri": parent["uri"], "cid": parent["cid"]}
    sess = _session()
    created = _post_xrpc("com.atproto.repo.createRecord", {
        "repo": sess["did"],
        "collection": "app.bsky.feed.post",
        "record": _add_richtext({
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": _now(),
            "langs": ["es"],
            "reply": {
                "root": root,
                "parent": {"uri": parent["uri"], "cid": parent["cid"]},
            },
        }),
    })
    _require_created_record(created, "app.bsky.feed.post")
    print("reply enviada (URI/CID confirmado)")


def follow(handle):
    """BUG REAL encontrado el 23/09 en la primera ejecucion real con volumen:
    esta funcion nunca comprobaba si ya seguiamos a `handle` antes de crear
    el registro - `com.atproto.repo.createRecord` no dedupe por si solo, asi
    que 3 de 6 follows de una sesion real resultaron ser registros de follow
    DUPLICADOS sobre cuentas que ya seguiamos (confirmado comparando
    getFollows antes/despues: el contador de "siguiendo" solo subio 1 en vez
    de 6). Corregido comprobando `viewer.following` via getProfile - el
    mismo campo que el docstring de unfollow() ya identificaba como la unica
    fuente fiable (getFollows NUNCA trae 'viewer', confirmado el 21/09)."""
    _require_credentials()
    profile = _prefetched(("profile", str(handle).lstrip("@").casefold()))
    if profile is None:
        profile = _get(AUTH_BASE, "app.bsky.actor.getProfile", {"actor": handle}, auth=True)
    viewer = profile.get("viewer")
    if not isinstance(viewer, dict):
        raise RuntimeError(f"No hay estado de follow verificable para @{handle}; se omite escritura")
    if viewer.get("following"):
        print(f"{handle}: ya se seguia (sin duplicar registro)")
        return "already"
    did = profile["did"]
    sess = _session()
    created = _post_xrpc("com.atproto.repo.createRecord", {
        "repo": sess["did"],
        "collection": "app.bsky.graph.follow",
        "record": {
            "$type": "app.bsky.graph.follow",
            "subject": did,
            "createdAt": _now(),
        },
    })
    _require_created_record(created, "app.bsky.graph.follow")
    print(f"{handle}: FOLLOWED (registro creado por API)")
    return "followed"


def unfollow(handle):
    """Obtener el URI de follow propio directamente de viewer.following.

    Antes se consultaban hasta 2000 registros propios, se perdía un follow
    más antiguo y se declaraba falsamente que ya no se seguía la cuenta.
    getProfile autenticado devuelve el URI del follow propio sin paginación.
    """
    _require_credentials()
    profile = _get(AUTH_BASE, "app.bsky.actor.getProfile",
                   {"actor": handle}, auth=True)
    if not isinstance(profile, dict) or not isinstance(profile.get("viewer"), dict):
        raise RuntimeError("No se puede verificar la relación activa antes de unfollow")
    uri = profile["viewer"].get("following")
    if not uri:
        print(f"{handle}: no hay relación de follow activa; no se modifica nada")
        return "already"
    sess = _session()
    prefix = f"at://{sess['did']}/app.bsky.graph.follow/"
    if (not isinstance(uri, str) or not uri.startswith(prefix)
            or not re.fullmatch(r"[A-Za-z0-9]+", uri[len(prefix):])):
        raise RuntimeError("El URI de follow no corresponde a un registro propio válido")
    result = _post_xrpc("com.atproto.repo.deleteRecord", {
        "repo": sess["did"], "collection": "app.bsky.graph.follow",
        "rkey": uri[len(prefix):],
    })
    if not isinstance(result, dict):
        raise RuntimeError(
            "La API no confirmó la eliminación: comprobar relación antes de reintentar"
        )
    print(f"{handle}: unfollow procesado por API")
    return "unfollowed"


def _upload_image(image_path, alt_text):
    """Sube una imagen via com.atproto.repo.uploadBlob y devuelve el embed
    app.bsky.embed.images listo para meter en el record del post. Anadido
    24/09 para la cola de autopromocion (publicaciones GPT) - Bluesky no
    tiene programacion nativa, pero SI soporta imagen+ALT en post() normal,
    que hasta ahora no se usaba."""
    _require_credentials()
    sess = _session()
    with open(image_path, "rb") as f:
        data = f.read()
    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp"}.get(ext)
    if not mime:
        raise ValueError("Bluesky: formato de imagen no admitido (jpg/jpeg/png/webp)")
    if len(data) > 2_000_000:
        raise ValueError("Bluesky: imagen > 2 MB; reducir antes de subir")
    r = requests.post(
        f"{AUTH_BASE}/com.atproto.repo.uploadBlob",
        data=data,
        headers={**_headers(auth=True), "Content-Type": mime},
        timeout=30,
    )
    _raise_if_rate_limited(r, "POST com.atproto.repo.uploadBlob")
    if r.status_code != 200:
        raise RuntimeError(f"uploadBlob fallo ({r.status_code}): {r.text[:300]}")
    blob = r.json()["blob"]
    return {"$type": "app.bsky.embed.images", "images": [{"alt": alt_text, "image": blob}]}


def post(text, image_path=None, alt_text=""):
    _require_credentials()
    _check_length(text)
    _check_spanish_orthography(text)
    sess = _session()
    record = _add_richtext({
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": _now(),
        "langs": ["es"],
    })
    if image_path:
        if not isinstance(alt_text, str) or not alt_text.strip():
            raise ValueError("Una imagen Bluesky exige ALT no vacío")
        record["embed"] = _upload_image(image_path, alt_text.strip())
    created = _post_xrpc("com.atproto.repo.createRecord", {
        "repo": sess["did"],
        "collection": "app.bsky.feed.post",
        "record": record,
    })
    _require_created_record(created, "app.bsky.feed.post")
    print("post publicado (URI/CID confirmado)" + (" (con imagen)" if image_path else ""))


def _dispatch():
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "health":
        health()
    elif cmd == "notifications":
        notifications()
    elif cmd == "timeline":
        timeline()
    elif cmd == "search":
        dump_search(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "es")
    elif cmd == "tag":
        tag = sys.argv[2].lstrip("#")
        dump_search(tag, sys.argv[3] if len(sys.argv) > 3 else "es", tag=[tag])
    elif cmd == "actors":
        dump_actors(sys.argv[2])
    elif cmd == "domain":
        domain = sys.argv[2]
        dump_search(domain, "all", domain=domain)
    elif cmd in ("quotes", "likers", "reposters"):
        mapping = {"quotes": "quotes", "likers": "likes", "reposters": "reposts"}
        dump_engagers(sys.argv[2], mapping[cmd])
    elif cmd == "profile":
        dump_profile(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "thread":
        dump_thread(sys.argv[2])
    elif cmd == "reply":
        reply_to(sys.argv[2], sys.argv[3])
    elif cmd == "like":
        like(sys.argv[2])
    elif cmd == "repost":
        repost(sys.argv[2])
    elif cmd == "quote":
        quote(sys.argv[2], sys.argv[3])
    elif cmd == "follow":
        follow(sys.argv[2])
    elif cmd == "unfollow":
        unfollow(sys.argv[2])
    elif cmd == "post":
        post(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None, sys.argv[4] if len(sys.argv) > 4 else "")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    _dispatch()
