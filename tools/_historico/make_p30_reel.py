# -*- coding: utf-8 -*-
"""
Crea video de 10s para P30 (#606, hilo azul) con zoom lento + music_tearsofjoy.
Equivale a lo que habría hecho Meta AI pero via ffmpeg.
"""
import subprocess, sys
from pathlib import Path
from PIL import Image
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
BASE = Path(__file__).parent.parent

IMAGE = str(BASE / "nuevo_flujo/Imagenes david/1000106606_v3.png")
MUSIC = str(BASE / "tools/reel_template/clips_post4/music_tearsofjoy.mp3")
OUT_DIR = BASE / "09_Usados_video/meta/piezas/30-dualidad-lectora"
OUT = str(OUT_DIR / "reel_p30_ig.mp4")
DURATION = 10

W, H = 1080, 1920

OUT_DIR.mkdir(parents=True, exist_ok=True)

w_src, h_src = Image.open(IMAGE).size
ar_src = w_src / h_src
ar_dst = W / H

if ar_src > ar_dst:
    scale = f"scale=-2:{H}"
else:
    scale = f"scale={W}:-2"

zoom_filt = (
    f"{scale}:flags=lanczos,"
    f"crop={W}:{H},"
    f"zoompan=z='1+0.025*on/({DURATION}*25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    f":d={DURATION * 25}:s={W}x{H}:fps=25,"
    f"setsar=1"
)

tmp = OUT.replace(".mp4", "_tmp.mp4")

# Paso 1: video mudo
r1 = subprocess.run(
    [FF, "-y", "-loop", "1", "-i", IMAGE,
     "-vf", zoom_filt,
     "-t", str(DURATION),
     "-c:v", "libx264", "-preset", "slow", "-crf", "22",
     "-pix_fmt", "yuv420p",
     tmp],
    capture_output=True, text=True
)
if r1.returncode != 0:
    print("ERROR paso 1:", r1.stderr[-300:])
    sys.exit(1)
print("Paso 1 OK — video mudo generado")

# Paso 2: mezclar musica
r2 = subprocess.run(
    [FF, "-y", "-i", tmp, "-i", MUSIC,
     "-map", "0:v", "-map", "1:a",
     "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
     "-shortest",
     OUT],
    capture_output=True, text=True
)
if r2.returncode != 0:
    print("ERROR paso 2:", r2.stderr[-300:])
    sys.exit(1)

size_mb = Path(OUT).stat().st_size / 1024 / 1024
print(f"Paso 2 OK — video con música: {size_mb:.1f}MB → {OUT}")
