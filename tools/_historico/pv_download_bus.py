"""Espera y descarga el vídeo más reciente de PixVerse (la parada de bus)."""
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

    # Esperar a que el primer card no tenga "generando" en su texto
    print("Esperando que el vídeo termine de generarse...")
    start = time.time()
    while time.time() - start < 180:
        pv.wait_for_timeout(5000)
        # Verificar si el primer card ya no está generando
        first_card = pv.evaluate("""
            () => {
                const cards = Array.from(document.querySelectorAll('[class*="card"]'))
                    .filter(el => { const bb = el.getBoundingClientRect(); return bb.y > 100 && bb.width > 200; });
                if (!cards.length) return null;
                const fc = cards[0];
                return {
                    text: fc.innerText.substring(0,60),
                    generating: fc.innerText.includes('generando') || fc.innerText.includes('%'),
                    x: fc.getBoundingClientRect().x + fc.getBoundingClientRect().width/2,
                    y: fc.getBoundingClientRect().y + fc.getBoundingClientRect().height/2
                };
            }
        """)
        elapsed = int(time.time()-start)
        if first_card:
            gen = first_card.get('generating')
            print(f"  {elapsed}s | generating={gen} | text={first_card['text'][:40]}", end="\r")
            if not gen:
                print(f"\n  ¡Generación completada!")
                # Clicar el card
                pv.mouse.click(first_card['x'], first_card['y'])
                pv.wait_for_timeout(3000)
                break
        else:
            print(f"  {elapsed}s | (no cards)", end="\r")

    pv.screenshot(path="C:/Temp/bus_done.png")

    # Descargar
    src = None
    for _ in range(20):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10: break
        pv.wait_for_timeout(1000)

    if src:
        print(f"src: {src[:80]}")
        cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
        ua = pv.evaluate("() => navigator.userAgent")
        r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
        if r.status_code == 200 and len(r.content) > 50000:
            OUT.write_bytes(r.content)
            dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
            print(f"✓ {OUT.name} ({OUT.stat().st_size//1024}KB) dur={dur}s")

            # Verificar que no es un vídeo anterior
            creds_final = pv.evaluate("""
                () => { for (const el of document.querySelectorAll('*')) {
                    const t = (el.innerText||'').trim();
                    if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                        const bb = el.getBoundingClientRect();
                        if (bb.x>1400 && bb.y<60) return t; }} return null; }
            """)
            print(f"Créditos finales: {creds_final}")
        else:
            print(f"Error: {r.status_code}")
    else:
        print("No src — verificar screenshot C:/Temp/bus_done.png")
