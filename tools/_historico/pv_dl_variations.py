"""
Descarga las 4 variaciones Multi-Toma de PixVerse como clip2, clip3, clip4.
Estamos ya en la vista de detalle del vídeo con 4 thumbnails en panel derecho.
Usa el botón 'Descargar' para cada variación.
"""
import sys, io, time, requests
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\04-resaca-libro")

def get_video_src(pv):
    for _ in range(10):
        src = pv.evaluate("() => { const v = document.querySelector('video'); return v ? (v.src||v.currentSrc) : null; }")
        if src and len(src) > 10: return src
        pv.wait_for_timeout(500)
    return None

def download_current(pv, cookies, ua, out_path):
    src = get_video_src(pv)
    if not src:
        print(f"  [WARN] No src")
        return False
    print(f"  src: {src[:70]}")
    r = requests.get(src, cookies=cookies, headers={"User-Agent": ua, "Referer": "https://app.pixverse.ai/"}, timeout=60)
    if r.status_code == 200:
        out_path.write_bytes(r.content)
        print(f"  ✓ {out_path.name} ({out_path.stat().st_size//1024}KB)")
        return True
    print(f"  Error {r.status_code}")
    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    ctx = b.contexts[0]
    pv = next(pg for pg in [x for c in b.contexts for x in c.pages] if "pixverse" in pg.url)
    pv.bring_to_front()

    cookies = {c['name']: c['value'] for c in ctx.cookies() if 'pixverse' in c.get('domain', '')}
    ua = pv.evaluate("() => navigator.userAgent")

    pv.screenshot(path="C:/Temp/pvvar_start.png")

    # Buscar los thumbnails de variaciones en el panel derecho
    thumbnails = pv.evaluate("""
        () => {
            // Las miniaturas de variaciones están en el panel derecho (~x>850)
            const imgs = Array.from(document.querySelectorAll('img, [class*="thumbnail"], video'));
            return imgs
                .filter(el => {
                    const bb = el.getBoundingClientRect();
                    return bb.x > 850 && bb.width > 40 && bb.height > 40 && bb.width < 200;
                })
                .map(el => ({
                    tag: el.tagName,
                    src: el.src ? el.src.substring(0,60) : '',
                    x: el.getBoundingClientRect().x,
                    y: el.getBoundingClientRect().y,
                    w: el.getBoundingClientRect().width,
                    h: el.getBoundingClientRect().height
                }));
        }
    """)
    print(f"Thumbnails panel derecho: {len(thumbnails)}")
    for t in thumbnails[:6]:
        print(f"  {t['tag']} x={t['x']:.0f} y={t['y']:.0f} {t['w']:.0f}x{t['h']:.0f}")

    # Descargar la variación actual (la que está en el player)
    print("\n=== Variación actual (clip2 o la que muestra el player) ===")
    current_src = get_video_src(pv)
    print(f"Video actual src: {current_src[:80] if current_src else 'None'}")

    # Si no es la misma que clip1, guardarla como clip2
    existing_clip1 = OUT_DIR / "clip1.mp4"
    clip1_size = existing_clip1.stat().st_size if existing_clip1.exists() else 0

    for i, clip_name in enumerate(["clip2.mp4", "clip3.mp4"], start=1):
        out = OUT_DIR / clip_name
        if out.exists() and out.stat().st_size > 10000:
            print(f"\n{clip_name}: ya existe")
            continue

        print(f"\n=== {clip_name} ===")
        # Clicar en el i-ésimo thumbnail del panel derecho
        if thumbnails and i <= len(thumbnails):
            t = thumbnails[i-1]
            cx = t['x'] + t['w']/2
            cy = t['y'] + t['h']/2
            print(f"  Clic en thumbnail {i} ({cx:.0f}, {cy:.0f})")
            pv.mouse.click(cx, cy)
            pv.wait_for_timeout(2000)
        elif i == 1 and current_src:
            # Usar el vídeo actual directamente
            pass
        else:
            print(f"  No hay thumbnail {i}")
            continue

        pv.screenshot(path=f"C:/Temp/pvvar_{clip_name}.png")
        download_current(pv, cookies, ua, out)

    print("\n=== RESUMEN ===")
    for name in ["clip1.mp4", "clip2.mp4", "clip3.mp4"]:
        f = OUT_DIR / name
        print(f"  {name}: {'✓' if f.exists() and f.stat().st_size > 10000 else '✗'} ({f.stat().st_size//1024 if f.exists() else 0}KB)")
