import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9223", timeout=10000)
    all_pages = [pg for c in b.contexts for pg in c.pages]
    print(f"Total pages in Edge: {len(all_pages)}")
    for i, pg in enumerate(all_pages):
        print(f"  [{i}] {pg.url[:100]}")
