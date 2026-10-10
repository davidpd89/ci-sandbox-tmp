"""
Genera 3 piezas con Meta AI usando REGLA CRÍTICA 2 (secuencia encadenada):
Beat 1 → último frame → Beat 2 → concatenar → render.
- DP-F0-081: "La leí veinte veces. La misma escena." (Jul 20 pieza 2)
- DP-F0-082: "Hay libros que no enseño." (Jul 21 pieza 2)
- DP-F0-083: "El protagonista, bien. El secundario, todo." (Jul 22 pieza 2)
"""
import sys, io, subprocess, base64, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
CDP = "http://127.0.0.1:9223"

PIECES = [
    {
        "slug": "23-misma-escena",
        "texts": ["La leí veinte veces.", "La misma escena.", "No me cansa.", "¿Cuál es la tuya?"],
        # Beat 1: imagen base → animación de lectora absorta pasando a la misma página
        "b1_img": "Young woman sitting in warm sunlit armchair at home, reading a paperback book, completely absorbed, no readable title, cozy room, natural afternoon light, realistic, 9:16 vertical",
        "b1_anim": "She slowly turns back several pages she already passed, reads the same passage again, slight smile of recognition, natural page-turning movement, warm light",
        # Beat 2: continúa desde el último fotograma, cierra los ojos un momento
        "b2_anim": "Continue exactly: she closes her eyes briefly as if savoring the words she just reread, then opens them slowly and looks at the page again with quiet satisfaction, no dialogue, natural movement",
        "music": r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\tt-viaje\music.mp3",
        "hashtags_ig": "#librosquereleo #lectoresreales #librosqueamo #cosasdelectores #comunidadlectora #instalibros #librosenespañol #booktok",
        "hashtags_tt": "#librosquereleo #cosasdelectores #booktok #librosenespañol #lectoresreales #lectores #parati",
    },
    {
        "slug": "24-libro-que-no-enseno",
        "texts": ["Hay libros que no enseño.", "No los presto.", "Los guardo.", "¿Tienes uno así?"],
        "b1_img": "Young woman at home with a bookshelf behind her, someone is walking toward her. She is holding a book she loves, starts to tuck it away behind another book before the person sees it. Subtle guilty smile. Realistic, 9:16 vertical, no readable titles",
        "b1_anim": "She quickly slides her favorite book behind others on the shelf as someone approaches, tries to look casual, natural quick motion",
        "b2_anim": "Continue exactly: the other person glances at the shelf and she gives an innocent shrug, then when they look away she sneaks a quick affectionate look back at where she hid the book, subtle humor",
        "music": r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\tt-personajes\music.mp3",
        "hashtags_ig": "#librosqueguardo #lectoresreales #cosasdelectores #libroslibroslibros #bookstagrammer #librosqueamo #instalibros #booktok",
        "hashtags_tt": "#librosqueguardo #lectoresreales #booktok #cosasdelectores #librosqueamo #instalibros #parati",
    },
    {
        "slug": "25-secundario-roba-novela",
        "texts": ["El protagonista, bien.", "El secundario, todo.", "Solo yo.", "¿A quién defiendes tú?"],
        "b1_img": "Young woman reading a fantasy paperback book, concentrated expression, afternoon light through window, cozy home setting, no readable title, realistic 9:16 vertical",
        "b1_anim": "She reads normally, then suddenly slows down at one passage, re-reads it, her expression changes from calm to deeply interested, leans slightly forward, natural reading body language",
        "b2_anim": "Continue exactly: she turns back to reread the same passage again, this time with a clear emotional investment, closes the book briefly to process it, then opens it right back to that page, subtle emotional reader reaction",
        "music": r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\04-gato-capitulo\music_gato.mp3",
        "hashtags_ig": "#personajessecundarios #bookstagrammer #comunidadlectora #lectoresunidos #librosqueamo #booktok #librosenespañol #cosasdelectores",
        "hashtags_tt": "#personajessecundarios #booktok #lectoresreales #librosenespañol #cosasdelectores #comunidadlectora #parati",
    },
]

def get_meta_page(b):
    pages = [pg for c in b.contexts for pg in c.pages]
    meta = next((pg for pg in pages if "meta.ai" in pg.url), None)
    if not meta:
        meta = b.contexts[0].new_page()
        meta.goto("https://www.meta.ai/")
        meta.wait_for_load_state("networkidle", timeout=20000)
    return meta

def send_and_get_image(page, prompt, out_path: Path):
    """Envía prompt a Meta AI y descarga la imagen generada."""
    if out_path.exists() and out_path.stat().st_size > 30000:
        print(f"    {out_path.name}: existe ({out_path.stat().st_size//1024}KB)")
        return True
    # Focus y enviar
    ta = page.locator("textarea, [contenteditable='true']").first
    try: ta.click(timeout=3000)
    except: page.evaluate("() => { const t = document.querySelector('textarea'); if(t) t.focus(); }")
    page.wait_for_timeout(300)
    page.keyboard.press("Control+A")
    page.evaluate("(t) => navigator.clipboard.writeText(t)", prompt)
    page.keyboard.press("Control+V")
    page.wait_for_timeout(500)
    page.keyboard.press("Enter")
    print(f"    Prompt enviado, esperando imagen...")
    page.wait_for_timeout(20000)
    # Buscar imagen
    for _ in range(40):
        imgs = page.evaluate("""
            () => Array.from(document.querySelectorAll('img[src*="fbcdn"], img[src*="scontent"]'))
                .filter(img => img.naturalWidth > 200 && img.naturalHeight > 200)
                .map(img => img.src)
        """)
        if imgs:
            src = imgs[-1]
            b64 = page.evaluate("""
                async (url) => {
                    const r = await fetch(url);
                    const buf = await r.arrayBuffer();
                    const b = new Uint8Array(buf);
                    let s=''; const C=8192;
                    for(let i=0;i<b.length;i+=C) s+=String.fromCharCode(...b.subarray(i,i+C));
                    return btoa(s);
                }
            """, src)
            out_path.write_bytes(base64.b64decode(b64))
            print(f"    {out_path.name}: {out_path.stat().st_size//1024}KB")
            return True
        page.wait_for_timeout(3000)
    return False

def send_and_get_video(page, prompt, out_path: Path):
    """Envía prompt de VIDEO a Meta AI y descarga el mp4."""
    if out_path.exists() and out_path.stat().st_size > 50000:
        print(f"    {out_path.name}: existe ({out_path.stat().st_size//1024}KB)")
        return True
    ta = page.locator("textarea, [contenteditable='true']").first
    try: ta.click(timeout=3000)
    except: page.evaluate("() => { const t = document.querySelector('textarea'); if(t) t.focus(); }")
    page.wait_for_timeout(300)
    page.keyboard.press("Control+A")
    page.evaluate("(t) => navigator.clipboard.writeText(t)", prompt)
    page.keyboard.press("Control+V")
    page.wait_for_timeout(500)
    page.keyboard.press("Enter")
    print(f"    Prompt vídeo enviado, esperando (~60s)...")
    page.wait_for_timeout(60000)
    # Buscar vídeo generado
    for _ in range(60):
        videos = page.evaluate("""
            () => Array.from(document.querySelectorAll('video'))
                .filter(v => v.src && v.src.length > 10)
                .map(v => v.src)
        """)
        if videos:
            src = videos[-1]
            b64 = page.evaluate("""
                async (url) => {
                    const r = await fetch(url);
                    const buf = await r.arrayBuffer();
                    const b = new Uint8Array(buf);
                    let s=''; const C=8192;
                    for(let i=0;i<b.length;i+=C) s+=String.fromCharCode(...b.subarray(i,i+C));
                    return btoa(s);
                }
            """, src)
            out_path.write_bytes(base64.b64decode(b64))
            print(f"    {out_path.name}: {out_path.stat().st_size//1024}KB")
            return True
        page.wait_for_timeout(3000)
    return False

def extract_last_frame(video_path: Path, out_path: Path):
    """Extrae el último fotograma de un vídeo."""
    cmd = [FF, "-sseof", "-0.15", "-i", str(video_path), "-frames:v", "1", str(out_path), "-y"]
    r = subprocess.run(cmd, capture_output=True, timeout=30)
    ok = r.returncode == 0 and out_path.exists()
    print(f"    Último frame: {out_path.name} {'OK' if ok else 'ERR'}")
    return ok

def concat_videos(v1: Path, v2: Path, out: Path):
    """Concatena dos vídeos sin crossfade."""
    concat_txt = out.parent / "concat.txt"
    concat_txt.write_text(f"file '{v1}'\nfile '{v2}'\n")
    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(out)]
    r = subprocess.run(cmd, capture_output=True, timeout=60)
    ok = r.returncode == 0 and out.exists()
    print(f"    Concat: {out.name} {'OK' if ok else 'ERR'} ({out.stat().st_size//1024 if ok else 0}KB)")
    return ok

def render_reel(concat_path: Path, texts: list, music: str, out: Path):
    SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")
    cmd = ([sys.executable, str(SCRIPT), str(out), music]
           + ["--clips", str(concat_path)]
           + ["--texts"] + texts
           + ["--seg", "2.0"])
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    ok = r.returncode == 0
    print(f"    Render: {out.name} {'OK' if ok else 'ERR'} ({out.stat().st_size//1024 if ok else 0}KB)")
    return ok

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP, timeout=15000)
    b.contexts[0].grant_permissions(["clipboard-read", "clipboard-write"])
    meta = get_meta_page(b)
    meta.bring_to_front()
    print(f"Meta AI: {meta.url}")

    for piece in PIECES:
        print(f"\n{'='*55}\n{piece['slug']}")
        base = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas") / piece["slug"]
        base.mkdir(parents=True, exist_ok=True)

        # Paso 1: Imagen base
        print("  Paso 1: Imagen base...")
        img_base = base / "base.jpg"
        ok1 = send_and_get_image(meta, piece["b1_img"], img_base)
        if not ok1:
            print("  [ERROR] No se generó imagen base")
            continue

        # Paso 2: Beat 1 — animar la imagen base con prompt de vídeo
        print("  Paso 2: Beat 1 (vídeo desde imagen)...")
        beat1 = base / "beat1.mp4"
        prompt_b1 = (
            f"Create a realistic video (no text, no logos, 9:16 vertical) based on this scene: "
            f"{piece['b1_anim']}"
        )
        ok2 = send_and_get_video(meta, prompt_b1, beat1)
        if not ok2:
            print("  [WARN] Beat 1 no generado como vídeo — intentando con 'Genera un vídeo de...'")
            prompt_b1_alt = f"Genera un vídeo realista 9:16 vertical, sin texto ni logos: {piece['b1_anim']}"
            ok2 = send_and_get_video(meta, prompt_b1_alt, beat1)
            if not ok2:
                print("  [ERROR] Beat 1 fallido")
                continue

        # Paso 3: Extraer último fotograma de Beat 1
        print("  Paso 3: Último fotograma Beat 1...")
        frame1 = base / "frame1.jpg"
        if not extract_last_frame(beat1, frame1):
            print("  [ERROR] No se pudo extraer el fotograma")
            continue

        # Paso 4: Beat 2 — continuar desde el fotograma
        print("  Paso 4: Beat 2 (continúa desde frame1)...")
        beat2 = base / "beat2.mp4"
        prompt_b2 = (
            f"Continue EXACTLY from this image. "
            f"{piece['b2_anim']}. "
            f"No text, no logos, 9:16 vertical, realistic, same person same room."
        )
        ok4 = send_and_get_video(meta, prompt_b2, beat2)
        if not ok4:
            print("  [WARN] Beat 2 falló")
            # Usar beat1 duplicado como fallback
            import shutil
            shutil.copy(beat1, beat2)
            print("  Fallback: beat1 duplicado como beat2")

        # Paso 5: Concatenar
        print("  Paso 5: Concatenando beats...")
        concat = base / "concat.mp4"
        concat_videos(beat1, beat2, concat)

        # Paso 6: Render con texto
        print("  Paso 6: Render con texto...")
        reel = base / "reel_v1.mp4"
        music_path = piece["music"] if Path(piece["music"]).exists() else r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\tt-viaje\music.mp3"
        render_reel(concat, piece["texts"], music_path, reel)

        print(f"  ✓ {piece['slug']} completo")
