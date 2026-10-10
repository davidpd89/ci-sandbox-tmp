"""
Estado actual: popup cerrado, página en creación normal.
Genera ahora mismo: clipboard paste exacto como resaca que funcionó,
y si aparece popup de suscripción → busca X → cierra → la generación sigue.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\06-olvide-la-trama")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "Cinematic 9:16, 5 seconds. "
    "A woman in her 30s sits at night in a cozy room, warm lamp light, "
    "holding an old worn paperback book with no visible title. "
    "She opens it slowly. In the dark window, a fleeting reflection of her teenage self appears, "
    "like a memory. She doesn't react with fear, just pauses and touches the page softly. "
    "Multi-shot: close on her face, then the reflection, then the book in her hands. "
    "Photorealistic, emotional, warm light, no text, no logos, 9:16 vertical."
)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pgen_{name}.png")

def get_creds(pv):
    return pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)

def close_popup_if_open(pv):
    """Si hay un popup de suscripción, lo cierra."""
    # Buscar cualquier botón de cierre en el popup
    closed = False
    for strategy in [
        # X o close button por aria-label o clase
        "button[aria-label*='close'], button[aria-label*='Close'], button[aria-label*='cerrar']",
        # SVG close icon dentro de button
        "button:has(svg[data-icon*='close']), button:has(svg[class*='close'])",
        # Texto del botón
        "button:has-text('×'), button:has-text('✕'), button:has-text('No gracias')",
    ]:
        try:
            btn = pv.locator(strategy).first
            if btn.is_visible(timeout=1000):
                btn.click()
                closed = True
                print(f"  Popup cerrado: {strategy}")
                pv.wait_for_timeout(500)
                break
        except Exception:
            pass

    if not closed:
        # Intentar Escape
        pv.keyboard.press("Escape")
        pv.wait_for_timeout(500)

    # Verificar si el popup sigue ahí
    has_subscribe = pv.evaluate("""
        () => {
            const el = Array.from(document.querySelectorAll('*')).find(
                e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'));
            return !!el;
        }
    """)
    return not has_subscribe  # True = popup cerrado

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(500)
    ss(pv, "00_clean")

    creds = get_creds(pv)
    print(f"Créditos: {creds}")

    btn = pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)
    print(f"Botón: '{btn}'")

    # === RELLENAR TEXTAREA (método resaca: JS focus + clipboard + Ctrl+V) ===
    print("\nRellenando textarea...")
    pv.evaluate("""
        () => {
            const ta = document.querySelector('textarea.w-full') ||
                       document.querySelector('textarea[placeholder*="Describa"]') ||
                       document.querySelector('textarea');
            if (ta) ta.focus();
        }
    """)
    pv.wait_for_timeout(300)
    pv.keyboard.press("Control+A")

    # Escribir al portapapeles y verificar
    pv.evaluate("(t) => navigator.clipboard.writeText(t)", PROMPT)
    # Pequeña espera para que el async de clipboard complete
    pv.wait_for_timeout(500)

    # Verificar que el clipboard tiene el texto
    clip_check = pv.evaluate("async () => await navigator.clipboard.readText()")
    print(f"Clipboard: {clip_check[:60]}...")

    pv.keyboard.press("Control+V")
    pv.wait_for_timeout(1000)

    val = pv.evaluate("""
        () => {
            const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea');
            return ta ? (ta.value || ta.innerText || '') : '';
        }
    """)
    print(f"Textarea valor: {val[:60]}")
    ss(pv, "01_prompt")

    # === ENVIAR: Crear button (force click) ===
    print("\nEnviando...")
    creds_before = get_creds(pv)

    # Clicar el botón Crear directamente
    crear = pv.locator("button:has-text('Crear'), button:has-text('Create')").last
    crear.click(force=True)
    pv.wait_for_timeout(2500)
    ss(pv, "02_after_crear")

    # === GESTIONAR POPUP SI APARECE ===
    popup_appeared = pv.evaluate("""
        () => {
            const el = Array.from(document.querySelectorAll('*')).find(
                e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'));
            return !!el;
        }
    """)
    if popup_appeared:
        print("Popup de suscripción detectado — cerrando...")
        ss(pv, "02b_popup")

        # Buscar el botón de cierre del popup de forma exhaustiva
        # Primero, inspeccionar qué botones hay en la zona del popup
        popup_btns = pv.evaluate("""
            () => {
                // El popup está centrado en la pantalla, buscar botones cerca del centro
                return Array.from(document.querySelectorAll('button, [role="button"]'))
                    .filter(el => {
                        const bb = el.getBoundingClientRect();
                        return bb.offsetParent !== null && bb.y < 600 && bb.x > 400 && bb.x < 1500;
                    })
                    .map(el => ({
                        text: (el.innerText||'').trim().substring(0,30),
                        x: el.getBoundingClientRect().x,
                        y: el.getBoundingClientRect().y,
                        w: el.getBoundingClientRect().width,
                        h: el.getBoundingClientRect().height
                    }));
            }
        """)
        print(f"Botones en zona del popup: {popup_btns[:10]}")

        # Buscar el botón X (pequeño, en la esquina del modal)
        # Normalmente está en la esquina superior derecha del modal
        for btn_info in popup_btns:
            text = btn_info['text'].strip()
            # Botón pequeño (X, ×, ✕) o sin texto en esquina del modal
            if text in ('×', '✕', 'x', 'X', '') and btn_info['w'] < 50:
                pv.mouse.click(btn_info['x'] + btn_info['w']/2, btn_info['y'] + btn_info['h']/2)
                print(f"  Clic en botón cierre: '{text}' en ({btn_info['x']:.0f},{btn_info['y']:.0f})")
                pv.wait_for_timeout(500)
                break
        else:
            # Si no hay X, presionar Escape
            pv.keyboard.press("Escape")
            pv.wait_for_timeout(500)

        ss(pv, "02c_after_close")
        popup_still = pv.evaluate("""
            () => !!Array.from(document.querySelectorAll('*')).find(
                e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'))
        """)
        print(f"Popup sigue: {popup_still}")

    # Verificar créditos
    creds_after = get_creds(pv)
    print(f"Créditos: {creds_before} → {creds_after}")

    if creds_after != creds_before:
        print(f"¡GENERACIÓN INICIADA!")
    else:
        print("[WARN] Créditos no bajaron todavía")

    # === ESPERAR GENERACIÓN ===
    print("\nEsperando generación (3 min)...")
    start = time.time()
    while time.time() - start < 180:
        pv.wait_for_timeout(5000)
        cur = get_creds(pv)
        elapsed = int(time.time()-start)
        print(f"  {elapsed}s cr={cur}", end="\r")
        if cur and creds_before and int(cur) < int(creds_before):
            print(f"\n  ¡Créditos bajaron! Generando...")
            break
    print()
    ss(pv, "03_wait")

    # === DESCARGAR ===
    print("Descargando...")
    # Buscar el primer card y clicar
    cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"]'))
            .filter(el => { const bb = el.getBoundingClientRect(); return bb.y > 100 && bb.width > 200; })
            .slice(0,3).map(el => ({
                x: el.getBoundingClientRect().x + el.getBoundingClientRect().width/2,
                y: el.getBoundingClientRect().y + el.getBoundingClientRect().height/2,
                text: el.innerText.substring(0,40)
            }))
    """)
    print(f"Cards: {[c['text'][:25] for c in cards]}")

    if cards:
        fc = cards[0]
        pv.mouse.click(fc['x'], fc['y'])
        pv.wait_for_timeout(3000)

    src = None
    for _ in range(20):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10: break
        pv.wait_for_timeout(1000)

    final_creds = get_creds(pv)
    print(f"\nCréditos finales: {final_creds} (antes: {creds_before})")

    if src:
        print(f"src: {src[:80]}")
        cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
        ua = pv.evaluate("() => navigator.userAgent")
        r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
        out = OUT_DIR / "clip1.mp4"
        if r.status_code == 200 and len(r.content) > 50000:
            out.write_bytes(r.content)
            dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
            print(f"✓ {out.name} ({out.stat().st_size//1024}KB) dur={dur}s")
        else:
            print(f"  Error: status={r.status_code} size={len(r.content)//1024}KB")
    else:
        print("  No src encontrado")

    ss(pv, "99_final")
