"""
Render reels P27 (libreria) y P29 (lectura bus) con stock videos y watermark top-right.
"""
import subprocess, sys, os, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "reel_template"))
from render_reel_v6_paced import build

BASE = Path(__file__).parent.parent
FF_PY = sys.executable

PIECES = [
    {
        "id": "27",
        "out_dir": BASE / "09_Usados_video/meta/piezas/27-entro-solo-mirar",
        "clip": BASE / "09_Usados_video/meta/piezas/27-entro-solo-mirar/stock_bookstore.mp4",
        "music": BASE / "tools/reel_template/tt_cerrar/music.mp3",
        "texts": [
            "La librería parecía normal.",
            "Solo estantes.",
            "Solo libros.",
            "Solo olor a papel.",
            "El segundo truco fue",
            "que no podía salir.",
        ],
        "seg": 2.0,
    },
    {
        "id": "29",
        "out_dir": BASE / "09_Usados_video/meta/piezas/29-comprar-vs-leer",
        "clip": BASE / "09_Usados_video/meta/piezas/29-comprar-vs-leer/stock_reading.mp4",
        "music": BASE / "tools/reel_template/clips_test/music_magical_moment.mp3",
        "texts": [
            "Iba a coger el bus.",
            "El libro tuvo un capítulo",
            "con muy mala educación.",
            "El bus se fue.",
            "El capítulo, no.",
            "¿Qué libro te hizo eso?",
        ],
        "seg": 2.0,
    },
]

import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()


def add_watermark(src: Path, dst: Path):
    """Add davidportodiaz.com watermark top-right via ffmpeg drawtext."""
    font = str(BASE / "tools/reel_template/fonts/PlayfairDisplay.ttf")
    # Escape Windows path for ffmpeg fontfile
    font_escaped = font.replace("\\", "/").replace(":", "\\:")
    filt = (
        f"drawtext=fontfile='{font_escaped}'"
        f":text='davidportodiaz.com'"
        f":fontcolor=white@0.85"
        f":fontsize=28"
        f":x=W-tw-24"
        f":y=24"
        f":shadowcolor=black@0.6"
        f":shadowx=2"
        f":shadowy=2"
    )
    r = subprocess.run(
        [FF, "-y", "-i", str(src), "-vf", filt, "-c:a", "copy", str(dst)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"watermark failed:\n{r.stderr[-1500:]}")
    print(f"  Watermark OK -> {dst.name}")


for p in PIECES:
    print(f"\n=== PIEZA {p['id']} ===")
    out_dir = Path(p["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    temp_out = out_dir / f"reel_p{p['id']}_temp.mp4"
    final_out = out_dir / f"reel_p{p['id']}.mp4"

    # Render reel (no brand - using stock video, no AI watermark to cover)
    print("  Rendering...")
    build(
        clips=[str(p["clip"])],
        texts=p["texts"],
        audio=str(p["music"]),
        out=str(temp_out),
        seg=p["seg"],
        use_brand=False,
    )

    # Add top-right watermark
    add_watermark(temp_out, final_out)
    temp_out.unlink(missing_ok=True)

    size_mb = final_out.stat().st_size / 1024 / 1024
    print(f"  Final: {final_out.name} ({size_mb:.1f} MB)")

print("\nAmbos reels listos. Revisar frames de texto antes de publicar.")
