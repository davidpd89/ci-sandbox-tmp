"""
Solución definitiva para React textarea de PixVerse.
Usa keyboard.type() que dispara eventos React por cada tecla (onChange).
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Prompt corto para que type() sea rápido
PROMPT = (
    "Cinematic 9:16 bookstore slow burn. "
    "Shot 1: Wide, two people apart in library aisle ignoring each other. "
    "Shot 2: Both reach for same book, hands almost touch, they freeze and lock eyes. "
    "Shot 3: Close-up, one looks away hiding emotion. "
    "Shot 4: Wide, they walk away separately but glance back at the same moment. "
    "Warm light, photorealistic, no text, no logos."
)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvt_{name}.png")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(500)

    # Cerrar todo
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(500)

    creds = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos: {creds}")

    # === 1. Cambiar a 10s ===
    pv.mouse.click(686, 902)
    pv.wait_for_timeout(1200)
    # Buscar y clicar 10s
    for sel in ["span:has-text('10s')", "button:has-text('10s')", "[class*='option']:has-text('10s')"]:
        try:
            el = pv.locator(sel).first
            if el.is_visible(timeout=1500):
                el.click(); print("10s OK"); break
        except Exception: pass
    pv.wait_for_timeout(400)
    btn = pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)
    print(f"Botón: '{btn}'")
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(400)

    # === 2. Foco en textarea via JS (sin click para evitar overlay) ===
    pv.evaluate("""
        () => {
            const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea');
            if (ta) ta.focus();
        }
    """)
    pv.wait_for_timeout(300)

    # Limpiar contenido existente
    pv.keyboard.press("Control+A")
    pv.keyboard.press("Delete")
    pv.wait_for_timeout(200)

    # === 3. type() caracter a caracter (dispara onChange React) ===
    print(f"Escribiendo prompt ({len(PROMPT)} chars) con type()...")
    pv.keyboard.type(PROMPT, delay=8)  # 8ms/char ≈ 1.5s total
    pv.wait_for_timeout(500)

    val = pv.evaluate("""
        () => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,70) || ''
    """)
    print(f"Texto en textarea: {val}")
    ss(pv, "01_prompt")

    if not val.strip():
        print("[ERROR] Textarea vacío incluso con type()")
        sys.exit(1)

    # === 4. Clicar Crear ===
    print("Clicando Crear...")
    crear = pv.locator("button:has-text('Crear'), button:has-text('Create')").last
    crear.click(force=True)
    pv.wait_for_timeout(2500)
    ss(pv, "02_after_crear")

    after_creds = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos: {creds} → {after_creds}")

    # Confirmar diálogo si aparece (busca "Crear" en un popup, no el botón principal)
    popups = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[role="dialog"] button, [class*="modal"] button, [class*="popup"] button'))
            .filter(b => b.offsetParent)
            .map(b => b.innerText.trim().substring(0,30))
    """)
    print(f"Botones en popup: {popups}")
    for popup_btn_text in ["Crear", "Confirmar", "OK", "Aceptar", "Continuar"]:
        try:
            popup_btn = pv.locator(f"[role='dialog'] button:has-text('{popup_btn_text}')").first
            if popup_btn.is_visible(timeout=1500):
                popup_btn.click()
                print(f"Popup confirmado: '{popup_btn_text}'")
                break
        except Exception: pass

    pv.wait_for_timeout(2000)
    ss(pv, "03_after_confirm")
    creds_after_confirm = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos post-confirmación: {creds_after_confirm}")

    # === 5. Esperar generación ===
    print("Esperando generación...")
    start = time.time()
    while time.time() - start < 300:
        pv.wait_for_timeout(5000)
        cur_creds = pv.evaluate("""
            () => { for (const el of document.querySelectorAll('*')) {
                const t = (el.innerText||'').trim();
                if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                    const bb = el.getBoundingClientRect();
                    if (bb.x>1400 && bb.y<60) return t; }} return null; }
        """)
        elapsed = int(time.time()-start)
        print(f"  {elapsed}s | cr={cur_creds}", end="\r")
        if cur_creds and creds and int(cur_creds or 99) < int(creds or 0):
            print(f"\n  CRÉDITOS BAJARON → generando")
            break

    ss(pv, "04_wait")
    # Esperar más si está generando
    pv.wait_for_timeout(30000)  # 30s más para que termine

    # === 6. Descargar ===
    # Clicar primer card
    pv.mouse.click(374, 262)
    pv.wait_for_timeout(3000)
    src = None
    for _ in range(20):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10: break
        pv.wait_for_timeout(1000)

    final_creds = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"\nCréditos finales: {final_creds} (antes={creds})")

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
