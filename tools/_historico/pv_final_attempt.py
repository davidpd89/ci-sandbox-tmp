"""
Intento definitivo:
1. Escape para cerrar popup existente
2. Mouse click en coordenadas exactas del textarea (no locator, bypasa overlays)
3. Type prompt
4. Mouse click en Crear button por coordenadas
5. Si popup aparece: detectarlo y cerrarlo con Escape
6. Verificar créditos, esperar generación, descargar
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
    "A woman in her 30s sits at night, warm lamp light, holding a worn paperback (no visible title). "
    "She opens it slowly. In the dark window, a fleeting reflection of her teenage self appears, like a memory. "
    "She pauses and touches the page softly. Multi-shot: face close-up, reflection in window, book in hands. "
    "Photorealistic, emotional, warm light, no text, no logos."
)

def ss(pv, name):
    pv.screenshot(path=f"C:/Temp/pfa_{name}.png")

def get_creds(pv):
    return pv.evaluate("""
        () => { for (const el of document.querySelectorAll('*')) {
            const t = (el.innerText||'').trim();
            if (/^\d+$/.test(t) && +t>=0 && +t<=200) {
                const bb = el.getBoundingClientRect();
                if (bb.x>1400 && bb.y<60) return t; }} return null; }
    """)

def popup_open(pv):
    return pv.evaluate("""
        () => !!Array.from(document.querySelectorAll('*')).find(
            e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar'))
    """)

def close_popup(pv):
    """Cierra el popup con Escape."""
    for _ in range(3):
        pv.keyboard.press("Escape")
        pv.wait_for_timeout(600)
        if not popup_open(pv):
            return True
    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()

    # Cerrar cualquier popup
    if popup_open(pv):
        print("Popup abierto al inicio — cerrando...")
        close_popup(pv)
    pv.wait_for_timeout(500)

    creds = get_creds(pv)
    print(f"Créditos: {creds}")

    # Encontrar coordenadas exactas del textarea
    ta_info = pv.evaluate("""
        () => {
            const tas = Array.from(document.querySelectorAll('textarea')).filter(t => t.offsetParent !== null);
            if (!tas.length) return null;
            const ta = tas.find(t => t.placeholder && t.placeholder.includes('Describ')) || tas[0];
            const bb = ta.getBoundingClientRect();
            return {x: bb.x + bb.width/2, y: bb.y + bb.height/2, placeholder: ta.placeholder.substring(0,30)};
        }
    """)
    print(f"Textarea: {ta_info}")
    ss(pv, "00_clean")

    if not ta_info:
        print("[ERROR] No se encontró textarea visible"); sys.exit(1)

    # === MOUSE CLICK DIRECTO en el textarea ===
    print(f"\nClick en textarea ({ta_info['x']:.0f}, {ta_info['y']:.0f})...")
    pv.mouse.click(ta_info['x'], ta_info['y'])
    pv.wait_for_timeout(400)

    # Seleccionar todo y borrar
    pv.keyboard.press("Control+A")
    pv.keyboard.press("Delete")
    pv.wait_for_timeout(200)

    # Type el prompt
    print(f"Escribiendo {len(PROMPT)} chars...")
    pv.keyboard.type(PROMPT, delay=8)
    pv.wait_for_timeout(600)

    val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''")
    print(f"Valor textarea: {val}")
    ss(pv, "01_typed")

    # Encontrar coordenadas del botón Crear
    crear_info = pv.evaluate("""
        () => {
            const btns = Array.from(document.querySelectorAll('button'));
            const crear = btns.find(b => /crear|create/i.test(b.innerText) && b.offsetParent);
            if (!crear) return null;
            const bb = crear.getBoundingClientRect();
            return {x: bb.x + bb.width/2, y: bb.y + bb.height/2, text: crear.innerText.trim()};
        }
    """)
    print(f"Botón Crear: {crear_info}")

    # === MOUSE CLICK DIRECTO en Crear ===
    creds_before = get_creds(pv)
    if crear_info:
        print(f"\nClick en Crear ({crear_info['x']:.0f}, {crear_info['y']:.0f})...")
        pv.mouse.click(crear_info['x'], crear_info['y'])
    else:
        # Fallback: coordenadas conocidas del inspect (x=1489, y=902)
        pv.mouse.click(1489, 902)
        print("Click en Crear por coordenada fallback (1489, 902)")

    pv.wait_for_timeout(3000)
    ss(pv, "02_after_crear")

    # Manejar popup si aparece
    if popup_open(pv):
        print("Popup apareció → cerrando con Escape...")
        ss(pv, "02b_popup")

        # Leer el contenido completo del popup para buscar close button
        popup_content = pv.evaluate("""
            () => {
                // Buscar el modal específico
                const allEls = Array.from(document.querySelectorAll('*'));
                const modal = allEls.find(e => e.offsetParent && (e.innerText||'').includes('Suscríbete para ahorrar') && e.tagName !== 'HTML' && e.tagName !== 'BODY');
                if (!modal) return null;
                // Buscar el botón de close dentro o cerca del modal
                const allBtns = Array.from(modal.querySelectorAll('button, [role="button"]'));
                const closeBtns = allBtns.map(b => ({
                    text: b.innerText.trim().substring(0,10),
                    x: b.getBoundingClientRect().x,
                    y: b.getBoundingClientRect().y,
                    w: b.getBoundingClientRect().width,
                    h: b.getBoundingClientRect().height,
                    html: b.outerHTML.substring(0,100)
                }));
                return {closeBtns, modalClass: modal.className.substring(0,50)};
            }
        """)
        print(f"Popup content: {popup_content}")

        # Intentar cerrar
        closed = close_popup(pv)
        if closed:
            print("Popup cerrado con Escape")
        else:
            print("Popup NO cerrado — probando click fuera del modal")
            pv.mouse.click(100, 100)  # Clic fuera del modal
            pv.wait_for_timeout(500)
            if not popup_open(pv):
                print("Popup cerrado con click fuera")

    creds_after = get_creds(pv)
    print(f"Créditos: {creds_before} → {creds_after}")

    # Esperar
    print("\nEsperando generación (3 min)...")
    start = time.time()
    while time.time() - start < 180:
        pv.wait_for_timeout(5000)
        cur = get_creds(pv)
        elapsed = int(time.time()-start)
        print(f"  {elapsed}s cr={cur}", end="\r")
        if cur and creds_before and int(cur or 99) < int(creds_before or 0):
            print(f"\n  ¡Generando!")
            break
    print()
    ss(pv, "03_wait")

    final_creds = get_creds(pv)
    print(f"Créditos finales: {final_creds}")

    # Descargar
    cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"]'))
            .filter(el => { const bb = el.getBoundingClientRect(); return bb.y > 100 && bb.width > 200; })
            .slice(0,3).map(el => ({
                x: el.getBoundingClientRect().x + el.getBoundingClientRect().width/2,
                y: el.getBoundingClientRect().y + el.getBoundingClientRect().height/2,
                text: el.innerText.substring(0,40)
            }))
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
            out = OUT_DIR / "clip1.mp4"
            if r.status_code == 200 and len(r.content) > 50000:
                out.write_bytes(r.content)
                dur = pv.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration : null; }")
                print(f"✓ {out.name} ({out.stat().st_size//1024}KB) {dur}s")
            else:
                print(f"  Error: {r.status_code} {len(r.content)//1024}KB")
        else:
            print("  No src")

    ss(pv, "99_final")
