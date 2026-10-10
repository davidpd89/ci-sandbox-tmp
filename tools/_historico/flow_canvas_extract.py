"""
Extrae las imágenes de Flow usando canvas — las imágenes ya están cargadas en el browser.
Para cada clip: clic en thumbnail → imagen grande en pantalla → canvas → base64 → guardar.
"""
import sys, io, base64
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
PROJECT_URL = "https://labs.google/fx/es/tools/flow/project/df4adbe8-1c2c-4578-b3b8-527985ec3850"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo\images")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Los 4 thumbnails identificados
THUMBS = [
    (356, 276, "img1_kindle_nightstand"),
    (598, 276, "img2_hand_kindle"),
    (838, 276, "img3_bookshelf"),
    (1080, 276, "img4_person_reading"),
]

def ss(page, name):
    page.screenshot(path=f"C:/Temp/canvas_{name}.png")

def extract_main_image(flow, out_path: Path):
    """Intenta extraer la imagen grande visible en el preview vía canvas."""
    # Buscar la imagen más grande visible en la pantalla
    result = flow.evaluate("""
        () => {
            const imgs = Array.from(document.querySelectorAll('img'));
            // Ordenar por tamaño descendente
            const sorted = imgs
                .filter(img => img.naturalWidth > 100 && img.naturalHeight > 100)
                .sort((a, b) => (b.naturalWidth * b.naturalHeight) - (a.naturalWidth * a.naturalHeight));

            if (!sorted.length) return {error: 'No images found'};

            const img = sorted[0];
            console.log('Using img:', img.src.substring(0, 50), img.naturalWidth, 'x', img.naturalHeight);

            try {
                const canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
                return {b64: dataUrl.split(',')[1], w: img.naturalWidth, h: img.naturalHeight, src: img.src.substring(0,60)};
            } catch(e) {
                // Canvas taint error — imagen con CORS restrictivo
                return {error: 'Canvas tainted: ' + e.message, src: img.src.substring(0,60), w: img.naturalWidth, h: img.naturalHeight};
            }
        }
    """)

    if 'error' in result:
        print(f"  Canvas error: {result['error']} | src: {result.get('src','?')}")
        return False

    b64 = result.get('b64', '')
    if not b64:
        print(f"  Sin datos b64")
        return False

    img_bytes = base64.b64decode(b64)
    out_path.write_bytes(img_bytes)
    print(f"  Guardado: {out_path.name} ({len(img_bytes)//1024}KB) {result['w']}x{result['h']}px")
    return True

def run():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        ctx = b.contexts[0]
        all_pages = [pg for c in b.contexts for pg in c.pages]
        flow = next(pg for pg in all_pages if "labs.google" in pg.url)
        flow.bring_to_front()

        if PROJECT_URL.rstrip("/") not in flow.url.rstrip("/"):
            flow.goto(PROJECT_URL)
            flow.wait_for_load_state("networkidle", timeout=20000)
        flow.wait_for_timeout(2000)

        for x, y, name in THUMBS:
            out_jpg = OUT_DIR / f"{name}.jpg"
            if out_jpg.exists() and out_jpg.stat().st_size > 10000:
                print(f"{name}: ya existe")
                continue

            print(f"\n{name}: clic en ({x},{y})")
            flow.mouse.click(x, y)
            flow.wait_for_timeout(3000)
            ss(flow, f"{name}_preview")

            ok = extract_main_image(flow, out_jpg)

            if not ok:
                # Fallback: screenshot de la zona visible
                ss_path = OUT_DIR / f"{name}_screenshot.png"
                # Capturar solo la zona del preview (center area)
                clip_area = {"x": 80, "y": 0, "width": 1300, "height": 780}
                flow.screenshot(path=str(ss_path), clip=clip_area)
                print(f"  Fallback screenshot: {ss_path.name}")

            # Volver al proyecto
            try:
                back = flow.locator("button:has-text('Atrás')").first
                if back.is_visible(timeout=2000):
                    back.click()
                    flow.wait_for_timeout(1500)
            except Exception:
                flow.keyboard.press("Escape")
                flow.wait_for_timeout(1000)

        print("\n=== RESUMEN ===")
        for _, _, name in THUMBS:
            for ext in ['jpg', 'png']:
                cp = OUT_DIR / f"{name}.{ext}"
                if cp.exists():
                    print(f"  {name}.{ext}: ✓ {cp.stat().st_size//1024}KB")
                    break
            else:
                # Check screenshot
                ss_p = OUT_DIR / f"{name}_screenshot.png"
                if ss_p.exists():
                    print(f"  {name}_screenshot.png: ✓ {ss_p.stat().st_size//1024}KB (screenshot)")
                else:
                    print(f"  {name}: ✗")

if __name__ == "__main__":
    run()
