"""
Herramienta unica para el dia a dia de Reddit (u/AutoraDemoEscritor) - mismo
patron que tools/x_interact.py y tools/threads_interact.py: Edge real via
CDP puerto 9223, ya logueado (David confirmo el login el 21/09/2026). No es
una copia ciega: Reddit usa componentes web modernos (shreddit-*, editor de
texto Lexical) muy distintos de X/Threads, localizados en vivo antes de
escribir nada.

Construida el 21/09/2026. Estado de cada accion mas abajo.

Uso:
    python reddit_interact.py ensure-browser
    python reddit_interact.py health
    python reddit_interact.py feed
    python reddit_interact.py subreddit <nombre>
    python reddit_interact.py search "consulta" [subreddit]
    python reddit_interact.py thread <url>
    python reddit_interact.py comment <url> "texto"

CONFIRMADO EN VIVO el 21/09 (probado de verdad, no solo escrito):
- feed, subreddit, search, thread: lectura de texto, funciona.
- comment: el cuadro de comentario real (`shreddit-composer`, editor
  Lexical) esta colapsado a altura 0 hasta que se hace clic en su
  contenedor visible (`comment-composer-host`, altura ~19px) - Playwright
  rechaza el clic normal por "elemento no visible" porque el propio
  `shreddit-composer` mide 0x0 hasta ese clic, asi que se hace clic por
  coordenadas crudas (`pg.mouse.click`) sobre el host en vez de sobre el
  composer. Tras eso el editor real aparece y el boton de envio se llama
  literalmente "Comentar". Probado con un texto de prueba, cancelado con
  el boton "Cancelar" antes de enviar nada real - la mecanica de escritura
  esta confirmada, el envio real se confirma con la primera accion
  ejecutada de verdad (ver diario/2026-09-21.md).

BUG/LIMITACION conocida desde el dia 1 (no una sorpresa futura): la
pagina de normas de una comunidad (`/r/<sub>/about/rules/`) no siempre
carga el contenido completo con una espera corta - si sale vacia o
truncada, mirar directamente la pagina principal del subreddit (la
descripcion y los posts fijados suelen bastar) o reintentar con mas
espera, nunca dar una comunidad por "sin normas" solo porque la pagina de
reglas salio vacia.

No hay seguro de "cuenta activa" en cada accion como en X/Threads - ver
la nota razonada en SISTEMA_DIARIO_REDDIT/REGLAS.md ("Seguro de cuenta
activa"): Reddit no permite cambiar de cuenta con un solo toque como
Meta, asi que health() lo comprueba una vez por sesion y no se repite en
cada comentario.
"""
import csv
import os
import re
import sys
import time
import subprocess
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from scan_common import ActionTargetNotFound, AlreadyCommented, check_length  # compartido entre redes, 23/09
from x_interact import _check_spanish_orthography  # reutilizado, no duplicado

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
# Mismo perfil dedicado que x_interact.py/threads_interact.py - David logueo
# u/AutoraDemoEscritor ahi el 21/09/2026, la sesion se queda guardada igual
# que en cualquier navegador normal.
EDGE_USER_DATA = r"C:\Temp\rrss-autorademo-edge"
MY_USERNAME = "AutoraDemoEscritor"
# BUG REAL encontrado el 28/09/2026 revisando esta PR: exigir la variable de
# entorno REDDIT_ACCOUNT_EMAIL sin valor por defecto rompia _health_check()
# de inmediato en cualquier maquina donde esa variable no estuviera puesta
# (confirmado en vivo - no lo estaba). Se mantiene la posibilidad de sacar
# el email del codigo fuente (quien quiera hacerlo solo tiene que exportar
# la variable), pero con un valor por defecto para no romper el despliegue
# actual el dia que esto se fusione.
MY_ACCOUNT_EMAIL = os.environ.get("REDDIT_ACCOUNT_EMAIL", "user@example.com").strip()
REGISTRO_CSV = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_REDDIT", "registro_interacciones.csv")

# Mismo seguro que las otras dos herramientas - parar de inmediato ante
# cualquier aviso real de spam/actividad inusual/cuenta restringida.
BOT_WARNING_SIGNALS = [
    "unusual activity",
    "actividad inusual",
    "actividad sospechosa",
    "suspicious activity",
    "account suspended",
    "cuenta suspendida",
    "cuenta ha sido suspendida",
    "temporarily banned",
    "verify you're human",
    "verifica que eres humano",
    "confirma que eres humano",
    "you've been rate limited",
    "te has quedado sin limite",
    "this action is limited",
]


class BotWarningDetected(RuntimeError):
    pass


def _check_bot_warning(pg):
    try:
        text = pg.inner_text("body").lower()
    except Exception as exc:
        raise BotWarningDetected("No se pudo leer la pantalla para verificar avisos de bloqueo; detener la sesión") from exc
    for signal in BOT_WARNING_SIGNALS:
        if signal in text:
            raise BotWarningDetected(
                f"AVISO REAL DETECTADO EN PANTALLA: \"{signal}\". "
                "Parando de inmediato. Avisar a David antes de reintentar."
            )


# _check_spanish_orthography importada de x_interact.py (23/09).


def _check_length(text, limit=10000):
    check_length(text, limit)


def _cdp_alive():
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3)
        return True
    except Exception:
        return False


def ensure_browser():
    """Comprueba que el Edge real con CDP 9223 esta arriba; si no, lo abre
    con el perfil dedicado (nunca el perfil real por defecto de David, ver
    comentario junto a EDGE_USER_DATA en threads_interact.py)."""
    if _cdp_alive():
        print("CDP ya activo en 9223")
        return
    print("CDP no responde, abriendo Edge (perfil dedicado de la automatizacion)...")
    subprocess.Popen([
        EDGE_EXE,
        "--remote-debugging-port=9223",
        f"--user-data-dir={EDGE_USER_DATA}",
        "https://www.reddit.com/",
    ])
    for _ in range(20):
        time.sleep(1)
        if _cdp_alive():
            print("CDP arriba.")
            return
    raise RuntimeError("Edge no respondio en CDP 9223 tras 20s")


def _connect():
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0]
    try:
        import browser_lean
        browser_lean.apply(ctx)         # 07/10: sin imagenes/video/fuentes
    except Exception:
        pass
    pages = [pg for pg in ctx.pages if urllib.parse.urlsplit(pg.url).hostname in {"reddit.com", "www.reddit.com"}]
    pg = pages[-1] if pages else ctx.new_page()
    return p, pg


def _health_check(pg):
    """Nucleo de health(), extraido el 22/09 (mismo patron que las otras
    herramientas) para que reddit_scan.py pueda reutilizar la misma
    conexion. Devuelve (ok, mensaje) - el mensaje NUNCA incluye el email
    (dato personal), solo confirma coincidencia o no."""
    pg.goto("https://www.reddit.com/settings/", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    text = pg.inner_text("body")
    if "Ajustes - Cuenta" not in text and "Account settings" not in text:
        return False, "PROBLEMA: no se detecta sesion logueada en Reddit - puede haber caducado la cookie."
    if not MY_ACCOUNT_EMAIL:
        return False, (
            "PROBLEMA: falta REDDIT_ACCOUNT_EMAIL en el entorno local. "
            "No ejecutar escrituras sin poder verificar la cuenta activa."
        )
    if MY_ACCOUNT_EMAIL not in text:
        return False, (
            "PROBLEMA REAL: la cuenta activa en esta sesion NO es la de "
            f"u/{MY_USERNAME} (el email no coincide). No ejecutar ninguna "
            "accion - cambiar de cuenta en Reddit antes de continuar."
        )
    return True, f"OK: sesion logueada y cuenta activa confirmada como u/{MY_USERNAME}."


def health():
    p, pg = _connect()
    try:
        ok, msg = _health_check(pg)
        print(msg)
    finally:
        p.stop()


_THREAD_ATTRS = [
    "permalink", "post-title", "author", "comment-count", "score",
    "subreddit-prefixed-name", "post-type",
]


def _extract_threads(pg, limit=25):
    """Vuelca los hilos visibles en un listado (feed/subreddit/busqueda)
    leyendo los atributos reales del componente web `<shreddit-post>` -
    confirmado en vivo el 22/09: permalink/post-title/author/comment-count/
    score/subreddit-prefixed-name vienen ya limpios como atributos HTML, sin
    falta parsear texto suelto como en dump_feed/dump_subreddit (equivalente
    a `_extract_posts` de threads_interact.py/instagram_interact.py, pero
    mas simple porque Reddit expone esto directamente)."""
    posts = pg.locator("shreddit-post")
    n = min(posts.count(), limit)
    out = []
    for i in range(n):
        el = posts.nth(i)
        vals = {a: el.get_attribute(a) for a in _THREAD_ATTRS}
        permalink = vals.get("permalink")
        if not permalink:
            continue
        out.append({
            "subreddit": vals.get("subreddit-prefixed-name") or "",
            "title": vals.get("post-title") or "",
            "url": f"https://www.reddit.com{permalink}",
            "author": vals.get("author") or "",
            "comment_count": int(vals.get("comment-count") or 0),
            "score": int(vals.get("score") or 0),
        })
    return out


def _dump_feed(pg):
    pg.goto("https://www.reddit.com/", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    print(pg.inner_text("body")[:6000])


def dump_feed():
    p, pg = _connect()
    try:
        _dump_feed(pg)
    finally:
        p.stop()


def _normalize_subreddit_name(value):
    """Normaliza solo prefijos Reddit reales; nunca usar str.lstrip("r/")."""
    if not isinstance(value, str):
        raise ValueError("subreddit debe ser texto")
    name = value.strip()
    if name.casefold().startswith("/r/"):
        name = name[3:]
    elif name.casefold().startswith("r/"):
        name = name[2:]
    elif name.startswith("/"):
        name = name[1:]
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("nombre de subreddit inválido")
    return name


def _dump_subreddit(pg, name, sort="hot"):
    name = _normalize_subreddit_name(name)
    suffix = "" if sort == "hot" else f"{sort}/"
    pg.goto(f"https://www.reddit.com/r/{name}/{suffix}", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2800)
    _check_bot_warning(pg)


def dump_subreddit(name, sort="hot"):
    p, pg = _connect()
    try:
        _dump_subreddit(pg, name, sort)
        print(pg.inner_text("body")[:6000])
    finally:
        p.stop()


def _dump_search(pg, query, subreddit=None):
    q = urllib.parse.quote(query)
    if subreddit:
        subreddit = _normalize_subreddit_name(subreddit)
        url = f"https://www.reddit.com/r/{subreddit}/search/?q={q}&restrict_sr=1&sort=new"
    else:
        url = f"https://www.reddit.com/search/?q={q}&sort=new"
    pg.goto(url, wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2800)
    _check_bot_warning(pg)


def dump_search(query, subreddit=None):
    p, pg = _connect()
    try:
        _dump_search(pg, query, subreddit)
        print(pg.inner_text("body")[:6000])
    finally:
        p.stop()


def dump_thread(url):
    """Vuelca el hilo COMPLETO (titulo, texto, comentarios existentes) -
    REDDIT.md es explicito en que nunca hay que comentar solo con el
    titular, hay que leer que se pidio, que respuestas ya tiene y si sigue
    vivo."""
    p, pg = _connect()
    try:
        if not url.startswith("http"):
            url = f"https://www.reddit.com{url}" if url.startswith("/") else f"https://www.reddit.com/{url}"
        pg.goto(url, wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(3000)
        _check_bot_warning(pg)
        print(pg.inner_text("body")[:8000])
    finally:
        p.stop()


def _expand_composer(pg):
    """El cuadro de comentario real (shreddit-composer, editor Lexical)
    mide 0x0 hasta que se hace clic en su contenedor colapsado
    (comment-composer-host, ~19px de alto) - confirmado en vivo el 21/09.
    Playwright rechaza el clic normal por "elemento no visible" porque el
    composer en si no tiene tamano todavia, asi que el clic se hace por
    coordenadas crudas sobre el host, no sobre el composer.

    BUG REAL encontrado en vivo el 25/09 en un hilo largo (mas de 3500px):
    bounding_box() da la posicion del host EN LA PAGINA, pero si el host
    esta mas abajo que la ventana visible actual (nunca se habia hecho
    scroll hasta el, a diferencia de hilos cortos donde ya estaba a la
    vista de entrada), pg.mouse.click con esas coordenadas cae fuera del
    viewport real y no hace nada - el composer se queda colapsado y el
    click posterior sobre su contenteditable falla por "elemento no
    visible" tras 30s de espera. Corregido forzando scroll_into_view_if_needed()
    antes de medir/clicar, igual que ya se hacia en otras redes."""
    host = pg.locator("comment-composer-host").first
    host.scroll_into_view_if_needed()
    pg.wait_for_timeout(300)
    box = host.bounding_box()
    if box is None:
        raise RuntimeError("no se encontro el cuadro de comentario (comment-composer-host) en esta pagina")
    pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.wait_for_timeout(1200)


# AlreadyCommented importada de scan_common (23/09, centralizada).



def _thread_identity(url):
    parts = urllib.parse.urlsplit(_validated_thread_url(url)).path.strip("/").split("/")
    return parts[1].casefold(), parts[3].casefold()


_CONFIRMED_HISTORY_RESULTS = {"confirmado", "publicado"}


def _comment_history_state(url):
    """Devuelve none|confirmed|uncertain sin convertir ausencia de estado en éxito."""
    if not os.path.exists(REGISTRO_CSV):
        return "none"
    target = _thread_identity(url)
    uncertain = False
    with open(REGISTRO_CSV, encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            kind = (row.get("tipo") or "").strip().casefold()
            if kind not in {"comment", "comentario", "reply", "respuesta"}:
                continue
            raw_url = (
                row.get("hilo_url") or row.get("url") or
                row.get("post_url") or row.get("post_resumen") or ""
            ).strip()
            if not raw_url:
                continue
            try:
                matches = _thread_identity(raw_url) == target
            except ValueError:
                continue
            if not matches:
                continue
            result = (row.get("resultado") or "").strip().casefold()
            if result in _CONFIRMED_HISTORY_RESULTS:
                return "confirmed"
            uncertain = True
    return "uncertain" if uncertain else "none"


def _already_commented_in_history(url):
    """Compatibilidad: True solo cuando el historial acredita publicación."""
    return _comment_history_state(url) == "confirmed"



def _already_commented(pg):
    """Reddit expone el autor de cada comentario como atributo real del
    componente web (`<shreddit-comment author="...">`, confirmado en vivo
    el 23/09) - mas simple y fiable que buscar texto: no hay riesgo de falso
    positivo por menciones, a diferencia de X."""
    comments = pg.locator("shreddit-comment")
    n = comments.count()
    for i in range(n):
        if (comments.nth(i).get_attribute("author") or "").lower() == MY_USERNAME.lower():
            return True
    return False



def _validated_thread_url(url):
    """Solo URL HTTPS del hilo raíz; nunca comentario, host ajeno o query."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Se requiere una URL de hilo Reddit")
    url = url.strip()
    if url.startswith("/"):
        url = "https://www.reddit.com" + url
    elif not url.startswith(("http://", "https://")):
        raise ValueError("Se requiere URL absoluta HTTPS o ruta /r/... del hilo")
    try:
        parts = urllib.parse.urlsplit(url)
        valid = (
            parts.scheme == "https"
            and parts.hostname in {"reddit.com", "www.reddit.com"}
            and not parts.username and not parts.password and parts.port is None
            and not parts.query and not parts.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("URL de hilo Reddit debe ser HTTPS oficial sin parámetros")
    # BUG REAL encontrado el 28/09/2026 probando esta PR con URLs reales de
    # esta sesion: el slug (parte cosmetica del titulo en la URL, la unica
    # que Reddit ignora al enrutar) solo aceptaba ASCII - cualquier post en
    # español con tilde/eñe en el titulo (la inmensa mayoria en r/libros y
    # r/escribir) quedaba rechazado como "no es el hilo raiz" y no se podia
    # ni votar ni comentar. El subreddit y el ID de hilo SI deben seguir
    # siendo estrictamente alfanumericos (esos son los que Reddit valida de
    # verdad), pero el slug puede ser cualquier cosa que no sea otra barra -
    # es justo lo que ya demuestra que /r/x/comments/id/ (sin slug) tambien
    # es una URL valida un poco mas abajo en este mismo fichero.
    if not re.fullmatch(
        r"/r/[A-Za-z0-9_]+/comments/[a-z0-9]+(?:/[^/]+)?/?",
        parts.path, re.I,
    ):
        raise ValueError("URL no corresponde al hilo raíz de Reddit")
    return url



def _thread_post_id(url):
    """ID base36 del hilo ya validado; la ruta canónica es /r/x/comments/ID/..."""
    parts = urllib.parse.urlsplit(_validated_thread_url(url)).path.strip("/").split("/")
    return parts[3].casefold()


def _visible_norm(value):
    return " ".join((value or "").split()).casefold()



def _assert_thread_destination(pg, expected_url):
    actual_url = _validated_thread_url(pg.url)
    actual = urllib.parse.urlsplit(actual_url).path.strip("/").split("/")
    expected = urllib.parse.urlsplit(expected_url).path.strip("/").split("/")
    if ((actual[1].casefold(), actual[3].casefold())
            != (expected[1].casefold(), expected[3].casefold())):
        raise RuntimeError("Reddit redirigió a otro hilo; no ejecutar acciones")



MICRO_MAX_WORDS = 8      # 07/10: David pide «una frasecita» breve y amable (antes 5 palabras)
MICRO_MAX_CHARS = 60
_URLISH = re.compile(r"https?://|www\.|\.(?:com|es|org|net)\b", re.IGNORECASE)


def _check_micro_comment(text):
    """Reddit solo admite microrrespuestas (03/10, decision de David): se nos
    reconocia como IA por comentar con texto elaborado. Ahora una palabra a cinco,
    sin justificar, sin preguntas ni enlaces: "Escribir.", "Machado, Lorca, Miguel
    Hernandez", "Ganas de mas." Cualquier otra cosa se rechaza."""
    stripped = (text or "").strip()
    words = re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", stripped)
    problems = []
    if not words:
        problems.append("vacio")
    if len(words) > MICRO_MAX_WORDS:
        problems.append(f"{len(words)} palabras (max {MICRO_MAX_WORDS})")
    if len(stripped) > MICRO_MAX_CHARS:
        problems.append(f"{len(stripped)} caracteres (max {MICRO_MAX_CHARS})")
    if "\n" in stripped:
        problems.append("una sola linea")
    if "?" in stripped:
        problems.append("sin preguntas")
    if _URLISH.search(stripped):
        problems.append("sin enlaces")
    if problems:
        raise ValueError(
            "comentario de Reddit debe ser una microrrespuesta sin justificar ("
            + "; ".join(problems) + "). Ejemplos: 'Escribir.', 'Machado, Lorca, Miguel Hernandez', "
            "'Ganas de mas.'"
        )


def comment(url, text):
    """Publica un comentario raiz en un hilo. Verifica que el texto
    aparezca en la pagina tras enviarlo, no solo que el clic no diera
    error - misma disciplina que el resto del proyecto."""
    _check_length(text)
    _check_micro_comment(text)
    _check_spanish_orthography(text)
<<<<<<< HEAD
    import voice_output_finalization as voice
    voice.inspect(text, network="reddit", queue="WEB")
=======
>>>>>>> origin/research/public-reuse-parent
    url = _validated_thread_url(url)
    history_state = _comment_history_state(url)
    if history_state == "confirmed":
        raise AlreadyCommented(
            f"El historial local ya confirma un comentario nuestro en {url}; no se repite."
        )
    if history_state == "uncertain":
        raise RuntimeError(
            f"El historial contiene un comentario incierto para {url}; "
            "revisar manualmente el hilo ANTES de reintentar"
        )
    p, pg = _connect()
    try:
        ok, msg = _health_check(pg)
        if not ok:
            raise RuntimeError(msg)
        pg.goto(url, wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        _assert_thread_destination(pg, url)
        if _already_commented(pg):
            raise AlreadyCommented(f"Ya hay un comentario nuestro en {url} - no se envia otro.")
        _expand_composer(pg)
        box = pg.locator("shreddit-composer [contenteditable='true']").first
        box.click()
        box.type(text, delay=8)
        pg.wait_for_timeout(500)
        pg.locator("shreddit-composer button", has_text="Comentar").first.click()
        pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        pg.reload(wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        _assert_thread_destination(pg, url)
        snippet = _visible_norm(text)[:60]
        confirmed = False
        comments = pg.locator("shreddit-comment")
        for idx in range(comments.count()):
            node = comments.nth(idx)
            if (node.get_attribute("author") or "").casefold() == MY_USERNAME.casefold():
                if snippet and snippet in _visible_norm(node.inner_text()):
                    confirmed = True
                    break
        if not confirmed:
            raise RuntimeError(
                "Comentario no confirmado tras recargar; revisar hilo ANTES de reintentar"
            )
        print("comentario publicado (confirmado tras recarga y autor)")
    finally:
        p.stop()


def _vote_widget_for_post(pg, thing_id):
    """Localiza el widget de voto (par de botones up/down) del POST
    principal, no el de un comentario cualquiera de la misma pagina - ambos
    usan el mismo componente `<shreddit-vote-animations thing-id="...">`,
    asi que hay que filtrar por el thing-id real del post (t3_...), nunca
    coger "el primero de la pagina" sin comprobar."""
    widgets = pg.locator(f'shreddit-vote-animations[thing-id="{thing_id}"]')
    if widgets.count() == 0:
        raise ActionTargetNotFound(f"no se encontro el widget de voto para {thing_id}")
    return widgets.first


def _vote_context_of_post(pg, thing_id):
    """Comprobar el título del post Reddit al que pertenece el botón de voto."""
    import like_context_policy as lcp
    post_id = thing_id.removeprefix("t3_")
    nodes = pg.locator("shreddit-post")
    for i in range(nodes.count()):
        node = nodes.nth(i)
        permalink = (node.get_attribute("permalink") or "").casefold()
        if not re.search(r"/comments/" + re.escape(post_id) + r"(?:/|$)", permalink):
            continue
        title = node.get_attribute("post-title") or ""
        post_type = (node.get_attribute("post-type") or "").casefold()
        sensitive = any(node.get_attribute(attr) in ("true", "1")
                        for attr in ("over-18", "nsfw", "is-nsfw"))
        return lcp.can_like(title, media_present=post_type not in ("text", "self"),
                            sensitive=sensitive)
    return False, "reddit_post_objetivo_sin_titulo_verificado"


def vote(url, direction="up"):
    """Vota (up/down) el post principal de un hilo. Descubierto en vivo el
    25/09 inspeccionando el shadow DOM real (Reddit no expone esto con
    aria-label ni data-testid legible desde fuera): cada post lleva un
    `<shreddit-vote-animations thing-id="t3_...">` con dos `<button
    data-action-bar-action="upvote|downvote">`; el estado actual se lee en
    `aria-pressed` de cada boton. Idempotente: si ya esta votado en la
    direccion pedida no vuelve a pulsar (un segundo clic en Reddit
    quita el voto en vez de repetirlo, asi que repetir por error
    deshacia un voto real ya puesto)."""
    if direction not in ("up", "down"):
        raise ValueError("direction debe ser 'up' o 'down'")
    url = _validated_thread_url(url)
    p, pg = _connect()
    try:
        ok, msg = _health_check(pg)
        if not ok:
            raise RuntimeError(msg)
        pg.goto(url, wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        _assert_thread_destination(pg, url)
        # El ID objetivo viene de la URL validada. No usar el primer
        # shreddit-post: Reddit puede insertar otros bloques en la página.
        thing_id = f"t3_{_thread_post_id(url)}"
        allowed, reason = _vote_context_of_post(pg, thing_id)
        if not allowed:
            raise ActionTargetNotFound(f"voto_rechazado_contexto:{reason}")
        widget = _vote_widget_for_post(pg, thing_id)
        btn = widget.locator(f'button[data-action-bar-action="{"upvote" if direction == "up" else "downvote"}"]')
        if btn.get_attribute("aria-pressed") == "true":
            print(f"ya estaba votado hacia '{direction}' - no se repite")
            return "already"
        btn.click()
        pg.wait_for_timeout(1000)
        _check_bot_warning(pg)
        if btn.get_attribute("aria-pressed") != "true":
            raise RuntimeError(
                f"voto '{direction}' no confirmado; revisar hilo ANTES de reintentar"
            )
        print(f"voto '{direction}' confirmado")
        return "created"
    finally:
        p.stop()


if __name__ == "__main__":
    def _dispatch():
        cmd = sys.argv[1] if len(sys.argv) > 1 else None
        if cmd == "ensure-browser":
            ensure_browser()
        elif cmd == "health":
            ensure_browser(); health()
        elif cmd == "feed":
            ensure_browser(); dump_feed()
        elif cmd == "subreddit":
            ensure_browser(); dump_subreddit(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "hot")
        elif cmd == "search":
            ensure_browser(); dump_search(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        elif cmd == "thread":
            ensure_browser(); dump_thread(sys.argv[2])
        elif cmd == "comment":
            ensure_browser(); comment(sys.argv[2], sys.argv[3])
        elif cmd == "vote":
            ensure_browser(); vote(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "up")
        else:
            print(__doc__)
            sys.exit(1)

    try:
        _dispatch()
    except BotWarningDetected as e:
        print(str(e))
        sys.exit(2)
