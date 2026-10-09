#!/usr/bin/env python3
import argparse
import asyncio
import html
import json
from pathlib import Path
from playwright.async_api import async_playwright

W, H = 1080, 1920


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def highlighted_quote(text: str, highlights: list[str]) -> str:
    out = esc(text)
    for phrase in sorted(highlights, key=len, reverse=True):
        out = out.replace(esc(phrase), f'<mark>{esc(phrase)}</mark>')
    return out


def base_css() -> str:
    return r'''
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&family=Playfair+Display:wght@700&display=swap');
    * { box-sizing: border-box; }
    html, body { margin: 0; width: 1080px; height: 1920px; }
    body { font-family: Inter, Arial, sans-serif; }
    .slide { width:1080px; height:1920px; overflow:hidden; position:relative; }
    .safe { position:absolute; inset:150px 96px 220px 96px; }
    .kicker { font-size:28px; line-height:1.2; font-weight:600; letter-spacing:.14em; text-transform:uppercase; }
    .hook { font-family:'Playfair Display', Georgia, serif; font-weight:700; font-size:104px; line-height:1.02; letter-spacing:-.025em; }
    .hook-slide { background:#0f0c0b; color:#f7f1e8; }
    .hook-slide .kicker { color:#c4783f; }
    .hook-wrap { height:100%; display:flex; flex-direction:column; justify-content:center; gap:42px; }
    .excerpt-slide { background:#f3eadb; color:#201a16; }
    .excerpt-slide:before { content:''; position:absolute; inset:0; opacity:.09; background-image:radial-gradient(#4c351a 0.55px, transparent 0.55px); background-size:7px 7px; }
    .excerpt-slide .safe { display:flex; flex-direction:column; }
    .excerpt-slide .kicker { color:#7b5738; margin-bottom:90px; }
    blockquote { margin:0; font-family:'Playfair Display', Georgia, serif; font-size:68px; line-height:1.22; font-weight:700; }
    mark { background:rgba(196,120,63,.18); color:inherit; padding:0 .08em .04em .08em; border-bottom:5px solid #c4783f; }
    .meta { margin-top:auto; padding-top:70px; border-top:2px solid rgba(32,26,22,.18); }
    .work { font-size:30px; font-weight:600; line-height:1.35; }
    .source { font-size:23px; line-height:1.4; margin-top:14px; color:#665d55; }
    '''


def html_hook(item: dict) -> str:
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{base_css()}</style></head>
    <body><div class="slide hook-slide"><div class="safe"><div class="hook-wrap">
      <div class="kicker">DOS SLIDES · UN TEXTO REAL</div>
      <div class="hook">{esc(item['hook'])}</div>
    </div></div></div></body></html>'''


def html_excerpt(item: dict) -> str:
    quote = highlighted_quote(item['quote'], item.get('highlights', []))
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{base_css()}</style></head>
    <body><div class="slide excerpt-slide"><div class="safe">
      <div class="kicker">FRAGMENTO REAL · TEXTO REMAQUETADO</div>
      <blockquote>{quote}</blockquote>
      <div class="meta"><div class="work">{esc(item['credit'])}</div>
      <div class="source">Fuente: Biblioteca Virtual Miguel de Cervantes</div></div>
    </div></div></body></html>'''


async def ensure_audited_fonts(page) -> None:
    await page.evaluate("document.fonts.ready")
    checks = {
        "Inter 500": "500 24px Inter",
        "Inter 600": "600 24px Inter",
        "Playfair Display 700": "700 24px 'Playfair Display'",
    }
    missing = []
    for label, spec in checks.items():
        loaded = await page.evaluate("spec => document.fonts.check(spec)", spec)
        if not loaded:
            missing.append(label)
    if missing:
        raise RuntimeError(
            "TT-05 bloqueado: no se han cargado las fuentes auditadas: "
            + ", ".join(missing)
            + ". Ejecuta con acceso a fonts.googleapis.com/fonts.gstatic.com y vuelve a lanzar el gate. "
            "No sustituir fuentes sin nueva revisión visual."
        )


async def shot(page, html_text: str, out: Path):
    await page.set_content(html_text, wait_until='networkidle')
    await ensure_audited_fonts(page)
    await page.screenshot(path=str(out), full_page=False)


async def render(manifest: Path, out_root: Path, only: str | None):
    data = json.loads(manifest.read_text(encoding='utf-8'))
    items = data['items']
    if only:
        items = [x for x in items if x['id'] == only]
        if not items:
            raise SystemExit(f'No existe item {only}')

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for item in items:
            folder = out_root / item['id']
            folder.mkdir(parents=True, exist_ok=True)
            await shot(page, html_hook(item), folder / '01_hook.png')
            await shot(page, html_excerpt(item), folder / '02_excerpt.png')
            (folder / 'metadata.json').write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"OK {item['id']} -> {folder}")
        await browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('manifest', type=Path)
    ap.add_argument('--out', type=Path, default=Path('build/tt05'))
    ap.add_argument('--item', help='Ej. tt05_01; si se omite, renderiza todo')
    args = ap.parse_args()
    asyncio.run(render(args.manifest, args.out, args.item))


if __name__ == '__main__':
    main()
