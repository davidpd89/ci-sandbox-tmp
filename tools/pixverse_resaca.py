"""
Genera en PixVerse el vídeo "Resaca de libro" (DP-F0-071).
Selector correcto: textarea.w-full. 12s, Multi-Toma, sin audio (48cr) o con (60cr).
"""
import sys, io, time, base64
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_AutoraDemo\09_Usados_video\pixverse\piezas\04-resaca-libro")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "A young woman lies on a couch at night, a closed book resting on the coffee table in front of her. "
    "She is not reading — she stares at the closed book with a quiet, unresolved expression, "
    "like she is still inside it even though it is finished. Warm lamp light from the side, "
    "a blanket over her legs, a forgotten mug nearby. Book cover has no visible text. "
    "Cinematic realism, no drama, raw emotion, real domestic setting. "
    "Multi-shot: close-up of face, then book alone on table, then wide shot of room. "
    "No text, no subtitles, no logos. 9:16 vertical."
)

def ss(page, name):
    page.screenshot(path=f"C:/Temp/pvr_{name}.png")

def run():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        ctx = b.contexts[0]
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        all_pages = [pg for c in b.contexts for pg in c.pages]

        pv = next((pg for pg in all_pages if "pixverse" in pg.url), None)
        if not pv:
            print("PixVerse no abierto en Edge")
            return
        pv.bring_to_front()
        pv.wait_for_timeout(1000)
        ss(pv, "01_start")

        # Contar vídeos antes
        before = pv.evaluate("() => document.querySelectorAll('video').length")
        print(f"Videos antes: {before}")

        # Foco via JS y pegar prompt
        pv.evaluate("""
            () => {
                const ta = document.querySelector('textarea.w-full') ||
                           document.querySelector('textarea[placeholder*="Describa"]') ||
                           document.querySelector('textarea[placeholder*="Describe"]') ||
                           document.querySelector('textarea');
                if (ta) ta.focus();
            }
        """)
        pv.wait_for_timeout(300)
        pv.keyboard.press("Control+A")
        pv.evaluate("(t) => navigator.clipboard.writeText(t)", PROMPT)
        pv.keyboard.press("Control+V")
        pv.wait_for_timeout(800)
        # Verificar que se pegó
        current_val = pv.evaluate("() => document.querySelector('textarea')?.value || ''")
        print(f"Prompt pegado: {current_val[:60]}...")
        if not current_val.strip():
            # Fallback: tipo a tipo
            pv.evaluate("() => { const ta = document.querySelector('textarea'); if(ta) { ta.value=''; ta.dispatchEvent(new Event('input')); } }")
            pv.keyboard.type(PROMPT[:200], delay=10)
        print("Prompt listo")
        ss(pv, "02_prompt")

        # Cambiar duración a 12s buscando el selector de duración
        # PixVerse suele tener botones de duración o un slider
        print("Buscando control de duración...")
        for dur in ["12", "12s", "12 s"]:
            for sel in [f"button:has-text('{dur}')", f"[data-value='{dur}']", f"[value='{dur}']"]:
                try:
                    el = pv.locator(sel).first
                    if el.is_visible(timeout=1000):
                        el.click()
                        print(f"  Duración 12s: {sel}")
                        break
                except Exception:
                    pass

        # Ver créditos del botón antes de confirmar
        btn_text = pv.evaluate("""
            () => {
                const bs = document.querySelectorAll('button');
                for (const b of bs) {
                    if (/crear|create/i.test(b.innerText) && b.offsetParent !== null) return b.innerText.trim();
                }
                return null;
            }
        """)
        print(f"Botón ahora: '{btn_text}'")
        ss(pv, "03_settings")

        # Clicar Crear
        crear = pv.locator("button:has-text('Crear'), button:has-text('Create')").first
        crear.wait_for(state="visible", timeout=5000)
        crear.click()
        print("Crear pulsado")
        pv.wait_for_timeout(2000)
        ss(pv, "04_after_crear")

        # Confirmar si hay diálogo de créditos
        for sel in ["button:has-text('Confirmar')", "button:has-text('Aceptar')", "button:has-text('OK')", "button:has-text('Continuar')"]:
            try:
                c = pv.locator(sel).first
                if c.is_visible(timeout=2000):
                    c.click()
                    print(f"Confirmado: {sel}")
                    break
            except Exception:
                pass

        ss(pv, "05_confirmed")
        print("Esperando generación (hasta 5 min)...")

        start = time.time()
        found_video = False
        while time.time() - start < 300:
            pv.wait_for_timeout(5000)
            elapsed = int(time.time() - start)

            # Verificar si hay un vídeo nuevo en la zona de generaciones recientes
            cur_videos = pv.evaluate("() => document.querySelectorAll('video').length")
            # Verificar si hay spinner/progress aún
            in_progress = pv.evaluate("""
                () => document.querySelectorAll('[class*="generating"], [class*="progress-"], [class*="loading"]').length
            """)
            print(f"  {elapsed}s | videos={cur_videos} in_progress={in_progress}", end="\r")

            if cur_videos > before:
                print(f"\n  Vídeo detectado ({cur_videos} total)")
                found_video = True
                break

        ss(pv, "06_result")

        if not found_video:
            print("\n  TIMEOUT — ver screenshot 06_result")
            print("  Verifica visualmente si el vídeo se generó (el thumbnail puede no mostrar <video>)")
            return

        # Descargar
        pv.wait_for_timeout(2000)
        src = pv.evaluate("""
            () => {
                const vs = Array.from(document.querySelectorAll('video'));
                const last = vs[vs.length - 1];
                return last ? (last.src || last.currentSrc) : null;
            }
        """)
        if not src:
            print("  No src de video encontrado — descarga manual necesaria")
            return

        print(f"  src: {src[:80]}")
        out = OUT_DIR / "clip1.mp4"
        if src.startswith("blob:"):
            b64 = pv.evaluate("""
                async (url) => {
                    const r = await fetch(url);
                    const buf = await r.arrayBuffer();
                    const b = new Uint8Array(buf);
                    let s = ''; for (let i=0; i<b.length; i++) s+=String.fromCharCode(b[i]);
                    return btoa(s);
                }
            """, src)
            out.write_bytes(base64.b64decode(b64))
        elif src.startswith("http"):
            import urllib.request
            urllib.request.urlretrieve(src, out)

        print(f"  Guardado: {out.name} ({out.stat().st_size//1024}KB)")

if __name__ == "__main__":
    run()
