#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica DP-F0-034: "Decir 'solo un capitulo mas' a las 23:50 es mentirle a mi propio cuerpo."
Reel largo (16.5s): 2 escenas animadas con Meta AI (mano pasando pagina, libro
en plano medio) + 2 escenas con Ken Burns local (videopython). Imagen base
generada con Meta AI a partir de una foto real de Pexels (lampara+libro+
cuaderno de noche). Musica Mixkit (mood relaxed).
Fecha: 2026-07-05 (domingo), hueco real vacio en el calendario.
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"

VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-034-capitulo-mas/DP-F0-034-capitulo-mas.mp4"

CAPTION_IG = """¿A qué hora te has rendido tú la última vez? Cuéntamela, quiero comparar récords.

#bookstagram #bookishhumor #bookaddicted #leoporquequiero #booktokespañol"""

CAPTION_FB = """¿A qué hora te rendiste tú la última vez leyendo "solo un poco más"?

https://davidportodiaz.com

#bookstagram"""

CAPTION_TT = """¿A qué hora te rendiste tú la última vez? Te leo en comentarios \U0001f447

#booktok #booktokespañol #leoporquequiero #fyp"""


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


print("=== PUBLICANDO DP-F0-034 en INSTAGRAM (REEL) ===")
result_ig = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": "2026-07-05T11:00:00+02:00",
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [VIDEO_URL],
        "providers": [{"network": "instagram"}],
        "publicationDate": {"dateTime": "2026-07-05T11:00:00", "timezone": "Europe/Madrid"},
        "text": CAPTION_IG,
        "instagramData": {"autoPublish": True, "type": "REEL", "showReelOnFeed": True},
        "descendants": []
    })
})
print(json.dumps(result_ig, indent=2, ensure_ascii=False))

print("\n=== PUBLICANDO DP-F0-034 en FACEBOOK (REEL) ===")
result_fb = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": "2026-07-05T12:30:00+02:00",
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [VIDEO_URL],
        "providers": [{"network": "facebook"}],
        "publicationDate": {"dateTime": "2026-07-05T12:30:00", "timezone": "Europe/Madrid"},
        "text": CAPTION_FB,
        "facebookData": {"type": "REEL"},
        "descendants": []
    })
})
print(json.dumps(result_fb, indent=2, ensure_ascii=False))

print("\n=== PUBLICANDO DP-F0-034 en TIKTOK ===")
result_tt = mcp_call("createScheduledPost", {
    "blogId": BRAND_ID,
    "date": "2026-07-05T19:30:00+02:00",
    "info": json.dumps({
        "autoPublish": True,
        "draft": False,
        "media": [VIDEO_URL],
        "providers": [{"network": "tiktok"}],
        "publicationDate": {"dateTime": "2026-07-05T19:30:00", "timezone": "Europe/Madrid"},
        "text": CAPTION_TT,
        "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": "Solo un capitulo mas a las 23:50", "photoCoverIndex": 0},
        "descendants": []
    })
})
print(json.dumps(result_tt, indent=2, ensure_ascii=False))
