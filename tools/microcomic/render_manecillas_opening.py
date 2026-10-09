#!/usr/bin/env python3
# Deterministic SVG renderer for IG-10, verified opening of Las manecillas del recuerdo.
# Usage: python tools/microcomic/render_manecillas_opening.py --out build/ig10
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

W, H = 1080, 1350
P = {
    "ink": "#17120B", "walnut": "#4C351A", "leather": "#6A4C28",
    "copper": "#C27937", "paper": "#F4EBDD", "blue": "#6E8EC5",
    "skin_tomas": "#C98F6B", "skin_manuel": "#B98261",
    "hair_tomas": "#3A2A23", "hair_manuel": "#82776C",
}
SOURCE_DOC_ID = "1CtjHvvy7BxBm-H7I5CXh5p7wK3QcykCt"
SOURCE_LINES = [
    "Tomás contó las siete veces que su abuelo miró el reloj durante el desayuno.",
    "Los domingos normales, Manuel apenas lo miraba.",
    "Mañana era la cita con el cardiólogo.",
    "El chocolate llevaba cinco minutos en la mesa y ninguno de los dos lo había tocado.",
]
REFERENCE_URLS = [
    "https://www.pexels.com/photo/bearded-man-sitting-beside-the-boy-8307480/",
    "https://www.pexels.com/photo/grandfather-pouring-milk-on-a-tall-glass-for-his-grandson-7118303/",
]
LICENSE_URL = "https://www.pexels.com/es-es/license/"
FONT_FACE = """
@font-face {
  font-family: 'IG10Inter';
  src: local('Inter');
  font-style: normal;
  font-weight: 100 900;
}
"""


def esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def narr_box(text: str, x: int = 72, y: int = 78, w: int = 850, font_size: int = 51) -> str:
    words = text.split()
    lines, current = [], []
    for word in words:
        probe = " ".join(current + [word])
        if len(probe) > 38 and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    line_h = int(font_size * 1.18)
    h = 86 + len(lines) * line_h
    tspans = "".join(
        f'<tspan x="{x+34}" y="{y+58+i*line_h}">{esc(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" fill="{P["paper"]}" fill-opacity=".96" '
        f'stroke="{P["ink"]}" stroke-width="5"/>'
        f'<text font-family="IG10Inter, Inter, sans-serif" font-size="{font_size}" font-weight="700" fill="{P["ink"]}">{tspans}</text>'
    )


def signature() -> str:
    return f'<text x="64" y="1300" font-family="IG10Inter,Inter,sans-serif" font-size="21" font-weight="600" fill="{P["ink"]}" opacity=".34">AUTORA DEMO DÍAZ</text>'


def page_ref() -> str:
    return f'<text x="1008" y="1300" text-anchor="end" font-family="IG10Inter,Inter,sans-serif" font-size="20" font-weight="600" fill="{P["ink"]}" opacity=".42">Las manecillas del recuerdo · pág. 13</text>'


def cup(cx: float, cy: float, scale: float = 1.0) -> str:
    return f'''<g transform="translate({cx},{cy}) scale({scale})">
      <ellipse cx="0" cy="0" rx="66" ry="22" fill="#E9D6BA" stroke="{P["ink"]}" stroke-width="8"/>
      <path d="M -62 0 L -52 92 Q 0 112 52 92 L 62 0 Z" fill="#DFC29B" stroke="{P["ink"]}" stroke-width="8"/>
      <path d="M 58 28 Q 106 20 102 60 Q 98 92 58 78" fill="none" stroke="{P["ink"]}" stroke-width="8"/>
      <ellipse cx="0" cy="0" rx="50" ry="15" fill="#6B412A"/></g>'''


def wristwatch(x: float, y: float, angle: float = 0) -> str:
    return f'''<g transform="translate({x},{y}) rotate({angle})">
      <rect x="-34" y="-8" width="68" height="16" rx="8" fill="{P["leather"]}"/>
      <circle cx="0" cy="0" r="23" fill="#D9C9AC" stroke="{P["ink"]}" stroke-width="7"/>
      <line x1="0" y1="0" x2="0" y2="-12" stroke="{P["ink"]}" stroke-width="4" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="10" y2="5" stroke="{P["ink"]}" stroke-width="4" stroke-linecap="round"/></g>'''


def face(cx: float, cy: float, skin: str, hair: str, child: bool = False, gaze: str = "front") -> str:
    rx, ry = (62, 70) if child else (73, 80)
    eye_offset = 22 if child else 26
    eye_dx = 2 if gaze == "right" else (-2 if gaze == "left" else 0)
    return f'''<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{skin}" stroke="{P["ink"]}" stroke-width="11"/>
      <path d="M {cx-rx+8} {cy-35} Q {cx-25} {cy-93} {cx+18} {cy-76} Q {cx+rx-3} {cy-83} {cx+rx-5} {cy-25} Q {cx+20} {cy-46} {cx-rx+8} {cy-35} Z"
        fill="{hair}" stroke="{P["ink"]}" stroke-width="11" stroke-linejoin="round"/>
      <circle cx="{cx-eye_offset+eye_dx}" cy="{cy+3}" r="7" fill="{P["ink"]}"/>
      <circle cx="{cx+eye_offset+eye_dx}" cy="{cy+3}" r="7" fill="{P["ink"]}"/>
      <path d="M {cx-18} {cy+38} L {cx+18} {cy+38}" stroke="{P["ink"]}" stroke-width="7" stroke-linecap="round"/>'''


def tomas(x: float = 330, y: float = 770, gaze: str = "right") -> str:
    head_y = y - 165
    return f'''<g id="tomas">
      <path d="M {x-45} {y+155} Q {x-70} {y+260} {x-100} {y+355}" fill="none" stroke="{P["walnut"]}" stroke-width="52" stroke-linecap="round"/>
      <path d="M {x+45} {y+155} Q {x+62} {y+260} {x+92} {y+355}" fill="none" stroke="{P["walnut"]}" stroke-width="52" stroke-linecap="round"/>
      <rect x="{x-95}" y="{y-30}" width="190" height="245" rx="75" fill="{P["blue"]}" stroke="{P["ink"]}" stroke-width="11"/>
      <path d="M {x-70} {y+25} Q {x-130} {y+115} {x-165} {y+170}" fill="none" stroke="{P["skin_tomas"]}" stroke-width="34" stroke-linecap="round"/>
      <path d="M {x+70} {y+25} Q {x+130} {y+115} {x+165} {y+170}" fill="none" stroke="{P["skin_tomas"]}" stroke-width="34" stroke-linecap="round"/>
      {face(x, head_y, P["skin_tomas"], P["hair_tomas"], True, gaze)}</g>'''


def manuel(x: float = 735, y: float = 745, look_watch: bool = True) -> str:
    head_y = y - 185
    right_arm = f'<path d="M {x+90} {y+30} Q {x+125} {y+85} {x+48} {y+125}" fill="none" stroke="{P["skin_manuel"]}" stroke-width="38" stroke-linecap="round"/>'
    if look_watch:
        left_arm = f'<path d="M {x-88} {y+28} Q {x-145} {y+65} {x-95} {y+116}" fill="none" stroke="{P["skin_manuel"]}" stroke-width="38" stroke-linecap="round"/>'
        watch = wristwatch(x - 100, y + 110, -20)
    else:
        left_arm = f'<path d="M {x-88} {y+28} Q {x-145} {y+120} {x-170} {y+175}" fill="none" stroke="{P["skin_manuel"]}" stroke-width="38" stroke-linecap="round"/>'
        watch = wristwatch(x - 145, y + 145, 18)
    return f'''<g id="manuel">
      <path d="M {x-50} {y+190} Q {x-65} {y+300} {x-75} {y+390}" fill="none" stroke="{P["ink"]}" stroke-width="62" stroke-linecap="round"/>
      <path d="M {x+50} {y+190} Q {x+68} {y+300} {x+80} {y+390}" fill="none" stroke="{P["ink"]}" stroke-width="62" stroke-linecap="round"/>
      <rect x="{x-112}" y="{y-35}" width="224" height="310" rx="92" fill="{P["leather"]}" stroke="{P["ink"]}" stroke-width="11"/>
      {left_arm}{right_arm}{watch}
      {face(x, head_y, P["skin_manuel"], P["hair_manuel"], False, "left")}</g>'''


def dining_background(cups_focus: bool = False) -> str:
    table_y = 900 if not cups_focus else 760
    return f'''<rect width="{W}" height="{H}" fill="{P["paper"]}"/>
      <rect x="0" y="0" width="{W}" height="420" fill="#DDD6CC"/>
      <rect x="110" y="250" width="860" height="12" rx="6" fill="{P["walnut"]}" opacity=".45"/>
      <rect x="90" y="{table_y}" width="900" height="{H-table_y+40}" rx="60" fill="{P["walnut"]}" stroke="{P["ink"]}" stroke-width="11"/>'''


def panel_svg(index: int) -> str:
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    focus = index == 4
    parts.append(dining_background(focus))
    if focus:
        parts += ['<g opacity=".92">', tomas(250, 630), manuel(820, 610, False), '</g>', cup(385, 925), cup(695, 925)]
    else:
        parts += [tomas(305, 790), manuel(755, 760, index in (1, 2)), cup(405, 1035, .86), cup(665, 1035, .86)]
    if index == 1:
        for i in range(7):
            x = 165 + i * 26
            parts.append(f'<line x1="{x}" y1="510" x2="{x}" y2="568" stroke="{P["copper"]}" stroke-width="8" stroke-linecap="round"/>')
    parts += [narr_box(SOURCE_LINES[index - 1]), signature(), page_ref(), "</svg>"]
    return "".join(parts)


def html_page(svg: str) -> str:
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
      {FONT_FACE}
      html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:{P["paper"]}}}
      svg{{display:block;width:{W}px;height:{H}px}}</style></head><body>{svg}</body></html>'''


def full_strip_html(paths: list[Path]) -> str:
    imgs = []
    for path in paths:
        uri = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
        imgs.append(f'<div class="cell"><img src="{uri}"/></div>')
    credit = "Apertura adaptada de las páginas 13–14 de Las manecillas del recuerdo · Autora Demo Díaz · Monza Ediciones"
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
      {FONT_FACE}
      html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:{P["paper"]};font-family:IG10Inter,Inter,sans-serif}}
      .grid{{position:absolute;left:42px;right:42px;top:42px;height:1115px;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:16px}}
      .cell{{display:flex;align-items:center;justify-content:center;overflow:hidden;background:{P["paper"]}}}
      .cell img{{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;border:4px solid {P["ink"]};box-sizing:border-box}}
      .credit{{position:absolute;left:55px;right:55px;bottom:78px;font-size:24px;line-height:1.25;font-weight:600;text-align:center;color:{P["ink"]}}}
      </style></head><body><div class="grid">{"".join(imgs)}</div><div class="credit">{esc(credit)}</div></body></html>'''


def ensure_inter(page) -> None:
    result = page.evaluate(
        """async () => {
          try {
            const a = await document.fonts.load('600 24px IG10Inter', 'Las manecillas del recuerdo');
            const b = await document.fonts.load('700 24px IG10Inter', 'Tomás Manuel');
            await document.fonts.ready;
            return a.length > 0 && b.length > 0 &&
                   document.fonts.check('600 24px IG10Inter') &&
                   document.fonts.check('700 24px IG10Inter');
          } catch (_) { return false; }
        }"""
    )
    if not result:
        raise RuntimeError(
            "IG10_RENDER_BLOCKED: Chromium no ha cargado la familia local Inter. "
            "Instala Inter y repite el gate; no exportar con una sustitución del sistema."
        )


def render(out_dir: Path) -> None:
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for idx in range(1, 5):
            page.set_content(html_page(panel_svg(idx)), wait_until="load")
            ensure_inter(page)
            target = out_dir / f"ig10_s{idx}.png"
            page.screenshot(path=str(target), full_page=False)
            outputs.append(target)
        page.set_content(full_strip_html(outputs), wait_until="load")
        ensure_inter(page)
        full = out_dir / "ig10_s5_full.png"
        page.screenshot(path=str(full), full_page=False)
        browser.close()
    manifest: dict[str, Any] = {
        "id": "IG-10_MANECILLAS_OPENING_v1",
        "source_document_id": SOURCE_DOC_ID,
        "source_scope": "verified opening only, pages 13–14 as recorded in canonical fragment document",
        "text_lines": SOURCE_LINES,
        "reference_urls": REFERENCE_URLS,
        "reference_use": "pose/composition only; identities are not used",
        "source_license": LICENSE_URL,
        "canonical_portraits": False,
        "generation_ai": False,
        "outputs": [str(p) for p in outputs] + [str(full)],
        "qa": [
            "No invented dialogue or thoughts",
            "Tomás/Manuel visual traits are non-canonical editorial codes",
            "Ordinary wristwatch only; not cover-watch reconstruction",
            "Exactly two chocolate cups throughout",
            "Text must match source lines exactly",
            "Slide 5 keeps every panel complete; no object-fit cover crop",
            "Slide 5 contains only the 2x2 strip and editorial credit",
            "Inter must be loaded; no silent font fallback",
        ],
    }
    (out_dir / "ig10_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    render(args.out)


if __name__ == "__main__":
    main()
