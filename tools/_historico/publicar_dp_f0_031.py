#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica DP-F0-031: "Capitulo cancelado por el gato"
Reel largo (16.5s): 2 escenas animadas con Meta AI (cara/cuerpo del gato,
sin texto en cuadro) + 2 escenas con Ken Burns local (videopython, primer
uso real en produccion) sobre el plano que SI lleva texto (marcapaginas),
para no arriesgar la tipografia. Musica Mixkit (mood happy).
Fecha: 2026-07-01 (miercoles), sustituye a DP-F0-029 IG de ese dia.
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"

VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-031-gato-capitulo/DP-F0-031-gato-capitulo.mp4"

CAPTION_IG = """¿Cuál fue la última excusa real que te impidió terminar un capítulo? Cuéntamela, voy anotando motivos.

#bookstagram #bookishhumor #bookaddicted #bookhumor #leoporquequiero"""

CAPTION_FB = """¿Qué fue lo último que te interrumpió justo en la mejor parte de un libro? Cuéntame.

https://davidportodiaz.com

#bookstagram"""

CAPTION_TT = """¿Qué te interrumpe siempre justo en la mejor parte de un libro? Te leo en comentarios \U0001f447

#bookstagram #booktokespañol #leoporquequiero #fyp"""


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
    except Exception:
        for line in raw.split("\n"):
            if line.startswith("data:"):
                d = line[5:].strip()
                if d and d != "[DONE]":
                    return json.loads(d).get("result", {})
    return {}


print("=== PUBLICANDO DP-F0-031 en INSTAGRAM (REEL) ===")
result_ig = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": "2026-07-01T11:00:00+02:00",
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [VIDEO_URL],
        "providers": [{"network": "instagram"}],
        "publicationDate": {"dateTime": "2026-07-01T11:00:00", "timezone": "Europe/Madrid"},
        "text": CAPTION_IG,
        "instagramData": {"autoPublish": True, "type": "REEL", "showReelOnFeed": True},
        "descendants": []
    })
})
print(json.dumps(result_ig, indent=2, ensure_ascii=False))

print("\n=== PUBLICANDO DP-F0-031 en FACEBOOK (REEL) ===")
result_fb = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": "2026-07-01T12:30:00+02:00",
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [VIDEO_URL],
        "providers": [{"network": "facebook"}],
        "publicationDate": {"dateTime": "2026-07-01T12:30:00", "timezone": "Europe/Madrid"},
        "text": CAPTION_FB,
        "facebookData": {"type": "REEL"},
        "descendants": []
    })
})
print(json.dumps(result_fb, indent=2, ensure_ascii=False))

print("\n=== PUBLICANDO DP-F0-031 en TIKTOK ===")
result_tt = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": "2026-07-01T19:30:00+02:00",
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [VIDEO_URL],
        "providers": [{"network": "tiktok"}],
        "publicationDate": {"dateTime": "2026-07-01T19:30:00", "timezone": "Europe/Madrid"},
        "text": CAPTION_TT,
        "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": "Capitulo cancelado por el gato", "photoCoverIndex": 0},
        "descendants": []
    })
})
print(json.dumps(result_tt, indent=2, ensure_ascii=False))
