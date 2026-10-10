"""
Herramienta unica para el dia a dia de TikTok (@davidportoescritor) - mismo
patron que instagram_interact.py (Edge real via CDP puerto 9223, ya
logueado - David dejo la sesion lista el 22/09/2026). TikTok es, de las
seis redes de este proyecto, la MAS sensible a deteccion de bots -
confirmado en vivo el mismo dia de construir esto: una navegacion directa
a una URL de busqueda con query string disparo un captcha real ("Arrastra
el deslizador para encajar en el puzle") ANTES de tocar ninguna accion de
escritura. Por eso esta herramienta:
- reutiliza la humanizacion real de instagram_interact.py (raton por
  curva de Bezier, tecleo con typos, tiempo de lectura, scroll no lineal)
  en vez de duplicarla;
- evita goto() directo a URLs de busqueda con query string (ver
  tiktok_scan.py - no hay busqueda automatizada todavia, solo fuentes
  mas seguras: perfil directo, feed "Siguiendo");
- aplica un techo de calentamiento MAS lento que instagram_interact.py
  (ver tiktok_execute.py, TECHO_POR_FASE) porque aqui no hay ningun
  historial de interaccion automatizada real, ni siquiera un dia.

La investigacion de origen (`SISTEMA_DIARIO_GPT investigation/TIKTOK.md`,
seccion 8.4) dice explicitamente "No automatizar follows, likes,
comentarios ni mensajes" - David vio esta advertencia (planteada
directamente antes de construir nada) y decidio explicitamente seguir
adelante igual que en las otras cinco redes, aceptando el riesgo. Esta
herramienta existe por esa decision explicita, no por ignorar la
advertencia.

Uso:
    python tiktok_interact.py ensure-browser
    python tiktok_interact.py health
    python tiktok_interact.py profile [handle]
    python tiktok_interact.py following-feed
    python tiktok_interact.py follow <handle>
    python tiktok_interact.py like <handle> "fragmento de la descripcion"
    python tiktok_interact.py comment <handle> "fragmento de la descripcion" "texto"

Sobre "like"/"comment": se localiza el post por HANDLE + fragmento de
texto de su descripcion (abriendo el grid del perfil y probando post a
post), nunca por URL directa ni por indice - ver docstring de
`_find_post_by_text` para el motivo (el grid no expone el texto sin abrir
cada post, y una URL de video no siempre lleva al contexto de perfil
donde estan los botones de accion verificados en vivo).

CONFIRMADO EN VIVO el 22/09 (antes de escribir nada, exploracion real):
- Cuenta activa: unico selector fiable encontrado es
  `[data-e2e="nav-profile"]` (href apunta al handle activo) - NO usar
  `get_by_role("link", name="Perfil")`, dio lecturas inconsistentes en
  vivo (a veces otro handle, a veces cero resultados) por timing de
  hidratacion del componente React - el atributo data-e2e es mucho mas
  estable.
- Navegar directo a un perfil (`/@handle`) o a un video (`/@handle/video/id`
  o `/@handle/photo/id`) es seguro - probado varias veces sin problema,
  incluso cuando el handle de la URL no coincidia con el dueño real del
  video (TikTok redirige solo, sin aviso).
- Navegar directo a una URL de BUSQUEDA con query string
  (`/search/video?q=...`) SI disparo un captcha real la primera vez que
  se probo - motivo de que la busqueda no este automatizada aqui todavia
  (ver tiktok_scan.py y PENDIENTES.md).
- Estructura de un post individual (tras hacer click en un item del grid
  de perfil, `[data-e2e="user-post-item"]`, nunca goto directo a la URL
  del video si se puede evitar): boton de like `[data-e2e="browse-like-icon"]`,
  boton de seguir `[data-e2e="browse-follow"]` (dentro del modal) o
  `[data-e2e="follow-button"]` (en la pagina de perfil completa), caja de
  comentario `[data-e2e="comment-text"]` (editor Draft.js, contenteditable
  real dentro), boton de enviar `[data-e2e="comment-post"]`.
- Feed "Siguiendo" (`[data-e2e="nav-following"]`) funciona bien y es
  fuente segura (solo cuentas ya seguidas, sin busqueda).
"""
import os
import sys
import time
import subprocess
import urllib.request
from urllib.parse import urlsplit

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(__file__))
import instagram_interact as ig  # reutiliza humanizacion (raton/tecleo/lectura/scroll), sin duplicarla
from scan_common import AlreadyCommented, check_length  # compartido entre redes, 23/09
from x_interact import _check_spanish_orthography  # reutilizado, no duplicado

CDP_URL = "http://127.0.0.1:9223"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
# Mismo perfil dedicado que las otras cinco herramientas - David logueo
# @davidportoescritor ahi el 22/09/2026.
EDGE_USER_DATA = r"C:\Temp\rrss-davidporto-edge"
MY_HANDLE = "davidportoescritor"

# Ampliado con las senales especificas vistas en vivo el 22/09 (captcha de
# TikTok) ademas del set ya usado en las otras redes.
BOT_WARNING_SIGNALS = [
    "unusual activity", "actividad inusual", "actividad sospechosa",
    "suspicious activity", "account suspended", "cuenta suspendida",
    "temporarily banned", "verify you're human", "verifica que eres humano",
    "confirma que eres humano", "you've been rate limited",
    "te has quedado sin limite", "this action is limited",
    "arrastra el deslizador", "encajar en el puzle", "verificacion de seguridad",
    "security verification", "algo salio mal", "something went wrong",
    # 04/10: reto de "gira la imagen hasta que encaje" y variantes que el filtro anterior no veia
    "gira la imagen", "girar la imagen", "rota la imagen", "rotate the image", "drag the slider",
    "desliza para completar", "slide to complete", "verifica para continuar", "verify to continue",
    "completa la verificacion", "completa la verificación",
]

# Contenedores del SDK de captcha de TikTok. OJO: en una pagina normal existen elementos "captcha" OCULTOS, asi que
# solo cuenta uno VISIBLE (caja con tamano real y sin display/visibility ocultos).
_CAPTCHA_VISIBLE_JS = """() => {
  const sel = '[class*="captcha" i], [id*="captcha" i], [class*="secsdk" i], iframe[src*="captcha" i], iframe[src*="verify" i]';
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    if (r.width >= 120 && r.height >= 60 && st.display !== 'none' && st.visibility !== 'hidden' && st.opacity !== '0') return true;
  }
  return false;
}"""


def captcha_visible(pg):
    """True si hay un reto (captcha) visible en la pagina. Ante un fallo al comprobarlo se asume que SI (parar)."""
    try:
        return bool(pg.evaluate(_CAPTCHA_VISIBLE_JS))
    except Exception:
        return True


class BotWarningDetected(RuntimeError):
    pass


class InteractionsPaused(RuntimeError):
    pass


# 28/09/2026 David lo desactivo tras TRES captchas reales (22/09, 24/09, 28/09). 04/10/2026 lo REACTIVA: primero
# revisar a quien seguimos y dejar de seguir a extranjeros/bots (`tiktok_following_audit.py`), luego 10 follows al dia
# a gente que merezca la pena. El captcha del deslizador lo resuelve David a mano cuando salga y se sigue. Ante
# cualquier aviso se para (BotWarningDetected). Volver a True desactiva todo de nuevo.
INTERACTIONS_PAUSED = False


def _refuse_if_paused():
    if INTERACTIONS_PAUSED:
        raise InteractionsPaused(
            "Automatizacion de cuenta TikTok desactivada indefinidamente "
            "(lectura/scan/follow/like/comment/health) por tres incidentes "
            "reales de CAPTCHA: 22/09, 24/09 y 28/09. Decision de David. "
            "La publicacion sigue en un sistema separado y no se ve afectada. "
            "Ver PROCESO.md."
        )


def _check_bot_warning(pg):
    if captcha_visible(pg):
        raise BotWarningDetected(
            "CAPTCHA/verificacion VISIBLE en TikTok; detener la sesion de inmediato, sin interactuar. "
            "Lo resuelve David a mano y solo entonces se decide si se sigue (NUNCA resolverlo ni reintentar)."
        )
    # Los retos de TikTok pueden estar dentro de iframe sin texto en body.
    # Comprobar también el DOM ANTES de buscar botones de interacción.
    try:
        challenge = pg.locator(
            'iframe[src*="captcha" i], iframe[src*="verify" i], '
            '[data-e2e*="captcha" i], [id*="captcha" i]'
        )
        if challenge.count() > 0:
            raise BotWarningDetected(
                "Componente de CAPTCHA/verificación detectado; detener sesión sin interactuar"
            )
    except BotWarningDetected:
        raise
    except Exception as exc:
        raise BotWarningDetected(
            "No se pudo inspeccionar el DOM para detectar CAPTCHA; detener sesión"
        ) from exc
    try:
        text = pg.inner_text("body").lower()
    except Exception as exc:
        raise BotWarningDetected("No se pudo comprobar avisos de bloqueo; detener ejecución") from exc
    for signal in BOT_WARNING_SIGNALS:
        if signal in text:
            raise BotWarningDetected(
                f"AVISO REAL DETECTADO EN PANTALLA: \"{signal}\". "
                "Parando de inmediato. Avisar a David antes de reintentar - "
                "NUNCA resolver un captcha ni reintentar en bucle."
            )


def _check_length(text, limit=150):
    """150 caracteres - limite publico documentado de un comentario de
    TikTok (no confundir con el limite de caption, mucho mas alto)."""
    check_length(text, limit)


# _check_spanish_orthography importada de x_interact.py (23/09).


def _cdp_alive():
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3)
        return True
    except Exception:
        return False


def ensure_browser():
    _refuse_if_paused()
    if _cdp_alive():
        print("CDP ya activo en 9223")
        return
    print("CDP no responde, abriendo Edge (perfil dedicado de la automatizacion)...")
    subprocess.Popen([
        EDGE_EXE,
        "--remote-debugging-port=9223",
        f"--user-data-dir={EDGE_USER_DATA}",
        "https://www.tiktok.com/",
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
    """Unico selector fiable encontrado en vivo el 22/09 - ver docstring
    del modulo. Reintenta varias veces porque el componente tarda en
    hidratar (visto en vivo: a veces 0 resultados en el primer intento)."""
    for _ in range(8):
        el = pg.locator('[data-e2e="nav-profile"]').first
        if el.count() > 0:
            href = el.get_attribute("href")
            if href and href.startswith("/@"):
                return href[2:]
        pg.wait_for_timeout(700)
    return None


def _health_check(pg):
    pg.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2000)
    _check_bot_warning(pg)
    active = _active_handle(pg)
    if active is None:
        return False, "PROBLEMA: no se pudo confirmar la cuenta activa (nav-profile no encontrado tras reintentos) - puede que la sesion haya caducado."
    if active != MY_HANDLE:
        return False, (
            f"PROBLEMA REAL: la cuenta ACTIVA en esta sesion es @{active}, "
            f"NO @{MY_HANDLE}. Cualquier follow/like/comment se ejecutaria como "
            f"@{active}. Cambiar de cuenta en TikTok antes de continuar."
        )
    return True, f"OK: sesion logueada y cuenta ACTIVA confirmada como @{MY_HANDLE}."


def health():
    _refuse_if_paused()
    p, pg = _connect()
    try:
        ok, msg = _health_check(pg)
        print(msg)
    finally:
        p.stop()


def _assert_active_account(pg):
    active = _active_handle(pg)
    if active != MY_HANDLE:
        raise RuntimeError(
            f"CUENTA ACTIVA INCORRECTA: esta sesion tiene activa @{active}, "
            f"no @{MY_HANDLE}. Accion cancelada antes de ejecutarse."
        )


def _dump_following_feed(pg):
    _refuse_if_paused()
    pg.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(1500)
    _check_bot_warning(pg)
    pg.locator('[data-e2e="nav-following"]').first.click()
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    ig._jittery_scroll(pg, "down")
    print(pg.inner_text("body")[:6000])


def dump_following_feed():
    _refuse_if_paused()
    p, pg = _connect()
    try:
        _dump_following_feed(pg)
    finally:
        p.stop()


def _extract_feed_items(pg, limit=15):
    """Vuelca (handle, texto) de los items visibles en el feed vertical ya
    cargado (Siguiendo/Para ti) - confirmado en vivo el 22/09:
    `[data-e2e="recommend-list-item-container"]` es el contenedor de cada
    video, con `a[href^="/@"]` para el autor y `[data-e2e="video-desc"]`
    para el texto. Algunos items (anuncios, tipos de tarjeta especiales)
    no exponen ninguno de los dos y se descartan solos."""
    containers = pg.locator('[data-e2e="recommend-list-item-container"]')
    n = min(containers.count(), limit)
    out = []
    for i in range(n):
        c = containers.nth(i)
        link = c.locator('a[href^="/@"]').first
        href = link.get_attribute("href") if link.count() > 0 else None
        if not href:
            continue
        handle = href.lstrip("/@").split("/")[0]
        desc = c.locator('[data-e2e="video-desc"]')
        text = desc.inner_text() if desc.count() > 0 else ""
        out.append((handle, text[:280]))
    return out


def _dump_profile(pg, handle=None):
    _refuse_if_paused()
    h = handle or MY_HANDLE
    pg.goto(f"https://www.tiktok.com/@{h}", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2800)
    _check_bot_warning(pg)


def dump_profile(handle=None):
    _refuse_if_paused()
    p, pg = _connect()
    try:
        _dump_profile(pg, handle)
        print(pg.inner_text("body")[:3000])
    finally:
        p.stop()


def _extract_grid_videos(pg, limit=12):
    """Vuelca (permalink, views) de los videos visibles en el grid de un
    perfil ya cargado (`[data-e2e="user-post-item"]`, confirmado en vivo
    el 22/09). No da autor/texto directamente en el grid (hay que abrir
    el post para eso, via _open_post) - sirve para elegir cuales abrir,
    no como candidato final por si solo."""
    items = pg.locator('[data-e2e="user-post-item"]')
    n = min(items.count(), limit)
    out = []
    for i in range(n):
        item = items.nth(i)
        link = item.locator("a").first
        href = link.get_attribute("href") if link.count() > 0 else None
        if not href:
            continue
        views_el = item.locator('[data-e2e="video-views"]')
        views = views_el.inner_text() if views_el.count() > 0 else "?"
        out.append({"url": href, "views": views})
    return out


def _open_post(pg, index=0):
    """Abre el post en el indice dado del grid ya cargado, haciendo CLICK
    (nunca goto directo a la URL del video si se puede evitar - mas fiel
    a un uso humano real). Devuelve True si se abrio el modal."""
    _refuse_if_paused()
    items = pg.locator('[data-e2e="user-post-item"]')
    if index >= items.count():
        return False
    items.nth(index).click()
    pg.wait_for_timeout(2500)
    return pg.locator('[data-e2e="browse-like-icon"]').count() > 0


def _close_post(pg):
    btn = pg.locator('[data-e2e="browse-close"]').first
    if btn.count() > 0:
        btn.click()
        pg.wait_for_timeout(500)
    else:
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(500)


def follow(handle):
    """Sigue una cuenta desde su perfil. Verifica que el boton deje de
    decir 'Seguir' (pasa a 'Siguiendo' o, si ya nos sigue, 'Amigos') -
    NO PROBADO EN VIVO con un envio real todavia (solo se confirmo la
    estructura del boton `[data-e2e="follow-button"]` y sus tres estados
    posibles: Seguir/Siguiendo/Amigos) - se confirma del todo con el
    primer uso real."""
    _refuse_if_paused()
    p, pg = _connect()
    try:
        _dump_profile(pg, handle)
        _assert_active_account(pg)
        btn = pg.locator('[data-e2e="follow-button"]').first
        if btn.count() == 0:
            raise RuntimeError(f"{handle}: no se encontró botón de seguir; no se realizó follow")
        current = btn.inner_text().strip()
        if current in ("Siguiendo", "Amigos", "Following", "Friends"):
            print(f"{handle}: ya estaba seguido ({current})")
            return "already"
        ig._human_click(pg, btn)
        pg.wait_for_timeout(1500)
        _check_bot_warning(pg)
        new_text = btn.inner_text().strip()
        if new_text in ("Siguiendo", "Amigos", "Following", "Friends"):
            print(f"{handle}: FOLLOWED (confirmado, estado={new_text})")
            return "followed"
        else:
            raise RuntimeError(f"{handle}: follow no confirmado (estado={new_text!r}); revisar antes de reintentar")
    finally:
        p.stop()


def _find_post_by_text(pg, target, limit=12):
    """Solo deja abierto el vídeo si hay una coincidencia única en el grid."""
    if not isinstance(target, str) or len(target.strip()) < 20:
        raise ValueError("text_fragment debe identificar el vídeo con 20 caracteres o más")
    n = min(pg.locator('[data-e2e="user-post-item"]').count(), limit)
    matches = []
    for i in range(n):
        if not _open_post(pg, i):
            continue
        _check_bot_warning(pg)
        desc_el = pg.locator('[data-e2e="browse-video-desc"]').first
        desc = desc_el.inner_text() if desc_el.count() > 0 else ""
        if target in desc:
            matches.append(i)
        _close_post(pg)
        if len(matches) > 1:
            raise RuntimeError(
                "El fragmento coincide con varios vídeos; usar texto o permalink "
                "más específico y NO actuar sobre el primer resultado"
            )
    if not matches:
        return False
    if not _open_post(pg, matches[0]):
        raise RuntimeError("El vídeo seleccionado dejó de estar disponible; no interactuar")
    _check_bot_warning(pg)
    desc = pg.locator('[data-e2e="browse-video-desc"]').first.inner_text()
    if target not in desc:
        raise RuntimeError("El vídeo ya no coincide con el fragmento tras reabrirlo")
    return True

def _video_like_control(pg):
    """Devuelve el botón de like del vídeo abierto y su estado aria-pressed."""
    controls = pg.locator(
        'button[data-e2e="browse-like-icon"], '
        'button:has([data-e2e="browse-like-icon"])'
    )
    if controls.count() != 1:
        raise RuntimeError(
            "TikTok: control de like ausente o ambiguo; no pulsar a ciegas"
        )
    button = controls.first
    state = button.get_attribute("aria-pressed")
    if state not in ("true", "false"):
        raise RuntimeError(
            "TikTok: el botón de like no expone aria-pressed; no se puede "
            "distinguir like de unlike con seguridad"
        )
    return button, state


def like(handle, text_fragment):
    """Da like a un post de `handle` cuya descripcion contenga
    `text_fragment` (mismo criterio que like_in_feed de instagram_interact.py
    - localizar por texto, nunca por indice ciego). NO PROBADO EN VIVO
    con un envio real todavia - estructura confirmada
    (`[data-e2e="browse-like-icon"]`), primer uso real lo confirma del
    todo."""
    _refuse_if_paused()
    p, pg = _connect()
    try:
        _dump_profile(pg, handle)
        _assert_active_account(pg)
        if not _find_post_by_text(pg, text_fragment):
            raise RuntimeError(f"No se encontró post de @{handle} con el texto {text_fragment!r}")
        text = pg.locator('[data-e2e="browse-video-desc"]').first.inner_text()
        ig._simulate_reading(pg, len(text.split()))
        btn, state = _video_like_control(pg)
        if state == "true":
            print(f"ese vídeo ya tenía like: {text[:80]}")
            return "already"
        ig._human_click(pg, btn)
        pg.wait_for_timeout(1200)
        _check_bot_warning(pg)
        _, final_state = _video_like_control(pg)
        if final_state != "true":
            raise RuntimeError(
                "TikTok: like no confirmado; revisar el vídeo antes de reintentar"
            )
        print(f"like dado (confirmado): {text[:80]}")
        return "created"
    finally:
        p.stop()


# AlreadyCommented importada de scan_common (23/09, centralizada). SIN
# VERIFICAR EN VIVO todavia (ver nota en _already_commented).


def _already_commented(pg):
    """NO VERIFICADO EN VIVO (23/09) - a proposito: `comment()` nunca se ha
    usado para un envio real (ver PENDIENTES.md, calentamiento conservador
    tras el incidente de captcha), asi que no hay ningun comentario nuestro
    real contra el que probar esta funcion, y TikTok es la red con el perfil
    de riesgo mas alto del proyecto para justificar navegacion extra solo
    para investigar el DOM. Implementado con el mismo patron de texto que
    Instagram (buscar `MY_HANDLE` como linea exacta en el cuerpo de la
    pagina) como red de seguridad razonable, pero DEBE confirmarse contra un
    video real la primera vez que `comment()` se use de verdad - ver
    PENDIENTES.md."""
    try:
        lines = [ln.strip() for ln in pg.inner_text("body").splitlines()]
    except Exception as exc:
        raise BotWarningDetected(
            "No se pudo comprobar si ya había comentario propio; se detiene la sesión"
        ) from exc
    return MY_HANDLE in lines


def comment(handle, text_fragment, comment_text):
    """Comenta un post de `handle` cuya descripcion contenga
    `text_fragment`. NO PROBADO EN VIVO con un envio real todavia -
    estructura confirmada (`[data-e2e="comment-text"]` editor Draft.js +
    `[data-e2e="comment-post"]`), primer uso real lo confirma del todo."""
    _refuse_if_paused()
    if not isinstance(comment_text, str) or not comment_text.strip():
        raise ValueError("El comentario de TikTok no puede estar vacío")
    _check_length(comment_text)
    _check_spanish_orthography(comment_text)
    p, pg = _connect()
    try:
        _dump_profile(pg, handle)
        _assert_active_account(pg)
        if not _find_post_by_text(pg, text_fragment):
            raise RuntimeError(f"No se encontró el vídeo de @{handle} con el fragmento {text_fragment!r}")
        if _already_commented(pg):
            raise AlreadyCommented(
                f"Ya parece haber un comentario nuestro en el video de {handle} - "
                "no se envia otro. (Guardia sin verificar en vivo, ver docstring.)"
            )
        text = pg.locator('[data-e2e="browse-video-desc"]').first.inner_text()
        ig._simulate_reading(pg, len(text.split()))
        box = pg.locator('[data-e2e="comment-text"]').first
        ig._human_type(pg, box, comment_text)
        pg.wait_for_timeout(500)
        pg.locator('[data-e2e="comment-post"]').first.click()
        pg.wait_for_timeout(2000)
        _check_bot_warning(pg)
        print(f"comentario enviado, pendiente de verificar en pantalla: {comment_text[:60]}")
        return "unverified"
    finally:
        p.stop()


if __name__ == "__main__":
    def _dispatch():
        _refuse_if_paused()
        cmd = sys.argv[1] if len(sys.argv) > 1 else None
        if cmd == "ensure-browser":
            ensure_browser()
        elif cmd == "health":
            ensure_browser(); health()
        elif cmd == "profile":
            ensure_browser(); dump_profile(sys.argv[2] if len(sys.argv) > 2 else None)
        elif cmd == "following-feed":
            ensure_browser(); dump_following_feed()
        elif cmd == "follow":
            ensure_browser(); follow(sys.argv[2])
        elif cmd == "like":
            ensure_browser(); like(sys.argv[2], sys.argv[3])
        elif cmd == "comment":
            ensure_browser(); comment(sys.argv[2], sys.argv[3], sys.argv[4])
        else:
            print(__doc__)
            sys.exit(1)

    try:
        _dispatch()
    except (InteractionsPaused, BotWarningDetected) as e:
        print(str(e))
        sys.exit(2)
