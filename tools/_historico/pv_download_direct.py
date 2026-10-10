import sys, io, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright
from pathlib import Path

CDP_URL = "http://127.0.0.1:9223"
OUT = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\04-resaca-libro\clip1.mp4")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    pv = next(pg for pg in [x for c in b.contexts for x in c.pages] if "pixverse" in pg.url)
    pv.bring_to_front()
    # Click the first video card (center at x=374, y=362)
    pv.mouse.click(374, 362)
    pv.wait_for_timeout(3000)
    pv.screenshot(path="C:/Temp/pvclick.png")

    src = None
    for _ in range(20):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src || v.currentSrc) : null; }")
        if src and len(src) > 10:
            print(f"src: {src[:80]}")
            break
        pv.wait_for_timeout(1000)
    else:
        print("No src encontrado")
        sys.exit(1)

    # Descargar siempre via browser fetch (tiene cookies de autenticación)
    print(f"Descargando via browser fetch...")
    b64 = pv.evaluate("""
        async (url) => {
            const r = await fetch(url, {credentials: 'include'});
            if (!r.ok) return {error: r.status + ' ' + r.statusText};
            const buf = await r.arrayBuffer();
            const bytes = new Uint8Array(buf);
            let s = ''; const C = 8192;
            for (let i = 0; i < bytes.length; i += C) s += String.fromCharCode(...bytes.subarray(i, i + C));
            return btoa(s);
        }
    """, src)
    if isinstance(b64, dict) and "error" in b64:
        print(f"Fetch error: {b64['error']}")
        sys.exit(1)
    OUT.write_bytes(base64.b64decode(b64))

    dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
    print(f"Guardado: {OUT.name} ({OUT.stat().st_size//1024}KB) dur={dur}s")
