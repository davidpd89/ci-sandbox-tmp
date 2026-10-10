"""Semillas Pinterest y normalización de imágenes v5; funciones puras sin red.

La selección de la imagen mayor adapta Pin.max_resolution_image_url de
pinterest/api-quickstart, python/src/pin.py, commit
592b4bacd85e5bb483bef2e2145aa841ae37ac5a (Apache-2.0).
Cambio: se usa área en píxeles, validación explícita y desempate estable.
Fuente: https://github.com/pinterest/api-quickstart/blob/592b4bacd85e5bb483bef2e2145aa841ae37ac5a/python/src/pin.py
"""
from __future__ import annotations

import unicodedata
from urllib.parse import urlsplit

# Consultas de intención lectora; no implican que una novela real tenga el tropo.
DISCOVERY_QUERIES = (
    "romantasy libros recomendados",
    "fantasía romántica juvenil libros en español",
    "enemies to lovers fantasía libros",
    "enemigos a amantes fantasía juvenil",
    "slow burn fantasía romántica libros",
    "found family novelas de fantasía",
    "academia mágica libros de fantasía",
    "libros de fantasía con dragones",
    "portal fantasy libros en español",
    "fantasía juvenil autora española",
    "libros de fantasía con protagonistas femeninas",
    "mapas de mundos de fantasía novelas",
    "club de lectura romantasy en español",
    "reseñas fantasía romántica en español",
    "recomendaciones de libros de magia",
    "fantasía oscura juvenil libros",
    "romance y magia novelas juveniles",
    "moodboard de libros de fantasía",
    "si te gustó Cuarta Ala libros fantasía",
    "libros de fantasía sin romance",
)


def merge_queries(current, additions=DISCOVERY_QUERIES):
    """Conserva las consultas existentes, deduplica Unicode y no altera cuotas."""
    out, seen = [], set()
    for item in current:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError("cada consulta debe ser (texto, metadato)")
        text, tag = item
        if not isinstance(text, str):
            raise ValueError("consulta no textual")
        clean = " ".join(unicodedata.normalize("NFKC", text).split())
        if not clean:
            continue
        key = clean.casefold()
        if key not in seen:
            out.append((clean, tag))
            seen.add(key)
    for text in additions:
        clean = " ".join(unicodedata.normalize("NFKC", text).split())
        if clean and clean.casefold() not in seen:
            out.append((clean, None))
            seen.add(clean.casefold())
    return out


def largest_image(pin):
    """Imagen verificable con mayor superficie: (url, width, height) o None.

    Adaptado del recorrido de `media.images` de Pinterest API Quickstart.
    Los metadatos no prueban legibilidad ni originalidad del contenido.
    """
    if not isinstance(pin, dict):
        return None
    media = pin.get("media")
    images = media.get("images") if isinstance(media, dict) else None
    if not isinstance(images, dict):
        return None
    valid = []
    for image in images.values():
        if not isinstance(image, dict):
            continue
        width, height, url = image.get("width"), image.get("height"), image.get("url")
        if type(width) is not int or type(height) is not int or not 0 < width <= 30000 or not 0 < height <= 30000:
            continue
        if not isinstance(url, str):
            continue
        try:
            parsed = urlsplit(url)
            good = (parsed.scheme == "https" and parsed.hostname == "i.pinimg.com"
                    and parsed.username is None and parsed.password is None and parsed.port is None)
        except ValueError:
            good = False
        if good:
            valid.append((width * height, width, height, url))
    if not valid:
        return None
    _, w, h, url = max(valid, key=lambda v: (v[0], v[1], v[2], v[3]))
    return (url, w, h)
