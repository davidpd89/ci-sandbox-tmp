"""
Descarga los clips ya generados en el proyecto Flow.
Los clips están en el panel izquierdo como thumbnails — hay que hacer clic en cada uno
para abrir el preview con <video> y descargar desde el src.
"""
import sys, io, time, base64
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
PROJECT_URL = "https://labs.google/fx/es/tools/flow/project/df4adbe8-1c2c-4578-b3b8-527985ec3850"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/dl_{name}.png")
    print(f"  [ss] C:/Temp/dl_{name}.png")

def get_video_src(page):
    """Intenta obtener el src de un <video> en la página."""
    for _ in range(20):
        src = page.evaluate("""
            () => {
                const vs = document.querySelectorAll('video');
                for (const v of vs) {
                    const s = v.src || v.currentSrc || '';
                    if (s && s.length > 10) return s;
                }
                return null;
            }
        """)
        if src:
            return src
        page.wait_for_timeout(1000)
    return None

def download_from_src(page, src, path: Path):
    print(f"  Descargando de: {src[:80]}...")
    if src.startswith("blob:"):
        b64 = page.evaluate("""
            async (u) => {
                const r = await fetch(u);
                const buf = await r.arrayBuffer();
                const b = new Uint8Array(buf);
                let s = ''; for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
                return btoa(s);
            }
        """, src)
        path.write_bytes(base64.b64decode(b64))
    elif src.startswith("http"):
        import urllib.request
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(src, headers=headers)
        with urllib.request.urlopen(req) as resp:
            path.write_bytes(resp.read())
    else:
        print(f"  [WARN] src no reconocido: {src[:60]}")
        return False
    kb = path.stat().st_size // 1024
    print(f"  Guardado: {path.name} ({kb} KB)")
    return kb > 50

def try_download_button(page, path: Path):
    """Intenta usar el botón de descarga de Flow."""
    for sel in [
        "button[aria-label*='Descargar']", "button[aria-label*='download']",
        "button[aria-label*='Download']", "a[download]",
        "button:has(svg[data-icon='download'])",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                with page.expect_download(timeout=30000) as dl_info:
                    btn.click()
                dl = dl_info.value
                dl.save_as(path)
                kb = path.stat().st_size // 1024
                print(f"  Descargado via botón: {path.name} ({kb} KB)")
                return kb > 50
        except Exception:
            continue
    return False

def get_trpc_video_url(page):
    """Busca URLs de vídeo del tipo /fx/api/trpc/media.getMediaUrlRedirect..."""
    urls = page.evaluate("""
        () => {
            const links = [];
            // Buscar en todos los elementos src
            document.querySelectorAll('[src]').forEach(el => {
                const s = el.src || el.getAttribute('src') || '';
                if (s.includes('trpc') || s.includes('media') || s.includes('.mp4')) links.push(s);
            });
            // También en XHR/fetch cache si existe
            return links.slice(0, 10);
        }
    """)
    return urls

def run():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        b.contexts[0].grant_permissions(["clipboard-read", "clipboard-write"])
        all_pages = [pg for c in b.contexts for pg in c.pages]
        flow = next(pg for pg in all_pages if "labs.google" in pg.url)
        flow.bring_to_front()

        # Ir al proyecto si no estamos ya
        if PROJECT_URL.rstrip("/") not in flow.url.rstrip("/"):
            flow.goto(PROJECT_URL)
            flow.wait_for_load_state("networkidle", timeout=20000)

        flow.wait_for_timeout(3000)
        ss(flow, "01_project")

        # Contar thumbnails de contenido en el panel izquierdo
        # Flow muestra los clips como tarjetas/thumbnails
        # Buscar cualquier elemento clickeable que represente un clip generado
        thumbnails_info = flow.evaluate("""
            () => {
                // Buscar por src de video/imagen dentro de tarjetas
                const cards = document.querySelectorAll('[role="button"], [role="gridcell"], .thumbnail, [class*="card"], [class*="item"]');
                const result = [];
                cards.forEach((c, i) => {
                    const img = c.querySelector('img');
                    const src = img ? img.src : '';
                    const bb = c.getBoundingClientRect();
                    if (bb.width > 50 && bb.height > 50 && bb.top > 0) {
                        result.push({idx: i, src: src.substring(0, 80), x: bb.x + bb.width/2, y: bb.y + bb.height/2});
                    }
                });
                return result.slice(0, 20);
            }
        """)
        print(f"\nElementos clickeables encontrados: {len(thumbnails_info)}")
        for t in thumbnails_info[:10]:
            print(f"  [{t['idx']}] x={t['x']:.0f} y={t['y']:.0f} src={t['src'][:50]}")

        # Estrategia alternativa: buscar directamente imágenes en el panel izquierdo
        # que podrían ser thumbnails de los clips
        left_imgs = flow.evaluate("""
            () => {
                const imgs = Array.from(document.querySelectorAll('img'));
                return imgs
                    .filter(img => {
                        const bb = img.getBoundingClientRect();
                        return bb.width > 50 && bb.height > 50;
                    })
                    .map(img => {
                        const bb = img.getBoundingClientRect();
                        return {src: img.src.substring(0,80), x: bb.x + bb.width/2, y: bb.y + bb.height/2, w: bb.width, h: bb.height};
                    });
            }
        """)
        print(f"\nImágenes visibles en página: {len(left_imgs)}")
        for img in left_imgs[:15]:
            print(f"  x={img['x']:.0f} y={img['y']:.0f} {img['w']:.0f}x{img['h']:.0f} src={img['src'][:60]}")

        # Intentar hacer clic en cada imagen grande para ver si abre un vídeo
        video_srcs = []
        for i, img_info in enumerate(left_imgs[:10]):
            print(f"\n--- Clic en imagen {i+1} (x={img_info['x']:.0f}, y={img_info['y']:.0f}) ---")
            flow.mouse.click(img_info['x'], img_info['y'])
            flow.wait_for_timeout(2000)
            ss(flow, f"02_click_img{i+1}")

            src = get_video_src(flow)
            if src:
                print(f"  Video src: {src[:80]}...")
                video_srcs.append(src)
            else:
                # Buscar URLs de trpc
                urls = get_trpc_video_url(flow)
                if urls:
                    print(f"  URLs de media: {urls}")
                    video_srcs.extend(urls)
                else:
                    print(f"  No se encontró video en este elemento")

            # Cerrar preview si se abrió (Escape)
            flow.keyboard.press("Escape")
            flow.wait_for_timeout(1000)

        print(f"\n=== VIDEO SRCS ENCONTRADOS: {len(video_srcs)} ===")
        for s in video_srcs:
            print(f"  {s[:100]}")

        # Descargar los que encontramos
        for i, src in enumerate(video_srcs[:5], 1):
            cp = OUT_DIR / f"clip{i}.mp4"
            if cp.exists() and cp.stat().st_size > 50000:
                print(f"  clip{i}: ya existe")
                continue
            ok = download_from_src(flow, src, cp)
            if not ok:
                print(f"  clip{i}: FALLO")

        print("\n=== RESUMEN ===")
        for i in range(1, 6):
            cp = OUT_DIR / f"clip{i}.mp4"
            ok = cp.exists() and cp.stat().st_size > 50000
            print(f"  clip{i}: {'✓' if ok else '✗'} ({cp.stat().st_size//1024 if cp.exists() else 0} KB)")

if __name__ == "__main__":
    run()
