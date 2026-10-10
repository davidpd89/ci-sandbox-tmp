"""Inspecciona la página de Flow en Edge para encontrar el selector del input."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    all_pages = [pg for c in b.contexts for pg in c.pages]
    flow = next(pg for pg in all_pages if "labs.google" in pg.url)
    flow.bring_to_front()
    flow.wait_for_timeout(2000)

    print(f"URL: {flow.url}")

    # Buscar todos los inputs/textareas/contenteditable visibles
    inputs = flow.evaluate("""
        () => {
            const els = document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"], [role="textbox"]');
            return Array.from(els).map(el => ({
                tag: el.tagName,
                type: el.getAttribute('type'),
                placeholder: el.getAttribute('placeholder'),
                aria: el.getAttribute('aria-label'),
                visible: el.offsetParent !== null,
                classes: el.className.substring(0, 80),
                id: el.id.substring(0, 40)
            }));
        }
    """)
    print(f"\nInputs encontrados: {len(inputs)}")
    for inp in inputs:
        if inp['visible']:
            print(f"  VISIBLE: {inp['tag']} | placeholder={inp['placeholder']} | aria={inp['aria']} | id={inp['id']}")

    # Ver si hay un botón de puntos/saldo
    points = flow.evaluate("""
        () => {
            const all = document.querySelectorAll('*');
            for (const el of all) {
                const t = (el.innerText || '').trim();
                if (/^\\d+$/.test(t) && parseInt(t) > 0 && parseInt(t) <= 200 && el.children.length === 0) {
                    return t + ' (en: ' + el.tagName + '.' + el.className.substring(0,30) + ')';
                }
            }
            return null;
        }
    """)
    print(f"\nPuntos detectados: {points}")

    # Screenshot
    flow.screenshot(path="C:/Temp/flow_screenshot.png")
    print("\nScreenshot guardado en C:/Temp/flow_screenshot.png")
