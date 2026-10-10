"""
Navega de nuevo a PixVerse para restaurar el estado por defecto (5s).
Genera 2 clips de 5s para enemies to lovers.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLIPS = [
    ("clip1.mp4",
     "Two young people in a bookstore library aisle, "
     "each reading books on opposite shelves, not acknowledging each other. "
     "Tense body language. Warm library light. 9:16 vertical, photorealistic, no text."),
    ("clip2.mp4",
     "Close-up two hands reaching for the same book on a shelf at the same time. "
     "Fingers almost touch. One person looks up at the other in surprise. "
     "Close-up reaction, looks away with subtle almost-smile. "
     "9:16 vertical, cinematic, photorealistic, no text."),
]

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvr2_{name}.png")

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

def download(pv, ctx, out_path):
    all_cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"]'))
            .filter(el => { const bb = el.getBoundingClientRect();
                return bb.y > 100 && bb.width > 200 && bb.height > 100; })
            .map(el => ({x: el.getBoundingClientRect().x + el.getBoundingClientRect().width/2,
                         y: el.getBoundingClientRect().y + el.getBoundingClientRect().height/2,
                         text: el.innerText.substring(0,40)}))
    """)
    if not all_cards: return False
    fc = all_cards[0]
    print(f"  Clic card: {fc['text'][:30]}")
    pv.mouse.click(fc['x'], fc['y'])
    pv.wait_for_timeout(3000)

    src = None
    for _ in range(20):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10: break
        pv.wait_for_timeout(1000)
    if not src: return False

    cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
    ua = pv.evaluate("() => navigator.userAgent")
    r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
    if r.status_code == 200 and len(r.content) > 50000:
        out_path.write_bytes(r.content)
        dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
        print(f"  ✓ {out_path.name} ({out_path.stat().st_size//1024}KB) {dur}s")
        return True
    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()

    print(f"Créditos: {get_creds(pv)}")

    for clip_name, prompt in CLIPS:
        out = OUT_DIR / clip_name
        if out.exists() and out.stat().st_size > 100000:
            print(f"\n{clip_name}: ya existe"); continue

        print(f"\n=== {clip_name} ===")

        # NAVEGAR DE NUEVO para restaurar estado por defecto (5s)
        print("Navegando a creación (reset a 5s por defecto)...")
        pv.goto("https://app.pixverse.ai/creation/video")
        pv.wait_for_load_state("networkidle", timeout=20000)
        pv.wait_for_timeout(2000)
        ss(pv, f"{clip_name}_reset")

        btn = get_btn(pv)
        creds = get_creds(pv)
        print(f"Después de reset: btn='{btn}' cr={creds}")

        if not btn or "20" not in (btn or "") and "40" in (btn or ""):
            print("[WARN] Sigue mostrando 40cr — intentando buscar 5s")

        # Escribir prompt
        pv.evaluate("""
            () => {
                const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea');
                if (ta) ta.focus();
            }
        """)
        pv.wait_for_timeout(300)
        pv.keyboard.press("Control+A")
        pv.keyboard.press("Delete")
        pv.wait_for_timeout(200)
        pv.keyboard.type(prompt, delay=8)
        pv.wait_for_timeout(400)

        val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''")
        print(f"Prompt: {val}")
        ss(pv, f"{clip_name}_prompt")

        if not val.strip():
            print("[ERROR] Textarea vacío"); continue

        creds_before = get_creds(pv)
        btn_before = get_btn(pv)
        print(f"Antes de crear: cr={creds_before} btn='{btn_before}'")

        # Click Crear
        pv.locator("button:has-text('Crear'), button:has-text('Create')").last.click(force=True)
        pv.wait_for_timeout(3000)
        ss(pv, f"{clip_name}_crear")

        creds_after = get_creds(pv)
        print(f"Créditos: {creds_before} → {creds_after}")

        if creds_after == creds_before:
            print("[WARN] Créditos no bajaron")
            pv.keyboard.press("Escape"); pv.wait_for_timeout(500)
            continue

        # Esperar generación
        print("Esperando generación...")
        start = time.time()
        while time.time() - start < 180:
            pv.wait_for_timeout(5000)
            cur = get_creds(pv)
            print(f"  {int(time.time()-start)}s cr={cur}", end="\r")
        print()

        download(pv, ctx, out)
        pv.wait_for_timeout(3000)

    final = get_creds(pv)
    print(f"\nCréditos finales: {final}")
    for name, _ in CLIPS:
        f = OUT_DIR / name
        print(f"  {name}: {'✓' if f.exists() and f.stat().st_size>100000 else '✗'} ({f.stat().st_size//1024 if f.exists() else 0}KB)")
    ss(pv, "final")
