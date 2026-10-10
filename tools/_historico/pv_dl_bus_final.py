"""Descarga el vídeo de la parada de bus ya generado."""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\07-tarde-por-una-escena\clip1.mp4")
OUT.parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    ctx = b.contexts[0]
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1000)
    pv.screenshot(path="C:/Temp/bus_current.png")

    # Buscar el primer card (el más reciente = el de hoy)
    # El primer card en la galería debería ser nuestro vídeo de la parada de bus
    # Coordenadas aproximadas del primer card: x~305, y~285 (en pantalla 1536x864)
    print("Clicando primer card...")
    pv.mouse.click(305, 285)
    pv.wait_for_timeout(3000)
    pv.screenshot(path="C:/Temp/bus_player.png")

    # Leer el título del video para confirmar que es el correcto
    title = pv.evaluate("""
        () => {
            // Buscar el texto del título en el panel de info
            const info = document.querySelector('[class*="info"], [class*="Info"], [class*="detail"]');
            if (info) return info.innerText.substring(0, 100);
            // Buscar el prompt en la sección de información
            const all = Array.from(document.querySelectorAll('*'));
            for (const el of all) {
                if ((el.innerText||'').includes('bus') && el.offsetParent) return el.innerText.substring(0,100);
            }
            return null;
        }
    """)
    print(f"Info del vídeo: {title}")

    # Obtener src del video
    src = None
    for _ in range(15):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10:
            print(f"src: {src[:80]}")
            break
        pv.wait_for_timeout(1000)

    if src:
        cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
        ua = pv.evaluate("() => navigator.userAgent")
        r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
        if r.status_code == 200 and len(r.content) > 50000:
            OUT.write_bytes(r.content)
            dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
            print(f"✓ {OUT.name} ({OUT.stat().st_size//1024}KB) dur={dur}s")
        else:
            print(f"Error: {r.status_code} {len(r.content)//1024}KB — puede ser el video incorrecto")
    else:
        print("No src — el vídeo puede no estar listo aún")

    # Verificar créditos
    creds = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos: {creds}")
