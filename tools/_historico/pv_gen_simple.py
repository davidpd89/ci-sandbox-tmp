"""
Genera el vídeo enemies to lovers con EXACTAMENTE el mismo método que funcionó
para la resaca de libro (clip1.mp4 = 215KB descargado con éxito).
JS focus → Ctrl+A → clipboard → Ctrl+V → Enter → confirmar → esperar → descargar.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Prompt compacto — si el textarea tiene límite de chars
PROMPT = (
    "Cinematic 9:16, bookstore slow burn tension. "
    "Shot 1: Wide — two people in same library aisle, standing far apart, ignoring each other. "
    "Shot 2: Medium — both reach for the same book, fingers almost touch, they freeze, lock eyes. "
    "Shot 3: Close-up — one looks away quickly, tries to hide a reaction, subtle almost-smile. "
    "Shot 4: Wide — they walk away in opposite directions, each glances back at the same moment. "
    "Warm natural light, photorealistic, no text, no logos, 9:16 vertical."
)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvs_{name}.png")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    pv = next(pg for pg in [x for c in b.contexts for x in c.pages] if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1000)
    ss(pv, "00_state")

    # Verificar créditos
    creds = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos: {creds}")

    # Intentar cambiar a 10s: clic en la zona del "5s" y luego seleccionar 10s
    print("Intentando cambiar duración a 10s...")
    pv.mouse.click(686, 902)  # coordenada del "5s" de la inspección
    pv.wait_for_timeout(1200)
    ss(pv, "01_dropdown")

    # Buscar y clicar "10s"
    clicked_10s = False
    for sel in ["span:has-text('10s')", "[class*='option']:has-text('10s')", "div:has-text('10s')", "li:has-text('10s')"]:
        try:
            el = pv.locator(sel).first
            if el.is_visible(timeout=1000):
                el.click(force=True)
                clicked_10s = True
                print("10s seleccionado")
                break
        except Exception:
            pass

    if not clicked_10s:
        # Leer qué opciones están visibles
        opts = pv.evaluate("""
            () => Array.from(document.querySelectorAll('*'))
                .filter(el => {
                    const t = (el.innerText||'').trim();
                    return (t==='5s'||t==='8s'||t==='10s'||t==='15s') && el.offsetParent!==null;
                })
                .map(el => ({t: el.innerText.trim(), x: el.getBoundingClientRect().x, y: el.getBoundingClientRect().y}))
        """)
        print(f"Opciones de duración visibles: {opts}")
        for o in opts:
            if o['t'] == '10s':
                pv.mouse.click(o['x'] + 5, o['y'] + 5)
                clicked_10s = True
                print(f"10s clickeado en ({o['x']}, {o['y']})")
                break

    pv.wait_for_timeout(500)
    btn = pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)
    print(f"Botón ahora: '{btn}' {'← 10s OK!' if '40' in (btn or '') else '← sigue 5s' if '20' in (btn or '') else ''}")

    # === MÉTODO EXACTO QUE FUNCIONÓ ===
    # 1. JS focus
    pv.evaluate("""
        () => {
            const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea');
            if (ta) ta.focus();
        }
    """)
    pv.wait_for_timeout(300)
    # 2. Ctrl+A para limpiar
    pv.keyboard.press("Control+A")
    # 3. Poner en clipboard
    pv.evaluate("(t) => navigator.clipboard.writeText(t)", PROMPT)
    pv.wait_for_timeout(200)
    # 4. Ctrl+V para pegar
    pv.keyboard.press("Control+V")
    pv.wait_for_timeout(1000)

    val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''")
    print(f"Texto en textarea: {val}")
    ss(pv, "02_prompt")

    if not val.strip():
        print("[ERROR] Textarea vacío — abortando")
        sys.exit(1)

    # 5. Enter para enviar
    before_creds = creds
    pv.keyboard.press("Enter")
    print("Enter pulsado")
    pv.wait_for_timeout(3000)
    ss(pv, "03_after_enter")

    # 6. Confirmar el diálogo de coste si aparece
    for sel in ["button:has-text('Crear')", "button:has-text('Confirmar')", "button:has-text('Aceptar')", "button:has-text('OK')"]:
        try:
            btn_el = pv.locator(sel).first
            if btn_el.is_visible(timeout=2000):
                btn_el.click()
                print(f"Confirmado: {sel}")
                break
        except Exception:
            pass

    pv.wait_for_timeout(2000)
    after_creds = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos: {before_creds} → {after_creds}")

    if after_creds == before_creds:
        print("[WARN] Créditos no bajaron — posible error")
        ss(pv, "03b_no_change")

    # 7. Esperar generación
    print("Esperando generación (4 min)...")
    start = time.time()
    while time.time() - start < 240:
        pv.wait_for_timeout(5000)
        cur_creds = pv.evaluate("""
            () => { for (const el of document.querySelectorAll('*')) {
                const t = (el.innerText||'').trim();
                if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                    const bb = el.getBoundingClientRect();
                    if (bb.x>1400 && bb.y<60) return t; }} return null; }
        """)
        elapsed = int(time.time()-start)
        # Buscar primer card con texto nuevo (no "young woman lies on a couch")
        first = pv.evaluate("""
            () => {
                const cards = Array.from(document.querySelectorAll('[class*="card"]'))
                    .filter(el => { const bb = el.getBoundingClientRect();
                        return bb.y > 100 && bb.width > 150 && bb.height > 100; });
                return cards.length > 0 ? cards[0].innerText.substring(0,60) : '?';
            }
        """)
        print(f"  {elapsed}s | cr={cur_creds} | first={first[:40]}", end="\r")
        if first and first != '?' and "young woman lies on a couch" not in first:
            print(f"\n  NUEVO VÍDEO DETECTADO: {first[:50]}")
            break
        if cur_creds and before_creds and int(cur_creds or 99) < int(before_creds or 0):
            print(f"\n  Créditos bajaron → generando")

    ss(pv, "04_after_wait")

    # 8. Descargar el primer card
    all_cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"]'))
            .filter(el => { const bb = el.getBoundingClientRect();
                return bb.y > 100 && bb.width > 200 && bb.height > 100; })
            .slice(0,3)
            .map(el => ({
                text: el.innerText.substring(0,60),
                x: el.getBoundingClientRect().x + el.getBoundingClientRect().width/2,
                y: el.getBoundingClientRect().y + el.getBoundingClientRect().height/2
            }))
    """)
    print(f"\nCards: {[c['text'][:30] for c in all_cards]}")

    if all_cards:
        fc = all_cards[0]
        pv.mouse.click(fc['x'], fc['y'])
        pv.wait_for_timeout(3000)
        src = None
        for _ in range(15):
            src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
            if src and len(src) > 10: break
            pv.wait_for_timeout(1000)

        if src:
            cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
            ua = pv.evaluate("() => navigator.userAgent")
            r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
            if r.status_code == 200:
                out = OUT_DIR / "clip1.mp4"
                out.write_bytes(r.content)
                dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
                print(f"Guardado: clip1.mp4 ({out.stat().st_size//1024}KB) dur={dur}s")
            else:
                print(f"Error descarga: {r.status_code}")
        else:
            print("[WARN] No se encontró video src")

    final_creds = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"\nCréditos finales: {final_creds}")
    ss(pv, "99_final")
