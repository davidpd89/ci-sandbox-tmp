"""
Herramienta unica para el dia a dia de Instagram (@davidportodiaz) - mismo
patron que x_interact.py/threads_interact.py/reddit_interact.py (Edge real
via CDP puerto 9223, ya logueado - David dejo la sesion lista el
21/09/2026). Instagram es, de las cinco redes de este proyecto, la mas
sensible a deteccion de bots - por eso esta herramienta incluye
humanizacion real (raton, tecleo, tiempo de lectura, scroll), no solo el
seguro que para ante un aviso.

Construida el 21/09/2026, primera sesion real ejecutada el mismo dia tras
la orden explicita de David. Ver SISTEMA_DIARIO_INSTAGRAM/diario/2026-09-21.md
para el detalle completo de bugs reales encontrados y corregidos en vivo.

Uso:
    python instagram_interact.py ensure-browser
    python instagram_interact.py health
    python instagram_interact.py feed
    python instagram_interact.py notifications
    python instagram_interact.py daily
    python instagram_interact.py profile [handle]
    python instagram_interact.py explore <hashtag_sin_almohadilla>
    python instagram_interact.py search-accounts "consulta"
    python instagram_interact.py like <url_del_post_o_indice_en_feed>
    python instagram_interact.py follow <handle>
    python instagram_interact.py comment <url_del_post_o_indice_en_feed> "texto"
    python instagram_interact.py edit-bio "texto nuevo"

Sobre "like"/"comment": usar SIEMPRE la URL/permalink del post
(`/<handle>/p/<id>/`), nunca el indice del feed 'Para ti' salvo para
pruebas rapidas - BUG REAL confirmado en vivo el 21/09: ese feed se
reordena en cada carga (mismo problema ya documentado en Threads el mismo
dia), 3 intentos seguidos de actuar sobre un indice fallaron los 3 porque
el post ya no estaba ahi en la siguiente carga.

CONFIRMADO EN VIVO el 21/09 (primera sesion real, con acciones reales):
- Cuenta activa confirmada por el enlace `a[href='/davidportodiaz/']`
  (con o sin texto visible segun la pagina - ver `_active_handle`).
- `edit_bio()`: funciona, bio corregida y verificada en el perfil real.
- `follow()`: funciona, verificado por incremento real del contador de
  seguidores de la cuenta seguida (no solo por el texto del boton).
- `like()`/`comment()` sobre un permalink de post: funcionan, verificados
  con una recarga fresca de la pagina despues de actuar.
- BUG REAL encontrado y corregido: en la pagina de un post individual,
  cada comentario visible tiene TAMBIEN su propio icono pequeño de "Me
  gusta" ademas del boton grande del post - `_find_action_button` ahora
  filtra por tamaño de boton (>=30px) para no dar like al comentario de
  otra persona por error en vez de al post.
- BUG REAL encontrado y corregido: `_bezier_mouse_move` fallaba con
  `TypeError`/`ValueError` porque `bounding_box()` de Playwright devuelve
  floats y `random.randint()` exige enteros - redondear antes de usar.
- BUG REAL encontrado y corregido: el placeholder real del cuadro de
  comentario es "Agrega un comentario..." (con puntos suspensivos ASCII),
  no "Añade un comentario…" como se habia escrito a ciegas la primera vez
  sin verificar en vivo - ahora se aceptan varias variantes.

Humanizacion adoptada de C:\\GIT\\Instagram (repo aparte, casi dos meses de
intentos reales mayo-septiembre 2026, ver SISTEMA_DIARIO_INSTAGRAM/README.md
para el detalle de que se cogio y que no): movimiento de raton por curva
de Bezier, tecleo con velocidad variable y typos reales corregidos con
Backspace, tiempo de "lectura" simulado antes de actuar sobre un post
(con micro-scroll y micro-movimientos de raton durante la espera), y
scroll no-lineal con algun retroceso ocasional. Nunca saltar directo a
una coordenada ni escribir un texto de golpe con `.type()` sin retraso.
"""
import os
import sys
import time
import random
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
# Mismo perfil dedicado que las otras tres herramientas - David logueo
# @davidportodiaz en Instagram ahi el 21/09/2026. Ver PENDIENTES.md sobre
# la posibilidad de migrar a un perfil de Edge aislado solo para esta red
# si en algun momento se ve necesario (los intentos archivados en
# C:\GIT\Instagram preferian perfiles aislados).
EDGE_USER_DATA = r"C:\Temp\rrss-davidporto-edge"
MY_HANDLE = "davidportodiaz"

# Seguro anti-bot ampliado (21/09) con las senales que los intentos
# reales de C:\GIT\Instagram encontraron en vivo entre mayo y septiembre
# de 2026 - Instagram es la red mas sensible de las cinco, asi que esta
# lista es mas larga que la de las otras herramientas a proposito.
BOT_WARNING_SIGNALS = [
    "unusual activity", "actividad inusual", "actividad sospechosa",
    "suspicious activity", "we suspended your account",
    "hemos suspendido tu cuenta", "cuenta suspendida",
    "cuenta ha sido deshabilitada", "account disabled",
    "confirma que eres humano", "verify you're human",
    "confirm it's you", "confirma que eres tu",
    "tu cuenta está en riesgo", "your account is at risk",
    "checkpoint", "challenge_required", "acción bloqueada",
    "action blocked", "te has quedado sin", "try again later",
    "inténtalo de nuevo más tarde", "no puedes usar esta función",
]

# Palabras clave que, si aparecen en la URL (no solo en el texto visible),
# tambien cuentan como aviso real - encontrado en vivo en los intentos de
# C:\GIT\Instagram (instagram_ultra_robusto_2026.py, detect_challenge_advanced).
BOT_WARNING_URL_SIGNALS = [
    "challenge", "suspended", "blocked", "disabled", "checkpoint",
]


class InteractionsPaused(RuntimeError):
    pass


# 03/10/2026 David pauso la interaccion (solo publicar); 04/10/2026 la REACTIVA con calentamiento suave: de momento
# solo 10 follows al dia a gente que comenta en posts de editoriales/libros (`instagram_commenters_scan.py`),
# cuentas pequenas que puedan seguirnos de vuelta. Ritmo humano; ante cualquier aviso se para (BotWarningDetected).
# Volver a True pausa de nuevo scan, follow, like y comment.
INTERACTIONS_PAUSED = False


def _refuse_if_paused():
    if INTERACTIONS_PAUSED:
        raise InteractionsPaused(
            "Automatizacion de interaccion en Instagram desactivada (03/10, decision de "
            "David): Instagram es solo para publicar. Ver SISTEMA_DIARIO_INSTAGRAM/ESTADO.md."
        )


class BotWarningDetected(RuntimeError):
    pass


# ActionTargetNotFound importada de scan_common (23/09, centralizada tras
# ver que se estaba a punto de duplicar por tercera vez).


def _check_bot_warning(pg):
    url = pg.url.lower()
    for signal in BOT_WARNING_URL_SIGNALS:
        if signal in url:
            raise BotWarningDetected(
                f"AVISO REAL EN LA URL: \"{signal}\" ({pg.url}). "
                "Parando de inmediato. Avisar a David antes de reintentar."
            )
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


# _check_spanish_orthography importada de x_interact.py (23/09).


def _check_length(text, limit=2200):
    """2.200 caracteres - limite real de un caption/comentario de Instagram
    (ver INSTAGRAM.md seccion 16.3), no el de otra red."""
    check_length(text, limit)


# ---------------------------------------------------------------------
# Humanizacion - adoptado de C:\GIT\Instagram, ver README.md de esta red
# para el criterio de que se cogio y que no.
# ---------------------------------------------------------------------

def _human_delay(min_ms=400, max_ms=1200):
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


def _bezier_mouse_move(pg, target_x, target_y, steps=None):
    """Mueve el raton hasta (target_x, target_y) por una curva de Bezier
    cubica con jitter, en vez de saltar directo - tecnica confirmada en
    C:\\GIT\\Instagram (instagram_ultra_robusto_2026.py,
    simulate_ultra_human_behavior)."""
    # BUG REAL encontrado en vivo el 21/09: bounding_box() de Playwright
    # devuelve floats, y random.randint() exige enteros - fallaba con
    # TypeError/ValueError en cuanto el objetivo no caia en un pixel
    # entero. Redondear target_x/target_y a entero antes de nada.
    target_x, target_y = int(round(target_x)), int(round(target_y))
    box = pg.viewport_size or {"width": 1280, "height": 800}
    start_x = random.randint(100, max(101, box["width"] - 100))
    start_y = random.randint(100, max(101, box["height"] - 100))
    c1x = random.randint(min(start_x, target_x), max(start_x, target_x))
    c1y = random.randint(min(start_y, target_y), max(start_y, target_y))
    c2x = random.randint(min(start_x, target_x), max(start_x, target_x))
    c2y = random.randint(min(start_y, target_y), max(start_y, target_y))
    steps = steps or random.randint(18, 28)
    for i in range(steps):
        t = i / steps
        x = (1 - t) ** 3 * start_x + 3 * (1 - t) ** 2 * t * c1x + 3 * (1 - t) * t ** 2 * c2x + t ** 3 * target_x
        y = (1 - t) ** 3 * start_y + 3 * (1 - t) ** 2 * t * c1y + 3 * (1 - t) * t ** 2 * c2y + t ** 3 * target_y
        x += random.randint(-6, 6)
        y += random.randint(-6, 6)
        pg.mouse.move(x, y)
        pg.wait_for_timeout(random.randint(12, 35))


def _human_click(pg, locator):
    """Mueve el raton por curva de Bezier hasta el elemento y hace clic -
    nunca un clic directo sin mover el raton antes."""
    box = locator.bounding_box()
    if box is None:
        raise RuntimeError("elemento no visible, no se puede mover el raton hasta el")
    tx = box["x"] + box["width"] / 2 + random.randint(-4, 4)
    ty = box["y"] + box["height"] / 2 + random.randint(-4, 4)
    _bezier_mouse_move(pg, tx, ty)
    _human_delay(80, 250)
    pg.mouse.click(tx, ty)


def _human_type(pg, locator, text):
    """Teclea con velocidad variable y typos reales corregidos con
    Backspace (~15% de probabilidad por caracter) - tecnica confirmada en
    C:\\GIT\\Instagram (instagram_definitivo_anti_ban.py,
    simulate_human_typing)."""
    locator.click()
    _human_delay(200, 500)
    typo_chars = "qwertyuiopasdfghjklzxcvbnm"
    for i, ch in enumerate(text):
        if i > 0 and random.random() < 0.15:
            locator.type(random.choice(typo_chars))
            pg.wait_for_timeout(random.randint(100, 300))
            locator.press("Backspace")
            pg.wait_for_timeout(random.randint(200, 500))
        locator.type(ch)
        pg.wait_for_timeout(random.randint(200, 400) if ch == " " else random.randint(70, 190))


def _simulate_reading(pg, word_count):
    """Simula el tiempo real que tardaria una persona en leer un post
    (200-250 palabras/minuto, con variacion) antes de actuar sobre el -
    durante la espera, micro-scroll y micro-movimientos de raton, nunca
    un sleep() a secas. Tecnica de C:\\GIT\\Instagram
    (instagram_definitivo_anti_ban.py, simulate_reading_time)."""
    speed = random.randint(200, 250)
    reading_time = (max(word_count, 5) / speed) * 60 * random.uniform(0.8, 1.4)
    reading_time = min(reading_time, 12)  # techo razonable para no alargar la sesion de mas
    start = time.time()
    while time.time() - start < reading_time:
        pg.mouse.wheel(0, random.randint(-30, 30))
        pg.wait_for_timeout(random.randint(400, 1100))


def _jittery_scroll(pg, direction="down"):
    """Varios scrolls pequenos con algun retroceso ocasional, nunca un
    unico salto grande - tecnica de C:\\GIT\\Instagram
    (instagram_definitivo_anti_ban.py, jittery_scroll)."""
    n = random.randint(3, 6)
    for _ in range(n):
        amount = random.randint(150, 400) * (1 if direction == "down" else -1)
        pg.mouse.wheel(0, amount)
        pg.wait_for_timeout(random.randint(250, 700))
        if random.random() < 0.3:
            pg.mouse.wheel(0, random.randint(-40, 40))
            pg.wait_for_timeout(random.randint(120, 300))


# ---------------------------------------------------------------------
# Navegador
# ---------------------------------------------------------------------

def _cdp_alive():
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3)
        return True
    except Exception:
        return False


def ensure_browser():
    if _cdp_alive():
        print("CDP ya activo en 9223")
        return
    print("CDP no responde, abriendo Edge (perfil dedicado de la automatizacion)...")
    subprocess.Popen([
        EDGE_EXE,
        "--remote-debugging-port=9223",
        f"--user-data-dir={EDGE_USER_DATA}",
        "https://www.instagram.com/",
    ])
    for _ in range(20):
        time.sleep(1)
        if _cdp_alive():
            print("CDP arriba.")
            return
    raise RuntimeError("Edge no respondio en CDP 9223 tras 20s")


def _connect():
    _refuse_if_paused()
    p = sync_playwright().start()
    try:
        import browser_common as bc
        browser = bc.connect_cdp(p.chromium, CDP_URL)
        pg = bc.new_owned_page(browser, lean=False)
        return bc.OwnedPlaywright(p, pg), pg
    except Exception:
        p.stop()
        raise


def _active_handle(pg):
    """Confirma la cuenta activa via el enlace con href exacto
    '/<handle>/'. BUG REAL encontrado en vivo el 21/09: la primera version
    solo aceptaba el enlace CON texto visible (el del selector de cuenta
    arriba a la derecha en la home), pero ese elemento concreto no esta
    presente en todas las paginas (ej. el perfil de otra cuenta) - ahi
    solo esta el icono de la barra lateral (mismo href, sin texto).
    Corregido: aceptar cualquiera de los dos, con o sin texto, mientras el
    href sea exacto."""
    link = pg.locator(f"a[href='/{MY_HANDLE}/']")
    return MY_HANDLE if link.count() > 0 else None


def _health_check(pg):
    """Nucleo de health(), extraido el 22/09 (mismo patron que
    x_interact.py/threads_interact.py) para que daily_briefing()/
    instagram_scan.py puedan reutilizar la misma conexion en vez de abrir
    una aparte solo para comprobar la sesion. Devuelve (ok, mensaje)."""
    pg.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(3000)
    _check_bot_warning(pg)
    active = None
    for _ in range(5):
        active = _active_handle(pg)
        if active:
            break
        pg.wait_for_timeout(1000)
    if active is None:
        return False, "PROBLEMA: no se pudo confirmar la cuenta activa - puede que la sesion haya caducado o que el selector haya cambiado."
    return True, f"OK: sesion logueada y cuenta activa confirmada como @{MY_HANDLE}."


def health():
    p, pg = _connect()
    try:
        ok, msg = _health_check(pg)
        print(msg)
    finally:
        p.stop()


def daily_briefing():
    """Disparador diario en una sola conexion (22/09, mismo patron que
    x_interact.py/threads_interact.py daily): health + notifications +
    feed. Para de inmediato si el health check falla."""
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
    pg.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(3000)
    _check_bot_warning(pg)
    _jittery_scroll(pg, "down")
    print(pg.inner_text("body")[:6000])


def dump_feed():
    p, pg = _connect()
    try:
        _dump_feed(pg)
    finally:
        p.stop()


def _dump_notifications(pg):
    """Abre el panel de Notificaciones (icono de campana, NO una pagina
    aparte - confirmado en vivo el 22/09: /notifications redirige a un
    fallback vacio, el contenido real esta en un panel superpuesto que se
    abre con click sobre el icono de la barra lateral, sin cambiar de
    URL). Sirve tanto para reciprocidad real (quien nos sigue/interactua)
    como para sugerencias por conexion mutua ("X y N mas siguen esta
    cuenta"), util para descubrir candidatos nuevos con coste minimo (una
    sola conexion, sin navegar a paginas nuevas)."""
    pg.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    btn = pg.locator('svg[aria-label="Notificaciones"]').first.locator(
        'xpath=ancestor::*[@role="link" or @role="button" or self::a][1]'
    )
    btn.click(force=True)
    pg.wait_for_timeout(2000)
    print(pg.inner_text("body")[:3000])


def dump_notifications():
    p, pg = _connect()
    try:
        _dump_notifications(pg)
    finally:
        p.stop()


def _post_containers(pg):
    return pg.locator("article")


def _extract_posts(pg, limit=12):
    """Vuelca (handle, permalink, texto) por cada post visible en el feed -
    equivalente a `_extract_articles`/`_extract_posts` de x_interact.py/
    threads_interact.py. Confirmado en vivo el 22/09: cada `<article>` del
    feed lleva un enlace de una sola barra (`/handle/`, sin `/p/` ni
    `/reel/`) para la cuenta y otro con `/p/<id>/` para el permalink -
    los posts patrocinados no llevan `/p/`, se descartan solos al no
    encontrar permalink. El feed 'Para ti' se reordena entre cargas (mismo
    aviso ya documentado en X/Threads) - usar el permalink devuelto para
    actuar despues, nunca el indice."""
    containers = _post_containers(pg)
    n = min(containers.count(), limit)
    out = []
    for i in range(n):
        c = containers.nth(i)
        links = c.locator('a[href^="/"]')
        handle = None
        permalink = None
        for j in range(links.count()):
            href = links.nth(j).get_attribute("href")
            if not href:
                continue
            if ("/p/" in href or "/reel/" in href) and "liked_by" not in href and "comments" not in href:
                if permalink is None:
                    permalink = f"https://www.instagram.com{href}"
            elif href.count("/") == 2 and "/p/" not in href and "/reel/" not in href:
                if handle is None:
                    handle = href.strip("/")
        if permalink is None:
            continue
        try:
            text = c.inner_text()[:280]
        except Exception:
            continue
        out.append((handle, permalink, text))
    return out


_NAV_PATHS = {
    "reels", "explore", "direct", "accounts", "popular", "stories",
    MY_HANDLE, "p", "reel", "tags",
}


def _search_accounts(pg, query):
    """Busca cuentas por palabra clave (barra de Buscar, NO el grid de un
    hashtag) - confirmado en vivo el 22/09 como fuente MUCHO mejor que
    `explore/tags/` para el pipeline: da handle + bio/descripcion +
    senales de conexion mutua ("X sigue esta cuenta") en una sola
    interaccion, sin abrir cada post. Tambien expone un aviso real y util
    para filtrar solo: "Perfil con contenido generado con IA".

    BUG REAL (mismo patron ya visto en X/Threads): el click sobre el icono
    de Buscar y sobre el campo de texto necesitan `force=True` - un boton
    de "limpiar" (X) superpuesto intercepta el click normal incluso con el
    campo vacio."""
    pg.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2000)
    _check_bot_warning(pg)
    btn = pg.locator('svg[aria-label="Buscar"]').first.locator(
        'xpath=ancestor::*[@role="link" or @role="button" or self::a][1]'
    )
    btn.click(force=True)
    pg.wait_for_timeout(1200)
    inp = pg.locator('input[placeholder="Buscar"]').first
    inp.click(force=True)
    _human_type(pg, inp, query)
    pg.wait_for_timeout(2000)
    links = pg.locator('a[href^="/"]')
    n = links.count()
    seen = set()
    out = []
    for i in range(n):
        href = links.nth(i).get_attribute("href")
        if not href or href.count("/") != 2:
            continue
        handle = href.strip("/")
        if not handle or handle in _NAV_PATHS or handle in seen:
            continue
        try:
            text = links.nth(i).inner_text().strip()
        except Exception:
            text = ""
        if not text:
            continue  # el enlace del avatar (sin texto) es un duplicado del de al lado
        seen.add(handle)
        out.append((handle, text[:200]))
    return out


def search_accounts(query):
    p, pg = _connect()
    try:
        results = _search_accounts(pg, query)
        for handle, text in results:
            print(f"@{handle} | {text}")
    finally:
        p.stop()


def dump_profile(handle=None):
    p, pg = _connect()
    try:
        h = handle or MY_HANDLE
        pg.goto(f"https://www.instagram.com/{h}/", wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(3000)
        _check_bot_warning(pg)
        print(pg.inner_text("body")[:3000])
    finally:
        p.stop()


def dump_explore(hashtag):
    p, pg = _connect()
    try:
        tag = hashtag.lstrip("#")
        pg.goto(f"https://www.instagram.com/explore/tags/{urllib.parse.quote(tag)}/", wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(3000)
        _check_bot_warning(pg)
        print(pg.inner_text("body")[:4000])
    finally:
        p.stop()


def edit_bio(new_text):
    """Cambia la presentacion (bio) del perfil - confirmado en vivo el
    21/09 (lectura del campo, no la escritura todavia): la pagina
    /accounts/edit/ tiene un unico <textarea> con el texto actual, limite
    real de 150 caracteres, y un boton 'Enviar' para guardar. Mantener la
    cuenta al dia (bio/fotos/enlaces/configuracion) es responsabilidad de
    Claude por instruccion explicita de David (21/09) - no esperar a que
    se pida cada vez."""
    if len(new_text) > 150:
        raise ValueError(f"bio de {len(new_text)} caracteres, por encima del limite de 150")
    _check_spanish_orthography(new_text)
    p, pg = _connect()
    try:
        pg.goto("https://www.instagram.com/accounts/edit/", wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(3000)
        _check_bot_warning(pg)
        # /accounts/edit/ no tiene el mismo nav que el resto de la app (es
        # una pagina de Configuracion aparte) - _active_handle() no aplica
        # aqui, se confirma con el texto plano del propio username visible
        # en la cabecera de "Editar perfil".
        if MY_HANDLE not in pg.inner_text("body"):
            raise RuntimeError("no se pudo confirmar la cuenta activa en la pagina de edicion - abortando antes de actuar")
        area = pg.locator("textarea").first
        area.click()
        pg.keyboard.press("Control+A")
        pg.keyboard.press("Backspace")
        pg.wait_for_timeout(300)
        _human_type(pg, area, new_text)
        pg.wait_for_timeout(500)
        btn = pg.get_by_role("button", name="Enviar").first
        _human_click(pg, btn)
        pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        pg.goto(f"https://www.instagram.com/{MY_HANDLE}/", wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(2500)
        if new_text.split("\n")[0] in pg.inner_text("body"):
            print("bio actualizada (confirmada)")
        else:
            raise RuntimeError("Instagram: no se confirmó el cambio de bio; revisar perfil")
    finally:
        p.stop()


def _find_action_button(scope, aria_label, min_button_size=30):
    """Busca el boton REAL de accion del post (no el de un comentario
    individual) cuyo svg interno tiene ese aria-label exacto ('Me gusta',
    'Comentar', ...).

    BUG REAL encontrado en vivo el 21/09: en la pagina de un post
    individual (permalink `/p/<id>/`), cada comentario visible tiene TAMBIEN
    su propio icono pequeno de "Me gusta" (16x16) ademas del boton grande
    del post (24x24 icono / 40x40 boton) - un `.first` ingenuo coge el
    like de un comentario en vez del post si hay comentarios cargados.
    Se filtra por tamano de boton para quedarse con el real."""
    svgs = scope.locator(f"svg[aria-label='{aria_label}']")
    n = svgs.count()
    best, best_w = None, 0
    for i in range(n):
        svg = svgs.nth(i)
        btn = svg.locator("xpath=ancestor::*[@role='button' or self::button][1]").first
        if btn.count() == 0:
            continue
        box = btn.bounding_box()
        if box and box["width"] >= min_button_size and box["width"] > best_w:
            best, best_w = btn, box["width"]
    return best


def _goto_post(pg, url_or_path):
    """Navega solo a un permalink canónico de post/reel de Instagram."""
    canonical = _validated_post_permalink(url_or_path)
    pg.goto(canonical, wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(3000)
    _check_bot_warning(pg)
    if _active_handle(pg) != MY_HANDLE:
        raise RuntimeError(
            "no se pudo confirmar la cuenta activa esperada; abortando antes de actuar"
        )
    return pg


def _validated_post_permalink(url_or_path):
    """Valida sin navegar y devuelve el permalink /p/ o /reel/ canónico."""
    if not isinstance(url_or_path, str) or not url_or_path.strip():
        raise ValueError("Se requiere permalink de Instagram")
    value = url_or_path.strip()
    if not value.startswith("http"):
        value = (
            f"https://www.instagram.com{value}"
            if value.startswith("/")
            else f"https://www.instagram.com/p/{value}/"
        )
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"instagram.com", "www.instagram.com"}
        or parsed.username
        or parsed.password
        or parsed.port
    ):
        raise ValueError("El permalink debe pertenecer a instagram.com por HTTPS")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2 or parts[0] not in {"p", "reel"} or not parts[1]:
        raise ValueError("Instagram: se requiere /p/<id>/ o /reel/<id>/")
    return f"https://www.instagram.com/{parts[0]}/{parts[1]}/"

def like(url):
    """Da like a un post por su URL/permalink (recomendado, fiable) - un
    entero (indice 0-based en el feed 'Para ti' actualmente cargado)
    tambien funciona pero NO es fiable: ese feed se reordena en cada
    carga, ver `_goto_post`. Simula tiempo de lectura antes de actuar."""
    p, pg = _connect()
    try:
        if isinstance(url, int):
            pg.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=20000)
            pg.wait_for_timeout(3000)
            _check_bot_warning(pg)
            if _active_handle(pg) is None:
                raise RuntimeError("no se pudo confirmar la cuenta activa - abortando antes de actuar")
            articles = pg.locator("article")
            if url >= articles.count():
                print(f"no hay post en el indice {url} (solo {articles.count()} cargados)")
                return
            scope = articles.nth(url)
            scope.scroll_into_view_if_needed()
        else:
            _goto_post(pg, url)
            scope = pg
        # Page.inner_text exige selector; Locator.inner_text no. La
        # distinción correcta, validada en vivo en main el 25/09, es identidad.
        text = pg.inner_text("body") if scope is pg else scope.inner_text()
        _simulate_reading(pg, len(text.split()))
        if (scope if hasattr(scope, "locator") else pg).locator(
            "svg[aria-label='Ya no me gusta'], svg[aria-label='Unlike']"
        ).count() > 0:
            print("ese post ya tenía like")
            return "already"
        btn = _find_action_button(scope, "Me gusta")
        if btn is None:
            raise ActionTargetNotFound("no se encontró un estado verificable del botón Me gusta")
        _human_click(pg, btn)
        pg.wait_for_timeout(1200)
        _check_bot_warning(pg)
        confirmed = (scope if hasattr(scope, "locator") else pg).locator("svg[aria-label='Ya no me gusta'], svg[aria-label='Unlike']").count() > 0
        if not confirmed:
            raise RuntimeError("Instagram: like no confirmado; revisar el post antes de reintentar")
        print("like dado (confirmado): " + text[:80].replace("\n", " | "))
        return "created"
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


def follow(handle):
    """Sigue una cuenta verificando el botón superior del perfil objetivo."""
    p, pg = _connect()
    try:
        pg.goto(
            f"https://www.instagram.com/{handle}/",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        pg.wait_for_timeout(3000)
        _check_bot_warning(pg)
        if _active_handle(pg) != MY_HANDLE:
            raise RuntimeError(
                "no se pudo confirmar la cuenta activa esperada; abortando antes de actuar"
            )
        _simulate_reading(pg, 40)

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
                f"{handle}: no se encontró un control Seguir inequívoco del perfil"
            )

        _human_click(pg, control)
        pg.wait_for_timeout(1800)
        _check_bot_warning(pg)
        final = _profile_follow_button_state(_top_profile_follow_button(pg))
        if final == "following":
            print(f"{handle}: FOLLOWED (confirmado en control del perfil)")
            return "followed"
        if final == "pending":
            print(f"{handle}: cuenta privada, solicitud enviada (pendiente)")
            return "pending"
        raise RuntimeError(
            f"{handle}: follow no confirmado en el control del perfil; "
            "revisar antes de reintentar"
        )
    finally:
        p.stop()

def _already_commented(pg):
    """Instagram usa nombres de clase generados/ofuscados (confirmado en
    vivo el 23/09: sin ningun atributo estable para aislar "el bloque de un
    comentario" como si hay en Reddit/X) - la comprobacion fiable es de
    TEXTO, no de estructura: cada comentario se renderiza como
    `<username>\n<tiempo>\n<texto>\nResponder` dentro de <main>, confirmado
    en vivo contra un post real donde sabiamos que habiamos comentado.
    Buscar `MY_HANDLE` como LINEA EXACTA (no substring, evita falsos
    positivos de una mencion en el pie de foto) seguida de 'Responder'
    dentro de las proximas lineas."""
    try:
        lines = [ln.strip() for ln in pg.inner_text("main").splitlines()]
    except Exception as exc:
        raise BotWarningDetected(
            "No se pudo comprobar si ya había comentario propio; se detiene la sesión"
        ) from exc
    for i, ln in enumerate(lines):
        if ln == MY_HANDLE and "Responder" in lines[i:i + 6]:
            return True
    return False


def comment(url, text):
    """Comenta un post por su URL/permalink (recomendado, fiable) - un
    entero (indice en el feed 'Para ti') tambien funciona pero NO es
    fiable, mismo motivo que `like()`. Confirmado en vivo el 21/09: el
    placeholder real del cuadro de comentario es 'Agrega un comentario...'
    (no 'Añade un comentario...' como se habia escrito a ciegas la primera
    vez, sin verificar en vivo)."""
    _check_length(text)
    _check_spanish_orthography(text)
    if isinstance(url, int):
        raise ValueError("Para comentar se exige el permalink del post, no un índice de feed variable")
    p, pg = _connect()
    try:
        _goto_post(pg, url)
        scope = pg
        if _already_commented(pg):
            raise AlreadyCommented(f"Ya hay un comentario nuestro en {url} - no se envia otro.")
        body_text = scope.inner_text() if hasattr(scope, "inner_text") else pg.inner_text("body")
        _simulate_reading(pg, len(body_text.split()))
        box = (scope if hasattr(scope, "locator") else pg).locator(
            "textarea[aria-label='Agrega un comentario...'], textarea[aria-label='Agrega un comentario…'], "
            "textarea[aria-label='Añade un comentario…'], textarea[aria-label='Add a comment…']"
        ).first
        if box.count() == 0:
            raise ActionTargetNotFound("no se encontro el cuadro de comentario en ese post")
        _human_type(pg, box, text)
        pg.wait_for_timeout(400)
        publish_btn = pg.get_by_role("button", name="Publicar").first
        if publish_btn.count() == 0:
            publish_btn = pg.get_by_role("button", name="Post").first
        _human_click(pg, publish_btn)
        pg.wait_for_timeout(2000)
        _check_bot_warning(pg)
        # El body aún puede incluir texto del editor; eso no acredita envío.
        # Verificar comentario con autor propio tras recargar el permalink.
        pg.reload(wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(2500)
        _check_bot_warning(pg)
        lines = [ln.strip() for ln in pg.inner_text("main").splitlines()]
        snippet = text.strip()[:30]
        confirmed = any(
            line == MY_HANDLE and snippet in "\n".join(lines[i + 1:i + 12])
            and any(label in lines[i + 1:i + 12] for label in ("Responder", "Reply"))
            for i, line in enumerate(lines)
        )
        if not confirmed:
            raise RuntimeError(
                "Instagram: comentario no confirmado con autor propio tras recarga; "
                "revisar el post ANTES de reintentar"
            )
        print("comentario confirmado tras recarga y autor")
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
        elif cmd == "notifications":
            ensure_browser(); dump_notifications()
        elif cmd == "daily":
            ensure_browser(); daily_briefing()
        elif cmd == "profile":
            ensure_browser(); dump_profile(sys.argv[2] if len(sys.argv) > 2 else None)
        elif cmd == "explore":
            ensure_browser(); dump_explore(sys.argv[2])
        elif cmd == "search-accounts":
            ensure_browser(); search_accounts(sys.argv[2])
        elif cmd == "like":
            arg = sys.argv[2]
            try:
                target = int(arg)
            except ValueError:
                target = arg
            ensure_browser(); like(target)
        elif cmd == "follow":
            ensure_browser(); follow(sys.argv[2])
        elif cmd == "comment":
            arg = sys.argv[2]
            try:
                target = int(arg)
            except ValueError:
                target = arg
            ensure_browser(); comment(target, sys.argv[3])
        elif cmd == "edit-bio":
            ensure_browser(); edit_bio(sys.argv[2])
        else:
            print(__doc__)
            sys.exit(1)

    try:
        _dispatch()
    except BotWarningDetected as e:
        print(str(e))
        sys.exit(2)
