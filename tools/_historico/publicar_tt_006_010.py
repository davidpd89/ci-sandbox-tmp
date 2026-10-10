#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica TT-006 a TT-010: 5 reels de TikTok para llenar el hueco real
(IG/FB ya estaban a 2/dia 25-28 jun, TikTok solo tenia 0-1/dia).
Banco de frases: 12_Metodo_y_recursos_IA/01_laboratorio_humano/shortlist_alto_impacto_v1.md
Ritmo nuevo: 3.5s/escena (antes 4.5s) tras feedback de David.
Horas variadas (mañana temprano + noche), no solo 11-22h.
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"
BASE = "https://davidpd89.github.io/rrss-davidporto-media/videos"


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


PIECES = [
    {
        "name": "TT-006-villano-razon",
        "date": "2026-06-25T08:30:00",
        "title": "El villano que tenia demasiada razon",
        "text": "¿Qué villano de un libro te hizo dudar de quién tenía razón? Te leo en comentarios 👇\n\n#fantasiaespañola #worldbuilding #bookstagram #booktok #fyp",
    },
    {
        "name": "TT-007-frase-subraya",
        "date": "2026-06-25T22:00:00",
        "title": "La frase que te subraya a ti",
        "text": "¿Qué frase te ha subrayado a ti alguna vez, en vez de subrayarla tú? Cuéntamela 👇\n\n#frasesdelibros #bookstagram #frases #booktok #fyp",
    },
    {
        "name": "TT-008-cerrar-libro",
        "date": "2026-06-26T08:00:00",
        "title": "Cierras el libro un momento",
        "text": "¿Qué escena te hizo cerrar el libro un momento? Te leo en comentarios 👇\n\n#bookstagram #frasesdelibros #booktokespañol #fyp",
    },
    {
        "name": "TT-009-mapa-promete",
        "date": "2026-06-27T07:30:00",
        "title": "El mapa que promete mas de lo que da",
        "text": "¿Tú también miras el mapa antes de empezar a leer, aunque sabes que promete de más? Cuéntamelo 👇\n\n#fantasiaespañola #worldbuilding #bookstagram #fyp",
    },
    {
        "name": "TT-010-marcapaginas-abandonos",
        "date": "2026-06-28T06:45:00",
        "title": "Mi marcapaginas sabe mas que mis amigos",
        "text": "¿Cuántos libros a medias tienes ahora mismo? Te leo en comentarios 👇\n\n#bookstagram #bookishhumor #leoporquequiero #fyp",
    },
]

for p in PIECES:
    video_url = f"{BASE}/{p['name']}/{p['name']}.mp4"
    print(f"=== PUBLICANDO {p['name']} ===")
    result = mcp_call("createScheduledPost", {
        "blogId": BRAND_ID,
        "date": p["date"] + "+02:00",
        "info": json.dumps({
            "autoPublish": True,
            "draft": False,
            "media": [video_url],
            "providers": [{"network": "tiktok"}],
            "publicationDate": {"dateTime": p["date"], "timezone": "Europe/Madrid"},
            "text": p["text"],
            "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": p["title"], "photoCoverIndex": 0},
            "descendants": []
        })
    })
    print(json.dumps(result, indent=2, ensure_ascii=False))
