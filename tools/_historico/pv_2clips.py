"""
2 × 5s clips en PixVerse = 10s de narrativa genuina enemies to lovers.
No bucle — 2 escenas DISTINTAS con 2 prompts diferentes.
Cada una cuesta 20cr. Total: 40cr.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLIPS = [
    {
        "name": "clip1.mp4",
        "prompt": (
            "Two young people in a bookstore library aisle, standing far apart, "
            "each looking at books on opposite shelves, clearly ignoring each other. "
            "Warm library light. Body language of avoidance. "
            "9:16 vertical, cinematic, photorealistic, no text."
        )
    },
    {
        "name": "clip2.mp4",
        "prompt": (
            "Close-up: two hands reaching for the same book on a library shelf at the same time. "
            "Their fingers almost touch. They both freeze. "
            "Pull back to show their faces looking at each other for the first time, "
            "one of them quickly looks away trying to hide a reaction. "
            "9:16 vertical, cinematic, photorealistic, no text."
        )
    }
]

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pv2c_{name}.png")

def generate_clip(pv, ctx, prompt, out_path, clip_name):
    """Genera un clip de 5s en PixVerse con el prompt dado."""
    print(f"\n=== Generando {clip_name} ===")
    if out_path.exists() and out_path.stat().st_size > 100000:
        print(f"  Ya existe ({out_path.stat().st_size//1024}KB)")
        return True

    # Verificar créditos
    creds_before = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"  Créditos disponibles: {creds_before}")
    if int(creds_before or 0) < 20:
        print("  [ERROR] Créditos insuficientes (<20)")
        return False

    # Verificar/asegurar 5s seleccionado
    btn = pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)
    print(f"  Botón: '{btn}' (debe ser ~20cr)")

    # Foco en textarea
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

    # Escribir prompt con type()
    pv.keyboard.type(prompt, delay=8)
    pv.wait_for_timeout(500)

    val = pv.evaluate("""
        () => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''
    """)
    print(f"  Prompt: {val}")
    ss(pv, f"{clip_name}_prompt")

    if not val.strip():
        print("  [ERROR] Textarea vacío")
        return False

    # Clicar Crear
    crear = pv.locator("button:has-text('Crear'), button:has-text('Create')").last
    crear.click(force=True)
    pv.wait_for_timeout(2500)
    ss(pv, f"{clip_name}_after_crear")

    creds_after = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"  Créditos: {creds_before} → {creds_after}")

    if creds_after == creds_before:
        print("  [WARN] Créditos no bajaron — ¿popup de suscripción?")
        # Buscar si hay un popup de suscripción — cerrarlo y cambiar a 5s
        has_sub_popup = pv.evaluate("""
            () => !!document.querySelector('[class*="modal"] [class*="Suscribirse"], [role="dialog"] button:contains("Suscribirse")')
        """)
        pv.keyboard.press("Escape")
        pv.wait_for_timeout(500)
        return False

    # Esperar generación
    print("  Esperando generación...")
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
        print(f"    {elapsed}s | cr={cur_creds}", end="\r")
        # Si los créditos bajaron, está generando; esperar a que suba el card
        # El vídeo se genera en ~30-120s
        if elapsed > 90:
            # Intentar encontrar un card nuevo
            break

    pv.wait_for_timeout(5000)
    ss(pv, f"{clip_name}_after_wait")

    # Clicar el primer card y descargar
    first_card = pv.evaluate("""
        () => {
            const cards = Array.from(document.querySelectorAll('[class*="card"]'))
                .filter(el => { const bb = el.getBoundingClientRect();
                    return bb.y > 150 && bb.width > 200; });
            if (!cards.length) return null;
            const bb = cards[0].getBoundingClientRect();
            return {x: bb.x + bb.width/2, y: bb.y + bb.height/2, text: cards[0].innerText.substring(0,40)};
        }
    """)
    if first_card:
        print(f"\n  Clicando card: {first_card['text'][:30]}")
        pv.mouse.click(first_card['x'], first_card['y'])
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
        if r.status_code == 200 and len(r.content) > 50000:
            out_path.write_bytes(r.content)
            dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
            print(f"  Guardado: {out_path.name} ({out_path.stat().st_size//1024}KB) dur={dur}s")
            return True
        print(f"  Error o fichero pequeño: status={r.status_code} size={len(r.content)}")
    else:
        print("  No se encontró src")

    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.keyboard.press("Escape")
    pv.wait_for_timeout(800)

    results = []
    for clip_info in CLIPS:
        out = OUT_DIR / clip_info["name"]
        ok = generate_clip(pv, ctx, clip_info["prompt"], out, clip_info["name"])
        results.append((clip_info["name"], ok))
        if ok:
            # Pequeña pausa entre generaciones
            pv.wait_for_timeout(5000)

    print("\n=== RESUMEN ===")
    for name, ok in results:
        f = OUT_DIR / name
        print(f"  {name}: {'✓' if ok else '✗'} ({f.stat().st_size//1024 if f.exists() else 0}KB)")

    # Créditos finales
    final = pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)
    print(f"Créditos finales: {final}")
