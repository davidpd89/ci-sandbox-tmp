"""
PixVerse: genera el vídeo de enemies to lovers.
Usa fill() de Playwright para React inputs + dispatchEvent para activar el state.
Intenta 10s; si falla el selector de duración, usa 5s x2 = 40cr.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Prompt corto y potente para un vídeo narrativo de 10s
PROMPT = (
    "Cinematic 9:16 slow burn tension video. Two young people in a bookstore, "
    "standing in the same aisle. Shot 1: Wide — they are apart, ignoring each other, "
    "both browsing books. Shot 2: Medium — both reach for the same book, hands almost touch, "
    "they freeze and lock eyes. Shot 3: Close up — one of them pulls back, looks away, "
    "trying to hide a reaction. Shot 4: Wide again — both walk away separately but each "
    "glances back at the other at the same time. "
    "Style: warm library light, realistic, photorealistic, no text, no logos, 9:16 vertical."
)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pv2_{name}.png")

def fill_react_textarea(page, selector, text):
    """Rellena un textarea de React activando los eventos correctos."""
    # Poner texto en clipboard y usar JS para leerlo
    page.evaluate("(t) => navigator.clipboard.writeText(t)", text[:500])
    page.evaluate("""
        async (sel) => {
            const ta = document.querySelector(sel);
            if (!ta) return;
            const text = await navigator.clipboard.readText();
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value').set;
            nativeInputValueSetter.call(ta, text);
            ta.dispatchEvent(new Event('input', { bubbles: true }));
            ta.dispatchEvent(new Event('change', { bubbles: true }));
        }
    """, selector)
    page.wait_for_timeout(500)

def run():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        ctx = b.contexts[0]
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        pv = next(pg for pg in [x for c in b.contexts for x in c.pages] if "pixverse" in pg.url)
        pv.bring_to_front()
        pv.wait_for_timeout(1000)

        # Ir a creación si no estamos
        if "/creation" not in pv.url:
            create_links = pv.evaluate("""
                () => Array.from(document.querySelectorAll('a[href]'))
                    .filter(a => a.href.includes('creat'))
                    .map(a => a.href)
            """)
            if create_links:
                pv.goto(create_links[0])
                pv.wait_for_load_state("networkidle", timeout=15000)
                pv.wait_for_timeout(1000)

        print(f"URL: {pv.url}")
        credits_before = pv.evaluate("""
            () => { const els = document.querySelectorAll('*');
                for (const el of els) { const t = (el.innerText||'').trim();
                    if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                        const bb = el.getBoundingClientRect();
                        if (bb.x>1400 && bb.y<60) return t; } } return null; }
        """)
        print(f"Créditos antes: {credits_before}")
        ss(pv, "00_start")

        # === Cambiar duración a 10s ===
        print("Intentando 10s...")
        # Clic en la zona de duración (x=686, y=902 del inspect anterior)
        pv.mouse.click(686, 902)
        pv.wait_for_timeout(1200)
        ss(pv, "01_dur_dropdown")

        # Buscar el 10s que ahora debería ser visible
        opt = pv.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    if ((el.innerText||'').trim() === '10s' && el.offsetParent !== null) {
                        const bb = el.getBoundingClientRect();
                        if (bb.width > 0 && bb.height > 0) return {x: bb.x, y: bb.y};
                    }
                }
                return null;
            }
        """)
        if opt:
            pv.mouse.click(opt['x'] + 5, opt['y'] + 5)
            print(f"  10s clickeado en ({opt['x']}, {opt['y']})")
            pv.wait_for_timeout(500)
        else:
            print("  10s no encontrado en dropdown — usando 5s")

        # Verificar botón
        btn = pv.evaluate("""
            () => { const bs = document.querySelectorAll('button');
                for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
                return null; }
        """)
        print(f"Botón Crear: '{btn}'")

        # === Rellenar textarea con React method ===
        print("Rellenando prompt via React setter...")
        fill_react_textarea(pv, "textarea.w-full", PROMPT)

        # Verificar que el texto está en el textarea
        val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0, 60) || ''")
        print(f"Valor textarea: {val}")

        if not val.strip():
            # Fallback: type directamente
            print("Fallback: usando Playwright fill()...")
            ta = pv.locator("textarea.w-full, textarea[placeholder*='Describe'], textarea[placeholder*='contenido']").first
            try:
                ta.fill(PROMPT[:500], force=True)
                val2 = pv.evaluate("() => document.querySelector('textarea')?.value?.substring(0,60) || ''")
                print(f"Valor tras fill: {val2}")
            except Exception as e:
                print(f"fill error: {e}")

        ss(pv, "02_prompt")

        # === Registrar cards antes de crear ===
        before_first = pv.evaluate("""
            () => {
                const cards = Array.from(document.querySelectorAll('[class*="card"]'))
                    .filter(el => { const bb = el.getBoundingClientRect();
                        return bb.y > 150 && bb.width > 150 && bb.height > 100; });
                return cards.length > 0 ? cards[0].innerText.substring(0,50) : null;
            }
        """)
        print(f"\nPrimer card antes: {before_first}")

        # === Clicar Crear ===
        # Buscar por texto, con force=True para bypasear overlays
        crear_btn = pv.locator("button:has-text('Crear'), button:has-text('Create')").last
        try:
            crear_btn.click(force=True)
            print("Crear pulsado (force=True)")
        except Exception as e:
            # Fallback por JS click
            pv.evaluate("""
                () => { const bs = document.querySelectorAll('button');
                    for (const b of bs) { if (/crear|create/i.test(b.innerText)) { b.click(); break; } } }
            """)
            print("Crear pulsado (JS click)")

        pv.wait_for_timeout(3000)
        ss(pv, "03_after_crear")

        credits_after_click = pv.evaluate("""
            () => { const els = document.querySelectorAll('*');
                for (const el of els) { const t = (el.innerText||'').trim();
                    if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                        const bb = el.getBoundingClientRect();
                        if (bb.x>1400 && bb.y<60) return t; } } return null; }
        """)
        print(f"Créditos tras Crear: {credits_after_click}")

        if credits_after_click == credits_before:
            print("[WARN] Los créditos no bajaron — la generación NO se inició")
            print("Intentando click alternativo en el botón...")
            pv.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.innerText.includes('Crear') || b.innerText.includes('Create')) {
                            b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                            return 'clicked: ' + b.innerText.substring(0,20);
                        }
                    }
                    return 'no button found';
                }
            """)
            pv.wait_for_timeout(3000)
            ss(pv, "03b_retry")

        # Esperar generación
        print("\nEsperando generación (hasta 4 min)...")
        start = time.time()
        while time.time() - start < 240:
            pv.wait_for_timeout(5000)
            elapsed = int(time.time() - start)
            # Verificar si el primer card cambió (nuevo video arriba)
            current_first = pv.evaluate("""
                () => {
                    const cards = Array.from(document.querySelectorAll('[class*="card"]'))
                        .filter(el => { const bb = el.getBoundingClientRect();
                            return bb.y > 150 && bb.width > 150; });
                    return cards.length > 0 ? cards[0].innerText.substring(0,50) : null;
                }
            """)
            current_creds = pv.evaluate("""
                () => { const els = document.querySelectorAll('*');
                    for (const el of els) { const t = (el.innerText||'').trim();
                        if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                            const bb = el.getBoundingClientRect();
                            if (bb.x>1400 && bb.y<60) return t; } } return null; }
            """)
            print(f"  {elapsed}s | cr={current_creds} | first_card={current_first[:30] if current_first else '?'}", end="\r")
            if current_first and current_first != before_first:
                print(f"\n  NUEVO CARD DETECTADO: {current_first[:50]}")
                break
            if current_creds and credits_before and int(current_creds) < int(credits_before):
                print(f"\n  Créditos bajaron ({credits_before} → {current_creds}) — generando")

        ss(pv, "04_after_wait")

        # Intentar descargar el primer card (más reciente)
        first_card = pv.evaluate("""
            () => {
                const cards = Array.from(document.querySelectorAll('[class*="card"]'))
                    .filter(el => { const bb = el.getBoundingClientRect();
                        return bb.y > 150 && bb.width > 200; });
                if (!cards.length) return null;
                const bb = cards[0].getBoundingClientRect();
                return {x: bb.x + bb.width/2, y: bb.y + bb.height/2, text: cards[0].innerText.substring(0,50)};
            }
        """)
        if first_card:
            print(f"\nClicando primer card: {first_card['text'][:40]}")
            pv.mouse.click(first_card['x'], first_card['y'])
            pv.wait_for_timeout(3000)
            ss(pv, "05_player")

            src = None
            for _ in range(20):
                src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
                if src and len(src) > 10: break
                pv.wait_for_timeout(800)

            if src:
                cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
                ua = pv.evaluate("() => navigator.userAgent")
                print(f"Descargando: {src[:80]}")
                r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=90)
                if r.status_code == 200:
                    out = OUT_DIR / "clip1.mp4"
                    out.write_bytes(r.content)
                    dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
                    print(f"Guardado: {out.name} ({out.stat().st_size//1024}KB) dur={dur}s")
                else:
                    print(f"Error: {r.status_code}")

        # Créditos finales
        final_creds = pv.evaluate("""
            () => { const els = document.querySelectorAll('*');
                for (const el of els) { const t = (el.innerText||'').trim();
                    if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                        const bb = el.getBoundingClientRect();
                        if (bb.x>1400 && bb.y<60) return t; } } return null; }
        """)
        print(f"\nCréditos finales: {final_creds} (antes={credits_before})")
        ss(pv, "99_final")

if __name__ == "__main__":
    run()
