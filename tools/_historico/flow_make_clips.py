"""
Procesa las 4 imágenes capturadas de Flow:
1. Detecta área no-negra (la imagen real, sin UI chrome de Flow)
2. Escala a 1080x1920
3. Convierte a clip MP4 8s con Ken Burns via imageio_ffmpeg
"""
import sys, io, subprocess, os
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
from PIL import Image
import imageio_ffmpeg

IMGS_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo\images")
CLIPS_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo\clips")
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
DURATION = 8  # segundos por clip

IMAGES = [
    "img1_kindle_nightstand.png",
    "img2_person_reading.png",
    "img3_bookshelf.png",
    "img4_kindle_closeup.png",
]

def crop_to_content(img_path: Path) -> Path:
    """Detecta y recorta el área no-negra de la imagen (la foto sin el chrome del UI)."""
    out_path = IMGS_DIR / f"{img_path.stem}_crop.jpg"
    if out_path.exists() and out_path.stat().st_size > 50000:
        print(f"  Crop existe: {out_path.name}")
        return out_path

    with Image.open(img_path) as img:
        arr = np.array(img.convert("RGB"))

    # Encontrar columnas con brillo promedio > 15 (no completamente negras)
    col_brightness = arr.mean(axis=(0, 2))  # promedio por columna (eje Y promediado, eje canal promediado)
    threshold = 15
    bright_cols = np.where(col_brightness > threshold)[0]
    if len(bright_cols) == 0:
        print(f"  [WARN] No hay columnas con brillo > {threshold}, usando imagen completa")
        bright_cols = np.arange(arr.shape[1])

    x_start = int(bright_cols[0])
    x_end = int(bright_cols[-1]) + 1

    # Similar para filas (con umbral más bajo por barras de UI grises)
    row_brightness = arr.mean(axis=(1, 2))
    bright_rows = np.where(row_brightness > threshold)[0]
    if len(bright_rows) == 0:
        bright_rows = np.arange(arr.shape[0])
    y_start = int(bright_rows[0])
    y_end = int(bright_rows[-1]) + 1

    cropped = arr[y_start:y_end, x_start:x_end]
    h, w = cropped.shape[:2]
    print(f"  Contenido detectado: x=[{x_start}:{x_end}] y=[{y_start}:{y_end}] → {w}x{h}px")

    # Ahora asegurar ratio 9:16
    target_ratio = 9 / 16
    current_ratio = w / h
    if current_ratio > target_ratio:
        # Demasiado ancho → crop lateral centrado
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        cropped = cropped[:, left:left + new_w]
    elif current_ratio < target_ratio:
        # Demasiado alto → crop vertical centrado
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        cropped = cropped[top:top + new_h, :]

    h2, w2 = cropped.shape[:2]

    # Escalar a 1080x1920
    pil_img = Image.fromarray(cropped).resize((1080, 1920), Image.LANCZOS)
    pil_img.save(out_path, "JPEG", quality=92)
    print(f"  Guardado: {out_path.name} 1080x1920px {out_path.stat().st_size//1024}KB")
    return out_path

def make_ken_burns_clip(img_path: Path, clip_path: Path):
    """Genera clip Ken Burns 8s 1080x1920 con ffmpeg."""
    if clip_path.exists() and clip_path.stat().st_size > 200000:
        print(f"  Clip existe: {clip_path.name}")
        return True

    fps = 30
    frames = DURATION * fps
    # zoom de 1.0 a 1.12 en 8s, pan suave
    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:-1:-1,"
        f"zoompan=z='min(zoom+0.0005,1.12)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s=1080x1920:fps={fps}:d={frames}"
    )

    cmd = [
        FFMPEG, "-y",
        "-loop", "1",
        "-i", str(img_path),
        "-vf", vf,
        "-t", str(DURATION),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "20",
        str(clip_path)
    ]

    print(f"  ffmpeg: {clip_path.name}...", end="", flush=True)
    result = subprocess.run(cmd, capture_output=True, timeout=180)
    if result.returncode != 0:
        print(f" ERROR")
        print(result.stderr.decode("utf-8", errors="replace")[-400:])
        return False

    size = clip_path.stat().st_size
    print(f" ✓ {size//1024}KB")
    return True

def main():
    print(f"ffmpeg: {FFMPEG}")
    for img_name in IMAGES:
        img_path = IMGS_DIR / img_name
        if not img_path.exists():
            print(f"\n{img_name}: NO EXISTE — saltando")
            continue

        stem = img_path.stem
        print(f"\n=== {stem} ===")
        cropped = crop_to_content(img_path)

        clip_out = CLIPS_DIR / f"{stem}.mp4"
        make_ken_burns_clip(cropped, clip_out)

    print("\n=== RESUMEN ===")
    for img_name in IMAGES:
        stem = Path(img_name).stem
        clip = CLIPS_DIR / f"{stem}.mp4"
        ok = clip.exists() and clip.stat().st_size > 200000
        print(f"  {stem}: {'✓' if ok else '✗'} {clip.stat().st_size//1024 if clip.exists() else 0}KB")

if __name__ == "__main__":
    main()
