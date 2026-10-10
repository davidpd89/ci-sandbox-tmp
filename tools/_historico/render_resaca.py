"""Monta el reel DP-F0-071 'Resaca de libro': clip1 × 3 = 15s, 6 líneas × 2.5s."""
import sys, subprocess
from pathlib import Path
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
BASE = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\pixverse\piezas\04-resaca-libro")
SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")
MUSIC = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\03-cerrar-libro\music_ventana.mp3")

# Crear clip1 extendido: concat el clip × 3 usando ffmpeg
CLIP1 = BASE / "clip1.mp4"
CLIP_EXT = BASE / "clip1_x3.mp4"

if not CLIP_EXT.exists():
    # Crear archivo concat
    concat_txt = BASE / "concat.txt"
    concat_txt.write_text(f"file '{CLIP1}'\nfile '{CLIP1}'\nfile '{CLIP1}'\n")
    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
           "-c", "copy", str(CLIP_EXT)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0:
        print(f"clip1_x3.mp4 creado ({CLIP_EXT.stat().st_size//1024}KB)")
    else:
        print(f"Error concat: {r.stderr.decode()[-200:]}")
        sys.exit(1)

# Verificar música
if not MUSIC.exists():
    # Buscar alternativa
    import glob
    mp3s = list(Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video").glob("**/*.mp3"))
    mp3s = [m for m in mp3s if "silent_descent" not in str(m)]  # no repetir el del Kindle
    if mp3s:
        MUSIC = mp3s[0]
        print(f"Usando música alternativa: {MUSIC.name}")
    else:
        print("No se encontró música")
        sys.exit(1)

OUT = BASE / "reel_v1.mp4"

TEXTS = [
    "Terminé el libro.",
    "El libro no terminó conmigo.",
    "Lo cerré.",
    "Lo puse en la mesita.",
    "Seguí con mi vida.",
    "¿Qué libro te dejó así?",
]

cmd = (
    [sys.executable, str(SCRIPT), str(OUT), str(MUSIC)]
    + ["--clips", str(CLIP_EXT)]
    + ["--texts"] + TEXTS
    + ["--seg", "2.5"]
)

print("Renderizando reel_v1.mp4...")
result = subprocess.run(cmd, capture_output=True, timeout=300)
stdout = result.stdout.decode("utf-8", errors="replace")
stderr = result.stderr.decode("utf-8", errors="replace")
print(stdout)
if result.returncode != 0:
    print("STDERR:", stderr[-300:])
else:
    print(f"OK: {OUT.name} ({OUT.stat().st_size//1024//1024}MB)")
