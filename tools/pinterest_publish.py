"""Publicacion propia en Pinterest por la WEB (06/10/2026, David: «Facebook, Instagram, Pinterest, Reddit… tendras que hacerlo, las tenemos logueadas por web»).

Flujo comprobado en vivo (es.pinterest.com/pin-creation-tool/): subir la imagen (`#storyboard-upload-input`) crea un BORRADOR automatico («Borradores de Pines»); se rellenan Titulo
(`#storyboard-selector-title`), Descripcion (div `combobox` «Describe tu Pin»), Enlace (`#WebsiteField`), Tablero (desplegable) y, en «Mas opciones», el Texto alternativo; se pulsa
«Publicar». Seguridades: pagina propia (no toca las pestanas de otras redes), cuenta comprobada, captcha/aviso = parar sin reintentar, todos los campos se RELEEN antes de publicar y,
si algo no coincide, NO se publica. Los borradores anteriores no se eliminan automaticamente: pueden ser trabajo manual de otro usuario.

    python tools/pinterest_publish.py FICHA_CARPETA [--apply]      # sin --apply solo valida la ficha local, sin abrir Pinterest
"""
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright
from pinterest_media_guard import (PinPreflightError, validate_web_pin_fields,
                                  validate_web_pin_image)

CDP_URL = "http://127.0.0.1:9223"
CREATE_URL = "https://es.pinterest.com/pin-creation-tool/"
BOT_SIGNALS = ["actividad inusual", "unusual activity", "verifica que eres una persona", "captcha", "tu cuenta ha sido suspendida", "temporarily restricted"]
TITLE_MAX, DESC_MAX = 100, 800


class PinterestPublishError(RuntimeError):
    pass


def _check(pg):
    if "/login" in pg.url:
        raise PinterestPublishError("Pinterest pide iniciar sesion; parar")
    try:
        text = pg.inner_text("body").lower()
    except Exception as exc:
        raise PinterestPublishError("no se pudo leer la pantalla; parar") from exc
    for signal in BOT_SIGNALS:
        if signal in text:
            raise PinterestPublishError(f"aviso de Pinterest en pantalla ({signal!r}); parar y avisar a David")


def _assert_account(pg):
    if pg.locator("text=David Porto Díaz | Escritor").count() == 0:
        raise PinterestPublishError("no se confirma la cuenta David Porto Díaz | Escritor; parar")


def board_slug(name):
    """«Fantasía juvenil española» -> fanta%C3%ADa-juvenil-espa%C3%B1ola (Pinterest conserva tildes y eñes, codificadas en la URL; comprobado en vivo el 06/10)."""
    words = re.findall(r"[^\W_]+", str(name).casefold())
    return urllib.parse.quote("-".join(words))


def board_pins(pg, board, limit=12):
    """[(url, etiqueta)] de los primeros Pines del tablero (los mas recientes primero)."""
    pg.goto(f"https://es.pinterest.com/davidportodiaz/{board_slug(board)}/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4500)
    _check(pg)
    rows = pg.evaluate("""() => Array.from(document.querySelectorAll('a[href*="/pin/"]')).map(a => [a.getAttribute('href'), a.getAttribute('aria-label') || ''])""")
    out, seen = [], set()
    for href, label in rows:
        if "/analytics" in href or href in seen:
            continue
        seen.add(href)
        out.append(("https://es.pinterest.com" + href if href.startswith("/") else href, label))
    return out[:limit]


def find_pin(pg, board, title, tries=4):
    """URL del Pin recien publicado: el primero del tablero cuya etiqueta contiene el titulo (el indice de Pinterest tarda unos segundos)."""
    for _ in range(tries):
        for url, label in board_pins(pg, board):
            if title.casefold() in label.casefold():
                return url
        pg.wait_for_timeout(5000)
    return None


def delete_drafts(pg, log=print):
    """Elimina los borradores de Pines pendientes (restos de un intento anterior o el que acaba de crear un ensayo). Devuelve cuantos."""
    removed = 0
    for _ in range(10):
        item = pg.get_by_label("Acciones en el borrador del Pin")
        if item.count() == 0:
            break
        item.first.click()
        pg.wait_for_timeout(500)
        pg.get_by_text("Eliminar", exact=True).first.click()
        pg.wait_for_timeout(600)
        pg.locator('[role="dialog"], [data-test-id="confirm-dialog"]').get_by_text("Eliminar", exact=True).last.click()
        pg.wait_for_timeout(1500)
        removed += 1
    if removed:
        log(f"  {removed} borrador(es) de Pines eliminado(s)")
    return removed


def _fill(pg, title, description, link, alt, board, log=print):
    title_box = pg.locator("#storyboard-selector-title")
    title_box.fill(title)
    desc = pg.locator('[role="combobox"][aria-label="Describe tu Pin"]').first
    desc.click()
    pg.keyboard.type(description, delay=4)
    pg.locator("#WebsiteField").fill(link)
    _choose_board(pg, board, log)
    pg.get_by_text("Más opciones", exact=True).first.click()
    pg.wait_for_timeout(800)
    pg.get_by_placeholder("Describe los detalles visuales de tu Pin").fill(alt)


# 06/10 (GPT): un typo o una ficha mal generada no debe crear un tablero publico nuevo. Lista cerrada + alias de los nombres que usan las fichas de GPT; los tableros nuevos se anaden aqui
# y en `pinterest_boards.BOARDS` a proposito (y se crean con `pinterest_boards.py --apply`).
KNOWN_BOARDS = ("Fantasía juvenil española", "Lugares literarios, bibliotecas y librerías", "Recursos para escritores", "Lecturas y reseñas de libros", "Samuel entre mundos")
BOARD_ALIASES = {"herramientas para escritores": "Recursos para escritores", "recursos para escritores": "Recursos para escritores", "lecturas y fantasía": "Lecturas y reseñas de libros",
                 "lecturas y fantasia": "Lecturas y reseñas de libros", "clubes de lectura": "Lecturas y reseñas de libros", "libros y reseñas": "Lecturas y reseñas de libros"}


def resolve_board(name):
    """Nombre canonico del tablero (lista cerrada o alias) o PinterestPublishError."""
    if not isinstance(name, str):
        raise PinterestPublishError("tablero: nombre obligatorio")
    wanted = name.strip()
    for known in KNOWN_BOARDS:
        if wanted.casefold() == known.casefold():
            return known
    if wanted.casefold() in BOARD_ALIASES:
        return BOARD_ALIASES[wanted.casefold()]
    raise PinterestPublishError(f"el tablero «{wanted}» no esta en la lista cerrada ({', '.join(KNOWN_BOARDS)}); corregir la ficha o anadirlo a KNOWN_BOARDS")


def _choose_board(pg, board, log=print):
    """Elige el tablero por su nombre exacto; si no existe falla (los tableros se crean aparte, con `pinterest_boards.py`)."""
    if _board_selected(pg, board):
        return
    pg.locator('[data-test-id="board-dropdown-select-button"]').first.click()
    pg.wait_for_timeout(1200)
    row = pg.locator('[data-test-id="board-row-' + board + '"]')
    if row.count() == 0:
        raise PinterestPublishError(f"el tablero «{board}» no existe en la cuenta: crearlo con pinterest_boards.py --apply (no se crea desde una ficha)")
    row.first.click()
    pg.wait_for_timeout(1000)


def _board_selected(pg, board):
    button = pg.locator('[data-test-id="board-dropdown-select-button"]').first
    try:
        return board.casefold() in (button.inner_text() or "").casefold()
    except Exception:
        return False


def _verify(pg, title, description, link, alt, board):
    """Comparar el contenido completo escrito, sin inferir éxito del editor."""
    problems = []
    if pg.locator("#storyboard-selector-title").input_value().strip() != title.strip():
        problems.append("titulo")
    # La descripción es un combobox de contenido enriquecido. Leer su texto
    # visible; un campo no legible equivale a preflight fallido.
    try:
        actual_description = pg.locator(
            '[role="combobox"][aria-label="Describe tu Pin"]').first.inner_text()
    except Exception:
        problems.append("descripcion no legible")
    else:
        if " ".join(actual_description.split()) != " ".join(description.split()):
            problems.append("descripcion")
    if pg.locator("#WebsiteField").input_value().strip().rstrip("/") != link.strip().rstrip("/"):
        problems.append("enlace")
    if pg.get_by_placeholder("Describe los detalles visuales de tu Pin").input_value().strip() != alt.strip():
        problems.append("texto alternativo")
    if not _board_selected(pg, board):
        problems.append("tablero")
    return problems


def publish_pin(image, title, description, link, alt, board, apply=False, log=print, before_submit=None):
    """Publica un Pin. Sin --apply: comprueba entrada local, sin red ni borradores.

    Después de iniciar un clic, cualquier excepción requiere conciliación
    remota; nunca limpiar borradores automáticamente ni suponer que falló.
    """
    board = resolve_board(board)
    # El guard maneja tipos inválidos, valores vacíos y longitudes antes de
    # abrir Playwright; no usar len() sobre metadatos externos sin validar.
    try:
        validate_web_pin_fields(title, description, link, alt)
        image_info = validate_web_pin_image(image)
    except PinPreflightError as exc:
        raise PinterestPublishError(str(exc)) from exc
    if not apply:
        log(f"  ensayo offline: imagen {image_info['format']} "
            f"{image_info['width']}x{image_info['height']} "
            f"({image_info['bytes']} bytes), metadatos válidos; "
            "no se crea borrador ni se confirma enlace remoto")
        if not image_info["aspect_2_3"]:
            log("  aviso: imagen no tiene proporción recomendada 2:3")
        return "ensayo"
    import voice_output_finalization as voice
    fields = {"titulo": title, "descripcion": description, "alt": alt}
    voice.inspect_fields(fields, network="pinterest", queue="WEB", log=log)
    p = sync_playwright().start()
    try:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        pg = browser.contexts[0].new_page()
        pg.set_default_timeout(15000)
        try:
            pg.goto(CREATE_URL, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(4000)
            _check(pg)
            _assert_account(pg)
            # No eliminar borradores preexistentes: pueden ser trabajo humano.
            # Revalidar justo antes de cargar: el archivo pudo cambiar mientras
            # se obtenía el turno exclusivo del navegador.
            try:
                validate_web_pin_image(image)
            except PinPreflightError as exc:
                raise PinterestPublishError(str(exc)) from exc
            pg.set_input_files("#storyboard-upload-input", image)
            pg.wait_for_selector('text="¡Cambios guardados!"', timeout=30000)
            _fill(pg, title, description, link, alt, board, log)
            problems = _verify(pg, title, description, link, alt, board)
            if problems:
                raise PinterestPublishError("el formulario no coincide con la ficha (" + ", ".join(problems) + "); no se publica")
            button = pg.get_by_role("button", name="Publicar", exact=True).first
            # Esperar acción posible SIN pulsar. Un botón bloqueado/no visible
            # no debe dejar una intención de publicación que nunca se intentó.
            button.click(trial=True)
            # El DOM puede cambiar durante la espera del botón. Volver a
            # comprobar también captcha, cuenta y descripción justo antes
            # de registrar la intención y efectuar el clic real.
            _check(pg)
            _assert_account(pg)
            problems = _verify(pg, title, description, link, alt, board)
            if problems:
                raise PinterestPublishError(
                    "el formulario cambió durante el preflight ("
                    + ", ".join(problems) + "); no se publica")
            if before_submit is not None:
                # Sólo después de comprobar acción y campos, antes del clic.
                before_submit()
            # El clic puede dispararse y luego fallar mientras Playwright espera
            # una navegación. Desde este punto el resultado SIEMPRE es incierto
            # hasta obtener permalink; no limpiar borradores en excepciones.
            button.click()
            for _ in range(30):
                pg.wait_for_timeout(2000)
                _check(pg)
                if pg.locator('[aria-label="Acciones en el borrador del Pin"]').count() == 0:
                    break
            else:
                raise PinterestPublishError("el borrador sigue en la lista tras 60 s: no se confirma la publicacion (comprobar el tablero antes de repetir)")
            try:
                pg.keyboard.press("Escape")          # aviso «Instala la extension» que Pinterest muestra tras publicar
            except Exception:
                pass
            url = find_pin(pg, board, title)
            if not url:
                raise PinterestPublishError("el borrador desaparecio pero el Pin no aparece aun en su tablero (comprobar antes de repetir)")
            return url
        finally:
            pg.close()
    finally:
        p.stop()


def own_recent_texts(boards=None):
    """Etiquetas de los Pines recientes de los tableros de la cuenta (la pestana «Creados» tarda en reflejarlos), para saber si una ficha ya esta publicada.
    Abre una pagina propia en el Edge (hace falta el turno del navegador)."""
    p = sync_playwright().start()
    try:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        pg = browser.contexts[0].new_page()
        pg.set_default_timeout(15000)
        try:
            if not boards:
                pg.goto("https://es.pinterest.com/davidportodiaz/_saved/", wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(4500)
                _check(pg)
                names = pg.evaluate("""() => Array.from(document.querySelectorAll('a[href^="/davidportodiaz/"]')).map(a => a.getAttribute('href').split('/')[2]).filter(s => s && !s.startsWith('_'))""")
                slugs = list(dict.fromkeys(names))[:8]
            else:
                slugs = [board_slug(b) for b in boards]
            texts = []
            for slug in slugs:
                for _url, label in board_pins(pg, urllib.parse.unquote(slug).replace("-", " "), limit=20):
                    if label not in texts:
                        texts.append(label)
            return texts
        finally:
            pg.close()
    finally:
        p.stop()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    import content_queue as cq
    import action_ledger
    folder = next((a for a in argv if not a.startswith("--")), None)
    item = next((i for i in cq.scan_items("pinterest") if os.path.basename(i["carpeta"]) == folder), None) if folder else None
    if not item:
        print(__doc__)
        return 2
    meta = item["meta"]
    apply = "--apply" in argv
    guard = action_ledger.browser_session(wait_minutes=40) if apply else None
    if guard is None:
        url = publish_pin(item["imagen"], item["titulo"], item["texto"], meta["enlace"], item["alt"] or meta.get("alt", ""), meta["tablero"], apply=False)
    else:
        with guard:
            import circuit_breaker as cb
            allowed, reason = cb.write_preflight("pinterest")
            if not allowed:
                print(f"[pinterest] NO se publica: cortacircuitos ABIERTO ({reason})")
                return 0
            url = publish_pin(item["imagen"], item["titulo"], item["texto"], meta["enlace"], item["alt"] or meta.get("alt", ""), meta["tablero"], apply=True)
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
