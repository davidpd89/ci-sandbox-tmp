#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reintenta los posts fallidos (Pinterest sin board, TikTok sin titulo) de DP-F0-060/061/062/063."""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"
BASE = "https://davidpd89.github.io/rrss-davidporto-media"
BOARD_ID = "1096626646706067800"


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
    print(network, date, str(r)[:300])
    return r


MEME = f"{BASE}/images/DP-F0-060-meme-cabras/meme.jpg"
RUN = f"{BASE}/videos/DP-F0-061-mujer-corriendo/reel.mp4"
WALL = f"{BASE}/videos/DP-F0-062-pared-mensajes/reel.mp4"
PLUMA = f"{BASE}/videos/DP-F0-0XX-pluma-otros-mundos/reel.mp4"

CAPTION_MEME = "A veces el norte no es tan tranquilo como parece 👀 ¿Le pondríais una historia de fantasía a esto, o solo yo veo ahí un villano esperando su turno? Contadme en comentarios.\n\n#fantasiaepica #humorliterario #bookstagram #literaturafantastica #davidportodiaz"
CAPTION_RUN = "Hay huidas que no se notan, porque no te mueves del sitio. ¿Cuál es la tuya? Te leo 👇\n\n#reflexion #literaturaemocional #identificacion #escritorespañol #davidportodiaz"
CAPTION_WALL = "Llevo tiempo pensando en una frase que nunca llegué a decir. ¿Y tú? Cuéntamela en comentarios, prometo leerlas todas.\n\n#reflexion #frasesquequedan #escrituraemocional #procesocreativo #davidportodiaz"
CAPTION_PLUMA = "Cada vez que me siento a escribir, algo se escapa de la página. Esta vez fue un dragón, un barco entero y una galaxia. ¿Qué crees que se te escaparía a ti si abrieras un tintero ahora mismo? Te leo 👇\n\n#fantasiaepica #mundosdefantasia #literaturafantastica #escrituracreativa #davidportodiaz"

# Pinterest meme (faltaba boardId/pinTitle/pinLink)
create("pinterest", "2026-06-29T15:00:00", [MEME], CAPTION_MEME, {
    "pinterestData": {
        "boardId": BOARD_ID,
        "pinTitle": "¿Paisaje del norte o presagio del infierno?",
        "pinLink": "https://davidportodiaz.com",
        "pinNewFormat": False,
    }
})

# TikTok (faltaba tiktokData.title)
create("tiktok", "2026-06-30T14:30:00", [RUN], CAPTION_RUN, {
    "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": "Corro y corro y nunca llego", "photoCoverIndex": 0}
})
create("tiktok", "2026-07-01T16:00:00", [WALL], CAPTION_WALL, {
    "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": "Frases que nunca dijiste", "photoCoverIndex": 0}
})
create("tiktok", "2026-07-02T16:00:00", [PLUMA], CAPTION_PLUMA, {
    "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": "La pluma que escribe otros mundos", "photoCoverIndex": 0}
})
