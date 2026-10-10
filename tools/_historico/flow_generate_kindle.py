"""
Genera 5 clips en Google Flow (Edge 9223) para DP-F0-070 — Kindle con polvo.
"""
import sys, io, time, base64
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
PROJECT_URL = "https://labs.google/fx/es/tools/flow/project/df4adbe8-1c2c-4578-b3b8-527985ec3850"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    ("A Kindle e-reader sitting on a wooden nightstand, covered in a thin layer of dust, "
     "warm amber lamp light, late at night, cozy bedroom, book spines visible on background "
     "bookshelf, the Kindle is closed and untouched, cinematic close-up, shallow depth of field, "
     "photorealistic, 9:16 vertical, no people"),
    ("A hand picking up a dusty Kindle e-reader from a nightstand, holding it briefly, "
     "then slowly placing it back down, warm bedside lamp light, "
     "cinematic close-up of hand and device, no face visible, wooden nightstand, "
     "photorealistic, 9:16 vertical"),
    ("A bookshelf filled with physical books in warm amber lighting, some with colorful "
     "bookmarks sticking out halfway, some books slightly askew, a few lying flat, "
     "cinematic wide shot, warm lamp light, no people, photorealistic, 9:16 vertical"),
    ("A person lying in bed at night, phone screen lighting their face blue, "
     "a closed Kindle e-reader visible on the nightstand untouched beside them, "
     "warm bedside lamp on, cinematic shot from above, photorealistic, 9:16 vertical"),
    ("Extreme close-up of a Kindle e-reader screen switched off, black reflection, "
     "dust particles visible on surface in warm lamp light, nightstand wood texture, "
     "completely still, cinematic macro shot, photorealistic, atmospheric, 9:16 vertical"),
]

def ss(page, name):
    page.screenshot(path=f"C:/Temp/flow_{name}.png")

def dismiss_modal(flow):
    """Cierra el modal 'Apply to be Featured' haciendo clic en el botón → del modal."""
    flow.wait_for_timeout(2000)
    # El modal tiene un botón con flecha →
    for sel in ["button[aria-label*='next']", "button[aria-label*='Next']",
                "button:has(svg[data-icon='chevron-right'])", "button:has(svg[data-icon='arrow-right'])",
                "button.sc-", "[data-testid*='next']"]:
        try:
            b = flow.locator(sel).first
            if b.is_visible(timeout=1000):
                b.click(); flow.wait_for_timeout(1000); return True
        except Exception: pass
    # Fallback: click en una zona fuera del modal (esquina)
    try:
        # Click en la X o botón de cierre si existe
        close = flow.locator("button[aria-label*='close'], button[aria-label*='Close'], button[aria-label*='cerrar']").first
        if close.is_visible(timeout=1000):
            close.click(); flow.wait_for_timeout(1000); return True
    except Exception: pass
    return False

def get_flow_input(flow):
    """Localiza el input de chat de Flow (Slate editor)."""
    # El input real de Flow es un div con data-slate-editor="true"
    for sel in [
        "[data-slate-editor='true']",
        "div[contenteditable='true'][data-slate-node='value']",
        "[role='textbox'][contenteditable='true']",
    ]:
        try:
            el = flow.locator(sel).first
            visible = el.is_visible(timeout=3000)
            if visible:
                print(f"  Input: {sel}")
                return el, sel
        except Exception: pass
    return None, None

def send_prompt(flow, prompt, inp_sel):
    """Pega el prompt en el input de Flow y envía."""
    # Foco via JS
    flow.evaluate(f"() => {{ const el = document.querySelector(\"{inp_sel}\"); if(el) el.focus(); }}")
    flow.wait_for_timeout(300)
    # Copiar al portapapeles y pegar
    flow.evaluate("(t) => navigator.clipboard.writeText(t)", prompt)
    flow.keyboard.press("Control+V")
    flow.wait_for_timeout(800)
    # Buscar botón de envío (botón con SVG o con texto "Crear"/"Generar")
    sent = False
    for btn_sel in ["button[type='submit']", "button[aria-label*='send']", "button[aria-label*='Enviar']",
                    "button[aria-label*='enviar']", "button:has(svg[data-icon='send'])","button:has(svg[data-icon='arrow-up'])"]:
        try:
            b = flow.locator(btn_sel).last
            if b.is_visible(timeout=1500):
                b.click(); sent = True; print(f"  Enviado con: {btn_sel}"); break
        except Exception: pass
    if not sent:
        flow.keyboard.press("Enter")
        print("  Enviado con Enter")

def confirm_cost(flow):
    """Confirma el coste de puntos si aparece el diálogo."""
    flow.wait_for_timeout(3000)
    for sel in ["button:has-text('Crear')", "button:has-text('Confirmar')",
                "button:has-text('Generar')", "button:has-text('10 puntos')",
                "button[data-testid='confirm']"]:
        try:
            b = flow.locator(sel).first
            if b.is_visible(timeout=2000):
                b.click(); print(f"  Coste confirmado: {sel}"); return True
        except Exception: pass
    return False

def count_videos(flow):
    return flow.evaluate("() => document.querySelectorAll('video').length")

def wait_video(flow, before, timeout_s=300):
    start = time.time()
    while time.time() - start < timeout_s:
        flow.wait_for_timeout(5000)
        cur = count_videos(flow)
        elapsed = int(time.time()-start)
        print(f"  {elapsed}s | videos={cur} (antes={before})", end="\r")
        if cur > before:
            print(f"\n  Nuevo vídeo detectado ({cur} total)")
            return True
    print(f"\n  TIMEOUT {timeout_s}s")
    return False

def download_video(flow, path: Path):
    flow.wait_for_timeout(2000)
    src = flow.evaluate("""
        () => {
            const vs = document.querySelectorAll('video');
            if (!vs.length) return null;
            const v = vs[vs.length-1];
            return v.src || v.currentSrc || null;
        }
    """)
    if not src:
        print("  [WARN] No video src"); return False
    print(f"  src: {src[:70]}...")
    if src.startswith("blob:"):
        b64 = flow.evaluate("""
            async (u) => {
                const r = await fetch(u);
                const buf = await r.arrayBuffer();
                const b = new Uint8Array(buf);
                let s = ''; for (let i=0;i<b.length;i++) s+=String.fromCharCode(b[i]);
                return btoa(s);
            }
        """, src)
        path.write_bytes(base64.b64decode(b64))
    elif src.startswith("http"):
        import urllib.request
        urllib.request.urlretrieve(src, path)
    else:
        print(f"  [WARN] src inesperado"); return False
    kb = path.stat().st_size // 1024
    print(f"  Guardado: {path.name} ({kb} KB)")
    return kb > 10

def run():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        b.contexts[0].grant_permissions(["clipboard-read","clipboard-write"])
        all_pages = [pg for c in b.contexts for pg in c.pages]
        flow = next(pg for pg in all_pages if "labs.google" in pg.url)
        flow.bring_to_front()

        # Navegar directamente al proyecto
        if PROJECT_URL not in flow.url:
            print(f"Navegando a proyecto...")
            flow.goto(PROJECT_URL)
            flow.wait_for_load_state("networkidle", timeout=20000)
        else:
            print(f"Ya en el proyecto: {flow.url}")

        flow.wait_for_timeout(3000)
        ss(flow, "A_project_loaded")

        # Cerrar modal si existe
        modal_visible = flow.evaluate("""
            () => {
                const m = document.querySelector('[role="dialog"], [data-state="open"]');
                return m ? m.innerText.substring(0,50) : null;
            }
        """)
        if modal_visible:
            print(f"Modal detectado: {modal_visible}")
            dismiss_modal(flow)
            ss(flow, "B_modal_closed")

        # Verificar input
        inp, inp_sel = get_flow_input(flow)
        if not inp:
            print("[ERROR] No se encontró input de chat. Capturando estado...")
            ss(flow, "B_no_input")
            # Volcar todos los elementos interactivos
            els = flow.evaluate("""
                () => Array.from(document.querySelectorAll('textarea,input,[contenteditable],[role="textbox"]'))
                     .map(e=>({tag:e.tagName,ce:e.contentEditable,role:e.getAttribute('role'),
                               vis:e.offsetParent!==null,slate:e.dataset.slateEditor}))
            """)
            print("Elementos encontrados:", els)
            return

        print(f"Input encontrado: {inp_sel}")

        # Generar clips
        for i, prompt in enumerate(PROMPTS, 1):
            cp = OUT_DIR / f"clip{i}.mp4"
            if cp.exists() and cp.stat().st_size > 10000:
                print(f"\n=== Clip {i}: ya existe ==="); continue

            print(f"\n=== Clip {i}/{len(PROMPTS)} ===")
            before = count_videos(flow)
            send_prompt(flow, prompt, inp_sel)
            ss(flow, f"C_after_send_clip{i}")
            confirm_cost(flow)
            ss(flow, f"D_after_confirm_clip{i}")

            ok = wait_video(flow, before, timeout_s=300)
            ss(flow, f"E_after_gen_clip{i}")

            if ok:
                download_video(flow, cp)
            else:
                print(f"  [WARN] No se generó vídeo para clip{i}")

            flow.wait_for_timeout(3000)

        print("\n=== RESUMEN ===")
        for i in range(1, 6):
            cp = OUT_DIR / f"clip{i}.mp4"
            ok = cp.exists() and cp.stat().st_size > 10000
            print(f"  clip{i}: {'✓' if ok else '✗'}")

if __name__ == "__main__":
    run()
