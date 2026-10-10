"""
Genera el contenido de las 5 piezas Jul 23-25 usando Meta AI via CDP.

Workflow por pieza:
  - Reel: subir imagen _v3 → Meta AI anima → download mp4 → render_reel_v6_paced.py + musica
  - Carrusel escritores: prompt x5 (imagen por escritor) → download imagenes
  - Carrusel dualidad: subir imagen _v3 → Meta AI genera 4 variantes → carousel

Referencia: protocolo en 09_Usados_video/meta/protocolo.md
"""
import sys, io, subprocess, base64, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout

from playwright.sync_api import sync_playwright
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
CDP = "http://127.0.0.1:9223"
IMAGES = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Imagenes david")
META_PIEZAS = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas")
REELS_OUT = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Reels_listos_v2")
CAROUSEL_OUT = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Carruseles_listos_v2")
REEL_SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")

REELS_OUT.mkdir(exist_ok=True)
CAROUSEL_OUT.mkdir(exist_ok=True)

MUSIC = {
    "determined":    r"C:\GIT\RRSS_DavidPorto\08_Usados_foto\perplexity\piezas\07-disciplina-escritura\music_determined.mp3",
    "forest":        r"C:\GIT\RRSS_DavidPorto\tools\reel_template\clips_post3\music_foresttreasure.mp3",
    "tears":         r"C:\GIT\RRSS_DavidPorto\tools\reel_template\clips_post4\music_tearsofjoy.mp3",
    "ventana":       r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\03-cerrar-libro\music_ventana.mp3",
    "gato":          r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\04-gato-capitulo\music_gato.mp3",
}


# ─────────────────────────────────────────────────────────────
# Funciones base
# ─────────────────────────────────────────────────────────────

def get_or_create_meta_page(b):
    pages = [pg for c in b.contexts for pg in c.pages]
    meta = next((pg for pg in pages if "meta.ai" in pg.url), None)
    if not meta:
        meta = b.contexts[0].new_page()
        meta.goto("https://www.meta.ai/")
        meta.wait_for_load_state("networkidle", timeout=25000)
        meta.wait_for_timeout(2000)
    return meta


def new_meta_chat(page):
    """Abre un chat nuevo en Meta AI para no contaminar el anterior."""
    page.goto("https://www.meta.ai/")
    page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(2000)


def focus_composer(page):
    """Localiza y enfoca el composer de Meta AI."""
    el = page.evaluate("""() => {
        const els = document.querySelectorAll("div[contenteditable='true'], textarea");
        for (const e of els) {
            const r = e.getBoundingClientRect();
            if (r.width > 100 && r.y > 100) return {x: r.x + 10, y: r.y + 10};
        }
        return null;
    }""")
    if el:
        page.mouse.click(el["x"], el["y"])
    else:
        page.locator("div[contenteditable='true']").first.click(timeout=5000)
    page.wait_for_timeout(300)


def send_text(page, ctx, text):
    """Envía texto via portapapeles (fix bug de pérdida de caracteres)."""
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    focus_composer(page)
    page.evaluate("(t) => navigator.clipboard.writeText(t)", text)
    page.keyboard.press("Control+V")
    page.wait_for_timeout(400)
    # Verificar que el texto llegó
    actual = page.evaluate("""() => {
        const el = document.activeElement;
        return el ? (el.innerText || el.value || '') : '';
    }""")
    if not actual.strip():
        # Fallback: keyboard.type
        focus_composer(page)
        page.keyboard.type(text[:200], delay=5)
    page.wait_for_timeout(300)


def upload_image(page, img_path: Path):
    """Sube imagen a Meta AI via file chooser."""
    print(f"  Subiendo {img_path.name}...")
    # Buscar botón + o input file
    try:
        with page.expect_file_chooser(timeout=8000) as fc_info:
            # Intentar click en botón de adjuntar
            btn = page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                for (const b of btns) {
                    if ((b.textContent||'').includes('+') || b.querySelector('svg') ||
                        (b.getAttribute('aria-label')||'').toLowerCase().includes('attach')) {
                        const r = b.getBoundingClientRect();
                        if (r.width > 0 && r.y > 400) return {x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                }
                return null;
            }""")
            if btn:
                page.mouse.click(btn["x"], btn["y"])
            else:
                # Usar input file directamente
                inp = page.locator("input[type='file']").first
                fc_info.value.set_files(str(img_path))
                return
        fc = fc_info.value
        fc.set_files(str(img_path))
        print(f"  Imagen subida via file chooser")
    except Exception as e:
        print(f"  Error file chooser: {e}")
        # Intentar input file directo
        try:
            page.locator("input[type='file']").first.set_input_files(str(img_path))
            print(f"  Imagen subida via input file")
        except Exception as e2:
            print(f"  Error input file: {e2}")
    page.wait_for_timeout(2000)


def wait_for_image(page, timeout_s=90):
    """Espera y descarga la última imagen generada por Meta AI."""
    print(f"  Esperando imagen Meta AI (hasta {timeout_s}s)...")
    waited = 0
    step = 3
    while waited < timeout_s:
        imgs = page.evaluate("""
            () => Array.from(document.querySelectorAll('img'))
                .filter(img => img.naturalWidth > 300 && img.naturalHeight > 300
                    && (img.src.includes('fbcdn') || img.src.includes('scontent') || img.src.includes('meta.ai')))
                .map(img => img.src)
        """)
        if imgs:
            return imgs[-1]
        page.wait_for_timeout(step * 1000)
        waited += step
    print("  TIMEOUT esperando imagen")
    return None


def wait_for_video(page, timeout_s=180):
    """Espera y obtiene la URL del último vídeo generado por Meta AI."""
    print(f"  Esperando vídeo Meta AI (hasta {timeout_s}s)...")
    waited = 0
    step = 5
    while waited < timeout_s:
        vids = page.evaluate("""
            () => Array.from(document.querySelectorAll('video'))
                .filter(v => v.src && v.src.length > 20 && !v.src.startsWith('blob:'))
                .map(v => v.src)
        """)
        if not vids:
            # También buscar en source elements
            vids = page.evaluate("""
                () => Array.from(document.querySelectorAll('video source'))
                    .filter(s => s.src && s.src.length > 20)
                    .map(s => s.src)
            """)
        if vids:
            return vids[-1]
        page.wait_for_timeout(step * 1000)
        waited += step
    print("  TIMEOUT esperando vídeo")
    return None


def download_url(page, url: str, out: Path) -> bool:
    """Descarga una URL (imagen o vídeo) via fetch en el contexto del browser."""
    try:
        b64 = page.evaluate("""
            async (url) => {
                const r = await fetch(url);
                const buf = await r.arrayBuffer();
                const b = new Uint8Array(buf);
                let s = ''; const C = 8192;
                for (let i = 0; i < b.length; i += C)
                    s += String.fromCharCode(...b.subarray(i, i + C));
                return btoa(s);
            }
        """, url)
        out.write_bytes(base64.b64decode(b64))
        print(f"  Descargado: {out.name} ({out.stat().st_size // 1024}KB)")
        return True
    except Exception as e:
        print(f"  Error descargando {url[:60]}: {e}")
        return False


def render_reel(clip_path: Path, texts: list, music: str, out_path: Path, seg=2.0):
    """Renderiza reel con render_reel_v6_paced.py."""
    import os
    cmd = [
        "python", str(REEL_SCRIPT),
        str(out_path), music,
        "--clips", str(clip_path),
        "--seg", str(seg),
        "--texts",
    ] + texts
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    print(f"  Renderizando {out_path.name}...")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env,
                       cwd=str(REEL_SCRIPT.parent))
    if r.returncode != 0:
        print(f"  Render ERROR:\n{r.stderr[-400:]}")
        return False
    size = out_path.stat().st_size // 1024 if out_path.exists() else 0
    print(f"  Reel OK: {out_path.name} ({size}KB)")
    return True


def extract_last_frame(video: Path, out: Path):
    cmd = [FF, "-y", "-sseof", "-0.15", "-i", str(video), "-frames:v", "1", str(out)]
    r = subprocess.run(cmd, capture_output=True, timeout=30)
    return r.returncode == 0 and out.exists()


# ─────────────────────────────────────────────────────────────
# PIEZA 27 — Jul 23 — REEL "Entro solo a mirar" (bookstore)
# Fuente: 1000106609_v3.png (editorial bookstore B&W)
# Meta AI: animar la imagen con movimiento de cámara por librería
# Música: determined (no usada aún)
# ─────────────────────────────────────────────────────────────

PIEZA27_DIR = META_PIEZAS / "27-entro-solo-mirar"
PIEZA27_DIR.mkdir(parents=True, exist_ok=True)

P27_ANIM_PROMPT = (
    "Genera una animacion de 10 segundos de duracion. "
    "Anima esta imagen de una libreria elegante. "
    "Movimiento de camara lento que recorre las estanterias de libros, "
    "como si alguien entrara a explorar sin prisa. "
    "Luz natural suave, ambiente tranquilo. "
    "Sin cambiar la composicion. Sin texto generado. Sin personas nuevas."
)

P27_TEXTS = [
    "Entro solo a mirar.",
    "Esta vez de verdad.",
    "Veinte minutos despues...",
    "Tres libros.",
    "Cara de culpable.",
    "Cero arrepentimiento.",
]

# ─────────────────────────────────────────────────────────────
# PIEZA 28 — Jul 24 manana — CARRUSEL escritores reales
# Meta AI: genera imagen por escritor en su era/estetica
# Luego PIL pone la cita encima con contraste
# ─────────────────────────────────────────────────────────────

PIEZA28_DIR = META_PIEZAS / "28-citas-escritores"
PIEZA28_DIR.mkdir(parents=True, exist_ok=True)

WRITERS = [
    {
        "name": "kafka",
        "prompt": (
            "Ilustracion editorial de Franz Kafka, escritor checo de principios del siglo XX. "
            "Ambiente: Praga 1915, habitacion austera, luz de lampara de noche, papeleo sobre la mesa. "
            "Estilo litografia o grabado en negro con toques sepia. "
            "Sin texto en la imagen. Sin libros con titulo visible. Vertical 9:16."
        ),
        "quote": '"Un libro debe ser el hacha que rompa el mar helado dentro de nosotros."',
        "author_line": "— Franz Kafka",
    },
    {
        "name": "borges",
        "prompt": (
            "Ilustracion editorial de Jorge Luis Borges, escritor argentino del siglo XX. "
            "Ambiente: Buenos Aires 1960, biblioteca laberintica, estanterias infinitas de libros, "
            "luz calida de lampara, aire literario y misterioso. "
            "Estilo acuarela detallada con tinta china. "
            "Sin texto en la imagen. Vertical 9:16."
        ),
        "quote": '"Que otros se jacten de las paginas que han escrito;\na mi me enorgullecen las que he leido."',
        "author_line": "— Jorge Luis Borges",
    },
    {
        "name": "woolf",
        "prompt": (
            "Ilustracion editorial de Virginia Woolf, escritora inglesa de principios del siglo XX. "
            "Ambiente: Londres 1920s, jardin con luz suave de tarde, mesa de escritura junto a la ventana. "
            "Estilo ilustracion art nouveau con paleta verde y dorado. "
            "Sin texto en la imagen. Vertical 9:16."
        ),
        "quote": '"Uno no puede pensar bien, amar bien, dormir bien,\nsi no ha comido bien. Y leer bien."',
        "author_line": "— Virginia Woolf",
    },
    {
        "name": "cortazar",
        "prompt": (
            "Ilustracion editorial de Julio Cortazar, escritor argentino. "
            "Ambiente: Paris 1970s, cafe literario, humo de cigarro, libros sobre la mesa, "
            "actitud bohemia y pensativa. "
            "Estilo dibujo de linea con color plano, influencia del surrealismo. "
            "Sin texto en la imagen. Vertical 9:16."
        ),
        "quote": '"Andaba por la vida como si nada, pero por dentro habia un lector\nque lo veia todo diferente."',
        "author_line": "— Julio Cortazar",
    },
    {
        "name": "dostoievski",
        "prompt": (
            "Ilustracion editorial de Fyodor Dostoievski, escritor ruso del siglo XIX. "
            "Ambiente: San Petersburgo invierno 1870, habitacion fria con chimenea, "
            "escribiendo a la luz de una vela, expresion intensa y apasionada. "
            "Estilo grabado al aguatinta, tonos oscuros con luz dramatica. "
            "Sin texto en la imagen. Vertical 9:16."
        ),
        "quote": '"El hombre es un misterio. Hay que descifrarlo,\ny si pasas toda la vida descifrando,\nno digas que has perdido el tiempo."',
        "author_line": "— Fiodor Dostoievski",
    },
]

# ─────────────────────────────────────────────────────────────
# PIEZA 29 — Jul 24 tarde — REEL humor lector
# Fuente: 1000106601_v3.png
# Meta AI: animar con movimiento natural de lectura/humor
# Musica: forest (no usada aun)
# ─────────────────────────────────────────────────────────────

PIEZA29_DIR = META_PIEZAS / "29-comprar-vs-leer"
PIEZA29_DIR.mkdir(parents=True, exist_ok=True)

P29_ANIM_PROMPT = (
    "Genera una animacion de 10 segundos de duracion. "
    "Anima esta imagen. "
    "Movimiento sutil y natural: la persona mira el libro, lo levanta ligeramente, "
    "sonrie de forma complice como reconociendo algo familiar. "
    "Sin cambiar la composicion ni el fondo. Sin texto generado. Sin nuevas personas."
)

P29_TEXTS = [
    "Comprar libros.",
    "Y leer libros.",
    "Son aficiones distintas.",
    "Una para el presente.",
    "Otra para el yo futuro",
    "que nunca llega.",
]

# ─────────────────────────────────────────────────────────────
# PIEZA 30 — Jul 25 manana — CARRUSEL dualidad lectora
# Fuente: 1000106606_v3.png (dos mujeres/dualidad)
# Meta AI: 4 variantes de la misma imagen en estilos distintos
# ─────────────────────────────────────────────────────────────

PIEZA30_DIR = META_PIEZAS / "30-dualidad-lectora"
PIEZA30_DIR.mkdir(parents=True, exist_ok=True)

P30_VARIANTS = [
    "Misma composicion que la imagen original. Paleta calida y dorada, luz de tarde de verano.",
    "Misma composicion que la imagen original. Paleta fria, azul noche, ambiente tranquilo.",
    "Misma composicion que la imagen original. Estilo ilustracion editorial lineal, minimalista.",
    "Misma composicion que la imagen original. Blanco y negro de alto contraste, estilo fotografico.",
]

# ─────────────────────────────────────────────────────────────
# PIEZA 31 — Jul 25 tarde — REEL emocional
# Fuente: 1000106610_v3.png (acantilado/amor suave)
# Meta AI: animar con movimiento de viento, luz cambiante
# Musica: tears_of_joy (no usada aun)
# ─────────────────────────────────────────────────────────────

PIEZA31_DIR = META_PIEZAS / "31-libros-que-encuentran"
PIEZA31_DIR.mkdir(parents=True, exist_ok=True)

P31_ANIM_PROMPT = (
    "Genera una animacion de 10 segundos de duracion. "
    "Anima esta imagen suave e ilustrada. "
    "Movimiento muy lento: el pelo se mueve con la brisa, la luz cambia suavemente. "
    "Atmosfera tranquila y emotiva. Sin cambiar composicion ni colores. "
    "Sin texto generado. Sin elementos nuevos."
)

P31_TEXTS = [
    "Hay libros que te encuentran.",
    "No los eliges tu.",
    "Aparecen cuando algo en ti",
    "necesita ser dicho",
    "por alguien que no eres tu.",
    "Ya no puedes volver",
    "al que eras antes.",
]


# ─────────────────────────────────────────────────────────────
# EJECUCION
# ─────────────────────────────────────────────────────────────

print("=== META AI GENERATOR — Piezas 27-31 ===")
print("Conectando a Edge CDP...")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP, timeout=15000)
    ctx = b.contexts[0]
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    meta = get_or_create_meta_page(b)
    meta.bring_to_front()
    print("Conectado a Meta AI.")

    # ─── PIEZA 27: Reel bookstore ───
    print("\n--- PIEZA 27: Reel bookstore (Jul 23) ---")
    p27_clip = PIEZA27_DIR / "clip_meta.mp4"
    p27_reel = REELS_OUT / "reel27_bookstore.mp4"

    if not p27_clip.exists() or p27_clip.stat().st_size < 50000:
        new_meta_chat(meta)
        upload_image(meta, IMAGES / "1000106609_v3.png")
        send_text(meta, ctx, P27_ANIM_PROMPT)
        meta.keyboard.press("Enter")
        vid_url = wait_for_video(meta, timeout_s=180)
        if vid_url:
            download_url(meta, vid_url, p27_clip)
        else:
            print("  No se pudo obtener el video. Usando imagen como fallback...")
    else:
        print(f"  Clip ya existe: {p27_clip.stat().st_size//1024}KB")

    if p27_clip.exists() and p27_clip.stat().st_size > 10000:
        render_reel(p27_clip, P27_TEXTS, MUSIC["determined"], p27_reel, seg=2.0)
    else:
        print("  Sin clip — reel no renderizado")

    meta.wait_for_timeout(3000)

    # ─── PIEZA 28: Carrusel escritores (Meta AI imagenes) ───
    print("\n--- PIEZA 28: Carrusel escritores (Jul 24 manana) ---")
    for w in WRITERS:
        out_img = PIEZA28_DIR / f"img_{w['name']}.png"
        if out_img.exists() and out_img.stat().st_size > 30000:
            print(f"  {w['name']}: ya existe ({out_img.stat().st_size//1024}KB)")
            continue
        new_meta_chat(meta)
        send_text(meta, ctx, w["prompt"])
        meta.keyboard.press("Enter")
        img_url = wait_for_image(meta, timeout_s=90)
        if img_url:
            download_url(meta, img_url, out_img)
        else:
            print(f"  {w['name']}: timeout sin imagen")
        meta.wait_for_timeout(3000)

    # ─── PIEZA 29: Reel humor lector ───
    print("\n--- PIEZA 29: Reel humor lector (Jul 24 tarde) ---")
    p29_clip = PIEZA29_DIR / "clip_meta.mp4"
    p29_reel = REELS_OUT / "reel29_humor.mp4"

    if not p29_clip.exists() or p29_clip.stat().st_size < 50000:
        new_meta_chat(meta)
        upload_image(meta, IMAGES / "1000106601_v3.png")
        send_text(meta, ctx, P29_ANIM_PROMPT)
        meta.keyboard.press("Enter")
        vid_url = wait_for_video(meta, timeout_s=180)
        if vid_url:
            download_url(meta, vid_url, p29_clip)
    else:
        print(f"  Clip ya existe: {p29_clip.stat().st_size//1024}KB")

    if p29_clip.exists() and p29_clip.stat().st_size > 10000:
        render_reel(p29_clip, P29_TEXTS, MUSIC["forest"], p29_reel, seg=2.2)

    meta.wait_for_timeout(3000)

    # ─── PIEZA 30: Carrusel dualidad (variantes) ───
    print("\n--- PIEZA 30: Carrusel dualidad (Jul 25 manana) ---")
    for i, variant_prompt in enumerate(P30_VARIANTS, 1):
        out_img = PIEZA30_DIR / f"variant_{i:02d}.png"
        if out_img.exists() and out_img.stat().st_size > 30000:
            print(f"  variant_{i}: ya existe")
            continue
        new_meta_chat(meta)
        upload_image(meta, IMAGES / "1000106606_v3.png")
        send_text(meta, ctx, variant_prompt)
        meta.keyboard.press("Enter")
        img_url = wait_for_image(meta, timeout_s=90)
        if img_url:
            download_url(meta, img_url, out_img)
        meta.wait_for_timeout(3000)

    # ─── PIEZA 31: Reel emocional ───
    print("\n--- PIEZA 31: Reel emocional (Jul 25 tarde) ---")
    p31_clip = PIEZA31_DIR / "clip_meta.mp4"
    p31_reel = REELS_OUT / "reel31_emocional.mp4"

    if not p31_clip.exists() or p31_clip.stat().st_size < 50000:
        new_meta_chat(meta)
        upload_image(meta, IMAGES / "1000106610_v3.png")
        send_text(meta, ctx, P31_ANIM_PROMPT)
        meta.keyboard.press("Enter")
        vid_url = wait_for_video(meta, timeout_s=180)
        if vid_url:
            download_url(meta, vid_url, p31_clip)
    else:
        print(f"  Clip ya existe: {p31_clip.stat().st_size//1024}KB")

    if p31_clip.exists() and p31_clip.stat().st_size > 10000:
        render_reel(p31_clip, P31_TEXTS, MUSIC["tears"], p31_reel, seg=2.3)

    print("\n=== FIN GENERACION META AI ===")
    print("\nResultados:")
    for f in REELS_OUT.glob("*.mp4"):
        print(f"  Reel: {f.name} ({f.stat().st_size//1024}KB)")
    for f in PIEZA28_DIR.glob("*.png"):
        print(f"  Escritor: {f.name} ({f.stat().st_size//1024}KB)")
    for f in PIEZA30_DIR.glob("*.png"):
        print(f"  Dualidad: {f.name} ({f.stat().st_size//1024}KB)")
