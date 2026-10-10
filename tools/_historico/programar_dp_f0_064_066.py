#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Programa DP-F0-064 (gato), 065 (glaciar/volcan), 066 (noria) en huecos reales de 07-10/11/12."""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"
BASE = "https://davidpd89.github.io/rrss-davidporto-media"


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


def create(network, date, media, text, extra=None):
    info = {
        "autoPublish": True, "draft": False,
        "media": media,
        "providers": [{"network": network}],
        "publicationDate": {"dateTime": date, "timezone": "Europe/Madrid"},
        "text": text,
    }
    if extra:
        info.update(extra)
    r = mcp_call("createScheduledPost", {"blogId": BRAND_ID, "date": date + "+02:00", "info": json.dumps(info)})
    print(network, date, str(r)[:250])
    return r


GATO = f"{BASE}/videos/DP-F0-064-gato-otra-vida/reel.mp4"
GLACIAR = f"{BASE}/videos/DP-F0-065-glaciar-volcan/reel.mp4"
NORIA = f"{BASE}/videos/DP-F0-066-noria-ciclo-vida/reel.mp4"

CAPTION_GATO = "Si la reencarnación existe, ya sé a qué le pongo cara. ¿Cuál sería la vuestra? 🐱\n\n#identificacion #humor #reflexion #davidportodiaz"
CAPTION_GLACIAR = "Hay gente que parece tranquila y por dentro lleva un incendio entero. ¿Te ha pasado, o conoces a alguien así?\n\n#reflexion #saludmental #identificacion #davidportodiaz"
CAPTION_NORIA = "A veces sentimos que damos vueltas sin avanzar. Pero creo que cada vuelta deja algo. ¿Vosotros qué pensáis?\n\n#reflexion #crecimientopersonal #identificacion #davidportodiaz"

# DP-F0-064 - gato - 2026-07-10 (huecos reales: tiktok solo tenia 1, threads/bluesky vacios)
create("tiktok", "2026-07-10T19:00:00", [GATO], CAPTION_GATO, {
    "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": "En otra vida, pido siesta", "photoCoverIndex": 0}
})
create("threads", "2026-07-10T10:00:00", [GATO], CAPTION_GATO)
create("bluesky", "2026-07-10T22:00:00", [GATO], CAPTION_GATO)

# DP-F0-065 - glaciar/volcan - 2026-07-11 (huecos reales: ig/fb/tiktok solo tenian 1, threads/bluesky vacios)
create("instagram", "2026-07-11T16:30:00", [GLACIAR], CAPTION_GLACIAR, {"instagramData": {"autoPublish": True, "type": "REEL", "showReelOnFeed": True}})
create("facebook", "2026-07-11T19:00:00", [GLACIAR], CAPTION_GLACIAR, {"facebookData": {"type": "REEL"}})
create("tiktok", "2026-07-11T09:30:00", [GLACIAR], CAPTION_GLACIAR, {
    "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": "Por fuera hielo, por dentro incendio", "photoCoverIndex": 0}
})
create("threads", "2026-07-11T13:00:00", [GLACIAR], CAPTION_GLACIAR)
create("bluesky", "2026-07-11T21:30:00", [GLACIAR], CAPTION_GLACIAR)

# DP-F0-066 - noria - 2026-07-12 (mismo patron de huecos que 07-11)
create("instagram", "2026-07-12T16:30:00", [NORIA], CAPTION_NORIA, {"instagramData": {"autoPublish": True, "type": "REEL", "showReelOnFeed": True}})
create("facebook", "2026-07-12T19:00:00", [NORIA], CAPTION_NORIA, {"facebookData": {"type": "REEL"}})
create("tiktok", "2026-07-12T09:30:00", [NORIA], CAPTION_NORIA, {
    "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": "No era repetir, era aprender la vuelta", "photoCoverIndex": 0}
})
create("threads", "2026-07-12T13:00:00", [NORIA], CAPTION_NORIA)
create("bluesky", "2026-07-12T21:30:00", [NORIA], CAPTION_NORIA)
