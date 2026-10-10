#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige TT-006 a TT-010: video propio (no banco de clips reutilizado) +
caption con estructura distinta cada vez (no la misma plantilla "Que X te
hizo Y? Te leo en comentarios"). Fuerza a Metricool a releer el media nuevo.
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


JOBS = [
    {
        "id": "341479238", "uuid": "1083719962820822078",
        "date": "2026-06-25T08:30:00",
        "video": f"{BASE}/TT-006-villano-v2/TT-006-villano-v2.mp4",
        "title": "El villano que tenia demasiada razon",
        "text": "Los villanos con razón son los que más me incomodan. ¿A ti cuál te ha hecho dudar de quién tenía razón?\n\n#fantasiaespañola #worldbuilding #bookstagram #booktok #fyp",
    },
    {
        "id": "341479242", "uuid": "-3562286430676955615",
        "date": "2026-06-25T22:00:00",
        "video": f"{BASE}/TT-007-subraya-v2/TT-007-subraya-v2.mp4",
        "title": "La frase que te subraya a ti",
        "text": "Hay frases que no olvidas aunque no las subrayaste. Mi turno: la dejo en comentarios, dime la tuya.\n\n#frasesdelibros #bookstagram #frases #booktok #fyp",
    },
    {
        "id": "341479250", "uuid": "4049477313369360838",
        "date": "2026-06-26T08:00:00",
        "video": f"{BASE}/TT-008-viaje/TT-008-viaje.mp4",
        "title": "El heroe que no queria el viaje",
        "text": "El elegido que acepta el viaje sin dudar me aburre un poco. El que no quería irse y aun así se quedó, ese sí me interesa. ¿Tienes uno?\n\n#fantasiaespañola #worldbuilding #librosdefantasia #booktok #fyp",
    },
    {
        "id": "341479254", "uuid": "-9183002557269127774",
        "date": "2026-06-27T07:30:00",
        "video": f"{BASE}/TT-009-mapa-v2/TT-009-mapa-v2.mp4",
        "title": "El mapa que promete mas de lo que da",
        "text": "Confieso: miro el mapa antes de leer aunque sé que casi nunca cumple lo que promete. ¿Solo me pasa a mí?\n\n#fantasiaespañola #worldbuilding #bookstagram #fyp",
    },
    {
        "id": "341479260", "uuid": "-2862938440900785441",
        "date": "2026-06-28T06:45:00",
        "video": f"{BASE}/TT-010-abandonos-v2/TT-010-abandonos-v2.mp4",
        "title": "Mi marcapaginas sabe mas que mis amigos",
        "text": "Cada marcapáginas de mi casa marca un libro sin terminar. No es una crisis, es un archivo activo. ¿Cuántos tienes tú ahora mismo?\n\n#bookstagram #bookishhumor #leoporquequiero #fyp",
    },
]

for j in JOBS:
    print(f"=== {j['title']} ===")
    info = {
        "autoPublish": True,
        "draft": False,
        "media": [j["video"]],
        "providers": [{"network": "tiktok"}],
        "publicationDate": {"dateTime": j["date"], "timezone": "Europe/Madrid"},
        "text": j["text"],
        "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": j["title"], "photoCoverIndex": 0},
    }
    result = mcp_call("updateScheduledPost", {"blogId": BRAND_ID, "id": j["id"], "uuid": j["uuid"], "info": json.dumps(info)})
    print(json.dumps(result, indent=2, ensure_ascii=False)[:400])
