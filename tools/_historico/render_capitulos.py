"""Monta DP-F0-076 'Hay capítulos que no terminas' y lo sube + programa."""
import sys, io, subprocess, requests, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
CLIP = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\08-gesto-minimo\clip1.mp4")
SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")
OUT = CLIP.parent / "reel_v1.mp4"

# Música que no hayamos usado recientemente
MUSIC = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\03-cerrar-libro\music_ventana.mp3")
if not MUSIC.exists():
    for mp3 in Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video").glob("**/*.mp3"):
        if "sfx" not in str(mp3).lower() and "rain" not in str(mp3).lower():
            MUSIC = mp3; break

# Texto: 3 líneas × ~1.35s = 4.05s (del banco shortlist, "Muy alta")
TEXTS = [
    "Hay capítulos que no terminas.",
    "Los cierras.",
    "¿Cuál fue el tuyo?",
]

print(f"Clip: {CLIP.stat().st_size//1024}KB")
cmd = ([sys.executable, str(SCRIPT), str(OUT), str(MUSIC)]
       + ["--clips", str(CLIP)]
       + ["--texts"] + TEXTS
       + ["--seg", "1.35"])

r = subprocess.run(cmd, capture_output=True, timeout=120)
print(r.stdout.decode("utf-8", errors="replace"))
if r.returncode != 0:
    print("ERROR:", r.stderr.decode("utf-8", errors="replace")[-200:])
    sys.exit(1)
print(f"OK: {OUT.stat().st_size//1024}KB")

# QA frames
import subprocess as sp
for t in [0.5, 2.0, 3.5]:
    sp.run([FF, "-ss", str(t), "-i", str(OUT), "-frames:v", "1", f"C:/Temp/cap_qa_{t}s.jpg", "-y"], capture_output=True)
