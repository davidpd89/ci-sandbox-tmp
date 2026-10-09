"""
Transforma imagenes de referencia usando ChatGPT + DALL-E.
Usa el proyecto "MCP - RRSS Autora Demo" (no crea chats nuevos en el root).

Flujo por imagen:
  1. Navegar al proyecto y abrir conversacion nueva
  2. Subir imagen + pedir analisis JSON y prompt DALL-E adaptado
  3. Esperar analisis (texto)
  4. Pedir la generacion DALL-E con ese prompt
  5. Capturar la imagen generada via interceptacion de red
  6. Guardar como <nombre>_v3.png

Uso:
    python chatgpt_image_transform.py [imagen1.png] [imagen2.jpg] ...
    Sin argumentos: procesa los 10 originales.
"""
import sys
import time
import base64
import threading
import queue
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

CDP_URL = "http://127.0.0.1:9223"
IMAGES_DIR = Path(r"C:\GIT\RRSS_AutoraDemo\nuevo_flujo\Imagenes david")
PROJECT_ID = "g-p-6a3bc1e919148191a7b1f1faf854f6d1"
PROJECT_URL = f"https://chatgpt.com/g/{PROJECT_ID}/project"

ORIGINALS = [
    "1000106600.png",
    "1000106601.png",
    "1000106602.png",
    "1000106603.png",
    "1000106604.png",
    "1000106605.png",
    "1000106606.png",
    "1000106608.jpg",
    "1000106609.png",
    "1000106610.png",
]

PROMPT_STEP1 = (
    "Analiza esta imagen. Extrae: "
    "(1) estilo visual (ilustracion, foto, meme, boceto, etc.), "
    "(2) composicion y estructura, "
    "(3) colores dominantes, "
    "(4) personaje o elemento principal con descripcion especifica, "
    "(5) texto exacto si lo hay y su funcion emocional, "
    "(6) tono emocional y por que funciona en redes literarias en espanol. "
    "Luego escribe un PROMPT DALL-E en ingles, detallado, que genere una imagen "
    "con LA MISMA FORMULA EMOCIONAL pero visualmente DISTINTA: "
    "- diferente paleta de color (si era calida, usa fria; si era oscura, usa clara) "
    "- personaje diferente en descripcion fisica, pose y expresion "
    "- escenario o fondo distinto pero con el mismo ambiente emocional "
    "- si habia texto, reformula el concepto con otras palabras y estructura "
    "- misma composicion general (vertical, centrada, etc.) "
    "El prompt debe resultar en una imagen que NO sea reconocible como la misma "
    "pero que tenga exactamente el mismo impacto en redes. "
    "Pon el prompt DALL-E entre triple comillas: \\\"\\\"\\\"...\\\"\\\"\\\"."
)

PROMPT_STEP2 = (
    "Genera ahora la imagen usando exactamente el prompt DALL-E que escribiste. "
    "Instrucciones adicionales obligatorias: "
    "(1) Si la imagen incluye una persona, debe ser atractiva, de aspecto joven y fotografica — "
    "no aspecto casual de meme, sino aspecto editorial/lifestyle. "
    "(2) Si aparece un libro, repres\\u00e9ntalo cerrado o como prop minimalista — "
    "nunca con texto interior visible (DALL-E lo distorsiona y queda raro). "
    "Crea la imagen ahora."
)

IMAGE_DOMAINS = [
    "oaiusercontent.com",
    "files.openai.com",
    "production.cdn.openai.com",
    "chatgpt.com/backend-api/estuary",
]


def find_chatgpt_page(b):
    pages = [pg for c in b.contexts for pg in c.pages]
    gpt = next((pg for pg in pages if "chatgpt.com" in pg.url), None)
    if gpt is None:
        raise RuntimeError("No hay pestana de ChatGPT en Edge (puerto 9223)")
    return gpt


def navigate_to_new_project_chat(gpt):
    """Navega al proyecto y arranca una nueva conversacion dentro de el."""
    gpt.goto(PROJECT_URL)
    gpt.wait_for_timeout(4000)
    # La pagina del proyecto ya tiene un composer activo para nueva conversacion
    # Si hay un boton explicito de nuevo chat dentro del proyecto, lo usamos
    new_btn = gpt.locator(f'a[href*="{PROJECT_ID}"][aria-label*="Nuevo"]')
    if new_btn.count() > 0:
        new_btn.first.click()
        gpt.wait_for_timeout(3000)
    # Si no, la pagina del proyecto ya sirve como punto de entrada para chat nuevo
    print(f"  Proyecto cargado: {gpt.url[:80]}", flush=True)


def stable_assistant_count(gpt, retries=10, delay=500):
    msg_sel = '[data-message-author-role="assistant"]'
    prev, stable = -1, 0
    for _ in range(retries):
        cur = gpt.locator(msg_sel).count()
        stable = stable + 1 if cur == prev else 0
        prev = cur
        if stable >= 2:
            break
        gpt.wait_for_timeout(delay)
    return prev


def wait_for_new_message(gpt, before, timeout_s=180):
    msg_sel = '[data-message-author-role="assistant"]'
    waited = 0
    while gpt.locator(msg_sel).count() <= before and waited < timeout_s:
        gpt.wait_for_timeout(2000)
        waited += 2
    if gpt.locator(msg_sel).count() <= before:
        raise TimeoutError("ChatGPT no respondio en el tiempo esperado")
    # Esperar a que el texto se estabilice (streaming)
    # Usar try/except porque DALL-E puede estar en loading y el texto no ser accesible
    prev_len, stable = -1, 0
    while stable < 6 and waited < timeout_s:
        gpt.wait_for_timeout(2000)
        try:
            cur = len(gpt.locator(msg_sel).last.inner_text(timeout=5000))
        except Exception:
            cur = prev_len  # Si no se puede leer, asumir que no ha cambiado
        stable = stable + 1 if cur == prev_len else 0
        prev_len = cur
        waited += 2
    gpt.wait_for_timeout(2000)
    return gpt.locator(msg_sel).last


def send_text(gpt, ctx, text):
    """Pega y envia un mensaje de texto en el composer activo."""
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    box = gpt.locator(
        '#prompt-textarea, div[contenteditable="true"][aria-label*="chat"], div[contenteditable="true"]'
    ).first
    box.click()
    gpt.evaluate("(t) => navigator.clipboard.writeText(t)", text)
    gpt.keyboard.press("Control+V")
    gpt.wait_for_timeout(1200)
    send_btn = gpt.locator('button[data-testid="send-button"]')
    if send_btn.count() > 0:
        send_btn.click()
    else:
        box.press("Enter")


def upload_image(gpt, image_path: Path):
    """Sube una imagen via el input file del composer."""
    for sel in ["#upload-photos", "#upload-files", 'input[type="file"]']:
        loc = gpt.locator(sel)
        if loc.count() > 0:
            loc.first.set_input_files(str(image_path))
            print(f"  Imagen subida via {sel}", flush=True)
            gpt.wait_for_timeout(2000)
            return
    # Fallback: filechooser via boton de adjuntar
    print("  Buscando boton de adjuntar...", flush=True)
    with gpt.expect_file_chooser(timeout=10000) as fc_info:
        gpt.locator(
            'button[aria-label*="Adjuntar"], button[aria-label*="Attach"], button[aria-label*="archivos"]'
        ).first.click()
    fc_info.value.set_files(str(image_path))
    gpt.wait_for_timeout(2000)


def extract_image_from_response(gpt, last_msg) -> bytes | None:
    """
    Busca la imagen DALL-E en el ultimo mensaje.
    Prueba: img tags con URL de oaiusercontent o blob.
    """
    # Buscar en toda la pagina (no solo en el ultimo mensaje)
    # porque DALL-E a veces renderiza fuera del contenedor del mensaje
    all_imgs_page = gpt.evaluate("""
        () => {
            return Array.from(document.querySelectorAll('img')).map(i => ({
                src: i.src || i.getAttribute('src') || '',
                w: i.naturalWidth,
                h: i.naturalHeight
            })).filter(i => i.w > 200 || i.h > 200 || i.src.includes('oai') || i.src.includes('blob'));
        }
    """)

    best_src = None
    for item in all_imgs_page:
        src = item.get("src", "")
        if any(d in src for d in IMAGE_DOMAINS):
            best_src = src
            break
        if src.startswith("blob:") and item.get("w", 0) > 200:
            best_src = src
            break

    if best_src is None:
        return None

    print(f"  Imagen encontrada: {best_src[:80]}...", flush=True)

    # Descargar via fetch dentro del contexto autenticado de la pagina
    try:
        b64 = gpt.evaluate(
            """async (url) => {
                const r = await fetch(url);
                const buf = await r.arrayBuffer();
                const arr = new Uint8Array(buf);
                let s = '';
                const chunk = 8192;
                for (let i = 0; i < arr.length; i += chunk) {
                    s += String.fromCharCode(...arr.subarray(i, i + chunk));
                }
                return btoa(s);
            }""",
            best_src,
        )
        return base64.b64decode(b64)
    except Exception as e:
        print(f"  Error descargando imagen: {e}", flush=True)
        return None


def wait_for_dalle_image(gpt, timeout_s=300) -> bytes | None:
    """
    Espera a que aparezca una imagen DALL-E en la pagina.
    Comprueba periodicamente los img tags buscando URLs de oaiusercontent.
    """
    waited = 0
    while waited < timeout_s:
        imgs = gpt.evaluate("""
            () => Array.from(document.querySelectorAll('img'))
                .map(i => ({src: i.src || '', w: i.naturalWidth, h: i.naturalHeight}))
                .filter(i => i.src.includes('oaiusercontent') || i.src.includes('files.openai')
                           || (i.src.startsWith('blob:') && i.w > 200))
        """)
        if imgs:
            src = imgs[0]["src"]
            print(f"  Imagen DALL-E detectada: {src[:80]}", flush=True)
            try:
                b64 = gpt.evaluate(
                    """async (url) => {
                        const r = await fetch(url);
                        const buf = await r.arrayBuffer();
                        const arr = new Uint8Array(buf);
                        let s = '';
                        for (let i = 0; i < arr.length; i += 8192) {
                            s += String.fromCharCode(...arr.subarray(i, i + 8192));
                        }
                        return btoa(s);
                    }""",
                    src,
                )
                return base64.b64decode(b64)
            except Exception as e:
                print(f"  Error descargando: {e}", flush=True)

        gpt.wait_for_timeout(4000)
        waited += 4
    return None


def get_all_content_img_srcs(gpt):
    """Devuelve el set de URLs de imagenes de contenido en la pagina (no avatares)."""
    return set(gpt.evaluate("""
        () => Array.from(document.querySelectorAll('img'))
            .map(i => i.src)
            .filter(s => s.includes('estuary') || s.includes('oaiusercontent')
                      || s.includes('files.openai'))
    """))


def download_img_src(gpt, src: str) -> bytes | None:
    try:
        b64 = gpt.evaluate(
            """async (url) => {
                const r = await fetch(url);
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const buf = await r.arrayBuffer();
                const arr = new Uint8Array(buf);
                let s = '';
                for (let i = 0; i < arr.length; i += 8192) {
                    s += String.fromCharCode(...arr.subarray(i, i + 8192));
                }
                return btoa(s);
            }""",
            src,
        )
        return base64.b64decode(b64)
    except Exception as e:
        print(f"  Error descargando {src[:60]}: {e}", flush=True)
        return None


def process_image(gpt, ctx, image_path: Path) -> bytes | None:
    navigate_to_new_project_chat(gpt)

    before_count = stable_assistant_count(gpt)

    # PASO 1: subir imagen + pedir analisis + prompt DALL-E
    upload_image(gpt, image_path)
    gpt.wait_for_timeout(1000)
    # Snapshot DESPUES de subir (incluye la imagen subida como baseline)
    imgs_after_upload = get_all_content_img_srcs(gpt)

    send_text(gpt, ctx, PROMPT_STEP1)
    print(f"  [Paso 1] Esperando analisis...", flush=True)
    wait_for_new_message(gpt, before_count, timeout_s=120)
    print(f"  [Paso 1] Analisis recibido.", flush=True)
    gpt.wait_for_timeout(1500)

    # Snapshot tras analisis (captura la imagen subida que puede aparecer en Step1)
    imgs_after_step1 = get_all_content_img_srcs(gpt)

    # PASO 2: pedir generacion
    before_count2 = stable_assistant_count(gpt)
    send_text(gpt, ctx, PROMPT_STEP2)
    print(f"  [Paso 2] Esperando imagen DALL-E (hasta 5 min)...", flush=True)

    # Esperar mensaje de respuesta inicial
    try:
        wait_for_new_message(gpt, before_count2, timeout_s=60)
    except TimeoutError:
        pass  # Puede que la imagen tarde en aparecer el mensaje

    # Esperar imagen real comparando contra el snapshot post-Step1
    waited = 0
    max_wait = 270  # 4.5 min
    while waited < max_wait:
        imgs_now = get_all_content_img_srcs(gpt)
        new_imgs = imgs_now - imgs_after_step1
        if new_imgs:
            # Tomar la imagen de mayor resolucion (la generada, no thumbnails)
            best = None
            best_size = 0
            for src in new_imgs:
                try:
                    dims = gpt.evaluate(
                        """(url) => {
                            const img = Array.from(document.querySelectorAll('img')).find(i => i.src === url);
                            return img ? {w: img.naturalWidth, h: img.naturalHeight} : {w: 0, h: 0};
                        }""",
                        src,
                    )
                    size = dims.get("w", 0) * dims.get("h", 0)
                    if size > best_size:
                        best_size = size
                        best = src
                except Exception:
                    best = src

            if best:
                print(f"  Nueva imagen DALL-E: {best[:80]}", flush=True)
                img_bytes = download_img_src(gpt, best)
                if img_bytes:
                    return img_bytes

        gpt.wait_for_timeout(5000)
        waited += 5

    print("  Timeout esperando imagen DALL-E.", flush=True)
    return None


def main():
    if len(sys.argv) > 1:
        paths = [Path(a) for a in sys.argv[1:]]
    else:
        paths = [IMAGES_DIR / name for name in ORIGINALS]

    to_process = []
    for p in paths:
        v3 = p.parent / f"{p.stem}_v3.png"
        if v3.exists():
            print(f"[SKIP] {p.name} ya tiene _v3", flush=True)
        elif not p.exists():
            print(f"[SKIP] {p.name} no existe", flush=True)
        else:
            to_process.append(p)

    if not to_process:
        print("Nada que procesar.")
        return

    print(f"Procesando {len(to_process)} imagen(es) en proyecto MCP - RRSS Autora Demo...\n", flush=True)

    with sync_playwright() as playwright:
        b = playwright.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        ctx = b.contexts[0]
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        gpt = find_chatgpt_page(b)
        gpt.bring_to_front()

        for img_path in to_process:
            out_path = img_path.parent / f"{img_path.stem}_v3.png"
            print(f"\n=== {img_path.name} ===", flush=True)
            try:
                img_bytes = process_image(gpt, ctx, img_path)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
                continue

            if img_bytes:
                out_path.write_bytes(img_bytes)
                print(f"  GUARDADO: {out_path.name} ({len(img_bytes)//1024} KB)", flush=True)
            else:
                print(f"  No se capturo imagen. Revisa la pestana de Edge manualmente.", flush=True)

            # Pausa entre imagenes
            gpt.wait_for_timeout(4000)

    print("\nFIN.", flush=True)


if __name__ == "__main__":
    main()
