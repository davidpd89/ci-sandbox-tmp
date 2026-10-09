#!/usr/bin/env python3
"""Renderer 1080×1920 para TT-02.

Slides 1–9: una foto Pexels real declarada, con crops/zoom deterministas.
Slide 10: portada real validada por dimensiones y SHA-256. No genera imágenes.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import html
import json
import mimetypes
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PIL import Image
from playwright.async_api import async_playwright

W, H = 1080, 1920
FONT_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700&family=Playfair+Display:wght@700&display=swap');"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True).replace("\n", "<br>")


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_cover(path: Path, spec: dict[str, Any]) -> None:
    if not path.exists():
        raise SystemExit(
            f"TT02_COVER_BLOCKED: falta {path}. Descarga el Drive ID {spec['drive_id']} con nombre exacto {spec['asset']}."
        )
    digest = sha256(path)
    if digest != spec["sha256"]:
        raise SystemExit(
            f"TT02_COVER_BLOCKED: SHA-256 incorrecto para {path.name}. Esperado {spec['sha256']}; obtenido {digest}. "
            "No usar otra exportación ni reconstruir la portada."
        )
    with Image.open(path) as image:
        if image.size != (spec["width"], spec["height"]):
            raise SystemExit(
                f"TT02_COVER_BLOCKED: dimensiones {image.size}; esperadas {(spec['width'], spec['height'])}."
            )


def validate_reference_sidecar(post: dict[str, Any], assets: Path, license_url: str) -> None:
    sidecar = assets / f"{post['id']}.reference.json"
    if not sidecar.exists():
        raise SystemExit(
            f"TT02_SOURCE_BLOCKED: falta {sidecar}. Ejecuta tools/writing_carousel/fetch_references.py con este manifest."
        )
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    if data.get("source_page") != post["reference_url"]:
        raise SystemExit(f"TT02_SOURCE_BLOCKED: {post['id']} sidecar apunta a otra referencia")
    if data.get("license_url") != license_url or not data.get("pexels_free_to_use_signal"):
        raise SystemExit(f"TT02_SOURCE_BLOCKED: {post['id']} no conserva licencia/señal Pexels auditada")


def font_size(text: str, kind: str) -> int:
    n = len(text.replace("\n", " "))
    if kind == "hook":
        return 76 if n <= 72 else 68
    if n <= 48:
        return 76
    if n <= 82:
        return 66
    if n <= 115:
        return 59
    return 53


def quote_html(data: dict[str, Any], post: dict[str, Any], slide: dict[str, Any], index: int, image: Path) -> str:
    crop = int(slide.get("crop_y", 50))
    zoom = float(slide.get("zoom", 1.0))
    text = slide["text"]
    size = font_size(text, slide["kind"])
    note = slide.get("note")
    note_html = f'<div class="note">{esc(note)}</div>' if note else ""
    label = "GANCHO" if slide["kind"] == "hook" else "FRAGMENTO"
    return f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><style>
{FONT_IMPORT}
*{{box-sizing:border-box}}html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#0f0c0b}}
.slide{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:#0f0c0b;color:#f7f1e8}}
.photo{{position:absolute;inset:-40px;background-image:url('{data_uri(image)}');background-size:cover;background-position:center {crop}%;transform:scale({zoom});filter:saturate(.82) contrast(1.08) brightness(.76)}}
.veil{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,12,11,.40) 0%,rgba(15,12,11,.30) 28%,rgba(15,12,11,.72) 62%,rgba(15,12,11,.96) 100%)}}
.top{{position:absolute;z-index:4;left:64px;right:64px;top:64px;display:flex;justify-content:space-between;font-family:Inter,sans-serif;font-size:20px;font-weight:700;letter-spacing:.08em}}
.counter{{padding:9px 14px;border:1px solid rgba(247,241,232,.55);border-radius:999px;background:rgba(15,12,11,.36)}}
.content{{position:absolute;z-index:4;left:70px;right:70px;bottom:190px}}
.kicker{{display:inline-block;margin-bottom:28px;color:#c4783f;font-family:Inter,sans-serif;font-size:20px;font-weight:700;letter-spacing:.13em}}
.text{{max-width:925px;font-family:'Playfair Display',serif;font-size:{size}px;line-height:1.16;font-weight:700;letter-spacing:-.018em;text-wrap:balance;text-shadow:0 3px 18px rgba(0,0,0,.45)}}
.note{{margin-top:34px;font-family:Inter,sans-serif;font-size:23px;font-weight:600;line-height:1.3;color:rgba(247,241,232,.82)}}
.swipe{{position:absolute;z-index:5;right:64px;bottom:55px;font-family:Inter,sans-serif;font-size:19px;font-weight:700;letter-spacing:.07em}}
</style></head><body><div class='slide'><div class='photo'></div><div class='veil'></div><div class='top'><div>{esc(data['brand'])}</div><div class='counter'>{index:02d} / 10</div></div><div class='content'><div class='kicker'>{label}</div><div class='text'>{esc(text)}</div>{note_html}</div><div class='swipe'>DESLIZA →</div></div></body></html>"""


def cover_html(data: dict[str, Any], post: dict[str, Any], cover: Path) -> str:
    spec = data["cover"]
    return f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><style>
{FONT_IMPORT}
*{{box-sizing:border-box}}html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#17120B}}
.slide{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:radial-gradient(circle at 22% 16%,rgba(194,121,55,.24),transparent 34%),linear-gradient(150deg,#17120B 0%,#4C351A 58%,#17120B 100%);color:#f7f1e8}}
.brand{{position:absolute;left:64px;top:62px;font-family:Inter,sans-serif;font-size:20px;font-weight:700;letter-spacing:.08em}}
.counter{{position:absolute;right:64px;top:55px;padding:9px 14px;border:1px solid rgba(247,241,232,.5);border-radius:999px;font-family:Inter,sans-serif;font-size:20px;font-weight:700}}
.cover{{position:absolute;left:190px;top:150px;width:700px;height:1050px;object-fit:contain;filter:drop-shadow(0 28px 30px rgba(0,0,0,.38))}}
.copy{{position:absolute;left:70px;right:70px;top:1280px;text-align:center}}
.title{{font-family:'Playfair Display',serif;font-size:54px;line-height:1.05;font-weight:700}}
.meta{{margin-top:22px;font-family:Inter,sans-serif;font-size:26px;line-height:1.45;font-weight:600}}
.support{{margin-top:38px;color:#CF9246;font-family:Inter,sans-serif;font-size:27px;font-weight:700}}
</style></head><body><div class='slide'><div class='brand'>{esc(data['brand'])}</div><div class='counter'>10 / 10</div><img class='cover' src='{data_uri(cover)}' alt=''><div class='copy'><div class='title'>{esc(spec['title'])}</div><div class='meta'>{esc(spec['author'])}<br>{esc(spec['publisher'])}</div><div class='support'>{esc(post['cover_support'])}</div></div></div></body></html>"""


async def ensure_fonts(page) -> None:
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
            "TT02_RENDER_BLOCKED: faltan fuentes auditadas: " + ", ".join(missing)
            + ". Repite con acceso a fonts.googleapis.com/fonts.gstatic.com; no exportar con fallback silencioso."
        )


async def screenshot(page, markup: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as td:
        source = Path(td) / "slide.html"
        source.write_text(markup, encoding="utf-8")
        await page.goto(source.as_uri(), wait_until="networkidle")
        await ensure_fonts(page)
        slide = page.locator(".slide")
        box = await slide.bounding_box()
        if not box or round(box["width"]) != W or round(box["height"]) != H:
            raise RuntimeError(f"TT02_RENDER_BLOCKED: geometría inesperada {box}")
        if await page.locator(".content").count():
            content = page.locator(".content")
            cbox = await content.bounding_box()
            if not cbox or cbox["y"] < 420 or cbox["y"] + cbox["height"] > 1740:
                raise RuntimeError(f"TT02_RENDER_BLOCKED: texto fuera de zona segura {cbox}")
        await slide.screenshot(path=str(output))


async def render(manifest: Path, assets: Path, out: Path, item: str | None, all_items: bool) -> None:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    cover = assets / data["cover"]["asset"]
    validate_cover(cover, data["cover"])
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
                    f"TT02_SOURCE_BLOCKED: falta {image}. SOURCE: {post['reference_url']}. "
                    "Ejecuta tools/writing_carousel/fetch_references.py; no usar el backup automáticamente."
                )
            validate_reference_sidecar(post, assets, data["license_url"])
            target_dir = out / post["id"]
            for index, slide in enumerate(post["slides"], start=1):
                target = target_dir / f"{index:02d}.png"
                markup = cover_html(data, post, cover) if slide["kind"] == "cover" else quote_html(data, post, slide, index, image)
                await screenshot(page, markup, target)
                print(f"OK {target}")
            metadata = {
                "id": post["id"],
                "canonical_source": data["canonical_source"],
                "date_proposed": post["date_proposed"],
                "schedule_rule": data["schedule_rule"],
                "caption": post["caption"],
                "hashtags": post["hashtags"],
                "reference_url": post["reference_url"],
                "license_url": data["license_url"],
                "reference_sha256": sha256(image),
                "cover_drive_id": data["cover"]["drive_id"],
                "cover_sha256": data["cover"]["sha256"],
                "production_route": data["production_route"],
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
    parser.add_argument("--assets", type=Path, default=Path("build/tt02/assets"))
    parser.add_argument("--out", type=Path, default=Path("build/tt02"))
    args = parser.parse_args()
    asyncio.run(render(args.manifest, args.assets, args.out, args.item, args.all))


if __name__ == "__main__":
    main()
