"""Inspecciona el popup de suscripción de PixVerse para encontrar el botón de cierre."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(500)
    pv.screenshot(path="C:/Temp/popup_inspect.png")

    # Verificar si el popup está abierto
    has_popup = pv.evaluate("""
        () => !!Array.from(document.querySelectorAll('*')).find(
            e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'))
    """)
    print(f"Popup abierto: {has_popup}")

    if has_popup:
        # Buscar cualquier elemento en el top-right del viewport (posible X)
        top_right = pv.evaluate("""
            () => {
                const W = window.innerWidth, H = window.innerHeight;
                return Array.from(document.querySelectorAll('*'))
                    .filter(el => {
                        const bb = el.getBoundingClientRect();
                        // Top right zone: x > 850, y < 350, visible
                        return bb.x > 850 && bb.y < 350 && bb.width > 0 && bb.height > 0 && el.offsetParent !== null;
                    })
                    .filter(el => {
                        // Small elements (likely buttons/icons)
                        const bb = el.getBoundingClientRect();
                        return bb.width < 80 && bb.height < 80;
                    })
                    .map(el => ({
                        tag: el.tagName,
                        text: (el.innerText||'').trim().substring(0,20),
                        cls: el.className.substring(0,50),
                        x: el.getBoundingClientRect().x,
                        y: el.getBoundingClientRect().y,
                        w: el.getBoundingClientRect().width,
                        h: el.getBoundingClientRect().height,
                        role: el.getAttribute('role'),
                        aria: el.getAttribute('aria-label')
                    }))
                    .slice(0, 30);
            }
        """)
        print(f"\nElementos pequeños en top-right:")
        for el in top_right:
            print(f"  {el['tag']:8} x={el['x']:.0f} y={el['y']:.0f} {el['w']:.0f}x{el['h']:.0f} text='{el['text']}' cls={el['cls'][:30]} aria={el['aria']}")

        # Dump el HTML del popup para encontrar el close button
        popup_html = pv.evaluate("""
            () => {
                const modal = Array.from(document.querySelectorAll('*')).find(
                    e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar') &&
                    e.tagName !== 'HTML' && e.tagName !== 'BODY');
                if (!modal) return 'modal not found';
                // Subir al padre más cercano con clase modal/overlay
                let el = modal;
                for (let i = 0; i < 5; i++) {
                    el = el.parentElement;
                    if (!el) break;
                }
                return el ? el.outerHTML.substring(0,2000) : 'no parent found';
            }
        """)
        print(f"\nHTML popup (primeros 2000 chars):")
        print(popup_html[:1500])
