"""
Genera 2 × 5s clips enemies to lovers en PixVerse.
PRIMERO resetea la duración a 5s (20cr cada una).
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLIPS_DATA = [
    ("clip1.mp4",
     "Two young people in a bookstore library aisle, "
     "each reading books on opposite shelves, not acknowledging each other. "
     "Tense body language. Warm library light. 9:16 vertical, photorealistic, no text."),
    ("clip2.mp4",
     "Two hands reaching for the same book on a shelf at the same time. "
     "Fingers almost touch. One person looks up at the other in surprise. "
     "Close-up reaction — looks away with subtle almost-smile. "
     "9:16 vertical, cinematic, photorealistic, no text."),
]

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pv5_{name}.png")

def set_5s(pv):
    """Abre settings y selecciona 5s."""
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(400)
    pv.mouse.click(686, 902)  # Zona del selector de duración
    pv.wait_for_timeout(1000)
    for sel in ["span:has-text('5s')", "button:has-text('5s')", "[class*='option']:has-text('5s')"]:
        try:
            el = pv.locator(sel).first
            if el.is_visible(timeout=1200):
                el.click(); pv.wait_for_timeout(400); pv.keyboard.press("Escape"); pv.wait_for_timeout(400)
                btn = pv.evaluate("""() => { const bs = document.querySelectorAll('button');
                    for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
                    return null; }""")
                print(f"  5s OK, botón: '{btn}'")
                return True
        except Exception: pass
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(400)
    btn = pv.evaluate("""() => { const bs = document.querySelectorAll('button');
        for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
        return null; }""")
    print(f"  No se cambió a 5s, botón: '{btn}'")
    return False

def download_latest(pv, ctx, out_path):
    """Clic en el primer card y descarga."""
    all_cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"]'))
            .filter(el => { const bb = el.getBoundingClientRect();
                return bb.y > 100 && bb.width > 200 && bb.height > 100; })
            .slice(0,3).map(el => ({
                text: el.innerText.substring(0,50),
                x: el.getBoundingClientRect().x + el.getBoundingClientRect().width/2,
                y: el.getBoundingClientRect().y + el.getBoundingClientRect().height/2
            }))
    """)
    print(f"  Cards: {[c['text'][:25] for c in all_cards]}")
    if not all_cards: return False

    fc = all_cards[0]
    pv.mouse.click(fc['x'], fc['y'])
    pv.wait_for_timeout(3000)

    src = None
    for _ in range(20):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10: break
        pv.wait_for_timeout(1000)

    if not src:
        print("  No src"); return False

    cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
    ua = pv.evaluate("() => navigator.userAgent")
    r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
    if r.status_code == 200 and len(r.content) > 50000:
        out_path.write_bytes(r.content)
        dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
        print(f"  Guardado: {out_path.name} ({out_path.stat().st_size//1024}KB) dur={dur}s")
        return True
    print(f"  Error: status={r.status_code} size={len(r.content)}")
    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()

    creds_start = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos iniciales: {creds_start}")

    for clip_name, prompt in CLIPS_DATA:
        out = OUT_DIR / clip_name
        if out.exists() and out.stat().st_size > 100000:
            print(f"\n{clip_name}: ya existe ({out.stat().st_size//1024}KB)"); continue

        print(f"\n=== {clip_name} ===")
        print("Seleccionando 5s...")
        set_5s(pv)

        creds_before = pv.evaluate("""
            () => { for (const el of document.querySelectorAll('*')) {
                const t = (el.innerText||'').trim();
                if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                    const bb = el.getBoundingClientRect();
                    if (bb.x>1400 && bb.y<60) return t; }} return null; }
        """)
        print(f"Créditos: {creds_before}")
        if int(creds_before or 0) < 20:
            print("[ERROR] Sin créditos"); break

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

        val = pv.evaluate("""() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''""")
        print(f"Prompt: {val}")
        ss(pv, f"{clip_name}_p")
        if not val.strip(): print("[ERROR] Textarea vacío"); continue

        # Crear
        pv.locator("button:has-text('Crear'), button:has-text('Create')").last.click(force=True)
        pv.wait_for_timeout(2500)

        after = pv.evaluate("""
            () => { for (const el of document.querySelectorAll('*')) {
                const t = (el.innerText||'').trim();
                if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                    const bb = el.getBoundingClientRect();
                    if (bb.x>1400 && bb.y<60) return t; }} return null; }
        """)
        print(f"Créditos: {creds_before} → {after}")
        ss(pv, f"{clip_name}_c")

        if after == creds_before:
            print("[WARN] Créditos no bajaron — posible paywall o error")
            pv.keyboard.press("Escape"); pv.wait_for_timeout(500)
            continue

        # Esperar
        print("Esperando generación...")
        start = time.time()
        while time.time() - start < 180:
            pv.wait_for_timeout(5000)
            cur = pv.evaluate("""
                () => { for (const el of document.querySelectorAll('*')) {
                    const t = (el.innerText||'').trim();
                    if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                        const bb = el.getBoundingClientRect();
                        if (bb.x>1400 && bb.y<60) return t; }} return null; }
            """)
            print(f"  {int(time.time()-start)}s cr={cur}", end="\r")

        print()
        download_latest(pv, ctx, out)
        pv.wait_for_timeout(3000)

    final = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"\n=== Créditos finales: {final} ===")
    for n, _ in CLIPS_DATA:
        f = OUT_DIR / n
        print(f"  {n}: {'✓' if f.exists() and f.stat().st_size>100000 else '✗'} ({f.stat().st_size//1024 if f.exists() else 0}KB)")
    ss(pv, "final")
