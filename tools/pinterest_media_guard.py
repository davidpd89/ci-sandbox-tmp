"""Preflight local del publicador web de Pinterest; ninguna operación remota.

Solo comprueba imagen estática (pin normal), no anuncios, vídeo o cargas móviles.
"""
from __future__ import annotations

import os
import warnings
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError

MAX_WEB_IMAGE_BYTES = 20_000_000  # límite web conservador: 20 MB decimales
WEB_FORMATS = frozenset({"BMP", "JPEG", "PNG", "TIFF", "WEBP"})


class PinPreflightError(ValueError):
    """Entrada local inválida: todavía no se ha abierto el navegador."""


def validate_web_pin_image(path):
    """Lee cabecera y decodificación de una imagen; devuelve datos comprobados."""
    if not isinstance(path, (str, os.PathLike)) or not os.fspath(path):
        raise PinPreflightError("imagen: ruta local vacía o inválida")
    try:
        size = os.stat(path).st_size
    except (OSError, ValueError) as exc:
        raise PinPreflightError("imagen: archivo inaccesible") from exc
    if not 0 < size <= MAX_WEB_IMAGE_BYTES:
        raise PinPreflightError("imagen: archivo vacío o superior a 20 MB web")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as source:
                fmt = source.format
                width, height = source.size
                if fmt not in WEB_FORMATS:
                    raise PinPreflightError("imagen: tipo no admitido para Pin web")
                if width <= 0 or height <= 0:
                    raise PinPreflightError("imagen: dimensiones inválidas")
                source.verify()
    except (OSError, ValueError, UnidentifiedImageError,
            Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        if isinstance(exc, PinPreflightError):
            raise
        raise PinPreflightError("imagen: formato ilegible, truncado o sospechoso") from exc
    return {"format": fmt, "bytes": size, "width": width,
            "height": height, "aspect_2_3": width * 3 == height * 2}


def validate_web_pin_fields(title, description, link, alt):
    """Valida metadatos entregados al compositor web, sin suponer publicación."""
    fields = (("título", title, 100), ("descripción", description, 800),
              ("texto alternativo", alt, None))
    for label, value, maximum in fields:
        if not isinstance(value, str) or not value.strip():
            raise PinPreflightError(f"{label}: obligatorio")
        if maximum is not None and len(value) > maximum:
            raise PinPreflightError(f"{label}: supera {maximum} caracteres")
    if not isinstance(link, str) or not link or any(ord(c) < 33 for c in link):
        raise PinPreflightError("enlace: debe ser URL HTTPS sin espacios ni controles")
    try:
        parsed = urlsplit(link)
        port = parsed.port
    except (ValueError, TypeError) as exc:
        raise PinPreflightError("enlace: URL malformada") from exc
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username is not None or parsed.password is not None or
            port is not None):
        raise PinPreflightError("enlace: solo HTTPS con host, sin credenciales ni puerto")
