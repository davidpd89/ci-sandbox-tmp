"""
Genera clips en Google Flow via CDP (Chrome ya iniciado con --remote-debugging-port=9222).
Uso: python generate_flow_video.py <carpeta_salida>
"""
import asyncio, sys, os, time, base64
from pathlib import Path
from playwright.async_api import async_playwright

FLOW_URL = "https://labs.google/fx/es/tools/flow"
OUTPUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

PROMPTS = [
    # Clip 1: biblioteca atmosférica
    ("A vast library at night, infinite tall wooden bookshelves reaching up into darkness, "
     "warm amber and gold light filtering between books from hidden lamps, dust motes floating "
     "in beams of light, some book spines glowing faintly, cinematic wide establishing shot, "
     "dark academia aesthetic, dramatic shadows, no people visible, atmospheric silence, "
     "photorealistic, 9:16 vertical"),
    # Clip 2: mano tocando lomos
    ("Close up of a woman's hand slowly running fingertips along wooden bookshelf, touching "
     "book spines one by one, warm lamp light from the side, fingers pause and rest on one book "
     "as if recognizing it, shallow depth of field, only hand and books visible, no face, "
     "intimate and careful gesture, dark library background, photorealistic, cinematic, 9:16 vertical"),
    # Clip 3: libro abierto con subrayados
    ("Close up from above of an old open book with handwritten annotations in the margins, "
     "pencil underlines on some passages, text too small to read clearly, warm reading lamp "
     "light casting soft shadows, some pages slightly worn at corners, subtle page movement "
     "like breathing, no hands visible, intimate detail shot, dark academia, photorealistic, 9:16 vertical"),
    # Clip 4: persona leyendo de noche
    ("A young woman in her bedroom reading a book late at night, face softly lit by a warm "
     "bedside lamp, completely absorbed in reading, mouth slightly open, phone face down on "
     "nightstand, outside window is dark, cozy but intense, cinematic portrait shot, real "
     "human emotion on face, photorealistic, Spanish-looking bedroom setting, 9:16 vertical"),
    # Clip 5: libro cerrado en estantería
    ("A single book placed back on a wooden bookshelf between other books, hand gently pushing "
     "it into place and then pulling away slowly, warm ambient light, other books slightly "
     "blurred in background, final gesture of putting away something precious, intimate close-up, "
     "cinematic, photorealistic, dark academia aesthetic, 9:16 vertical"),
]

async def save_video_from_page(page, clip_path: Path):
    """Extrae el src del <video> más reciente y descarga el blob/url."""
    await page.wait_for_timeout(2000)
    src = await page.evaluate("""
        () => {
            const videos = Array.from(document.querySelectorAll('video'));
            if (!videos.length) return null;
            // Tomar el último video visible (el más reciente generado)
            const last = videos[videos.length - 1];
            return last.src || last.currentSrc || null;
        }
    """)
    if not src:
        print(f"  [WARN] No se encontró <video src> para {clip_path.name}")
        return False
    if src.startswith("blob:"):
        data_b64 = await page.evaluate("""
            async (url) => {
                const r = await fetch(url);
                const buf = await r.arrayBuffer();
                const bytes = new Uint8Array(buf);
                let b = '';
                for (let i = 0; i < bytes.length; i++) b += String.fromCharCode(bytes[i]);
                return btoa(b);
            }
        """, src)
        clip_path.write_bytes(base64.b64decode(data_b64))
    elif src.startswith("http"):
        import urllib.request
        urllib.request.urlretrieve(src, clip_path)
    else:
        print(f"  [WARN] src inesperado: {src[:80]}")
        return False
    print(f"  [OK] Guardado: {clip_path} ({clip_path.stat().st_size // 1024} KB)")
    return True


async def generate_clip(page, prompt: str, clip_idx: int) -> bool:
    clip_path = OUTPUT_DIR / f"clip{clip_idx}.mp4"
    print(f"\n=== Clip {clip_idx} ===")
    print(f"  Prompt: {prompt[:80]}...")

    # Localizar el textarea del chat en Flow
    textarea = page.locator("textarea").first
    await textarea.click()
    await textarea.fill(prompt)
    await page.wait_for_timeout(500)

    # Pulsar Enter o botón de envío
    await textarea.press("Enter")
    print("  Prompt enviado, esperando confirmación de puntos...")

    # Esperar diálogo de confirmación de puntos (aparece en ~2-5s)
    await page.wait_for_timeout(3000)

    # Buscar y pulsar el botón de confirmación (suele ser "Crear" o similar)
    confirm_selectors = [
        "button:has-text('Crear')",
        "button:has-text('Generar')",
        "button:has-text('Confirmar')",
        "button:has-text('Aceptar')",
        "[role='button']:has-text('10')",  # muestra el coste
    ]
    confirmed = False
    for sel in confirm_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                confirmed = True
                print(f"  Confirmación pulsada: {sel}")
                break
        except Exception:
            continue

    if not confirmed:
        print("  [WARN] No se encontró botón de confirmación — puede que ya se generó")

    # Esperar a que el vídeo aparezca (máx 3 min)
    print("  Esperando generación (hasta 3 min)...")
    start = time.time()
    while time.time() - start < 180:
        await page.wait_for_timeout(5000)
        # Verificar si hay un video nuevo visible
        n_videos = await page.evaluate("() => document.querySelectorAll('video').length")
        if n_videos >= clip_idx:
            print(f"  Vídeos detectados en página: {n_videos}")
            break
        elapsed = int(time.time() - start)
        print(f"  ... {elapsed}s transcurridos, {n_videos} vídeos visibles", end="\r")

    # Intentar descargar
    return await save_video_from_page(page, clip_path)


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        # Buscar pestaña de Flow o abrir una nueva
        flow_page = None
        for pg in context.pages:
            if "labs.google" in pg.url or "flow" in pg.url.lower():
                flow_page = pg
                break

        if not flow_page:
            flow_page = await context.new_page()
            await flow_page.goto(FLOW_URL)
            print("Abriendo Flow... esperando carga")
            await flow_page.wait_for_load_state("networkidle", timeout=30000)
        else:
            print(f"Reutilizando pestaña: {flow_page.url}")

        await flow_page.bring_to_front()
        print(f"Página activa: {flow_page.url}")

        # Verificar puntos disponibles (leer del contador)
        await flow_page.wait_for_timeout(2000)
        points_text = await flow_page.evaluate("""
            () => {
                const els = Array.from(document.querySelectorAll('*'));
                for (const el of els) {
                    const t = el.innerText;
                    if (t && /\\d+.*punto/i.test(t) && t.length < 50) return t.trim();
                }
                return null;
            }
        """)
        print(f"Puntos disponibles: {points_text or '(no detectado)'}")

        # Generar cada clip
        results = []
        for i, prompt in enumerate(PROMPTS, 1):
            if (OUTPUT_DIR / f"clip{i}.mp4").exists():
                print(f"\n=== Clip {i} ya existe, saltando ===")
                results.append(True)
                continue
            ok = await generate_clip(flow_page, prompt, i)
            results.append(ok)
            if ok:
                print(f"  clip{i}.mp4 guardado ✓")
            else:
                print(f"  clip{i}.mp4 FALLÓ ✗")
            # Pequeña pausa entre generaciones
            await flow_page.wait_for_timeout(3000)

        print(f"\n=== RESULTADO: {sum(results)}/{len(results)} clips generados ===")
        for i, ok in enumerate(results, 1):
            print(f"  clip{i}: {'✓' if ok else '✗'}")


if __name__ == "__main__":
    asyncio.run(main())
