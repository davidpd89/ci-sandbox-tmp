#!/usr/bin/env python3
"""Render one canonical Instagram carousel slide from a treated real image.

Usage:
  python tools/carousel_template/render_slide.py image.jpg "KICKER" "Titulo<br>de la slide" "01 / 05" out.png --cue swipe
  python tools/carousel_template/render_slide.py image.jpg "CIERRE" "Frase final" "05 / 05" out.png --cue save

Only <br> is accepted as markup in title; all other text is escaped.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import html
import mimetypes
from pathlib import Path
from tempfile import TemporaryDirectory
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template_slide.html"
LOCAL_BROWSERS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def chromium_launch_kwargs() -> dict[str, str]:
    for browser_path in LOCAL_BROWSERS:
        if browser_path.exists():
            return {"executable_path": str(browser_path)}
    return {}


def safe_title(value: str) -> str:
    marker = "__BR__"
    value = value.replace("<br />", marker).replace("<br/>", marker).replace("<br>", marker)
    return html.escape(value, quote=True).replace(marker, "<br>")


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    raw = path.read_bytes()
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


async def ensure_audited_fonts(page) -> None:
    await page.evaluate("document.fonts.ready")
    checks = {
        "Inter 600": "600 24px Inter",
        "Inter 700": "700 24px Inter",
        "Playfair Display 700": "700 24px 'Playfair Display'",
    }
    missing: list[str] = []
    for label, spec in checks.items():
        count = await page.evaluate("spec => document.fonts.load(spec, 'BESbwy').then(x => x.length)", spec)
        if not count:
            missing.append(label)
    if missing:
        raise RuntimeError(
            "CAROUSEL_RENDER_BLOCKED: faltan fuentes auditadas: " + ", ".join(missing)
            + ". Repite con acceso a fonts.googleapis.com/fonts.gstatic.com; no exportar con fallback silencioso."
        )


async def render(image: Path, kicker: str, title: str, counter: str, output: Path, cue: str) -> None:
    if not image.exists():
        raise SystemExit(f"ERROR: no existe la imagen {image}")
    if not TEMPLATE.exists():
        raise SystemExit(f"ERROR: falta plantilla {TEMPLATE}")
    if cue not in {"swipe", "save", "none"}:
        raise SystemExit("ERROR: --cue debe ser swipe, save o none")

    cue_html = {
        "swipe": "<span>DESLIZA -></span>",
        "save": "<span>▱ GUARDA</span>",
        "none": "",
    }[cue]
    cue_class = "save" if cue == "save" else ""

    page_html = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{{IMAGE_DATA}}": data_uri(image),
        "{{KICKER}}": html.escape(kicker, quote=True),
        "{{TITLE}}": safe_title(title),
        "{{COUNTER}}": html.escape(counter, quote=True),
        "{{CUE_CLASS}}": cue_class,
        "{{CUE_HTML}}": cue_html,
    }
    for old, new in replacements.items():
        page_html = page_html.replace(old, new)

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as td:
        tmp = Path(td) / "slide.html"
        tmp.write_text(page_html, encoding="utf-8")
        async with async_playwright() as p:
            browser = await p.chromium.launch(**chromium_launch_kwargs())
            page = await browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
            await page.goto(tmp.as_uri(), wait_until="networkidle")
            await ensure_audited_fonts(page)
            slide = page.locator(".slide")
            box = await slide.bounding_box()
            if not box or round(box["width"]) != 1080 or round(box["height"]) != 1350:
                raise RuntimeError(f"CAROUSEL_RENDER_BLOCKED: geometria inesperada {box}")
            await slide.screenshot(path=str(output))
            await browser.close()
    print(f"OK {output} 1080x1350 cue={cue}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("kicker")
    ap.add_argument("title")
    ap.add_argument("counter")
    ap.add_argument("output")
    ap.add_argument("--cue", choices=["swipe", "save", "none"], default="swipe")
    args = ap.parse_args()
    asyncio.run(render(Path(args.image).resolve(), args.kicker, args.title, args.counter, Path(args.output).resolve(), args.cue))


if __name__ == "__main__":
    main()
