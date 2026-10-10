"""
DP-F0-075: "Llegué tarde por una escena" — parada de bus.
Cierra popup X, llena textarea, crea video 4s/16cr.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\07-tarde-por-una-escena")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "9:16 vertical video, 5 seconds, cinematic photorealism, daytime urban bus stop. "
    "A young woman sits on a bench reading a paperback novel with no visible title. "
    "Casual clothes, backpack beside her. A city bus arrives, opens doors, people board. "
    "She stays completely absorbed reading, turns a page with total concentration. "
    "Bus closes doors and pulls away. She finally looks up, sees the bus leaving, "
    "freezes a second, then looks back at the book with a slight 'worth it' smile. "
    "Natural light, realistic movement, subtle humor, urban life, no text in image, no logos."
)

def ss(pv, name):
    pv.screenshot(path=f"C:/Temp/bus_{name}.png")

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

def close_popup_x(pv):
    """Cierra el popup con la X visible en ~(1028, 96)."""
    for x, y in [(1028, 96), (1030, 93), (1025, 98), (1033, 91), (1026, 95)]:
        pv.mouse.click(x, y)
        pv.wait_for_timeout(400)
        if not popup_open(pv):
            print(f"  Popup cerrado en ({x},{y})")
            return True
    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next(pg for pg in all_pages if "pixverse" in pg.url)
    pv.bring_to_front()
    pv.wait_for_timeout(500)

    if popup_open(pv):
        print("Popup abierto — cerrando X...")
        close_popup_x(pv)

    creds = get_creds(pv)
    print(f"Créditos: {creds}")
    ss(pv, "00_clean")

    # Buscar coordenadas exactas del textarea
    ta = pv.evaluate("""
        () => {
            const tas = Array.from(document.querySelectorAll('textarea')).filter(t => t.offsetParent !== null);
            const ta = tas.find(t => (t.placeholder||'').includes('Describ')) || tas[0];
            if (!ta) return null;
            const bb = ta.getBoundingClientRect();
            return {x: bb.x + bb.width/2, y: bb.y + bb.height/2};
        }
    """)
    print(f"Textarea en: {ta}")

    if ta:
        # Clic directo en coordenadas del textarea
        pv.mouse.click(ta['x'], ta['y'])
        pv.wait_for_timeout(300)
        pv.keyboard.press("Control+A")
        pv.keyboard.press("Delete")
        pv.wait_for_timeout(200)
        # Type del prompt (dispara React onChange)
        pv.keyboard.type(PROMPT, delay=7)
        pv.wait_for_timeout(500)

    val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value?.substring(0,60) || ''")
    print(f"Prompt: {val}")
    ss(pv, "01_prompt")

    # Botón Crear por coordenadas exactas
    btn = pv.evaluate("""
        () => { const bs = document.querySelectorAll('button');
            for (const b of bs) if (/crear|create/i.test(b.innerText) && b.offsetParent) return b.innerText.trim();
            return null; }
    """)
    print(f"Botón: '{btn}'")

    creds_before = get_creds(pv)
    print(f"Clicando Crear (cr={creds_before})...")
    pv.mouse.click(1492, 911)
    pv.wait_for_timeout(3000)
    ss(pv, "02_after_crear")

    # Si popup → cerrar X
    if popup_open(pv):
        print("Popup apareció → cerrando X (1028, 96)...")
        ss(pv, "02b_popup")
        closed = close_popup_x(pv)
        print(f"  Cerrado: {closed}")
        if not closed:
            # Probar clic en (1028, 96) directamente aunque no detecte cierre
            pv.mouse.click(1028, 96)
            pv.wait_for_timeout(500)

    pv.wait_for_timeout(1000)
    creds_after = get_creds(pv)
    print(f"Créditos: {creds_before} → {creds_after}")

    if creds_after == creds_before:
        print("[WARN] Créditos no bajaron")

    # Esperar generación
    print("Esperando generación (3 min)...")
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
    final = get_creds(pv)
    print(f"Créditos finales: {final}")

    # Descargar
    cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"]'))
            .filter(el => { const bb = el.getBoundingClientRect(); return bb.y > 100 && bb.width > 200; })
            .slice(0,3).map(el => ({x: el.getBoundingClientRect().x+el.getBoundingClientRect().width/2,
                                    y: el.getBoundingClientRect().y+el.getBoundingClientRect().height/2,
                                    text: el.innerText.substring(0,30)}))
    """)
    print(f"Cards: {[c['text'][:20] for c in cards]}")

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
                print(f"Error: {r.status_code} {len(r.content)//1024}KB")
        else:
            print("No src")
    ss(pv, "99_final")
