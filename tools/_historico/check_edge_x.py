import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9223", timeout=5000)
    all_pages = [pg for c in b.contexts for pg in c.pages]
    print(f"Pages open ({len(all_pages)}):")
    for pg in all_pages:
        print(f"  {pg.url[:80]}")

    x_pages = [pg for pg in all_pages if "x.com" in pg.url]
    if x_pages:
        xp = x_pages[0]
        xp.screenshot(path="C:/Temp/x_current.png")
        print(f"\nX page: {xp.url}")
        # Contar posts scheduled
        count = xp.evaluate("() => document.querySelectorAll('article[data-testid=\"tweet\"]').length")
        print(f"Tweets visible: {count}")
