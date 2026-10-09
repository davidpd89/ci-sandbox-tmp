#!/usr/bin/env python3
"""Render IG-14 fictional book covers/back covers from JSON. No AI, no stock.

Dependency:
  pip install pillow
  fontconfig + Playfair Display + Inter installed locally

Usage:
  python tools/fake_books/render_fake_books.py tools/fake_books/ig14_manifest.json --out build/ig14
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, textwrap
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont

W,H=1080,1350
PALETTES={
 "A":("#F3EBDD","#1E1915","#C27937"),
 "B":("#AAB9C0","#17120B","#F7F1E8"),
 "C":("#B96F55","#F5E9D8","#201914"),
 "D":("#9EAA8B","#1B1B17","#F5F0E7"),
 "E":("#D8B95D","#1D1813","#F8F2E5"),
 "F":("#7B4B4A","#F3E8D9","#1B1714")
}


def require_font(query: str, expected_family: str, expected_styles: tuple[str, ...]) -> str:
 if not shutil.which("fc-match"):
  raise RuntimeError("IG14_RENDER_BLOCKED: falta fc-match/fontconfig. Instala fontconfig y Playfair Display + Inter antes del gate.")
 try:
  raw=subprocess.check_output(["fc-match","-f","%{family}\n%{style}\n%{file}",query],text=True).strip().splitlines()
 except Exception as exc:
  raise RuntimeError(f"IG14_RENDER_BLOCKED: no se pudo resolver {query!r}") from exc
 if len(raw)<3:
  raise RuntimeError(f"IG14_RENDER_BLOCKED: fontconfig no devolvió familia/estilo/ruta para {query!r}")
 family,style,path=raw[0],raw[1],raw[2].strip()
 if expected_family.casefold() not in family.casefold() or not Path(path).exists():
  raise RuntimeError(
   f"IG14_RENDER_BLOCKED: se pidió {query!r}, pero fontconfig resolvió {family!r} ({style!r}). "
   "No se permite fallback tipográfico silencioso."
  )
 normalized=style.casefold().replace(" ","").replace("-","")
 if not any(token.casefold().replace(" ","").replace("-","") in normalized for token in expected_styles):
  raise RuntimeError(
   f"IG14_RENDER_BLOCKED: {query!r} resolvió estilo {style!r}; se esperaba {expected_styles!r}. "
   "La familia correcta con peso distinto también es un fallback."
  )
 return path

FONT_PATHS={
 "serif_bold":require_font("Playfair Display:style=ExtraBold","Playfair Display",("ExtraBold","Extra Bold")),
 "sans":require_font("Inter:style=Medium","Inter",("Medium",)),
 "sans_bold":require_font("Inter:style=SemiBold","Inter",("SemiBold","Semi Bold")),
}

def hx(s):
 s=s.lstrip('#'); return tuple(int(s[i:i+2],16) for i in (0,2,4))

def font(kind,size):
 return ImageFont.truetype(FONT_PATHS[kind],size=size)

def measure(draw,text,font_obj,line_spacing=1.02):
 lines=text.split('\n')
 boxes=[draw.textbbox((0,0),line,font=font_obj) for line in lines]
 width=max((b[2]-b[0] for b in boxes),default=0)
 height=sum((b[3]-b[1] for b in boxes))+int(font_obj.size*(line_spacing-1)*max(0,len(lines)-1))
 return width,height

def fit_font(draw,text,kind,max_size,min_size,max_width,max_height,line_spacing=1.02,label="text"):
 for size in range(max_size,min_size-1,-2):
  f=font(kind,size); width,height=measure(draw,text,f,line_spacing)
  if width<=max_width and height<=max_height:return f,size
 f=font(kind,min_size); width,height=measure(draw,text,f,line_spacing)
 raise RuntimeError(
  f"IG14_RENDER_BLOCKED: {label} no cabe ni a {min_size}px: {width}x{height}; "
  f"máximo {max_width}x{max_height}. Corregir manifest/layout, no recortar el PNG después."
 )

def centered_lines(draw,text,y,font_obj,fill,spacing=8):
 lines=text.split('\n')
 heights=[]
 for line in lines:
  b=draw.textbbox((0,0),line,font=font_obj); heights.append(b[3]-b[1])
 cy=y
 for line,h in zip(lines,heights):
  b=draw.textbbox((0,0),line,font=font_obj); tw=b[2]-b[0]
  draw.text(((W-tw)//2,cy),line,font=font_obj,fill=fill)
  cy+=h+spacing
 return cy

def symbol(draw,kind,cx,cy,size,ink,accent,bg):
 lw=max(7,size//24)
 if kind=="bookmark_corner":
  draw.rectangle((cx-size*.34,cy-size*.42,cx+size*.16,cy+size*.40),outline=ink,width=lw)
  draw.polygon([(cx+size*.02,cy-size*.42),(cx+size*.18,cy-size*.42),(cx+size*.18,cy-size*.10),(cx+size*.10,cy-size*.18),(cx+size*.02,cy-size*.10)],fill=accent)
  draw.polygon([(cx+size*.16,cy-size*.42),(cx+size*.36,cy-size*.24),(cx+size*.16,cy-size*.24)],outline=ink,fill=bg)
 elif kind=="character_map":
  pts=[(cx-size*.28,cy-size*.18),(cx,cy-size*.32),(cx+size*.28,cy-size*.16),(cx-size*.15,cy+size*.22),(cx+size*.18,cy+size*.28)]
  for a,b in [(0,1),(1,2),(0,3),(1,4),(3,4)]:draw.line((*pts[a],*pts[b]),fill=ink,width=lw)
  for i,(x,y) in enumerate(pts):draw.ellipse((x-size*.07,y-size*.07,x+size*.07,y+size*.07),fill=accent if i==4 else bg,outline=ink,width=lw)
  q=font("sans_bold",int(size*.13)); draw.text((pts[4][0]-size*.035,pts[4][1]-size*.085),"?",font=q,fill=ink)
 elif kind=="suitcase_books":
  draw.rounded_rectangle((cx-size*.36,cy-size*.10,cx+size*.36,cy+size*.38),radius=size*.05,outline=ink,width=lw)
  draw.arc((cx-size*.16,cy-size*.28,cx+size*.16,cy+size*.05),180,360,fill=ink,width=lw)
  colors=[accent,ink,bg,accent]
  for i in range(4):
   x=cx-size*.25+i*size*.14; top=cy-size*(.40+.05*(i%2)); draw.rectangle((x,top,x+size*.105,cy-size*.08),fill=colors[i],outline=ink,width=max(3,lw//2))
 elif kind=="redacted_blurb":
  for i in range(5):
   y=cy-size*.30+i*size*.14; x1=cx-size*.34; x2=cx+size*(.34 if i%2==0 else .24); draw.line((x1,y,x2,y),fill=ink,width=max(5,lw))
  draw.rectangle((cx-size*.38,cy+size*.01,cx+size*.38,cy+size*.39),fill=accent)
 elif kind=="thin_pages":
  draw.rectangle((cx-size*.35,cy-size*.30,cx+size*.28,cy+size*.30),outline=ink,width=lw)
  for i in range(12):
   y=cy-size*.26+i*size*.045; draw.line((cx+size*.18,y,cx+size*.35,y),fill=accent,width=max(3,lw//2))
 elif kind=="book_bag":
  draw.polygon([(cx-size*.34,cy-size*.15),(cx+size*.34,cy-size*.15),(cx+size*.28,cy+size*.38),(cx-size*.28,cy+size*.38)],outline=ink,fill=bg)
  draw.arc((cx-size*.18,cy-size*.36,cx+size*.18,cy+size*.02),180,360,fill=ink,width=lw)
  for i,col in enumerate([accent,ink,accent]):
   x=cx-size*.22+i*size*.16; draw.rectangle((x,cy-size*.34,x+size*.12,cy-size*.13),fill=col,outline=ink,width=max(3,lw//2))

def cover(ep,series):
 bg,fg,accent=map(hx,PALETTES[ep['palette']]); im=Image.new('RGB',(W,H),bg); d=ImageDraw.Draw(im)
 fsmall=font('sans_bold',24); d.text((70,62),series['disclosure_cover'],font=fsmall,fill=fg)
 ftitle,_=fit_font(d,ep['title'],'serif_bold',150,90,900,340,label=f"{ep['id']} cover title")
 y=centered_lines(d,ep['title'],190,ftitle,fg,6)
 fsub=font('sans_bold',44); lines=textwrap.wrap(ep['subtitle'],width=35,break_long_words=False)
 sy=max(y+58,520)
 for line in lines:
  b=d.textbbox((0,0),line,font=fsub); width=b[2]-b[0]
  if width>900: raise RuntimeError(f"IG14_RENDER_BLOCKED: {ep['id']} subtitle line overflows: {line!r}")
  d.text(((W-width)//2,sy),line,font=fsub,fill=fg); sy+=58
 if sy>770: raise RuntimeError(f"IG14_RENDER_BLOCKED: {ep['id']} subtitle invades symbol area")
 symbol(d,ep['symbol'],W//2,910,330,fg,accent,bg)
 fbrand=font('sans',22); d.text((70,1264),series['brand_line'],font=fbrand,fill=fg)
 return im

def back(ep,series):
 bg,fg,accent=map(hx,PALETTES[ep['palette']]); im=Image.new('RGB',(W,H),bg); d=ImageDraw.Draw(im)
 d.text((70,62),series['disclosure_back'],font=font('sans_bold',28),fill=fg)
 fback,_=fit_font(d,ep['back'],'serif_bold',88,62,880,320,label=f"{ep['id']} back title")
 end=centered_lines(d,ep['back'],210,fback,fg,12)
 if end>555: raise RuntimeError(f"IG14_RENDER_BLOCKED: {ep['id']} back title invades divider")
 d.line((70,590,1010,590),fill=accent,width=9)
 d.text((70,645),'INCLUYE:',font=font('sans_bold',30),fill=fg)
 fitem=font('sans_bold',40); y=710
 for item in ep['includes']:
  lines=textwrap.wrap('— '+item,width=42,break_long_words=False)
  for line in lines:
   b=d.textbbox((0,0),line,font=fitem)
   if b[2]-b[0]>900: raise RuntimeError(f"IG14_RENDER_BLOCKED: {ep['id']} includes overflows: {line!r}")
   d.text((82,y),line,font=fitem,fill=fg); y+=54
  y+=18
 if y>1190: raise RuntimeError(f"IG14_RENDER_BLOCKED: {ep['id']} includes invades brand footer")
 d.text((70,1264),series['brand_line'],font=font('sans',22),fill=fg)
 return im

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('manifest',type=Path); ap.add_argument('--out',required=True,type=Path); args=ap.parse_args()
 series=json.loads(args.manifest.read_text(encoding='utf-8')); args.out.mkdir(parents=True,exist_ok=True); outputs=[]
 for ep in series['episodes']:
  for n,im in [(1,cover(ep,series)),(2,back(ep,series))]:
   p=args.out/f"{ep['id']}_s{n}.png"; im.save(p,'PNG',optimize=True)
   with Image.open(p) as check:
    if check.size!=(W,H): raise RuntimeError(f"IG14_RENDER_BLOCKED: {p.name} has {check.size}, expected {(W,H)}")
   outputs.append(str(p))
 (args.out/'ig14_render_manifest.json').write_text(json.dumps({
  'source':series['id'],
  'font_policy':'Playfair Display 800 + Inter 600/500; no fallback',
  'outputs':outputs,
  'status':'RENDERED_NOT_SCHEDULED'
 },ensure_ascii=False,indent=2),encoding='utf-8')
 print(f"Rendered {len(outputs)} slides")

if __name__=='__main__':main()
