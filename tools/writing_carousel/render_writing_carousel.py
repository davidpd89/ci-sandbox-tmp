#!/usr/bin/env python3
"""Renderer determinista 1080×1350 para IG-02.

Usa una foto Pexels exacta por carrusel y solo cambia el encuadre vertical declarado
en el manifest. No genera imágenes, no busca sustitutos y no programa publicaciones.
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
FONT_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700&family=Playfair+Display:wght@700&display=swap');"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True).replace("\n", "<br>")


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def page_html(post: dict[str, Any], slide: dict[str, Any], index: int, total: int, image: Path, brand: str) -> str:
    kind = slide["kind"]
    crop_y = int(slide.get("crop_y", 50))
    title = esc(slide["title"])
    body = esc(slide.get("body", ""))
    cta = esc(slide.get("cta", ""))
    body_html = f'<div class="body">{body}</div>' if body else ""
    cta_html = f'<div class="cta">{cta}</div>' if cta else ""
    cue = "" if kind == "final" else '<div class="cue">DESLIZA →</div>'
    kind_class = f"content {kind}"
    return f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><style>
{FONT_IMPORT}
*{{box-sizing:border-box}}html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#0f0c0b}}
.slide{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:#0f0c0b;color:#f7f1e8}}
.photo{{position:absolute;inset:-12px;background-image:url('{data_uri(image)}');background-size:cover;background-position:center {crop_y}%;filter:saturate(.78) contrast(1.15) brightness(.80);transform:scale(1.025)}}
.terracotta{{position:absolute;inset:0;background:rgba(180,110,60,.16)}}
.veil{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,12,11,.30) 0%,rgba(15,12,11,.48) 34%,rgba(15,12,11,.91) 73%,rgba(15,12,11,.98) 100%)}}
.top{{position:absolute;z-index:4;left:64px;right:64px;top:54px;display:flex;justify-content:space-between;align-items:center;font-family:Inter,sans-serif;font-size:19px;font-weight:700;letter-spacing:.08em}}
.counter{{padding:9px 14px;border:1px solid rgba(247,241,232,.55);border-radius:999px;background:rgba(15,12,11,.35)}}
.content{{position:absolute;z-index:4;left:64px;right:64px;bottom:112px;max-width:930px}}
.kicker{{display:inline-block;margin-bottom:22px;padding:9px 14px;border-radius:5px;background:#c4783f;color:#17120b;font-family:Inter,sans-serif;font-size:19px;font-weight:700;letter-spacing:.08em}}
.title{{font-family:'Playfair Display',serif;font-size:54px;line-height:1.06;font-weight:700;letter-spacing:-.02em;text-wrap:balance;text-shadow:0 2px 14px rgba(0,0,0,.35)}}
.body{{margin-top:28px;max-width:900px;font-family:Inter,sans-serif;font-size:29px;line-height:1.34;font-weight:500;text-wrap:pretty}}
.hero .title{{font-size:64px;max-width:900px}}.hero .body{{font-size:29px;max-width:820px}}
.final{{bottom:145px}}.final .title{{font-size:61px;max-width:900px}}.final .cta{{margin-top:36px;display:inline-block;padding:13px 17px;border:1px solid #c4783f;border-radius:5px;color:#f7f1e8;font-family:Inter,sans-serif;font-size:20px;font-weight:700;letter-spacing:.055em}}
.cue{{position:absolute;z-index:5;right:64px;bottom:42px;font-family:Inter,sans-serif;font-size:18px;font-weight:700;letter-spacing:.06em}}
</style></head><body><div class='slide'><div class='photo'></div><div class='terracotta'></div><div class='veil'></div><div class='top'><div>{esc(brand)}</div><div class='counter'>{index:02d} / {total:02d}</div></div><div class='{kind_class}'><div class='kicker'>{esc(post['kicker'])}</div><div class='title'>{title}</div>{body_html}{cta_html}</div>{cue}</div></body></html>"""


async def ensure_fonts(page) -> None:
    await page.evaluate("document.fonts.ready")
    checks = {
        "Inter 500": "500 24px Inter",
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
            "IG02_RENDER_BLOCKED: faltan fuentes auditadas: " + ", ".join(missing)
            + ". Repite con acceso a fonts.googleapis.com/fonts.gstatic.com; no exportar con fallback silencioso."
        )


async def shot(page, markup: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as td:
        source = Path(td) / "slide.html"
        source.write_text(markup, encoding="utf-8")
        await page.goto(source.as_uri(), wait_until="networkidle")
        await ensure_fonts(page)
        content = page.locator(".content")
        box = await content.bounding_box()
        if not box or box["y"] < 250 or box["y"] + box["height"] > 1260:
            raise RuntimeError(f"IG02_RENDER_BLOCKED: contenido fuera de zona segura: {box}")
        await page.locator(".slide").screenshot(path=str(output))


async def render(manifest: Path, assets: Path, out: Path, item: str | None, all_items: bool) -> None:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    posts = data["posts"]
    if not all_items:
        posts = [post for post in posts if post["id"] == item]
    if not posts:
        raise SystemExit("ERROR: no hay posts seleccionados")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for post in posts:
            image = assets / post["asset"]
            if not image.exists():
                raise SystemExit(
                    f"MISSING_ASSET: {image}\nSOURCE: {post['reference_url']}\n"
                    "Ejecuta fetch_references.py; no se busca sustituto automáticamente."
                )
            target_dir = out / post["id"]
            slides = post["slides"]
            for index, slide in enumerate(slides, start=1):
                target = target_dir / f"{index:02d}.png"
                await shot(page, page_html(post, slide, index, len(slides), image, data["brand"]), target)
                print(f"OK {target}")
            metadata = {
                "id": post["id"],
                "date_proposed": post["date_proposed"],
                "schedule_rule": data["schedule_rule"],
                "caption": post["caption"],
                "hashtags": post["hashtags"],
                "reference_url": post["reference_url"],
                "license_url": data["license_url"],
                "asset": str(image),
                "production_route": data["production_route"],
                "slides": len(slides),
                "status": "RENDERED_NOT_SCHEDULED",
            }
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--assets", type=Path, default=Path("build/ig02/assets"))
    parser.add_argument("--out", type=Path, default=Path("build/ig02"))
    args = parser.parse_args()
    asyncio.run(render(args.manifest, args.assets, args.out, args.item, args.all))


if __name__ == "__main__":
    main()
