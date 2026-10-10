# -*- coding: utf-8 -*-
"""
Anima imagen P30 (#606) via Meta AI CDP + descarga el video resultante.
Pide: animacion cinematica sutil, misma composicion, no texto generado.
"""
import asyncio, base64, os, sys, time
from pathlib import Path
from playwright.async_api import async_playwright

EDGE_CDP = "http://localhost:9223"
IMG = r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Imagenes david\1000106606_v3.png"
OUT_DIR = r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\30-dualidad-lectora"
LOG = r"C:\GIT\RRSS_DavidPorto\tools\meta_p30_out.txt"

os.makedirs(OUT_DIR, exist_ok=True)


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


async def paste_text(page, text):
    await page.evaluate("(t) => navigator.clipboard.writeText(t)", text)
    els = await page.query_selector_all("div[contenteditable='true']")
    for el in els:
        bb = await el.bounding_box()
        if bb and bb["width"] > 100 and bb["y"] > 50:
            await page.mouse.click(bb["x"] + 10, bb["y"] + 10)
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Control+v")
            await asyncio.sleep(0.6)
            content = await page.evaluate("document.activeElement.innerText")
            log(f"  Compositor: {len(content)} chars")
            return True
    log("  ERROR: no compositor found")
    return False


async def upload_image(page, img_path):
    inputs = await page.query_selector_all("input[type='file']")
    for inp in inputs:
        try:
            await inp.set_input_files(img_path)
            log("  Imagen subida via input[type=file]")
            return True
        except Exception:
            pass
    # Try via button click
    try:
        async with page.expect_file_chooser(timeout=6000) as fc_info:
            btn = page.locator("[aria-label='Attach'], button:has-text('+')").first
            await btn.click(timeout=5000)
        fc = await fc_info.value
        await fc.set_files(img_path)
        log("  Imagen subida via file chooser")
        return True
    except Exception as e:
        log(f"  Upload error: {e}")
    return False


async def wait_for_video(page, timeout_s=240):
    for i in range(timeout_s):
        videos = await page.query_selector_all("video")
        for v in videos:
            src = await v.get_attribute("src")
            if src and src.startswith("http"):
                return src
        if i % 30 == 0:
            log(f"  Esperando video... {i}s")
        await asyncio.sleep(1)
    return None


async def download_url(page, url, out_path):
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
    log(f"[{time.strftime('%H:%M:%S')}] Iniciando animacion P30...")
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(EDGE_CDP)
        except Exception as e:
            log(f"ERROR CDP: {e}. Edge debe estar abierto con --remote-debugging-port=9223")
            return

        ctx = browser.contexts[0]
        page = await ctx.new_page()
        await page.goto("https://www.meta.ai/", wait_until="networkidle", timeout=30000)
        log("Meta AI abierto")
        await asyncio.sleep(3)

        # 1. Subir imagen
        log("\n[1] Subiendo imagen...")
        uploaded = await upload_image(page, IMG)
        if not uploaded:
            log("ERROR: no se pudo subir la imagen")
            await page.close()
            return

        await asyncio.sleep(1.5)

        # 2. Prompt de animacion
        anim_prompt = (
            "Genera una animación de 10 segundos de esta imagen. "
            "Mantén exactamente la misma composición: el hombre sentado enredado en el hilo azul, "
            "la mujer frente a él. Fondo blanco. "
            "Movimiento sutil: el hilo azul ondea muy lentamente, "
            "la cámara hace un zoom lento de 2% hacia los personajes. "
            "Atmósfera tranquila y contemplativa. Sin texto generado en la imagen."
        )
        log(f"\n[2] Enviando prompt de animación...")
        ok = await paste_text(page, anim_prompt)
        if not ok:
            await page.close()
            return
        await page.keyboard.press("Enter")

        log("  Esperando video Meta AI (hasta 240s)...")
        vid_src = await wait_for_video(page, 240)
        if vid_src:
            out_path = os.path.join(OUT_DIR, "clip_meta_p30.mp4")
            vid_bytes = await download_url(page, vid_src, out_path)
            log(f"  Video descargado: {vid_bytes // 1024}KB ({vid_bytes / 1024 / 1024:.1f}MB)")
            log(f"  Guardado en: {out_path}")
        else:
            log("  TIMEOUT video — usar imagen con zoom como fallback")

        await page.close()


if __name__ == "__main__":
    asyncio.run(main())
