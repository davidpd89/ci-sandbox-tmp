"""
DP-F0-076: "No fue el beso. Fue que apartó el vaso roto."
6s × 4cr = 24cr (todos los restantes). Multi-Toma ON.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\08-gesto-minimo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "9:16 vertical video, 6 seconds, cinematic photorealism. "
    "Two people in a cozy apartment living room at night, warm lamp light. "
    "One person is walking past when they casually notice a broken glass on the floor "
    "in the exact path where the other person is about to step. "
    "Without making a big deal of it, without saying anything, "
    "they quietly and quickly move it out of the way. "
    "The other person never even notices. "
    "Multi-shot: close-up of the glass on floor, hand moving it aside, "
    "wide shot showing both people continuing naturally as if nothing happened. "
    "Intimate, subtle, warm, realistic human behavior. "
    "No dramatic music cues in the visual, no text, no logos, 9:16."
)

def ss(pv, name):
    pv.screenshot(path=f"C:/Temp/pgm_{name}.png")

def get_creds(pv):
    return pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)

def popup_open(pv):
    return pv.evaluate("""
        () => !!Array.from(document.querySelectorAll('*')).find(
            e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'))
    """)

def close_x(pv):
    for x, y in [(1028, 96), (1030, 93), (1025, 98)]:
        pv.mouse.click(x, y)
        pv.wait_for_timeout(400)
        if not popup_open(pv):
            print(f"  X cerrado en ({x},{y})")
            return True
    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()

    if popup_open(pv):
        close_x(pv)
    pv.wait_for_timeout(500)

    creds = get_creds(pv)
    print(f"Créditos: {creds}")
    ss(pv, "00")

    # === Abrir settings y seleccionar 6s ===
    print("Abriendo settings → 6s...")
    # El textarea vacío + Enter abre el settings popup
    pv.evaluate("() => { const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea'); if(ta) { ta.focus(); ta.value = ''; } }")
    pv.wait_for_timeout(200)
    pv.keyboard.press("Control+A")
    pv.keyboard.press("Delete")
    pv.wait_for_timeout(200)
    pv.keyboard.press("Enter")  # Abre el settings popup
    pv.wait_for_timeout(1500)
    ss(pv, "01_popup")

    # Clicar 6s
    clicked = False
    for sel in ["span:has-text('6s')", "button:has-text('6s')", "div:has-text('6s')"]:
        try:
            el = pv.locator(sel).first
            if el.is_visible(timeout=1200):
                el.click()
                clicked = True
                print(f"  6s: {sel}")
                break
        except Exception:
            pass
    if not clicked:
        opts = pv.evaluate("""
            () => Array.from(document.querySelectorAll('*'))
                .filter(el => (el.innerText||'').trim() === '6s' && el.offsetParent)
                .map(el => { const bb = el.getBoundingClientRect(); return {x:bb.x+bb.width/2,y:bb.y+bb.height/2,w:bb.width}; })
        """)
        for o in opts:
            if o['w'] > 0:
                pv.mouse.click(o['x'], o['y'])
                clicked = True
                print(f"  6s coord ({o['x']:.0f},{o['y']:.0f})")
                break

    pv.wait_for_timeout(400)
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(400)

    btn = pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)
    print(f"Botón: '{btn}' (esperado: Crear 24)")

    # === Escribir prompt con mouse.click en textarea ===
    ta_info = pv.evaluate("""
        () => {
            const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea[placeholder*="Describ"]') || document.querySelector('textarea');
            if (!ta) return null;
            const bb = ta.getBoundingClientRect();
            return {x: bb.x + bb.width/2, y: bb.y + bb.height/2};
        }
    """)
    if ta_info:
        pv.mouse.click(ta_info['x'], ta_info['y'])
        pv.wait_for_timeout(300)
        pv.keyboard.press("Control+A")
        pv.keyboard.press("Delete")
        pv.wait_for_timeout(200)
        pv.keyboard.type(PROMPT, delay=7)
        pv.wait_for_timeout(500)
    ss(pv, "02_prompt")

    # === Clicar Crear por coordenadas ===
    crear_info = pv.evaluate("""
        () => {
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(b => /crear|create/i.test(b.innerText) && b.offsetParent);
            if (!b) return null;
            const bb = b.getBoundingClientRect();
            return {x: bb.x + bb.width/2, y: bb.y + bb.height/2, text: b.innerText.trim()};
        }
    """)
    print(f"Crear: {crear_info}")

    creds_before = get_creds(pv)
    if crear_info:
        pv.mouse.click(crear_info['x'], crear_info['y'])
    else:
        pv.mouse.click(1492, 911)
    pv.wait_for_timeout(3000)
    ss(pv, "03_after_crear")

    # Cerrar popup X si aparece
    if popup_open(pv):
        print("Popup → cerrando X...")
        ss(pv, "03b_popup")
        close_x(pv)
        pv.wait_for_timeout(500)

    creds_after = get_creds(pv)
    print(f"Créditos: {creds_before} → {creds_after}")

    if creds_after != creds_before:
        print("¡Generando!")
    else:
        print("[WARN] Créditos no bajaron")

    # === Esperar ===
    print("Esperando generación (3 min)...")
    start = time.time()
    while time.time() - start < 180:
        pv.wait_for_timeout(5000)
        cur = get_creds(pv)
        elapsed = int(time.time()-start)
        print(f"  {elapsed}s cr={cur}", end="\r")
        if cur and creds_before and int(cur or 99) < int(creds_before or 0):
            print(f"\n  Generando (cr bajó)")
            break
    print()
    ss(pv, "04_wait")
    print(f"Créditos finales: {get_creds(pv)}")

    # === Descargar ===
    print("Descargando...")
    pv.mouse.click(305, 285)
    pv.wait_for_timeout(3000)

    src = None
    for _ in range(20):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10: break
        pv.wait_for_timeout(1000)

    if src and src != "https://media.pixverse.ai/pixverse%2Fmp4%2Fmedia%2Fweb%2Fori%2F1d96a74a-e833-499":
        cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
        ua = pv.evaluate("() => navigator.userAgent")
        r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
        out = OUT_DIR / "clip1.mp4"
        if r.status_code == 200 and len(r.content) > 50000:
            out.write_bytes(r.content)
            dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
            print(f"✓ {out.name} ({out.stat().st_size//1024}KB) {dur}s")
        else:
            print(f"Error: {r.status_code} {len(r.content)//1024}KB")
    elif src:
        print(f"src parece ser un vídeo anterior: {src[:60]}")
    else:
        print("No src")

    ss(pv, "99")
