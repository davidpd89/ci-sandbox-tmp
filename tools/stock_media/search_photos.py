"""
Busca fotos reales en Pexels y Pixabay via su API oficial (con clave en .env,
PEXELS_API_KEY / PIXABAY_API_KEY) - sustituye depender de que WebFetch
resuma bien una busqueda de Unsplash. Mas fiable: API oficial, no scraping.

Uso:
    python search_photos.py "old book warm light" [n_resultados]

Sigue haciendo falta revisar las fotos a tamano completo (Read) antes de
montar nada - la API no garantiza que la foto encaje con el tono pedido.
"""
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

ENV_PATH = Path(__file__).parent.parent.parent / ".env"


def load_key(name):
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{name} no encontrada en {ENV_PATH}")


def search_pexels(query, n):
    key = load_key("PEXELS_API_KEY")
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page={n}"
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    return [
        {"source": "pexels", "id": p["id"], "width": p["width"], "height": p["height"],
         "url": p["src"]["large2x"], "photographer": p["photographer"]}
        for p in data.get("photos", [])
    ]


def search_pixabay(query, n):
    key = load_key("PIXABAY_API_KEY")
    n = max(n, 3)  # Pixabay exige per_page entre 3 y 200
    url = f"https://pixabay.com/api/?key={key}&q={urllib.parse.quote(query)}&image_type=photo&per_page={n}"
    data = json.loads(urllib.request.urlopen(url, timeout=15).read())
    return [
        {"source": "pixabay", "id": h["id"], "width": h["imageWidth"], "height": h["imageHeight"],
         "url": h["largeImageURL"], "photographer": h["user"]}
        for h in data.get("hits", [])
    ]


def main():
    query = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    results = search_pexels(query, n) + search_pixabay(query, n)
    print(json.dumps(results, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
