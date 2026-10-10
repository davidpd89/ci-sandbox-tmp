#!/usr/bin/env python3
"""Render deterministic 4-panel microcomics from JSON.

Dependencies:
    pip install playwright
    playwright install chromium

Usage:
    python tools/microcomic/render_microcomic.py tools/microcomic/scenes/ig08_01.json --out build/ig08_01

The renderer intentionally avoids image-generation APIs. Character, props and
text are SVG/HTML primitives so the same character stays identical across episodes.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import textwrap
from pathlib import Path
from typing import Any

W, H = 1080, 1350
ROOT = Path(__file__).resolve().parent
CHARACTER_PATH = ROOT / "character_lector_a_v1.json"
EDGE_EXE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
CHROME_EXE = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
FONT_FAMILY = "IG08_Inter"
INTER_FONT = ROOT / "fonts" / "Inter-4.1" / "InterVariable.ttf"
BRAND = "DAVID PORTO DÍAZ"
WEB = "davidportodiaz.com"


def font_face_css() -> str:
    if not INTER_FONT.exists():
        raise RuntimeError(
            "IG08_RENDER_BLOCKED: falta tools/microcomic/fonts/Inter-4.1/InterVariable.ttf. "
            "No renderizar con Arial/sans-serif como sustitución silenciosa."
        )
    font_b64 = base64.b64encode(INTER_FONT.read_bytes()).decode("ascii")
    return f"""
@font-face {{
  font-family: 'IG08_Inter';
  src: url('data:font/ttf;base64,{font_b64}') format('truetype'), local('Inter');
  font-style: normal;
  font-weight: 100 900;
}}
"""


FONT_FACE_CSS = "FONT_FACE_CSS"

KNOWN_SETTINGS = {"bed", "sofa", "stack", "bookstore", "handoff", "notes"}
KNOWN_ACTIONS = {
    "bed_read", "bed_read_tired", "bed_read_alarm", "bed_pages", "bed_close", "bed_tea", "bed_reopen",
    "stand_stack", "stack_look", "stack_open", "bookstore_read", "bookstore_close", "bookstore_return",
    "sofa_read", "phone_note", "handoff", "cling_book", "hold_book",
}


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_character(scene: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not CHARACTER_PATH.exists():
        raise RuntimeError(f"IG08_RENDER_BLOCKED: falta biblia {CHARACTER_PATH}")
    character = json.loads(CHARACTER_PATH.read_text(encoding="utf-8"))
    requested = scene.get("character_version")
    if not requested:
        raise RuntimeError("IG08_RENDER_BLOCKED: la escena no declara character_version")
    if requested != character.get("id"):
        raise RuntimeError(
            f"IG08_RENDER_BLOCKED: escena pide {requested!r} pero la biblia cargada es {character.get('id')!r}. "
            "Crear una v2 explícita; no modificar v1 silenciosamente."
        )
    if not character.get("wardrobe_locked"):
        raise RuntimeError("IG08_RENDER_BLOCKED: LECTOR_A_v1 debe conservar wardrobe_locked=true")
    if scene.get("style"):
        raise RuntimeError(
            "IG08_RENDER_BLOCKED: una escena no puede sobreescribir paleta/geometría de LECTOR_A_v1. "
            "Cambiar la biblia y su versión, no el episodio."
        )

    palette = character.get("palette") or {}
    geometry = character.get("geometry") or {}
    required_palette = {
        "line", "skin", "hair", "sweatshirt", "trousers", "socks", "accent", "background", "background_secondary"
    }
    required_geometry = {
        "stroke_px", "head_width_px", "head_height_px", "normal_eye_diameter_px", "alarm_eye_diameter_px",
        "mouth_min_px", "mouth_max_px", "torso_width_px", "torso_height_px", "limb_stroke_px",
        "book_width_px", "book_height_px",
    }
    if missing := sorted(required_palette - set(palette)):
        raise RuntimeError(f"IG08_RENDER_BLOCKED: faltan campos de paleta en la biblia: {missing}")
    if missing := sorted(required_geometry - set(geometry)):
        raise RuntimeError(f"IG08_RENDER_BLOCKED: faltan campos geométricos en la biblia: {missing}")

    style = dict(palette)
    style["stroke"] = int(geometry["stroke_px"])
    style["geometry"] = geometry
    style["font"] = FONT_FAMILY
    return character, style


def validate_scene(scene: dict[str, Any], character: dict[str, Any]) -> None:
    panels = scene.get("panels") or []
    if len(panels) != 4:
        raise RuntimeError(f"IG08_RENDER_BLOCKED: expected exactly 4 panels, got {len(panels)}")
    allowed_expressions = set(character.get("expressions") or [])
    for idx, panel in enumerate(panels, start=1):
        setting = panel.get("setting", "sofa")
        action = panel.get("action", "sofa_read")
        expression = panel.get("expression", "neutral")
        if setting not in KNOWN_SETTINGS:
            raise RuntimeError(f"IG08_RENDER_BLOCKED: panel {idx} usa setting desconocido {setting!r}")
        if action not in KNOWN_ACTIONS:
            raise RuntimeError(f"IG08_RENDER_BLOCKED: panel {idx} usa action desconocida {action!r}")
        if expression not in allowed_expressions:
            raise RuntimeError(
                f"IG08_RENDER_BLOCKED: panel {idx} usa expresión {expression!r} fuera de LECTOR_A_v1: {sorted(allowed_expressions)}"
            )
    if not str(scene.get("reference_url", "")).startswith("https://www.pexels.com/photo/"):
        raise RuntimeError("IG08_RENDER_BLOCKED: reference_url debe ser la foto Pexels exacta del episodio")
    if "pexels.com" not in str(scene.get("source_license", "")):
        raise RuntimeError("IG08_RENDER_BLOCKED: falta source_license de Pexels")


def svg_text_block(text: str, x: int, y: int, width_chars: int = 28,
                   font_size: int = 46, anchor: str = "start",
                   fill: str = "#241D18", weight: int = 650,
                   line_height: float = 1.18) -> str:
    lines = []
    for paragraph in str(text).split("\n"):
        wrapped = textwrap.wrap(paragraph, width=width_chars, break_long_words=False,
                                break_on_hyphens=False) or [""]
        lines.extend(wrapped)
    tspans = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else int(font_size * line_height)
        tspans.append(f'<tspan x="{x}" dy="{dy if i else 0}">{esc(line)}</tspan>')
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{fill}" '
        f'font-family="{FONT_FAMILY}, sans-serif" font-size="{font_size}" '
        f'font-weight="{weight}">' + "".join(tspans) + "</text>"
    )


def bubble(text: str | None, x: int = 90, y: int = 90, w: int = 900,
           tail_x: int = 540, tail_y: int = 360, style: dict[str, Any] | None = None) -> str:
    if not text:
        return ""
    if style is None:
        raise RuntimeError("IG08_RENDER_BLOCKED: bubble sin estilo de personaje")
    st = style
    lines = []
    for p in str(text).split("\n"):
        lines += textwrap.wrap(p, width=30, break_long_words=False, break_on_hyphens=False) or [""]
    h = max(145, 68 + len(lines) * 56)
    out = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="38" fill="#FFFFFF" stroke="{st["line"]}" stroke-width="8"/>',
        f'<path d="M {tail_x-28} {y+h-4} L {tail_x} {tail_y} L {tail_x+35} {y+h-4} Z" fill="#FFFFFF" stroke="{st["line"]}" stroke-width="8" stroke-linejoin="round"/>',
        f'<rect x="{tail_x-38}" y="{y+h-10}" width="82" height="20" fill="#FFFFFF"/>',
    ]
    ty = y + 62
    for i, line in enumerate(lines):
        out.append(
            f'<text x="{x+w/2}" y="{ty+i*56}" text-anchor="middle" font-family="{FONT_FAMILY}, sans-serif" font-size="46" font-weight="650" fill="{st["line"]}">{esc(line)}</text>'
        )
    return "".join(out)


def face(expression: str, cx: float, cy: float, st: dict[str, Any]) -> str:
    line = st["line"]
    geom = st["geometry"]
    eye_y = cy - 5
    normal_r = float(geom["normal_eye_diameter_px"]) / 2
    alarm_r = float(geom["alarm_eye_diameter_px"]) / 2
    mouth_half = float(geom["mouth_max_px"]) / 2
    if expression == "cansado":
        eyes = (
            f'<path d="M {cx-40} {eye_y} q 14 8 28 0" fill="none" stroke="{line}" stroke-width="8" stroke-linecap="round"/>'
            f'<path d="M {cx+12} {eye_y} q 14 8 28 0" fill="none" stroke="{line}" stroke-width="8" stroke-linecap="round"/>'
        )
        mouth = f'<path d="M {cx-mouth_half} {cy+42} L {cx+mouth_half} {cy+42}" stroke="{line}" stroke-width="8" stroke-linecap="round"/>'
    elif expression == "alarma":
        eyes = f'<circle cx="{cx-28}" cy="{eye_y}" r="{alarm_r}" fill="{line}"/><circle cx="{cx+28}" cy="{eye_y}" r="{alarm_r}" fill="{line}"/>'
        mouth = f'<circle cx="{cx}" cy="{cy+40}" r="10" fill="none" stroke="{line}" stroke-width="7"/>'
    elif expression == "sospecha":
        eyes = f'<circle cx="{cx-28}" cy="{eye_y}" r="{normal_r}" fill="{line}"/><path d="M {cx+12} {eye_y+4} q 14 7 28 0" fill="none" stroke="{line}" stroke-width="7" stroke-linecap="round"/>'
        mouth = f'<path d="M {cx-20} {cy+45} L {cx+17} {cy+37}" stroke="{line}" stroke-width="8" stroke-linecap="round"/>'
    elif expression == "contento":
        eyes = f'<circle cx="{cx-28}" cy="{eye_y}" r="{normal_r}" fill="{line}"/><circle cx="{cx+28}" cy="{eye_y}" r="{normal_r}" fill="{line}"/>'
        mouth = f'<path d="M {cx-24} {cy+35} Q {cx} {cy+58} {cx+24} {cy+35}" fill="none" stroke="{line}" stroke-width="8" stroke-linecap="round"/>'
    elif expression == "resignado":
        eyes = f'<circle cx="{cx-28}" cy="{eye_y}" r="{normal_r}" fill="{line}"/><circle cx="{cx+28}" cy="{eye_y}" r="{normal_r}" fill="{line}"/>'
        mouth = f'<path d="M {cx-20} {cy+38} L {cx+18} {cy+48}" stroke="{line}" stroke-width="8" stroke-linecap="round"/>'
    else:
        eyes = f'<circle cx="{cx-28}" cy="{eye_y}" r="{normal_r}" fill="{line}"/><circle cx="{cx+28}" cy="{eye_y}" r="{normal_r}" fill="{line}"/>'
        mouth = f'<path d="M {cx-mouth_half} {cy+42} L {cx+mouth_half} {cy+42}" stroke="{line}" stroke-width="8" stroke-linecap="round"/>'
    return eyes + mouth


def book(cx: float, cy: float, scale: float, st: dict[str, Any], angle: float = 0, near_end: bool = False) -> str:
    geom = st["geometry"]
    w, h = float(geom["book_width_px"]) * scale, float(geom["book_height_px"]) * scale
    line = st["line"]
    extra = ""
    if near_end:
        x0 = w * 0.18
        x1 = w / 2 - 7 * scale
        y0 = -h / 2 + 18 * scale
        y1 = h / 2 - 18 * scale
        extra = (
            f'<path d="M {x0} {y0} L {x1} {y0+6*scale} L {x1} {y1-6*scale} L {x0} {y1} Z" '
            f'fill="#F8F3E8" stroke="{line}" stroke-width="{4*scale}"/>'
            f'<line x1="{x1-8*scale}" y1="{y0+12*scale}" x2="{x1-8*scale}" y2="{y1-12*scale}" stroke="{line}" stroke-width="{2.5*scale}" opacity=".55"/>'
            f'<line x1="{x1-14*scale}" y1="{y0+14*scale}" x2="{x1-14*scale}" y2="{y1-14*scale}" stroke="{line}" stroke-width="{2*scale}" opacity=".35"/>'
        )
    return (
        f'<g transform="translate({cx},{cy}) rotate({angle})">'
        f'<rect x="{-w/2}" y="{-h/2}" width="{w}" height="{h}" rx="{10*scale}" fill="#C8A77D" stroke="{line}" stroke-width="{8*scale}"/>'
        f'<line x1="{-w/2+16*scale}" y1="{-h/2}" x2="{-w/2+16*scale}" y2="{h/2}" stroke="{line}" stroke-width="{5*scale}" opacity=".6"/>'
        f'{extra}</g>'
    )


def phone(cx: float, cy: float, st: dict[str, Any], text: str | None = None) -> str:
    line = st["line"]
    s = (
        f'<g><rect x="{cx-55}" y="{cy-90}" width="110" height="180" rx="18" fill="#2F3133" stroke="{line}" stroke-width="8"/>'
        f'<rect x="{cx-44}" y="{cy-72}" width="88" height="140" rx="9" fill="#E8ECEE"/>'
    )
    if text:
        s += f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="middle" font-family="{FONT_FAMILY}, sans-serif" font-size="22" font-weight="700" fill="{line}">{esc(text)}</text>'
    return s + '</g>'


def social_footer(st: dict[str, Any], cue: str = "DESLIZA", arrow: bool = True) -> str:
    line = st["line"]
    accent = st["accent"]
    bg = st["background"]
    actions = [("♡", "Like"), ("✎", "Comenta"), ("↗", "Envía"), ("◇", "Guarda")]
    x = 58
    y = 1252
    out = [
        f'<text x="58" y="1216" font-family="{FONT_FAMILY}, sans-serif" font-size="20" font-weight="750" fill="{line}" opacity=".70">{BRAND}</text>',
        f'<text x="58" y="1240" font-family="{FONT_FAMILY}, sans-serif" font-size="18" font-weight="650" fill="{line}" opacity=".62">{WEB}</text>',
    ]
    for icon, label in actions:
        label_w = max(38, len(label) * 8)
        pill_w = 22 + 24 + 8 + label_w + 20
        out.append(
            f'<rect x="{x}" y="{y}" width="{pill_w}" height="42" rx="21" '
            f'fill="{bg}" stroke="{line}" stroke-width="2" opacity=".92"/>'
        )
        out.append(
            f'<text x="{x+18}" y="{y+27}" font-family="Segoe UI Symbol, {FONT_FAMILY}, sans-serif" '
            f'font-size="22" font-weight="700" fill="{accent}">{icon}</text>'
        )
        out.append(
            f'<text x="{x+50}" y="{y+27}" font-family="{FONT_FAMILY}, sans-serif" '
            f'font-size="16" font-weight="750" fill="{line}">{label}</text>'
        )
        x += pill_w + 14

    cue_w = 146 if arrow else 112
    cue_x = 1022 - cue_w
    out.append(
        f'<rect x="{cue_x}" y="{y-1}" width="{cue_w}" height="45" rx="23" '
        f'fill="#FFFFFF" stroke="{line}" stroke-width="2" opacity=".96"/>'
    )
    out.append(
        f'<text x="{cue_x+18}" y="{y+28}" font-family="{FONT_FAMILY}, sans-serif" '
        f'font-size="17" font-weight="800" fill="{line}">{cue}</text>'
    )
    if arrow:
        cx, cy = 1000, y + 21
        out.append(f'<circle cx="{cx}" cy="{cy}" r="16" fill="{accent}"/>')
        out.append(f'<line x1="{cx-8}" y1="{cy}" x2="{cx+7}" y2="{cy}" stroke="{bg}" stroke-width="3" stroke-linecap="round"/>')
        out.append(f'<path d="M {cx+6} {cy-7} L {cx+15} {cy} L {cx+6} {cy+7} Z" fill="{bg}"/>')
    return "".join(out)


def reader(action: str, expression: str, st: dict[str, Any]) -> str:
    line, skin = st["line"], st["skin"]
    sw, tr, hair = st["sweatshirt"], st["trousers"], st["hair"]
    geom = st["geometry"]
    stroke = int(geom["stroke_px"])
    limb = int(geom["limb_stroke_px"])
    torso_w = int(geom["torso_width_px"])
    torso_h = int(geom["torso_height_px"])
    head_rx = float(geom["head_width_px"]) / 2
    head_ry = float(geom["head_height_px"]) / 2
    cx, head_y = 540, 650
    torso_y = 760
    torso_x = cx - torso_w / 2
    parts = []

    if action in {"bed_read", "bed_read_tired", "bed_read_alarm", "bed_pages", "bed_close", "bed_tea", "bed_reopen"}:
        head_y, torso_y = 690, 790
        torso_x = cx - torso_w / 2
        parts += [
            f'<path d="M 455 1010 Q 390 1110 300 1190" fill="none" stroke="{tr}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<path d="M 610 1010 Q 700 1080 790 1180" fill="none" stroke="{tr}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<rect x="{torso_x}" y="{torso_y}" width="{torso_w}" height="{torso_h}" rx="100" fill="{sw}" stroke="{line}" stroke-width="{stroke}"/>',
        ]
    elif action in {"stand_stack", "stack_look", "stack_open", "bookstore_read", "bookstore_close", "bookstore_return"}:
        head_y, torso_y = 560, 660
        torso_x = cx - torso_w / 2
        parts += [
            f'<path d="M 485 940 L 460 1200" fill="none" stroke="{tr}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<path d="M 600 940 L 630 1200" fill="none" stroke="{tr}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<rect x="{torso_x}" y="{torso_y}" width="{torso_w}" height="{torso_h}" rx="100" fill="{sw}" stroke="{line}" stroke-width="{stroke}"/>',
        ]
    else:
        head_y, torso_y = 620, 720
        torso_x = cx - torso_w / 2
        parts += [
            f'<path d="M 485 970 Q 430 1080 390 1190" fill="none" stroke="{tr}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<path d="M 600 970 Q 650 1080 705 1190" fill="none" stroke="{tr}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<rect x="{torso_x}" y="{torso_y}" width="{torso_w}" height="{torso_h}" rx="100" fill="{sw}" stroke="{line}" stroke-width="{stroke}"/>',
        ]

    parts += [
        f'<ellipse cx="{cx}" cy="{head_y}" rx="{head_rx}" ry="{head_ry}" fill="{skin}" stroke="{line}" stroke-width="{stroke}"/>',
        f'<path d="M {cx-head_rx+8} {head_y-38} Q {cx-34} {head_y-head_ry-18} {cx+14} {head_y-head_ry+2} Q {cx+head_rx+2} {head_y-head_ry-8} {cx+head_rx-2} {head_y-20} Q {cx+24} {head_y-44} {cx-head_rx+8} {head_y-38} Z" fill="{hair}" stroke="{line}" stroke-width="{stroke}" stroke-linejoin="round"/>',
        face(expression, cx, head_y + 5, st),
    ]

    if action in {"bed_read", "bed_read_tired", "bed_read_alarm", "bed_pages", "sofa_read", "stack_open", "bookstore_read", "bed_reopen"}:
        by = 930 if "bed" in action else 865
        parts += [
            f'<path d="M 460 {torso_y+110} Q 410 {by-35} 440 {by}" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<path d="M 620 {torso_y+110} Q 675 {by-35} 640 {by}" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            book(540, by + 10, .82, st, 0, near_end=(action == "bed_pages")),
        ]
    elif action == "phone_note":
        parts += [
            f'<path d="M 465 {torso_y+120} Q 430 850 470 900" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<path d="M 615 {torso_y+120} Q 650 850 610 900" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            phone(540, 900, st),
        ]
    elif action in {"handoff", "cling_book", "hold_book"}:
        parts += [
            f'<path d="M 462 {torso_y+120} Q 420 875 495 930" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<path d="M 620 {torso_y+120} Q 660 875 585 930" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            book(540, 940, .72, st),
        ]
    elif action == "bookstore_close":
        parts += [
            f'<path d="M 462 {torso_y+120} Q 430 860 500 915" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<path d="M 620 {torso_y+120} Q 650 860 580 915" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            book(540, 930, .72, st, 90),
        ]
    elif action == "bookstore_return":
        parts += [
            f'<path d="M 620 {torso_y+120} Q 730 820 815 760" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            book(850, 720, .58, st),
        ]
    elif action == "bed_close":
        parts += [book(720, 1080, .66, st, 90)]
    elif action == "bed_tea":
        parts += [
            f'<path d="M 620 {torso_y+120} Q 680 880 705 930" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            f'<circle cx="730" cy="950" r="45" fill="#D7C0A4" stroke="{line}" stroke-width="8"/>',
            f'<path d="M 768 935 q 50 5 25 45 q -18 20 -40 2" fill="none" stroke="{line}" stroke-width="8"/>',
        ]
    elif action == "stand_stack":
        parts += [
            f'<path d="M 620 {torso_y+110} Q 730 770 810 700" fill="none" stroke="{skin}" stroke-width="{limb}" stroke-linecap="round"/>',
            book(840, 675, .55, st),
        ]
    return "".join(parts)


def background(setting: str, st: dict[str, Any]) -> str:
    bg, line, sec = st["background"], st["line"], st["background_secondary"]
    out = [f'<rect width="{W}" height="{H}" fill="{bg}"/>']
    if setting == "bed":
        out += [
            f'<rect x="105" y="910" width="870" height="330" rx="90" fill="#EEE1D4" stroke="{line}" stroke-width="10"/>',
            f'<rect x="125" y="845" width="290" height="155" rx="58" fill="#FFFFFF" stroke="{line}" stroke-width="8"/>',
            f'<rect x="810" y="910" width="165" height="230" rx="24" fill="#B98E68" stroke="{line}" stroke-width="9"/>',
        ]
    elif setting == "sofa":
        out += [
            f'<rect x="150" y="850" width="780" height="320" rx="110" fill="{sec}" stroke="{line}" stroke-width="10"/>',
            f'<rect x="180" y="775" width="720" height="185" rx="80" fill="{sec}" stroke="{line}" stroke-width="10"/>',
        ]
    elif setting == "stack":
        for i in range(8):
            y = 1170 - i * 48
            color = ["#B98E68", "#8FA2A8", "#D4B78D", "#A78174"][i % 4]
            out.append(f'<rect x="{740-i%2*18}" y="{y}" width="{230+i%3*25}" height="42" rx="6" fill="{color}" stroke="{line}" stroke-width="5"/>')
    elif setting == "bookstore":
        for col in [70, 765]:
            out.append(f'<rect x="{col}" y="330" width="245" height="850" rx="10" fill="#D7B58E" stroke="{line}" stroke-width="10"/>')
            for j in range(5):
                sy = 450 + j * 145
                out.append(f'<line x1="{col+15}" y1="{sy}" x2="{col+230}" y2="{sy}" stroke="{line}" stroke-width="7"/>')
                for k in range(5):
                    x = col + 25 + k * 40
                    color = ["#B46D5D", "#7D8E97", "#C6A875", "#8A7769"][k % 4]
                    out.append(f'<rect x="{x}" y="{sy-90}" width="30" height="88" fill="{color}" stroke="{line}" stroke-width="3"/>')
    elif setting == "handoff":
        out += [
            f'<rect x="90" y="1060" width="900" height="190" rx="40" fill="#D8C9B6" stroke="{line}" stroke-width="9"/>',
            f'<rect x="770" y="650" width="260" height="400" rx="100" fill="#7D8E97" stroke="{line}" stroke-width="12"/>',
        ]
    elif setting == "notes":
        out.append(f'<rect x="120" y="1020" width="840" height="180" rx="28" fill="#C7A77F" stroke="{line}" stroke-width="10"/>')
    return "".join(out)


def panel_svg(panel: dict[str, Any], st: dict[str, Any], brand: bool = True) -> str:
    setting = panel.get("setting", "sofa")
    action = panel.get("action", "sofa_read")
    expr = panel.get("expression", "neutral")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    out.append(f'<rect width="{W}" height="{H}" fill="{st["background"]}"/>')
    scene_parts = [background(setting, st), reader(action, expr, st)]
    if setting == "handoff" and action in {"handoff", "cling_book"}:
        scene_parts.append('<path d="M 820 800 Q 730 850 635 930" fill="none" stroke="#B98462" stroke-width="36" stroke-linecap="round"/>')
    if panel.get("clock"):
        scene_parts.append(phone(900, 1130, st, str(panel["clock"])))
    if panel.get("note"):
        scene_parts.append(f'<rect x="640" y="930" width="340" height="180" rx="24" fill="#EEF2F3" stroke="{st["line"]}" stroke-width="8"/>')
        scene_parts.append(svg_text_block(panel["note"], 810, 1000, width_chars=22, font_size=30, anchor="middle", fill=st["line"], weight=650))
    if panel.get("stack_new_book"):
        scene_parts.append(book(835, 745, .55, st))
    scene_markup = "".join(scene_parts)
    if setting == "bed":
        out.append(f'<g transform="translate(-110 -350) scale(1.2)">{scene_markup}</g>')
    else:
        out.append(scene_markup)
    if panel.get("bubble"):
        out.append(bubble(panel["bubble"], int(panel.get("bubble_x", 90)), int(panel.get("bubble_y", 90)), int(panel.get("bubble_w", 900)), int(panel.get("tail_x", 540)), int(panel.get("tail_y", 500)), st))
    if panel.get("small_text"):
        out.append(svg_text_block(panel["small_text"], 540, 180, width_chars=28, font_size=40, anchor="middle", fill=st["line"], weight=650))
    if brand:
        out.append(social_footer(st, "DESLIZA", True))
    out.append('</svg>')
    return "".join(out)


def wrap_svg_in_html(svg: str) -> str:
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{font_face_css()}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#fff;font-family:{FONT_FAMILY},sans-serif}}
svg{{display:block;width:{W}px;height:{H}px}}</style></head><body>{svg}</body></html>'''


def full_strip_html(panel_paths: list[Path], st: dict[str, Any]) -> str:
    import base64
    imgs = []
    for p in panel_paths:
        b64 = base64.b64encode(p.read_bytes()).decode('ascii')
        imgs.append(f'data:image/png;base64,{b64}')
    tiles = ''.join(f'<img src="{u}"/>' for u in imgs)
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{font_face_css()}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:{st["background"]};font-family:{FONT_FAMILY},sans-serif}}
.grid{{position:absolute;left:42px;top:42px;width:996px;height:1020px;display:grid;grid-template-columns:490px 490px;grid-template-rows:502px 502px;gap:16px;overflow:hidden}}
.grid img{{display:block;width:490px;height:502px;object-fit:contain;background:{st["background"]};border:4px solid {st["line"]};border-radius:8px;box-sizing:border-box;min-width:0;min-height:0}}
.share{{position:absolute;left:42px;right:42px;bottom:168px;text-align:center;font-size:24px;font-weight:750;letter-spacing:.3px;color:{st["line"]}}}
.brand{{position:absolute;left:58px;bottom:112px;font-size:18px;font-weight:750;color:{st["line"]};opacity:.70}}
.web{{position:absolute;left:58px;bottom:88px;font-size:16px;font-weight:650;color:{st["line"]};opacity:.62}}
.actions{{position:absolute;left:58px;bottom:32px;display:flex;gap:14px;align-items:center}}
.pill{{height:42px;padding:0 18px;border:2px solid {st["line"]};border-radius:21px;box-sizing:border-box;background:{st["background"]};display:flex;align-items:center;gap:8px;font-size:16px;font-weight:750;color:{st["line"]};opacity:.92}}
.icon{{font-family:"Segoe UI Symbol",{FONT_FAMILY},sans-serif;font-size:22px;font-weight:700;color:{st["accent"]}}}
.cue{{position:absolute;right:58px;bottom:31px;height:45px;padding:0 18px;border:2px solid {st["line"]};border-radius:23px;background:#fff;box-sizing:border-box;display:flex;align-items:center;font-size:17px;font-weight:800;color:{st["line"]};opacity:.96}}
</style></head><body><div class="grid">{tiles}</div><div class="share">GUÁRDALO O MÁNDALO A ESA PERSONA.</div><div class="brand">{BRAND}</div><div class="web">{WEB}</div><div class="actions"><div class="pill"><span class="icon">♡</span>Like</div><div class="pill"><span class="icon">✎</span>Comenta</div><div class="pill"><span class="icon">↗</span>Envía</div><div class="pill"><span class="icon">◇</span>Guarda</div></div><div class="cue">GUARDA</div></body></html>'''


def ensure_inter(page) -> None:
    result = page.evaluate(
        """async () => {
          try {
            const faces = await document.fonts.load('650 24px IG08_Inter', 'Microcómic lector ÁÉÍÓÚÑ 23:48');
            await document.fonts.ready;
            return {
              loaded: faces.length > 0,
              check650: document.fonts.check('650 24px IG08_Inter', 'Microcómic lector'),
              check700: document.fonts.check('700 24px IG08_Inter', '23:48')
            };
          } catch (error) {
            return {loaded: false, check650: false, check700: false, error: String(error)};
          }
        }"""
    )
    if not (result.get("loaded") and result.get("check650") and result.get("check700")):
        detail = result.get("error") or "Chromium no ha podido cargar Inter desde la máquina local."
        raise RuntimeError(
            "IG08_RENDER_BLOCKED: falta la tipografía auditada Inter. "
            + detail
            + " Ejecuta tools/microcomic/check_fonts.py e instala Inter; no exportar con fallback silencioso."
        )


def launch_browser(playwright):
    if EDGE_EXE.exists():
        return playwright.chromium.launch(executable_path=str(EDGE_EXE))
    if CHROME_EXE.exists():
        return playwright.chromium.launch(executable_path=str(CHROME_EXE))
    return playwright.chromium.launch()


def render_scene(scene_path: Path, out_dir: Path) -> None:
    from playwright.sync_api import sync_playwright
    if not INTER_FONT.exists():
        raise RuntimeError(
            "IG08_RENDER_BLOCKED: falta tools/microcomic/fonts/Inter-4.1/InterVariable.ttf. "
            "No renderizar con Arial/sans-serif como sustitución silenciosa."
        )
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    character, st = load_character(scene)
    validate_scene(scene, character)
    panels = scene["panels"]
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = scene.get("id", scene_path.stem)
    panel_paths: list[Path] = []
    clean_panel_paths: list[Path] = []
    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for idx, panel in enumerate(panels, 1):
            page.set_content(wrap_svg_in_html(panel_svg(panel, st)), wait_until="load")
            ensure_inter(page)
            target = out_dir / f"{prefix}_slide_{idx}.png"
            page.screenshot(path=str(target), full_page=False)
            panel_paths.append(target)
            clean_target = out_dir / f".{prefix}_panel_{idx}_clean.png"
            page.set_content(wrap_svg_in_html(panel_svg(panel, st, brand=False)), wait_until="load")
            ensure_inter(page)
            page.screenshot(path=str(clean_target), full_page=False)
            clean_panel_paths.append(clean_target)
        page.set_content(full_strip_html(clean_panel_paths, st), wait_until="load")
        ensure_inter(page)
        final_path = out_dir / f"{prefix}_slide_5_full.png"
        page.screenshot(path=str(final_path), full_page=False)
        browser.close()
    for clean_path in clean_panel_paths:
        clean_path.unlink(missing_ok=True)
    manifest = {
        "scene": str(scene_path),
        "outputs": [str(x) for x in panel_paths] + [str(final_path)],
        "character_version": character["id"],
        "character_file": str(CHARACTER_PATH),
        "character_sha256": file_sha256(CHARACTER_PATH),
        "reference_url": scene.get("reference_url"),
        "source_license": scene.get("source_license"),
        "slide5_fit": "contain",
        "font_family": "Inter local, required",
        "status": "RENDERED_NOT_SCHEDULED",
    }
    (out_dir / f"{prefix}_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    render_scene(args.scene, args.out)


if __name__ == "__main__":
    main()
