"""
Descarga los clips de Flow haciendo clic en cada thumbnail y luego en el botón de descarga.
También intenta capturar el content-type para confirmar si son imágenes o vídeos.
"""
import sys, io, base64, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
PROJECT_URL = "https://labs.google/fx/es/tools/flow/project/df4adbe8-1c2c-4578-b3b8-527985ec3850"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/btn_{name}.png")

def download_with_cookies(flow, url: str, path: Path):
    """Obtiene cookies del browser y descarga usando requests."""
    import requests
    cookies = flow.context.cookies()
    jar = {c['name']: c['value'] for c in cookies if 'google' in c.get('domain', '')}
    headers = {
        "User-Agent": flow.evaluate("() => navigator.userAgent"),
        "Referer": "https://labs.google/",
    }
    print(f"  cookies: {len(jar)}, url: {url[:60]}")
    try:
        r = requests.get(url, cookies=jar, headers=headers, allow_redirects=True, timeout=60)
        print(f"  status={r.status_code} ct={r.headers.get('content-type','?')[:40]} size={len(r.content)//1024}KB url={r.url[:60]}")
        if r.status_code == 200 and len(r.content) > 10000:
            path.write_bytes(r.content)
            return True
    except Exception as e:
        print(f"  requests error: {e}")
    return False

def run():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        ctx = b.contexts[0]
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        all_pages = [pg for c in b.contexts for pg in c.pages]
        flow = next(pg for pg in all_pages if "labs.google" in pg.url)
        flow.bring_to_front()

        # Navegar al proyecto
        if PROJECT_URL.rstrip("/") not in flow.url.rstrip("/"):
            flow.goto(PROJECT_URL)
            flow.wait_for_load_state("networkidle", timeout=20000)
        flow.wait_for_timeout(2000)
        ss(flow, "00_project")

        # Encontrar los thumbnails en el panel principal (las 4 imágenes 225x400)
        thumb_coords = flow.evaluate("""
            () => {
                return Array.from(document.querySelectorAll('img'))
                    .filter(img => {
                        const bb = img.getBoundingClientRect();
                        return Math.abs(bb.width - 225) < 30 && bb.height > 300 && bb.y > 0 && bb.y < 500;
                    })
                    .map(img => {
                        const bb = img.getBoundingClientRect();
                        const fullSrc = img.src;
                        return {x: bb.x + bb.width/2, y: bb.y + bb.height/2, src: fullSrc};
                    });
            }
        """)
        print(f"\nThumbnails encontrados: {len(thumb_coords)}")
        for i, t in enumerate(thumb_coords):
            print(f"  [{i+1}] x={t['x']:.0f} y={t['y']:.0f} src={t['src'][-60:]}")

        # Para cada thumbnail: hacer clic, capturar descarga o guardar desde URL
        for i, thumb in enumerate(thumb_coords, 1):
            cp_img = OUT_DIR / f"clip{i}.jpg"
            cp_vid = OUT_DIR / f"clip{i}.mp4"
            if (cp_img.exists() and cp_img.stat().st_size > 5000) or (cp_vid.exists() and cp_vid.stat().st_size > 5000):
                print(f"\nclip{i}: ya existe")
                continue

            print(f"\n=== clip{i} ===")

            # Intentar descargar directamente por URL usando cookies del browser
            src_url = thumb['src']
            # Quitar el thumbnail size param si existe
            base_url = src_url.split('?')[0] + '?' + '&'.join(
                p for p in src_url.split('?')[1].split('&') if not p.startswith('w=') and not p.startswith('h=')
            ) if '?' in src_url else src_url

            ok = download_with_cookies(flow, base_url, cp_img)
            if ok:
                # Verificar si es imagen o vídeo por la extensión del content-type
                if cp_img.read_bytes()[:4] == b'\x00\x00\x00\x1c' or cp_img.read_bytes()[:4] == b'ftyp':
                    # Es MP4
                    cp_vid = OUT_DIR / f"clip{i}.mp4"
                    cp_img.rename(cp_vid)
                    print(f"  Es MP4! Renombrado a {cp_vid.name}")
                else:
                    print(f"  Guardado como imagen: {cp_img.name}")
                continue

            # Fallback: hacer clic en el thumbnail y buscar botón de descarga
            print(f"  Haciendo clic en thumbnail...")
            flow.mouse.click(thumb['x'], thumb['y'])
            flow.wait_for_timeout(2000)
            ss(flow, f"click_{i}")

            # Buscar botón de descarga
            for btn_sel in [
                "button[aria-label*='Descargar']", "button[aria-label*='Download']",
                "button[aria-label*='download']", "button[title*='Descargar']",
                "button[title*='Download']", "[data-testid*='download']",
                "button:has(svg[aria-label*='download'])",
            ]:
                try:
                    btn = flow.locator(btn_sel).first
                    if btn.is_visible(timeout=1500):
                        print(f"  Botón descarga: {btn_sel}")
                        with flow.expect_download(timeout=30000) as dl_info:
                            btn.click()
                        dl = dl_info.value
                        save_path = OUT_DIR / f"clip{i}{Path(dl.suggested_filename).suffix}"
                        dl.save_as(save_path)
                        print(f"  Descargado: {save_path.name} ({save_path.stat().st_size//1024}KB)")
                        break
                except Exception:
                    continue

            # Si llegamos aquí sin download, inspeccionar los elementos de la pantalla
            els = flow.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('button, a[href]'));
                    return btns.filter(b => b.offsetParent !== null)
                               .map(b => ({text: b.innerText.substring(0,30), aria: b.getAttribute('aria-label') || '',
                                          title: b.getAttribute('title') || ''}))
                               .filter(b => b.text || b.aria || b.title)
                               .slice(0, 20);
                }
            """)
            print(f"  Botones visibles: {els[:10]}")

            flow.keyboard.press("Escape")
            flow.wait_for_timeout(1000)

        print("\n=== RESUMEN ===")
        for i in range(1, 6):
            for ext in ['mp4', 'jpg', 'png', 'webm']:
                cp = OUT_DIR / f"clip{i}.{ext}"
                if cp.exists():
                    print(f"  clip{i}.{ext}: ✓ {cp.stat().st_size//1024}KB")
                    break
            else:
                print(f"  clip{i}: ✗")

if __name__ == "__main__":
    run()
