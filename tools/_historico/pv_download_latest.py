"""Descarga el vídeo más reciente de PixVerse (primer thumbnail en la lista)."""
import sys, io, base64, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\04-resaca-libro\clip1.mp4")

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvdl_{name}.png")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    ctx = b.contexts[0]
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1500)
    ss(pv, "01_before")

    # Encontrar y clicar el primer card de vídeo generado (el más reciente)
    # Los cards tienen thumbnails de imagen con alt text que coincide con el prompt
    cards = pv.evaluate("""
        () => {
            // Buscar elementos con texto del prompt o thumbnails de vídeo
            const imgs = Array.from(document.querySelectorAll('img[src*="cdn"], img[src*="storage"], img[alt]'));
            return imgs.slice(0, 8).map(img => ({
                src: img.src.substring(0, 80),
                alt: img.alt.substring(0, 60),
                bb: {x: img.getBoundingClientRect().x, y: img.getBoundingClientRect().y,
                     w: img.getBoundingClientRect().width, h: img.getBoundingClientRect().height}
            }));
        }
    """)
    print(f"Thumbnails encontrados: {len(cards)}")
    for c in cards[:5]:
        print(f"  x={c['bb']['x']:.0f} y={c['bb']['y']:.0f} alt={c['alt'][:50]}")

    # Clic en el primer card (más reciente = el nuestro)
    if cards:
        first = cards[0]
        pv.mouse.click(first['bb']['x'] + first['bb']['w']/2, first['bb']['y'] + first['bb']['h']/2)
        pv.wait_for_timeout(2000)
        ss(pv, "02_card_clicked")

        # Esperar a que aparezca el player con <video>
        for _ in range(20):
            src = pv.evaluate("""
                () => {
                    const vs = document.querySelectorAll('video');
                    if (!vs.length) return null;
                    const v = vs[vs.length-1];
                    return v.src || v.currentSrc || null;
                }
            """)
            if src and len(src) > 10:
                print(f"src: {src[:80]}")
                break
            pv.wait_for_timeout(1000)
        else:
            print("No se encontró src de video — ver screenshot")
            src = None

        if src:
            print(f"Descargando...")
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
            print(f"Guardado: {OUT.name} ({size//1024}KB)")
            # Verificar duración
            dur = pv.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    return v ? v.duration : null;
                }
            """)
            print(f"Duración: {dur}s")
        ss(pv, "03_player")
