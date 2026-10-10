# -*- coding: utf-8 -*-
import sys, os, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "reel_template"))
from render_reel_v6_paced import build
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
BASE = Path(__file__).parent.parent
OUT_DIR = BASE / "09_Usados_video/meta/piezas/31-libros-que-encuentran"
CLIP = OUT_DIR / "stock_emotional.mp4"
MUSIC = BASE / "tools/reel_template/tt_subraya/music.mp3"
FONT = BASE / "tools/reel_template/fonts/PlayfairDisplay.ttf"

TEXTS = [
    "A veces, querer bien",
    "no es sacarte del abismo.",
    "Es sentarse cerca",
    "hasta que puedas",
    "mirar arriba.",
]

temp = OUT_DIR / "reel_p31_temp.mp4"
final = OUT_DIR / "reel_p31.mp4"

print("Rendering P31...")
build(
    clips=[str(CLIP)],
    texts=TEXTS,
    audio=str(MUSIC),
    out=str(temp),
    seg=1.7,
    use_brand=False,
)

print("Adding watermark...")
font_e = str(FONT).replace("\\", "/").replace(":", "\\:")
filt = (
    "drawtext=fontfile='" + font_e + "'"
    ":text='davidportodiaz.com'"
    ":fontcolor=white@0.85:fontsize=28"
    ":x=W-tw-24:y=24"
    ":shadowcolor=black@0.6:shadowx=2:shadowy=2"
)
r = subprocess.run(
    [FF, "-y", "-i", str(temp), "-vf", filt, "-c:a", "copy", str(final)],
    capture_output=True, text=True
)
if r.returncode != 0:
    print("ERROR: " + r.stderr[-500:])
    sys.exit(1)
temp.unlink(missing_ok=True)
sz = final.stat().st_size / 1024 / 1024
print("Done: reel_p31.mp4 (" + str(round(sz, 1)) + " MB)")
