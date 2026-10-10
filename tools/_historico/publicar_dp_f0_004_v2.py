#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica DP-F0-004 v2: "Tres senales de que una magia tiene coste"
Carrusel de 5 slides generado con el sistema definitivo
(tools/carousel_template/) -- fotos reales de Unsplash + HTML/CSS/Playwright,
NO Canva generate-design.

La version anterior (con ilustracion IA de Canva) fue borrada manualmente
por David de Instagram y Facebook. Esta es la sustitucion con texto e
imagenes mejoradas.

Fecha: 2026-06-21T23:55:00+02:00 (publicacion inmediata a peticion de David)
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"
FECHA = "2026-06-21T23:55:00+02:00"

CAROUSEL_IMAGES = [
    "https://files.catbox.moe/owgesz.png",
    "https://files.catbox.moe/f3w47f.png",
    "https://files.catbox.moe/bzo4pv.png",
    "https://files.catbox.moe/4s8x2c.png",
    "https://files.catbox.moe/ogb2qp.png",
]

CAPTION_IG = """La magia se vuelve más interesante cuando no funciona como un atajo.

Si todo se resuelve con un gesto o una luz bonita, el conflicto desaparece demasiado pronto.

Para mí, una magia con coste real cumple tres señales:

1. Usarla deja consecuencias.
2. No todos pueden pagar el mismo precio.
3. La decisión importa más que el efecto.

En Samuel entre mundos, Noveris funciona así: los canalizadores no son adornos, cada desplazamiento de energía exige una compensación real.

¿Prefieres una magia con reglas claras o una magia casi sin límites?

Guarda este carrusel si quieres volver a estas claves antes de escribir o leer tu próxima fantasía. Más sobre Noveris en davidportodiaz.com.

#FantasiaEspanola #PortalFantasy #FantasiaJuvenil #LibrosDeFantasia #Bookstagram #SamuelEntreMundos #Noveris"""

CAPTION_FB = """La magia se vuelve más interesante cuando no funciona como un atajo.

Tres señales de que una magia tiene coste real:
1. Usarla deja consecuencias.
2. No todos pueden pagar el mismo precio.
3. La decisión importa más que el efecto.

En Samuel entre mundos, Noveris funciona así: los canalizadores no son adornos, cada desplazamiento de energía exige una compensación real.

¿Prefieres una magia con reglas claras o casi sin límites?

https://davidportodiaz.com

#FantasiaEspanola #PortalFantasy"""


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
    raw = urllib.request.urlopen(req, timeout=60).read().decode()
    try:
        return json.loads(raw).get("result", {})
    except:
        for line in raw.split("\n"):
            if line.startswith("data:"):
                d = line[5:].strip()
                if d and d != "[DONE]":
                    return json.loads(d).get("result", {})
    return {}


print("=== PUBLICANDO DP-F0-004 v2 (carrusel 5 slides) en INSTAGRAM ===")
result_ig = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": FECHA,
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": CAROUSEL_IMAGES,
        "providers": [{"network": "instagram"}],
        "publicationDate": {"dateTime": "2026-06-21T23:55:00", "timezone": "Europe/Madrid"},
        "text": CAPTION_IG,
        "instagramData": {"type": "POST"},
        "descendants": []
    })
})
print(json.dumps(result_ig, indent=2, ensure_ascii=False))

print("\n=== PUBLICANDO DP-F0-004 v2 (carrusel 5 slides) en FACEBOOK ===")
result_fb = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": FECHA,
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": CAROUSEL_IMAGES,
        "providers": [{"network": "facebook"}],
        "publicationDate": {"dateTime": "2026-06-21T23:55:00", "timezone": "Europe/Madrid"},
        "text": CAPTION_FB,
        "facebookData": {"type": "POST"},
        "descendants": []
    })
})
print(json.dumps(result_fb, indent=2, ensure_ascii=False))
