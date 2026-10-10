"""Descarga el vídeo de PixVerse usando requests + cookies del browser."""
import sys, io, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright
import requests

CDP_URL = "http://127.0.0.1:9223"
OUT = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\04-resaca-libro\clip1.mp4")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    pv = next(pg for pg in [x for c in b.contexts for x in c.pages] if "pixverse" in pg.url)
    pv.bring_to_front()

    # Obtener el src del vídeo activo
    src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
    if not src:
        # Clicar en el primer card para activar el player
        pv.mouse.click(374, 362)
        time.sleep(3)
        for _ in range(15):
            src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
            if src and len(src) > 10: break
            time.sleep(1)

    print(f"Video URL: {src[:100] if src else 'None'}")
    if not src:
        sys.exit(1)

    # Obtener cookies del browser
    cookies = b.contexts[0].cookies()
    pv_cookies = {c['name']: c['value'] for c in cookies if 'pixverse' in c.get('domain', '')}
    print(f"Cookies PixVerse: {len(pv_cookies)}")

    # User-Agent del browser
    ua = pv.evaluate("() => navigator.userAgent")

    # Descargar con requests
    headers = {
        "User-Agent": ua,
        "Referer": "https://app.pixverse.ai/",
        "Origin": "https://app.pixverse.ai",
    }
    r = requests.get(src, cookies=pv_cookies, headers=headers, stream=True, timeout=60)
    print(f"Status: {r.status_code} Content-Type: {r.headers.get('content-type','?')}")

    if r.status_code == 200:
        with open(OUT, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        dur_est = OUT.stat().st_size / 1024 / 100  # rough estimate
        print(f"Guardado: {OUT.name} ({OUT.stat().st_size//1024}KB)")
    else:
        print(f"Error {r.status_code}: {r.text[:200]}")

        # Fallback: buscar botón de descarga y usar expect_download
        print("Intentando botón de descarga...")
        try:
            dl_btn = pv.locator("button[aria-label*='download'], button[aria-label*='Descargar'], button:has-text('Download')").first
            if dl_btn.is_visible(timeout=3000):
                with pv.expect_download(timeout=30000) as dl:
                    dl_btn.click()
                d = dl.value
                d.save_as(OUT)
                print(f"Descargado: {OUT.name} ({OUT.stat().st_size//1024}KB)")
        except Exception as e:
            print(f"Fallback error: {e}")
