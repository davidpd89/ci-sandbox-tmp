"""Lee el contenido del popup de suscripción y busca el botón de cierre."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1000)
    pv.screenshot(path="C:/Temp/pv_popup_now.png")

    # Leer todos los botones visibles en el popup
    all_btns = pv.evaluate("""
        () => Array.from(document.querySelectorAll('button, [role="button"], a[href="#"]'))
            .filter(el => el.offsetParent !== null)
            .map(el => ({
                text: (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().substring(0,40),
                cls: el.className.substring(0,50),
                x: el.getBoundingClientRect().x,
                y: el.getBoundingClientRect().y,
                w: el.getBoundingClientRect().width,
                h: el.getBoundingClientRect().height
            }))
            .filter(el => el.text || el.cls)
    """)
    print(f"Botones visibles: {len(all_btns)}")
    for btn in all_btns[:20]:
        print(f"  '{btn['text'][:30]}' x={btn['x']:.0f} y={btn['y']:.0f} {btn['w']:.0f}x{btn['h']:.0f} cls={btn['cls'][:30]}")

    # Buscar texto del popup
    popup_text = pv.evaluate("""
        () => {
            const modals = document.querySelectorAll('[class*="modal"], [class*="Modal"], [class*="dialog"], [role="dialog"], [class*="popup"]');
            const texts = [];
            for (const m of modals) {
                if (m.offsetParent) texts.push(m.innerText.substring(0,200));
            }
            return texts;
        }
    """)
    print(f"\nTexto en modales: {popup_text[:3]}")

    # Buscar específicamente botones de cierre (X)
    close_btns = pv.evaluate("""
        () => Array.from(document.querySelectorAll('button, [role="button"]'))
            .filter(el => {
                const t = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().toLowerCase();
                return el.offsetParent !== null && (t === 'x' || t === '×' || t === 'close' || t === 'cerrar' || t === '✕' || t.includes('close') || el.querySelector('svg[class*="close"]') || el.querySelector('[class*="close"]'));
            })
            .map(el => ({
                text: el.innerText.trim().substring(0,20),
                x: el.getBoundingClientRect().x,
                y: el.getBoundingClientRect().y
            }))
    """)
    print(f"\nBotones de cierre: {close_btns}")
