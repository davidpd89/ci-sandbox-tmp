"""
Herramienta unica para el dia a dia de Threads - mismo patron que
tools/x_interact.py (mismo Edge real via CDP puerto 9223, ya logueado).
No es una copia ciega: Threads no tiene data-testid como X, así que casi
todo se localiza por el texto real de la interfaz (español, porque asi
esta configurada esta cuenta) o por el <title> que llevan dentro los SVG
de los iconos de accion.

Construida el 17/09/2026, primer dia, con exploracion en vivo real (no
adivinada) antes de escribir nada. Estado de cada accion mas abajo.

Uso:
    python threads_interact.py ensure-browser
    python threads_interact.py health
    python threads_interact.py feed
    python threads_interact.py profile [handle]
    python threads_interact.py notifications
    python threads_interact.py search "consulta"
    python threads_interact.py like <indice_o_fragmento_de_texto> [fuente]
    python threads_interact.py follow <handle>
    python threads_interact.py reply <fragmento_de_texto> "texto de la respuesta" [fuente]
    python threads_interact.py post "texto"

Sobre "like": aceptar un indice numerico (0-based, rapido pero fragil en
el feed "Para ti", ver docstring de like_in_feed) o un fragmento de texto
copiado del dump anterior (mas lento pero fiable, actua solo si encuentra
ese texto exacto en la carga actual).

CONFIRMADO EN VIVO el 17/09 (probado de verdad, no solo escrito):
- feed, profile, notifications: lectura de texto, funciona.
- like: funciona y se verifica (el <title> del SVG pasa de "Me gusta" a
  "Ya no me gusta"). Probado en un post real de @fantasybox.es.
- follow: funciona y se verifica (el boton pasa de "Seguir" a "Siguiendo").
  Probado en @fantasybox.es.
- El menu de repost abre bien (opciones "Repostear"/"Citar" via el SVG
  title "Repostear"), pero no se completo un repost real todavia - falta
  probar el flujo entero una vez haya contenido que de verdad merezca
  repostearse.
- El compositor de post nuevo abre bien (contenteditable real, boton
  "Publicar" visible) - no se ha probado el envio completo todavia.

CORREGIDO el 22/09 (diagnostico incompleto del 17/09, encontrado en vivo
tras un aviso directo de David con capturas reales): lo que esta roto NO es
la pagina de un post en si, sino navegar a ella por URL DIRECTA
(pg.goto("threads.com/@handle/post/ID")) - eso SI redirige silenciosamente
a "/" sin avisar (confirmado en vivo el 22/09). Pero hacer CLICK en el
boton "Responder" de un post tal y como aparece en un listado (feed/
activity/perfil/busqueda) funciona perfectamente: navega a la pagina del
post por routing interno (sin recarga completa) y esa pagina SI carga bien,
con un compositor de respuesta real ("Responde a @handle...",
contenteditable) y su propio boton de enviar (unico <svg title="Respuesta">
de toda la pagina, distinto del <svg title="Responder"> que es el boton de
contador bajo cada post). Ver reply_to() mas abajo - mismo patron que
like_in_feed/follow: actuar SIEMPRE sobre el post como aparece en un
listado, nunca con pg.goto() directo a su URL propia.
"""
import os
import re
import sys
import time
import subprocess
import urllib.request
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(__file__))
from scan_common import ActionTargetNotFound, AlreadyCommented, check_length  # compartido entre redes, 23/09
from x_interact import _check_spanish_orthography  # reutilizado, no duplicado

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
# Cambiado el 17/09: mismo motivo que x_interact.py - el perfil real por
# defecto dejo de aceptar --remote-debugging-port (visto en vivo). Perfil
<<<<<<< HEAD
# dedicado solo para esta automatizacion; David loguea @autorademodiaz en
# Threads ahi UNA vez y la sesion se queda guardada.
EDGE_USER_DATA = r"C:\Temp\rrss-autorademo-edge"
MY_HANDLE = "autorademodiaz"
=======
# dedicado solo para esta automatizacion; David loguea @davidportodiaz en
# Threads ahi UNA vez y la sesion se queda guardada.
EDGE_USER_DATA = r"C:\Temp\rrss-davidporto-edge"
MY_HANDLE = "davidportodiaz"
>>>>>>> origin/research/public-reuse-parent

# Mismo seguro que x_interact.py (añadido alli el 17/09 a peticion de
# David) - si Threads muestra cualquier aviso real de bot/actividad
# inusual/cuenta restringida, parar todo de inmediato.
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
    "unusual login activity",
    "automated behavior",
    "comportamiento automatizado",
]


class BotWarningDetected(RuntimeError):
    pass


class WrongAccountActive(RuntimeError):
    pass


# AlreadyCommented y ActionTargetNotFound: importadas de scan_common (23/09,
# antes definidas aqui - centralizadas para que un fix del tipo de excepcion
# no haya que repetirlo red por red, ver scan_common.py).


def _assert_active_account(pg):
    """Seguro real anadido el 21/09 tras un aviso de David: la cuenta
    ACTIVA de la sesion (la que ejecuta follow/like/post) puede no ser
<<<<<<< HEAD
    autorademodiaz aunque la sesion este logueada - Threads/Instagram
=======
    davidportodiaz aunque la sesion este logueada - Threads/Instagram
>>>>>>> origin/research/public-reuse-parent
    permiten varias cuentas a la vez con un selector de cuenta activa.
    Se llama antes de CUALQUIER accion de escritura (follow/like/post),
    reutilizando la pagina ya cargada - no anade una navegacion extra."""
    active = _active_profile_handle(pg)
    if active != MY_HANDLE:
        raise WrongAccountActive(
            f"CUENTA ACTIVA INCORRECTA: esta sesion tiene activa @{active}, "
            f"no @{MY_HANDLE}. Accion cancelada antes de ejecutarse. "
<<<<<<< HEAD
            "Cambiar de cuenta en Threads (perfil Autora Demo Escritor) "
=======
            "Cambiar de cuenta en Threads (perfil David Porto Diaz Escritor) "
>>>>>>> origin/research/public-reuse-parent
            "y volver a intentar."
        )


# 06/10: un `evaluate` de Playwright sobre un Edge colgado no tiene tiempo limite y dejo una prueba parada 19 minutos (y el bloqueo del navegador con ella). Vigilante: si no
# hay actividad (`beat()`) en `limit` segundos, el proceso termina; el registro es accion a accion y el bloqueo de archivo caduca con el proceso, asi que no se pierde nada.
<<<<<<< HEAD
_WATCH = {"last": time.time(), "started": False}


def beat():
    _WATCH["last"] = time.time()


def start_watchdog(limit=300, interval=15):
    if _WATCH["started"] or not limit:
        return
    import threading
    _WATCH["started"] = True

    def loop():
        while True:
            time.sleep(interval)
            idle = time.time() - _WATCH["last"]
            if idle > limit:
                print(f"VIGILANTE: {int(idle)} s sin actividad en el navegador (Edge colgado); se aborta el proceso para liberar el turno. "
                      "Receta: tools/cdp_resume_workers.py", flush=True)
                os._exit(6)

    beat()
    threading.Thread(target=loop, daemon=True, name="threads-watchdog").start()
=======
import browser_common as bc

_WATCHDOG = bc.Watchdog("threads")


def beat():
    _WATCHDOG.beat()


def start_watchdog(limit=300, interval=15):
    _WATCHDOG.start(limit=limit, interval=interval)

>>>>>>> origin/research/public-reuse-parent


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
                f"AVISO REAL DETECTADO EN PANTALLA: \"{signal}\". "
                "Parando de inmediato. Avisar a David antes de reintentar."
            )


def _cdp_alive():
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3)
        return True
    except Exception:
        return False


def _edge_locking_profile_without_cdp():
    """Mismo caso que en x_interact.py: detecta si otro proceso ya tiene
    abierto el perfil dedicado (EDGE_USER_DATA) sin el flag de depuracion -
    en ese caso lanzar otro Edge con el flag no sirve de nada, Chromium
    reenvia la peticion al proceso ya vivo."""
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
    el perfil real por defecto de David, ver comentario junto a la
    constante: dejo de aceptar depuracion remota)."""
    if _cdp_alive():
        print("CDP ya activo en 9223")
        return
    print("CDP no responde, abriendo Edge (perfil dedicado de la automatizacion)...")
    subprocess.Popen([
        EDGE_EXE,
        "--remote-debugging-port=9223",
        f"--user-data-dir={EDGE_USER_DATA}",
        "https://www.threads.com/",
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
            "el flag de depuracion. Solucion: cerrar esa ventana y volver a ejecutar "
            "ensure-browser."
        )
    raise RuntimeError("Edge no respondio en CDP 9223 tras 20s")


class _KeepOpen:
    """`p.stop()` de las funciones sueltas no hace nada cuando hay una sesion compartida abierta (ver `session`)."""

    def stop(self):
        pass


_SHARED = {"pg": None}


def session():
    """Una sola conexion CDP para TODAS las acciones de un plan (05/10). Antes cada like/follow/reply abria un Playwright y una conexion nuevos (~2-4 s de
    sobrecarga y un riesgo de cuelgue del Edge por accion). Uso: `with t.session() as pg: ...`; dentro, `_connect()` devuelve esa misma pagina."""
    import contextlib

    @contextlib.contextmanager
    def manager():
        p = sync_playwright().start()
<<<<<<< HEAD
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            ctx = browser.contexts[0]
            pages = [pg for pg in ctx.pages if urlsplit(pg.url).hostname in {"threads.com", "www.threads.com", "threads.net", "www.threads.net"}]
            pg = pages[-1] if pages else ctx.new_page()
=======
        pg = None
        try:
            import browser_common as bc
            browser = bc.connect_cdp(p.chromium, CDP_URL)
            pg = bc.new_owned_page(browser)
>>>>>>> origin/research/public-reuse-parent
            pg.set_default_timeout(15000)             # 06/10: ninguna llamada espera los 30 s por defecto (un perfil que no responde tardaba minutos entre botones)
            pg.set_default_navigation_timeout(30000)
            _SHARED["pg"] = pg
            start_watchdog()
            yield pg
        finally:
            _SHARED["pg"] = None
<<<<<<< HEAD
            p.stop()
=======
            try:
                if pg is not None:
                    pg.close()
            except Exception:
                pass
            finally:
                try:
                    _WATCHDOG.stop()
                finally:
                    p.stop()
>>>>>>> origin/research/public-reuse-parent

    return manager()


def _connect():
    if _SHARED["pg"] is not None:
        return _KeepOpen(), _SHARED["pg"]
    p = sync_playwright().start()
<<<<<<< HEAD
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0]
    try:
        import browser_lean
        browser_lean.apply(ctx)         # 07/10: sin imagenes/video/fuentes
    except Exception:
        pass
    pages = [pg for pg in ctx.pages if urlsplit(pg.url).hostname in {
        "threads.com", "www.threads.com", "threads.net", "www.threads.net"
    }]
    pg = pages[-1] if pages else ctx.new_page()
    return p, pg
=======
    try:
        import browser_common as bc
        browser = bc.connect_cdp(p.chromium, CDP_URL)
        pg = bc.new_owned_page(browser)
        return bc.OwnedPlaywright(p, pg), pg
    except Exception:
        p.stop()
        raise
>>>>>>> origin/research/public-reuse-parent


def _active_profile_handle(pg):
    """Devuelve el handle de la cuenta REALMENTE activa en esta sesion (la
    que ejecuta follow/like/post), no solo una cuenta que se pueda ver.
    BUG REAL encontrado en vivo el 21/09: comprobar que /@{MY_HANDLE} carga
    y muestra el texto del handle NO demuestra nada, porque esa es una
    pagina de perfil publica - se ve igual la mires con la identidad que la
    mires. Threads/Instagram permiten varias cuentas logueadas a la vez con
    un selector de cuenta activa; la unica prueba real de cual esta activa
    es el href del enlace de navegacion 'Perfil' en la pagina de inicio,
    que SIEMPRE apunta a la cuenta activa. Debe llamarse con `pg` ya en
    'https://www.threads.com/'."""
    href = pg.get_by_role("link", name="Perfil").first.get_attribute("href")
    if href and href.startswith("/@"):
        return href[2:]
    return None


def _health_check(pg):
    """Nucleo de health(), extraido el 22/09 (mismo patron que x_interact.py)
    para que `daily`/`threads_scan.py` puedan reutilizar la misma conexion
    en vez de abrir una aparte solo para comprobar la sesion. Devuelve
    (ok, mensaje)."""
    pg.goto("https://www.threads.com/", wait_until="domcontentloaded", timeout=50000)
    ok = False
    for _ in range(5):
        pg.wait_for_timeout(1200)
        if pg.get_by_text("Nuevo hilo").count() > 0:
            ok = True
            break
    _check_bot_warning(pg)
    if not ok:
        return False, "PROBLEMA: no se detecta sesion logueada en Threads tras varios intentos."
    active = _active_profile_handle(pg)
    if active is None:
        return False, "PROBLEMA: logueado, pero no se pudo determinar la cuenta activa (enlace 'Perfil' no encontrado)."
    if active != MY_HANDLE:
        return False, (
            f"PROBLEMA REAL: la cuenta ACTIVA en esta sesion es @{active}, "
            f"NO @{MY_HANDLE}. Cualquier follow/like/post se ejecutaria como "
            f"@{active}. Cambiar de cuenta en Threads antes de continuar - "
            "no ejecutar ninguna accion con este resultado."
        )
    return True, f"OK: sesion logueada y cuenta ACTIVA confirmada como @{MY_HANDLE}."


def health():
    """Comprueba que la sesion sigue logueada Y que la cuenta ACTIVA es
<<<<<<< HEAD
    autorademodiaz - no solo que exista una sesion cualquiera. Mismo
=======
    davidportodiaz - no solo que exista una sesion cualquiera. Mismo
>>>>>>> origin/research/public-reuse-parent
    reintento que x_interact.py (evita el falso negativo por hidratacion
    lenta visto en vivo en X el 17/09)."""
    p, pg = _connect()
    try:
        ok, msg = _health_check(pg)
        print(msg)
    finally:
        p.stop()


def daily_briefing():
    """Disparador diario en una sola conexion (anadido 22/09, mismo patron
    y motivo que x_interact.py daily): health + notifications + feed. Para
    de inmediato si el health check falla."""
    p, pg = _connect()
    try:
        print("=== HEALTH ===")
        ok, msg = _health_check(pg)
        print(msg)
        if not ok:
            print("\nParando aqui - resolver esto antes de nada mas.")
            return
        print("\n=== NOTIFICATIONS ===")
        _dump_notifications(pg)
        print("\n=== FEED ===")
        _dump_feed(pg)
    finally:
        p.stop()


def _dump_feed(pg):
    pg.goto("https://www.threads.com/", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    print(pg.inner_text("body")[:6000])


def dump_feed():
    """Vuelca el feed 'Para ti' en texto. Es la fuente principal de
    descubrimiento: a diferencia de X, Threads ya mezcla en este feed
    cuentas de comunidades tematicas reales (visto en vivo: posts
    etiquetados 'Book Threads') sin tener que buscar nada - confirmar cada
    sesion si sigue asi de bueno."""
    p, pg = _connect()
    try:
        _dump_feed(pg)
    finally:
        p.stop()


def _dump_profile(pg, handle=None):
    h = handle or MY_HANDLE
    pg.goto(f"https://www.threads.com/@{h}", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2200)
    _check_bot_warning(pg)
    print(pg.inner_text("body")[:2000])


def dump_profile(handle=None):
    p, pg = _connect()
    try:
        _dump_profile(pg, handle)
    finally:
        p.stop()


def _dump_notifications(pg):
    pg.goto("https://www.threads.com/activity", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    print(pg.inner_text("body")[:4000])


def dump_notifications():
    p, pg = _connect()
    try:
        _dump_notifications(pg)
    finally:
        p.stop()


def _dump_search(pg, query):
    import urllib.parse
    q = urllib.parse.quote(query)
    pg.goto(f"https://www.threads.com/search?q={q}", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    print(pg.inner_text("body")[:4000])


def dump_search(query):
    """Busca en Threads. A diferencia de X no hay pestana Latest/Top
    documentada todavia - probar y anotar en THREADS_CUENTAS_VIGILAR.md
    equivalente si el orden es por relevancia o por fecha."""
    p, pg = _connect()
    try:
        _dump_search(pg, query)
    finally:
        p.stop()


def _post_containers(pg):
    """Cada post en un feed/perfil/busqueda es un [data-pressable-container]
    - equivalente al <article> de X. Confirmado en vivo el 17/09."""
    return pg.locator("[data-pressable-container]")


def _fold_text(text):
    """Texto comparable: sin acentos, minusculas y espacios/saltos de linea colapsados."""
    import unicodedata
    plain = "".join(ch for ch in unicodedata.normalize("NFD", text or "") if unicodedata.category(ch) != "Mn")
    return " ".join(plain.casefold().split())


def _find_container_by_text(pg, target, max_scrolls=4):
    """Busca `target` (fragmento de texto) entre los [data-pressable-container]
    cargados, haciendo scroll si no aparece a la primera. Anadido 23/09 tras
    confirmar en vivo que like_in_feed()/reply_to() fallaban con
    ActionTargetNotFound sobre posts reales que solo estaban mas abajo en la
    pagina de perfil/busqueda, no realmente ausentes (ver PENDIENTES.md).
    Devuelve el indice del contenedor o None si no aparece tras agotar los
    scrolls (entonces si es razonable concluir que no esta cargado)."""
    containers = _post_containers(pg)
    checked = 0
    wanted = _fold_text(target)
    for _ in range(max_scrolls + 1):
        n = containers.count()
        for i in range(checked, n):
            try:
                body = containers.nth(i).inner_text()
            except Exception:         # contenedor desmontado por el feed virtualizado
                continue
            if target in body or wanted in _fold_text(body):       # 07/10: el fragmento llega con espacios simples y el texto del post trae saltos de linea y acentos distintos: las replies fallaban «no se encontro ningun post»
                return i
        checked = n
        pg.mouse.wheel(0, 1800)
        pg.wait_for_timeout(900)
        containers = _post_containers(pg)
        if containers.count() <= checked:
            break  # scroll no cargo nada nuevo, no seguir insistiendo
    return None


def _extract_posts(pg, limit=15):
    """Vuelca (handle, permalink, texto) por cada post visible - equivalente
    al `_extract_articles` de x_interact.py. Anadido 22/09 para que
    `threads_scan.py` pueda trabajar con candidatos estructurados en vez de
    parsear el texto plano de `dump_feed`. El link `a[href^="/@"]` dentro de
    cada `[data-pressable-container]` es estable (confirmado en vivo)
    aunque el ORDEN del feed no lo sea - ver el bug de reordenamiento en
    PENDIENTES.md, sigue aplicando igual aqui."""
    containers = _post_containers(pg)
    n = min(containers.count(), limit)
    out = []
    for i in range(n):
        c = containers.nth(i)
        # 07/10: el feed virtualizado desmonta contenedores mientras se desplaza; un enlace que desaparece bloqueaba 30 s y mataba el scan entero (ronda de Threads de las 11:00): se salta ese post
        try:
            links = c.locator('a[href^="/@"]')
            if links.count() == 0:
                continue
            handle_href = links.first.get_attribute("href", timeout=4000)
            handle = handle_href[2:] if handle_href else None
            permalink = None
            for j in range(links.count()):
                href = links.nth(j).get_attribute("href", timeout=4000)
                if href and "/post/" in href:
                    permalink = f"https://www.threads.com{href}"
                    break
            text = c.inner_text(timeout=4000)
        except Exception as exc:
            if isinstance(exc, (BotWarningDetected, WrongAccountActive)):
                raise
            continue
        out.append((handle, permalink, text[:280]))
    return out


def _already_commented_in_modal(pg, n_before):
    """Escanea el contenido anadido al abrir el modal de "Responder"
    (todo lo que aparece a partir del indice `n_before` en
    `[data-pressable-container]`, ver comentario en reply_to()) buscando un
    comentario cuyo AUTOR seamos nosotros - via el primer enlace
    `a[href^="/@"]` de cada contenedor, mismo patron fiable que
    `_extract_posts`. Confirmado en vivo el 23/09: el modal incluye el post
    original repetido (mismo autor que el de fondo) mas los comentarios
    reales visibles."""
    containers = _post_containers(pg)
    n_after = containers.count()
    for i in range(n_before, n_after):
        links = containers.nth(i).locator('a[href^="/@"]')
        if links.count() == 0:
            continue
        href = links.first.get_attribute("href") or ""
        handle = href[2:].split("/")[0] if href.startswith("/@") else ""
        if handle == MY_HANDLE:
            return True
    return False


def _find_action_button(container, title_text):
    """Busca, dentro de un post, el boton de accion cuyo SVG interno tiene
    ese <title> exacto (p.ej. 'Me gusta', 'Responder', 'Repostear'). Los
    iconos de Threads no llevan aria-label ni data-testid - el <title> del
    SVG es lo unico estable encontrado en vivo el 17/09."""
    like_titles = ("Me gusta", "Ya no me gusta")
    btns = container.locator('div[role="button"]')
    n = btns.count()
    for i in range(n):
        b = btns.nth(i)
        try:
            t = b.evaluate('(el) => { const t = el.querySelector("svg title"); return t ? t.textContent : null; }', timeout=6000)
        except Exception:
            t = None
        if title_text in like_titles and t in like_titles:
            # 06/10: en una pagina de hilo el contenedor puede incluir mas de un post. Manda el PRIMER boton de like en orden de documento (el del post de arriba): si ese
            # ya es «Ya no me gusta» no se pulsa el «Me gusta» de un post de debajo (un like acabo en el post padre de otra cuenta).
            return b if t == title_text else None
        if t == title_text:
            return b
    return None


def like_in_feed(target, source="feed"):
    """Da like a un post del feed/perfil/busqueda actualmente cargado.

    BUG REAL encontrado en vivo el 21/09 y causa de dos likes reales dados
    a la cuenta equivocada ese mismo dia: el feed "Para ti" es algoritmico
    y se reordena entre la llamada que hace `dump` (para elegir que post)
    y la llamada posterior `like <indice>` - cada comando es un proceso
    nuevo que vuelve a cargar la pagina desde cero, y lo que era el post 2
    en una carga puede ser otro completamente distinto en la siguiente.

    Por eso `target` acepta dos formas:
    - un entero (comportamiento antiguo, indice 0-based) - rapido pero NO
      fiable en el feed "Para ti", solo usar en paginas mas estables
      (perfil, busqueda dentro de una comunidad) donde el orden no cambia
      solo, o cuando ya se sabe que el riesgo es aceptable.
    - un fragmento de texto (recomendado, sobre todo en el feed "Para ti"):
      busca el primer post cuyo texto visible contenga ese fragmento
      exacto (copiado del `dump` anterior) y actua solo si lo encuentra -
      si el post ya no esta en la carga actual, avisa en vez de dar like a
      otra cosa sin darse cuenta."""
    p, pg = _connect()
    try:
        return _like_in_feed(pg, target, source)
    finally:
        p.stop()


def _like_context_of_container(container):
    """Sin lector visual completo: exige cuerpo literario sustantivo en el post."""
    import threads_pool as pool
    import like_context_policy as lcp
    return lcp.can_like(pool.body_of(container.inner_text()), media_present=True)


def _like_in_feed(pg, target, source="feed"):
    url = "https://www.threads.com/" if source == "feed" else source
    pg.goto(url, wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    _assert_active_account(pg)
    containers = _post_containers(pg)
    if isinstance(target, int):
        index = target
        if index >= containers.count():
            print(f"no hay post en el indice {index} (solo {containers.count()} cargados)")
            return
    else:
        index = _find_container_by_text(pg, target)
        containers = _post_containers(pg)  # puede haber crecido tras el scroll
        if index is None:
            raise ActionTargetNotFound(
                f"no se encontro ningun post con el texto {target!r} en la carga "
                "actual - el feed puede haberse reordenado, volver a hacer `dump` "
                "y comprobar si el post sigue apareciendo antes de reintentar."
            )
    c = containers.nth(index)
    allowed, reason = _like_context_of_container(c)
    if not allowed:
        raise ProfileRejected(f"like_contexto:{reason}")
    btn = _find_action_button(c, "Me gusta")
    if btn is None:
        if _find_action_button(c, "Ya no me gusta") is not None:
            print("ese post ya tenia like")
            return "already"
        raise ActionTargetNotFound("no se encontro el boton de like en ese post")
    preview = c.inner_text()[:80].replace("\n", " | ")
    btn.click()
    pg.wait_for_timeout(1000)
    _check_bot_warning(pg)
    confirmed = _find_action_button(c, "Ya no me gusta") is not None
    if not confirmed:
        raise RuntimeError("Threads: like no confirmado; revisar el post antes de reintentar")
    print("like dado (confirmado): " + preview)
    return "created"


class ProfileRejected(RuntimeError):
    """El perfil no pasa el filtro de calidad antes de seguirlo (no es un fallo: se salta con motivo)."""


def _own_container(containers, permalink, handle):
    """(contenedor, autor_del_primero) del post pedido dentro de la pagina de un permalink. Si el post es una RESPUESTA la pagina muestra primero el hilo padre (de otro autor):
    el 06/10 dos de 11 likes fallaron asi («el post abierto es de @blackcat77773, no de @ricardonoziglia»). Se busca el contenedor que enlaza a ese permalink y es del autor esperado;
    si no, el primero del autor esperado entre los primeros contenedores. Sin ninguno: (None, autor del primer contenedor)."""
    code = permalink.rstrip("/").split("/post/")[-1].split("?")[0]
    first_author, fallback = "", None
    for i in range(min(containers.count(), 8)):
        c = containers.nth(i)
        links = c.locator('a[href^="/@"]')
        if links.count() == 0:
            continue
        author = (links.first.get_attribute("href") or "")[2:].split("/")[0]
        if i == 0:
            first_author = author
        if author.casefold() != handle.casefold():
            continue
        if fallback is None:
            fallback = c
        for j in range(links.count()):
            if f"/post/{code}" in (links.nth(j).get_attribute("href") or ""):
                return c, author
    return fallback, first_author


def like_post(permalink, handle):
    """Like abriendo el PERMALINK del post (05/10). La limitacion de 2022/09 («pg.goto a la URL del post redirige a /») ya no existe: probado en vivo el 05/10 en tres
    posts, la pagina carga y el post principal es el primer contenedor. Mas fiable y mas rapido que buscar el fragmento de texto en el perfil del autor (que fallaba
    5-10 % de las veces con ActionTargetNotFound si el autor publica a menudo). Comprueba que el autor del primer contenedor es el esperado antes de actuar."""
    p, pg = _connect()
    try:
        pg.goto(permalink, wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        containers = _post_containers(pg)
        if containers.count() == 0 or "/post/" not in pg.url:
            raise ActionTargetNotFound(f"el permalink no cargo un post ({pg.url})")
        c, author = _own_container(containers, permalink, handle)
        if c is None:
            raise ActionTargetNotFound(f"el post abierto es de @{author}, no de @{handle}; no se da like")
        allowed, reason = _like_context_of_container(c)
        if not allowed:
            raise ProfileRejected(f"like_contexto:{reason}")
        btn = _find_action_button(c, "Me gusta")
        if btn is None:
            if _find_action_button(c, "Ya no me gusta") is not None:
                print("ese post ya tenia like")
                return "already"
            raise ActionTargetNotFound("no se encontro el boton de like en ese post")
        preview = c.inner_text()[:80].replace("\n", " | ")
        btn.click()
        pg.wait_for_timeout(1000)
        _check_bot_warning(pg)
        if _find_action_button(c, "Ya no me gusta") is None:
            raise RuntimeError("Threads: like no confirmado; revisar el post antes de reintentar")
        print("like dado (confirmado, permalink): " + preview)
        return "created"
    finally:
        p.stop()


def collect_posts_scrolling(pg, passes=3, limit=60):
    """(handle, permalink, texto) de los posts visibles tras hacer scroll `passes` veces (05/10: el scan leia solo los 15 primeros de cada pagina sin scroll).
    Deduplica por permalink; para cuando el scroll no carga nada nuevo."""
    seen, out = set(), []
    for step in range(passes + 1):
        for handle, permalink, text in _extract_posts(pg, limit=limit):
            key = (permalink or "").rstrip("/") or (handle, " ".join((text or "").split())[:80])
            if key in seen:
                continue
            seen.add(key)
            out.append((handle, permalink, text))
        if len(out) >= limit or step == passes:
            break
        before = len(seen)
        pg.mouse.wheel(0, 1800)
        pg.wait_for_timeout(1300)
        _check_bot_warning(pg)
        if before == len(seen) and step > 0:
            # nada nuevo en la ultima pasada: se mira una vez mas tras el scroll y se corta
            if not [1 for h, pl, tx in _extract_posts(pg, limit=limit) if ((pl or "").rstrip("/") or (h, " ".join((tx or "").split())[:80])) not in seen]:
                break
    return out[:limit]


_FOLLOWERS_RE = re.compile(r"([\d][\d.,]*)\s*(mil|k|m)?\s+seguidores", re.I)


def _count_text(number, suffix):
    """«1.234» -> 1234; «1,2 mil» / «1.2K» -> 1200; «3 M» -> 3.000.000."""
    suffix = (suffix or "").casefold()
    if suffix:
        return int(float(number.replace(",", ".")) * (1000 if suffix in ("mil", "k") else 1_000_000))
    return int(number.replace(".", "").replace(",", ""))


def profile_info(pg):
    """{'followers': int|None, 'bio': str, 'follows_me': bool} del perfil cargado (lo que ya esta en pantalla al ir a seguir: no cuesta una navegacion mas).
    Estructura real (probada en vivo el 05/10): menu de la app hasta «Archivo», luego `handle / nombre / handle / [Te sigue] / biografia / etiquetas / N seguidores`."""
    try:
        body = pg.inner_text("body")[:2500]
    except Exception:
        return {"followers": None, "bio": "", "follows_me": False}
    match = _FOLLOWERS_RE.search(body)
    followers = None
    if match:
        try:
            followers = _count_text(match.group(1), match.group(2))
        except ValueError:
            followers = None
    head = body[:match.start()] if match else body[:600]
    lines = [line.strip() for line in head.split("\n") if line.strip()]
    if "Archivo" in lines:
        lines = lines[len(lines) - 1 - lines[::-1].index("Archivo") + 1:]        # lo que sigue al menu de la app
    follows_me = any(line.casefold() == "te sigue" for line in lines)
    lines = [line for line in lines if line.casefold() != "te sigue"]
    if len(lines) >= 3 and lines[0].casefold() == lines[2].casefold():
        lines = lines[3:]                                                          # handle, nombre, handle
    return {"followers": followers, "bio": " ".join(" ".join(lines).split())[:400], "follows_me": follows_me}


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# 06/10/2026: fuentes nuevas de Threads (descubiertas en vivo): busqueda «Recientes», pestana «Perfiles» y la lista de seguidores de las cuentas del nicho.
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
SEARCH_MODES = {"top": "", "recent": "&filter=recent", "profiles": "&filter=profiles"}
_ROW_STOP = {"seguir", "siguiendo", "mas perfiles", "más perfiles", "verificado", "te sigue", "solicitado"}


def open_search(pg, query, mode="top"):
    """Abre la busqueda en la pestana pedida: top (Principales), recent (Recientes: posts de hace minutos/horas) o profiles (Perfiles: cuentas por nombre y biografia)."""
    import urllib.parse
    pg.goto(f"https://www.threads.com/search?q={urllib.parse.quote(query)}{SEARCH_MODES[mode]}", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)


def parse_account_rows(text, handles, own=None):
    """[(handle, nombre, bio)] desde el texto de un listado de cuentas: cada fila empieza con una linea igual a un handle conocido (el de su enlace /@handle)
    y sigue con nombre y biografia hasta el boton «Seguir»/«Siguiendo» o el siguiente handle."""
    known = {h.casefold(): h for h in handles}
    own = (own or MY_HANDLE or "").casefold()
    rows, current = [], None
    for raw in str(text or "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        key = line.casefold()
        if key in known and (current is None or len(current[1]) >= 1 or key != current[0].casefold()):
            if current:
                rows.append(current)
            current = [known[key], []]
            continue
        if current is None:
            continue
        if key in _ROW_STOP:
            continue
        current[1].append(line)
    if current:
        rows.append(current)
    out, seen = [], set()
    for handle, lines in rows:
        if handle.casefold() == own or handle.casefold() in seen:
            continue
        seen.add(handle.casefold())
        out.append((handle, lines[0] if lines else "", " ".join(lines[1:])[:300]))
    return out


def collect_account_rows(pg, passes=3, limit=120, scope="body"):
    """Cuentas (handle, nombre, bio) de un listado con scroll: la pestana Perfiles de la busqueda (scope='body') o el dialogo de seguidores (scope='[role=dialog]')."""
    seen, out, stale = set(), [], 0
    for step in range(passes + 1):
        try:
            area = pg.locator(scope).first
            text = area.inner_text()
            handles = area.evaluate("""el => [...new Set([...el.querySelectorAll('a[href^="/@"]')].map(a => (a.getAttribute('href') || '').slice(2).split('/')[0]).filter(Boolean))]""")
        except Exception:
            break
        fresh = 0
        for row in parse_account_rows(text, handles):
            if row[0].casefold() not in seen:
                seen.add(row[0].casefold())
                out.append(row)
                fresh += 1
        stale = 0 if fresh else stale + 1
        if len(out) >= limit or stale >= 2 or step == passes:
            break
        try:
            if scope == "body":
                pg.mouse.wheel(0, 1600)
            else:      # el dialogo tiene su propio contenedor con scroll: la rueda del raton no lo mueve (probado en vivo el 06/10), `scrollTop` si
                pg.evaluate("""sel => { const d = document.querySelector(sel); let best = null;
                    for (const el of d.querySelectorAll('*')) { const cs = getComputedStyle(el);
                        if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 5 && (!best || el.scrollHeight > best.scrollHeight)) best = el; }
                    if (best) best.scrollTop = best.scrollHeight; }""", scope)
        except Exception:
            break
        pg.wait_for_timeout(1500)
        _check_bot_warning(pg)
    return out[:limit]


def _parse_short_count(text):
    """'69' -> 69; '1.234' -> 1234; '12,5 mil' -> 12500; '1,2 M' -> 1200000. None si no es un numero."""
    match = re.match(r"^\s*([\d.,]+)\s*(mil|k|m|mill\.?|millones)?\s*$", str(text or ""), re.I)
    if not match:
        return None
    raw, unit = match.group(1), (match.group(2) or "").lower()
    if unit:
        value = float(raw.replace(".", "").replace(",", ".")) if raw.count(",") == 1 and raw.count(".") == 0 else float(raw.replace(",", "."))
        return int(value * (1000 if unit in ("mil", "k") else 1_000_000))
    digits = re.sub(r"[.,\s]", "", raw)
    return int(digits) if digits.isdigit() else None


_FOLLOWING_TAB = re.compile(r"Seguidos\s*\n\s*([\d.,]+(?:\s?(?:mil|k|M|mill\.?))?)")


def following_count(pg):
    """Cuantas cuentas sigue el perfil abierto: el perfil solo muestra «N seguidores», pero el dialogo que abre trae las pestanas «Seguidores N | Seguidos N | En comun»
    (David lo comprobo a mano el 07/10: «Seguidores 10 / Seguidos 69»). Abre y cierra el dialogo (~3 s); None si no se puede leer."""
    try:
        pg.get_by_text(re.compile(r"\bseguidores$", re.I)).first.click(timeout=4000)
        pg.wait_for_timeout(1500)
        dialog = pg.locator("[role=dialog]")
        if dialog.count() == 0:
            return None
        match = _FOLLOWING_TAB.search(dialog.first.inner_text())
        return _parse_short_count(match.group(1)) if match else None
    except Exception as exc:
        if isinstance(exc, (BotWarningDetected, WrongAccountActive)):
            raise
        return None
    finally:
        # el dialogo debe quedar CERRADO: con el abierto el control «Seguir» del perfil no se encuentra (4 follows fallidos en la ronda de las 12:39 del 07/10)
        try:
            for _ in range(2):
                pg.keyboard.press("Escape")
                pg.wait_for_timeout(500)
                if pg.locator("[role=dialog]").count() == 0:
                    break
            else:
                pg.reload(wait_until="domcontentloaded", timeout=50000)
                pg.wait_for_timeout(2000)
        except Exception:
            pass


def _vet_info(pg, handle):
    """Perfil abierto + contador de seguidos, handle y red: `exec_common.follow_vet` anota los contadores (hubs de reciprocidad, 07/10)."""
    info = profile_info(pg)
    info["following"] = following_count(pg)
    info["handle"], info["network"] = handle, "threads"
    return info


def collect_followers(pg, handle, passes=4, limit=120, kind="seguidores"):
    """Cuentas de la lista de seguidores (o seguidos) de `handle`, las mas recientes primero. Devuelve (info_del_perfil, filas)."""
    pg.goto(f"https://www.threads.com/@{handle}", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    _assert_active_account(pg)
    info = profile_info(pg)
    try:
        # el perfil solo muestra «N seguidores»; el dialogo trae las pestanas Seguidores | Seguidos | En comun (probado en vivo el 06/10)
        pg.get_by_text(re.compile(r"\bseguidores$", re.I)).first.click(timeout=5000)
        pg.wait_for_timeout(2200)
        if pg.locator("[role=dialog]").count() == 0:
            return info, []
        tabs = _FOLLOWING_TAB.search(pg.locator("[role=dialog]").first.inner_text())
        info["following"] = _parse_short_count(tabs.group(1)) if tabs else None
        if kind.casefold() == "seguidos":
            pg.locator("[role=dialog]").get_by_text("Seguidos", exact=True).first.click(timeout=5000)
            pg.wait_for_timeout(2200)
        rows = collect_account_rows(pg, passes=passes, limit=limit, scope="[role=dialog]")
    except Exception as exc:
        if isinstance(exc, (BotWarningDetected, WrongAccountActive)):
            raise
        return info, []
    finally:
        try:
            pg.keyboard.press("Escape")
        except Exception:
            pass
    return info, [row for row in rows if row[0].casefold() != handle.casefold()]


def new_followers(pg):
    """Handles que acaban de seguirnos, de la pagina de Actividad («<handle> [y N mas] <edad> Ahora te sigue(n)»). Los «y N mas» no traen handle: solo se devuelven los visibles."""
    pg.goto("https://www.threads.com/activity", wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2800)
    _check_bot_warning(pg)
    handles = pg.evaluate("""() => [...new Set([...document.querySelectorAll('a[href^="/@"]')].map(a => (a.getAttribute('href') || '').slice(2).split('/')[0]).filter(Boolean))]""")
    return parse_new_followers(pg.inner_text("body"), handles)


def parse_new_followers(text, handles):
    known = {h.casefold(): h for h in handles}
    lines = [line.strip() for line in str(text or "").split(chr(10)) if line.strip()]
    out = []
    for i, line in enumerate(lines):
        if "te sigue" not in line.casefold() or not line.casefold().startswith("ahora"):
            continue
        for back in range(1, 7):                   # el handle del bloque queda unas lineas antes («handle | y 1 mas | 4 h | hace 4 horas | Ahora te sigue(n)»)
            if i - back < 0:
                break
            candidate = known.get(lines[i - back].casefold())
            if candidate:
                if candidate.casefold() != MY_HANDLE.casefold() and candidate not in out:
                    out.append(candidate)
                break
    return out


def like_latest(handle, vet=None, max_age_days=45):
    """Like al ultimo post propio y reciente de `handle` (no fijado, no repost, en espanol, sin politica), con el perfil ya cargado por `follow` si es el mismo (no navega
    otra vez). `vet(info)` como en `follow`. Devuelve ('created'|'already', texto_del_post). Lanza ProfileRejected si no hay un post apto."""
    import threads_pool as pool
    import text_common as bp
    import scan_common as sc
    p, pg = _connect()
    try:
        here = (pg.url or "").rstrip("/").casefold().endswith(f"/@{handle}".casefold())
        if not here:
            pg.goto(f"https://www.threads.com/@{handle}", wait_until="domcontentloaded", timeout=50000)
            pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        if vet is not None:
            reason = vet(profile_info(pg))
            if reason:
                raise ProfileRejected(reason)
        containers = _post_containers(pg)
        for i in range(min(containers.count(), 8)):
            c = containers.nth(i)
            try:
                text = c.inner_text()
            except Exception:
                continue
            links = c.locator('a[href^="/@"]')
            author = (links.first.get_attribute("href") or "")[2:].split("/")[0] if links.count() else ""
            if author.casefold() != handle.casefold() or "fijado" in " ".join(text.split())[:60].casefold():
                continue
            age = pool.parse_age_hours(text)
            if age is not None and age > max_age_days * 24:
                continue
            body = pool.body_of(text)
            if len(body) < 25 or sc.is_political(body) or (bp.looks_english(body) and not bp.looks_spanish(body)):
                continue
            if not _like_context_of_container(c)[0]:
                continue
            btn = _find_action_button(c, "Me gusta")
            if btn is None:
                if _find_action_button(c, "Ya no me gusta") is not None:
                    return "already", body[:120]
                continue
            btn.click()
            pg.wait_for_timeout(1000)
            _check_bot_warning(pg)
            if _find_action_button(c, "Ya no me gusta") is None:
                raise RuntimeError("Threads: like no confirmado; revisar el post antes de reintentar")
            print(f"{handle}: like al ultimo post (confirmado): {body[:70]}")
            return "created", body[:120]
        raise ProfileRejected("sin post reciente apto")
    finally:
        p.stop()


def reply_to(target, text, source="feed"):
    """Responde a un post localizado en una pagina de listado (feed/
    activity/perfil/busqueda) - NUNCA pg.goto() directo a la URL del post
    (ver correccion del 22/09 en el docstring del modulo: eso redirige a
    "/" sin avisar). `target` es un fragmento de texto del post (mismo
    criterio que like_in_feed - el feed "Para ti" se reordena, buscar por
    texto es lo unico fiable ahi).

    Verificado en vivo el 22/09: click en 'Responder' abre el compositor
    real y acepta texto sin problema. El envio final (boton 'Respuesta')
    se deja probado hasta el aria-disabled=None con texto real escrito,
    sin llegar a pulsarlo en la investigacion para no dejar una respuesta
    de prueba publica en una cuenta ajena - queda confirmado del todo con
    el primer uso real en un plan.json (mismo criterio que post(), que
    tampoco se probo con un envio completo hasta el primer post real)."""
    _check_length(text)
    _check_spanish_orthography(text)
    p, pg = _connect()
    try:
        url = "https://www.threads.com/" if source == "feed" else source
        pg.goto(url, wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        index = _find_container_by_text(pg, target)
        if index is None:
            raise ActionTargetNotFound(
                f"no se encontro ningun post con el texto {target!r} en la carga "
                "actual - el feed puede haberse reordenado, volver a hacer `dump` "
                "y comprobar si el post sigue apareciendo antes de reintentar."
            )
        containers = _post_containers(pg)
        n_before = containers.count()  # tras el scroll de la busqueda, no antes
        c = containers.nth(index)
        btn = _find_action_button(c, "Responder")
        if btn is None:
            raise ActionTargetNotFound("no se encontro el boton 'Responder' en ese post")
        preview = c.inner_text()[:80].replace("\n", " | ")
        btn.click(force=True)
        pg.wait_for_timeout(1500)
        # Guardia anadida 23/09 (mismo criterio que x_interact.py): Threads no
        # permite navegar directo a la URL de un post (redirige a "/" sin
        # avisar, ver docstring del modulo), asi que la unica forma de ver
        # los comentarios existentes es el propio modal que se abre al pulsar
        # "Responder" - reutiliza el post original de fondo + sus comentarios.
        # Confirmado en vivo: los `[data-pressable-container]` del modal se
        # anaden DESPUES de los del feed de fondo en el DOM, asi que todo lo
        # que aparece a partir del indice `n_before` es contenido del modal
        # (post original repetido + comentarios reales).
        if _already_commented_in_modal(pg, n_before):
            pg.keyboard.press("Escape")
            raise AlreadyCommented(f"Ya hay un comentario nuestro en ese post - {preview}")
        box = pg.locator('div[contenteditable="true"]').first
        box.click(force=True)
        box.type(text, delay=12)
        pg.wait_for_timeout(500)
        send_btn = pg.locator('div[role="button"]').filter(
            has=pg.locator('svg title:text-is("Respuesta")')
        ).first
        if send_btn.count() == 0:
            raise ActionTargetNotFound(
                "no se encontro el boton de enviar - el texto puede haber quedado "
                "escrito en el compositor sin enviarse, revisar a mano"
            )
        try:
            send_btn.click(force=True, timeout=8000)
        except Exception:
            # 04/10: "Element is outside of the viewport" dejo una respuesta escrita sin enviar; el clic por DOM
            # no depende de la posicion en pantalla
            send_btn.evaluate("el => el.click()")
        pg.wait_for_timeout(1800)
        _check_bot_warning(pg)
        print("reply enviada; confirmación remota pendiente: " + preview)
        return "unverified"
    finally:
        p.stop()


def _top_profile_follow_button(pg):
    """Botón Follow/Following superior del perfil; ignora sugerencias inferiores."""
    allowed = {
        "seguir", "siguiendo", "follow", "following",
        "solicitado", "requested", "pendiente", "pending",
    }
    buttons = pg.get_by_role("button")
    best = None
    best_y = None
    for i in range(buttons.count()):
        button = buttons.nth(i)
        try:
            text = (button.inner_text() or "").strip().casefold()
            box = button.bounding_box()
        except Exception:
            continue
        if text in allowed and box and (best_y is None or box["y"] < best_y):
            best = button
            best_y = box["y"]
    return best


def _profile_follow_button_state(button):
    if button is None:
        return None
    try:
        text = (button.inner_text() or "").strip().casefold()
    except Exception:
        return None
    if text in {"siguiendo", "following"}:
        return "following"
    if text in {"solicitado", "requested", "pendiente", "pending"}:
        return "pending"
    if text in {"seguir", "follow"}:
        return "follow"
    return None


def follow(handle, vet=None):
    """Sigue una cuenta verificando el botón superior del perfil objetivo. `vet(info)` (05/10) devuelve un motivo de rechazo o None: se decide con el perfil ya
    cargado (seguidores y bio), sin una navegacion extra, y un rechazo lanza ProfileRejected (la ejecucion lo anota como saltado, no como fallo)."""
    p, pg = _connect()
    try:
        pg.goto(
            f"https://www.threads.com/@{handle}",
            wait_until="domcontentloaded",
            timeout=50000,
        )
        pg.wait_for_timeout(2200)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        if vet is not None:
            reason = vet(_vet_info(pg, handle))
            if reason:
                raise ProfileRejected(reason)

        control = _top_profile_follow_button(pg)
        state = _profile_follow_button_state(control)
        if state == "following":
            print(f"{handle}: ya estaba seguido")
            return "already"
        if state == "pending":
            print(f"{handle}: solicitud ya pendiente")
            return "pending"
        if state != "follow":
            raise ActionTargetNotFound(
                f"{handle}: no se encontró un control Follow inequívoco del perfil"
            )

        control.click()
        pg.wait_for_timeout(1500)
        _check_bot_warning(pg)
        final = _profile_follow_button_state(_top_profile_follow_button(pg))
        if final == "following":
            print(f"{handle}: FOLLOWED (confirmado en control del perfil)")
            return "followed"
        if final == "pending":
            print(f"{handle}: solicitud enviada (pendiente de aprobación)")
            return "pending"
        raise RuntimeError(
            f"{handle}: follow no confirmado en el control del perfil; "
            "revisar antes de reintentar"
        )
    finally:
        p.stop()

def unfollow(handle):
    """Deja de seguir a `handle` desde su perfil: boton «Siguiendo» -> dialogo «¿Dejar de seguir a X?» -> «Dejar de seguir» (flujo comprobado en vivo el 06/10). Devuelve
    'unfollowed' o 'already'; verifica el estado final del boton."""
    p, pg = _connect()
    try:
        pg.goto(f"https://www.threads.com/@{handle}", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2200)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        control = _top_profile_follow_button(pg)
        state = _profile_follow_button_state(control)
        if state == "follow":
            return "already"
        if state != "following":
            raise ActionTargetNotFound(f"{handle}: no hay un control «Siguiendo» inequivoco en el perfil (estado {state!r})")
        control.click()
        pg.wait_for_timeout(1200)
        dialog = pg.locator('[role="dialog"]')
        if dialog.count() == 0 or "Dejar de seguir" not in dialog.first.inner_text():
            raise RuntimeError("Threads: no aparecio el dialogo de confirmacion de «Dejar de seguir»")
        dialog.first.get_by_text("Dejar de seguir", exact=True).last.click(timeout=5000)
        pg.wait_for_timeout(1500)
        _check_bot_warning(pg)
        if _profile_follow_button_state(_top_profile_follow_button(pg)) != "follow":
            raise RuntimeError(f"{handle}: unfollow no confirmado en el control del perfil")
        print(f"{handle}: UNFOLLOWED (confirmado en el control del perfil)")
        return "unfollowed"
    finally:
        p.stop()


def _check_length(text, limit=500):
    """Threads admite 500 caracteres (REGLAS.md, confirmado 21/09) - no
    280 (X) ni 300 (Bluesky), ese fue exactamente el bug real ya visto una
    vez en X (copiar un limite de otra red sin comprobar)."""
    check_length(text, limit)


# _check_spanish_orthography importada de x_interact.py (23/09).



def _matching_own_post_urls(pg, text):
    """Permalinks propios visibles cuyo cuerpo contiene el texto objetivo."""
    pg.goto(f"https://www.threads.com/@{MY_HANDLE}",
            wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(2200)
    _check_bot_warning(pg)
    needle = " ".join((text or "").split())[:140]
    if not needle:
        return set()
    urls = set()
    for handle, permalink, visible in _extract_posts(pg, limit=20):
        haystack = " ".join((visible or "").split())
        if (handle and handle.casefold() == MY_HANDLE.casefold()
                and permalink and needle in haystack):
            urls.add(permalink)
    return urls



def post(text, image_path=None):
    """Publica un hilo nuevo. Confirmado en vivo el 17/09 que el
    compositor abre bien (contenteditable real + boton 'Publicar').
    Adjuntar imagen anadido 24/09 (cola de autopromocion) - el boton de
    adjuntar no tiene aria-label, solo un <title> dentro del <svg>
    ("Adjuntar archivo multimedia"), es el primero de los 4 botones de
    iconos sin etiqueta del dialogo de composicion (media/GIF/emoji/
    sticker, en ese orden fijo)."""
    _check_length(text)
    _check_spanish_orthography(text)
    p, pg = _connect()
    try:
        before_urls = _matching_own_post_urls(pg, text)
        pg.goto("https://www.threads.com/", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2000)
        _check_bot_warning(pg)
        _assert_active_account(pg)
        # 06/10: el placeholder cambio a «¿Qué novedades hay?» y el campo de la portada ya no es editable: el compositor se abre con «Nuevo hilo» (dialogo)
        try:
            pg.get_by_text("Nuevo hilo", exact=True).first.click(timeout=8000)
        except Exception:
            pg.get_by_text("Qué novedades", exact=False).first.click(timeout=8000)
        pg.wait_for_timeout(1500)
        box = pg.locator('div[role="dialog"] div[contenteditable="true"]').first
        box.click()
        box.type(text, delay=12)
        pg.wait_for_timeout(600)
        if image_path:
            # Validado en vivo en main el 25/09: el filechooser por click
            # puede hacer timeout. Usar el input ya presente en el diálogo.
            dialog = pg.locator('div[role="dialog"]').first
            file_input = dialog.locator('input[type="file"]')
            if file_input.count() != 1:
                raise RuntimeError(
                    "Threads: input de archivo ausente o ambiguo; no adjuntar a ciegas"
                )
            file_input.first.set_input_files(image_path)
            pg.wait_for_timeout(2500)
        pg.locator('div[role="dialog"]').get_by_role("button", name="Publicar", exact=True).last.click(timeout=8000)
        pg.wait_for_timeout(3500)
        _check_bot_warning(pg)
        after_urls = _matching_own_post_urls(pg, text)
        created = after_urls - before_urls
        if len(created) != 1:
            raise RuntimeError(
                "Threads recibió el envío pero no hay un único permalink nuevo "
                "verificable; revisar perfil ANTES de reintentar"
            )
        permalink = next(iter(created))
        print("post publicado y confirmado: " + permalink)
        return permalink
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
        elif cmd == "profile":
            ensure_browser(); dump_profile(sys.argv[2] if len(sys.argv) > 2 else None)
        elif cmd == "notifications":
            ensure_browser(); dump_notifications()
        elif cmd == "search":
            ensure_browser(); dump_search(sys.argv[2])
        elif cmd == "like":
            arg = sys.argv[2]
            try:
                target = int(arg)
            except ValueError:
                target = arg
            ensure_browser(); like_in_feed(target, sys.argv[3] if len(sys.argv) > 3 else "feed")
        elif cmd == "follow":
            ensure_browser(); follow(sys.argv[2])
        elif cmd == "reply":
            ensure_browser(); reply_to(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "feed")
        elif cmd == "post":
            ensure_browser(); post(sys.argv[2])
        elif cmd == "daily":
            ensure_browser(); daily_briefing()
        else:
            print(__doc__)
            sys.exit(1)

    try:
        _dispatch()
    except BotWarningDetected as e:
        print(str(e))
        sys.exit(2)
    except WrongAccountActive as e:
        print(str(e))
        sys.exit(3)
