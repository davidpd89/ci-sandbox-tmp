# -*- coding: utf-8 -*-
"""
Crea videos cortos de 7s para Instagram Reels desde las imagenes _v3.
Zoom sutil (1.00 -> 1.02), musica diferente para cada pieza, watermark top-right.
"""
import subprocess, sys
from pathlib import Path
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
BASE = Path(__file__).parent.parent
FONT = str(BASE / "tools/reel_template/fonts/PlayfairDisplay.ttf")
FONT_ESC = FONT.replace("\\", "/").replace(":", "\\:")

OUT_DIR = BASE / "09_Usados_video/meta/piezas"

PIECES = [
    {
        "id": "p27_ig",
        "image": str(BASE / "nuevo_flujo/Imagenes david/1000106609_v3.png"),
        "music": str(BASE / "tools/reel_template/tiktok_p3/music.mp3"),
        "out": str(OUT_DIR / "27-entro-solo-mirar/reel_p27_ig.mp4"),
    },
    {
        "id": "p29_ig",
        "image": str(BASE / "nuevo_flujo/Imagenes david/1000106605_v3.png"),
        "music": str(BASE / "tools/reel_template/clips_post4/music_tearsofjoy.mp3"),
        "out": str(OUT_DIR / "29-comprar-vs-leer/reel_p29_ig.mp4"),
    },
    {
        "id": "p31_ig",
        "image": str(BASE / "nuevo_flujo/Imagenes david/1000106604_v3.png"),
        "music": str(BASE / "tools/reel_template/clips_post3/music_foresttreasure.mp3"),
        "out": str(OUT_DIR / "31-libros-que-encuentran/reel_p31_ig.mp4"),
    },
]

DURATION = 7


def make_reel(piece):
    image = piece["image"]
    music = piece["music"]
    out = piece["out"]
    pid = piece["id"]

    # Temp file without watermark
    out_tmp = out.replace(".mp4", "_tmp.mp4")

    # Get image dimensions via PIL
    from PIL import Image as PILImage
    with PILImage.open(image) as im:
        W, H = im.size
    print(f"  Image dimensions: {W}x{H}")

    # Subtle zoom filter: 1.00 -> 1.02 over duration
    # Use pad to ensure exactly W x H output
    zoom_filt = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={W}:{H},"
        f"zoompan=z='1+0.02*on/({DURATION}*25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={DURATION * 25}:s={W}x{H}:fps=25,"
        f"setsar=1"
    )

    cmd_video = [
        FF, "-y",
        "-loop", "1", "-i", image,
        "-i", music,
        "-vf", zoom_filt,
        "-t", str(DURATION),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        out_tmp,
    ]

    print(f"\n[{pid}] Rendering {W}x{H} video...")
    r = subprocess.run(cmd_video, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  VIDEO ERROR: {r.stderr[-800:]}")
        return False

    # Add watermark top-right
    wm_filt = (
        f"drawtext=fontfile='{FONT_ESC}'"
        f":text='davidportodiaz.com'"
        f":fontcolor=white@0.85:fontsize=28"
        f":x=W-tw-24:y=24"
        f":shadowcolor=black@0.6:shadowx=2:shadowy=2"
    )
    cmd_wm = [FF, "-y", "-i", out_tmp, "-vf", wm_filt, "-c:a", "copy", out]
    r2 = subprocess.run(cmd_wm, capture_output=True, text=True)
    Path(out_tmp).unlink(missing_ok=True)

    if r2.returncode != 0:
        print(f"  WATERMARK ERROR: {r2.stderr[-400:]}")
        return False

    size_mb = Path(out).stat().st_size / 1024 / 1024
    print(f"  Done: {Path(out).name} ({size_mb:.1f} MB)")
    return True


if __name__ == "__main__":
    for piece in PIECES:
        Path(piece["out"]).parent.mkdir(parents=True, exist_ok=True)
        ok = make_reel(piece)
        if not ok:
            print(f"  FAILED: {piece['id']}")

    print("\nTodos los reels generados.")
