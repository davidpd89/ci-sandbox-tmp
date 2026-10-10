"""
Captura las 4 imágenes de Flow haciendo screenshot recortado del área central de cada preview.
Luego las convierte a clips de vídeo Ken Burns 8s con ffmpeg.
"""
import sys, io, subprocess
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright
from PIL import Image

CDP_URL = "http://127.0.0.1:9223"
PROJECT_URL = "https://labs.google/fx/es/tools/flow/project/df4adbe8-1c2c-4578-b3b8-527985ec3850"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo")
IMGS_DIR = OUT_DIR / "images"
CLIPS_DIR = OUT_DIR / "clips"
IMGS_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

THUMBS = [
    (356, 276, "img1_kindle_nightstand"),
    (598, 276, "img2_person_reading"),
    (838, 276, "img3_bookshelf"),
    (1080, 276, "img4_kindle_closeup"),
]

def get_viewport(flow):
    return flow.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")

def capture_preview_image(flow, thumb_x, thumb_y, name: str) -> Path:
    out = IMGS_DIR / f"{name}.png"
    if out.exists() and out.stat().st_size > 50000:
        print(f"  {name}: ya existe")
        return out

    flow.mouse.click(thumb_x, thumb_y)
    flow.wait_for_timeout(2500)

    vp = get_viewport(flow)
    print(f"  Viewport: {vp['w']}x{vp['h']}")

    # El panel derecho ocupa ~350px, panel izquierdo ~75px, barra sup ~35px, barra inf ~65px
    clip = {
        "x": 75,
        "y": 35,
        "width": vp['w'] - 75 - 350,
        "height": vp['h'] - 35 - 65,
    }
    print(f"  Clip area: {clip}")
    flow.screenshot(path=str(out), clip=clip)

    # Verificar que se capturó algo
    with Image.open(out) as img:
        print(f"  {name}: {img.size[0]}x{img.size[1]}px {out.stat().st_size//1024}KB")

    # Volver al proyecto
    try:
        back = flow.locator("button:has-text('Atrás')").first
        if back.is_visible(timeout=2000):
            back.click()
            flow.wait_for_timeout(1500)
    except Exception:
        flow.keyboard.press("Escape")
        flow.wait_for_timeout(1000)

    return out

def image_to_ken_burns_clip(img_path: Path, clip_path: Path, duration=8):
    """Convierte imagen a vídeo 9:16 con Ken Burns (zoom lento) usando ffmpeg."""
    if clip_path.exists() and clip_path.stat().st_size > 100000:
        print(f"  {clip_path.name}: ya existe")
        return True

    # Primero redimensionar imagen a 1080x1920 con PIL para asegurar 9:16
    resized = IMGS_DIR / f"{img_path.stem}_1080.jpg"
    with Image.open(img_path) as img:
        # Crop center to 9:16 if needed
        w, h = img.size
        target_ratio = 9/16
        current_ratio = w/h
        if current_ratio > target_ratio:
            # Demasiado ancho — crop lateral
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        elif current_ratio < target_ratio:
            # Demasiado alto — crop vertical
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))
        img = img.resize((1080, 1920), Image.LANCZOS)
        img.save(resized, "JPEG", quality=92)
        print(f"  Imagen resized: {img.size}")

    # ffmpeg Ken Burns: zoom lento desde 1.0 a 1.15
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(resized),
        "-vf", f"zoompan=z='min(zoom+0.0009,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30:d={duration*30}",
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        str(clip_path)
    ]
    print(f"  ffmpeg Ken Burns → {clip_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  ffmpeg error: {result.stderr[-300:]}")
        return False
    print(f"  {clip_path.name}: {clip_path.stat().st_size//1024}KB")
    return True

def run():
    # Fase 1: capturar imágenes
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        b.contexts[0].grant_permissions(["clipboard-read", "clipboard-write"])
        all_pages = [pg for c in b.contexts for pg in c.pages]
        flow = next(pg for pg in all_pages if "labs.google" in pg.url)
        flow.bring_to_front()

        if PROJECT_URL.rstrip("/") not in flow.url.rstrip("/"):
            flow.goto(PROJECT_URL)
            flow.wait_for_load_state("networkidle", timeout=20000)
        flow.wait_for_timeout(2000)

        for x, y, name in THUMBS:
            print(f"\nCapturando {name}...")
            capture_preview_image(flow, x, y, name)

    # Fase 2: convertir a clips Ken Burns
    print("\n=== Convirtiendo imágenes a clips de vídeo ===")
    for _, _, name in THUMBS:
        img = IMGS_DIR / f"{name}.png"
        clip = CLIPS_DIR / f"{name}.mp4"
        if img.exists():
            image_to_ken_burns_clip(img, clip, duration=8)

    print("\n=== RESUMEN ===")
    for _, _, name in THUMBS:
        img = IMGS_DIR / f"{name}.png"
        clip = CLIPS_DIR / f"{name}.mp4"
        print(f"  {name}: img={'✓' if img.exists() else '✗'} clip={'✓' if clip.exists() and clip.stat().st_size > 100000 else '✗'}")

if __name__ == "__main__":
    run()
