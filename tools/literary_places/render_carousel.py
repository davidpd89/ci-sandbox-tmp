#!/usr/bin/env python3
"""Render 4 slides por mini-guía IG-13. No altera el contenido de las fotografías."""

from __future__ import annotations
import argparse
import json
import pathlib
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=pathlib.Path(__file__).resolve().parent
MANIFEST=ROOT/"manifest.json"
ASSETS=ROOT/"assets"
OUTPUT=ROOT/"output"

W,H=1080,1350
M=54
BG=(247,243,235)
INK=(28,25,21)
MUTED=(92,84,75)
RULE=(202,195,184)


def fnt(size,bold=False):
    # El kit exige una sans legible, no una familia concreta. Mantenemos un
    # orden cerrado y reproducible entre las familias neutras ya usadas.
    names=(
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name,size)
        except OSError:
            pass
    raise RuntimeError(
        "IG13_RENDER_BLOCKED: no se encontró DejaVu Sans ni Arial. "
        "Instala una sans autorizada y repite el gate; no usar la fuente bitmap por defecto de Pillow."
    )


def asset(item_id):
    matches=[p for p in ASSETS.glob(f"{item_id}.*") if p.suffix.lower() in {".jpg",".jpeg",".png",".webp"}]
    if len(matches)!=1:
        raise FileNotFoundError(f"{item_id}: expected exactly 1 asset, got {len(matches)}")
    return matches[0]


def wrap(draw,text,font,maxw):
    out=[]
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            out.append("")
            continue
        line=""
        for word in paragraph.split():
            test=word if not line else line+" "+word
            box=draw.textbbox((0,0),test,font=font)
            if box[2]-box[0] <= maxw:
                line=test
            else:
                if line:
                    out.append(line)
                line=word
        if line:
            out.append(line)
    return out


def place_photo(im,path,box):
    src=Image.open(path).convert("RGB")
    fitted=ImageOps.contain(src,(box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS)
    panel=Image.new("RGB",(box[2]-box[0],box[3]-box[1]),BG)
    panel.paste(fitted,((panel.width-fitted.width)//2,(panel.height-fitted.height)//2))
    im.paste(panel,box[:2])


def draw_lines(draw,text,y,font,maxw,center=False,fill=INK,spacing=10):
    for line in wrap(draw,text,font,maxw):
        if not line:
            y+=20
            continue
        b=draw.textbbox((0,0),line,font=font)
        x=(W-(b[2]-b[0]))//2 if center else M
        draw.text((x,y),line,font=font,fill=fill)
        y+=(b[3]-b[1])+spacing
    return y


def make_slide(item,num,path):
    im=Image.new("RGB",(W,H),BG)
    d=ImageDraw.Draw(im)
    if num==1:
        place_photo(im,path,(M,45,W-M,900))
        d.line((M,930,W-M,930),fill=RULE,width=2)
        draw_lines(d,item["slides"][0],970,fnt(53,True),W-2*M,True,INK,10)
    elif num in (2,3):
        place_photo(im,path,(M,45,W-M,640))
        d.line((M,670,W-M,670),fill=RULE,width=2)
        draw_lines(d,item["slides"][num-1],710,fnt(39,False),W-2*M,False,INK,12)
    else:
        place_photo(im,path,(M,45,W-M,770))
        d.line((M,800,W-M,800),fill=RULE,width=2)
        y=840
        y=draw_lines(d,item["slides"][3],y,fnt(31,False),W-2*M,False,MUTED,9)
        if item.get("share_alike_notice"):
            y+=18
            draw_lines(d,item["share_alike_notice"],y,fnt(26,True),W-2*M,False,INK,8)
    return im


def render(item):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    p=asset(item["id"])
    for num in range(1,5):
        im=make_slide(item,num,p)
        im.save(OUTPUT/f"{item['id']}_slide{num}.png",optimize=True)
    print("RENDERED",item["id"])


def main():
    ap=argparse.ArgumentParser()
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--item")
    g.add_argument("--all",action="store_true")
    args=ap.parse_args()
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    items=data["items"] if args.all else [x for x in data["items"] if x["id"]==args.item]
    if not items:
        raise SystemExit(f"Unknown item: {args.item}")
    # Preflight antes de crear outputs.
    fnt(20,False)
    fnt(20,True)
    for it in items:
        render(it)


if __name__=="__main__":
    main()
