"""
Investigacion de hashtags via paginas publicas de Instagram, SIN login.

Usa un contexto de navegador anonimo (Playwright) para abrir la pagina de
exploracion de un hashtag y los posts/reels que aparecen ahi, y lee los
meta-tags og:description/og:title/og:image (los mismos que usan los bots
de previsualizacion de enlaces) para sacar likes, comentarios, cuenta,
caption y hashtags usados, sin necesidad de iniciar sesion ni de usar la
cuenta @autorademodiaz.

IMPORTANTE: esto es solo lectura de paginas publicas, no toca la cuenta
de David ni publica nada. No confundir con automatizacion de publicacion
(esa sigue prohibida, solo Metricool MCP). Aun asi, ir con calma entre
peticiones para no parecer trafico de bot agresivo.

Uso:
    python scrape_hashtag_top.py <hashtag_sin_almohadilla> [n_posts]
"""
import sys
import re
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).parent / "resultados"


META_PATTERN = re.compile(
    r"^([\d.,]+[KM]?) likes?(?:, ([\d.,]+[KM]?) comments?)? - ([^\s]+) on ([^:]+): &quot;(.*)&quot;\.\s*$",
    re.S,
)


def parse_meta(html):
    desc = re.findall(r'<meta property="og:description" content="([^"]+)"', html)
    img = re.findall(r'<meta property="og:image" content="([^"]+)"', html)
    desc = desc[0] if desc else ""
    m = META_PATTERN.match(desc)
    if not m:
        return {"likes": None, "comments": None, "account": None, "date": None, "caption": desc, "image": img[0] if img else None}
    likes, comments, account, date, caption = m.groups()
    return {"likes": likes, "comments": comments, "account": account, "date": date, "caption": caption, "image": img[0] if img else None}


def scrape_hashtag(tag, n=8):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"https://www.instagram.com/explore/tags/{tag}/", timeout=20000)
        page.wait_for_timeout(3000)
        links = page.eval_on_selector_all(
            "a[href*='/p/'], a[href*='/reel/']", "els => els.map(e => e.href)"
        )
        seen = []
        for l in links:
            base = l.split("?")[0]
            if base not in seen:
                seen.append(base)
        for url in seen[:n]:
            page.goto(url, timeout=20000)
            page.wait_for_timeout(1800)
            html = page.content()
            meta = parse_meta(html)
            meta["url"] = url
            meta["tag"] = tag
            results.append(meta)
            time.sleep(1.2)
        browser.close()
    return results


def main():
    tag = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    results = scrape_hashtag(tag, n)
    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"{tag}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(results)} posts -> {out_path}")
    for r in results:
        print(f"  {r.get('likes')} likes | {r.get('comments')} comments | {r.get('account')} | {r.get('url')}")


if __name__ == "__main__":
    main()
