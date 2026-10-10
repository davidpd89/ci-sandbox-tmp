"""Preflight local, sin red, de media editorial para nueve redes.

Pillow (ya en requirements-ci) inspecciona el contenido real, no la extension.
Las recomendaciones de encuadre no bloquean; los errores de formato, carga,
ALT y decodificacion si. Para video se requiere ffprobe local: sin el binario
NO se declara compatible un archivo no inspeccionado.

No publica, no escribe sobre assets originales, no usa credenciales.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

NETWORKS = frozenset({
    "x", "threads", "facebook", "pinterest", "reddit", "bluesky",
    "mastodon", "tiktok", "instagram",
})
IMAGE_EXTENSIONS = frozenset({".jpeg", ".jpg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".webm", ".mkv"})
# Contrato seguro de salida preparado: el origen se puede convertir con prepare_image.
IMAGE_FORMATS = frozenset({"JPEG", "PNG"})
# Un unico limite verificado a nivel de protocolo; los limites no confirmados
# permanecen configurables, no se convierten en bloqueos arbitrarios.
IMAGE_BYTE_LIMITS = {"bluesky": 2_000_000}
# Relaciones sugeridas para el diseño (orientativas, NUNCA bloqueantes).
PREFERRED_RATIOS = {
    "instagram": (4 / 5, 1.0), "pinterest": (2 / 3,),
    "tiktok": (9 / 16,), "facebook": (1.0, 4 / 5),
    "threads": (1.0, 4 / 5), "x": (1.0, 16 / 9),
    "bluesky": (1.0,), "mastodon": (1.0,), "reddit": (1.0,),
}


def _issue(code: str, message: str, *, severity: str = "error") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _dhash(image: Image.Image) -> str:
    # Solo indicador editorial (aproximado); no motivo de bloqueo.
    g = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
    p = list(g.getdata())
    result = 0
    for y in range(8):
        for x in range(8):
            result = (result << 1) | int(p[y * 9 + x] > p[y * 9 + x + 1])
    return f"{result:016x}"


def _probe_video(path: Path, ffprobe: str | None = None) -> dict[str, Any]:
    binary = ffprobe or shutil.which("ffprobe")
    if not binary:
        raise RuntimeError("ffprobe no disponible: video sin verificar")
    result = subprocess.run(
        [binary, "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if result.returncode or not result.stdout.strip():
        raise ValueError("ffprobe no puede decodificar los metadatos del video")
    return json.loads(result.stdout)


def inspect_asset(
    path: str | Path, network: str, *, alt: str = "",
    root: str | Path | None = None, ffprobe: str | None = None,
    max_bytes: int | None = None,
) -> dict[str, Any]:
    """Contrato estable: errors/warnings + metadatos, nunca acciones de red.

    max_bytes permite limites configurados por adaptador/servidor sin inventar
    restricciones globales. La inspeccion NO modifica el archivo.
    """
    if network not in NETWORKS:
        raise ValueError(f"Red desconocida: {network}")
    file = Path(path)
    report: dict[str, Any] = {
        "network": network, "filename": file.name, "kind": None,
        "errors": [], "warnings": [], "metadata": {},
    }
    def add(code: str, message: str, *, warning: bool = False) -> None:
        entry = _issue(code, message, severity="warning" if warning else "error")
        report["warnings" if warning else "errors"].append(entry)

    if root is not None and not _contained(file, Path(root)):
        add("unsafe_path", "Asset fuera del directorio permitido")
        return report
    if not file.is_file():
        add("missing", "El archivo no existe")
        return report
    try:
        size = file.stat().st_size
        if size <= 0:
            add("empty", "El archivo esta vacio")
            return report
        report["metadata"]["bytes"] = size
        report["metadata"]["sha256"] = _digest(file)
    except OSError:
        add("unreadable", "No se puede leer el archivo")
        return report

    suffix = file.suffix.lower()
    # Un nombre valido en Linux puede romper la ruta al transferirla a Windows.
    # Se avisa (no bloquea) antes de preparar el asset con un nombre portable.
    if (any(c in file.name for c in '<>:"/\\|?*') or
            file.name.rstrip(" .") != file.name or
            file.stem.upper() in {"CON", "PRN", "AUX", "NUL", "COM1", "LPT1"}):
        add("filename_windows", "Renombrar para compatibilidad Windows", warning=True)
    if suffix in IMAGE_EXTENSIONS:
        report["kind"] = "image"
        if not alt or not alt.strip():
            add("alt_missing", "Falta ALT descriptivo de la imagen")
        try:
            with Image.open(file) as source:
                fmt = source.format
                declared = "JPEG" if suffix in {".jpg", ".jpeg"} else "PNG" if suffix == ".png" else None
                if declared is not None and fmt != declared:
                    add("image_extension", "La extension no coincide con los bytes de imagen")
                if fmt not in IMAGE_FORMATS:
                    add("image_format", f"Formato {fmt} requiere preparar JPEG/PNG")
                if getattr(source, "n_frames", 1) > 1:
                    add("animated", "Media animada: requiere adaptador especifico")
                source.load()
                im = ImageOps.exif_transpose(source)
                width, height = im.size
                if not width or not height:
                    add("invalid_dimensions", "Dimensiones invalidas")
                else:
                    report["metadata"].update({
                        "format": fmt, "width": width, "height": height,
                        "ratio": round(width / height, 4), "dhash": _dhash(im),
                    })
                    if min(width, height) < 320:
                        add("small", "Resolucion baja; revisar en vista previa", warning=True)
                    preferred = PREFERRED_RATIOS[network]
                    if min(abs(width / height - r) for r in preferred) > 0.35:
                        add("ratio", "Encuadre alejado del recomendado; revisar sin recortar personas", warning=True)
                if source.getexif().get(274, 1) != 1:
                    add("exif_orientation", "Normalizar orientacion EXIF antes de publicar", warning=True)
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
            add("image_corrupt", "Imagen ilegible, truncada o demasiado grande para decodificar")
        limit = max_bytes if max_bytes is not None else IMAGE_BYTE_LIMITS.get(network)
    elif suffix in VIDEO_EXTENSIONS:
        report["kind"] = "video"
        try:
            media = _probe_video(file, ffprobe=ffprobe)
            tracks = media.get("streams") or []
            video = next((t for t in tracks if t.get("codec_type") == "video"), None)
            audio = next((t for t in tracks if t.get("codec_type") == "audio"), None)
            if not video:
                add("video_track", "Sin pista de video")
            else:
                report["metadata"].update({
                    "video_codec": video.get("codec_name"),
                    "width": video.get("width"), "height": video.get("height"),
                    "audio_codec": audio.get("codec_name") if audio else None,
                    "duration": (media.get("format") or {}).get("duration"),
                })
                if suffix not in {".mp4", ".m4v"}:
                    add("video_container", "Preparar MP4 para salida comun")
                if video.get("codec_name") != "h264":
                    add("video_codec", "Preparar video H.264 para salida comun")
                if audio and audio.get("codec_name") != "aac":
                    add("audio_codec", "Preparar audio AAC para salida comun")
                if not video.get("width") or not video.get("height"):
                    add("video_dimensions", "Dimensiones de video ausentes")
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            add("video_unverified", f"Video sin verificar: {type(exc).__name__}")
        limit = max_bytes
    else:
        add("unknown_type", "Extension de media no admitida en preflight")
        return report
    if limit is not None and size > limit:
        add("file_size", f"Archivo {size} bytes supera limite configurado {limit}")
    return report


def inspect_item(item: dict[str, Any]) -> list[str]:
    """Puente de lectura con content_queue (9 redes); sin mutar la ficha."""
    errors: list[str] = []
    root = item.get("carpeta")
    for entry in item.get("media") or []:
        if not entry.get("exists"):
            continue  # El publicador ya informa de ausencias.
        path = entry.get("path")
        if not path:
            errors.append("asset declarado sin ruta verificable")
            continue
        # El ALT global solo es equivalente al ALT de un asset si es unico.
        # En un carrusel, cada imagen necesita su descripcion independiente.
        media = item.get("media") or []
        fallback_alt = item.get("alt") if len(media) == 1 else ""
        result = inspect_asset(
            path, item["red"], alt=entry.get("alt") or fallback_alt or "",
            root=root,
        )
        errors.extend(f"{entry.get('filename')}: {e['code']}: {e['message']}"
                      for e in result["errors"])
    return errors


def find_duplicates(reports: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Igualdad exacta y similitud visual informativas, nunca borrado automatico."""
    found = []
    previous: list[dict[str, Any]] = []
    for report in reports:
        meta = report.get("metadata") or {}
        for other in previous:
            om = other.get("metadata") or {}
            exact = meta.get("sha256") and meta["sha256"] == om.get("sha256")
            a, b = meta.get("dhash"), om.get("dhash")
            similar = a and b and (int(a, 16) ^ int(b, 16)).bit_count() <= 5
            if exact or similar:
                found.append({
                    "first": other["filename"], "second": report["filename"],
                    "kind": "exact" if exact else "visual_candidate",
                })
                break
        previous.append(report)
    return found


def prepare_image(
    source: str | Path, output: str | Path, *, max_side: int = 2048,
    jpeg_quality: int = 85,
) -> Path:
    """Conversion explicita, sin crop ni upscale, EXIF normalizado y sin metadatos."""
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError("No sobreescribir el original")
    if output.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("Salida debe ser JPEG o PNG")
    if not 1 <= jpeg_quality <= 95 or max_side < 1:
        raise ValueError("Parametros de conversion invalidos")
    with Image.open(source) as original:
        original.load()
        if getattr(original, "n_frames", 1) > 1:
            raise ValueError("La animacion no se debe aplanar automaticamente")
        im = ImageOps.exif_transpose(original)
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        if output.suffix.lower() in {".jpg", ".jpeg"}:
            if im.mode in ("RGBA", "LA") or "transparency" in im.info:
                rgba = im.convert("RGBA")
                bg = Image.new("RGB", rgba.size, "white")
                bg.paste(rgba, mask=rgba.getchannel("A"))
                im = bg
            else:
                im = im.convert("RGB")
            im.save(output, "JPEG", quality=jpeg_quality, optimize=True)
        else:
            im.save(output, "PNG", optimize=True)
    return output


def thumbnail(source: str | Path, output: str | Path, size: tuple[int, int] = (480, 480)) -> Path:
    """Previsualizacion opt-in de un solo asset: nunca modifica origen."""
    if Path(source).resolve() == Path(output).resolve():
        raise ValueError("No sobrescribir original")
    with Image.open(source) as original:
        original.load()
        im = ImageOps.exif_transpose(original).convert("RGB")
        im.thumbnail(size, Image.Resampling.LANCZOS)
        im.save(output, "JPEG", quality=80)
    return Path(output)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network", choices=sorted(NETWORKS))
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--alt", default="")
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    reports = [inspect_asset(p, args.network, alt=args.alt, root=args.root) for p in args.paths]
    print(json.dumps({"reports": reports, "duplicates": find_duplicates(reports)},
                     ensure_ascii=False, indent=2))
    return int(any(report["errors"] for report in reports))


if __name__ == "__main__":
    raise SystemExit(main())
