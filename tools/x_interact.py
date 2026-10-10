"""
Herramienta unica para el dia a dia de X: abrir el navegador real si hace
falta, leer donde hay actividad (timeline, listas, notificaciones) y
ejecutar acciones (responder, like, repost/cita, seguir, dejar de seguir).
Todo via CDP puerto 9223 sobre el Edge real ya logueado - mismo patron que
x_schedule_post.py.

Pensada para no tener que escribir un script nuevo cada sesion: es el punto
de entrada que SISTEMA_DIARIO_X/PROCESO.md espera que se use.

Uso:
    python x_interact.py ensure-browser
    python x_interact.py following-feed
    python x_interact.py list-feed <url_de_la_lista>
    python x_interact.py notifications
    python x_interact.py followers [handle]
    python x_interact.py profile [handle]
    python x_interact.py search "consulta de busqueda" [live|top]
    python x_interact.py explore
    python x_interact.py replies <url_del_tuit>
    python x_interact.py reply <url_del_tuit> "texto de la respuesta" [ruta/imagen.jpg]
    python x_interact.py like <url_del_tuit>
    python x_interact.py repost <url_del_tuit>
    python x_interact.py unrepost <url_del_tuit>
    python x_interact.py quote <url_del_tuit> "texto del comentario"
    python x_interact.py follow <handle>
    python x_interact.py unfollow <handle>
    python x_interact.py post "texto del post" [ruta/imagen.jpg]
    python x_interact.py pin "texto del post fijado"
    python x_interact.py thread "tuit 1" "tuit 2" "tuit 3" ...
    python x_interact.py health
    python x_interact.py daily

Cada comando de accion (reply/like/repost/quote/follow/unfollow) ejecuta
sobre la cuenta REAL en cuanto se llama - no pide confirmacion el mismo
script. La confirmacion de "esto se va a hacer" pasa siempre antes, en el
chat con David, tal como manda SISTEMA_DIARIO_X/REGLAS.md.

`daily` (anadido 22/09, optimizacion de consumo de tokens): hace en una
sola conexion/proceso lo que antes eran 8 llamadas sueltas (ensure-browser +
health + notifications + following-feed + 3 list-feed + explore) - mismo
contenido exacto, un solo bloque de salida con secciones claras en vez de 8
tool calls y 8 arranques de proceso/conexion CDP independientes. Si el
health check falla (sesion caducada o cuenta activa incorrecta), para ahi
mismo y no malgasta las siguientes navegaciones. Ver PROCESO.md.

Pipeline recomendado para el uso diario normal (anadido 22/09, ver
PROCESO.md para el detalle completo): `x_scan.py` (escanea y filtra
automaticamente, saca una lista corta de candidatos) -> Claude decide y
escribe un plan.json -> `x_execute.py plan.json` (ejecuta y registra solo,
sin que haya que escribir los CSV/ESTADO.md a mano). Este archivo sigue
siendo la base que ambos scripts importan como modulo.
"""
import os
import re
import sys
import time
import subprocess
import urllib.request
from urllib.parse import urlsplit
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))
from scan_common import ActionTargetNotFound, AlreadyCommented, check_length  # compartido entre redes, 23/09

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
# Cambiado el 17/09: el perfil real por defecto de David dejo de aceptar
# --remote-debugging-port (confirmado en vivo - Edge no escribe
# DevToolsActivePort ahi, pero SI lo hace en cualquier carpeta que no sea
# el perfil por defecto; probablemente una restriccion de seguridad de una
# version reciente de Chromium/Edge sobre el perfil "default"). Se usa un
# perfil dedicado solo para esta automatizacion - David tiene que loguear
# @davidportodiaz en X y Threads ahi UNA vez; despues la sesion se queda
# guardada igual que en el perfil real. Ver SISTEMA_DIARIO_X/README.md.
EDGE_USER_DATA = r"C:\Temp\rrss-davidporto-edge"

# Seguro anadido 17/09 a peticion explicita de David: si X muestra cualquier
# aviso de que nos ha detectado como bot / actividad inusual / cuenta
# restringida / verificacion humana, hay que parar TODO de inmediato, no
# seguir intentando acciones a ciegas. Frases reales conocidas de X (ingles
# y espanol, la cuenta puede mostrar cualquiera de los dos segun idioma del
# navegador) - lista ampliable si aparece una nueva por primera vez.
BOT_WARNING_SIGNALS = [
    "detected unusual activity",
    "actividad inusual",
    "temporarily restricted",
    "restringida temporalmente",
    "restringido temporalmente",
    "verify you're not a robot",
    "confirm you're human",
    "verifica que no eres un robot",
    "confirma que eres humano",
    "suspicious activity",
    "actividad sospechosa",
    "account has been locked",
    "cuenta ha sido bloqueada",
    "cuenta ha sido suspendida",
    "we've limited some of your account features",
    "hemos limitado algunas funciones de tu cuenta",
    "unusual login activity",
    "automated behavior",
    "comportamiento automatizado",
    "your account is temporarily locked",
]


class BotWarningDetected(RuntimeError):
    """Se lanza cuando X muestra un aviso real de deteccion de bot/actividad
    inusual - para todo el script de inmediato en vez de seguir."""


class WrongAccountActive(RuntimeError):
    """Se lanza cuando la cuenta ACTIVA de la sesion (la que ejecutaria la
    accion) no es davidportodiaz - ver _assert_active_account."""


class XWriteUnverified(RuntimeError):
    """Hubo posible escritura en X pero no un ACK comprobable: nunca replay."""


def _write_tap_with_uncertain_transport(callback, kind):
    """Después de llamar al control de escritura, un timeout NO prueba ausencia de tap.

    Es conservador: puede bloquear alguna escritura que realmente no ocurrió.
    Las paradas por seguridad conservan su propia excepción.
    """
    try:
        return callback()
    except (BotWarningDetected, WrongAccountActive, XWriteUnverified):
        raise
    except Exception as exc:
        raise XWriteUnverified(f"X: {kind} sin ACK tras intentar tap") from exc


def _check_warning_after_tap(pg):
    """No perder evidencia de escritura incierta ante CAPTCHA tras un tap."""
    try:
        _check_bot_warning(pg)
    except BotWarningDetected as exc:
        exc.possible_write = True
        raise


def _active_account_handle(pg):
    """Devuelve el handle de la cuenta REALMENTE activa en esta sesion de
    X (la que ejecuta follow/like/reply/post), no solo una cuenta que se
    pueda ver navegando a su perfil publico.

    BUG REAL encontrado el 21/09 (aviso de David sobre el equivalente en
    Threads, comprobado que X tenia el mismo fallo de fondo): tanto
    health() como cualquier otra funcion comprobaban la sesion navegando a
    x.com/davidportodiaz y mirando si "@davidportodiaz" aparecia en el
    texto - eso es SIEMPRE cierto independientemente de la cuenta activa,
    porque es una pagina de perfil publica, se ve igual la mires con la
    identidad que la mires. X permite tener varias cuentas logueadas a la
    vez con un selector de cuenta activa (el mismo mecanismo que causo el
    problema real en Threads) - la unica prueba real de cual esta activa
    es el boton `[data-testid="SideNav_AccountSwitcher_Button"]`, que
    siempre muestra el nombre/handle de la cuenta que se usaria para
    cualquier accion. Confirmado en vivo el 21/09."""
    btn = pg.locator('[data-testid="SideNav_AccountSwitcher_Button"]')
    if btn.count() == 0:
        return None
    try:
        text = btn.first.inner_text()
    except Exception:
        text = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("@"):
            return line[1:]
    # BUG REAL visto en vivo el 02/10: con el sidebar colapsado (solo
    # icono, p.ej. tras reabrir Edge con una ventana mas estrecha que
    # antes), el boton nunca muestra "Nombre\n@handle" como texto - solo
    # el avatar - asi que el bucle de arriba nunca encuentra nada aunque
    # la cuenta activa sea correcta. El avatar interno SI lleva el handle
    # de forma estable, independiente del ancho de la ventana:
    # data-testid="UserAvatar-Container-<handle>".
    try:
        avatar = btn.first.locator('[data-testid^="UserAvatar-Container-"]').first
        if avatar.count() > 0:
            testid = avatar.get_attribute("data-testid") or ""
            prefix = "UserAvatar-Container-"
            if testid.startswith(prefix):
                return testid[len(prefix):]
    except Exception:
        pass
    return None


def _assert_active_account(pg, expected="davidportodiaz"):
    """Seguro real anadido el 21/09: comprobar la cuenta activa antes de
    CUALQUIER accion de escritura (reply/like/repost/follow/unfollow/post).
    Reutiliza la pagina ya cargada - no anade una navegacion extra.

    BUG REAL encontrado el 22/09: esto comprobaba una sola vez, sin esperar,
    justo despues de un `goto(wait_until="domcontentloaded")` - en una pagina
    de un tuit individual (via `_goto_status`) el selector de cuenta a veces
    no habia terminado de hidratar todavia, y `_active_account_handle`
    devolvia None -> cancelaba una accion real perfectamente valida con un
    falso "CUENTA ACTIVA INCORRECTA: @None". No era peligroso (fallaba hacia
    el lado seguro, nunca ejecutaba con la cuenta equivocada) pero si poco
    fiable - abortaba respuestas/likes/follows buenos porque la pagina tardo
    un pelin mas de la cuenta. Corregido con el mismo reintento que ya usaba
    `_health_check` (hasta 5 intentos de 600ms) antes de dar el fallo por
    real."""
    active = _active_account_handle(pg)
    for _ in range(5):
        if active:
            break
        pg.wait_for_timeout(600)
        active = _active_account_handle(pg)
    if active != expected:
        raise WrongAccountActive(
            f"CUENTA ACTIVA INCORRECTA: esta sesion tiene activa @{active}, "
            f"NO @{expected}. Accion cancelada antes de ejecutarse. Cambiar "
            "de cuenta en X (selector de cuenta abajo a la izquierda) y "
            "volver a intentar."
        )


def _check_bot_warning(pg):
    beat()
    try:
        text = pg.inner_text("body").lower()
    except Exception as exc:
        raise BotWarningDetected(
            "No se pudo leer la pantalla para verificar avisos de bloqueo; "
            "acción detenida, revisar el navegador antes de reintentar"
        ) from exc
    for signal in BOT_WARNING_SIGNALS:
        if signal in text:
            raise BotWarningDetected(
                f"AVISO REAL DE X DETECTADO EN PANTALLA: \"{signal}\". "
                "Parando de inmediato, no se ejecuta ninguna accion mas. "
                "Avisar a David antes de volver a intentar nada."
            )


def _cdp_alive():
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3)
        return True
    except Exception:
        return False


def _edge_locking_profile_without_cdp():
    """Detecta si otro proceso ya tiene ABIERTO justo el perfil dedicado de
    esta automatizacion (EDGE_USER_DATA) sin el flag de depuracion -
    Chromium solo activa --remote-debugging-port en el PRIMER proceso que
    abre un user-data-dir, asi que un segundo intento no sirve de nada
    mientras el primero siga vivo. Con el perfil dedicado (ver comentario
    junto a EDGE_USER_DATA) esto deberia ser raro - nadie mas lo abre a
    mano - pero puede pasar si una sesion anterior lo dejo abierto sin
    depuracion. Devuelve True si detecta ese caso."""
    try:
        marker = EDGE_USER_DATA.split("\\")[-1]
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | "
             f"Where-Object {{ $_.CommandLine -like '*{marker}*' -and "
             f"$_.CommandLine -notlike '*remote-debugging-port=9223*' }}).Count"],
            capture_output=True, text=True, timeout=15,
        )
        count = int(out.stdout.strip() or "0")
        return count > 0
    except Exception:
        return False


def ensure_browser():
    """Comprueba que el Edge real con CDP 9223 esta arriba; si no, lo abre
    con el perfil dedicado de esta automatizacion (EDGE_USER_DATA - NUNCA
    el perfil real por defecto de David, que dejo de aceptar depuracion
    remota, ver comentario junto a la constante)."""
    if _cdp_alive():
        print("CDP ya activo en 9223")
        return
    print("CDP no responde, abriendo Edge (perfil dedicado de la automatizacion)...")
    subprocess.Popen([
        EDGE_EXE,
        "--remote-debugging-port=9223",
        f"--user-data-dir={EDGE_USER_DATA}",
        "https://x.com/home",
    ])
    for _ in range(20):
        time.sleep(1)
        if _cdp_alive():
            print("CDP arriba.")
            return
    if _edge_locking_profile_without_cdp():
        raise RuntimeError(
            "Edge no respondio en CDP 9223 tras 20s - causa probable: ya hay una "
            f"ventana de Edge abierta con el perfil dedicado ({EDGE_USER_DATA}) sin "
            "el flag de depuracion, y Chromium ignora --remote-debugging-port cuando "
            "el perfil ya esta en uso. Solucion: cerrar esa ventana y volver a "
            "ejecutar ensure-browser."
        )
    raise RuntimeError(
        "Edge no respondio en CDP 9223 tras 20s. Si esto pasa con el perfil dedicado "
        f"({EDGE_USER_DATA}) recien creado, comprobar a mano que Edge no muestre un "
        "aviso o dialogo bloqueante en primer plano - un perfil nuevo a veces pide "
        "confirmar idioma/importar datos antes de terminar de arrancar."
    )


import browser_common as bc

_BROWSER = bc.Browser("x", CDP_URL, {"x.com", "www.x.com", "twitter.com", "www.twitter.com"})


def beat():
    _BROWSER.watchdog.beat()


def start_watchdog(limit=300):
    _BROWSER.watchdog.start(limit)


def session():
    """Una sola conexion CDP para TODAS las acciones de un plan (06/10; antes cada like/follow abria un Playwright nuevo). `with x.session() as pg: ...`;
    dentro, `_connect()` devuelve esa misma pagina. Vigilante: sin actividad 300 s el proceso termina (browser_common.Watchdog)."""
    return _BROWSER.session()


def _connect():
    return _BROWSER.connect()


def _extract_articles(pg, limit=15):
    """Vuelca los tuits visibles: autor, cuando, texto, permalink. El
    permalink es lo importante - es lo que hay que pasar a reply/like/repost
    para no depender de que el texto siga siendo unico/visible despues.

    Descarta tuits promocionados (badge <span>Ad</span> que X renderiza en
    vez del handle) - confirmado en vivo el 29/09: sin este filtro,
    following-feed/list-feed/search devuelven anuncios como si fueran
    contenido real de cuentas seguidas, y en x_scan.py contaminaban ademas
    seed_pool (una semilla de "comentaristas" entera gastada en el publico
    generico de un anuncio, nada que ver con el nicho)."""
    arts = pg.locator("article")
    n = min(arts.count(), limit)
    out = []
    for i in range(n):
        a = arts.nth(i)
        if a.locator('span:text-is("Ad")').count() > 0:
            continue
        try:
            text = a.inner_text()
        except Exception:
            continue
        href = None
        links = a.locator('a[href*="/status/"]')
        if links.count() > 0:
            href = links.first.get_attribute("href")
        out.append((href, text[:280]))
    return out


def _dump_following_feed(pg):
    pg.goto("https://x.com/home", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2000)
    _check_bot_warning(pg)
    pg.get_by_role("tab", name="Following").click(timeout=8000)
    pg.wait_for_timeout(2500)
    for href, text in _extract_articles(pg):
        print("---")
        print("URL:", f"https://x.com{href}" if href and href.startswith("/") else href)
        print(text)


def dump_following_feed():
    p, pg = _connect()
    try:
        _dump_following_feed(pg)
    finally:
        p.stop()


def _dump_list_feed(pg, list_url):
    pg.goto(list_url, wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(3000)
    _check_bot_warning(pg)
    for href, text in _extract_articles(pg):
        print("---")
        print("URL:", f"https://x.com{href}" if href and href.startswith("/") else href)
        print(text)


def dump_list_feed(list_url):
    p, pg = _connect()
    try:
        _dump_list_feed(pg, list_url)
    finally:
        p.stop()


# Las 3 Listas fijas del disparador diario (ver PROCESO.md) - centralizadas
# aqui para que `daily` no dependa de copiar las URLs a mano dos veces.
DAILY_LISTS = [
    ("Editoriales ilustracion", "https://x.com/i/lists/1712399650060210560"),
    ("Editoriales", "https://x.com/i/lists/168792611"),
    ("Lo que leemos", "https://x.com/i/lists/1298202194538373120"),
]


def _dump_search(pg, query, mode="live"):
    import urllib.parse
    q = urllib.parse.quote(query)
    url = f"https://x.com/search?q={q}&src=typed_query"
    if mode == "live":
        url += "&f=live"
    pg.goto(url, wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2800)
    _check_bot_warning(pg)
    arts = _extract_articles(pg, limit=15)
    if not arts:
        print("sin resultados (o X no cargo nada en pantalla)")
        return
    for href, text in arts:
        print("---")
        print("URL:", f"https://x.com{href}" if href and href.startswith("/") else href)
        print(text)


def dump_search(query, mode="live"):
    """Busca en X de verdad (no solo las 3 Listas ni las 34 cuentas curadas) -
    anadido 17/09 porque limitarse a un circulo fijo es quedarse ciego a
    donde de verdad esta la variedad de lectores. 'live' (por defecto) usa
    la pestana Latest de X - lo mas reciente, que es lo que importa para
    responder mientras el post esta fresco; 'top' usa la pestana por
    defecto (Top, mas volumen pero menos fresco). Sirve tanto para
    hashtags (#NovelaJuvenil) como para busquedas de intencion en lenguaje
    natural (p.ej. 'recomendadme un libro de fantasia juvenil')."""
    p, pg = _connect()
    try:
        _dump_search(pg, query, mode)
    finally:
        p.stop()


def _dump_explore(pg):
    """Filtrado anadido 23/09 tras ver en vivo que el volcado crudo de
    Explore (hasta 4000 caracteres) traia sobre todo marcadores de futbol y
    la seccion "Posts For You" (memes/virales sin relacion), sin producir
    NUNCA un candidato real en la lista filtrada de x_scan.py - puro coste
    de tokens sin beneficio. Se corta la salida justo antes de "Posts For
    You" (esa seccion es siempre generica) y se descartan lineas que son
    solo un marcador de resultado deportivo (codigo de equipo o numero
    suelto), quedandose con tendencias/noticias/sugerencias de seguimiento,
    que es lo unico que alguna vez ha aportado una pista literaria real."""
    pg.goto("https://x.com/explore", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    text = pg.inner_text("main")[:4000]
    text = text.split("Posts For You")[0]
    score_line_re = __import__("re").compile(r"^([A-Z]{2,4}|\d{1,2}|Final|[A-Z][a-z]{2} \d{1,2})$")
    lines = [ln for ln in text.splitlines() if not score_line_re.match(ln.strip())]
    print("\n".join(lines).strip()[:1500])


def dump_explore():
    """Vuelca la pestana Explore/Trending de X (que tendencias reales hay
    ahora mismo en Espana) - anadida 17/09 a peticion de David: la busqueda
    por frase exacta es UNA herramienta, no el metodo entero. Explore es la
    forma de ver novedades/tendencias genericas sin tener que adivinar antes
    una palabra clave concreta - a veces una tendencia del dia (un premio
    literario, una noticia editorial) es mejor punto de entrada que
    cualquier busqueda ceñida."""
    p, pg = _connect()
    try:
        _dump_explore(pg)
    finally:
        p.stop()


def dump_replies(status_url):
    """Vuelca el post principal Y las respuestas que tiene debajo - anadido
    17/09 a peticion de David: la comunidad real no esta solo en la cuenta
    grande que escribio el post, esta en quien comenta de verdad debajo,
    aunque tenga pocos seguidores. Sirve para encontrar comentaristas
    activos a los que seguir/interactuar por su cuenta, no solo responder
    al post original."""
    p, pg = _connect()
    try:
        _goto_status(pg, status_url)  # devuelve (art, index), no hace falta aqui
        pg.wait_for_timeout(1200)
        arts = _extract_articles(pg, limit=20)
        if not arts:
            print("no se encontraron respuestas (o el post no cargo)")
            return
        for href, text in arts:
            print("---")
            print("URL:", f"https://x.com{href}" if href and href.startswith("/") else href)
            print(text)
    finally:
        p.stop()


def _dump_notifications(pg):
    pg.goto("https://x.com/notifications", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    print(pg.inner_text("main")[:4000])


def dump_notifications():
    p, pg = _connect()
    try:
        _dump_notifications(pg)
    finally:
        p.stop()


def _notification_candidates(pg):
    """Version accionable de notifications, anadida 23/09 a peticion
    explicita de David tras ver que la reciprocidad (maxima prioridad segun
    REGLAS.md) nunca se traducia en acciones reales: `_dump_notifications`
    solo imprime texto crudo SIN URL/handle estructurado por elemento, asi
    que nunca era posible pasar un item de notificaciones a
    reply_to()/like()/follow() sin ir a buscar el dato a mano - la
    prioridad maxima del sistema era, en la practica, inaccionable.

    Investigado en vivo el 23/09: cada notificacion es un
    `[data-testid="cellInnerDiv"]` (NO un `<article>` como el timeline, ni
    `UserCell` como la lista de seguidores - los dos intentos previos con
    esos selectores devolvian 0 resultados en esta pagina). Cada celda
    contiene uno o mas `[data-testid="UserAvatar-Container-<handle>"]` con
    el @handle EXACTO (mas fiable que el nombre mostrado, que no tiene por
    que coincidir), y si la notificacion referencia un post real (un reply
    directo a nosotros, tipicamente) trae ademas un enlace
    `a[href*="/status/"]`.

    Devuelve una lista de dicts, uno por celda con contenido real:
    {"handles": [...], "url": str|None, "kind_hint": "reply_recibido"|
    "nuevo_seguidor"|"reciprocidad_sin_url", "text": str}."""
    pg.goto("https://x.com/notifications", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    out = []
    cells = pg.locator('[data-testid="cellInnerDiv"]')
    for i in range(cells.count()):
        c = cells.nth(i)
        try:
            text = c.inner_text()
        except Exception:
            continue
        if not text.strip():
            continue
        links = c.locator('a[href*="/status/"]')
        url = links.first.get_attribute("href") if links.count() > 0 else None
        if url and url.startswith("/"):
            url = f"https://x.com{url}"
        avatars = c.locator('[data-testid^="UserAvatar-Container-"]')
        handles = []
        for j in range(avatars.count()):
            tid = avatars.nth(j).get_attribute("data-testid") or ""
            h = tid.replace("UserAvatar-Container-", "")
            if h and h not in handles:
                handles.append(h)
        if not handles:
            continue  # notificacion de sistema (union a comunidad, etc.), no accionable
        if url:
            kind_hint = "reply_recibido"
        elif "followed you" in text:
            kind_hint = "nuevo_seguidor"
        else:
            kind_hint = "reciprocidad_sin_url"  # dieron like/repost, sin post nuestro nuevo que enlazar
        out.append({"handles": handles, "url": url, "kind_hint": kind_hint, "text": text[:200].replace("\n", " ")})
    return out


def dump_followers(handle=None):
    """Vuelca la lista real de seguidores (handle + bio corta, una linea por
    cuenta). Pensado para la revision periodica de COMUNIDAD.md: cruzar quien
    nos sigue de verdad ahora mismo contra la tabla de reciprocidad y contra
    Following, no para uso diario."""
    p, pg = _connect()
    try:
        h = handle or "davidportodiaz"
        pg.goto(f"https://x.com/{h}/followers", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        cells = pg.locator('[data-testid="UserCell"]')
        n = cells.count()
        if n == 0:
            print("no se encontraron seguidores en pantalla (o la lista esta vacia)")
            return
        for i in range(n):
            try:
                line = cells.nth(i).inner_text().replace("\n", " | ")
            except Exception:
                continue
            print(line)
    finally:
        p.stop()


def dump_profile(handle=None):
    """BUG REAL visto en vivo el 21/09: a diferencia de following-feed/list-feed/
    search, esto solo volcaba inner_text sin URL por tuit - obligaba a ir a
    buscar el permalink a mano (con search o abriendo el perfil en el
    navegador real) para poder pasarselo despues a reply/like/repost. Mismo
    patron que el resto de comandos ahora: cabecera del perfil primero
    (bio, contadores) y luego cada post con su URL via _extract_articles."""
    p, pg = _connect()
    try:
        url = f"https://x.com/{handle}" if handle else "https://x.com/davidportodiaz"
        pg.goto(url, wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2200)
        _check_bot_warning(pg)
        header = pg.inner_text("main")[:700]
        print(header)
        print("=== posts (con URL) ===")
        for href, text in _extract_articles(pg):
            print("---")
            print("URL:", f"https://x.com{href}" if href and href.startswith("/") else href)
            print(text)
    finally:
        p.stop()



def _validated_status_url(status_url):
    """URL de status X/Twitter exacta; nunca navegar a un host arbitrario."""
    if not isinstance(status_url, str) or not status_url.strip():
        raise ValueError("Se requiere status URL/ID de X")
    value = status_url.strip()
    if re.fullmatch(r"\d+", value):
        return f"https://x.com/i/web/status/{value}"
    if value.startswith("/"):
        value = "https://x.com" + value
    parsed = urlsplit(value)
    if (parsed.scheme != "https"
            or parsed.hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
            or parsed.username or parsed.password or parsed.port):
        raise ValueError("Status debe pertenecer a x.com/twitter.com por HTTPS")
    parts = parsed.path.strip("/").split("/")
    valid = (
        len(parts) >= 3
        and ((parts[0] == "i" and parts[1] == "web" and len(parts) >= 4
              and parts[2] == "status" and re.fullmatch(r"\d+", parts[3]))
             or (parts[1] == "status" and re.fullmatch(r"[A-Za-z0-9_]{1,15}", parts[0])
                 and re.fullmatch(r"\d+", parts[2])))
    )
    if not valid:
        raise ValueError("URL no corresponde a un status canónico de X")
    target_id = parts[3] if parts[0] == "i" else parts[2]
    if parts[0] == "i":
        return f"https://x.com/i/web/status/{target_id}"
    return f"https://x.com/{parts[0]}/status/{target_id}"



def _status_id(status_url):
    """Extrae el ID numerico final de una URL/handle de status - usado para
    localizar el articulo REAL dentro de la pagina (ver bug real descrito en
    _goto_status)."""
    m = re.search(r"/status/(\d+)", status_url) or re.search(r"^(\d+)$", status_url.strip())
    return m.group(1) if m else None


def _goto_status(pg, status_url):
    """Punto de paso unico de reply_to/like/repost/unrepost - por eso el
    seguro de cuenta activa (anadido 21/09) se comprueba aqui una sola vez
    en vez de repetirlo en cada funcion.

    BUG REAL encontrado en vivo el 25/09 (mismo tipo de confusion ya
    corregida en Mastodon el 24/09 - ancestro/descendiente, nunca se habia
    comprobado en X): en un hilo con mas de un nivel (post original ->
    respuesta A -> respuesta B, con status_url apuntando a B), la pagina de
    permalink renderiza TODOS los antecesores como <article> propios ANTES
    del tuit al que en realidad se navego - `pg.locator("article").first`
    coge el antecesor de arriba del todo, NO el tuit objetivo. Esto hacia
    que reply_to/like/repost actuaran sobre el tuit equivocado (el mas
    antiguo de la cadena) en cualquier respuesta a una respuesta, y que
    `_already_commented` diera falsos positivos si YA se habia respondido a
    un antecesor mas arriba en el mismo hilo. Corregido buscando, entre
    todos los <article> cargados, el que de verdad tiene un enlace de
    permalink a ESE id concreto (`a[href$="/status/<id>"]`, sin el sufijo
    "/analytics" que tambien contiene el id) - confirmado en vivo comparando
    los hrefs reales de cada articulo. Si no se encuentra (id no extraible,
    o pagina con estructura distinta), se cae al comportamiento antiguo
    (`.first`) en vez de fallar duro."""
    status_url = _validated_status_url(status_url)
    pg.goto(status_url, wait_until="domcontentloaded", timeout=50000)
    _check_bot_warning(pg)
    _assert_active_account(pg)
    target_id = _status_id(status_url)
    arts = pg.locator("article")
    if not target_id:
        raise ActionTargetNotFound(
            f"no se pudo extraer un status ID numérico de {status_url!r}"
        )
    index = None
    # La página hidrata los artículos progresivamente. Esperar al status
    # EXACTO; nunca caer al primer artículo, porque en un hilo puede ser un
    # antecesor distinto y una escritura sobre él sería irrecuperable.
    for _ in range(6):
        n = arts.count()
        for i in range(n):
            if arts.nth(i).locator(f'a[href$="/status/{target_id}"]').count() > 0:
                index = i
                break
        if index is not None:
            break
        pg.wait_for_timeout(600)
    if index is None:
        raise ActionTargetNotFound(
            f"no se encontró el status objetivo {target_id}; no actuar sobre otro artículo"
        )
    art = arts.nth(index)
    # primer intento puede pillar la pagina a medio hidratar (visto en vivo:
    # el boton like/reply tarda un pelin mas que domcontentloaded) - esperar
    # a que el articulo objetivo tenga ya su barra de acciones antes de seguir.
    for _ in range(8):
        if art.locator('[data-testid="reply"]').count() > 0:
            break
        pg.wait_for_timeout(500)
    return art, index


def _attach_media(pg, media_path):
    """Adjunta una imagen/video al compositor abierto - mismo patron probado
    en x_schedule_post.py (expect_file_chooser es mas fiable que
    set_input_files directo, sobre todo con video). Reencodar antes si el
    video pesa >15MB aprox (ver REGLAS.md)."""
    # 06/10: el boton «Add photos or video» deja de ser pulsable en algunas disposiciones del compositor (tiempo agotado a los 30 s); el <input type=file> oculto del propio
    # compositor admite la subida directa y es mas fiable. El selector de archivos con clic queda de respaldo.
    inputs = pg.locator('input[data-testid="fileInput"], input[type="file"][accept*="image"]')
    if inputs.count() > 0:
        inputs.first.set_input_files(media_path)
    else:
        with pg.expect_file_chooser(timeout=10000) as fc_info:
            pg.locator('[aria-label="Add photos or video"]').first.click(timeout=10000)
        fc_info.value.set_files(media_path)
    pg.wait_for_timeout(4000)


def _click_send(pg, scope_dialog=False):
    """Envia el post/reply/hilo haciendo clic via JS directo, no con el
    click normal de Playwright. BUG REAL visto en vivo el 16/09: cuando el
    texto lleva una URL, la tarjeta de vista previa que genera X mete un
    overlay que intercepta el click normal sobre el boton de enviar (y a
    veces sobre el propio cuadro de texto) - Playwright lo detecta y aborta
    tras 30s en vez de forzar el click a ciegas. x_schedule_post.py ya tenia
    resuelto el mismo problema para el boton de Schedule con esta misma
    tecnica; aqui se aplica igual para tweetButton/tweetButtonInline.

    BUG REAL gemelo visto en vivo el 21/09: en la pagina de un tuit
    individual coexisten DOS composers a la vez - el modal que abre
    reply_to() (testid tweetButton) y la caja "Post your reply" siempre
    presente mas abajo en la pagina (testid tweetButtonInline, vacia y
    deshabilitada). El filtro anterior comprobaba `!b.disabled`, la
    propiedad nativa de <button>, pero estos son elementos con ARIA
    (aria-disabled="true") sin la propiedad disabled nativa - el filtro no
    los excluia de verdad y podia intentar hacer click en el boton vacio
    equivocado, o fallar la comprobacion de raro en raro segun el orden del
    DOM. Ahora se excluye explicitamente por aria-disabled, y reply/quote
    (unicos casos donde coexisten los dos composers) pasan
    `scope_dialog=True` para buscar el boton solo dentro de algun
    `[role="dialog"]` del modal, sin poder confundirlo nunca con el de la
    caja "Post your reply" de la pagina.

    BUG REAL visto en vivo el 21/09 (segunda vuelta del mismo bug): X anida
    DOS elementos con role="dialog" para un mismo modal (un wrapper externo
    y el dialog real) - usar querySelector (solo el primero) podia coger el
    wrapper vacio y no encontrar nunca el boton, aunque el modal estuviera
    perfectamente abierto y con texto. Cambiado a querySelectorAll sobre
    TODOS los [role="dialog"], igual que ya hacia Playwright al buscar el
    textarea con locator() (que sí busca en todos)."""
    clicked = pg.evaluate("""(scopeDialog) => {
        let roots = [document];
        if (scopeDialog) {
            roots = Array.from(document.querySelectorAll('[role="dialog"]'));
            if (roots.length === 0) return false;
        }
        const sel = '[data-testid="tweetButton"], [data-testid="tweetButtonInline"]';
        const btns = roots.flatMap(root => Array.from(root.querySelectorAll(sel)));
        const visible = btns.filter(b => {
            const r = b.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && !b.disabled && b.getAttribute('aria-disabled') !== 'true';
        });
        if (visible.length > 0) { visible[0].click(); return true; }
        return false;
    }""", scope_dialog)
    if not clicked:
        raise RuntimeError("no se encontro boton de enviar visible (tweetButton/tweetButtonInline)")
    pg.wait_for_timeout(2500)


def _check_length(text):
    """BUG REAL visto en vivo el 21/09: un texto 3 caracteres por encima del
    limite de X (280) deja el boton de enviar deshabilitado sin ningun
    aviso claro - _click_send solo podia fallar con un mensaje generico
    ('no se encontro boton de enviar') que no dice la causa real. Con esto
    se falla antes, con el motivo real, en vez de despues sin explicacion.
    Comprobacion en si compartida via scan_common.check_length (23/09).
    06/10: X cuenta cada enlace como 23 caracteres, sea cual sea su longitud (recuento ponderado): se mide asi."""
    check_length(re.sub(r"https?://\S+", "x" * 23, text), 280)


# Anadido 22/09 tras un error real y grave (no tecnico): 6 de 8
# respuestas/citas de una sesion salieron publicadas sin tildes ni "ene"
# ("anos" en vez de "anios", que ademas cambia el sentido a algo vulgar;
# "Azua" en vez de "Azua" con tilde, el nombre real de un autor citado).
# `tools/spellcheck_es.py` (ya existia en el repo, del pipeline de
# contenido) cubre las tildes de forma generica via diccionario - mucho
# mas robusto que una lista fija para ese caso. Lo que NO cubre es la
# "ene" perdida (n -> ñ), porque solo prueba variantes de vocal: "anos" o
# "senal" son palabras reales en el diccionario (distinto significado),
# asi que el chequeo de tildes nunca las marcaria. Esta lista corta cubre
# exactamente ese hueco - los casos reales vistos, no un intento de
# cobertura total.
_SPANISH_ENIE_RISK_WORDS = [
    "anos", "anio", "senal", "senor", "senora", "manana", "mananas",
    "pequeno", "pequena", "espanol", "espanola", "nino", "nina", "diseno",
    "extrano", "extrana", "sueno", "otono", "dueno", "montana", "campana",
    "compania", "companero", "companera", "ensenar", "enganar", "empenar",
]


def _check_spanish_orthography(text):
    """Comprueba tildes perdidas (via `spellcheck_es.py`, diccionario real)
    y "ene" perdida (via `_SPANISH_ENIE_RISK_WORDS`, su punto ciego) -
    juntos cubren el error real visto en vivo el 22/09. No sustituye una
    relectura real, pero atrapa el patron exacto que ya fallo una vez."""
    import re
    from spellcheck_es import check_missing_accents

    text = re.sub(r"https?://\S+", " ", text)      # los slugs de URL (…/portal-fantasy-espanol/) no llevan ene: no son texto
    problems = []
    tildes = check_missing_accents(text)
    problems += [w for w, _ in tildes]
    words = re.findall(r"[a-záéíóúñü]+", text.lower())
    problems += [w for w in words if w in _SPANISH_ENIE_RISK_WORDS]
    found = sorted(set(problems))
    if found:
        raise ValueError(
            f"posible tilde/ene perdida en: {', '.join(found)} - revisa el texto "
            "antes de publicar (ver REGLAS.md, seccion 'Ortografia real')"
        )


# AlreadyCommented importada de scan_common (23/09, centralizada - primer
# sitio donde se definio esta excepcion, ahora movida a un solo lugar
# compartido por las 8 redes que soportan reply/comment).


def _already_commented(pg, from_index=0):
    """Escanea los articulos de RESPUESTA visibles bajo el tuit objetivo
    (todo lo que viene DESPUES de `from_index`, el indice real del tuit al
    que se navego - ver bug real corregido en `_goto_status` el 25/09)
    buscando uno cuyo AUTOR seamos nosotros, via el mismo
    `UserAvatar-Container-<handle>` que ya identifica de forma fiable al
    autor de un tuit en notifications. No basta con buscar el texto
    "davidportodiaz" en la pagina entera: un post que nos responde a
    NOSOTROS incluye "Replying to @davidportodiaz" en su propio texto, lo
    que daria un falso positivo si se buscara la cadena suelta en vez del
    autor real de cada respuesta.

    BUG REAL corregido el 25/09: antes se escaneaba siempre desde el indice
    1 asumiendo un hilo de un solo nivel (original + respuestas). En un
    hilo mas profundo, cualquier respuesta NUESTRA a un ANTECESOR (un nivel
    por encima del tuit objetivo real) aparecia tambien en ese rango y daba
    un falso "ya comentado" aunque nunca se hubiera respondido al tuit
    concreto que se queria responder ahora - visto en vivo con un hilo real
    de @VekaDuncan donde David ya habia respondido al post ORIGINAL pero no
    a la respuesta nueva de Veka, y el chequeo antiguo lo bloqueaba igual."""
    arts = pg.locator("article")
    n = arts.count()
    for i in range(from_index + 1, n):
        if arts.nth(i).locator('[data-testid="UserAvatar-Container-davidportodiaz"]').count() > 0:
            return True
    return False


def reply_to(status_url, text, media_path=None):
    _check_length(text)
    _check_spanish_orthography(text)
    p, pg = _connect()
    try:
        art, index = _goto_status(pg, status_url)
        if _already_commented(pg, index):
            raise AlreadyCommented(
                f"Ya hay un comentario nuestro debajo de {status_url} - no se "
                "envia un segundo comentario al mismo post."
            )
        box = pg.locator('[role="dialog"] [data-testid="tweetTextarea_0"]').first
        # BUG REAL visto en vivo el 02/10: el click sobre "reply" a veces no
        # abre el dialogo (DOM re-renderizado tras el scroll de _goto_status,
        # el mismo tipo de desincronizacion ya visto en like()) - esperar
        # 30s por un cuadro de texto que nunca va a aparecer. Mismo remedio
        # que en like(): reintentar el click de apertura en vez de confiar
        # en uno solo, con una espera corta por intento.
        opened = False
        for _ in range(3):
            if box.is_visible():
                opened = True
                break
            art.locator('[data-testid="reply"]').first.click()
            try:
                box.wait_for(state="visible", timeout=4000)
                opened = True
                break
            except Exception:
                pg.wait_for_timeout(600)
        if not opened:
            raise ActionTargetNotFound(
                f"no se abrio el dialogo de respuesta tras 3 intentos en {status_url}"
            )
        # BUG REAL visto en vivo el 22/09: el mismo overlay de tarjeta de
        # vista previa que ya rompia el click en el compositor de citas
        # (ver repost()) tambien rompe aqui cuando el tuit al que se
        # responde lleva un enlace (genera su propia tarjeta de preview en
        # el dialogo de reply) - timeout de 30s en el primer click sobre el
        # cuadro de texto. Mismo remedio: force=True salta el hit-test.
        box.click(force=True)
        box.type(text, delay=15)
        pg.wait_for_timeout(800)
        if media_path:
            _attach_media(pg, media_path)
        _write_tap_with_uncertain_transport(
            lambda: _click_send(pg, scope_dialog=True), "reply")
        _check_warning_after_tap(pg)
        # Sondeo hasta 4s en vez de una sola comprobacion tras volver a
        # navegar - bug real visto en vivo el 29/09 (misma clase que el de
        # like()): recargar la pagina del status y releer todas las
        # respuestas es mas pesado que un simple boton, asi que una sola
        # comprobacion inmediata daba falso negativo en la mayoria de una
        # tanda de 9 (6/9 "fallos" resultaron ser replies que SI se habian
        # publicado, confirmado reintentando reply_to() sobre las mismas
        # URLs: AlreadyCommented salto de inmediato en vez de duplicar).
        confirmed = False
        for attempt in range(5):
            _, refreshed_index = _write_tap_with_uncertain_transport(
                lambda: _goto_status(pg, status_url), "reply-verificacion")
            if _write_tap_with_uncertain_transport(
                    lambda: _already_commented(pg, refreshed_index), "reply-verificacion"):
                confirmed = True
                break
            if attempt < 4:
                _write_tap_with_uncertain_transport(
                    lambda: pg.wait_for_timeout(800), "reply-verificacion")
        if not confirmed:
            raise XWriteUnverified(
                "X: reply no confirmada tras volver al status; revisar antes de reintentar"
            )
        print("reply enviada y confirmada")
        return "created"
    finally:
        p.stop()


def _like_context_of_article(art):
    """Lee el cuerpo del status OBJETIVO en el DOM, no el plan ni un ancestro."""
    import like_context_policy as lcp
    text_node = art.locator('[data-testid="tweetText"]')
    body = text_node.first.inner_text() if text_node.count() else ""
    media = bool(art.locator(
        '[data-testid="tweetPhoto"], [data-testid="videoPlayer"], video'
    ).count())
    return lcp.can_like(body, media_present=media)


def like(status_url):
    p, pg = _connect()
    try:
        art, _ = _goto_status(pg, status_url)
        allowed, reason = _like_context_of_article(art)
        if not allowed:
            raise ProfileRejected(f"like_contexto:{reason}")
        unlike = art.locator('[data-testid="unlike"]')
        if unlike.count() > 0:
            print("ese status ya tenía like")
            return "already"
        like_btn = art.locator('[data-testid="like"]')
        if like_btn.count() != 1:
            raise ActionTargetNotFound(
                "X: botón like ausente o ambiguo; no asumir que ya estaba dado"
            )
        _write_tap_with_uncertain_transport(lambda: like_btn.first.click(), "like")
        _check_warning_after_tap(pg)
        # Espera fija de 1200ms sustituida por sondeo hasta 3s - bug real
        # visto en vivo el 29/09: en tandas largas, el re-render del boton
        # unlike a veces tarda mas de 1200ms y el check original daba un
        # falso negativo (4 de 5 "fallos" en una tanda de 37 resultaron ser
        # likes que SI se habian aplicado, confirmado navegando de nuevo al
        # status tras el hecho).
        confirmed = False
        for _ in range(5):
            if _write_tap_with_uncertain_transport(
                    lambda: art.locator('[data-testid="unlike"]').count(), "like-verificacion") == 1:
                confirmed = True
                break
            _write_tap_with_uncertain_transport(
                lambda: pg.wait_for_timeout(600), "like-verificacion")
        if not confirmed:
            raise XWriteUnverified("X: like no confirmado; revisar status antes de reintentar")
        print("like dado (confirmado)")
        return "created"
    finally:
        p.stop()


def _click_menuitem(pg, name):
    """Clic por JS directo sobre un [role="menuitem"] cuyo texto contenga
    `name`. BUG REAL visto en vivo el 17/09: el mismo overlay de tarjeta de
    vista previa (ya resuelto para el boton de enviar en _click_send) puede
    interceptar tambien el menu Repost/Quote cuando el post original lleva
    un enlace - Playwright aborta con 'intercepts pointer events' igual que
    antes. Mismo remedio: saltarse el hit-test de Playwright."""
    clicked = pg.evaluate("""(name) => {
        const items = document.querySelectorAll('[role="menuitem"]');
        for (const el of items) {
            if (el.innerText && el.innerText.trim().toLowerCase().includes(name.toLowerCase())) {
                el.click();
                return true;
            }
        }
        return false;
    }""", name)
    if not clicked:
        raise RuntimeError(f"no se encontro menuitem visible con texto '{name}'")
    pg.wait_for_timeout(800)


def delete_post(status_url, text_snippet=None):
    """Borra un post propio (reply, cita o post) - anadido 22/09 porque X no
    permite editar un tuit ya enviado, y hizo falta corregir varios textos
    reales publicados con tildes/enes perdidas (ver diario 22/09). No es lo
    mismo que "borrar contenido nervioso" (prohibido en PROCESO.md - eso es
    esconderse de una critica real): esto es corregir un error propio real,
    con el texto corregido publicado de inmediato despues, documentado sin
    disimular que paso.

    `text_snippet` (recomendado siempre que se sepa el texto exacto) evita
    borrar el articulo equivocado: en la pagina de un permalink de reply
    puede haber mas de un <article> (el tuit original al que se respondio,
    el propio, y respuestas debajo) - sin el snippet se asume que el primero
    es el nuestro, que no siempre es cierto."""
    p, pg = _connect()
    try:
        pg.goto(status_url, wait_until="domcontentloaded", timeout=50000)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        pg.wait_for_timeout(1500)
        if text_snippet:
            art = pg.locator("article").filter(has_text=text_snippet).first
        else:
            art = pg.locator("article").first
        art.locator('[data-testid="caret"]').first.click()
        pg.wait_for_timeout(700)
        _click_menuitem(pg, "Delete")
        pg.wait_for_timeout(700)
        confirm = pg.get_by_test_id("confirmationSheetConfirm")
        if confirm.count() > 0:
            confirm.click()
        pg.wait_for_timeout(1500)
        _check_bot_warning(pg)
        print("post borrado (confirmado)")
    finally:
        p.stop()


def _own_latest_post_url(pg, text_hint=None, limit=5):
    """Busca entre los ultimos posts propios el que coincide con text_hint
    (recorte de las primeras palabras del texto que se acaba de publicar) y
    devuelve su URL - usado para capturar el own_uri de una cita recien
    creada (necesario para el TTL de limpieza a los 21 dias, 29/09). X no
    devuelve un ID/URL directo tras publicar (a diferencia de Bluesky/
    Mastodon via API), asi que se confirma por contenido, nunca por indice a
    ciegas: si no hay coincidencia de texto, no se asume que el primer post
    del perfil es el nuestro."""
    pg.goto("https://x.com/davidportodiaz", wait_until="domcontentloaded", timeout=50000)
    _check_bot_warning(pg)
    needle = " ".join((text_hint or "").split())[:40].casefold()
    for _ in range(6):          # 06/10: el perfil tarda en hidratar (con 1,8 s fijos no aparecia el post recien publicado)
        pg.wait_for_timeout(1500)
        for href, text in _extract_articles(pg, limit=limit):
            if needle and needle not in " ".join((text or "").split()).casefold():
                continue
            if href:
                return f"https://x.com{href}" if href.startswith("/") else href
    return None


def own_recent_texts(scrolls=6):
    """Textos de los ultimos posts propios del perfil (con scroll), para saber si una ficha ya esta publicada (06/10: content_queue_alert / content_publisher)."""
    p, pg = _connect()
    try:
        pg.goto("https://x.com/davidportodiaz", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2200)
        _assert_active_account(pg)
        _check_bot_warning(pg)
        texts = []
        for _ in range(scrolls):
            for _href, text in _extract_articles(pg, limit=20):
                if text and text not in texts:
                    texts.append(text)
            pg.mouse.wheel(0, 2200)
            pg.wait_for_timeout(1400)
        return texts
    finally:
        p.stop()


def repost(status_url, quote_text=None):
    """Devuelve (status, own_uri). own_uri es la URL del post propio creado
    (solo relevante para citas - un repost plano no tiene permalink propio
    distinto del original, se deshace con unrepost(status_url)) - anadido
    29/09 para poder programar la limpieza TTL de citas igual que Bluesky."""
    if quote_text:
        _check_length(quote_text)
        _check_spanish_orthography(quote_text)
    p, pg = _connect()
    try:
        art, _ = _goto_status(pg, status_url)
        if not quote_text and art.locator('[data-testid="unretweet"]').count() > 0:
            print("ese status ya estaba reposteado")
            return "already", None
        retweet = art.locator('[data-testid="retweet"]')
        if retweet.count() != 1:
            raise ActionTargetNotFound("X: botón repost ausente o ambiguo")
        retweet.first.click()
        pg.wait_for_timeout(900)
        if quote_text:
            _click_menuitem(pg, "Quote")
            pg.wait_for_timeout(1200)
            box = pg.locator('[role="dialog"] [data-testid="tweetTextarea_0"]').first
            # BUG REAL visto en vivo el 22/09: a diferencia del dialogo de
            # reply (sin preview de nada), el compositor de cita SIEMPRE
            # incrusta la tarjeta de vista previa del tuit citado - el mismo
            # tipo de overlay que ya se sabia que intercepta el click normal
            # de Playwright en _click_send/_click_menuitem (ver sus
            # docstrings). Aqui rompia con un timeout de 30s en el primer
            # click sobre el propio cuadro de texto, antes incluso de poder
            # escribir nada. Corregido con force=True (ya usado en follow()
            # para el mismo tipo de problema) para saltarse el hit-test de
            # Playwright en vez de reintentar 30s contra un overlay que
            # nunca se va a apartar solo.
            box.click(force=True)
            box.type(quote_text, delay=15)
            pg.wait_for_timeout(800)
            _write_tap_with_uncertain_transport(
                lambda: _click_send(pg, scope_dialog=True), "quote")
            _check_warning_after_tap(pg)
            own_uri = _write_tap_with_uncertain_transport(
                lambda: _own_latest_post_url(pg, text_hint=quote_text), "quote-verificacion")
            if own_uri:
                print(f"cita enviada (confirmada, own_uri={own_uri})")
                return "created", own_uri
            print("cita enviada; confirmación remota pendiente (no se localizó el post propio)")
            return "unverified", None
        else:
            _write_tap_with_uncertain_transport(
                lambda: _click_menuitem(pg, "Repost"), "repost")
            _write_tap_with_uncertain_transport(
                lambda: pg.wait_for_timeout(1500), "repost-verificacion")
            _check_warning_after_tap(pg)
            if _write_tap_with_uncertain_transport(
                    lambda: art.locator('[data-testid="unretweet"]').count(), "repost-verificacion") != 1:
                raise XWriteUnverified("X: repost no confirmado; revisar antes de reintentar")
            print("repost hecho (confirmado)")
            return "created", None
    finally:
        p.stop()


def unrepost(status_url):
    """Retira un repost propio (nunca una cita/quote - esas son contenido
    propio y no se tocan). Pensado para la limpieza programada a 21 dias de
    REGLAS.md ('Vencimiento a 3 semanas'), leyendo reposts_activos.csv.
    Verifica que el boton paso de 'unretweet' a 'retweet' tras confirmar, no
    solo que el click no diera error - misma disciplina que el resto del
    fichero."""
    p, pg = _connect()
    try:
        art, _ = _goto_status(pg, status_url)
        btn = art.locator('[data-testid="unretweet"]').first
        if btn.count() == 0:
            print("no aparece boton 'unretweet' en ese tuit - puede que ya no estuviera reposteado")
            return
        btn.click()
        pg.wait_for_timeout(800)
        confirm = pg.get_by_test_id("unretweetConfirm")
        if confirm.count() > 0:
            confirm.click(timeout=5000)
        else:
            _click_menuitem(pg, "Undo repost")
        pg.wait_for_timeout(1500)
        _check_bot_warning(pg)
        if art.locator('[data-testid="unretweet"]').count() == 0:
            print("repost retirado (confirmado)")
        else:
            raise RuntimeError("No se confirmó la retirada del repost; revisar antes de reintentar")
    finally:
        p.stop()


def _top_profile_follow_control(pg):
    """Control Follow/Unfollow superior del perfil; ignora recomendaciones inferiores.

    BUG REAL encontrado en vivo en la revisión externa de esta PR (28/09):
    el widget "A quién seguir" de la columna derecha renderiza SIEMPRE a un
    y menor que el propio botón del perfil (confirmado en 3 perfiles reales
    distintos - el widget queda fijo cerca de y=130 sin importar la altura
    de la cabecera del perfil visitado), así que la heurística "menor y de
    toda la página" elegía sistemáticamente una cuenta ajena de esa columna
    en vez del perfil objetivo - exactamente el mismo tipo de confusión que
    esta PR decía haber corregido. `[data-testid="primaryColumn"]` acota la
    columna central real (perfil + su timeline) y excluye esa columna
    lateral; sin ese contenedor (cambio de maquetación), no hay forma fiable
    de distinguir columnas y se prefiere no adivinar."""
    scope = pg.locator('[data-testid="primaryColumn"]')
    if scope.count() != 1:
        return None
    controls = scope.first.locator(
        '[data-testid="follow"], [data-testid="unfollow"], '
        '[data-testid$="-follow"], [data-testid$="-unfollow"]'
    )
    best = None
    best_y = None
    for i in range(controls.count()):
        control = controls.nth(i)
        try:
            box = control.bounding_box()
        except Exception:
            box = None
        if box and (best_y is None or box["y"] < best_y):
            best = control
            best_y = box["y"]
    return best


def _profile_follow_state(control):
    if control is None:
        return None
    testid = (control.get_attribute("data-testid") or "").casefold()
    try:
        text = (control.inner_text() or "").strip().casefold()
    except Exception:
        text = ""
    if text in {"pending", "pendiente"}:
        return "pending"
    if testid == "unfollow" or testid.endswith("-unfollow") or text in {"following", "siguiendo"}:
        return "following"
    if testid == "follow" or testid.endswith("-follow") or text in {"follow", "seguir"}:
        return "follow"
    return None


def follow(handle, vet=None):
    """Sigue la cuenta del perfil abierto y verifica el MISMO control superior. `vet(info)` (06/10): motivo de rechazo del perfil ANTES de seguir (None si vale)."""
    p, pg = _connect()
    try:
        tapped = False
        for _ in range(3):
            pg.goto(
                f"https://x.com/{handle}",
                wait_until="domcontentloaded",
                timeout=50000,
            )
            pg.wait_for_timeout(2200)
            _check_bot_warning(pg)
            _assert_active_account(pg)

            control = _top_profile_follow_control(pg)
            state = _profile_follow_state(control)
            if vet is not None and state == "follow":
                reason = vet(_vet_info(pg, handle))
                if reason:
                    raise ProfileRejected(reason)
            if state == "following":
                print(f"{handle}: ya estaba seguido")
                return "already"
            if state == "pending":
                print(f"{handle}: solicitud de follow ya pendiente")
                return "pending"
            if state != "follow":
                pg.wait_for_timeout(1200)
                continue

            control.scroll_into_view_if_needed()
            # Un timeout de Playwright puede llegar DESPUÉS del click.
            tapped = True
            _write_tap_with_uncertain_transport(
                lambda: control.click(force=True), "follow")
            _write_tap_with_uncertain_transport(
                lambda: pg.wait_for_timeout(2000), "follow-verificacion")
            _check_warning_after_tap(pg)

            final = _write_tap_with_uncertain_transport(
                lambda: _profile_follow_state(_top_profile_follow_control(pg)),
                "follow-verificacion")
            if final == "following":
                print(f"{handle}: FOLLOWED (confirmado en control del perfil)")
                return "followed"
            if final == "pending":
                print(f"{handle}: solicitud enviada (pendiente de aprobación)")
                return "pending"
            # Tras UN posible tap, no repetirlo en la siguiente navegación.
            raise XWriteUnverified(
                f"{handle}: follow sin ACK tras el click; conciliación manual"
            )

        error = XWriteUnverified if tapped else RuntimeError
        raise error(
            f"{handle}: follow no confirmado en el control del perfil; "
            "revisar antes de reintentar"
        )
    finally:
        p.stop()

def post(text, media_path=None):
    """Publica un post normal (no programado, no fijado) - la via A del dia
    a dia. 06/10: devuelve el permalink del post nuevo, localizado por su texto en el perfil
    (X no lo devuelve al publicar); si no aparece, lo dice sin asumir que salio ni que no."""
    _check_length(text)
    _check_spanish_orthography(text)
    p, pg = _connect()
    try:
        pg.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(1500)
        _assert_active_account(pg)
        box = pg.locator('[data-testid="tweetTextarea_0"]').first
        box.click()
        box.type(text, delay=12)
        pg.wait_for_timeout(800)
        if media_path:
            _attach_media(pg, media_path)
        _click_send(pg)
        _check_bot_warning(pg)
        for _ in range(3):
            url = _own_latest_post_url(pg, text_hint=text, limit=8)
            if url:
                print(f"post publicado: {url}")
                return url
            pg.wait_for_timeout(2500)
        raise RuntimeError("post enviado pero no aparece aun en el perfil (permalink no verificable); no repetir: comprobar el perfil")
    finally:
        p.stop()


def post_and_pin(text):
    """Publica un post normal (no programado) y lo fija en el perfil.
    Fijar un post es un cambio de cuenta visible para cualquiera que visite
    el perfil - solo llamar tras aprobacion explicita del texto (ver
    SISTEMA_DIARIO_X/PENDIENTES.md)."""
    _check_length(text)
    _check_spanish_orthography(text)
    p, pg = _connect()
    try:
        pg.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(1500)
        _assert_active_account(pg)
        box = pg.locator('[data-testid="tweetTextarea_0"]').first
        box.click()
        box.type(text, delay=12)
        pg.wait_for_timeout(800)
        _click_send(pg)
        _check_bot_warning(pg)
        print("post publicado")

        # IMPORTANTE (bug real visto en vivo 16/09): en el perfil, un post ya
        # fijado sale SIEMPRE primero, encima de los recientes - "article
        # first" puede coger el pin antiguo en vez del post que se acaba de
        # publicar, y fijar el equivocado sin dar ningun error. Hay que
        # localizar el articulo por un trozo literal del texto nuevo, nunca
        # por posicion, y esperar a que aparezca de verdad antes de tocarlo.
        snippet = text[:40]
        pg.goto("https://x.com/davidportodiaz", wait_until="domcontentloaded", timeout=50000)
        target = None
        for _ in range(10):
            cand = pg.locator("article").filter(has_text=snippet)
            if cand.count() > 0:
                target = cand.first
                break
            pg.wait_for_timeout(700)
            pg.reload(wait_until="domcontentloaded", timeout=15000)
        if target is None:
            raise RuntimeError("no encontre el post recien publicado en el perfil - no se toco ningun pin")
        target.locator('[data-testid="caret"]').click()
        pg.wait_for_timeout(800)
        _click_menuitem(pg, "Pin to your profile")
        pg.wait_for_timeout(800)
        confirm = pg.get_by_role("button", name="Pin", exact=True)
        if confirm.count() > 0:
            confirm.click()
        pg.wait_for_timeout(1500)

        # verificar de verdad que quedo fijado EL CORRECTO, no otro
        pg.reload(wait_until="domcontentloaded", timeout=15000)
        pg.wait_for_timeout(2000)
        pinned_block = pg.locator("article").first
        if snippet in pinned_block.inner_text():
            print("post fijado y confirmado")
        else:
            raise RuntimeError("No se confirmó qué publicación quedó fijada; revisar manualmente")
    finally:
        p.stop()


def post_thread(texts):
    """Publica un hilo (varios tuits encadenados) usando el compositor
    multi-post nativo de X (boton 'Add post', data-testid='addButton') -
    comprobado en vivo el 16/09: al pulsarlo aparece tweetTextarea_1,
    tweetTextarea_2, etc., y el envio final es un unico boton 'Post all'
    (data-testid='tweetButton') que publica todo el hilo encadenado de una
    vez, no uno a uno."""
    for t in texts:
        _check_length(t)
        _check_spanish_orthography(t)
    p, pg = _connect()
    try:
        pg.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(1500)
        _assert_active_account(pg)
        box0 = pg.locator('[data-testid="tweetTextarea_0"]').first
        box0.click()
        box0.type(texts[0], delay=10)
        pg.wait_for_timeout(500)
        for i, text in enumerate(texts[1:], start=1):
            pg.locator('[data-testid="addButton"]').first.click()
            pg.wait_for_timeout(900)
            box = pg.locator(f'[data-testid="tweetTextarea_{i}"]').first
            box.click()
            box.type(text, delay=10)
            pg.wait_for_timeout(500)
        _click_send(pg)
        _check_bot_warning(pg)
        print(f"hilo publicado ({len(texts)} tuits)")
    finally:
        p.stop()


def health():
    """Comprueba que la sesion de X sigue logueada de verdad (no solo que
    Edge responda en el puerto 9223). Sin esto, una cookie caducada podria
    hacer fallar todo en silencio el dia que David diga 'hazlo'.

    BUG REAL visto en vivo el 17/09: la primera comprobacion daba falso
    negativo (SideNav_NewTweet_Button con count 0) simplemente porque la
    pagina no habia terminado de hidratar en los 2s de espera fija - un
    goto+wait_for_timeout inmediatamente despues confirmaba que si estaba
    logueado. Se reintenta unas cuantas veces antes de dar el problema por
    real, misma disciplina de "verificar antes de fallar" que el resto del
    fichero aplica para verificar antes de dar por bueno.

    BUG REAL gemelo visto en vivo el 21/09, y CORREGIDO DE RAIZ el mismo
    dia tras un aviso de David sobre el equivalente en Threads: la segunda
    comprobacion navegaba a x.com/davidportodiaz y miraba si el texto
    aparecia - eso es SIEMPRE cierto da igual la cuenta activa, porque es
    una pagina de perfil publica. Nunca demostraba de verdad cual era la
    cuenta activa. Sustituido por `_active_account_handle()`, que lee el
    selector de cuenta real (`SideNav_AccountSwitcher_Button`) - la unica
    prueba real de que accion se ejecutaria como quien."""
    p, pg = _connect()
    try:
        ok, msg = _health_check(pg)
        print(msg)
    finally:
        p.stop()


def _health_check(pg):
    """Nucleo de health(), extraido el 22/09 para que `daily` pueda
    reutilizar la misma conexion/pagina en vez de abrir una aparte solo
    para comprobar la sesion. Devuelve (ok, mensaje) en vez de imprimir
    directamente, para que quien llama pueda decidir si sigue o para."""
    pg.goto("https://x.com/home", wait_until="domcontentloaded", timeout=50000)
    _check_bot_warning(pg)
    logged_in = False
    for _ in range(5):
        pg.wait_for_timeout(1200)
        if pg.locator('[data-testid="SideNav_NewTweet_Button"]').count() > 0:
            logged_in = True
            break
    if not logged_in:
        return False, "PROBLEMA: no se detecta sesion logueada en x.com tras varios intentos - puede haber caducado la cookie. Avisar a David, no seguir con acciones."
    active = None
    for _ in range(5):
        pg.wait_for_timeout(1000)
        active = _active_account_handle(pg)
        if active:
            break
    if active is None:
        return False, "PROBLEMA: logueado, pero no se pudo determinar la cuenta activa (selector de cuenta no encontrado)."
    if active != "davidportodiaz":
        return False, (
            f"PROBLEMA REAL: la cuenta ACTIVA en esta sesion es @{active}, "
            "NO @davidportodiaz. Cualquier reply/like/repost/follow/post se "
            f"ejecutaria como @{active}. Cambiar de cuenta en X antes de "
            "continuar - no ejecutar ninguna accion con este resultado."
        )
    return True, "OK: sesion logueada y cuenta ACTIVA confirmada como @davidportodiaz."


def daily_briefing():
    """Disparador diario completo (PROCESO.md) en una sola conexion/proceso:
    health + notifications + following-feed + las 3 listas fijas + explore.

    Anadido 22/09 a peticion explicita de David para reducir gasto de tokens:
    antes esto eran 8 llamadas de terminal independientes (8 arranques de
    Python/Playwright/conexion CDP, 8 bloques de salida que Claude tenia que
    leer por separado). El contenido que produce cada paso es exactamente el
    mismo que antes (misma funcion interna, solo se dejo de crear/cerrar una
    conexion nueva en cada paso) - esto no cambia que se lee, solo cuantas
    veces se paga el coste fijo de conectar y cuantos tool calls hacen falta.

    Para antes de las secciones de descubrimiento si el health check falla
    (sesion caducada o cuenta activa incorrecta) - no tiene sentido seguir
    navegando si ya sabemos que algo esta mal."""
    p, pg = _connect()
    try:
        print("=== HEALTH ===")
        ok, msg = _health_check(pg)
        print(msg)
        if not ok:
            print("\nParando aqui - no se seguira con notifications/feeds/explore hasta resolver esto.")
            return

        print("\n=== NOTIFICATIONS ===")
        _dump_notifications(pg)

        print("\n=== FOLLOWING FEED ===")
        _dump_following_feed(pg)

        for name, url in DAILY_LISTS:
            print(f"\n=== LISTA: {name} ===")
            _dump_list_feed(pg, url)

        print("\n=== EXPLORE ===")
        _dump_explore(pg)
    finally:
        p.stop()


def unfollow(handle):
    """Deja de seguir y VERIFICA que el boton volvio a «Follow». Devuelve 'unfollowed' o 'already' (06/10: antes solo imprimia y no comprobaba nada)."""
    p, pg = _connect()
    try:
        pg.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2000)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        control = _top_profile_follow_control(pg)
        state = _profile_follow_state(control)
        if state == "follow":
            print(f"{handle}: ya no se seguia")
            return "already"
        if state != "following":
            raise RuntimeError(f"{handle}: no se encontro el control Following del perfil; revisar antes de reintentar")
        control.click()
        pg.wait_for_timeout(800)
        confirm = pg.get_by_test_id("confirmationSheetConfirm")
        if confirm.count() > 0:
            confirm.click()
            pg.wait_for_timeout(1200)
        _check_bot_warning(pg)
        if _profile_follow_state(_top_profile_follow_control(pg)) != "follow":
            raise RuntimeError(f"{handle}: unfollow no confirmado; revisar antes de reintentar")
        print(f"{handle}: UNFOLLOWED (confirmado)")
        return "unfollowed"
    finally:
        p.stop()


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# 06/10/2026 (David: «hagamos crecer X como Bluesky, Mastodon y Threads»): lectura con scroll de posts y de cuentas, busqueda por pestana (Recientes / Personas), listas de
# seguidores, perfil, like al ultimo post y sesion compartida con vigilante. Mismo contrato que `threads_interact.py`; el vigilante y la sesion viven en `browser_common.py`.
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
MY_HANDLE = "davidportodiaz"
SEARCH_MODES = {"top": "", "live": "&f=live", "user": "&f=user"}


class ProfileRejected(RuntimeError):
    """El perfil no cumple los filtros antes de seguirlo / darle like (idioma, tamaño, politica)."""


def parse_count(text):
    """«1.234 Followers» -> 1234; «1,2 mil Seguidores» / «3.4K Followers» -> 3400; «2 M» -> 2.000.000. None si no hay cifra."""
    match = re.search(r"(\d[\d.,]*)\s*(mill\w*|mil\b|K\b|M\b)?", str(text or ""), re.I)
    if not match:
        return None
    number, suffix = match.group(1), (match.group(2) or "").casefold()
    if suffix:
        try:
            value = float(number.replace(",", "."))
        except ValueError:
            return None
        return int(value * (1_000_000 if suffix.startswith("m") and suffix != "mil" else 1000))
    digits = re.sub(r"[.,]", "", number)
    return int(digits) if digits.isdigit() else None


_ARTICLES_JS = """(limit) => Array.from(document.querySelectorAll('article[data-testid="tweet"]')).slice(0, limit).map(a => {
    const t = a.querySelector('[data-testid="tweetText"]');
    const time = a.querySelector('time');
    const link = time ? time.closest('a') : null;
    const sc = a.querySelector('[data-testid="socialContext"]');
    const ad = Array.from(a.querySelectorAll('span')).some(s => s.textContent === 'Ad' || s.textContent === 'Anuncio');
    return {href: link ? link.getAttribute('href') : null, datetime: time ? time.getAttribute('datetime') : null, text: t ? t.innerText : '',
            lang: t ? t.getAttribute('lang') : null, social: sc ? sc.innerText : '', ad: ad};
})"""
_REPOST_RE = re.compile(r"repost|retwe|retuit|reposte", re.I)
_PINNED_RE = re.compile(r"pinned|fijado", re.I)


def extract_posts(pg, limit=40):
    """[{handle, url, text, lang, age_hours, repost, pinned}] de los posts visibles. El texto es el CUERPO del post (sin cabecera ni contadores) y `lang` el idioma que X
    le asigna (`es`, `en`, `und`…): mas fiable que adivinarlo del texto. Descarta anuncios y articulos sin permalink."""
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    out = []
    for row in pg.evaluate(_ARTICLES_JS, limit) or []:
        href = row.get("href") or ""
        match = re.match(r"^/([A-Za-z0-9_]{1,15})/status/(\d+)", href)
        if row.get("ad") or not match:
            continue
        age = None
        try:
            age = max(0.0, (now - _dt.datetime.fromisoformat(str(row["datetime"]).replace("Z", "+00:00"))).total_seconds() / 3600)
        except (ValueError, TypeError, KeyError):
            pass
        social = row.get("social") or ""
        out.append({"handle": match.group(1), "url": f"https://x.com/{match.group(1)}/status/{match.group(2)}", "text": (row.get("text") or "").strip(),
                    "lang": (row.get("lang") or "").casefold(), "age_hours": age, "repost": bool(_REPOST_RE.search(social)), "pinned": bool(_PINNED_RE.search(social))})
    return out


def collect_posts_scrolling(pg, passes=3, limit=60):
    """Posts (ver `extract_posts`) tras hacer scroll `passes` veces; deduplica por permalink y para cuando el scroll no trae nada nuevo."""
    seen, out, stale = set(), [], 0
    for step in range(passes + 1):
        fresh = 0
        for post in extract_posts(pg, limit=60):
            if post["url"] not in seen:
                seen.add(post["url"])
                out.append(post)
                fresh += 1
        stale = 0 if fresh else stale + 1
        if len(out) >= limit or step == passes or stale >= 2:
            break
        pg.mouse.wheel(0, 1800)
        pg.wait_for_timeout(1300)
        _check_bot_warning(pg)
    return out[:limit]


def open_search(pg, query, mode="live"):
    """Abre la busqueda en la pestana pedida: top (Destacados), live (Recientes) o user (Personas: cuentas por nombre y biografia)."""
    import urllib.parse
    pg.goto(f"https://x.com/search?q={urllib.parse.quote(query)}&src=typed_query{SEARCH_MODES[mode]}", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)


_USERCELLS_JS = """() => Array.from(document.querySelectorAll('[data-testid="primaryColumn"] [data-testid="UserCell"]')).map(c => {
    const a = Array.from(c.querySelectorAll('a[href^="/"]')).find(x => /^\\/[A-Za-z0-9_]{1,15}$/.test(x.getAttribute('href') || ''));
    return {handle: a ? a.getAttribute('href').slice(1) : '', text: c.innerText};
})"""
_ROW_NOISE = {"follow", "following", "follows you", "te sigue", "seguir", "siguiendo", "pending", "pendiente", "·"}


def parse_user_cell(handle, text):
    """(handle, nombre, bio) del texto de una celda de usuario: «Nombre / @handle / [Follows you] / bio… / [Follow]»."""
    lines = [line.strip() for line in str(text or "").split(chr(10)) if line.strip()]
    name, bio = "", []
    for index, line in enumerate(lines):
        if line.casefold() == f"@{handle}".casefold():
            name = " ".join(lines[:index])[:80]
            bio = [l for l in lines[index + 1:] if l.casefold() not in _ROW_NOISE]
            break
    return handle, name, " ".join(bio)[:300]


def collect_account_rows(pg, passes=3, limit=120):
    """Cuentas (handle, nombre, bio) de un listado con scroll: pestana Personas de la busqueda o lista de seguidores/seguidos de un perfil."""
    seen, out, stale = set(), [], 0
    for step in range(passes + 1):
        fresh = 0
        for row in pg.evaluate(_USERCELLS_JS) or []:
            handle = row.get("handle") or ""
            if handle and handle.casefold() not in seen and handle.casefold() != MY_HANDLE:
                seen.add(handle.casefold())
                out.append(parse_user_cell(handle, row.get("text")))
                fresh += 1
        stale = 0 if fresh else stale + 1
        if len(out) >= limit or stale >= 2 or step == passes:
            break
        pg.mouse.wheel(0, 1800)
        pg.wait_for_timeout(1500)
        _check_bot_warning(pg)
    return out[:limit]


def _vet_info(pg, handle):
    """Perfil abierto + handle y red: `exec_common.follow_vet` anota los contadores (hubs de reciprocidad, 07/10) sin navegar de mas."""
    info = profile_info(pg)
    info["handle"], info["network"] = handle, "x"
    return info


def profile_info(pg):
    """{name, bio, followers, following, handle} del perfil abierto."""
    data = pg.evaluate("""() => {
        const txt = s => { const e = document.querySelector(s); return e ? e.innerText : ''; };
        const link = suffix => { const a = Array.from(document.querySelectorAll('a[href$="' + suffix + '"]'))[0]; return a ? a.innerText : ''; };
        return {name: txt('[data-testid="UserName"]'), bio: txt('[data-testid="UserDescription"]'),
                followers: link('/verified_followers') || link('/followers'), following: link('/following')};
    }""") or {}
    return {"name": data.get("name", ""), "bio": data.get("bio", ""), "followers": parse_count(data.get("followers")), "following": parse_count(data.get("following"))}


def collect_followers(pg, handle, passes=4, limit=120, kind="seguidores"):
    """Cuentas de la lista de seguidores (o seguidos) de `handle`, las mas recientes primero. Devuelve (info_del_perfil, filas)."""
    pg.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2200)
    _check_bot_warning(pg)
    _assert_active_account(pg)
    info = profile_info(pg)
    pg.goto(f"https://x.com/{handle}/{'following' if kind.casefold() == 'seguidos' else 'followers'}", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    rows = collect_account_rows(pg, passes=passes, limit=limit)
    return info, [row for row in rows if row[0].casefold() != handle.casefold()]


def follows_me(handle):
    """True si la cuenta nos sigue, mirando su perfil («Follows you» / «Te sigue»: indicador `userFollowIndicator`)."""
    p, pg = _connect()
    try:
        pg.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2200)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        return pg.locator('[data-testid="userFollowIndicator"]').count() > 0
    finally:
        p.stop()


def like_latest(handle, vet=None, max_age_days=45):
    """Like al ultimo post propio y reciente de `handle` (no fijado, no repost, en espanol, sin politica). `vet(info)` como en `follow`.
    Devuelve ('created'|'already', texto). Lanza ProfileRejected si no hay un post apto."""
    import text_common as tc
    p, pg = _connect()
    try:
        here = (pg.url or "").rstrip("/").casefold().endswith(f"x.com/{handle}".casefold())
        if not here:
            pg.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=50000)
            pg.wait_for_timeout(2400)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        if vet is not None:
            reason = vet(_vet_info(pg, handle))
            if reason:
                raise ProfileRejected(reason)
        articles = pg.locator('article[data-testid="tweet"]')
        posts = extract_posts(pg, limit=8)
        for index, post in enumerate(posts):
            if post["handle"].casefold() != handle.casefold() or post["repost"] or post["pinned"]:
                continue
            if post["age_hours"] is not None and post["age_hours"] > max_age_days * 24:
                continue
            body = " ".join(post["text"].split())
            if len(body) < 25 or sc_is_political(body) or post["lang"] not in ("es", "ca", "gl", "eu", "und", "") or tc.foreign_language(body):
                continue
            art = articles.nth(index)
            status_id = _status_id(post["url"])
            if not status_id or not art.locator(f'a[href$="/status/{status_id}"]').count():
                continue  # lista filtrada y artículos pueden diferir por anuncios
            if not _like_context_of_article(art)[0]:
                continue
            if art.locator('[data-testid="unlike"]').count() > 0:
                return "already", body[:120]
            btn = art.locator('[data-testid="like"]')
            if btn.count() != 1:
                continue
            _write_tap_with_uncertain_transport(lambda: btn.first.click(), "like_latest")
            _write_tap_with_uncertain_transport(
                lambda: pg.wait_for_timeout(1000), "like_latest-verificacion")
            _check_warning_after_tap(pg)
            for _ in range(5):
                if _write_tap_with_uncertain_transport(
                        lambda: art.locator('[data-testid="unlike"]').count(),
                        "like_latest-verificacion") == 1:
                    print(f"{handle}: like al ultimo post (confirmado): {body[:70]}")
                    return "created", body[:120]
                _write_tap_with_uncertain_transport(
                    lambda: pg.wait_for_timeout(600), "like_latest-verificacion")
            raise XWriteUnverified("X: like no confirmado; revisar el post antes de reintentar")
        raise ProfileRejected("sin post reciente apto")
    finally:
        p.stop()


def sc_is_political(text):
    import scan_common as _sc
    return _sc.is_political(text)



def _dispatch():
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "ensure-browser":
        ensure_browser()
    elif cmd == "following-feed":
        ensure_browser(); dump_following_feed()
    elif cmd == "list-feed":
        ensure_browser(); dump_list_feed(sys.argv[2])
    elif cmd == "notifications":
        ensure_browser(); dump_notifications()
    elif cmd == "followers":
        ensure_browser(); dump_followers(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "search":
        ensure_browser(); dump_search(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "live")
    elif cmd == "explore":
        ensure_browser(); dump_explore()
    elif cmd == "replies":
        ensure_browser(); dump_replies(sys.argv[2])
    elif cmd == "profile":
        ensure_browser(); dump_profile(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "reply":
        ensure_browser(); reply_to(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "like":
        ensure_browser(); like(sys.argv[2])
    elif cmd == "repost":
        ensure_browser(); repost(sys.argv[2])
    elif cmd == "unrepost":
        ensure_browser(); unrepost(sys.argv[2])
    elif cmd == "delete":
        ensure_browser(); delete_post(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "quote":
        ensure_browser(); repost(sys.argv[2], sys.argv[3])
    elif cmd == "follow":
        ensure_browser(); follow(sys.argv[2])
    elif cmd == "unfollow":
        ensure_browser(); unfollow(sys.argv[2])
    elif cmd == "post":
        ensure_browser(); post(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "pin":
        ensure_browser(); post_and_pin(sys.argv[2])
    elif cmd == "thread":
        ensure_browser(); post_thread(sys.argv[2:])
    elif cmd == "health":
        ensure_browser(); health()
    elif cmd == "daily":
        ensure_browser(); daily_briefing()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    try:
        _dispatch()
    except BotWarningDetected as e:
        print(str(e))
        sys.exit(2)
    except WrongAccountActive as e:
        print(str(e))
        sys.exit(3)
