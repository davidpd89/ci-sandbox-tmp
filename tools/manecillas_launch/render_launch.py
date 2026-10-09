#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, html, json
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
W,H=1080,1350

def esc(x): return html.escape(str(x or ''))
def file_uri(p:Path)->str: return p.resolve().as_uri()
def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()
def verify_cover(p:Path,cfg:dict)->None:
    if sha(p)!=cfg['sha256']: raise SystemExit('IG06_RENDER_BLOCKED: portada SHA-256 incorrecto')
    with Image.open(p) as im:
        if list(im.size)!=[cfg['width'],cfg['height']]: raise SystemExit(f"IG06_RENDER_BLOCKED: portada {im.size}, esperada {(cfg['width'],cfg['height'])}")
def font_css(playfair:Path|None, inter:Path|None)->str:
    if playfair and inter:
        return f"@font-face{{font-family:Playfair Display;src:url('{file_uri(playfair)}');font-weight:700}}@font-face{{font-family:Inter;src:url('{file_uri(inter)}');font-weight:100 900}}"
    return "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&family=Playfair+Display:wght@700&display=swap');"
def slide_html(s:dict,kind:str,asset:Path,cover:Path,pal:dict,font_rule:str)->str:
    title=esc(s.get('title')); body=esc(s.get('body')); kicker=esc(s.get('kicker')); footer=esc(s.get('footer')); support=esc(s.get('support')); question=esc(s.get('question')); secondary=esc(s.get('secondary')); quote=esc(s.get('quote'))
    if kind=='archive':
        visual=f"<div class='photo' style=\"background-image:linear-gradient(180deg,transparent 55%,rgba(23,18,11,.45)),url('{file_uri(asset)}')\"></div>"
        timeline=esc(s.get('timeline'))
        content="<div class='card'>" + (f"<div class='kicker'>{kicker}</div>" if kicker else '') + (f"<h1>{title}</h1>" if title else '') + (f"<p>{body}</p>" if body else '') + (f"<div class='timeline'>{timeline}</div>" if timeline else '') + (f"<div class='footer'>{footer}</div>" if footer else '') + "</div>"
    elif kind=='bridge':
        visual=''; content=f"<div class='bridge'>{body}</div>"
    elif kind=='excerpt':
        visual=''; content="<div class='excerpt'><div class='label'>FRAGMENTO REAL</div>" + f"<blockquote>{quote}</blockquote>" + (f"<p>{secondary}</p>" if secondary else '') + f"<div class='footer'>{footer}</div></div>"
    else:
        visual=f"<div class='bookwrap'><img src='{file_uri(cover)}'></div>"
        content="<div class='bookcopy'>" + (f"<h1>{title}</h1>" if title else '') + (f"<p>{support}</p>" if support else '') + (f"<div class='question'>{question}</div>" if question else '') + "</div>"
    css = r"""__FONT__
*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1350px;overflow:hidden;background:__INK__;color:__PAPER__;font-family:Inter,sans-serif}body{position:relative}.photo{height:760px;background-size:cover;background-position:center}.card{position:absolute;left:58px;right:58px;bottom:56px;min-height:500px;background:__PAPER__;color:__INK__;padding:48px 52px;border-top:10px solid __COPPER__}h1{font-family:'Playfair Display',serif;font-size:70px;line-height:1.02;margin:0 0 26px}p{font-size:36px;line-height:1.25;margin:0 0 24px}.kicker,.label{font-weight:600;letter-spacing:.08em;font-size:23px;color:__COPPER__;margin-bottom:20px}.timeline{font:600 34px Inter;margin-top:22px;color:__BRONZE__}.footer{font-size:23px;margin-top:30px;color:__GREY__}.bridge{height:100%;display:flex;align-items:center;padding:100px;font-family:'Playfair Display';font-weight:700;font-size:94px;line-height:1.03;border-left:18px solid __COPPER__}.excerpt{height:100%;padding:115px 92px;background:__PAPER__;color:__INK__}blockquote{font-family:'Playfair Display';font-weight:700;font-size:82px;line-height:1.08;margin:90px 0 55px}.excerpt p{font-size:31px;line-height:1.35}.bookwrap{position:absolute;left:70px;top:120px;width:390px;height:585px;display:flex;align-items:center;justify-content:center}.bookwrap img{max-width:100%;max-height:100%;object-fit:contain;box-shadow:0 20px 40px rgba(0,0,0,.35)}.bookcopy{position:absolute;left:520px;right:70px;top:160px;bottom:110px;display:flex;flex-direction:column;justify-content:center}.bookcopy h1{font-size:65px}.bookcopy p{font-size:34px}.question{margin-top:38px;border-top:3px solid __COPPER__;padding-top:30px;font:600 34px/1.25 Inter}
""".replace('__FONT__',font_rule).replace('__INK__',pal['ink']).replace('__PAPER__',pal['paper']).replace('__COPPER__',pal['copper']).replace('__BRONZE__',pal['bronze']).replace('__GREY__',pal['grey'])
    return "<!doctype html><html><head><meta charset='utf-8'><style>" + css + "</style></head><body>" + visual + content + "</body></html>"
def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('manifest',type=Path); ap.add_argument('--assets',type=Path,required=True); ap.add_argument('--cover',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--playfair-font',type=Path); ap.add_argument('--inter-font',type=Path); a=ap.parse_args()
    data=json.loads(a.manifest.read_text(encoding='utf-8')); verify_cover(a.cover,data['cover']); a.out.mkdir(parents=True,exist_ok=True); fr=font_css(a.playfair_font,a.inter_font); outputs=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True); page=browser.new_page(viewport={'width':W,'height':H},device_scale_factor=1)
        for ep in data['episodes']:
            asset=a.assets/f"{ep['id']}_source.jpg"
            if not asset.exists(): raise SystemExit(f"IG06_RENDER_BLOCKED: falta {asset}")
            for i,s in enumerate(ep['slides'],1):
                doc=slide_html(s,s['kind'],asset,a.cover,data['palette'],fr); page.set_content(doc,wait_until='networkidle')
                ok=page.evaluate("""async()=>{await document.fonts.ready; const a=await document.fonts.load("700 60px 'Playfair Display'"); const b=await document.fonts.load("600 36px 'Inter'"); return a.length>0&&b.length>0}""")
                if not ok: raise SystemExit('IG06_RENDER_BLOCKED: Playfair Display 700 / Inter 600 no cargadas')
                out=a.out/f"{ep['id']}_s{i}.png"; page.screenshot(path=str(out),full_page=True); outputs.append({'episode':ep['id'],'slide':i,'file':out.name,'sha256':sha(out)})
        browser.close()
    (a.out/'ig06_render_manifest.json').write_text(json.dumps({'source':data['id'],'status':'RENDERED_NOT_SCHEDULED','manifest_sha256':sha(a.manifest),'cover_sha256':sha(a.cover),'outputs':outputs},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"Rendered {len(outputs)} slides · RENDERED_NOT_SCHEDULED")
if __name__=='__main__': main()
