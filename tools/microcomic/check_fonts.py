#!/usr/bin/env python3
"""Preflight tipográfico para IG-08/TT-04.

Comprueba desde Chromium que la familia local Inter está disponible antes de
renderizar el microcómic. El renderer usa Inter 650/700/750; sin esta prueba,
Chromium puede sustituir silenciosamente por Arial/sans-serif y cambiar saltos,
densidad y jerarquía visual.

Dependencia ya requerida por el pipeline:
    python -m pip install playwright
    python -m playwright install chromium
"""
from __future__ import annotations

import base64
from pathlib import Path

from playwright.sync_api import sync_playwright


EDGE_EXE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
CHROME_EXE = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
INTER_FONT = Path(__file__).resolve().parent / "fonts" / "Inter-4.1" / "InterVariable.ttf"


def html_probe() -> str:
    if not INTER_FONT.exists():
        raise SystemExit(
            "IG-08 BLOQUEADO: falta tools/microcomic/fonts/Inter-4.1/InterVariable.ttf. "
            "No renderizar con Arial/sans-serif como sustitución silenciosa."
        )
    font_b64 = base64.b64encode(INTER_FONT.read_bytes()).decode("ascii")
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
@font-face {{
  font-family: "IG08_Inter_Probe";
  src: url("data:font/ttf;base64,{font_b64}") format("truetype"), local("Inter");
  font-style: normal;
  font-weight: 100 900;
}}
body {{ font-family: "IG08_Inter_Probe"; font-weight: 650; }}
</style>
</head>
<body>Microcómic lector ÁÉÍÓÚÑ 23:48</body>
</html>"""


def main() -> None:
    with sync_playwright() as p:
        if EDGE_EXE.exists():
            browser = p.chromium.launch(executable_path=str(EDGE_EXE))
        elif CHROME_EXE.exists():
            browser = p.chromium.launch(executable_path=str(CHROME_EXE))
        else:
            browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 640, "height": 240})
        page.set_content(html_probe(), wait_until="load")
        result = page.evaluate(
            """async () => {
              try {
                const faces = await document.fonts.load('650 32px IG08_Inter_Probe', 'Microcómic lector ÁÉÍÓÚÑ 23:48');
                await document.fonts.ready;
                return {
                  loaded: faces.length > 0,
                  check650: document.fonts.check('650 32px IG08_Inter_Probe', 'Microcómic lector'),
                  check700: document.fonts.check('700 32px IG08_Inter_Probe', '23:48')
                };
              } catch (error) {
                return {loaded: false, check650: false, check700: false, error: String(error)};
              }
            }"""
        )
        browser.close()

    if not (result.get("loaded") and result.get("check650") and result.get("check700")):
        detail = result.get("error") or "Chromium no ha podido cargar Inter desde la máquina local."
        raise SystemExit(
            "IG-08 BLOQUEADO: falta la tipografía auditada Inter. "
            f"{detail} Instala Inter y repite este preflight. "
            "No renderizar con Arial/sans-serif como sustitución silenciosa."
        )

    print("OK: Inter disponible en Chromium para IG-08/TT-04.")


if __name__ == "__main__":
    main()
