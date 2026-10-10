"""Pregunta a ChatGPT RRSS project via Edge CDP puerto 9223."""
import sys, io, time
try:
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
RRSS_PROJECT_PART = "g-p-6a3bc1e919148191a7b1f1faf854f6d1"

def paste(page, locator, text):
    locator.click()
    page.evaluate("(t) => navigator.clipboard.writeText(t)", text)
    page.keyboard.press("Control+V")
    time.sleep(0.5)

def ask(query, timeout_s=240):
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        ctx = b.contexts[0]
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        pages = [pg for c in b.contexts for pg in c.pages]
        gpt = next(pg for pg in pages if RRSS_PROJECT_PART in pg.url)
        gpt.bring_to_front()

        msg_sel = '[data-message-author-role="assistant"]'
        prev_count, stable = -1, 0
        for _ in range(10):
            cur = gpt.locator(msg_sel).count()
            stable = stable + 1 if cur == prev_count else 0
            prev_count = cur
            if stable >= 2: break
            gpt.wait_for_timeout(500)
        before = prev_count

        box = gpt.locator('[contenteditable="true"]').first
        paste(gpt, box, query)
        gpt.wait_for_timeout(1000)
        # la UI cambia: antes data-testid="send-button", ahora aria-label="Enviar" (type=submit)
        gpt.locator('button[data-testid="send-button"], button[type="submit"][aria-label="Enviar"], '
                    'button[type="submit"][aria-label*="Send"]').first.click()

        waited = 0
        while gpt.locator(msg_sel).count() <= before and waited < timeout_s:
            gpt.wait_for_timeout(2000); waited += 2
        gpt.wait_for_timeout(3000)

        last = gpt.locator(msg_sel).last
        prev_len, stable = -1, 0
        while (stable < 8 or prev_len < 200) and waited < timeout_s:
            gpt.wait_for_timeout(2000)
            cur = len(last.inner_text())
            stable = stable + 1 if cur == prev_len else 0
            prev_len = cur; waited += 2
        return last.inner_text()

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "hola"
    print(ask(q))
