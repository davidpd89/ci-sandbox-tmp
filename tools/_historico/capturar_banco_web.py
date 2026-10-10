from __future__ import annotations

import csv
import math
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "publicaciones GPT" / "banco imagenes web"
SITEMAP = ROOT.parent / "web-escritor" / "sitemap.xml"
WIDTH, HEIGHT, MAX_H = 1080, 1350, 1250


def clean(text, limit=700):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def urls():
    tree = ET.parse(SITEMAP)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    found = [n.text.strip() for n in tree.findall(".//s:loc", ns) if n.text]
    home = "https://davidportodiaz.com"
    return [home] + [u for u in found if u.rstrip("/") != home]


def category(url, zone):
    value = (urlparse(url).path + " " + zone).lower()
    rules = [
        ("herramient", "herramientas, utilidad, web"),
        ("manecillas", "libros, Las manecillas del recuerdo, ventas"),
        ("samuel", "libros, Samuel entre mundos, fantasía"),
        ("premio", "premios, trayectoria, autoridad"),
        ("prensa", "prensa, entrevistas, autoridad"),
        ("feria", "ferias, lectores, comunidad"),
        ("evento", "eventos, agenda, comunidad"),
        ("cuaderno", "artículos, divulgación, tráfico web"),
        ("recomend", "recomendaciones, lectores, libros"),
        ("editorial", "editoriales, escritores, recursos"),
        ("convocatoria", "convocatorias, escritores, recursos"),
        ("lector", "lectores, comunidad, recursos"),
        ("autor", "autor, biografía, marca personal"),
        ("libro", "libros, obra, ventas"),
    ]
    return next((tags for key, tags in rules if key in value), "web, navegación, contenido")


def prepare(page):
    enter = page.get_by_role("button", name="Entrar", exact=False)
    if enter.count():
        try:
            enter.first.click(timeout=1000)
            page.wait_for_timeout(700)
        except Exception:
            pass
    for label in ("Rechazo", "Rechazar", "Aceptar", "Cerrar", "Ahora no"):
        button = page.get_by_role("button", name=label, exact=False)
        if button.count():
            try:
                button.first.click(timeout=600)
            except Exception:
                pass
    page.evaluate("""() => {
      document.querySelectorAll(
        '[class*="clarity"],[id*="clarity"],[data-chat],[class*="newsletter-popup"],' +
        '[class*="cookie"],[id*="cookie"]'
      ).forEach(element => element.remove());
    }""")
    page.evaluate("""async () => {
      for (let y=0; y<document.documentElement.scrollHeight; y+=900) {
        window.scrollTo(0,y); await new Promise(r=>setTimeout(r,30));
      }
      window.scrollTo(0,0);
    }""")
    page.wait_for_timeout(200)


def band_data(page, top, bottom):
    links = page.evaluate("""({top,bottom}) => Array.from(document.querySelectorAll('a[href]'))
      .map(a => { const r=a.getBoundingClientRect(); return {
        y:r.top+scrollY, text:(a.innerText||a.getAttribute('aria-label')||'').trim(), href:a.href
      }})
      .filter(x => x.y>=top && x.y<bottom && x.href)
      .map(x => [x.text,x.href])""", {"top": top, "bottom": bottom})
    unique, seen = [], set()
    for text, href in links:
        if href not in seen:
            seen.add(href)
            unique.append((clean(text, 90) or "Enlace", href))
        if len(unique) == 30:
            break
    summary = page.evaluate("""({top,bottom}) => Array.from(document.querySelectorAll('main *'))
      .filter(e => { const r=e.getBoundingClientRect(), y=r.top+scrollY;
        return y>=top && y<bottom && r.width>0 && r.height>0 && !e.children.length; })
      .map(e => (e.innerText||'').trim()).filter(Boolean).join(' ')""",
      {"top": top, "bottom": bottom})
    return unique, clean(summary)


def write_info(number, title, zone, url, links, summary):
    folder = OUT / f"{number:03d}"
    lines = [
        f"# {number:03d}. {title} · {zone}", "",
        f"- **URL:** {url}",
        f"- **Página:** {title}",
        f"- **Zona:** {zone}",
        f"- **Categorías:** {category(url, zone)}",
        f"- **Captura:** captura.png",
        f"- **Fecha:** {date.today().isoformat()}", "",
        "## Qué contiene", "", summary or "Bloque visual de la zona indicada.", "",
        "## Enlaces visibles o asociados", "",
    ]
    lines += [f"- [{text}]({href})" for text, href in links] or ["- No hay enlaces propios en esta zona."]
    lines += ["", "## Uso posterior", "",
              "Fuente para preparar publicaciones adaptadas a cada red. Antes de usarla,",
              "comprobar que la página y sus datos siguen vigentes.", ""]
    (folder / "info.md").write_text("\n".join(lines), encoding="utf-8")


def capture_band(page, rows, number, title, zone, url, top, bottom):
    doc_h = page.evaluate("document.documentElement.scrollHeight")
    top, bottom = max(0, top), min(doc_h, bottom)
    if bottom <= top:
        return number
    parts = max(1, math.ceil((bottom-top)/MAX_H))
    for part in range(parts):
        y1, y2 = top + part*MAX_H, min(bottom, top+(part+1)*MAX_H)
        if y2-y1 < 260 and part:
            y1 = max(top, y2-260)
        label = zone if parts == 1 else f"{zone} · parte {part+1} de {parts}"
        folder = OUT / f"{number:03d}"
        folder.mkdir(parents=True, exist_ok=True)
        page.evaluate("(y) => window.scrollTo(0, y)", y1)
        page.wait_for_timeout(80)
        actual_top = page.evaluate("window.scrollY")
        actual_bottom = min(doc_h, actual_top + HEIGHT)
        page.screenshot(path=str(folder/"captura.png"))
        links, summary = band_data(page, actual_top, actual_bottom)
        write_info(number, title, label, url, links, summary)
        rows.append([f"{number:03d}", title, label, url, category(url,label), f"{number:03d}"])
        number += 1
    return number


def capture_locator(page, rows, number, title, zone, url, loc):
    if not loc.count():
        return number
    loc.scroll_into_view_if_needed()
    page.wait_for_timeout(120)
    box = loc.bounding_box()
    if not box or box["height"] <= 1:
        return number
    return capture_band(page, rows, number, title, zone, url,
                        box["y"]-12, box["y"]+box["height"]+12)


def capture_element(page, rows, number, title, zone, url, selector):
    return capture_locator(page, rows, number, title, zone, url, page.locator(selector).first)


def capture_home(page, rows, number, url):
    title = "Inicio"
    number = capture_element(page, rows, number, title, "Cabecera global", url, "header.site-header")
    number = capture_element(page, rows, number, title, "Portada y navegación principal", url, ".masthead")
    triggers = page.locator(".masthead-nav__submenu-trigger")
    for i in range(triggers.count()):
        trigger = triggers.nth(i)
        label = trigger.get_attribute("aria-label") or f"Menú {i+1}"
        trigger.click(); page.wait_for_timeout(100)
        number = capture_element(page, rows, number, title, label, url, ".masthead")
        trigger.click()
    blocks = page.locator("main section, main article")
    for i in range(blocks.count()):
        block = blocks.nth(i)
        if "masthead" in (block.get_attribute("class") or "").split():
            continue
        heading = block.locator("h1,h2,h3").first
        label = clean(heading.inner_text(), 140) if heading.count() else f"Bloque de inicio {i+1}"
        kind = "Sección" if block.evaluate("(e) => e.tagName") == "SECTION" else "Bloque"
        number = capture_locator(page, rows, number, title, f"{kind}: {label}", url, block)
    number = capture_element(page, rows, number, title, "Pie de página y navegación secundaria",
                             url, "footer.site-footer")
    return number


def capture_page(page, rows, number, url):
    h1 = page.locator("h1").first
    title = clean(h1.inner_text() if h1.count() else page.title(), 140)
    main = page.locator("main").first
    box = main.bounding_box()
    if not box:
        return number
    heads = []
    h2s = page.locator("main h2")
    for i in range(h2s.count()):
        item, ibox = h2s.nth(i), h2s.nth(i).bounding_box()
        if ibox and ibox["height"] > 0:
            heads.append((ibox["y"], clean(item.inner_text(), 140)))
    start, end = box["y"], box["y"]+box["height"]
    if not heads:
        return capture_band(page, rows, number, title, "Página completa", url, start, end)
    number = capture_band(page, rows, number, title, "Introducción y cabecera",
                          url, start, heads[0][0]-18)
    for i, (top, label) in enumerate(heads):
        bottom = heads[i+1][0]-18 if i+1 < len(heads) else end
        number = capture_band(page, rows, number, title, label or f"Bloque {i+1}",
                              url, top-18, bottom)
    return number


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_urls, rows, number = urls(), [], 1
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9223")
        page = browser.contexts[0].new_page()
        page.set_viewport_size({"width":WIDTH, "height":HEIGHT})
        for i, url in enumerate(all_urls):
            print(f"[{i+1}/{len(all_urls)}] {url}", flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_timeout(7000 if i == 0 else 600); prepare(page)
                number = capture_home(page, rows, number, url) if i == 0 else capture_page(page, rows, number, url)
            except Exception as exc:
                print(f"ERROR {url}: {exc}", flush=True)
        page.close(); browser.close()
    with (OUT/"indice.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.writer(f); w.writerow(["numero","pagina","zona","url","categorias","carpeta"]); w.writerows(rows)
    readme = f"""# Banco de imágenes de la web

Inventario visual de davidportodiaz.com capturado el {date.today().isoformat()}.

- Páginas recorridas: **{len(all_urls)}**
- Capturas creadas: **{len(rows)}**
- Orden: home completa primero; después, páginas del sitemap.
- Cada carpeta contiene captura.png e info.md.
- indice.csv permite filtrar por página, zona, URL o categoría.

Son fuentes de trabajo, no publicaciones terminadas. Antes de publicar hay que adaptar la
imagen a la red, comprobar sus datos y redactar un texto para el objetivo concreto.
"""
    (OUT/"README.md").write_text(readme, encoding="utf-8")
    print(f"CAPTURAS={len(rows)}", flush=True)


if __name__ == "__main__":
    main()
