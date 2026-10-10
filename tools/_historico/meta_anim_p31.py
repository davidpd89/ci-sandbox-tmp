# -*- coding: utf-8 -*-
"""
Animate P31 reference image via Meta AI CDP.
Uses the correct approach:
1. New chat on meta.ai
2. Upload image
3. Send image prompt (Instantaneo for 4 variants)
4. Download best image
5. Then send animation prompt (Reflexivo, "Genera una animacion de 10 segundos...")
6. Download video
"""
import asyncio, base64, os, sys
from pathlib import Path
from playwright.async_api import async_playwright

EDGE_CDP = "http://localhost:9223"
IMG = r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Imagenes david\1000106610_v3.png"
OUT_DIR = r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\31-libros-que-encuentran"

os.makedirs(OUT_DIR, exist_ok=True)


async def paste_text(page, text):
    """Paste text via clipboard to avoid character loss."""
    await page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    await page.evaluate("(t) => navigator.clipboard.writeText(t)", text)
    # Find the composer box (bounding box filter)
    el = await page.evaluate("""() => {
        const els = document.querySelectorAll("div[contenteditable='true']");
        for (const e of els) {
            const r = e.getBoundingClientRect();
            if (r.width > 100 && r.height > 5 && r.y > 50) {
                return {x: r.x + 10, y: r.y + 10};
            }
        }
        return null;
    }""")
    if not el:
        raise RuntimeError("No composer box found")
    await page.mouse.click(el["x"], el["y"])
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Control+V")
    await asyncio.sleep(0.5)
    # Verify content length
    content = await page.evaluate("document.activeElement.innerText")
    print(f"  Compositor has {len(content)} chars")
    return len(content)


async def upload_image(page, img_path):
    """Upload image via file input."""
    try:
        async with page.expect_file_chooser(timeout=8000) as fc_info:
            # Try the "+" or attach button
            btn = page.locator("[aria-label='Attach'], [data-testid='attach'], button:has-text('+')").first
            await btn.click(timeout=5000)
        fc = await fc_info.value
        await fc.set_files(img_path)
        print("  Imagen subida via file chooser")
        return True
    except Exception:
        pass
    # Fallback: input[type=file]
    try:
        inputs = await page.query_selector_all("input[type='file']")
        for inp in inputs:
            try:
                await inp.set_input_files(img_path)
                print("  Imagen subida via input[type=file]")
                return True
            except Exception:
                continue
    except Exception as e:
        print(f"  Upload error: {e}")
    return False


async def wait_for_image(page, timeout_s=90):
    """Wait for a generated image in Meta AI chat."""
    for _ in range(timeout_s):
        imgs = await page.query_selector_all("img[src*='fbcdn']")
        for img in imgs:
            src = await img.get_attribute("src")
            if src and "fbcdn" in src:
                return src
        await asyncio.sleep(1)
    return None


async def wait_for_video(page, timeout_s=180):
    """Wait for a generated video in Meta AI chat."""
    for _ in range(timeout_s):
        videos = await page.query_selector_all("video")
        for v in videos:
            src = await v.get_attribute("src")
            if src and src.startswith("http"):
                return src
        await asyncio.sleep(1)
    return None


async def download_url(page, url, out_path):
    """Download a URL via browser fetch (avoids CORS)."""
    result = await page.evaluate("""async (url) => {
        const resp = await fetch(url);
        const buf = await resp.arrayBuffer();
        const bytes = new Uint8Array(buf);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
        return btoa(binary);
    }""", url)
    data = base64.b64decode(result)
    with open(out_path, "wb") as f:
        f.write(data)
    return len(data)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(EDGE_CDP)
        ctx = browser.contexts[0]

        # Open a fresh meta.ai tab
        page = await ctx.new_page()
        await page.goto("https://www.meta.ai/", wait_until="networkidle", timeout=30000)
        print("Meta AI abierto")
        await asyncio.sleep(2)

        # --- STEP 1: Upload image + image prompt ---
        print("\n[1] Subiendo imagen y pidiendo variante animable...")
        uploaded = await upload_image(page, IMG)
        if not uploaded:
            print("ERROR: no se pudo subir la imagen")
            return

        await asyncio.sleep(1)
        img_prompt = (
            "A partir de esta imagen, mantén exactamente la misma composición y atmósfera: "
            "el hombre sentado en el muro desde arriba, la mujer sentada abajo contra la pared. "
            "Ciudad de fondo con cielo azul-gris de tarde. "
            "Hazla más cinematográfica: luces de ciudad que empiezan a encenderse, "
            "la escena más dramática y emotiva. Sin texto en la imagen."
        )
        await paste_text(page, img_prompt)
        await page.keyboard.press("Enter")
        print("  Esperando imagen mejorada (hasta 90s)...")
        img_src = await wait_for_image(page, 90)
        if img_src:
            img_bytes = await download_url(page, img_src, os.path.join(OUT_DIR, "img_mejorada.png"))
            print(f"  Imagen descargada: {img_bytes // 1024}KB")
        else:
            print("  Timeout imagen — continuando con animación de referencia original")

        # --- STEP 2: Animation prompt ---
        print("\n[2] Pidiendo animación...")
        anim_prompt = (
            "Genera una animación de 10 segundos de duración. "
            "Anima esta escena con movimiento muy sutil: la cámara hace un zoom lento "
            "hacia las dos figuras. El viento mueve levemente el pelo de la mujer. "
            "Las luces de la ciudad parpadean suavemente al fondo. "
            "No cambies la composición. Sin texto generado."
        )
        await paste_text(page, anim_prompt)
        await page.keyboard.press("Enter")
        print("  Esperando video Meta AI (hasta 240s)...")
        vid_src = await wait_for_video(page, 240)
        if vid_src:
            vid_bytes = await download_url(page, vid_src, os.path.join(OUT_DIR, "clip_meta_p31.mp4"))
            print(f"  Video descargado: {vid_bytes // 1024}KB ({vid_bytes / 1024 / 1024:.1f}MB)")
        else:
            print("  TIMEOUT video — usar stock como fallback")

        await page.close()

asyncio.run(main())
