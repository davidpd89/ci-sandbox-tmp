"""
Genera con Meta AI las imágenes para 3 reels:
- DP-F0-077: "Este libro ya vivió" (Jul 21)
- DP-F0-078: "Olvidé el final" (Jul 22 pieza 1)
- DP-F0-079: "Doce euros bolsillo" (Jul 22 pieza 2)
4 imágenes por concepto → Ken Burns clips → render_reel_v6_paced.py
"""
import sys, io, subprocess, base64, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from playwright.sync_api import sync_playwright
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
CDP_URL = "http://127.0.0.1:9223"

PIECES = [
    {
        "id": "DP-F0-077",
        "slug": "libro-ya-vivio",
        "texts": ["Este libro ya vivió.", "Traía una nota dentro.", "¿La abrirías?"],
        "prompts": [
            "Close-up of worn old second-hand paperback book open on wooden table, yellowed pages, pencil marks, no visible title, warm afternoon light, no text visible, photorealistic 9:16 vertical",
            "A small folded handwritten note slipping out from between book pages onto a wooden table, warm light, dust particles, hands hovering nearby, no readable text on the note, photorealistic 9:16 vertical",
            "Person's face with quiet look of curiosity and hesitation, old book open in lap, a folded note between fingers, warm lamp light, realistic emotion, 9:16 vertical",
            "Wide shot: person at a café or home table, old book open, folded note beside it, a warm cup nearby, soft light, contemplative mood, photorealistic 9:16 vertical"
        ],
        "music_hint": "reflective"
    },
    {
        "id": "DP-F0-078",
        "slug": "olvide-el-final",
        "texts": ["Olvidé el final.", "Sé que me dolió.", "¿Con qué libro?"],
        "prompts": [
            "Woman standing in front of personal bookshelf in daylight, running fingers along anonymous book spines with no readable text, soft window light, gentle contemplative expression, photorealistic 9:16 vertical",
            "Close-up of a hand stopping on one old paperback spine halfway pulled from the shelf, no readable title, subtle emotional reaction, warm natural light, photorealistic 9:16 vertical",
            "Woman's face in soft profile, looking at the book she holds, distant expression as if remembering a feeling not a plot, natural indoor light, realistic, 9:16 vertical",
            "The same book placed back on the shelf gently, hand releasing it, quiet domestic scene, afternoon light, emotional but restrained, 9:16 vertical"
        ],
        "music_hint": "melancholic"
    },
    {
        "id": "DP-F0-079",
        "slug": "doce-euros-bolsillo",
        "texts": ["Doce euros bolsillo.", "Treinta si brilla.", "¿También te dolió?"],
        "prompts": [
            "Person in a bookstore picking up a beautiful paperback, cover blurred and unreadable, looking at the back price tag, slightly surprised expression, natural bookstore lighting, 9:16 vertical",
            "Close-up of hand holding a book with a price sticker visible but unreadable, wallet visible in other hand, conflicted gesture, bookstore background blurred, 9:16 vertical",
            "Person carefully placing the expensive book back on the shelf, look of resignation mixed with desire, bookstore aisle, natural light, humorous but real emotion, 9:16 vertical",
            "Person walking out of the bookstore with one small bag, slight guilty-happy expression, daylight on street, casual clothes, no brand logos, 9:16 vertical"
        ],
        "music_hint": "playful"
    }
]

def find_meta(b):
    for pg in [x for c in b.contexts for x in c.pages]:
        if "meta.ai" in pg.url:
            return pg
    ctx = b.contexts[0]
    pg = ctx.new_page()
    pg.goto("https://www.meta.ai/")
    pg.wait_for_load_state("networkidle", timeout=20000)
    return pg

def gen_image(meta, prompt, out_path: Path):
    if out_path.exists() and out_path.stat().st_size > 30000:
        print(f"  {out_path.name}: existe")
        return True
    ta = meta.locator("textarea, [contenteditable='true']").first
    try: ta.click(timeout=3000)
    except: meta.evaluate("() => { const t = document.querySelector('textarea'); if(t) t.focus(); }")
    meta.wait_for_timeout(300)
    meta.keyboard.press("Control+A")
    meta.evaluate("(t) => navigator.clipboard.writeText(t)", prompt)
    meta.keyboard.press("Control+V")
    meta.wait_for_timeout(500)
    meta.keyboard.press("Enter")
    print(f"  Prompt enviado, esperando imagen...")
    meta.wait_for_timeout(25000)
    for _ in range(30):
        imgs = meta.evaluate("""
            () => Array.from(document.querySelectorAll('img[src*="fbcdn"], img[src*="scontent"]'))
                .filter(img => img.naturalWidth > 200)
                .map(img => img.src)
        """)
        if imgs:
            src = imgs[-1]
            b64 = meta.evaluate("""
                async (url) => {
                    const r = await fetch(url);
                    const buf = await r.arrayBuffer();
                    const b = new Uint8Array(buf);
                    let s = ''; const C = 8192;
                    for (let i=0; i<b.length; i+=C) s += String.fromCharCode(...b.subarray(i,i+C));
                    return btoa(s);
                }
            """, src)
            out_path.write_bytes(base64.b64decode(b64))
            print(f"  {out_path.name} ({out_path.stat().st_size//1024}KB)")
            return True
        meta.wait_for_timeout(5000)
    return False

def img_to_clip(img, out, dur=8):
    if out.exists() and out.stat().st_size > 100000: return True
    fps, frames = 30, dur*30
    vf = (f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:-1:-1,"
          f"zoompan=z='min(zoom+0.0005,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}:d={frames}")
    cmd = [FF,"-y","-loop","1","-i",str(img),"-vf",vf,"-t",str(dur),"-c:v","libx264","-pix_fmt","yuv420p","-preset","fast","-crf","20",str(out)]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    if r.returncode == 0:
        print(f"  clip: {out.stat().st_size//1024}KB")
        return True
    return False

def render_reel(clips, texts, music, out):
    SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")
    n = len(clips)
    seg = round(n * 8 / len(texts), 1)
    cmd = ([sys.executable, str(SCRIPT), str(out), str(music)]
           + ["--clips"] + [str(c) for c in clips]
           + ["--texts"] + texts
           + ["--seg", str(seg)])
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    ok = r.returncode == 0
    if ok: print(f"  reel: {out.stat().st_size//1024}KB {seg}s/línea")
    else: print(f"  reel ERROR: {r.stderr.decode()[-100:]}")
    return ok

MUSIC_MAP = {
    "reflective": Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\03-la-gravedad-se-rinde\silent_descent.mp3"),
    "melancholic": Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\03-cerrar-libro\music_ventana.mp3"),
    "playful": Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\tt-viaje\music.mp3"),
}

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    b.contexts[0].grant_permissions(["clipboard-read","clipboard-write"])
    meta = find_meta(b)
    meta.bring_to_front()
    print(f"Meta AI: {meta.url}")

    for piece in PIECES:
        print(f"\n{'='*50}")
        print(f"{piece['id']} — {piece['slug']}")
        base = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas") / f"20-{piece['slug']}"
        imgs_dir = base / "images"
        clips_dir = base / "clips"
        imgs_dir.mkdir(parents=True, exist_ok=True)
        clips_dir.mkdir(parents=True, exist_ok=True)

        # Generar imágenes
        print("Generando 4 imágenes...")
        imgs = []
        for i, prompt in enumerate(piece["prompts"], 1):
            out_img = imgs_dir / f"scene{i}.jpg"
            print(f"  Escena {i}: {prompt[:50]}...")
            ok = gen_image(meta, prompt, out_img)
            if ok: imgs.append(out_img)

        if not imgs:
            print(f"  [ERROR] No se generaron imágenes para {piece['id']}")
            continue

        # Ken Burns clips
        print(f"Convirtiendo {len(imgs)} imágenes a clips...")
        clips = []
        for i, img in enumerate(imgs, 1):
            clip = clips_dir / f"clip{i}.mp4"
            if img_to_clip(img, clip):
                clips.append(clip)

        # Render
        music = MUSIC_MAP.get(piece["music_hint"])
        if not music or not music.exists():
            for mp3 in Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video").glob("**/*.mp3"):
                if "sfx" not in str(mp3).lower():
                    music = mp3; break
        reel_out = base / "reel_v1.mp4"
        print(f"Renderizando con música: {music.name}...")
        render_reel(clips, piece["texts"], music, reel_out)

        print(f"✓ {piece['id']} completo")
