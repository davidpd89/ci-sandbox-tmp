"""
Genera DP-F0-073 "Enemies to lovers" usando Meta AI via CDP Edge (puerto 9223).
4 imágenes → 4 clips Ken Burns 8s → reel 32s, 5 líneas × ~6s = 30s.
"""
import sys, io, subprocess, base64
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\18-enemies-to-lovers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 4 escenas para la narrativa enemies to lovers
PROMPTS = [
    "Two young people standing in a cozy bookstore, far apart in the same aisle, each reading a different book, not acknowledging the other. Tense body language, arms slightly crossed. Warm ambient light. Realistic, cinematic, 9:16 vertical, no text.",
    "Close-up: two hands reaching for the same book on a wooden library shelf at the same time. Fingers almost touching. The moment frozen. Shallow depth of field. Warm library lighting. 9:16 vertical, photorealistic, cinematic.",
    "A young woman looking away from someone off-screen, biting her lip slightly, trying to suppress a smile but failing. Library bookshelf behind her. Natural light. 9:16 vertical, photorealistic, candid emotion.",
    "Wide shot of a bookstore aisle. Two people walking in opposite directions, backs to each other. Each one glances back over their shoulder at the same moment without the other noticing. Warm lighting, cinematic, 9:16 vertical."
]

TEXTS = [
    "Si se odian demasiado, ya sospecho.",
    "Discuten. Se miran. Miran para otro lado.",
    "Una herida, una venda, un momento cerrado.",
    "Y yo ya he comprado el arroz.",
    "¿Qué enemies to lovers te tuvo así?",
]

def find_meta_page(b):
    for pg in [x for c in b.contexts for x in c.pages]:
        if "meta.ai" in pg.url:
            return pg
    return None

def open_meta(ctx):
    pg = ctx.new_page()
    pg.goto("https://www.meta.ai/")
    pg.wait_for_load_state("networkidle", timeout=20000)
    pg.wait_for_timeout(2000)
    return pg

def generate_image(page, prompt, out_path: Path):
    """Genera una imagen en Meta AI y la descarga."""
    if out_path.exists() and out_path.stat().st_size > 50000:
        print(f"  {out_path.name}: ya existe")
        return True

    # Buscar el textarea
    ta = page.locator("textarea, [contenteditable='true'], [role='textbox']").first
    try:
        ta.click(timeout=3000)
    except Exception:
        page.evaluate("() => { const t = document.querySelector('textarea'); if(t) t.focus(); }")

    page.wait_for_timeout(300)
    page.keyboard.press("Control+A")
    page.evaluate("(t) => navigator.clipboard.writeText(t)", prompt)
    page.keyboard.press("Control+V")
    page.wait_for_timeout(500)
    page.keyboard.press("Enter")
    print(f"  Prompt enviado, esperando imagen...")
    page.wait_for_timeout(30000)  # Esperar 30s para imagen

    # Buscar la imagen generada
    for _ in range(30):
        imgs = page.evaluate("""
            () => Array.from(document.querySelectorAll('img[src*="cdn"]'))
                .filter(img => img.naturalWidth > 200 && img.naturalHeight > 200)
                .map(img => img.src)
        """)
        if imgs:
            src = imgs[-1]  # La más reciente
            print(f"  Imagen encontrada: {src[:60]}")
            # Descargar
            b64 = page.evaluate("""
                async (url) => {
                    const r = await fetch(url);
                    const buf = await r.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    let s = ''; const C = 8192;
                    for (let i = 0; i < bytes.length; i += C)
                        s += String.fromCharCode(...bytes.subarray(i, i + C));
                    return btoa(s);
                }
            """, src)
            out_path.write_bytes(base64.b64decode(b64))
            print(f"  Guardada: {out_path.name} ({out_path.stat().st_size//1024}KB)")
            return True
        page.wait_for_timeout(5000)

    print(f"  [WARN] No se generó imagen")
    return False

def image_to_kenburns_clip(img_path, clip_path, duration=8):
    if clip_path.exists() and clip_path.stat().st_size > 200000:
        print(f"  {clip_path.name}: ya existe")
        return True

    fps = 30
    frames = duration * fps
    vf = (f"scale=1080:1920:force_original_aspect_ratio=decrease,"
          f"pad=1080:1920:-1:-1,"
          f"zoompan=z='min(zoom+0.0005,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}:d={frames}")
    cmd = [FF, "-y", "-loop", "1", "-i", str(img_path), "-vf", vf,
           "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-preset", "fast", "-crf", "20", str(clip_path)]
    r = subprocess.run(cmd, capture_output=True, timeout=180)
    if r.returncode == 0:
        print(f"  {clip_path.name}: ✓ {clip_path.stat().st_size//1024}KB")
        return True
    print(f"  ffmpeg error: {r.stderr.decode()[-200:]}")
    return False

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    b.contexts[0].grant_permissions(["clipboard-read", "clipboard-write"])

    # Usar Meta AI
    meta = find_meta_page(b)
    if not meta:
        print("Abriendo Meta AI...")
        meta = open_meta(b.contexts[0])
    meta.bring_to_front()
    print(f"Meta AI: {meta.url}")

    # === Fase 1: Generar 4 imágenes ===
    print("\n=== Generando 4 imágenes con Meta AI ===")
    img_dir = OUT_DIR / "images"
    img_dir.mkdir(exist_ok=True)

    generated_images = []
    for i, prompt in enumerate(PROMPTS, 1):
        out_img = img_dir / f"scene{i}.jpg"
        print(f"\nEscena {i}/{len(PROMPTS)}: {prompt[:60]}...")
        ok = generate_image(meta, prompt, out_img)
        if ok:
            generated_images.append(out_img)

    print(f"\nImágenes generadas: {len(generated_images)}/{len(PROMPTS)}")

    # === Fase 2: Ken Burns clips ===
    print("\n=== Convirtiendo a clips Ken Burns ===")
    clips_dir = OUT_DIR / "clips"
    clips_dir.mkdir(exist_ok=True)

    clips = []
    for i, img_path in enumerate(generated_images, 1):
        clip = clips_dir / f"clip{i}.mp4"
        ok = image_to_kenburns_clip(img_path, clip)
        if ok:
            clips.append(clip)

    print(f"\nClips listos: {len(clips)}")

    if len(clips) < 2:
        print("Insuficientes clips. Abortando render.")
        sys.exit(1)

    # === Fase 3: Render con texto ===
    print("\n=== Renderizando reel final ===")
    SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")
    MUSIC = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\tt-viaje\music.mp3")
    if not MUSIC.exists():
        # Buscar alternativa
        for mp3 in Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video").glob("**/*.mp3"):
            if "silent_descent" not in str(mp3) and "ventana" not in str(mp3) and "sfx" not in str(mp3):
                MUSIC = mp3; break

    OUT_REEL = OUT_DIR / "reel_v1.mp4"
    n_clips = len(clips)
    n_texts = len(TEXTS)
    # Duración por texto: total_dur / n_texts, donde total_dur = n_clips × 8s
    total_sec = n_clips * 8
    seg = round(total_sec / n_texts, 1)
    print(f"  {n_clips} clips × 8s = {total_sec}s | {n_texts} textos | seg={seg}s/texto")

    cmd = ([sys.executable, str(SCRIPT), str(OUT_REEL), str(MUSIC)]
           + ["--clips"] + [str(c) for c in clips]
           + ["--texts"] + TEXTS
           + ["--seg", str(seg)])
    r2 = subprocess.run(cmd, capture_output=True, timeout=300)
    print(r2.stdout.decode("utf-8", errors="replace"))
    if r2.returncode == 0:
        print(f"✓ reel_v1.mp4 ({OUT_REEL.stat().st_size//1024//1024}MB)")
    else:
        print(f"ERROR render: {r2.stderr.decode()[-300:]}")
