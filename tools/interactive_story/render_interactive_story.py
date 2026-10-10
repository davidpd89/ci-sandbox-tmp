#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, html, json
from pathlib import Path
from typing import Any

W,H=1080,1350
COLORS={"bg":"#11100F","text":"#F7F1E8","a":"#C27937","b":"#8FA2A8"}

FONT_IMPORT="@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800&family=Playfair+Display:wght@700&display=swap');"


def data_uri(path: Path)->str:
    mime="image/png" if path.suffix.lower()==".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def esc(x: str)->str:
    return html.escape(x).replace("\n","<br>")


def body_markup(body: str, emphasis: str="")->str:
    if not emphasis or emphasis not in body:
        return esc(body)
    before, after = body.split(emphasis, 1)
    return f"{esc(before)}<span class='emphasis'>{html.escape(emphasis)}</span>{esc(after)}"


def page_html(image_uri:str, kicker:str, body:str="", choice_a:str="", choice_b:str="",
              footer:str="", overlay:float=.54, small_label:str="", composite:dict[str,str]|None=None,
              composite_row:list[dict[str,str]]|None=None, empty_photo_caption:str="", emphasis:str="")->str:
    choice = ""
    if choice_a or choice_b:
        choice = f'''
        <div class="choices">
          <div class="choice a"><span>A</span>{html.escape(choice_a)}</div>
          <div class="choice b"><span>B</span>{html.escape(choice_b)}</div>
        </div>'''
    composite_html=""
    if composite:
        composite_html=f'''<div class="photo-inset">
          <img src="{composite["uri"]}">
          <div class="photo-caption">{html.escape(composite.get("caption",""))}</div>
        </div>'''
    row_html=""
    if composite_row:
        tiles="".join(f'<div class="mini-photo"><img src="{x["uri"]}"></div>' for x in composite_row)
        row_html=f'<div class="photo-row">{tiles}</div>'
    empty_html=""
    if empty_photo_caption:
        empty_html=f'''<div class="empty-photo"><div class="empty-inner"></div>
        <div class="empty-caption">{html.escape(empty_photo_caption)}</div></div>'''
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
    {FONT_IMPORT}
    html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:{COLORS["bg"]};}}
    body{{font-family:Inter,Arial,sans-serif;color:{COLORS["text"]};position:relative;}}
    .bg{{position:absolute;inset:0;background:url("{image_uri}") center/cover no-repeat;filter:saturate(.88) contrast(1.03);}}
    .veil{{position:absolute;inset:0;background:rgba(0,0,0,{overlay});}}
    .kicker{{position:absolute;top:62px;left:80px;right:80px;font:700 28px Inter,Arial,sans-serif;letter-spacing:1.5px;opacity:.78;}}
    .body{{position:absolute;left:80px;right:80px;top:180px;font:700 68px/1.12 "Playfair Display",Georgia,serif;text-wrap:balance;}}
    .body .emphasis{{font-family:Inter,Arial,sans-serif;font-weight:800;font-size:.86em;line-height:1.18;letter-spacing:.015em;display:inline-block;margin-top:.12em;}}
    .label{{position:absolute;left:80px;right:80px;top:135px;font:700 30px Inter,Arial,sans-serif;letter-spacing:.5px;color:{COLORS["a"]};}}
    .choices{{position:absolute;left:80px;right:80px;bottom:175px;display:grid;gap:28px;}}
    .choice{{border:3px solid rgba(247,241,232,.55);border-radius:22px;background:rgba(17,16,15,.82);padding:30px 34px;font:700 48px/1.1 Inter,Arial,sans-serif;display:flex;gap:25px;align-items:flex-start;}}
    .choice span{{font-size:38px;min-width:50px;height:50px;border-radius:50%;display:grid;place-items:center;color:#11100F;}}
    .choice.a span{{background:{COLORS["a"]};}} .choice.b span{{background:{COLORS["b"]};}}
    .footer{{position:absolute;left:80px;right:80px;bottom:76px;font:600 26px Inter,Arial,sans-serif;opacity:.8;text-align:center;}}
    .brand{{position:absolute;left:65px;bottom:30px;font:600 20px Inter,Arial,sans-serif;opacity:.28;letter-spacing:.5px;}}
    .photo-inset{{position:absolute;width:440px;height:530px;right:75px;bottom:115px;background:#f5f1e9;padding:18px 18px 54px;transform:rotate(-2deg);box-shadow:0 16px 50px rgba(0,0,0,.35);}}
    .photo-inset img{{width:100%;height:100%;object-fit:cover;}}
    .photo-caption{{position:absolute;left:18px;right:18px;bottom:14px;color:#312820;font:700 22px Inter,Arial,sans-serif;text-align:center;}}
    .photo-row{{position:absolute;left:80px;right:80px;bottom:95px;display:grid;grid-template-columns:repeat(3,1fr);gap:24px;}}
    .mini-photo{{height:330px;background:#f5f1e9;padding:13px 13px 38px;box-shadow:0 12px 38px rgba(0,0,0,.34);}}
    .mini-photo:nth-child(1){{transform:rotate(-2deg)}} .mini-photo:nth-child(2){{transform:rotate(1deg)}} .mini-photo:nth-child(3){{transform:rotate(-1deg)}}
    .mini-photo img{{width:100%;height:100%;object-fit:cover;}}
    .empty-photo{{position:absolute;width:470px;height:560px;left:305px;bottom:120px;background:#f5f1e9;padding:20px 20px 62px;box-shadow:0 16px 50px rgba(0,0,0,.35);}}
    .empty-inner{{width:100%;height:100%;background:#d9d3c9;border:2px solid #c2bbb0;}}
    .empty-caption{{position:absolute;left:20px;right:20px;bottom:18px;color:#312820;font:800 28px Inter,Arial,sans-serif;text-align:center;letter-spacing:.5px;}}
    </style></head><body><div class="bg"></div><div class="veil"></div>
    <div class="kicker">{html.escape(kicker)}</div>
    {f'<div class="label">{html.escape(small_label)}</div>' if small_label else ''}
    <div class="body">{body_markup(body, emphasis)}</div>{choice}{composite_html}{row_html}{empty_html}
    {f'<div class="footer">{html.escape(footer)}</div>' if footer else ''}
    <div class="brand">AUTORA DEMO DÍAZ</div></body></html>'''


def ensure_audited_fonts(page)->None:
    page.evaluate("document.fonts.ready")
    checks={
        "Inter 600":"600 24px Inter",
        "Inter 700":"700 24px Inter",
        "Inter 800":"800 24px Inter",
        "Playfair Display 700":"700 24px 'Playfair Display'",
    }
    missing=[]
    for label,spec in checks.items():
        if not page.evaluate("spec => document.fonts.check(spec)",spec):
            missing.append(label)
    if missing:
        raise RuntimeError(
            "IG09_RENDER_BLOCKED: no se han cargado las fuentes auditadas: "
            + ", ".join(missing)
            + ". Ejecuta con acceso a fonts.googleapis.com/fonts.gstatic.com y repite el gate. "
            "No exportar con Georgia/Arial como fallback silencioso."
        )


def render(manifest:dict[str,Any], assets:Path, out:Path)->None:
    from playwright.sync_api import sync_playwright
    asset_map={}
    for key, spec in manifest["assets"].items():
        p=assets/spec["filename"]
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}. Download from {spec['source_url']}")
        asset_map[key]=data_uri(p)
    out.mkdir(parents=True,exist_ok=True)
    outputs=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":W,"height":H},device_scale_factor=1)
        for ep in manifest["episodes"]:
            ep_id=ep["id"]
            epdir=out/ep_id
            epdir.mkdir(exist_ok=True)
            for slide in ep["slides"]:
                variants=slide.get("variants")
                todo=variants.items() if variants else [("",slide)]
                for suffix,spec in todo:
                    merged={**slide, **spec} if variants else spec
                    asset=merged.get("asset",ep["asset"])
                    composite=None
                    if merged.get("composite_asset"):
                        composite={"uri":asset_map[merged["composite_asset"]],"caption":merged.get("composite_caption","")}
                    composite_row=None
                    if merged.get("composite_assets"):
                        composite_row=[{"uri":asset_map[k]} for k in merged["composite_assets"]]
                    htmltxt=page_html(
                        asset_map[asset],ep["kicker"],merged.get("body",""),merged.get("choice_a",""),
                        merged.get("choice_b",""),merged.get("footer",""),float(merged.get("overlay",.54)),
                        merged.get("small_label",""),composite,composite_row,merged.get("empty_photo_caption",""),
                        merged.get("emphasis","")
                    )
                    page.set_content(htmltxt,wait_until="networkidle")
                    ensure_audited_fonts(page)
                    suffix_txt=f"_{suffix}" if suffix else ""
                    target=epdir/f"{ep_id}_s{slide['n']}{suffix_txt}.png"
                    page.screenshot(path=str(target),full_page=False)
                    outputs.append(str(target))
        browser.close()
    (out/"manifest_render.json").write_text(json.dumps({
        "source_manifest":manifest.get("id","ig09"),"outputs":outputs,
        "assets":{k:v["source_url"] for k,v in manifest["assets"].items()}
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Rendered {len(outputs)} files into {out}")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("manifest",type=Path)
    ap.add_argument("--assets",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
    render(manifest,args.assets,args.out)


if __name__=="__main__":
    main()
