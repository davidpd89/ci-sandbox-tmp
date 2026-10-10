import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    pv = next(pg for pg in [x for c in b.contexts for x in c.pages] if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1000)
    pv.screenshot(path="C:/Temp/pv_state.png")

    # Ver texto visible y créditos
    credits = pv.evaluate("""
        () => {
            const els = document.querySelectorAll('*');
            for (const el of els) {
                const t = (el.innerText || '').trim();
                if (/\d+/.test(t) && t.length < 20 && el.children.length === 0) {
                    const bb = el.getBoundingClientRect();
                    if (bb.x > 1400 && bb.y < 60) return t;
                }
            }
            return null;
        }
    """)
    print(f"Créditos visibles: {credits}")

    # Ver todos los portales/dialogs abiertos
    dialogs = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[data-base-ui-portal], [role="dialog"], [class*="modal"]'))
            .filter(el => el.offsetParent !== null || el.children.length > 0)
            .map(el => el.innerText.substring(0, 100))
    """)
    print(f"Dialogs: {dialogs[:3]}")

    # Cards en la galería
    cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"], [class*="item"]'))
            .filter(el => {
                const bb = el.getBoundingClientRect();
                return bb.y > 150 && bb.width > 200;
            })
            .slice(0, 6)
            .map(el => ({
                text: el.innerText.substring(0, 60),
                x: el.getBoundingClientRect().x,
                y: el.getBoundingClientRect().y
            }))
    """)
    print(f"Cards ({len(cards)}):")
    for c in cards:
        print(f"  x={c['x']:.0f} y={c['y']:.0f} text={c['text'][:50]}")
