"""Clic directo en el primer card de PixVerse y descarga via blob."""
import sys, io, base64, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\04-resaca-libro\clip1.mp4")

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvc_{name}.png")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    ctx = b.contexts[0]
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1000)

    # Buscar cards de vídeo por sus contenedores — PixVerse usa divs clickeables
    cards_info = pv.evaluate("""
        () => {
            // Buscar los elementos con texto del alt que matchean nuestro prompt
            const allEls = Array.from(document.querySelectorAll('[class*="card"], [class*="item"], [class*="video"], [class*="Card"], [class*="Item"]'));
            return allEls.filter(el => {
                const bb = el.getBoundingClientRect();
                return bb.width > 80 && bb.height > 60 && bb.y > 30 && bb.y < 300;
            }).map(el => ({
                tag: el.tagName,
                cls: el.className.substring(0, 50),
                x: el.getBoundingClientRect().x,
                y: el.getBoundingClientRect().y,
                w: el.getBoundingClientRect().width,
                h: el.getBoundingClientRect().height,
                text: (el.innerText || '').substring(0, 40)
            })).slice(0, 10);
        }
    """)
    print(f"Cards encontrados: {len(cards_info)}")
    for c in cards_info[:5]:
        print(f"  {c['tag']} x={c['x']:.0f} y={c['y']:.0f} {c['w']:.0f}x{c['h']:.0f} text={c['text']}")

    if cards_info:
        # Clicar el primero (más reciente)
        fc = cards_info[0]
        cx, cy = fc['x'] + fc['w']/2, fc['y'] + fc['h']/2
        print(f"Clic en ({cx:.0f}, {cy:.0f})")
        pv.mouse.click(cx, cy)
    else:
        # Fallback: clic estimado en primera posición de la galería
        print("Fallback: clic estimado en primer card")
        pv.mouse.click(170, 150)  # Estimado para pantalla 1912px

    pv.wait_for_timeout(3000)
    ss(pv, "01_after_click")

    # Esperar <video> en el player
    src = None
    for attempt in range(20):
        src = pv.evaluate("""
            () => {
                const vs = document.querySelectorAll('video');
                for (const v of vs) {
                    const s = v.src || v.currentSrc || '';
                    if (s && s.length > 10) return s;
                }
                return null;
            }
        """)
        if src:
            print(f"Video src: {src[:80]}")
            break
        pv.wait_for_timeout(1000)

    ss(pv, "02_player")

    if src:
        print("Descargando...")
        if src.startswith("blob:"):
            b64 = pv.evaluate("""
                async (url) => {
                    const r = await fetch(url);
                    const buf = await r.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    let s = ''; const C = 8192;
                    for (let i=0; i<bytes.length; i+=C) s += String.fromCharCode(...bytes.subarray(i, i+C));
                    return btoa(s);
                }
            """, src)
            OUT.write_bytes(base64.b64decode(b64))
        elif src.startswith("http"):
            import urllib.request
            urllib.request.urlretrieve(src, OUT)

        size = OUT.stat().st_size
        dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
        print(f"Guardado: {OUT.name} ({size//1024}KB) duración={dur}s")
    else:
        print("[WARN] No se encontró video src. Ver screenshot 02_player")
