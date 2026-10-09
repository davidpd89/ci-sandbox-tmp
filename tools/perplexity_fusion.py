"""Generador de imagenes humanas via Perplexity Pro (sesion real de David), automatizado con Playwright.

Encapsula el protocolo validado en 08_Contenido_mas_IA/protocolos/generacion_imagen_humana_ia_real.md:
- conecta sobre el Edge real de David (mismo perfil, login conservado)
- sube 1-2 imagenes de referencia + prompt
- espera el resultado de GPT-4o image gen y lo descarga en alta resolucion (nunca screenshot)

Uso:
    from perplexity_fusion import generate
    generate(["foto.png", "portada_real.jpg"], "prompt...", "salida.png")
"""
import os
import re
import subprocess
import time
import urllib.request

from playwright.sync_api import sync_playwright

EDGE_PORT = 9223
EDGE_PATH = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
EDGE_PROFILE = "C:/Users/demouser/AppData/Local/Microsoft/Edge/User Data"

# Bug real encontrado en vivo (2026-07-12, capitulo 11 del libro de Alicia):
# cuando Perplexity agota su cuota de generacion de imagenes NO lanza ningun
# error visible - responde con una respuesta de TEXTO normal ofreciendo un
# prompt para pegar en Midjourney/DALL-E/Krea en su lugar. El codigo anterior
# no tenia forma de distinguir esto de "todavia esta generando", asi que
# esperaba el timeout_s completo (90s) para nada. Deteccion: si no hay
# imagen nueva pero SI aparecio este texto de rechazo, fallar YA en vez de
# seguir esperando.
_CUOTA_AGOTADA_RE = re.compile(
    r"no puedo generar la imagen directamente|no puedo crear im[aá]genes directamente|"
    r"puedo darte un prompt|prueba con (midjourney|dall-?e|krea)",
    re.IGNORECASE,
)


class CuotaAgotadaError(RuntimeError):
    pass


def ensure_edge_running(allow_start: bool = False):
    try:
        urllib.request.urlopen(f"http://localhost:{EDGE_PORT}/json/version", timeout=2)
        return
    except Exception:
        pass
    if not allow_start:
        raise RuntimeError(
            f"Edge no responde en CDP {EDGE_PORT}. Abre el Edge ya logueado/preparado "
            "con --remote-debugging-port=9223; este script no arranca otro navegador por defecto."
        )
    subprocess.Popen([
        EDGE_PATH,
        f"--remote-debugging-port={EDGE_PORT}",
        f"--user-data-dir={EDGE_PROFILE}",
        "https://www.perplexity.ai/",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(1)
        try:
            urllib.request.urlopen(f"http://localhost:{EDGE_PORT}/json/version", timeout=2)
            return
        except Exception:
            continue
    raise RuntimeError("Edge no respondio en el puerto de depuracion tras 20s")


def generar_en_pagina(page, image_paths, prompt, timeout_s=90):
    """Igual que `generate()` pero opera sobre una `page` YA conectada
    (compartida con otros proveedores) en vez de abrir su propia instancia
    de Playwright. Existe porque `sync_playwright()` no admite instancias
    anidadas en el mismo hilo (bug real 2026-07-12: al usar ChatGPT y
    Perplexity en la misma sesion del generador multiproveedor, la segunda
    llamada a `sync_playwright()` fallaba con "using Playwright Sync API
    inside the asyncio loop"). Devuelve los BYTES de la imagen (no escribe
    a disco - a diferencia de `generate()`, para poder compartir la page
    con el resto del pipeline sin gestionar su propio archivo temporal)."""
    page.goto("https://www.perplexity.ai/")
    page.wait_for_timeout(2500)
    if image_paths:
        file_input = page.query_selector("input[type=file]")
        file_input.set_input_files(image_paths)
        page.wait_for_timeout(3000)
    box = page.query_selector("textarea, [contenteditable=true]")
    box.click()
    box.fill(prompt)
    page.wait_for_timeout(800)
    for attempt in range(5):
        try:
            page.click("button[aria-label=Enviar]", timeout=10000)
            break
        except Exception:
            page.wait_for_timeout(1500)
    else:
        raise RuntimeError("No se pudo pulsar Enviar tras varios intentos")

    url = None
    elapsed = 0
    while elapsed < timeout_s:
        page.wait_for_timeout(5000)
        elapsed += 5
        for im in page.query_selector_all("img"):
            src = im.get_attribute("src")
            if src and "gpt4o_images" in src:
                url = src
        if url:
            break
        if elapsed >= 10 and _CUOTA_AGOTADA_RE.search(page.inner_text("body")):
            raise CuotaAgotadaError(
                "Perplexity ha agotado la cuota de generacion de imagenes "
                "(respondio con texto en vez de imagen). Cambia de proveedor."
            )
    if not url:
        raise TimeoutError(f"No se genero ninguna imagen en {timeout_s}s")
    resp = page.request.get(url)
    return resp.body()


def generate(image_paths, prompt, out_path, timeout_s=90, allow_start: bool | None = None):
    """Sube image_paths (1 o 2 rutas) + prompt a Perplexity, descarga el
    resultado en out_path. Abre su PROPIA instancia de Playwright - no la
    uses junto con otro driver (ChatGPT/Meta AI) en el mismo hilo dentro de
    la misma sesion; para eso usa `generar_en_pagina()` sobre una page
    compartida (ver `generador_imagen_libro.py`)."""
    if allow_start is None:
        allow_start = os.environ.get("RRSS_ALLOW_BROWSER_START") == "1"
    ensure_edge_running(allow_start=allow_start)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://localhost:{EDGE_PORT}")
        ctx = browser.contexts[0]
        page = ctx.pages[0]
        data = generar_en_pagina(page, image_paths, prompt, timeout_s=timeout_s)
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path


REGLAS_PROMPT = """
Reglas fijas para construir prompts con esta herramienta (de las lecciones del protocolo):
1. La instruccion mas critica va primera y sola, nunca dentro de una lista numerada.
2. Si hay un libro/objeto real de por medio: pasar su imagen real como segunda referencia, nunca dejar que la IA la invente bajo un nombre real.
3. Listar explicitamente que elementos NO pueden quedar iguales que la referencia (si se quiere variacion real).
4. Pedir siempre proporciones reales de objetos (ej. libro de bolsillo, no grueso).
5. Si hay texto a renderizar: especificar EN ESPAÑOL explicitamente.
6. Verificar el resultado contra la realidad (portada real, etc.) antes de aceptarlo.
"""
