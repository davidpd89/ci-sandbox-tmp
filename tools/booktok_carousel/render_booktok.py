#!/usr/bin/env python3
"""Renderer 1080×1350 para IG-01.

Tipos: text, book, choice, multi_cover, place.
Las portadas siempre se insertan como imágenes independientes con object-fit:contain.
Las slides `place` exigen fondo final salvo --travel-reference-fallback.
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

FONT_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700&family=Playfair+Display:wght@700&display=swap');"
SYSTEM_BROWSERS = [
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
]


def uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def need(path: Path, label: str) -> Path:
    if not path.exists():
        raise SystemExit(f"ERROR: falta {label}: {path}")
    return path


def esc(value: str | None) -> str:
    return html.escape(value or "").replace("\n", "<br>")


def cover_tag(path: Path, cls: str = "cover") -> str:
    return f"<img class='{cls}' src='{uri(path)}' alt=''>"


def render_slide_html(data: dict, slide: dict, index: int, total: int, assets: Path, travel_fallback: bool) -> tuple[str, str]:
    palette = data["palette"]
    stype = slide["type"]
    bg_style = ""
    overlay = ""
    asset_mode = "none"

    background_key = slide.get("background")
    if not background_key and stype != "place":
        cycle = data.get("default_soft_background_cycle") or list(data.get("soft_backgrounds", {}))
        if cycle:
            background_key = cycle[(index - 1) % len(cycle)]

    if stype == "place":
        spec = data["travel_backgrounds"][slide["background"]]
        final = assets / spec["final_asset"]
        if final.exists():
            bg = final
            asset_mode = "final_travel"
        elif travel_fallback:
            bg = need(assets / spec["asset"], f"referencia de viaje {slide['background']}")
            asset_mode = "reference_fallback"
        else:
            raise SystemExit(
                f"ERROR: falta fondo final {final}. Crea la variación según el JSON del manifest o usa "
                f"--travel-reference-fallback solo para gate técnico."
            )
        bg_style = f"background-image:url('{uri(bg)}');background-size:cover;background-position:center;"
        overlay = "<div class='photo-overlay'></div>"
    elif background_key:
        spec = data["soft_backgrounds"][background_key]
        bg = need(assets / spec["asset"], f"fondo suave {background_key}")
        bg_style = f"background-image:url('{uri(bg)}');background-size:cover;background-position:center;"
        overlay = "<div class='soft-bg'></div><div class='soft-overlay'></div>"
        asset_mode = "soft_background"

    cover_html = ""
    if stype in {"book", "choice", "place"}:
        spec = data["covers"][slide["cover"]]
        cover_html = cover_tag(need(assets / spec["asset"], f"portada {spec['title']}"))
    elif stype == "multi_cover":
        tags = []
        count = len(slide["covers"])
        for pos, slug in enumerate(slide["covers"]):
            spec = data["covers"][slug]
            tags.append(cover_tag(need(assets / spec["asset"], f"portada {spec['title']}"), f"mini-cover mc{count}-{pos+1}"))
        cover_html = "<div class='cover-fan'>" + "".join(tags) + "</div>"

    kicker = esc(slide.get("kicker"))
    title = esc(slide.get("title"))
    body = esc(slide.get("body"))
    label = esc(slide.get("label"))
    cta = esc(slide.get("cta"))
    bottom_cue = "GUARDA" if index == total else "DESLIZA →"

    content_class = f"content {stype}"
    label_html = f"<div class='label'>{label}</div>" if label else ""
    kicker_html = f"<div class='kicker'>{kicker}</div>" if kicker else ""
    body_html = f"<div class='body'>{body}</div>" if body else ""
    cta_html = f"<div class='cta'>{cta}</div>" if cta else ""
    chrome_html = (
        "<div class='web'>davidportodiaz.com</div>"
        "<div class='bottom'><div class='actions'>"
        "<div class='action'><span class='icon'>♡</span>Like</div>"
        "<div class='action'><span class='icon'>✎</span>Comenta</div>"
        "<div class='action'><span class='icon'>↗</span>Envía</div>"
        "<div class='action'><span class='icon'>◇</span>Guarda</div>"
        f"</div><div class='cue'>{bottom_cue}</div></div>"
    )
    cover_html += chrome_html

    doc = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><style>
{FONT_IMPORT}
*{{box-sizing:border-box}}html,body{{margin:0;width:1080px;height:1350px;overflow:hidden;background:{palette['bg']}}}
.card{{position:relative;width:1080px;height:1350px;overflow:hidden;background:
 radial-gradient(circle at 78% 14%,rgba(196,120,63,.13),transparent 34%),
 linear-gradient(145deg,{palette['bg']} 0%,#17100d 55%,#090706 100%);{bg_style}}}
.photo-overlay{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(15,12,11,.91) 0%,rgba(15,12,11,.73) 48%,rgba(15,12,11,.28) 100%)}}
.soft-bg{{position:absolute;inset:-28px;background:inherit;filter:blur(16px) saturate(.92) brightness(1.02);transform:scale(1.05);z-index:1}}
.soft-overlay{{position:absolute;inset:0;z-index:2;background:
 radial-gradient(circle at 72% 24%,rgba(196,120,63,.12),transparent 34%),
 linear-gradient(90deg,rgba(15,12,11,.70) 0%,rgba(15,12,11,.52) 50%,rgba(15,12,11,.38) 100%),
 linear-gradient(180deg,rgba(15,12,11,.24) 0%,rgba(15,12,11,.10) 45%,rgba(15,12,11,.66) 100%)}}
.brand,.counter,.web,.content,.cover,.cover-fan,.bottom{{position:absolute;z-index:3}}
.brand{{left:64px;top:55px;color:{palette['text']};font:600 18px/1 Inter,sans-serif;letter-spacing:.18em}}
.counter{{right:64px;top:55px;color:{palette['muted']};font:600 18px/1 Inter,sans-serif;letter-spacing:.08em}}
.web{{right:64px;top:82px;color:{palette['accent']};font:600 17px/1 Inter,sans-serif;letter-spacing:.02em}}
.rule{{position:absolute;z-index:3;left:64px;top:91px;width:68px;height:3px;background:{palette['accent']}}}
.content{{left:64px;top:178px;width:560px;color:{palette['text']}}}
.content.text{{width:900px;top:245px}}
.content.multi_cover{{width:560px;top:190px}}
.content.place{{width:515px;top:205px}}
.content.choice{{width:560px;top:220px}}
.kicker{{font:700 19px/1.2 Inter,sans-serif;letter-spacing:.13em;color:{palette['accent']};margin-bottom:24px}}
.title{{font:700 58px/1.04 'Playfair Display',serif;letter-spacing:-.025em;text-wrap:balance}}
.content.text .title{{font-size:67px;max-width:900px}}
.content.choice .title{{font-size:53px}}
.content.place .title{{font-size:52px}}
.body{{font:500 29px/1.38 Inter,sans-serif;color:{palette['text']};margin-top:28px;max-width:780px}}
.content.text .body{{font-size:31px;max-width:840px}}
.label{{display:inline-block;margin-top:26px;padding:10px 15px;border:1px solid rgba(247,241,232,.38);border-radius:999px;color:{palette['muted']};font:700 17px/1 Inter,sans-serif;letter-spacing:.08em}}
.cta{{margin-top:42px;color:{palette['accent']};font:700 20px/1 Inter,sans-serif;letter-spacing:.14em}}
.cover{{right:64px;top:205px;width:350px;height:720px;object-fit:contain;filter:drop-shadow(0 20px 20px rgba(0,0,0,.45))}}
.content.choice + .cover{{width:330px}}
.content.place + .cover{{right:55px;top:255px;width:310px;height:650px}}
.cover-fan{{right:48px;bottom:112px;width:440px;height:650px}}
.mini-cover{{position:absolute;width:250px;height:520px;object-fit:contain;filter:drop-shadow(0 16px 18px rgba(0,0,0,.45));transform-origin:bottom center}}
.mc3-1{{left:0;bottom:0;transform:rotate(-8deg)}}.mc3-2{{left:95px;bottom:18px;z-index:2}}.mc3-3{{left:190px;bottom:0;transform:rotate(8deg)}}
.mc4-1{{left:-5px;bottom:0;transform:rotate(-11deg)}}.mc4-2{{left:70px;bottom:12px;transform:rotate(-4deg)}}.mc4-3{{left:145px;bottom:12px;transform:rotate(4deg)}}.mc4-4{{left:220px;bottom:0;transform:rotate(11deg)}}
.bottom{{left:64px;right:64px;bottom:44px;display:flex;align-items:flex-end;justify-content:space-between;gap:26px}}
.actions{{display:flex;gap:28px;align-items:center;color:rgba(247,241,232,.78);font:700 18px/1 Inter,sans-serif}}
.action .icon{{color:{palette['accent']};font-size:21px;margin-right:8px}}
.cue{{color:{palette['accent']};font:700 20px/1 Inter,sans-serif;letter-spacing:.13em;white-space:nowrap}}
.footer-note{{display:none}}
</style></head><body><div class='card'>{overlay}<div class='brand'>{esc(data['brand'])}</div><div class='counter'>{index:02d} / {total:02d}</div><div class='rule'></div><div class='{content_class}'>{kicker_html}<div class='title'>{title}</div>{body_html}{label_html}{cta_html}</div>{cover_html}<div class='footer-note'>Portadas reales · fuentes editoriales verificadas en el manifest</div></div></body></html>"""
    return doc, asset_mode


async def ensure_audited_fonts(page) -> None:
    await page.evaluate("document.fonts.ready")
    checks = {
        "Inter 500": "500 24px Inter",
        "Inter 600": "600 24px Inter",
        "Inter 700": "700 24px Inter",
        "Playfair Display 700": "700 24px 'Playfair Display'",
    }
    missing: list[str] = []
    for label, spec in checks.items():
        faces = await page.evaluate("spec => document.fonts.load(spec, 'BESbwy').then(x => x.length)", spec)
        if not faces:
            missing.append(label)
    if missing:
        raise RuntimeError(
            "IG01_RENDER_BLOCKED: no se han cargado las fuentes auditadas: "
            + ", ".join(missing)
            + ". Ejecuta con acceso a fonts.googleapis.com/fonts.gstatic.com y repite el gate. "
            "No exportar con Georgia/Arial/sans-serif como fallback silencioso."
        )


async def screenshot(doc: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as td:
        page_file = Path(td) / "slide.html"
        page_file.write_text(doc, encoding="utf-8")
        async with async_playwright() as p:
            launch_kwargs = {}
            for candidate in SYSTEM_BROWSERS:
                if candidate.exists():
                    launch_kwargs["executable_path"] = str(candidate)
                    break
            browser = await p.chromium.launch(**launch_kwargs)
            page = await browser.new_page(viewport={"width":1080,"height":1350}, device_scale_factor=1)
            await page.goto(page_file.as_uri(), wait_until="networkidle")
            await ensure_audited_fonts(page)
            title = page.locator(".title")
            box = await title.bounding_box()
            if not box or box["y"] < 120 or box["y"] + box["height"] > 1120:
                raise RuntimeError(f"título fuera de zona segura: {box}")
            await page.locator(".card").screenshot(path=str(output))
            await browser.close()


async def render_post(data: dict, post: dict, assets: Path, out: Path, travel_fallback: bool) -> None:
    post_out = out / post["id"]
    modes: list[str] = []
    total = len(post["slides"])
    for i, slide in enumerate(post["slides"], start=1):
        doc, mode = render_slide_html(data, slide, i, total, assets, travel_fallback)
        modes.append(mode)
        await screenshot(doc, post_out / f"{i:02d}.png")
    metadata = {
        "id":post["id"],"date":post["date"],"caption":post["caption"],"hashtags":post["hashtags"],
        "slides":total,"travel_asset_modes":modes,
        "production_status":"TECHNICAL_GATE_ONLY" if "reference_fallback" in modes else "ASSETS_RENDERED"
    }
    post_out.mkdir(parents=True, exist_ok=True)
    (post_out / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK {post['id']} -> {post_out}")


async def run(args) -> None:
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    posts = data["posts"]
    if args.post:
        posts = [p for p in posts if p["id"] == args.post]
        if not posts:
            raise SystemExit(f"ERROR: no existe {args.post}")
    for post in posts:
        await render_post(data, post, args.assets, args.out, args.travel_reference_fallback)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--assets", type=Path, default=Path("build/ig01/assets"))
    ap.add_argument("--out", type=Path, default=Path("build/ig01"))
    ap.add_argument("--post")
    ap.add_argument("--travel-reference-fallback", action="store_true")
    args=ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
