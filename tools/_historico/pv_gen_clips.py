"""Genera clip2 y clip3 para DP-F0-071 en PixVerse. 20cr cada uno."""
import sys, io, time, requests, base64
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\04-resaca-libro")

CLIPS = [
    {
        "name": "clip2.mp4",
        "prompt": (
            "A closed book lying alone on a wooden coffee table or nightstand, late at night, "
            "warm bedside lamp illuminating the cover (no visible text on cover), "
            "a half-empty mug nearby, quiet and still atmosphere, "
            "cinematic still life, shallow depth of field, no people, "
            "9:16 vertical, photorealistic."
        )
    },
    {
        "name": "clip3.mp4",
        "prompt": (
            "Wide shot: a young woman lying on a couch, staring at a closed book on the coffee table "
            "in front of her. She is not reaching for it, just looking at it with a quiet, "
            "unresolved expression. Warm lamp light. The book is closed. Room is calm and dim. "
            "Realistic emotion, no drama, domestic night scene. "
            "9:16 vertical, cinematic, photorealistic."
        )
    }
]

def get_pv_page(b):
    return next(pg for pg in [x for c in b.contexts for x in c.pages] if "pixverse" in pg.url)

def get_video_src(pv):
    for _ in range(15):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10:
            return src
        pv.wait_for_timeout(1000)
    return None

def wait_new_card(pv, before_text):
    """Espera a que aparezca un nuevo card en la galería."""
    start = time.time()
    while time.time() - start < 300:
        pv.wait_for_timeout(5000)
        cards = pv.evaluate("""
            () => Array.from(document.querySelectorAll('[class*="card"], [class*="item"]'))
                .filter(el => el.getBoundingClientRect().y > 150 && el.getBoundingClientRect().width > 200)
                .map(el => el.innerText.substring(0, 50))
        """)
        # Si hay un card nuevo con diferente texto al primero anterior
        if cards and cards[0] != before_text:
            print(f"\n  Nuevo card: {cards[0][:40]}")
            return True
        elapsed = int(time.time()-start)
        print(f"  {elapsed}s esperando nuevo card...", end="\r")
    return False

def download_current_video(pv, cookies, ua, out_path):
    """Descarga el vídeo actualmente en el player."""
    src = get_video_src(pv)
    if not src:
        # Intentar clicar el primer card
        pv.mouse.click(374, 362)
        pv.wait_for_timeout(2000)
        src = get_video_src(pv)

    if not src:
        print("  [WARN] No se encontró src")
        return False

    print(f"  src: {src[:70]}")
    r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, stream=True, timeout=60)
    if r.status_code == 200:
        out_path.write_bytes(r.content)
        print(f"  Guardado: {out_path.name} ({out_path.stat().st_size//1024}KB)")
        return True
    print(f"  Error: {r.status_code}")
    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    pv = get_pv_page(b)
    pv.bring_to_front()

    # Leer cookies y UA
    cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
    ua = pv.evaluate("() => navigator.userAgent")

    # Leer estado inicial de los cards
    initial_cards = pv.evaluate("""
        () => Array.from(document.querySelectorAll('[class*="card"], [class*="item"]'))
            .filter(el => el.getBoundingClientRect().y > 150 && el.getBoundingClientRect().width > 200)
            .map(el => el.innerText.substring(0, 50))
    """)
    print(f"Cards iniciales: {initial_cards[:3]}")

    for clip_info in CLIPS:
        out = OUT_DIR / clip_info["name"]
        if out.exists() and out.stat().st_size > 10000:
            print(f"\n{clip_info['name']}: ya existe")
            continue

        print(f"\n=== Generando {clip_info['name']} ===")

        # Limpiar textarea y escribir prompt
        pv.evaluate("""
            () => {
                const ta = document.querySelector('textarea.w-full') || document.querySelector('textarea');
                if (ta) { ta.focus(); ta.value = ''; ta.dispatchEvent(new Event('input')); }
            }
        """)
        pv.wait_for_timeout(300)
        pv.evaluate("(t) => navigator.clipboard.writeText(t)", clip_info["prompt"])
        pv.keyboard.press("Control+A")
        pv.keyboard.press("Control+V")
        pv.wait_for_timeout(800)

        val = pv.evaluate("() => (document.querySelector('textarea.w-full') || document.querySelector('textarea'))?.value || ''")
        print(f"  Prompt: {val[:50]}...")

        # Obtener texto del primer card antes de generar
        first_card_before = initial_cards[0] if initial_cards else ""

        # Clicar Crear
        crear = pv.locator("button:has-text('Crear'), button:has-text('Create')").first
        crear.click()
        print("  Crear pulsado, esperando generación...")
        pv.wait_for_timeout(2000)
        pv.screenshot(path=f"C:/Temp/pvgen_{clip_info['name']}.png")

        # Esperar a que aparezca nuevo card
        found = wait_new_card(pv, first_card_before)
        pv.wait_for_timeout(2000)

        # Clicar el primer card (el más nuevo)
        pv.mouse.click(374, 362)
        pv.wait_for_timeout(3000)

        # Descargar
        download_current_video(pv, cookies, ua, out)

        # Actualizar la lista de cards para la siguiente iteración
        initial_cards = pv.evaluate("""
            () => Array.from(document.querySelectorAll('[class*="card"], [class*="item"]'))
                .filter(el => el.getBoundingClientRect().y > 150 && el.getBoundingClientRect().width > 200)
                .map(el => el.innerText.substring(0, 50))
        """)

    print("\n=== RESUMEN ===")
    for clip_info in CLIPS:
        out = OUT_DIR / clip_info["name"]
        print(f"  {clip_info['name']}: {'✓' if out.exists() and out.stat().st_size > 10000 else '✗'}")
