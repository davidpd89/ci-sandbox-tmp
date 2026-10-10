"""
Genera DP-F0-073 "Enemies to lovers" en PixVerse.
10s, Multi-Toma, sin audio, 40 créditos.
Historia visual narrativa en 4 planos conectados — no un bucle.
"""
import sys, io, time, requests, base64
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\05-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Prompt con historia visual NARRATIVA progresiva — 4 planos conectados en 10s
# Fuente humana base: Reddit r/libros (lectora que prefiere "slow burn y enemies to lovers")
PROMPT = (
    "Cinematic vertical 9:16 video, 10 seconds, multi-shot progression, "
    "realistic slow-burn tension between two young people in a bookstore or university library. "
    "Shot 1 (0-3s): Wide shot — two people standing apart in the same aisle, both reaching for books "
    "on opposite shelves, not looking at each other, arms crossed body language, obvious avoidance. "
    "Shot 2 (3-6s): Medium shot — both reach for the same book on the shelf at the same time, "
    "their hands almost touching, they freeze and look up at each other for the first time. "
    "Shot 3 (6-9s): Close-up alternating — her face then his, both look away immediately "
    "pretending nothing happened, one of them takes the book anyway, a subtle almost-smile. "
    "Shot 4 (9-10s): Wide shot again — they walk in opposite directions but both look back "
    "at the same moment without realizing it. "
    "Style: warm natural library light, realistic human emotion, no exaggeration, no text, "
    "no subtitles, no logos, cinematic film grain, photorealistic."
)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pve_{name}.png")

def get_pv_page(b):
    return next(pg for pg in [x for c in b.contexts for x in c.pages] if "pixverse" in pg.url)

def run():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        ctx = b.contexts[0]
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        pv = get_pv_page(b)
        pv.bring_to_front()

        # Asegurarse de estar en la vista de creación
        if "/creation" not in pv.url and "/create" not in pv.url:
            # Navegar al panel de creación
            create_link = pv.locator("a[href*='creat'], li:has-text('Creación'), nav a").first
            try:
                if create_link.is_visible(timeout=2000):
                    create_link.click()
                    pv.wait_for_timeout(2000)
            except Exception:
                pass

        pv.wait_for_timeout(1000)
        ss(pv, "01_start")
        print(f"URL: {pv.url}")

        # Verificar créditos actuales
        credits = pv.evaluate("""
            () => {
                const els = document.querySelectorAll('*');
                for (const el of els) {
                    const t = (el.innerText || '').trim();
                    if (/^\d+$/.test(t) && parseInt(t) > 0 && parseInt(t) <= 200) {
                        const bb = el.getBoundingClientRect();
                        if (bb.x > 1400 && bb.y < 60) return t;
                    }
                }
                return null;
            }
        """)
        print(f"Créditos actuales: {credits}")

        # === PASO 1: Cambiar duración a 10s ===
        print("\nCambiando duración a 10s...")
        # Buscar el span/button de "5s" visible y clicar para abrir dropdown
        dur_span = pv.locator("span:has-text('5s'), button:has-text('5s'), [class*='duration']:has-text('5s')").first
        try:
            if dur_span.is_visible(timeout=3000):
                dur_span.click()
                pv.wait_for_timeout(1500)
                ss(pv, "02_dur_dropdown")

                # Ahora los 10s deberían ser visibles
                opt_10s = pv.locator("div:has-text('10s'):not(:has(*)), span:has-text('10s'):not(:has(*)), [role='option']:has-text('10s')").first
                if opt_10s.is_visible(timeout=2000):
                    opt_10s.click()
                    print("  10s seleccionado")
                    pv.wait_for_timeout(1000)
                else:
                    # Intentar clic por coordenadas relativas al dropdown
                    # Los divs ocultos estaban en x=0,y=0 — ahora deberían haberse movido
                    all_dur = pv.evaluate("""
                        () => Array.from(document.querySelectorAll('div, span, button, li'))
                            .filter(el => {
                                const t = (el.innerText || '').trim();
                                return t === '10s' && el.offsetParent !== null;
                            })
                            .map(el => ({x: el.getBoundingClientRect().x, y: el.getBoundingClientRect().y, text: t}))
                    """)
                    print(f"  Opciones 10s visibles: {all_dur}")
                    if all_dur:
                        pv.mouse.click(all_dur[0]['x'] + 5, all_dur[0]['y'] + 5)
                        print(f"  Clic en 10s en ({all_dur[0]['x']}, {all_dur[0]['y']})")
                        pv.wait_for_timeout(1000)
            else:
                print("  [WARN] Span 5s no encontrado, buscando por coordenadas")
                # De la inspección: SPAN en x=686, y=902
                pv.mouse.click(686, 902)
                pv.wait_for_timeout(1500)
                ss(pv, "02b_dur_after_click")
        except Exception as e:
            print(f"  Error cambiando duración: {e}")

        # Verificar el botón Crear actualizado
        btn_text = pv.evaluate("""
            () => {
                const bs = document.querySelectorAll('button');
                for (const b of bs) {
                    if (/crear|create/i.test(b.innerText) && b.offsetParent !== null) return b.innerText.trim();
                }
                return null;
            }
        """)
        print(f"Botón Crear ahora: '{btn_text}' (esperado: Crear 40)")

        # === PASO 2: Escribir prompt ===
        print("\nEscribiendo prompt...")
        pv.evaluate("""
            () => {
                const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea');
                if (ta) { ta.focus(); ta.select(); }
            }
        """)
        pv.wait_for_timeout(300)
        pv.keyboard.press("Control+A")
        pv.evaluate("(t) => navigator.clipboard.writeText(t)", PROMPT)
        pv.keyboard.press("Control+V")
        pv.wait_for_timeout(800)

        val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''")
        print(f"Prompt en textarea: {val}...")
        ss(pv, "03_prompt_filled")

        # === PASO 3: Generar ===
        # Contar cards actuales
        before_cards = pv.evaluate("""
            () => Array.from(document.querySelectorAll('[class*="card"], [class*="item"]'))
                .filter(el => {
                    const bb = el.getBoundingClientRect();
                    return bb.y > 150 && bb.width > 200;
                }).length
        """)
        print(f"\nCards antes: {before_cards}")

        crear = pv.locator("button:has-text('Crear'), button:has-text('Create')").last
        crear.click()
        print("Crear pulsado")
        pv.wait_for_timeout(2000)
        ss(pv, "04_after_crear")

        # Esperar nuevo card
        print("Esperando generación (hasta 6 min)...")
        start = time.time()
        new_card_found = False
        while time.time() - start < 360:
            pv.wait_for_timeout(5000)
            cur_cards = pv.evaluate("""
                () => Array.from(document.querySelectorAll('[class*="card"], [class*="item"]'))
                    .filter(el => {
                        const bb = el.getBoundingClientRect();
                        return bb.y > 150 && bb.width > 200;
                    }).length
            """)
            elapsed = int(time.time() - start)
            print(f"  {elapsed}s | cards={cur_cards} (antes={before_cards})", end="\r")
            if cur_cards > before_cards:
                print(f"\n  Nuevo card detectado! ({cur_cards} total)")
                new_card_found = True
                break

        ss(pv, "05_after_gen")

        if not new_card_found:
            print("\n  TIMEOUT — verificar screenshot 05_after_gen")
            # El vídeo podría estar ahí aunque no detectemos el card
            print("  Continuando de todas formas...")

        # Clicar en el primer card (más reciente)
        pv.wait_for_timeout(2000)
        all_cards = pv.evaluate("""
            () => Array.from(document.querySelectorAll('[class*="card"], [class*="item"]'))
                .filter(el => {
                    const bb = el.getBoundingClientRect();
                    return bb.y > 150 && bb.width > 200;
                })
                .map(el => ({
                    text: el.innerText.substring(0, 50),
                    x: el.getBoundingClientRect().x + el.getBoundingClientRect().width/2,
                    y: el.getBoundingClientRect().y + el.getBoundingClientRect().height/2
                }))
        """)
        if all_cards:
            fc = all_cards[0]
            print(f"\nClicando primer card: {fc['text'][:40]} ({fc['x']:.0f},{fc['y']:.0f})")
            pv.mouse.click(fc['x'], fc['y'])
            pv.wait_for_timeout(3000)
            ss(pv, "06_player")

        # Descargar
        print("Buscando src del vídeo...")
        src = None
        for _ in range(15):
            src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
            if src and len(src) > 10: break
            pv.wait_for_timeout(1000)

        if src:
            print(f"src: {src[:80]}")
            out = OUT_DIR / "clip1.mp4"
            cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
            ua = pv.evaluate("() => navigator.userAgent")
            r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=120)
            if r.status_code == 200:
                out.write_bytes(r.content)
                print(f"Guardado: {out.name} ({out.stat().st_size//1024}KB)")
            else:
                print(f"Error descarga: {r.status_code}")
        else:
            print("[WARN] No se encontró video src — verificar screenshot 06_player")
            print("  El vídeo puede estar ahí pero no en el player todavía")

if __name__ == "__main__":
    run()
