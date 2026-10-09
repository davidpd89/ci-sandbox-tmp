"""Comprueba si un fragmento de texto ya se ha usado en alguna respuesta,
cita o post propio en CUALQUIERA de las nueve redes (X, Threads, Bluesky,
Reddit, Instagram, TikTok, Facebook, Mastodon, Pinterest) - no solo en la
red donde se va a publicar ahora.

Por que existe: cada red tiene su propio registro_interacciones.csv y hasta
ahora cada sistema (SISTEMA_DIARIO_X, SISTEMA_DIARIO_THREADS,
SISTEMA_DIARIO_BLUESKY, SISTEMA_DIARIO_REDDIT, SISTEMA_DIARIO_INSTAGRAM,
SISTEMA_DIARIO_TIKTOK, SISTEMA_DIARIO_FACEBOOK, SISTEMA_DIARIO_MASTODON,
SISTEMA_DIARIO_PINTEREST) solo comprobaba el suyo antes de redactar. Pero la
voz es la misma persona en las tres - si la misma frase concreta ("una
respuesta que podria pegarse en veinte posts distintos" es justo lo que hay
que evitar, ver BLUESKY.md 6.1) aparece igual en dos redes, cualquiera que
siga a David en ambas lo nota, y a ojos de un sistema de deteccion de
patrones repetidos cuenta como plantilla aunque haya sido codo con codo
David quien la aprobo cada vez. Un lector real nunca reconoceria "un
sistema", pero una frase copiada literal si es reconocible.

Uso:
    python check_duplicate_phrase.py "fragmento de texto o frase completa"

Busca coincidencia por subcadena de al menos 25 caracteres (no exige el
texto completo identico - una frase de remate reutilizada aunque el resto
cambie ya cuenta como plantilla) en los tres registro_interacciones.csv.
Salida clara: en que fichero, que fila, que fecha - para decidir si hay que
reescribir antes de aprobar."""
import csv
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
REGISTROS = {
    "X": os.path.join(ROOT, "SISTEMA_DIARIO_X", "registro_interacciones.csv"),
    "Threads": os.path.join(ROOT, "SISTEMA_DIARIO_THREADS", "registro_interacciones.csv"),
    "Bluesky": os.path.join(ROOT, "SISTEMA_DIARIO_BLUESKY", "registro_interacciones.csv"),
    "Reddit": os.path.join(ROOT, "SISTEMA_DIARIO_REDDIT", "registro_interacciones.csv"),
    "Instagram": os.path.join(ROOT, "SISTEMA_DIARIO_INSTAGRAM", "registro_interacciones.csv"),
    "TikTok": os.path.join(ROOT, "SISTEMA_DIARIO_TIKTOK", "registro_interacciones.csv"),
    "Facebook": os.path.join(ROOT, "SISTEMA_DIARIO_FACEBOOK", "registro_interacciones.csv"),
    "Mastodon": os.path.join(ROOT, "SISTEMA_DIARIO_MASTODON", "registro_interacciones.csv"),
    "Pinterest": os.path.join(ROOT, "SISTEMA_DIARIO_PINTEREST", "registro_interacciones.csv"),
}

MIN_CHUNK = 25


def _chunks(text, size=MIN_CHUNK):
    text = text.strip()
    if len(text) <= size:
        return [text]
    return [text[i:i + size] for i in range(0, len(text) - size + 1, 8)]


def check(candidate):
    hits = []
    for red, path in REGISTROS.items():
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                used = (row.get("texto_usado") or "").strip()
                if not used:
                    continue
                for chunk in _chunks(candidate):
                    if chunk and chunk.lower() in used.lower():
                        hits.append((red, row.get("fecha"), row.get("cuenta"), used))
                        break
    return hits


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    candidate = sys.argv[1]
    hits = check(candidate)
    if not hits:
        print("OK: no se encontro solape con ningun texto ya usado en X/Threads/Bluesky/Reddit/Instagram/TikTok/Facebook/Mastodon/Pinterest.")
    else:
        print(f"AVISO: {len(hits)} coincidencia(s) - revisar antes de aprobar:")
        for red, fecha, cuenta, used in hits:
            print(f"  [{red}] {fecha} -> {cuenta}: {used[:150]}")
