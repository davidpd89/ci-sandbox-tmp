"""
DP-F0-075: "Olvidé la trama. Recuerdo aquella versión mía."
- 4s en PixVerse (16cr, gratis, sin paywall de 10s)
- Flujo EXACTO que funcionó para resaca: settings popup → 4s → focus → type → Enter → confirmar
- 3 líneas × ~1.7s = 5s → regla 2s cumplida
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\06-olvide-la-trama")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Prompt en inglés para PixVerse (funciona mejor)
PROMPT = (
    "Cinematic 9:16 vertical video, 5 seconds, photorealistic. "
    "A woman in her 30s sits at night in a cozy room, warm lamp light, "
    "holding an old worn paperback book (no visible title or text). "
    "Bookshelf behind her, blanket, cup nearby, dark window with subtle reflection. "
    "She opens the book slowly and looks at a page with quiet nostalgic surprise. "
    "In the window glass, for a brief moment, appears a faint reflection of her "
    "teenage self, like a memory, not a ghost. She doesn't react with fear, "
    "just pauses and touches the page softly. Close shot, slow movement, warm light, "
    "very emotional and human. No portals, no magic worlds, no text on screen, no logos."
)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvj_{name}.png")

def get_creds(pv):
    return pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)

def get_btn(pv):
    return pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(500)
    ss(pv, "00_start")

    creds = get_creds(pv)
    btn = get_btn(pv)
    print(f"Estado inicial: cr={creds} btn='{btn}'")

    # === PASO 1: Abrir settings popup y seleccionar 4s ===
    print("\nPASO 1: Abrir popup de duración...")
    # El popup se abre haciendo Enter en el textarea vacío (confirmado en pvs_03_after_enter.png)
    pv.evaluate("() => { const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea'); if(ta) ta.focus(); }")
    pv.wait_for_timeout(300)
    pv.keyboard.press("Control+A")
    pv.keyboard.press("Delete")
    pv.wait_for_timeout(200)
    pv.keyboard.press("Enter")  # Abre el settings popup
    pv.wait_for_timeout(1500)
    ss(pv, "01_popup_open")

    # Buscar y clicar 4s en el popup
    clicked = False
    for sel in ["span:has-text('4s')", "button:has-text('4s')", "div:has-text('4s')", "[class*='option']:has-text('4s')"]:
        try:
            el = pv.locator(sel).first
            if el.is_visible(timeout=1500):
                el.click()
                clicked = True
                print(f"  4s clickeado: {sel}")
                break
        except Exception:
            pass

    if not clicked:
        # Buscar por posición
        opts = pv.evaluate("""
            () => Array.from(document.querySelectorAll('*'))
                .filter(el => (el.innerText||'').trim() === '4s' && el.offsetParent !== null)
                .map(el => { const bb = el.getBoundingClientRect(); return {x:bb.x+bb.width/2,y:bb.y+bb.height/2,w:bb.width}; })
        """)
        print(f"  4s por posición: {opts}")
        for o in opts:
            if o['w'] > 0:
                pv.mouse.click(o['x'], o['y'])
                clicked = True
                print(f"  4s clickeado en ({o['x']:.0f},{o['y']:.0f})")
                break

    pv.wait_for_timeout(500)
    # Cerrar popup con Escape
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(500)
    ss(pv, "01b_after_4s")

    btn_after = get_btn(pv)
    print(f"Botón ahora: '{btn_after}' (esperado: Crear 16)")

    # === PASO 2: Escribir prompt con type() ===
    print("\nPASO 2: Escribir prompt...")
    pv.evaluate("() => { const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea'); if(ta) ta.focus(); }")
    pv.wait_for_timeout(300)
    pv.keyboard.press("Control+A")
    pv.keyboard.press("Delete")
    pv.wait_for_timeout(200)
    pv.keyboard.type(PROMPT, delay=8)
    pv.wait_for_timeout(500)

    val = pv.evaluate("() => (document.querySelector('textarea.w-full')||document.querySelector('textarea'))?.value?.substring(0,60)||''")
    print(f"Prompt en textarea: {val}")
    ss(pv, "02_prompt_filled")

    if not val.strip():
        print("[WARN] textarea parece vacío según .value, pero puede estar en React state")
        print("  Continuando de todas formas (el texto puede estar visualmente ahí)")

    # === PASO 3: Enter para enviar (mismo método que funcionó con resaca) ===
    creds_before = get_creds(pv)
    print(f"\nPASO 3: Enter para enviar (cr={creds_before})...")
    pv.keyboard.press("Enter")
    pv.wait_for_timeout(3000)
    ss(pv, "03_after_enter")

    creds_after_enter = get_creds(pv)
    print(f"Créditos: {creds_before} → {creds_after_enter}")

    # Buscar y confirmar el diálogo de confirmación de créditos
    print("Buscando diálogo de confirmación...")
    confirmed = False
    for sel in ["button:has-text('Crear')", "button:has-text('Confirmar')", "button:has-text('Aceptar')", "button:has-text('OK')"]:
        try:
            conf = pv.locator(sel).first
            if conf.is_visible(timeout=2000):
                print(f"  Confirmando: {sel}")
                conf.click()
                confirmed = True
                break
        except Exception:
            pass

    if not confirmed:
        print("  No apareció diálogo de confirmación")

    pv.wait_for_timeout(2000)
    ss(pv, "03b_after_confirm")
    creds_after_confirm = get_creds(pv)
    print(f"Créditos post-confirm: {creds_before} → {creds_after_confirm}")

    if creds_after_confirm == creds_before:
        print("[WARN] Créditos no bajaron — revisar screenshot 03b_after_confirm")

    # === PASO 4: Esperar generación ===
    print("\nPASO 4: Esperando generación (3 min)...")
    start = time.time()
    while time.time() - start < 180:
        pv.wait_for_timeout(5000)
        cur = get_creds(pv)
        elapsed = int(time.time()-start)
        print(f"  {elapsed}s cr={cur}", end="\r")
        if cur and creds_before and int(cur) < int(creds_before):
            print(f"\n  Créditos bajaron ({creds_before}→{cur}) — generando")
            break
    print()
    ss(pv, "04_after_wait")

    # === PASO 5: Descargar ===
    print("PASO 5: Descargando...")
    # Clicar primer card
    cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"]'))
            .filter(el => { const bb = el.getBoundingClientRect(); return bb.y > 100 && bb.width > 200; })
            .map(el => ({x: el.getBoundingClientRect().x+el.getBoundingClientRect().width/2,
                         y: el.getBoundingClientRect().y+el.getBoundingClientRect().height/2,
                         text: el.innerText.substring(0,40)}))
    """)
    if not cards:
        print("  No se encontraron cards")
    else:
        print(f"  Clic en: {cards[0]['text'][:30]}")
        pv.mouse.click(cards[0]['x'], cards[0]['y'])
        pv.wait_for_timeout(3000)

    src = None
    for _ in range(20):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10: break
        pv.wait_for_timeout(1000)

    final_creds = get_creds(pv)
    print(f"\nCréditos finales: {final_creds} (antes={creds_before})")

    if src:
        print(f"src: {src[:80]}")
        cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
        ua = pv.evaluate("() => navigator.userAgent")
        r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
        if r.status_code == 200 and len(r.content) > 50000:
            out = OUT_DIR / "clip1.mp4"
            out.write_bytes(r.content)
            dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
            print(f"✓ clip1.mp4 ({out.stat().st_size//1024}KB) dur={dur}s")
        else:
            print(f"  Error descarga: status={r.status_code} size={len(r.content)//1024}KB")
    else:
        print("  No se encontró video src — verificar screenshots pvj_*")

    ss(pv, "99_final")
