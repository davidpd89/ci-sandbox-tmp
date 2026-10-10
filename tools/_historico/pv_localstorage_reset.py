"""Reset PixVerse settings via localStorage.clear() + reload."""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_C1 = ("Two young people in a bookstore library aisle, "
             "each reading books on opposite shelves, not acknowledging each other. "
             "Tense body language. Warm library light. 9:16 vertical, photorealistic, no text.")
PROMPT_C2 = ("Close-up: two hands reaching for the same book on a library shelf. "
             "Fingers almost touch. One person looks up at the other in surprise, "
             "then looks away hiding emotion. 9:16 vertical, cinematic, photorealistic, no text.")

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvls_{name}.png")

def get_creds(pv):
    return pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)

def get_btn_text(pv):
    return pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)

def download_video(pv, ctx, out_path):
    cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"]'))
            .filter(el => { const bb = el.getBoundingClientRect();
                return bb.y > 100 && bb.width > 200; })
            .map(el => ({x: el.getBoundingClientRect().x+el.getBoundingClientRect().width/2,
                         y: el.getBoundingClientRect().y+el.getBoundingClientRect().height/2}))
    """)
    if not cards: return False
    pv.mouse.click(cards[0]['x'], cards[0]['y'])
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

    print(f"Créditos: {get_creds(pv)}, btn: {get_btn_text(pv)}")

    # RESET via localStorage
    print("Limpiando localStorage para reset a 5s...")
    ls_keys = pv.evaluate("() => Object.keys(localStorage)")
    duration_keys = [k for k in ls_keys if 'dur' in k.lower() or 'time' in k.lower() or 'video' in k.lower() or 'setting' in k.lower()]
    print(f"Keys de duración en localStorage: {duration_keys}")

    # Mostrar todos los keys para diagnóstico
    all_ls = pv.evaluate("() => { const r = {}; for (const k of Object.keys(localStorage)) r[k] = localStorage.getItem(k); return JSON.stringify(r).substring(0, 500); }")
    print(f"localStorage (primeros 500 chars): {all_ls}")

    # Limpiar todo
    pv.evaluate("() => localStorage.clear()")
    pv.reload()
    pv.wait_for_load_state("networkidle", timeout=20000)
    pv.wait_for_timeout(3000)
    ss(pv, "00_after_reset")

    btn_after_reset = get_btn_text(pv)
    creds_after_reset = get_creds(pv)
    print(f"Después de reset: btn='{btn_after_reset}' cr={creds_after_reset}")

    # Intentar generar ambos clips
    for clip_name, prompt in [("clip1.mp4", PROMPT_C1), ("clip2.mp4", PROMPT_C2)]:
        out = OUT_DIR / clip_name
        if out.exists() and out.stat().st_size > 100000:
            print(f"\n{clip_name}: ya existe"); continue

        print(f"\n=== {clip_name} ===")
        btn = get_btn_text(pv)
        creds = get_creds(pv)
        print(f"btn='{btn}' cr={creds}")

        # Focus + type prompt
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
        pv.wait_for_timeout(500)

        val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''")
        print(f"Prompt: {val}")
        ss(pv, f"{clip_name}_p")

        if not val.strip():
            print("[ERROR] Textarea vacío"); continue

        creds_before = get_creds(pv)
        pv.locator("button:has-text('Crear'), button:has-text('Create')").last.click(force=True)
        pv.wait_for_timeout(3000)
        ss(pv, f"{clip_name}_c")

        creds_after = get_creds(pv)
        print(f"Créditos: {creds_before} → {creds_after}")

        if creds_after == creds_before:
            print("[WARN] Créditos no cambiaron — generación no arrancó")
            pv.keyboard.press("Escape"); pv.wait_for_timeout(400)
            continue

        # Esperar
        print("Esperando generación (3 min)...")
        start = time.time()
        while time.time() - start < 180:
            pv.wait_for_timeout(5000)
            print(f"  {int(time.time()-start)}s cr={get_creds(pv)}", end="\r")
        print()

        download_video(pv, ctx, out)
        pv.wait_for_timeout(3000)

        # Reset para siguiente clip
        if clip_name == "clip1.mp4":
            print("Reset para siguiente clip...")
            pv.evaluate("() => localStorage.clear()")
            pv.reload()
            pv.wait_for_load_state("networkidle", timeout=20000)
            pv.wait_for_timeout(2000)

    print(f"\nCréditos finales: {get_creds(pv)}")
    for name, _ in [("clip1.mp4",""), ("clip2.mp4","")]:
        f = OUT_DIR / name
        print(f"  {name}: {'✓' if f.exists() and f.stat().st_size>100000 else '✗'} ({f.stat().st_size//1024 if f.exists() else 0}KB)")
    ss(pv, "final")
