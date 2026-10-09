"""
Herramienta unica para el dia a dia de Facebook (pagina "Autora Demo
Escritor") - mismo patron que reddit_interact.py/bluesky_interact.py (Edge
real via CDP puerto 9223, ya logueado - David dejo la sesion lista el
22/09/2026). Se opera como PAGINA (Page), no como perfil personal - no hay
"follow" a personas individuales, las acciones reales son reaccionar
(like), comentar y (mas adelante, no construido hoy) unirse/participar en
grupos.

Construida el 22/09/2026, exploracion en vivo real antes de escribir nada
(mismo criterio que las otras seis redes).

Uso:
    python facebook_interact.py ensure-browser
    python facebook_interact.py health
    python facebook_interact.py own-feed
    python facebook_interact.py like [indice=0]
    python facebook_interact.py comment "texto" [indice=0]

Sobre el indice: 0 = el post mas reciente/primero de la pagina propia
(orden estable, no un feed algoritmico) - ver docstring de like()/comment()
para el motivo de usar indice en vez de fragmento de texto aqui (distinto
de las otras redes).

CONFIRMADO EN VIVO el 22/09 (antes de escribir nada, exploracion real):
- La pagina no tiene username propio (sin vanity URL) - se identifica por
  ID numerico: `facebook.com/61590793667301` /
  `facebook.com/profile.php?id=61590793667301`. Guardar el ID, no adivinar
  un slug.
- Facebook NO usa `role="article"` para envolver cada post (asuncion
  vieja de otras guias de scraping, descartada tras comprobar en vivo que
  el boton de "Me gusta" no tiene ningun ancestro con ese rol en 12
  niveles) - los posts se localizan por su TEXTO visible, buscando hacia
  arriba desde el boton de accion mas cercano.
- Boton de "Me gusta": `div[aria-label="Me gusta"][role="button"]`.
  Confirmado en vivo dando like real a un post propio: tras el click el
  aria-label cambia a "Suprimir Me gusta" (asi se verifica que el like
  quedo dado, no solo que el click no dio error).
- Comentar: click en `div[aria-label="Dejar un comentario"][role="button"]`
  (mismo bug real ya visto en X/Reddit - un overlay de modo oscuro
  intercepta el click normal, hace falta `force=True`), luego escribir en
  `[contenteditable="true"][aria-label="Comentas como <Nombre>"]` - este
  aria-label es una comprobacion de identidad activa GRATIS y mas fiable
  que en cualquier otra red (dice literalmente con que nombre se va a
  publicar, comprobado en cada comentario, no solo al principio de la
  sesion). Enviar con `div[aria-label="Publicar comentario"][role="button"]`.
- Bio desactualizada encontrada y corregida el mismo dia: decia "Muy
  pronto: Las manecillas el recuerdo" (con errata real, falta "del") -
  corregido a mismo texto que las otras redes, ver diario.
"""
import os
import re
import sys
import time
import subprocess
import urllib.request
from urllib.parse import urlsplit

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(__file__))
import instagram_interact as ig  # reutiliza humanizacion (raton/tecleo/lectura), sin duplicarla
from scan_common import ActionTargetNotFound, AlreadyCommented, check_length  # compartido entre redes, 23/09
from x_interact import _check_spanish_orthography  # reutilizado, no duplicado

CDP_URL = "http://127.0.0.1:9223"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EDGE_USER_DATA = r"C:\Temp\rrss-autorademo-edge"
MY_PAGE_ID = "61590793667301"
MY_PAGE_NAME = "Autora Demo Escritor"

BOT_WARNING_SIGNALS = [
    "unusual activity", "actividad inusual", "actividad sospechosa",
    "suspicious activity", "account suspended", "cuenta suspendida",
    "pagina inhabilitada", "page disabled", "temporarily blocked",
    "verify you're human", "verifica que eres humano",
    "confirma que eres humano", "you've been rate limited",
    "te has quedado sin limite", "this action is limited",
    "algo salio mal", "something went wrong", "accion bloqueada",
    "action blocked",
]


class BotWarningDetected(RuntimeError):
    pass


def _check_bot_warning(pg):
    try:
        text = pg.inner_text("body").lower()
    except Exception as exc:
        raise BotWarningDetected("No se pudo comprobar avisos de bloqueo; detener ejecución") from exc
    for signal in BOT_WARNING_SIGNALS:
        if signal in text:
            raise BotWarningDetected(
                f"AVISO REAL DETECTADO EN PANTALLA: \"{signal}\". "
                "Parando de inmediato. Avisar a David antes de reintentar."
            )


def _check_length(text, limit=8000):
    """Facebook admite comentarios largos (miles de caracteres) - el
    limite real no es la restriccion que importa aqui, FACEBOOK.md pide
    brevedad por criterio editorial, no por limite tecnico. Techo alto
    solo como red de seguridad ante un error de generacion."""
    check_length(text, limit)


# _check_spanish_orthography importada de x_interact.py (23/09).


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
        "https://www.facebook.com/",
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
    pages = [pg for pg in ctx.pages if urlsplit(pg.url).hostname in {"facebook.com", "www.facebook.com"}]
    pg = pages[-1] if pages else ctx.new_page()
    return p, pg


def _own_page_url():
    return f"https://www.facebook.com/profile.php?id={MY_PAGE_ID}"


def _health_check(pg):
    """Navega a la pagina propia y comprueba dos marcas que solo
    aparecen cuando la sesion tiene de verdad permisos de administrador
    sobre ESTA pagina concreta ('Editar' del perfil, 'Panel para
    profesionales') - no basta con estar logueado en Facebook, hay que
    confirmar que se administra esta pagina en particular."""
    pg.goto(_own_page_url(), wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    text = pg.inner_text("body")
    if MY_PAGE_NAME not in text:
        return False, "PROBLEMA: no se detecta la pagina esperada - puede haber caducado la sesion."
    if "Panel para profesionales" not in text:
        return False, (
            f"PROBLEMA REAL: se ve la pagina '{MY_PAGE_NAME}' pero sin marcas de administrador "
            "('Panel para profesionales' no aparece) - la sesion puede no tener permisos sobre "
            "esta pagina concreta. No ejecutar ninguna accion."
        )
    return True, f"OK: sesion con permisos de administrador confirmados sobre la pagina '{MY_PAGE_NAME}'."


def health():
    p, pg = _connect()
    try:
        ok, msg = _health_check(pg)
        print(msg)
    finally:
        p.stop()


def _dump_own_feed(pg, scroll=True):
    pg.goto(_own_page_url(), wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(3000)
    _check_bot_warning(pg)
    if scroll:
        # Facebook solo renderiza el primer post de la pagina hasta hacer
        # scroll - confirmado en vivo el 22/09 (buscar un post mas abajo
        # sin scrollear antes no lo encuentra, aunque exista).
        ig._jittery_scroll(pg, "down")
        ig._jittery_scroll(pg, "down")
        _check_bot_warning(pg)
    # BUG REAL encontrado en vivo el 24/09: el conteo de botones 'Me gusta'
    # justo despues del scroll es INCONSISTENTE entre llamadas (0 o 1 en
    # ejecuciones identicas seguidas) - el post tarda en montarse en el DOM
    # despues del scroll y los timeouts fijos de arriba no siempre alcanzan.
    # Antes like()/comment() contaban los botones inmediatamente y fallaban
    # con "0 botones cargados" por pura carrera, no porque el post no
    # existiera. Corregido esperando explicitamente a que aparezca al menos
    # un boton (con timeout acotado, nunca cuelga si de verdad no hay nada).
    try:
        pg.locator('div[aria-label="Me gusta"][role="button"]').first.wait_for(
            state="attached", timeout=8000
        )
    except Exception:
        pass


def dump_own_feed():
    p, pg = _connect()
    try:
        _dump_own_feed(pg)
        print(pg.inner_text("body")[:6000])
    finally:
        p.stop()


def _post_preview(pg, index):
    """Texto de vista previa de un post por su indice - solo para el
    mensaje al usuario, no para localizar botones (ver nota en like()/
    comment() sobre por que el indice, no el texto, es lo que decide cual
    post se toca)."""
    els = pg.locator('div[aria-label="Me gusta"][role="button"]')
    if index >= els.count():
        return ""
    return els.nth(index).evaluate(
        '''(el) => {
            let n = el;
            for (let d = 0; d < 20; d++) {
                n = n.parentElement;
                if (!n) return "";
                const t = (n.innerText || "").trim();
                // BUG REAL visto en vivo el 22/09: la primera version
                // solo detectaba el placeholder "Facebook" repetido si
                // venia separado por saltos de linea - a veces aparece
                // concatenado sin separador ("FacebookFacebook...").
                // Comprobar quitando todas las apariciones de la palabra,
                // no solo linea a linea.
                const cleaned = t.replace(/(Facebook\\s*)+/g, "").trim();
                if (cleaned.length > 40) return cleaned.slice(0, 100);
            }
            return "";
        }'''
    )


def like(index=0):
    """Da like (reaccion 'Me gusta') al post en `index` (0 = el mas
    reciente/primero) de la pagina propia. BUG REAL encontrado en vivo el
    22/09: localizar el post por FRAGMENTO DE TEXTO (buscando hacia
    arriba desde el boton) no es fiable aqui - a diferencia de X/Threads/
    Instagram, Facebook no envuelve cada post en un contenedor propio
    identificable, y la busqueda hacia arriba puede acabar en un
    contenedor de sugerencias/fotos ajeno sin relacion con el post real.
    Por eso, a diferencia de las otras redes, aqui se actua por INDICE
    sobre la pagina propia (donde el orden es estable, no un feed
    algoritmico que se reordene) en vez de por texto - ver PENDIENTES.md.
    Verificado en vivo con un post real: el aria-label pasa de 'Me
    gusta' a 'Suprimir Me gusta' tras el click."""
    p, pg = _connect()
    try:
        _dump_own_feed(pg)
        preview = _post_preview(pg, index)
        btns = pg.locator('div[aria-label="Me gusta"][role="button"]')
        if index >= btns.count():
            raise ActionTargetNotFound(
                f"no hay post en el indice {index} (solo {btns.count()} botones 'Me gusta' cargados)"
            )
        btn = btns.nth(index)
        # BUG REAL visto en vivo el 22/09: un Locator se re-evalua en cada
        # llamada - tras el click, el boton clicado ya no cumple el
        # selector 'Me gusta' (paso a 'Suprimir Me gusta'), asi que
        # `btns.nth(index)` en ese momento apunta a OTRO boton distinto
        # que ocupo ese hueco, no al que se acaba de clicar. Fijar un
        # `element_handle()` ANTES del click para comprobar el mismo
        # elemento fisico despues, no una posicion que se mueve.
        try:
            handle = btn.element_handle()
            btn.scroll_into_view_if_needed()
        except Exception:
            # BUG REAL visto en vivo el 22/09: Facebook re-renderiza el
            # DOM con frecuencia (mas que X/Threads/Instagram) y el boton
            # puede desprenderse justo entre localizarlo y moverse hasta
            # el - no hay much margen para "arreglarlo del todo", solo
            # avisar con claridad en vez de que la excepcion suba en
            # crudo, y dejar que se reintente la sesion. Corregido 23/09:
            # antes hacia print+return, lo que dejaba la accion como
            # "confirmado" en el registro sin haber ocurrido (mismo bug
            # real ya corregido en Threads/Instagram) - ahora se hace
            # visible como fallo real en el registro.
            raise ActionTargetNotFound(
                f"el post en el indice {index} se desprendio del DOM antes de poder actuar "
                "(Facebook re-renderiza mucho) - reintentar la sesion."
            )
        pg.wait_for_timeout(400)
        ig._human_click(pg, btn)
        pg.wait_for_timeout(1200)
        _check_bot_warning(pg)
        confirmed = handle.get_attribute("aria-label") == "Suprimir Me gusta"
        if not confirmed:
            raise RuntimeError("Facebook: like no confirmado; revisar el post antes de reintentar")
        print("like dado (confirmado): " + preview)
        return "created"
    finally:
        p.stop()


# AlreadyCommented importada de scan_common (23/09, centralizada). SIN
# VERIFICAR EN VIVO con un caso real todavia - ver docstring de
# _already_commented.


def _already_commented(pg, index):
    """NO VERIFICADO EN VIVO con un caso real (23/09) - ver PENDIENTES.md.
    BUG REAL evitado antes de publicarlo: una primera version buscaba
    `MY_PAGE_NAME` como linea exacta en TODA la pagina, pero como
    comment()/like() actuan sobre posts PROPIOS, el nombre de la pagina ya
    aparece como autor de cada post (ademas de en la cabecera) - esa
    version habria bloqueado TODOS los comentarios siempre, no solo los
    repetidos. Corregido: reutiliza el mismo contenedor amplio que
    `_post_preview` (sube desde el boton 'Me gusta' de ese indice) y cuenta
    cuantas veces aparece `MY_PAGE_NAME` DENTRO de ese post concreto -  1
    aparicion es solo la autoria del post; 2 o mas sugiere que ademas hay un
    comentario nuestro ahi. Sigue siendo una aproximacion (el DOM de
    Facebook es el mas fragil de las 7 redes) - confirmar contra un caso
    real la primera vez que se envie un comentario de verdad.

    BUG REAL encontrado y corregido en vivo el 23/09 antes de dar esto por
    bueno: el cuadro de comentario muestra "Comentas como {MY_PAGE_NAME}"
    en cuanto esta en el DOM (confirmado que aparece incluso sin haber
    clicado para expandirlo) - sin excluir esa frase, el contador siempre
    daba 2 (autoria del post + ese texto fijo) y la guardia habria
    bloqueado TODOS los comentarios desde el primero. Verificado en vivo
    tras la correccion: False en los 3 primeros posts (ninguno tiene
    comentario real nuestro todavia, coincide con lo esperado)."""
    els = pg.locator('div[aria-label="Me gusta"][role="button"]')
    if index < 0 or index >= els.count():
        raise ActionTargetNotFound(
            f"No se puede comprobar comentario previo en el índice {index}: "
            f"hay {els.count()} posts visibles; no enviar comentario"
        )
    count = els.nth(index).evaluate(
        '''(el, name) => {
            let n = el;
            for (let d = 0; d < 20; d++) {
                n = n.parentElement;
                if (!n) return 0;
                let t = (n.innerText || "");
                // BUG REAL encontrado y corregido en la misma sesion (23/09):
                // el cuadro de comentario SIEMPRE muestra "Comentas como
                // {name}" en cuanto es visible en el DOM, aunque no se haya
                // escrito ni enviado nada todavia - sin quitar esta frase,
                // el contador siempre daba >=2 (autoria del post + este
                // placeholder) y la guardia bloqueaba TODOS los comentarios
                // desde el primero, no solo los repetidos. Confirmado en
                // vivo contra el indice 0 antes de corregirlo.
                t = t.split("Comentas como " + name).join("");
                const matches = t.split(name).length - 1;
                if (t.replace(/(Facebook\\s*)+/g, "").trim().length > 40 && matches > 0) {
                    return matches;
                }
            }
            return 0;
        }''',
        MY_PAGE_NAME,
    )
    return count >= 2


def comment(comment_text, index=0):
    """Comenta el post en `index` (0 = el mas reciente/primero) de la
    pagina propia - mismo motivo que like() para actuar por indice, no
    por texto. Comprueba en vivo, en el propio aria-label del cuadro de
    texto, que se va a publicar como `MY_PAGE_NAME` antes de escribir
    nada - si no coincide, aborta."""
    _check_length(comment_text)
    _check_spanish_orthography(comment_text)
    p, pg = _connect()
    try:
        _dump_own_feed(pg)
        preview = _post_preview(pg, index)
        if _already_commented(pg, index):
            raise AlreadyCommented(
                f"Ya parece haber un comentario nuestro en el post indice {index} - "
                "no se envia otro. (Guardia sin verificar en vivo, ver docstring.)"
            )
        triggers = pg.locator('div[aria-label="Dejar un comentario"][role="button"]')
        if index >= triggers.count():
            raise ActionTargetNotFound(
                f"no hay post en el indice {index} (solo {triggers.count()} cuadros de comentario cargados)"
            )
        trigger = triggers.nth(index)
        try:
            trigger.scroll_into_view_if_needed()
        except Exception:
            # Mismo motivo que en like() - Facebook re-renderiza mucho,
            # el elemento se puede desprender entre localizarlo y
            # moverse hasta el.
            raise ActionTargetNotFound(
                f"el post en el indice {index} se desprendio del DOM antes de poder actuar "
                "(Facebook re-renderiza mucho) - reintentar la sesion."
            )
        pg.wait_for_timeout(400)
        trigger.click(force=True)
        pg.wait_for_timeout(1200)
        box = pg.locator(f'[contenteditable="true"][aria-label="Comentas como {MY_PAGE_NAME}"]').first
        if box.count() == 0:
            raise RuntimeError(
                f"no se encontro el cuadro de comentario con identidad '{MY_PAGE_NAME}' confirmada - "
                "abortando antes de escribir nada (puede que la sesion este comentando como otra identidad)."
            )
        box.click(force=True)
        box.type(comment_text, delay=15)
        pg.wait_for_timeout(500)
        send = pg.locator('div[aria-label="Publicar comentario"][role="button"]').first
        send.click(force=True)
        pg.wait_for_timeout(2000)
        _check_bot_warning(pg)
        print(f"comentario enviado; confirmación remota pendiente: {comment_text[:60]}")
        return "unverified"
    finally:
        p.stop()


def _validated_facebook_permalink(permalink):
    if not isinstance(permalink, str) or not permalink.strip():
        raise ValueError("Se requiere permalink de Facebook")
    parsed = urlsplit(permalink.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"facebook.com", "www.facebook.com"}
        or parsed.username
        or parsed.password
        or parsed.port
    ):
        raise ValueError("El permalink debe pertenecer a facebook.com por HTTPS")
    path = parsed.path.rstrip("/") or "/"
    query = dict(part.split("=", 1) for part in parsed.query.split("&") if "=" in part)
    is_photo = path == "/photo" and query.get("fbid", "").isdigit()
    is_story = path == "/story.php" and query.get("story_fbid", "").isdigit()
    post_id = r"[A-Za-z0-9._-]+"
    is_post_path = bool(re.fullmatch(rf"/[^/]+/(?:posts|permalink)/{post_id}", path))
    is_group_post = bool(re.fullmatch(rf"/groups/[^/]+/posts/{post_id}", path))
    if not (is_photo or is_story or is_post_path or is_group_post):
        raise ValueError("Se requiere un permalink de publicación de Facebook, no un perfil o página")
    return parsed.geturl()


def _dump_permalink(pg, permalink):
    """Anadido 24/09 para el descubrimiento externo (hashtags) - equivalente
    a `_dump_own_feed` pero navegando a la URL EXACTA de un post ajeno en vez
    de a la pagina propia. Confirmado en vivo: en la pagina de un post
    concreto (ej. `facebook.com/photo/?fbid=...`), el indice 0 de los
    botones 'Me gusta' es siempre el post principal, los siguientes son los
    comentarios existentes debajo - mismo convenio que en `_dump_own_feed`,
    asi que like()/comment() por indice funcionan igual aqui sin cambios."""
    permalink = _validated_facebook_permalink(permalink)
    pg.goto(permalink, wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(3000)
    _check_bot_warning(pg)
    try:
        pg.locator('div[aria-label="Me gusta"][role="button"]').first.wait_for(
            state="attached", timeout=8000
        )
    except Exception:
        pass


def _already_commented_external(pg):
    """Version de `_already_commented` para posts AJENOS (descubrimiento
    externo, ver `_dump_permalink`) - la diferencia real es el umbral: en un
    post PROPIO, `MY_PAGE_NAME` aparece 1 vez solo por ser el autor (de ahi
    el umbral >=2 en `_already_commented`); en un post AJENO no somos el
    autor, asi que CUALQUIER aparicion (>=1) ya significa que comentamos ahi
    de verdad."""
    els = pg.locator('div[aria-label="Me gusta"][role="button"]')
    if els.count() == 0:
        return False
    count = els.nth(0).evaluate(
        '''(el, name) => {
            let n = el;
            for (let d = 0; d < 20; d++) {
                n = n.parentElement;
                if (!n) return 0;
                let t = (n.innerText || "");
                t = t.split("Comentas como " + name).join("");
                const matches = t.split(name).length - 1;
                if (t.replace(/(Facebook\\s*)+/g, "").trim().length > 40 && matches > 0) {
                    return matches;
                }
            }
            return 0;
        }''',
        MY_PAGE_NAME,
    )
    return count >= 1


def like_external(permalink):
    """Da like a un post AJENO encontrado por descubrimiento externo
    (hashtag, ver `facebook_scan.py`) por su URL exacta - mismo mecanismo
    que like() sobre indice 0, solo cambia la navegacion (URL directa en vez
    de la pagina propia)."""
    p, pg = _connect()
    try:
        _dump_permalink(pg, permalink)
        preview = _post_preview(pg, 0)
        btns = pg.locator('div[aria-label="Me gusta"][role="button"]')
        if btns.count() == 0:
            raise ActionTargetNotFound(f"no se encontro el boton 'Me gusta' en {permalink}")
        btn = btns.nth(0)
        try:
            handle = btn.element_handle()
            btn.scroll_into_view_if_needed()
        except Exception:
            raise ActionTargetNotFound(
                f"el post se desprendio del DOM antes de poder actuar en {permalink} - reintentar."
            )
        pg.wait_for_timeout(400)
        ig._human_click(pg, btn)
        pg.wait_for_timeout(1200)
        _check_bot_warning(pg)
        confirmed = handle.get_attribute("aria-label") == "Suprimir Me gusta"
        if not confirmed:
            raise RuntimeError("Facebook: like no confirmado; revisar el post antes de reintentar")
        print("like dado (confirmado): " + preview)
        return "created"
    finally:
        p.stop()


def comment_external(comment_text, permalink):
    """Comenta un post AJENO por su URL exacta - mismo mecanismo que
    comment() sobre indice 0, con el umbral de `_already_commented_external`
    en vez del de posts propios."""
    _check_length(comment_text)
    _check_spanish_orthography(comment_text)
    p, pg = _connect()
    try:
        _dump_permalink(pg, permalink)
        preview = _post_preview(pg, 0)
        if _already_commented_external(pg):
            raise AlreadyCommented(f"Ya parece haber un comentario nuestro en {permalink} - no se envia otro.")
        triggers = pg.locator('div[aria-label="Dejar un comentario"][role="button"]')
        if triggers.count() == 0:
            raise ActionTargetNotFound(f"no se encontro el cuadro de comentario en {permalink}")
        trigger = triggers.nth(0)
        try:
            trigger.scroll_into_view_if_needed()
        except Exception:
            raise ActionTargetNotFound(
                f"el post se desprendio del DOM antes de poder actuar en {permalink} - reintentar."
            )
        pg.wait_for_timeout(400)
        trigger.click(force=True)
        pg.wait_for_timeout(1200)
        box = pg.locator(f'[contenteditable="true"][aria-label="Comentas como {MY_PAGE_NAME}"]').first
        if box.count() == 0:
            raise RuntimeError(
                f"no se encontro el cuadro de comentario con identidad '{MY_PAGE_NAME}' confirmada en "
                f"{permalink} - abortando antes de escribir nada."
            )
        box.click(force=True)
        box.type(comment_text, delay=15)
        pg.wait_for_timeout(500)
        send = pg.locator('div[aria-label="Publicar comentario"][role="button"]').first
        send.click(force=True)
        pg.wait_for_timeout(2000)
        _check_bot_warning(pg)
        print(
            f"comentario enviado; confirmación remota pendiente: "
            f"{comment_text[:60]} -- {preview[:60]}"
        )
        return "unverified"
    finally:
        p.stop()


def dump_hashtag(tag):
    """Descubrimiento externo (24/09) - vuelca los posts visibles en
    `facebook.com/hashtag/<tag>` para que `facebook_scan.py` pueda sacar
    candidatos reales fuera de la pagina propia. Confirmado en vivo el
    24/09: da contenido real y afin (ej. #literaturafantastica -> Dolmen
    Editorial hablando del festival Celsius 232)."""
    p, pg = _connect()
    try:
        pg.goto(f"https://www.facebook.com/hashtag/{tag}", wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(3000)
        _check_bot_warning(pg)
        print(pg.inner_text("body")[:4000])
    finally:
        p.stop()


def get_hashtag_data(tag, limit=40, scrolls=6):
    """Posts de un hashtag. 04/10 (David: "si no encuentras es fallo del script"): antes leia solo los 8 primeros botones
    sin desplazar la pagina y salian 1-2 posts por etiqueta; ahora baja `scrolls` veces y lee hasta `limit`."""
    return _feed_data(f"https://www.facebook.com/hashtag/{tag}", limit, scrolls)


def get_search_data(query, limit=40, scrolls=6):
    """Posts recientes de la busqueda de Facebook (no solo hashtags): mismo formato que get_hashtag_data."""
    from urllib.parse import quote
    return _feed_data(f"https://www.facebook.com/search/posts/?q={quote(query)}", limit, scrolls)


def _feed_data(url, limit=18, scrolls=3):
    """Version estructurada de dump_hashtag() para facebook_scan.py - vuelca
    (autor, permalink, texto) por cada post real del hashtag. El autor real
    de un post ajeno esta en el primer enlace `a[href]` dentro del mismo
    contenedor amplio que ya usa `_post_preview`/`_already_commented`
    (subiendo desde el boton 'Me gusta'), filtrando los enlaces de
    navegacion propios (hashtag/watch/etc) - mismo patron de "subir desde el
    boton mas cercano" que el resto del modulo, no `role="article"` (Facebook
    no lo usa, ver docstring de like())."""
    p, pg = _connect()
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(3000)
        _check_bot_warning(pg)
        for _ in range(scrolls):
            pg.mouse.wheel(0, 1800)
            pg.wait_for_timeout(1800)
        _check_bot_warning(pg)
        btns = pg.locator('div[aria-label="Me gusta"][role="button"]')
        n = min(btns.count(), limit)
        out = []
        for i in range(n):
            btn = btns.nth(i)
            try:
                data = btn.evaluate(
                    '''(el) => {
                        let n = el;
                        for (let d = 0; d < 20; d++) {
                            n = n.parentElement;
                            if (!n) return null;
                            const t = (n.innerText || "").trim();
                            const cleaned = t.replace(/(Facebook\\s*)+/g, "").trim();
                            if (cleaned.length > 40) {
                                const permaLink = n.querySelector('a[href*="fbid="], a[href*="/posts/"], a[href*="/videos/"]');
                                return {
                                    text: cleaned.slice(0, 300),
                                    permalink: permaLink ? permaLink.href : null,
                                };
                            }
                        }
                        return null;
                    }'''
                )
            except Exception:
                # BUG REAL visto en vivo el 24/09: Facebook re-renderiza el
                # hashtag feed mientras se itera (mismo patron ya documentado
                # en like()) - un boton que existia al contar `btns.count()`
                # puede desprenderse del DOM antes de llegarle el turno.
                # Saltar ese item en vez de tirar toda la recogida.
                continue
            if data and data.get("permalink"):
                # BUG REAL evitado el 24/09: intentar sacar el autor con un
                # selector de enlace aparte casi siempre daba "?" (el enlace
                # de la Pagina no coincide de forma fiable) - el nombre de la
                # Pagina es casi siempre la primera linea del texto visible
                # ("Dolmen Editorial\n· Seguir ·..." o "Dolmen Editorial esta
                # con..."), mas barato y mas fiable que seguir buscando el
                # selector correcto.
                first_line = data["text"].split("\n")[0].strip()
                author = re.split(r"\s+est[aá] (con|en)\b", first_line)[0].strip()
                out.append((author or "?", data["permalink"], data["text"]))
        return out
    finally:
        p.stop()


if __name__ == "__main__":
    def _dispatch():
        cmd = sys.argv[1] if len(sys.argv) > 1 else None
        if cmd == "ensure-browser":
            ensure_browser()
        elif cmd == "health":
            ensure_browser(); health()
        elif cmd == "own-feed":
            ensure_browser(); dump_own_feed()
        elif cmd == "like":
            ensure_browser(); like(int(sys.argv[2]) if len(sys.argv) > 2 else 0)
        elif cmd == "comment":
            ensure_browser(); comment(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0)
        elif cmd == "hashtag":
            ensure_browser(); dump_hashtag(sys.argv[2])
        elif cmd == "like-external":
            ensure_browser(); like_external(sys.argv[2])
        elif cmd == "comment-external":
            ensure_browser(); comment_external(sys.argv[2], sys.argv[3])
        else:
            print(__doc__)
            sys.exit(1)

    try:
        _dispatch()
    except BotWarningDetected as e:
        print(str(e))
        sys.exit(2)
