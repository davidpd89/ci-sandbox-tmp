from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1] / "publicaciones GPT"

CAPTURES = [
    (
        2,
        "https://autorademodiaz.com/las-manecillas-del-recuerdo/fragmentos/",
        None,
    ),
    (
        4,
        "https://autorademodiaz.com/premios.html",
        "[data-award-result]:has-text('Primer Premio')",
    ),
    (
        5,
        "https://autorademodiaz.com/prensa.html",
        "text=La orilla de las letras",
    ),
    (
        7,
        "https://autorademodiaz.com/cuaderno/que-es-el-portal-fantasy/",
        None,
    ),
    (
        8,
        "https://autorademodiaz.com/herramientas/repeticiones/",
        "text=Analizar repeticiones",
    ),
]


def close_overlays(page):
    for label in ("Rechazo", "Rechazar", "Aceptar", "Cerrar", "Ahora no"):
        button = page.get_by_role("button", name=label, exact=False)
        if button.count():
            try:
                button.first.click(timeout=800)
            except Exception:
                pass


with sync_playwright() as playwright:
    browser = playwright.chromium.connect_over_cdp("http://127.0.0.1:9223")
    context = browser.contexts[0]
    page = context.new_page()
    page.set_viewport_size({"width": 1080, "height": 1350})

    for number, url, focus in CAPTURES:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1800)
        close_overlays(page)

        if focus:
            target = page.locator(focus).first
            target.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
        else:
            page.evaluate("window.scrollTo(0, 0)")

        page.screenshot(path=str(ROOT / str(number) / "imagen.png"), full_page=False)

    page.close()
    browser.close()
