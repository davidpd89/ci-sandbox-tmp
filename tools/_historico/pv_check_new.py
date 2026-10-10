"""Toma screenshot de PixVerse y verifica si hay un vídeo nuevo de enemies to lovers."""
import sys, io, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    ctx = b.contexts[0]
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1500)
    pv.screenshot(path="C:/Temp/pv_new_check.png")

    # Créditos restantes
    credits = pv.evaluate("""
        () => {
            const els = document.querySelectorAll('*');
            for (const el of els) {
                const t = (el.innerText || '').trim();
                if (/^\d+$/.test(t) && parseInt(t) >= 0 && parseInt(t) <= 200) {
                    const bb = el.getBoundingClientRect();
                    if (bb.x > 1400 && bb.y < 60) return t;
                }
            }
            return null;
        }
    """)
    print(f"Créditos: {credits}")

    # Buscar el vídeo más reciente con prompt de librería/tensión
    # Buscar tarjetas con texto que indique el prompt de enemies
    recent_cards = pv.evaluate("""
        () => {
            const cards = Array.from(document.querySelectorAll('[class*="card"], [class*="item"]'));
            return cards
                .filter(el => {
                    const bb = el.getBoundingClientRect();
                    return bb.width > 150 && bb.height > 100 && bb.y > 50 && bb.y < 500;
                })
                .slice(0, 8)
                .map(el => ({
                    text: el.innerText.substring(0, 80),
                    x: el.getBoundingClientRect().x,
                    y: el.getBoundingClientRect().y,
                    w: el.getBoundingClientRect().width,
                    h: el.getBoundingClientRect().height
                }));
        }
    """)
    print(f"\nCards visibles: {len(recent_cards)}")
    for c in recent_cards[:8]:
        print(f"  x={c['x']:.0f} y={c['y']:.0f} text={c['text'][:60]}")

    # ¿El primer card es enemies to lovers (distinto de resaca de libro)?
    if recent_cards:
        fc = recent_cards[0]
        print(f"\nPrimer card: {fc['text'][:80]}")
        is_new = "young woman" not in fc['text'].lower() and "couch" not in fc['text'].lower()
        print(f"¿Es nuevo (no resaca)? {is_new}")

        if is_new:
            print("Descargando vídeo nuevo...")
            pv.mouse.click(fc['x'] + fc['w']/2, fc['y'] + fc['h']/2)
            pv.wait_for_timeout(3000)
            src = None
            for _ in range(15):
                src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
                if src and len(src) > 10: break
                pv.wait_for_timeout(1000)
            if src:
                print(f"src: {src[:80]}")
                cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
                ua = pv.evaluate("() => navigator.userAgent")
                r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=60)
                if r.status_code == 200:
                    out = OUT_DIR / "clip1.mp4"
                    out.write_bytes(r.content)
                    print(f"Guardado: {out.name} ({out.stat().st_size//1024}KB)")
                    # Verificar duración
                    dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
                    print(f"Duración: {dur}s")
