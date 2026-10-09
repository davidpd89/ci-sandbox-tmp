#!/usr/bin/env python3
"""Renderiza las dos tarjetas 1080×1920 de TT-01 desde el manifest.

Por defecto exige fondos finales s1/s2. `--reference-fallback` existe solo para
probar layout usando conscientemente la referencia Pexels; nunca busca otra imagen.
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

from playwright.async_api import async_playwright

FONT_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600&family=Playfair+Display:wght@700&display=swap');"
EDGE_EXE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def resolve_asset(item: dict, assets_dir: Path, key: str, allow_reference: bool) -> tuple[Path, str]:
    final_path = assets_dir / item["assets"][key]
    if final_path.exists():
        return final_path, "final"
    if allow_reference:
        ref = assets_dir / item["assets"]["reference"]
        if ref.exists():
            return ref, "reference_fallback"
    raise SystemExit(
        f"ERROR {item['id']}: falta {final_path}. "
        f"Genera/edita el fondo siguiendo el manifest o usa --reference-fallback solo para gate técnico."
    )


def page_html(image: Path, brand: str, text: str, slide: int) -> str:
    overlay = 0.42 if slide == 1 else 0.48
    font_size = 88 if slide == 1 else 58
    max_width = 900 if slide == 1 else 880
    safe_text = html.escape(text).replace("\n", "<br>")
    return f"""<!doctype html>
<html lang='es'><head><meta charset='utf-8'><style>
{FONT_IMPORT}
*{{box-sizing:border-box}}html,body{{margin:0;width:1080px;height:1920px;overflow:hidden;background:#111}}
.card{{position:relative;width:1080px;height:1920px;background-image:url('{data_uri(image)}');background-size:cover;background-position:center;}}
.card::after{{content:'';position:absolute;inset:0;background:rgba(0,0,0,{overlay});}}
.brand{{position:absolute;z-index:3;left:70px;top:72px;color:#f7f1e8;font:600 24px/1.1 Inter,sans-serif;letter-spacing:.16em;}}
.rule{{position:absolute;z-index:3;left:70px;top:112px;width:80px;height:3px;background:#c4783f;}}
.copy{{position:absolute;z-index:3;left:70px;bottom:220px;width:{max_width}px;color:#f7f1e8;font-weight:700;font-size:{font_size}px;line-height:1.16;letter-spacing:-.018em;text-wrap:balance;text-shadow:0 2px 12px rgba(0,0,0,.34);}}
.hook{{font-family:'Playfair Display',serif;}}
.payoff{{font-family:Inter,sans-serif;font-weight:600;line-height:1.24;letter-spacing:-.01em;}}
</style></head><body><div class='card'><div class='brand'>{html.escape(brand)}</div><div class='rule'></div><div class='copy {'hook' if slide == 1 else 'payoff'}'>{safe_text}</div></div></body></html>"""


async def ensure_audited_fonts(page) -> None:
    await page.evaluate("document.fonts.ready")
    checks = {
        "Inter 600": "600 24px Inter",
        "Playfair Display 700": "700 24px 'Playfair Display'",
    }
    missing: list[str] = []
    for label, spec in checks.items():
        loaded = await page.evaluate("spec => document.fonts.check(spec)", spec)
        if not loaded:
            missing.append(label)
    if missing:
        raise RuntimeError(
            "TT01_RENDER_BLOCKED: no se han cargado las fuentes auditadas: "
            + ", ".join(missing)
            + ". Ejecuta con acceso a fonts.googleapis.com/fonts.gstatic.com y repite el gate. "
            "No exportar con Georgia/Arial/sans-serif como fallback silencioso."
        )


async def screenshot(html_text: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as td:
        tmp = Path(td) / "card.html"
        tmp.write_text(html_text, encoding="utf-8")
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch()
            except Exception:
                if not EDGE_EXE.exists():
                    raise
                browser = await p.chromium.launch(executable_path=str(EDGE_EXE))
            page = await browser.new_page(viewport={"width":1080,"height":1920}, device_scale_factor=1)
            await page.goto(tmp.as_uri(), wait_until="networkidle")
            await ensure_audited_fonts(page)
            card = page.locator(".card")
            box = await card.bounding_box()
            copy = page.locator(".copy")
            cbox = await copy.bounding_box()
            if not box or not cbox or cbox["y"] < 150 or cbox["y"] + cbox["height"] > 1760:
                raise RuntimeError("bloque de texto fuera de zona segura")
            await card.screenshot(path=str(output))
            await browser.close()


async def render_item(data: dict, item: dict, assets: Path, out: Path, allow_reference: bool) -> None:
    s1_asset, s1_mode = resolve_asset(item, assets, "slide1", allow_reference)
    s2_asset, s2_mode = resolve_asset(item, assets, "slide2", allow_reference)
    item_out = out / item["id"]
    await screenshot(page_html(s1_asset, data["brand"], item["hook"], 1), item_out / "01_hook.png")
    await screenshot(page_html(s2_asset, data["brand"], item["payoff"], 2), item_out / "02_payoff.png")
    meta = {
        "id": item["id"], "date": item["date"], "caption": item["caption"], "hashtags": item["hashtags"],
        "reference_url": item["reference_url"], "slide1_asset": str(s1_asset), "slide2_asset": str(s2_asset),
        "slide1_asset_mode": s1_mode, "slide2_asset_mode": s2_mode,
        "production_status": "TECHNICAL_GATE_ONLY" if "reference_fallback" in {s1_mode, s2_mode} else "FINAL_ASSETS_RENDERED",
    }
    (item_out / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK {item['id']} -> {item_out} [{s1_mode}/{s2_mode}]")


async def run(args) -> None:
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    items = data["items"]
    if args.item:
        items = [x for x in items if x["id"] == args.item]
        if not items:
            raise SystemExit(f"ERROR: no existe {args.item}")
    for item in items:
        await render_item(data, item, args.assets, args.out, args.reference_fallback)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--assets", type=Path, default=Path("build/tt01/assets"))
    ap.add_argument("--out", type=Path, default=Path("build/tt01"))
    ap.add_argument("--item")
    ap.add_argument("--reference-fallback", action="store_true", help="Solo gate técnico: usa la referencia si faltan fondos finales")
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
