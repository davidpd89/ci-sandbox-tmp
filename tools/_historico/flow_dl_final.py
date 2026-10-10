"""Descarga los 4 clips/imágenes de Flow haciendo clic en 'Descargar'."""
import sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
PROJECT_URL = "https://labs.google/fx/es/tools/flow/project/df4adbe8-1c2c-4578-b3b8-527985ec3850"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/final_{name}.png")

def run():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        ctx = b.contexts[0]
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        all_pages = [pg for c in b.contexts for pg in c.pages]
        flow = next(pg for pg in all_pages if "labs.google" in pg.url)
        flow.bring_to_front()

        if PROJECT_URL.rstrip("/") not in flow.url.rstrip("/"):
            flow.goto(PROJECT_URL)
            flow.wait_for_load_state("networkidle", timeout=20000)
        flow.wait_for_timeout(2000)

        # Los 4 thumbnails están a y≈276, x=356,598,838,1080
        thumb_positions = [
            (356, 276, "clip1"),
            (598, 276, "clip2"),
            (838, 276, "clip3"),
            (1080, 276, "clip4"),
        ]

        for x, y, name in thumb_positions:
            out_file = None
            for ext in ['mp4', 'jpg', 'png', 'webm']:
                p_try = OUT_DIR / f"{name}.{ext}"
                if p_try.exists() and p_try.stat().st_size > 5000:
                    print(f"{name}: ya existe ({p_try.name})")
                    out_file = p_try
                    break
            if out_file:
                continue

            print(f"\n{name}: clic en ({x},{y})")
            flow.mouse.click(x, y)
            flow.wait_for_timeout(2000)
            ss(flow, f"01_{name}_preview")

            # Buscar y clicar el botón Descargar
            dl_btn = flow.locator("button:has-text('Descargar')").first
            try:
                dl_btn.wait_for(state="visible", timeout=5000)
                print(f"  Botón 'Descargar' encontrado")
                with flow.expect_download(timeout=60000) as dl_info:
                    dl_btn.click()
                dl = dl_info.value
                suggested = dl.suggested_filename
                ext = Path(suggested).suffix or ".bin"
                save_path = OUT_DIR / f"{name}{ext}"
                dl.save_as(save_path)
                size = save_path.stat().st_size
                print(f"  Guardado: {save_path.name} ({size//1024}KB) [ct sugerido: {suggested}]")
            except Exception as e:
                print(f"  Error: {e}")
                ss(flow, f"02_{name}_error")

            # Volver al proyecto
            back_btn = flow.locator("button:has-text('Atrás')").first
            try:
                if back_btn.is_visible(timeout=2000):
                    back_btn.click()
                    flow.wait_for_timeout(1500)
            except Exception:
                flow.keyboard.press("Escape")
                flow.wait_for_timeout(1500)

        print("\n=== RESUMEN FINAL ===")
        for i in range(1, 5):
            for ext in ['mp4', 'jpg', 'png', 'webm', 'bin']:
                cp = OUT_DIR / f"clip{i}.{ext}"
                if cp.exists():
                    print(f"  clip{i}.{ext}: ✓ {cp.stat().st_size//1024}KB")
                    break
            else:
                print(f"  clip{i}: ✗")

if __name__ == "__main__":
    run()
