"""
Diagnóstico rápido: el prompt está visualmente pero .value da vacío.
Ignoramos el val-check y simplemente clicamos Crear.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")

PROMPT_C1 = "Two young people in a bookstore aisle, each reading separate books, ignoring each other. Tense. Warm library light. 9:16 vertical, photorealistic, no text."
PROMPT_C2 = "Close-up two hands reaching for the same book on a shelf at the same time. Fingers almost touch. One looks up surprised at the other. Quick look away. 9:16 cinematic photorealistic no text."

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvjc_{name}.png")

def get_creds(pv):
    return pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(1000)
    ss(pv, "00_start")

    creds = get_creds(pv)
    print(f"Créditos: {creds}")

    btn = pv.evaluate("""() => { const bs = document.querySelectorAll('button');
        for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
        return null; }""")
    print(f"Botón: '{btn}'")

    # Diagnóstico: leer todos los textarea
    all_ta = pv.evaluate("""
        () => Array.from(document.querySelectorAll('textarea'))
            .map(ta => ({
                cls: ta.className.substring(0,40),
                val: ta.value.substring(0,60),
                inner: (ta.innerText||'').substring(0,60),
                placeholder: ta.placeholder,
                visible: ta.offsetParent !== null,
                focused: ta === document.activeElement
            }))
    """)
    print(f"Textareas: {len(all_ta)}")
    for ta in all_ta:
        print(f"  vis={ta['visible']} focused={ta['focused']} val={ta['val'][:40]} inner={ta['inner'][:40]} placeholder={ta['placeholder'][:30]}")

    # El prompt c1 fue escrito en la sesión anterior → ya está ahí
    # Leer el texto actual del textarea visible
    current_text = pv.evaluate("""
        () => {
            const textareas = Array.from(document.querySelectorAll('textarea')).filter(t => t.offsetParent !== null);
            if (!textareas.length) return '';
            // Leer tanto .value como innerText
            const ta = textareas[0];
            return ta.value || ta.innerText || ta.textContent || '';
        }
    """)
    print(f"Texto actual del textarea: {current_text[:80]}")

    # Si hay texto, clicar Crear directamente
    if current_text.strip():
        print("\nHay texto — clicando Crear directamente...")
        creds_before = get_creds(pv)
        pv.locator("button:has-text('Crear'), button:has-text('Create')").last.click(force=True)
        pv.wait_for_timeout(3000)
        ss(pv, "01_after_crear")
        creds_after = get_creds(pv)
        print(f"Créditos: {creds_before} → {creds_after}")

        if creds_after != creds_before:
            print("¡GENERACIÓN INICIADA!")
            print("Esperando...")
            start = time.time()
            while time.time() - start < 150:
                pv.wait_for_timeout(5000)
                print(f"  {int(time.time()-start)}s", end="\r")
            print()

            # Descargar
            all_cards = pv.evaluate("""
                () => Array.from(document.querySelectorAll('[class*="card"]'))
                    .filter(el => { const bb = el.getBoundingClientRect(); return bb.y > 100 && bb.width > 200; })
                    .map(el => ({x: el.getBoundingClientRect().x + el.getBoundingClientRect().width/2,
                                 y: el.getBoundingClientRect().y + el.getBoundingClientRect().height/2,
                                 text: el.innerText.substring(0,40)}))
            """)
            if all_cards:
                fc = all_cards[0]
                print(f"Clic card: {fc['text'][:30]}")
                pv.mouse.click(fc['x'], fc['y'])
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
                    out = OUT_DIR / "clip1.mp4"
                    if r.status_code == 200 and len(r.content) > 50000:
                        out.write_bytes(r.content)
                        dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
                        print(f"✓ clip1.mp4 ({out.stat().st_size//1024}KB) {dur}s")
        else:
            print("Créditos no bajaron — leyendo error de PixVerse...")
            err = pv.evaluate("""
                () => {
                    const notifications = Array.from(document.querySelectorAll('[class*="toast"], [class*="notification"], [role="alert"], [class*="error"]'));
                    return notifications.map(n => n.innerText.substring(0,100)).join(' | ');
                }
            """)
            print(f"Error PixVerse: {err}")
    else:
        print("Textarea vacío — escribiendo prompt c1 y clicando Crear...")
        # Type directamente sin check posterior
        pv.evaluate("""
            () => {
                const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea[placeholder*="Describ"]');
                if (ta) { ta.focus(); }
            }
        """)
        pv.wait_for_timeout(300)
        pv.keyboard.press("Control+A")
        pv.keyboard.press("Delete")
        pv.wait_for_timeout(200)
        pv.keyboard.type(PROMPT_C1, delay=8)
        pv.wait_for_timeout(600)
        ss(pv, "01_typed")

        # Dar tiempo a que React actualice
        pv.wait_for_timeout(1000)

        creds_before = get_creds(pv)
        pv.locator("button:has-text('Crear'), button:has-text('Create')").last.click(force=True)
        pv.wait_for_timeout(3000)
        ss(pv, "01b_crear")
        creds_after = get_creds(pv)
        print(f"Créditos: {creds_before} → {creds_after}")

        err = pv.evaluate("""
            () => {
                const all = Array.from(document.querySelectorAll('*'));
                for (const el of all) {
                    if ((el.innerText||'').length > 10 && (el.innerText||'').length < 200) {
                        if (/error|fail|invalid|empty|required|suscrib/i.test(el.innerText||'')) {
                            return el.innerText.trim().substring(0,100);
                        }
                    }
                }
                return null;
            }
        """)
        if err: print(f"Error detectado: {err}")

    print(f"\nCréditos finales: {get_creds(pv)}")
    ss(pv, "99_final")
