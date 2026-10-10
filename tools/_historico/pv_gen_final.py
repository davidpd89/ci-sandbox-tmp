"""
Flujo correcto PixVerse para enemies to lovers:
1. Abrir settings popup (clic en zona de duración/aspecto)
2. Clicar "10s" en el popup
3. Cerrar popup (Escape)
4. Llenar textarea con Playwright fill()
5. Clicar "Crear" por posición exacta
6. Confirmar diálogo de créditos
7. Esperar y descargar
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "Cinematic 9:16, bookstore slow burn. "
    "Shot 1: Wide — two people in library aisle apart, ignoring each other. "
    "Shot 2: Medium — both reach for the same book, fingers almost touch, they freeze. "
    "Shot 3: Close-up — one looks away quickly, subtle reaction. "
    "Shot 4: Wide — they walk away separately, each glances back at the same moment. "
    "Warm light, photorealistic, no text, no logos."
)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvf_{name}.png")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1000)

    # Cerrar cualquier popup abierto
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(500)
    ss(pv, "00_clean")

    # Verificar créditos
    creds = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos: {creds}")

    # === PASO 1: Abrir settings y cambiar a 10s ===
    print("Abriendo settings de duración...")
    # El "5s" estaba en x=686, y=902. Clicar ahí abre el settings popup.
    pv.mouse.click(686, 902)
    pv.wait_for_timeout(1200)
    ss(pv, "01_settings_open")

    # Buscar el botón "10s" en el popup que acabamos de abrir
    # De la screenshot: el popup tiene fila "4s | 6s | 8s | 10s"
    dur_10s = None
    for sel in ["button:has-text('10s')", "[class*='option']:has-text('10s')", "span:has-text('10s')"]:
        try:
            el = pv.locator(sel).first
            if el.is_visible(timeout=2000):
                print(f"  10s encontrado: {sel}")
                el.click()
                dur_10s = True
                break
        except Exception:
            pass

    if not dur_10s:
        # Buscar por posición — de la screenshot el "10s" estaba en el popup
        opts = pv.evaluate("""
            () => Array.from(document.querySelectorAll('*'))
                .filter(el => {
                    const t = (el.innerText||'').trim();
                    return t === '10s' && el.offsetParent !== null;
                })
                .map(el => {
                    const bb = el.getBoundingClientRect();
                    return {x: bb.x, y: bb.y, w: bb.width, h: bb.height};
                })
        """)
        print(f"  10s elementos: {opts}")
        for o in opts:
            if o['w'] > 0:
                pv.mouse.click(o['x'] + o['w']/2, o['y'] + o['h']/2)
                dur_10s = True
                print(f"  10s clickeado en ({o['x']:.0f}, {o['y']:.0f})")
                break

    pv.wait_for_timeout(500)
    ss(pv, "01b_dur_selected")

    # Verificar que se cambió a 10s
    btn_text = pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)
    print(f"Botón Crear: '{btn_text}'")

    # Cerrar el popup settings (Escape)
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(600)

    # === PASO 2: Llenar textarea ===
    print("\nLlenando textarea con Playwright fill()...")
    # Primero clicar en la zona del textarea
    pv.mouse.click(750, 478)  # coordenada aproximada del textarea
    pv.wait_for_timeout(300)

    # Usar Playwright fill() que maneja React inputs correctamente
    textarea = pv.locator("textarea.w-full, textarea[placeholder*='Describe'], textarea[placeholder*='Describa'], textarea[placeholder*='contenido']").first
    try:
        textarea.fill(PROMPT, force=True, timeout=5000)
        val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''")
        print(f"Fill OK: {val}")
    except Exception as e:
        print(f"fill() error: {e} — usando clipboard")
        # Fallback con clipboard
        pv.evaluate("""
            () => {
                const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea');
                if (ta) ta.focus();
            }
        """)
        pv.wait_for_timeout(200)
        pv.keyboard.press("Control+A")
        pv.evaluate("(t) => navigator.clipboard.writeText(t)", PROMPT)
        pv.wait_for_timeout(200)
        pv.keyboard.press("Control+V")
        pv.wait_for_timeout(500)
        val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''")
        print(f"Clipboard val: {val}")

    ss(pv, "02_prompt_filled")

    if not val.strip():
        print("[ERROR CRÍTICO] Textarea vacío — el método de llenado falló")
        # Último intento: type() directo
        pv.keyboard.type(PROMPT[:200], delay=5)
        pv.wait_for_timeout(500)
        val2 = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''")
        print(f"type() val: {val2}")

    # === PASO 3: Clicar Crear ===
    print("\nClicando Crear...")
    # El botón Crear estaba en x=1438, y=895 de la inspección
    # También buscar por texto
    crear_clicked = False
    for sel in ["button:has-text('Crear')", "button:has-text('Create')"]:
        try:
            btn = pv.locator(sel).last
            if btn.is_visible(timeout=2000):
                btn.click(force=True)
                crear_clicked = True
                print(f"Crear via selector: {sel}")
                break
        except Exception as e:
            pass

    if not crear_clicked:
        # Clic directo por coordenada (de inspect: x=1438, y=895)
        pv.mouse.click(1489, 902)
        crear_clicked = True
        print("Crear via coordenada (1489, 902)")

    pv.wait_for_timeout(3000)
    ss(pv, "03_after_crear")

    after_creds = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos tras Crear: {creds} → {after_creds}")

    # Confirmar diálogo de créditos si aparece
    for conf_sel in ["button:has-text('Crear')", "button:has-text('Confirmar')", "button:has-text('OK')"]:
        try:
            conf = pv.locator(conf_sel).first
            if conf.is_visible(timeout=2000):
                conf.click()
                print(f"Diálogo confirmado: {conf_sel}")
                break
        except Exception:
            pass

    # === PASO 4: Esperar generación ===
    print("\nEsperando generación...")
    start = time.time()
    gen_started = False
    while time.time() - start < 300:
        pv.wait_for_timeout(5000)
        cur_creds = pv.evaluate("""
            () => { for (const el of document.querySelectorAll('*')) {
                const t = (el.innerText||'').trim();
                if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                    const bb = el.getBoundingClientRect();
                    if (bb.x>1400 && bb.y<60) return t; }} return null; }
        """)
        # Buscar texto "bookstore" o "cinematic" en cualquier card
        new_video = pv.evaluate("""
            () => {
                const all = document.querySelectorAll('[class*="card"], [data-cy*="video"], [class*="VideoCard"]');
                for (const el of all) {
                    const t = (el.innerText||'').toLowerCase();
                    if (t.includes('bookstore') || t.includes('cinematic') || t.includes('seed') || t.includes('07-02')) {
                        const bb = el.getBoundingClientRect();
                        if (bb.y > 100 && bb.width > 150) return el.innerText.substring(0,60);
                    }
                }
                return null;
            }
        """)
        elapsed = int(time.time()-start)
        print(f"  {elapsed}s | cr={cur_creds} | new={new_video}", end="\r")
        if cur_creds and creds and int(cur_creds or 99) < int(creds or 0):
            print(f"\n  CRÉDITOS BAJARON ({creds} → {cur_creds}) — generando")
            gen_started = True
        if new_video:
            print(f"\n  NUEVO VÍDEO: {new_video[:50]}")
            break

    ss(pv, "04_after_wait")

    if not gen_started:
        final_creds = pv.evaluate("""
            () => { for (const el of document.querySelectorAll('*')) {
                const t = (el.innerText||'').trim();
                if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                    const bb = el.getBoundingClientRect();
                    if (bb.x>1400 && bb.y<60) return t; }} return null; }
        """)
        print(f"\nCréditos finales: {final_creds} — {'SE USARON' if final_creds != creds else 'SIN CAMBIO (generación no arrancó)'}")
        print("Ver screenshots pvf_* para diagnosis")
        sys.exit(1)

    # === PASO 5: Descargar ===
    # Clicar primer card (el más nuevo)
    pv.wait_for_timeout(2000)
    pv.mouse.click(374, 262)  # coordenada del primer card de la galería
    pv.wait_for_timeout(3000)
    src = None
    for _ in range(20):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10: break
        pv.wait_for_timeout(1000)

    if src:
        cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
        ua = pv.evaluate("() => navigator.userAgent")
        r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=120)
        if r.status_code == 200:
            out = OUT_DIR / "clip1.mp4"
            out.write_bytes(r.content)
            dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
            print(f"Guardado: {out.name} ({out.stat().st_size//1024}KB) dur={dur}s")
        else:
            print(f"Error descarga: {r.status_code}")
    else:
        print("No se encontró video src")

    ss(pv, "99_final")
