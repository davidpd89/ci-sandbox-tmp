import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
    all_pages = [pg for c in b.contexts for pg in c.pages]
    pv = next((pg for pg in all_pages if "pixverse" in pg.url), None)
    if not pv:
        print("PixVerse no abierto")
        exit()
    pv.bring_to_front()
    pv.wait_for_timeout(1000)

    # Inspeccionar todos los elementos de input visible
    els = pv.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll('textarea, [contenteditable], [role="textbox"], input[type="text"]'));
            return inputs.filter(el => el.offsetParent !== null).map(el => ({
                tag: el.tagName,
                id: el.id || '',
                cls: el.className.substring(0, 60),
                placeholder: el.placeholder || el.getAttribute('aria-placeholder') || '',
                text: (el.value || el.innerText || '').substring(0, 80),
                editable: el.contentEditable,
                visible: el.offsetParent !== null
            }));
        }
    """)
    print(f"Inputs visibles: {len(els)}")
    for e in els:
        print(f"  {e['tag']} id={e['id'][:20]} cls={e['cls'][:40]}")
        print(f"    placeholder={e['placeholder'][:50]}")
        print(f"    text={e['text'][:50]}")

    # También buscar el botón Crear
    btns = pv.evaluate("""
        () => Array.from(document.querySelectorAll('button'))
            .filter(b => b.offsetParent !== null && /crear|create|generar|generate/i.test(b.innerText))
            .map(b => ({text: b.innerText.trim().substring(0,40), cls: b.className.substring(0,40)}))
    """)
    print(f"\nBotones Crear visibles: {len(btns)}")
    for b_info in btns:
        print(f"  '{b_info['text']}' cls={b_info['cls']}")

    pv.screenshot(path="C:/Temp/pv_inspect.png")
