#!/usr/bin/env python3
"""Render a four-slide typographic documentary carousel from a JSON manifest.

Designed for IG-17 and future text-first kits. No image generation, no stock.

Usage:
  python tools/text_carousel/render_text_carousel.py tools/text_carousel/ig17_manifest.json --item ig17_01 --out build/ig17
  python tools/text_carousel/render_text_carousel.py tools/text_carousel/ig17_manifest.json --all --out build/ig17

Dependencies:
  pip install playwright
  python -m playwright install chromium
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from playwright.async_api import async_playwright

W, H = 1080, 1350

CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700&family=Noto+Sans:wght@600&family=Playfair+Display:wght@600;700;900&display=swap');
*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1350px;overflow:hidden;background:#f7f1e8}
body{font-family:Inter,Arial,sans-serif;color:#17120b}.slide{position:relative;width:1080px;height:1350px;padding:64px 70px 70px;background:#f7f1e8;overflow:hidden}
.slide.dark{background:#17120b;color:#f7f1e8}.brandrow{display:flex;justify-content:space-between;align-items:center;font-size:22px;font-weight:700;letter-spacing:.07em}.count{padding:9px 15px;border:1px solid currentColor;border-radius:999px;opacity:.68}.rule{height:4px;width:86px;background:#c4783f;margin-top:42px}.kicker{margin-top:48px;font-size:23px;font-weight:700;letter-spacing:.09em;color:#c4783f;text-transform:uppercase}
.word{font-family:'Playfair Display',Georgia,serif;font-weight:900;font-size:142px;line-height:.92;letter-spacing:-.045em;margin-top:58px;overflow-wrap:anywhere}.sub{font-family:'Playfair Display',Georgia,serif;font-size:48px;line-height:1.08;font-weight:600;max-width:850px;margin-top:48px}.chain{font-family:'Noto Sans',Inter,Arial,sans-serif;font-size:51px;line-height:1.26;font-weight:600;max-width:900px;margin-top:115px;overflow-wrap:anywhere}.body{font-family:'Playfair Display',Georgia,serif;font-size:50px;line-height:1.22;font-weight:600;max-width:890px;margin-top:90px}.today{font-family:'Playfair Display',Georgia,serif;font-size:58px;line-height:1.14;font-weight:700;max-width:880px;margin-top:95px}.source{position:absolute;left:70px;right:70px;bottom:98px;border-top:2px solid rgba(196,120,63,.65);padding-top:25px;font-size:24px;line-height:1.35}.cue{position:absolute;right:70px;bottom:42px;font-size:20px;font-weight:700;letter-spacing:.06em}.note{position:absolute;left:70px;bottom:42px;font-size:18px;opacity:.62}.accent{color:#c4783f}
"""


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def shell(content: str, counter: str, dark: bool = False, cue: bool = True) -> str:
    cls = "slide dark" if dark else "slide"
    cue_html = '<div class="cue">DESLIZA →</div>' if cue else ""
    return f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style></head><body>
<div class='{cls}'>
<div class='brandrow'><div>DAVID PORTO DÍAZ</div><div class='count'>{esc(counter)}</div></div>
<div class='rule'></div>{content}{cue_html}</div></body></html>"""


def slide_html(post: dict[str, Any], n: int) -> str:
    if n == 1:
        content = f"<div class='kicker'>UNA PALABRA, UN VIAJE</div><div class='word'>{esc(post['word'])}</div><div class='sub'>{esc(post['sub'])}</div>"
        return shell(content, "01 / 04", dark=True, cue=True)
    if n == 2:
        content = f"<div class='kicker'>DE DÓNDE VIENE</div><div class='chain'>{esc(post['chain'])}</div>"
        return shell(content, "02 / 04", dark=False, cue=True)
    if n == 3:
        content = f"<div class='kicker'>QUÉ DICE LA FUENTE</div><div class='body'>{esc(post['body'])}</div>"
        return shell(content, "03 / 04", dark=False, cue=True)
    content = (
        f"<div class='kicker'>HOY</div><div class='today'>{esc(post['today'])}</div>"
        f"<div class='source'><strong>Fuente:</strong> RAE-ASALE · Diccionario de la lengua española<br>{esc(post['source'])}</div>"
        "<div class='note'>Texto final añadido por HTML/CSS · sin generación de imagen</div>"
    )
    return shell(content, "04 / 04", dark=True, cue=False)


async def ensure_audited_fonts(page) -> None:
    await page.evaluate("document.fonts.ready")
    checks = {
        "Inter 500": "500 24px Inter",
        "Inter 600": "600 24px Inter",
        "Inter 700": "700 24px Inter",
        "Noto Sans 600": "600 24px 'Noto Sans'",
        "Playfair Display 600": "600 24px 'Playfair Display'",
        "Playfair Display 700": "700 24px 'Playfair Display'",
        "Playfair Display 900": "900 24px 'Playfair Display'",
    }
    missing: list[str] = []
    for label, spec in checks.items():
        loaded = await page.evaluate("spec => document.fonts.check(spec)", spec)
        if not loaded:
            missing.append(label)
    if missing:
        raise RuntimeError(
            "TEXT_CAROUSEL_BLOCKED: no se han cargado las fuentes auditadas: "
            + ", ".join(missing)
            + ". Ejecuta con acceso a fonts.googleapis.com/fonts.gstatic.com y repite el gate. "
            "No exportar con Arial/Georgia/fallback Unicode no controlado."
        )


async def screenshot(page, markup: str, output: Path) -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td) / "slide.html"
        tmp.write_text(markup, encoding="utf-8")
        await page.goto(tmp.as_uri(), wait_until="networkidle")
        await ensure_audited_fonts(page)
        await page.locator(".slide").screenshot(path=str(output))


async def render(manifest: Path, out_dir: Path, item: str | None, all_items: bool) -> None:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    posts = data.get("posts", [])
    if not posts:
        raise SystemExit("ERROR: manifest sin posts")
    if not all_items:
        posts = [p for p in posts if p.get("id") == item]
        if not posts:
            raise SystemExit(f"ERROR: no existe item {item}")
    out_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for post in posts:
            for n in range(1, 5):
                target = out_dir / f"{post['id']}_s{n}.png"
                await screenshot(page, slide_html(post, n), target)
                print(f"OK {target}")
        await browser.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--item")
    group.add_argument("--all", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    asyncio.run(render(Path(args.manifest).resolve(), Path(args.out).resolve(), args.item, args.all))


if __name__ == "__main__":
    main()
