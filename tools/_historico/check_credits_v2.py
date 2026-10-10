import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    all_pages = [pg for c in b.contexts for pg in c.pages]
    flow = next((pg for pg in all_pages if "labs.google" in pg.url), None)

    if flow:
        # Navegar a la galería principal de Flow para ver créditos
        flow.bring_to_front()
        flow.goto("https://labs.google/fx/es/tools/flow")
        flow.wait_for_load_state("networkidle", timeout=15000)
        flow.wait_for_timeout(2000)
        flow.screenshot(path="C:/Temp/flow_home.png")

        # Buscar créditos en texto visible
        pts = flow.evaluate("""
            () => {
                // Buscar en todos los textos del DOM
                const walk = (node) => {
                    if (node.nodeType === 3) {
                        const t = node.textContent.trim();
                        if (/\d+\s*(puntos|points)/i.test(t) && t.length < 100) return t;
                    }
                    for (const c of node.childNodes) {
                        const r = walk(c);
                        if (r) return r;
                    }
                    return null;
                };
                return walk(document.body);
            }
        """)
        print(f"Flow créditos: {pts or '(no detectados en DOM)'}")

        # Navegar a PixVerse
        pixverse_page = flow.context.new_page()
        pixverse_page.goto("https://app.pixverse.ai/create/video")
        pixverse_page.wait_for_load_state("networkidle", timeout=20000)
        pixverse_page.wait_for_timeout(3000)
        pixverse_page.screenshot(path="C:/Temp/pixverse_credits.png")
        print("PixVerse screenshot guardado")
