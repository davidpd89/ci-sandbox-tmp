"""
Lee la pestana activa de Chrome (conectado via CDP, sesion ya logueada por
David - este script NUNCA navega ni hace clic, solo lee lo que ya esta en
pantalla). Uso puntual para la investigacion visual de TikTok/Instagram.
"""
import sys
from playwright.sync_api import sync_playwright


def pick_page(browser):
    pages = [pg for ctx in browser.contexts for pg in ctx.pages]
    pages = [pg for pg in pages if not pg.is_closed()]
    non_ads = [pg for pg in pages if "ads.tiktok.com" not in pg.url]
    pool = non_ads or pages
    return pool[-1]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "cards"
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://localhost:9222", timeout=15000)
        page = pick_page(b)
        page.wait_for_timeout(500)
        print("URL:", page.url)

        if mode == "cards":
            js = (
                "(els) => els.map((e) => {"
                "  let card = e.closest('div[data-e2e]') || e.parentElement.parentElement.parentElement;"
                "  let txt = card ? card.innerText : '';"
                "  txt = txt.split(String.fromCharCode(10)).filter(Boolean).join(' | ');"
                "  return {href: e.href, txt: txt.slice(0, 250)};"
                "})"
            )
            cards = page.eval_on_selector_all("a[href*='/video/']", js)
            for c in cards[:15]:
                print(c["href"])
                print("  ", c["txt"])
                print("---")
        elif mode == "text":
            print(page.inner_text("body")[:4000])


if __name__ == "__main__":
    main()
