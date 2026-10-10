"""Diagnóstico: screenshot de X y busca el overlay que bloquea el compose button."""
import sys, time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9223", timeout=5000)
    pages = [pg for c in b.contexts for pg in c.pages]
    x = next((pg for pg in pages if "x.com" in pg.url), None)
    if not x:
        print("X no abierto"); exit()
    x.bring_to_front()
    x.wait_for_timeout(1000)
    x.screenshot(path="C:/Temp/x_diagnose.png")
    print(f"URL: {x.url}")

    # Buscar el botón de compose y ver qué lo bloquea
    btn = x.locator('[data-testid="SideNav_NewTweet_Button"]').first
    bb = btn.bounding_box()
    print(f"Compose button: {bb}")

    # Ver qué elemento está encima de esas coordenadas
    if bb:
        cx = bb['x'] + bb['width']/2
        cy = bb['y'] + bb['height']/2
        element_at = x.evaluate(f"""
            () => {{
                const el = document.elementFromPoint({cx}, {cy});
                return el ? {{tag: el.tagName, cls: el.className.substring(0,60), text: (el.innerText||'').substring(0,30)}} : null;
            }}
        """)
        print(f"Elemento en ({cx:.0f},{cy:.0f}): {element_at}")

    # Intentar click directo via JS (bypasa Playwright overlay check)
    print("\nIntentando JS click en New Tweet...")
    clicked = x.evaluate("""
        () => {
            const btn = document.querySelector('[data-testid="SideNav_NewTweet_Button"]');
            if (!btn) return 'not found';
            btn.click();
            return 'clicked';
        }
    """)
    print(f"Resultado: {clicked}")
    time.sleep(2)
    x.screenshot(path="C:/Temp/x_after_click.png")
    print(f"URL after click: {x.url}")
