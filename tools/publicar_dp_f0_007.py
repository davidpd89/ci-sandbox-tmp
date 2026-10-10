#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica DP-F0-007: "Un libro en una caseta no se vende solo"
Foto real de la Feria del Libro de Madrid 2026, caseta 337
Fecha: 2026-06-26T18:00:00+02:00 (jueves, slot tarde)
Post de autor/proceso: humanizar la cuenta con evento real
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"

<<<<<<< HEAD
IMAGE_URL = "https://autorademodiaz.com/assets/eventos/samuel-entre-mundos-feria-libro-madrid-2026-caseta-337.webp"
=======
IMAGE_URL = "https://davidportodiaz.com/assets/eventos/samuel-entre-mundos-feria-libro-madrid-2026-caseta-337.webp"
>>>>>>> origin/research/public-reuse-parent
FECHA = "2026-06-26T18:00:00+02:00"

CAPTION_IG = """Un libro en una caseta no se vende solo.

Primero está la mesa.
Luego la portada.
Luego alguien que pasa, mira un segundo más de lo normal y pregunta:

"¿De qué va?"

Ese momento parece pequeño, pero para un autor debut sostiene mucho.

Porque entonces el libro deja de ser una ficha, una web o un archivo.
Pasa a ser una conversación.

Samuel entre mundos estuvo en la Feria del Libro de Madrid 2026, caseta 337.

Y yo sigo aprendiendo a explicar una historia sin quitarle el misterio.

<<<<<<< HEAD
La crónica y más sobre el libro están en autorademodiaz.com.

#AutoraDemoDiaz #SamuelEntreMundos #FeriaDelLibroMadrid #FantasiaEspanola #VidaDeAutor"""
=======
La crónica y más sobre el libro están en davidportodiaz.com.

#DavidPortoDiaz #SamuelEntreMundos #FeriaDelLibroMadrid #FantasiaEspanola #VidaDeAutor"""
>>>>>>> origin/research/public-reuse-parent

CAPTION_FB = """Un libro en una caseta no se vende solo.

Primero está la mesa. Luego la portada. Luego alguien que pasa, mira un segundo más de lo normal y pregunta: "¿De qué va?"

Samuel entre mundos estuvo en la Feria del Libro de Madrid 2026, caseta 337. Para un autor debut, esos momentos pequeños sostienen mucho.

<<<<<<< HEAD
https://autorademodiaz.com
=======
https://davidportodiaz.com
>>>>>>> origin/research/public-reuse-parent

#SamuelEntreMundos #FeriaDelLibroMadrid"""


def mcp_call(name, args):
    token = get_valid_token()
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": args}
    }).encode()
    req = urllib.request.Request(MCP, data=body,
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        method="POST")
    raw = urllib.request.urlopen(req, timeout=30).read().decode()
    try:
        return json.loads(raw).get("result", {})
    except:
        for line in raw.split("\n"):
            if line.startswith("data:"):
                d = line[5:].strip()
                if d and d != "[DONE]":
                    return json.loads(d).get("result", {})
    return {}


print("=== PUBLICANDO DP-F0-007 en INSTAGRAM ===")
print(f"Imagen: {IMAGE_URL}")
print(f"Fecha:  {FECHA}")
result_ig = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": FECHA,
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [IMAGE_URL],
        "providers": [{"network": "instagram"}],
        "publicationDate": {
            "dateTime": "2026-06-26T18:00:00",
            "timezone": "Europe/Madrid"
        },
        "text": CAPTION_IG,
        "instagramData": {"type": "POST", "showReelOnFeed": False},
        "descendants": []
    })
})
print(json.dumps(result_ig, indent=2, ensure_ascii=False))

print("\n=== PUBLICANDO DP-F0-007 en FACEBOOK ===")
result_fb = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": FECHA,
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [IMAGE_URL],
        "providers": [{"network": "facebook"}],
        "publicationDate": {
            "dateTime": "2026-06-26T18:00:00",
            "timezone": "Europe/Madrid"
        },
        "text": CAPTION_FB,
        "facebookData": {"type": "POST"},
        "descendants": []
    })
})
print(json.dumps(result_fb, indent=2, ensure_ascii=False))
