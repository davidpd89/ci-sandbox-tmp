"""
Convierte una imagen en un clip de video 9:16 con efecto Ken Burns (zoom lento).
Salida: clip MP4 1080x1920 px, 30fps, sin audio.
El clip se pasa luego a render_reel_v6_paced.py.
"""
import sys
import subprocess
from pathlib import Path
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()

def make_ken_burns(
    image_path: str,
    output_path: str,
    duration: float = 20.0,
    zoom_direction: str = "in",  # "in" | "out" | "pan_left" | "pan_right"
    zoom_speed: float = 0.0012,
):
    """
    Genera un clip 9:16 con efecto Ken Burns desde una imagen.
    zoom_direction:
      "in"         → zoom hacia dentro (lento, centrado)
      "out"        → zoom hacia fuera
      "pan_left"   → zoom + paneo de derecha a izquierda
      "pan_right"  → zoom + paneo de izquierda a derecha
    """
    img = Path(image_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # El filtro zoompan necesita el frame con suficiente resolución.
    # Primero escalamos la imagen a 4K para dar margen al zoom (hasta 1.5x).
    # Luego crop final a 1080x1920.
    d = int(duration * 30)  # frames totales

    if zoom_direction == "in":
        z = f"min(zoom+{zoom_speed},1.5)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif zoom_direction == "out":
        z = f"max(zoom-{zoom_speed},1.0)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif zoom_direction == "pan_right":
        z = f"min(zoom+{zoom_speed},1.4)"
        x = "if(lte(on,1),0,x+iw/zoom/200)"
        y = "ih/2-(ih/zoom/2)"
    else:  # pan_left
        z = f"min(zoom+{zoom_speed},1.4)"
        x = "if(lte(on,1),iw-(iw/zoom),x-iw/zoom/200)"
        y = "ih/2-(ih/zoom/2)"

    vf = (
        # Paso 1: escalar a 2160 de ancho para dar margen al zoom
        "scale=2160:3840:force_original_aspect_ratio=increase:flags=lanczos,"
        "crop=2160:3840,"
        # Paso 2: Ken Burns
        f"zoompan=z='{z}':d=1:x='{x}':y='{y}',"
        # Paso 3: recortar al formato final 9:16
        "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,"
        "crop=1080:1920,"
        "setsar=1,"
        "fps=30"
    )

    cmd = [
        FF, "-y",
        "-loop", "1",
        "-i", str(img),
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        str(out),
    ]

    print(f"Generando Ken Burns clip: {out.name} ({zoom_direction}, {duration}s)...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR ffmpeg:\n{result.stderr[-500:]}", flush=True)
        return False
    print(f"  OK -> {out}", flush=True)
    return True


if __name__ == "__main__":
    IMAGES = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Imagenes david")
    OUT = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\clips_ken_burns")
    OUT.mkdir(exist_ok=True)

    # Clip 1: Reel Jul 23 — bookstore editorial B&W, zoom in suave
    make_ken_burns(
        str(IMAGES / "1000106609_v3.png"),
        str(OUT / "clip_bookstore.mp4"),
        duration=20,
        zoom_direction="in",
        zoom_speed=0.0010,
    )

    # Clip 2: Reel Jul 24 tarde — humor lector (mujer libro), pan ligero
    make_ken_burns(
        str(IMAGES / "1000106601_v3.png"),
        str(OUT / "clip_humor.mp4"),
        duration=18,
        zoom_direction="pan_right",
        zoom_speed=0.0008,
    )

    # Clip 3: Reel Jul 25 tarde — acantilado/amor, zoom out suave
    make_ken_burns(
        str(IMAGES / "1000106610_v3.png"),
        str(OUT / "clip_emocional.mp4"),
        duration=20,
        zoom_direction="out",
        zoom_speed=0.0008,
    )

    print("\nDone.")
