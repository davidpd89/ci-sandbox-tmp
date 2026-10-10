"""
1. Cierra popup con X (1028, 96)
2. Lee el prompt que ya hay en la textarea
3. Confirma 4s/16cr
4. Crea video
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

def ss(pv, name):
    pv.screenshot(path=f"C:/Temp/xcl_{name}.png")

def get_creds(pv):
    return pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    ctx = b.contexts[0]
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(500)

    print(f"Créditos: {get_creds(pv)}")
    ss(pv, "00_state")

    # Cerrar popup con la X visible en (1028, 96)
    has_popup = pv.evaluate("""
        () => !!Array.from(document.querySelectorAll('*')).find(
            e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'))
    """)
    print(f"Popup abierto: {has_popup}")

    if has_popup:
        print("Cerrando popup con X en (1028, 96)...")
        pv.mouse.click(1028, 96)
        pv.wait_for_timeout(1000)
        ss(pv, "01_after_x")

        still_open = pv.evaluate("""
            () => !!Array.from(document.querySelectorAll('*')).find(
                e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'))
        """)
        print(f"Popup sigue: {still_open}")
        if still_open:
            # Probar un poco a la derecha/arriba
            for x, y in [(1030, 93), (1025, 98), (1033, 91)]:
                pv.mouse.click(x, y)
                pv.wait_for_timeout(400)
                if not pv.evaluate("""
                    () => !!Array.from(document.querySelectorAll('*')).find(
                        e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'))
                """):
                    print(f"  Cerrado con ({x},{y})")
                    break

    ss(pv, "02_popup_closed")
    print(f"Créditos: {get_creds(pv)}")

    # Leer el prompt que ya hay (de intento anterior)
    current_val = pv.evaluate("""
        () => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value || ''
    """)
    print(f"Prompt actual: {current_val[:80]}")

    # Verificar botón Crear
    btn = pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)
    print(f"Botón: '{btn}'")

    if current_val.strip():
        print("\nHay prompt — clicando Crear directamente...")
        creds_before = get_creds(pv)
        pv.mouse.click(1492, 911)  # Coordenadas exactas del Crear 16
        pv.wait_for_timeout(3000)
        ss(pv, "03_after_crear")

        # Si popup vuelve a aparecer → cerrar con X
        if pv.evaluate("""
            () => !!Array.from(document.querySelectorAll('*')).find(
                e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'))
        """):
            print("Popup volvió — cerrando X (1028, 96)...")
            pv.mouse.click(1028, 96)
            pv.wait_for_timeout(500)

        creds_after = get_creds(pv)
        print(f"Créditos: {creds_before} → {creds_after}")

        if creds_after != creds_before:
            print("¡GENERANDO!")
            for i in range(36):
                pv.wait_for_timeout(5000)
                cur = get_creds(pv)
                print(f"  {(i+1)*5}s cr={cur}", end="\r")
            print()

            # Descargar
            cards = pv.evaluate("""
                () => Array.from(document.querySelectorAll('[class*="card"]'))
                    .filter(el => { const bb = el.getBoundingClientRect(); return bb.y > 100 && bb.width > 200; })
                    .map(el => ({x: el.getBoundingClientRect().x+el.getBoundingClientRect().width/2,
                                 y: el.getBoundingClientRect().y+el.getBoundingClientRect().height/2,
                                 text: el.innerText.substring(0,40)}))
            """)
            if cards:
                pv.mouse.click(cards[0]['x'], cards[0]['y'])
                pv.wait_for_timeout(3000)
                src = None
                for _ in range(20):
                    src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
                    if src and len(src) > 10: break
                    pv.wait_for_timeout(1000)
                if src:
                    cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
                    ua = pv.evaluate("() => navigator.userAgent")
                    r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
                    if r.status_code == 200 and len(r.content) > 50000:
                        out = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\06-olvide-la-trama") / "clip1.mp4"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(r.content)
                        dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
                        print(f"✓ {out.name} ({out.stat().st_size//1024}KB) dur={dur}s")
        else:
            print("Créditos no bajaron")
    else:
        print("Textarea vacío — necesita prompt")

    ss(pv, "99_final")
    print(f"Créditos finales: {get_creds(pv)}")
