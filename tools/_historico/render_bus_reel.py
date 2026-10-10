"""Monta DP-F0-075 con texto humano real y lo sube + programa."""
import sys, io, subprocess, requests, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
CLIP = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\07-tarde-por-una-escena\clip1.mp4")
SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")
OUT = CLIP.parent / "reel_v1.mp4"

# Buscar música nueva no usada recientemente
# Usar la de "tt-viaje" que es urbana/positiva
MUSIC = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\tt-viaje\music.mp3")
if not MUSIC.exists():
    for mp3 in Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video").glob("**/*.mp3"):
        if "sfx" not in str(mp3).lower() and "rain" not in str(mp3).lower():
            MUSIC = mp3; break

# Texto humano real (basado en "me pasé de parada" de Reddit)
# 3 líneas × 1.4s = 4.2s (ligeramente más que el clip de 4.04s — perfecto)
TEXTS = [
    "Se me fue el bus.",
    "Estaba en lo importante.",
    "¿A qué llegas tarde tú?",
]

print(f"Clip: {CLIP} ({CLIP.stat().st_size//1024}KB)")
print(f"Música: {MUSIC.name}")
print(f"Textos: {TEXTS}")

cmd = ([sys.executable, str(SCRIPT), str(OUT), str(MUSIC)]
       + ["--clips", str(CLIP)]
       + ["--texts"] + TEXTS
       + ["--seg", "1.4"])

print("\nRenderizando...")
r = subprocess.run(cmd, capture_output=True, timeout=120)
print(r.stdout.decode("utf-8", errors="replace"))
if r.returncode != 0:
    print("ERROR:", r.stderr.decode("utf-8", errors="replace")[-300:])
    sys.exit(1)

print(f"OK: {OUT.name} ({OUT.stat().st_size//1024}KB)")

# Verificar QA frames
import subprocess as sp
for t in [0.5, 1.5, 2.5, 3.5]:
    sp.run([FF, "-ss", str(t), "-i", str(OUT), "-frames:v", "1", f"C:/Temp/bus_qa_{t}s.jpg", "-y"],
           capture_output=True)
print("QA frames en C:/Temp/bus_qa_*.jpg")
