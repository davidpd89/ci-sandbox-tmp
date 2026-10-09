"""
Busca clips de video reales en Pexels Video y Pixabay Video via su API
oficial (clave en .env) - sustituye el scraping de Mixkit via Playwright
(funcionaba, pero es manual y da solo 720p). La API da hasta 4K.

Uso:
    python search_videos.py "old library shelves" [n_resultados]

Sigue haciendo falta ver un frame del clip antes de usarlo (igual que con
Mixkit) - la busqueda por palabra clave no garantiza el tono/composicion.
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
    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page={n}"
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    results = []
    for v in data.get("videos", []):
        best = max(v["video_files"], key=lambda f: f.get("width") or 0)
        results.append({"source": "pexels", "id": v["id"], "width": best["width"],
                         "height": best["height"], "url": best["link"]})
    return results


def search_pixabay(query, n):
    key = load_key("PIXABAY_API_KEY")
    n = max(n, 3)  # Pixabay exige per_page entre 3 y 200
    url = f"https://pixabay.com/api/videos/?key={key}&q={urllib.parse.quote(query)}&per_page={n}"
    data = json.loads(urllib.request.urlopen(url, timeout=15).read())
    results = []
    for h in data.get("hits", []):
        v = h["videos"].get("large") or h["videos"].get("medium")
        results.append({"source": "pixabay", "id": h["id"], "width": v["width"],
                         "height": v["height"], "url": v["url"]})
    return results


def main():
    query = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    results = search_pexels(query, n) + search_pixabay(query, n)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
