"""Inspecciona el panel de creación de PixVerse para ver el selector de duración."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()

    # Navegar al panel de creación y esperar que cargue
    # Primero volver al video creation desde el estado actual (detail view)
    # Buscar el botón de volver o navegar a /create/video
    back_btn = pv.locator("button[aria-label='Volver'], button:has-text('Atrás'), a[href*='create']").first
    try:
        if back_btn.is_visible(timeout=1000):
            back_btn.click()
            pv.wait_for_timeout(1500)
    except Exception:
        pass

    # Si seguimos en la vista de detalle, ir a la galería y crear
    if "/create" not in pv.url:
        # Buscar el icono de creación en sidebar
        create_icon = pv.locator("a[href*='create'], [data-menu='create'], li:has-text('Creación'), li:has-text('Crear')").first
        try:
            if create_icon.is_visible(timeout=2000):
                create_icon.click()
                pv.wait_for_timeout(2000)
        except Exception:
            pass

    pv.screenshot(path="C:/Temp/pv_create_full.png")
    print(f"URL: {pv.url}")

    # Capturar la barra inferior completa donde están los controles
    pv.screenshot(path="C:/Temp/pv_create_bottom.png", clip={"x": 0, "y": 380, "width": 1912, "height": 120})

    # Buscar todos los botones en la barra de creación (duración, aspecto, etc.)
    bottom_controls = pv.evaluate("""
        () => {
            const elements = Array.from(document.querySelectorAll('button, select, input, [role="radio"], [role="tab"]'));
            return elements
                .filter(el => {
                    const bb = el.getBoundingClientRect();
                    return bb.y > 380 && bb.height > 10 && bb.width > 10 && bb.offsetParent !== null;
                })
                .map(el => ({
                    tag: el.tagName,
                    text: (el.innerText || el.value || '').trim().substring(0, 30),
                    cls: el.className.substring(0, 50),
                    x: el.getBoundingClientRect().x,
                    y: el.getBoundingClientRect().y,
                    w: el.getBoundingClientRect().width,
                    h: el.getBoundingClientRect().height
                }))
                .slice(0, 30);
        }
    """)
    print(f"\nControles en zona inferior: {len(bottom_controls)}")
    for c in bottom_controls:
        print(f"  {c['tag']:8} x={c['x']:.0f} y={c['y']:.0f} {c['w']:.0f}x{c['h']:.0f} text='{c['text']}'")

    # Buscar específicamente textos que parezcan duraciones (5s, 8s, 10s, etc.)
    duration_els = pv.evaluate("""
        () => {
            const all = Array.from(document.querySelectorAll('*'));
            return all
                .filter(el => {
                    const t = (el.innerText || '').trim();
                    return /^(5|8|10|15)\s*s(eg)?$/i.test(t) && el.children.length === 0;
                })
                .map(el => ({
                    tag: el.tagName,
                    text: el.innerText.trim(),
                    x: el.getBoundingClientRect().x,
                    y: el.getBoundingClientRect().y,
                    visible: el.offsetParent !== null
                }));
        }
    """)
    print(f"\nElementos de duración (5s/8s/10s/15s): {len(duration_els)}")
    for d in duration_els:
        print(f"  {d['tag']} x={d['x']:.0f} y={d['y']:.0f} vis={d['visible']} '{d['text']}'")
