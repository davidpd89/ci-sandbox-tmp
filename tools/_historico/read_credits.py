import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    all_pages = [pg for c in b.contexts for pg in c.pages]

    # --- FLOW ---
    flow = next((pg for pg in all_pages if "labs.google" in pg.url), None)
    if flow:
        flow.bring_to_front()
        # Clic en avatar (esquina sup derecha) para ver puntos
        try:
            avatar = flow.locator("header img, [aria-label*='cuenta'], [aria-label*='account'], button img").last
            if avatar.is_visible(timeout=2000):
                avatar.click()
                flow.wait_for_timeout(1500)
        except Exception:
            pass
        flow.screenshot(path="C:/Temp/flow_avatar.png")
        # Leer todo el texto visible
        all_text = flow.evaluate("() => document.body.innerText")
        # Buscar líneas con números que parezcan créditos
        for line in all_text.split('\n'):
            l = line.strip()
            if l and any(w in l.lower() for w in ['punto', 'point', 'crédit', 'credit', 'saldo', 'balance']):
                print(f"Flow: {l[:100]}")

    # --- PIXVERSE ---
    pv = next((pg for pg in all_pages if "pixverse" in pg.url), None)
    if pv:
        pv.bring_to_front()
        pv.wait_for_timeout(1000)
        pv.screenshot(path="C:/Temp/pv_full.png")
        # Leer texto con créditos
        all_text_pv = pv.evaluate("() => document.body.innerText")
        for line in all_text_pv.split('\n'):
            l = line.strip()
            if l and any(w in l.lower() for w in ['crédit', 'credit', 'saldo', 'balance', 'gratis', 'free', 'diario']):
                print(f"PixVerse: {l[:100]}")
        # Buscar número cerca del avatar (suele ser el saldo)
        pv.screenshot(path="C:/Temp/pv_top.png", clip={"x":0,"y":0,"width":1912,"height":60})
    else:
        print("PixVerse no abierto — abriendo...")
