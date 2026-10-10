#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica DP-F0-003: "Un objeto magico no es poderoso por brillar"
Imagen: medallon real de Samuel entre mundos
Fecha: 2026-06-24T11:00:00+02:00 (martes, mejor dia segun datos FB)
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"

IMAGE_URL = "https://davidportodiaz.com/assets/david-porto-medallon.webp"

CAPTION_IG = """Un objeto mágico no es poderoso por brillar.

Es poderoso si recuerda.
Si exige.
Si cambia la forma en que alguien decide.

En fantasía, los mejores objetos no son accesorios: son preguntas que caben en la mano.

Una llave.
Una medalla.
Un reloj.
Una puerta.

Lo importante no es que parezcan mágicos.
Es que, cuando aparecen, ya nada pueda seguir exactamente igual.

¿Qué objeto mágico recuerdas mejor de una novela?

Más fantasía con coste y objetos con memoria en davidportodiaz.com.

#FantasiaEspanola #PortalFantasy #ObjetosMagicos #SamuelEntreMundos #Noveris"""

CAPTION_FB = """Un objeto mágico no es poderoso por brillar.

Para mí, funciona cuando guarda memoria, exige algo o cambia una decisión. Una llave, una medalla, un reloj, una puerta: lo importante no es que parezcan mágicos, sino que al aparecer cambien la historia.

En Samuel entre mundos, los objetos con memoria y los canalizadores forman parte de esa lógica: la magia no es decorado, tiene coste.

¿Qué objeto mágico recuerdas mejor de una novela?

https://davidportodiaz.com

#FantasiaEspanola #SamuelEntreMundos"""


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


# Instagram usa caption propio; Facebook usa caption diferente (con URL y menos hashtags)
# Metricool permite texto diferente por red via descendants o providers con texto propio.
# La API no soporta texto distinto por red en un solo createScheduledPost.
# Solución: publicar dos posts separados, uno por red.

print("=== PUBLICANDO DP-F0-003 en INSTAGRAM ===")
result_ig = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": "2026-06-24T11:00:00+02:00",
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [IMAGE_URL],
        "providers": [{"network": "instagram"}],
        "publicationDate": {
            "dateTime": "2026-06-24T11:00:00",
            "timezone": "Europe/Madrid"
        },
        "text": CAPTION_IG,
        "instagramData": {"type": "POST", "showReelOnFeed": True},
        "descendants": []
    })
})
print(json.dumps(result_ig, indent=2, ensure_ascii=False))

print("\n=== PUBLICANDO DP-F0-003 en FACEBOOK ===")
result_fb = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": "2026-06-24T11:00:00+02:00",
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [IMAGE_URL],
        "providers": [{"network": "facebook"}],
        "publicationDate": {
            "dateTime": "2026-06-24T11:00:00",
            "timezone": "Europe/Madrid"
        },
        "text": CAPTION_FB,
        "facebookData": {"type": "POST"},
        "descendants": []
    })
})
print(json.dumps(result_fb, indent=2, ensure_ascii=False))
