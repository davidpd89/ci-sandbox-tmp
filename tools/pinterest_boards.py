"""Tableros de Pinterest con nombre claro y descripcion con palabras clave (06/10/2026, David: «informate bien y ajusta bien los tableros, asignalos bien»).

Las guias de 2026 coinciden en que el nombre del tablero y su descripcion pesan en la busqueda de Pinterest (~20 % del posicionamiento junto al titulo y la descripcion del Pin):
nombres buscables, no creativos, y 1-2 frases con la frase que la gente teclea. Aqui se define el MAPA de tableros de la cuenta; `ensure_boards()` crea el que falte y rellena la
descripcion SOLO si esta vacia (nunca pisa lo que David haya escrito). `pinterest_growth.board_for` reparte los Pines guardados segun el contenido.

    python tools/pinterest_boards.py [--apply]       # sin --apply solo informa de lo que haria
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pinterest_publish as pp
from playwright.sync_api import sync_playwright

BOARDS = {
    "Fantasía juvenil española": "Libros de fantasía juvenil escritos en español: novedades de 2025 y 2026, sagas, portal fantasy y romantasy, portadas y recomendaciones de lectura.",
    "Lugares literarios, bibliotecas y librerías": "Bibliotecas bonitas, librerías con encanto, cafeterías literarias y rincones de lectura para viajar de libro en libro.",
    "Recursos para escritores": "Herramientas gratuitas, guías y consejos para escribir una novela: personajes, construcción de mundos, estructura, corrección y autopublicación.",
    "Lecturas y reseñas de libros": "Reseñas, listas de lectura, retos y recomendaciones de libros en español: fantasía, novela y literatura para tu próxima lectura.",
    "Samuel entre mundos": "La novela Samuel entre mundos, de Autora Demo Díaz: portada, fragmentos, reseñas y el universo del libro.",
}


def board_exists(pg, name):
    """El tablero existe si su pagina carga con cabecera de tablero (la lista del perfil no expone nombres fiables)."""
    pg.goto(f"https://es.pinterest.com/autorademodiaz/{pp.board_slug(name)}/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4000)
    pp._check(pg)
    return pg.locator('[data-test-id="board-header"]').count() > 0


def create_board(pg, name, log=print):
    pg.goto("https://es.pinterest.com/autorademodiaz/_saved/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4500)
    pg.get_by_text("Crear", exact=True).last.click()
    pg.wait_for_timeout(1500)
    dialog = pg.locator('[role="dialog"]').last
    dialog.locator('input[type="text"], input:not([type])').first.fill(name)
    pg.wait_for_timeout(500)
    dialog.get_by_role("button", name="Crear", exact=True).last.click()
    pg.wait_for_timeout(3500)
    log(f"  tablero «{name}» creado")


def set_description_if_empty(pg, name, description, log=print):
    pg.goto(f"https://es.pinterest.com/autorademodiaz/{pp.board_slug(name)}/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4500)
    pg.get_by_label("Más opciones de tablero").first.click()
    pg.wait_for_timeout(900)
    pg.get_by_text("Editar información y configuración").first.click()
    pg.wait_for_timeout(1500)
    box = pg.locator("#boardEditDescription")
    if (box.input_value() or "").strip():
        log(f"  «{name}»: ya tiene descripcion; se respeta")
        pg.keyboard.press("Escape")
        return False
    box.fill(description)
    pg.wait_for_timeout(500)
    pg.get_by_role("button", name="Hecho", exact=True).last.click()
    pg.wait_for_timeout(2500)
    log(f"  «{name}»: descripcion puesta")
    return True


def ensure_boards(apply=False, log=print):
    p = sync_playwright().start()
    try:
        browser = p.chromium.connect_over_cdp(pp.CDP_URL)
        pg = browser.contexts[0].new_page()
        pg.set_default_timeout(15000)
        try:
            for name, description in BOARDS.items():
                if not board_exists(pg, name):
                    log(f"- falta el tablero «{name}»" + ("" if apply else " (se crearia)"))
                    if apply:
                        create_board(pg, name, log)
                if apply:
                    set_description_if_empty(pg, name, description, log)
        finally:
            pg.close()
    finally:
        p.stop()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    import action_ledger
    with action_ledger.browser_session(wait_minutes=40):
        ensure_boards(apply="--apply" in argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
