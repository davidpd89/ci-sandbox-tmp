"""
Genera los 4 PNG de texto centrado y transparente para un reel v5.

Uso:
    python render_text_pngs.py <carpeta_salida> "texto1" "texto2" "texto3" "texto4"

Cada texto admite <br> para salto de linea. Escribir SIEMPRE con tildes,
enes y signos de apertura ¿/¡ correctos (ver sistema_reel_instagram.md,
bug #1) - no hay valor por defecto a proposito, para no arriesgarse a
renderizar el guion de un reel anterior por olvido.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

TEMPLATE = Path(__file__).parent / "text_overlay_template.html"
LOCAL_BROWSERS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]


def launch_chromium(p):
    kwargs = {"headless": True}
    for browser_path in LOCAL_BROWSERS:
        if browser_path.exists():
            kwargs["executable_path"] = str(browser_path)
            break
    return p.chromium.launch(**kwargs)


def main():
    if len(sys.argv) != 6:
        print(__doc__)
        sys.exit(1)
    out_dir = Path(sys.argv[1])
    texts = sys.argv[2:6]

    out_dir.mkdir(exist_ok=True)
    html = TEMPLATE.read_text(encoding="utf-8")
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        for i, text in enumerate(texts, start=1):
            page.set_content(html)
            page.evaluate("(t) => { document.getElementById('text').innerHTML = t; }", text)
            page.wait_for_timeout(300)
            page.screenshot(path=str(out_dir / f"text{i}.png"), omit_background=True)
        browser.close()
    print("done ->", out_dir)


if __name__ == "__main__":
    main()
