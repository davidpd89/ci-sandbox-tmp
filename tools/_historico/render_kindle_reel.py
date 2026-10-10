"""Re-renderiza el reel del Kindle con tildes correctas."""
import sys, io, subprocess
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
BASE = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo")
CLIPS = BASE / "clips"
SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")
MUSIC = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\03-la-gravedad-se-rinde\silent_descent.mp3")
OUT = BASE / "reel_v2.mp4"

TEXTS = [
    "Me compré el Kindle para leer más.",
    "Eso fue hace nueve meses.",
    "Ahí está.",
    "Cargado.",
    "Sin abrir.",
    "A veces lo cojo.",
    "Le quito el polvo.",
    "Lo pongo en la mesita.",
    "Pienso: «hoy empiezo algo».",
    "Y abro el móvil.",
    "Hay libros en papel que tampoco termino.",
    "Hay audiolibros a medias.",
    "Y sigo comprando libros.",
    "Sigo diciendo «cuando tenga tiempo».",
    "No eres el único.",
    "¿Qué llevas meses prometiéndote leer?",
]

clips_list = [
    str(CLIPS / "img1_kindle_nightstand.mp4"),
    str(CLIPS / "img2_person_reading.mp4"),
    str(CLIPS / "img3_bookshelf.mp4"),
    str(CLIPS / "img4_kindle_closeup.mp4"),
]

cmd = (
    [sys.executable, str(SCRIPT), str(OUT), str(MUSIC)]
    + ["--clips"] + clips_list
    + ["--texts"] + TEXTS
    + ["--seg", "2.0"]
)

print("Renderizando reel_v2 con tildes correctas...")
result = subprocess.run(cmd, capture_output=True, timeout=300)
print(result.stdout.decode("utf-8", errors="replace"))
if result.returncode != 0:
    print("STDERR:", result.stderr.decode("utf-8", errors="replace")[-500:])
else:
    size = OUT.stat().st_size
    print(f"OK: {OUT.name} ({size//1024//1024}MB)")
