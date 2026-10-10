#!/usr/bin/env python3
"""Deterministic renderer for documentary Instagram carousels.

The manifest is the authority. This tool never searches for replacement assets.
If a required local image is missing, it fails and prints the exact source URL
stored in the manifest.

`detail_card=true` is for small archival details: it keeps the image inside a
fixed editorial box instead of stretching it full-canvas. This is intentionally
used for manuscript fragments where authenticity matters more than filling 4:5.

Usage:
  python tools/documentary_carousel/render_documentary.py manifests/ig15.json --item ig15_01 --assets build/ig15/assets --out build/ig15
  python tools/documentary_carousel/render_documentary.py manifests/ig15.json --all --assets build/ig15/assets --out build/ig15

Dependency:
  pip install playwright
  python -m playwright install chromium
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import html
import json
import mimetypes
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from playwright.async_api import async_playwright

W, H = 1080, 1350

CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;900&family=Inter:wght@500;600;700&display=swap');
*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1350px;overflow:hidden;background:#f7f1e8}
body{font-family:Inter,Arial,sans-serif;color:#17120b}.slide{position:relative;width:1080px;height:1350px;overflow:hidden;background:#f7f1e8}
.header{position:absolute;z-index:6;left:58px;right:58px;top:42px;display:flex;justify-content:space-between;align-items:center;color:#f7f1e8;text-shadow:0 2px 12px rgba(0,0,0,.5);font-size:20px;font-weight:700;letter-spacing:.06em}.header.light{color:#17120b;text-shadow:none}.counter{padding:8px 13px;border:1px solid currentColor;border-radius:999px;background:rgba(15,12,11,.15)}
.image{position:absolute;inset:0;width:100%;height:100%;object-position:center}.image.cover{object-fit:cover}.image.contain{object-fit:contain;background:#eee5d8}
.image.detail-card{inset:auto;left:210px;top:105px;width:660px;height:740px;object-fit:contain;background:#eee5d8;border:1px solid #d8cbbb;box-shadow:0 12px 34px rgba(23,18,11,.16)}
.veil{position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,12,11,.12),rgba(15,12,11,.24) 38%,rgba(15,12,11,.88) 82%,rgba(15,12,11,.96));z-index:2}
.titlebox{position:absolute;z-index:4;left:64px;right:64px;bottom:118px;color:#f7f1e8}.kicker{display:inline-block;background:#c4783f;color:#17120b;padding:9px 14px;border-radius:5px;font-size:21px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;margin-bottom:22px}.title{font-family:'Playfair Display',Georgia,serif;font-size:67px;line-height:1.04;font-weight:700;letter-spacing:-.02em;white-space:pre-line;text-shadow:0 2px 14px rgba(0,0,0,.42)}
.doc-image{position:absolute;left:0;right:0;top:0;height:690px;background:#eee5d8;display:flex;align-items:center;justify-content:center;overflow:hidden}.doc-image img{width:100%;height:100%}.doc-image img.cover{object-fit:cover}.doc-image img.contain{object-fit:contain}.doc-image img.detail-card{width:660px;height:590px;object-fit:contain;border:1px solid #d8cbbb;box-shadow:0 10px 28px rgba(23,18,11,.14)}
.doc-band{position:absolute;left:0;right:0;top:690px;bottom:0;padding:54px 66px 92px;background:#f7f1e8}.doc-band.dark{background:#17120b;color:#f7f1e8}.doc-band .kicker{margin-bottom:18px}.body{font-family:'Playfair Display',Georgia,serif;font-size:43px;line-height:1.23;font-weight:600;white-space:pre-line}.body.small{font-size:36px;line-height:1.28}.body.xsmall{font-size:31px;line-height:1.3}.textslide{position:absolute;inset:0;padding:72px 70px 100px;background:#f7f1e8}.textslide.dark{background:#17120b;color:#f7f1e8}.textslide .kicker{margin-top:110px}.texttitle{font-family:'Playfair Display',Georgia,serif;font-size:64px;line-height:1.08;font-weight:700;white-space:pre-line;margin-top:36px}.textbody{font-family:'Playfair Display',Georgia,serif;font-size:43px;line-height:1.24;font-weight:600;white-space:pre-line;margin-top:46px}.sourcebox{position:absolute;left:64px;right:64px;bottom:72px;padding-top:20px;border-top:2px solid rgba(196,120,63,.7);font-size:20px;line-height:1.35;white-space:pre-line}.cue{position:absolute;z-index:7;right:58px;bottom:32px;font-size:18px;font-weight:700;letter-spacing:.05em}.credit{position:absolute;z-index:7;left:58px;bottom:30px;font-size:16px;max-width:720px;line-height:1.25;opacity:.72;white-space:pre-line}.credit.onimage{color:#f7f1e8;text-shadow:0 1px 8px rgba(0,0,0,.8)}
"""


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def image_data(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def resolve_asset(slide: dict[str, Any], assets: Path) -> str | None:
    name = slide.get("image")
    if not name:
        return None
    path = assets / name
    if not path.exists():
        src = slide.get("source_url", "(source_url no definido)")
        raise SystemExit(f"MISSING_ASSET: {path}\nSOURCE: {src}\nNo se busca sustituto automáticamente.")
    return image_data(path)


def font_class(body: str) -> str:
    n = len(body)
    if n > 420:
        return "body xsmall"
    if n > 280:
        return "body small"
    return "body"


def cue_html(cue: str | None) -> str:
    if cue == "swipe":
        return '<div class="cue">DESLIZA →</div>'
    if cue == "save":
        return '<div class="cue">GUARDA · COMPARTE</div>'
    return ""


def header(counter: str, light: bool = False) -> str:
    cls = "header light" if light else "header"
<<<<<<< HEAD
    return f'<div class="{cls}"><div>AUTORA DEMO DÍAZ</div><div class="counter">{esc(counter)}</div></div>'
=======
    return f'<div class="{cls}"><div>DAVID PORTO DÍAZ</div><div class="counter">{esc(counter)}</div></div>'
>>>>>>> origin/research/public-reuse-parent


def image_classes(slide: dict[str, Any], fit: str, *, full: bool) -> str:
    classes = ["image", fit] if full else [fit]
    if slide.get("detail_card"):
        classes.append("detail-card")
    return " ".join(classes)


def make_slide(slide: dict[str, Any], counter: str, assets: Path) -> str:
    mode = slide.get("mode", "text")
    cue = cue_html(slide.get("cue"))
    kicker = esc(slide.get("kicker", ""))
    title = esc(slide.get("title", ""))
    body = esc(slide.get("body", ""))
    footer = esc(slide.get("footer", ""))
    credit = esc(slide.get("credit", ""))
    fit = slide.get("fit", "cover")
    img = resolve_asset(slide, assets)

    if mode == "image_title":
        if not img:
            raise SystemExit("ERROR: image_title requiere image")
        img_cls = image_classes(slide, fit, full=True)
        return (
            f'<div class="slide">{header(counter)}<img class="{img_cls}" src="{img}"><div class="veil"></div>'
            f'<div class="titlebox"><div class="kicker">{kicker}</div><div class="title">{title}</div></div>'
            f'<div class="credit onimage">{credit}</div>{cue}</div>'
        )

    if mode in {"image_body", "source_image"}:
        if not img:
            raise SystemExit(f"ERROR: {mode} requiere image")
        dark = " dark" if slide.get("dark_band") else ""
        img_cls = image_classes(slide, fit, full=False)
        return (
            f'<div class="slide">{header(counter)}<div class="doc-image"><img class="{img_cls}" src="{img}"></div>'
            f'<div class="doc-band{dark}"><div class="kicker">{kicker}</div><div class="{font_class(body)}">{body}</div>'
            f'<div class="sourcebox">{footer}</div></div><div class="credit">{credit}</div>{cue}</div>'
        )

    dark = bool(slide.get("dark"))
    cls = "textslide dark" if dark else "textslide"
    hdr = header(counter, light=not dark)
    return (
        f'<div class="slide"><div class="{cls}">{hdr}<div class="kicker">{kicker}</div>'
        f'<div class="texttitle">{title}</div><div class="textbody">{body}</div>'
        f'<div class="sourcebox">{footer}</div></div>{cue}</div>'
    )


def page_html(slide_markup: str) -> str:
    return f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{slide_markup}</body></html>"


async def ensure_audited_fonts(page) -> None:
    await page.evaluate("document.fonts.ready")
    checks = {
        "Inter 500": "500 24px Inter",
        "Inter 600": "600 24px Inter",
        "Inter 700": "700 24px Inter",
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
            "DOCUMENTARY_RENDER_BLOCKED: no se han cargado las fuentes auditadas: "
            + ", ".join(missing)
            + ". Ejecuta con acceso a fonts.googleapis.com/fonts.gstatic.com y repite el gate. "
            "No exportar con Georgia/Arial como fallback silencioso."
        )


async def shot(page, markup: str, output: Path) -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td) / "slide.html"
        tmp.write_text(page_html(markup), encoding="utf-8")
        await page.goto(tmp.as_uri(), wait_until="networkidle")
        await ensure_audited_fonts(page)
        await page.locator(".slide").screenshot(path=str(output))


async def render(manifest: Path, item: str | None, all_items: bool, assets: Path, out: Path) -> None:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    posts = data.get("posts", [])
    if not all_items:
        posts = [p for p in posts if p.get("id") == item]
    if not posts:
        raise SystemExit("ERROR: no hay posts seleccionados")
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for post in posts:
            slides = post.get("slides", [])
            total = len(slides)
            for idx, slide in enumerate(slides, start=1):
                counter = f"{idx:02d} / {total:02d}"
                target = out / f"{post['id']}_s{idx}.png"
                await shot(page, make_slide(slide, counter, assets), target)
                print(f"OK {target}")
        await browser.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--item")
    group.add_argument("--all", action="store_true")
    ap.add_argument("--assets", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    asyncio.run(render(Path(args.manifest).resolve(), args.item, args.all, Path(args.assets).resolve(), Path(args.out).resolve()))


if __name__ == "__main__":
    main()
