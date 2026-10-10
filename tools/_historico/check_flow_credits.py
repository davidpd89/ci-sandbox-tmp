"""Screenshot de Flow y PixVerse para ver créditos disponibles."""
import sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    all_pages = [pg for c in b.contexts for pg in c.pages]

    for pg in all_pages:
        print(f"  {pg.url[:80]}")

    # Screenshot de Flow
    flow = next((pg for pg in all_pages if "labs.google" in pg.url), None)
    if flow:
        flow.bring_to_front()
        flow.wait_for_timeout(1500)
        flow.screenshot(path="C:/Temp/flow_credits.png")
        # Intentar leer puntos
        pts = flow.evaluate("""
            () => {
                const els = document.querySelectorAll('*');
                for (const el of els) {
                    const t = (el.innerText || '').trim();
                    if (/\d+\s*(puntos|points|créditos)/i.test(t) && t.length < 60) return t;
                }
                return null;
            }
        """)
        print(f"Flow puntos detectados: {pts}")
    else:
        print("Flow no está abierto en Edge")
