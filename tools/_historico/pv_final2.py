"""
ÚLTIMO INTENTO: seleccionar 4s del popup (16cr×2=32cr<40cr), locator.type() para textarea.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLIPS = [
    ("clip1.mp4", "Two young people in a bookstore aisle, each reading separate books, ignoring each other. Tense. Warm library light. 9:16 vertical, photorealistic, no text."),
    ("clip2.mp4", "Close-up two hands reaching for the same book on a shelf, fingers almost touching. One person looks up at the other surprised, then quickly looks away. 9:16, cinematic, photorealistic, no text."),
]

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvf2_{name}.png")

def get_creds(pv):
    return pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)

def select_4s_from_popup(pv):
    """Abre el popup de duración y selecciona 4s."""
    pv.keyboard.press("Escape"); pv.wait_for_timeout(400)
    # Clic en la zona de duración (abre el popup)
    pv.mouse.click(686, 902)
    pv.wait_for_timeout(1500)
    ss(pv, "popup")
    # Buscar y clicar 4s
    for sel in ["span:has-text('4s')", "button:has-text('4s')", "[class*='option']:has-text('4s')", "div:has-text('4s')"]:
        try:
            el = pv.locator(sel).first
            if el.is_visible(timeout=1200):
                el.click(); pv.wait_for_timeout(500); pv.keyboard.press("Escape"); pv.wait_for_timeout(400)
                btn = pv.evaluate("""() => { const bs = document.querySelectorAll('button');
                    for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
                    return null; }""")
                print(f"  4s seleccionado. Botón: '{btn}'")
                return True
        except Exception: pass
    # Si no hay 4s, buscar por coordenadas después del popup
    opts = pv.evaluate("""
        () => Array.from(document.querySelectorAll('*'))
            .filter(el => (el.innerText||'').trim() === '4s' && el.offsetParent)
            .map(el => {const bb=el.getBoundingClientRect(); return {x:bb.x,y:bb.y,w:bb.width,h:bb.height};})
    """)
    if opts:
        o = opts[0]
        pv.mouse.click(o['x']+o['w']/2, o['y']+o['h']/2)
        pv.wait_for_timeout(500); pv.keyboard.press("Escape"); pv.wait_for_timeout(400)
        return True
    pv.keyboard.press("Escape"); pv.wait_for_timeout(400)
    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1000)
    print(f"URL: {pv.url}")

    # Ir a /creation/video si no estamos
    if "creation" not in pv.url:
        pv.goto("https://app.pixverse.ai/creation/video")
        pv.wait_for_load_state("networkidle", timeout=20000)
        pv.wait_for_timeout(3000)

    print(f"Créditos: {get_creds(pv)}")
    ss(pv, "00_start")

    for clip_name, prompt in CLIPS:
        out = OUT_DIR / clip_name
        if out.exists() and out.stat().st_size > 100000:
            print(f"\n{clip_name}: ya existe"); continue

        print(f"\n=== {clip_name} ===")

        # Cambiar a 4s
        print("Seleccionando 4s...")
        select_4s_from_popup(pv)

        # Textarea via locator.type() — maneja focus automáticamente
        print("Escribiendo prompt via locator.type()...")
        ta_loc = pv.locator("textarea.w-full").first
        try:
            ta_loc.clear(timeout=3000)
        except Exception:
            try:
                pv.evaluate("() => { const ta = document.querySelector('textarea.w-full'); if(ta){ta.focus(); ta.value='';} }")
            except Exception:
                pass
        pv.wait_for_timeout(200)

        # Type con locator (no necesita click separado, gestiona su propio focus)
        try:
            ta_loc.type(prompt, delay=8, timeout=30000)
        except Exception as e:
            print(f"locator.type error: {e}")
            # Fallback: JS focus + keyboard.type
            pv.evaluate("() => { const ta = document.querySelector('textarea.w-full'); if(ta) ta.focus(); }")
            pv.wait_for_timeout(200)
            pv.keyboard.press("Control+A")
            pv.keyboard.press("Delete")
            pv.wait_for_timeout(100)
            pv.keyboard.type(prompt, delay=8)

        pv.wait_for_timeout(400)
        val = pv.evaluate("() => document.querySelector('textarea.w-full')?.value?.substring(0,60) || ''")
        print(f"Prompt: {val}")
        ss(pv, f"{clip_name}_p")

        if not val.strip():
            print("[ERROR] Textarea vacío — abortando este clip"); continue

        creds_before = get_creds(pv)
        btn_text = pv.evaluate("""() => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }""")
        print(f"Antes: cr={creds_before} btn='{btn_text}'")

        # Click Crear
        pv.locator("button:has-text('Crear'), button:has-text('Create')").last.click(force=True)
        pv.wait_for_timeout(3000)
        ss(pv, f"{clip_name}_c")

        creds_after = get_creds(pv)
        print(f"Créditos: {creds_before} → {creds_after}")

        if creds_after == creds_before:
            print("[WARN] Créditos no cambiaron")
            pv.keyboard.press("Escape"); pv.wait_for_timeout(500)
            continue

        # Esperar generación
        print("Generando...")
        start = time.time()
        while time.time() - start < 120:
            pv.wait_for_timeout(5000)
            print(f"  {int(time.time()-start)}s", end="\r")
        print()

        # Descargar
        cards = pv.evaluate("""
            () => Array.from(document.querySelectorAll('[class*="card"]'))
                .filter(el => { const bb = el.getBoundingClientRect(); return bb.y > 100 && bb.width > 200; })
                .map(el => ({x: el.getBoundingClientRect().x+el.getBoundingClientRect().width/2,
                             y: el.getBoundingClientRect().y+el.getBoundingClientRect().height/2,
                             text: el.innerText.substring(0,30)}))
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
                    out.write_bytes(r.content)
                    dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
                    print(f"✓ {out.name} ({out.stat().st_size//1024}KB) {dur}s")
        pv.wait_for_timeout(3000)

    print(f"\nCréditos finales: {get_creds(pv)}")
    for name, _ in CLIPS:
        f = OUT_DIR / name
        print(f"  {name}: {'✓' if f.exists() and f.stat().st_size>100000 else '✗'} ({f.stat().st_size//1024 if f.exists() else 0}KB)")
    ss(pv, "99_final")
