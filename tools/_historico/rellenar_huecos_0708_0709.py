#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rellena huecos reales encontrados en auditoria: Threads/Bluesky/Pinterest vacios el 2026-07-08 y 07-09."""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"
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
    print(network, date, str(r)[:250])
    return r


NOVERIS = "https://static.metricool.com/planner/202606/6435452-file-2757517776343253794.png"
ESTANTERIA = "https://static.metricool.com/planner/202606/6435452-file-8112426513972962484.png"
SILLAS = "https://static.metricool.com/planner/202606/6435452-file-7879013076938517870.png"
PERSONAJE = "https://static.metricool.com/planner/202606/6435452-file-16931304731493411887.png"

TXT_NOVERIS = "En Noveris, cuando un hechizo falla o se degrada, no queda solo el desastre: queda residuo.\n\nLos Gorx son aves esponjosas que se alimentan de esa hechicería residual. Funcionan como limpieza urbana, rastreo y alarma biológica. Si ves un Gorx posado cerca, algo mágico ha fallado hace poco.\n\nGlosario de Noveris, primera entrada. Si os gusta esta serie, decídmelo y sigo con el resto de criaturas/objetos.\n\n#fantasiajuvenil #worldbuilding #librosdefantasia #fantasyromance #bookstagram"
TXT_ESTANTERIA = "Tengo un sistema para ordenar la estantería. No es por colores, ni por autor. Es por \"cuánto me dolió\", y nadie más lo entendería.\n\n¿Cuál es el vuestro?\n\n#bookstagram #libros"
TXT_SILLAS = "Hay sillas que se quedan vacías mucho antes de que alguien se dé cuenta.\n\nNo pasa nada dramático. Solo deja de haber alguien ahí, poco a poco, hasta que un día lo notas.\n\n¿Hay algo en tu vida que te recuerde a esto? Cuéntamelo si quieres.\n\n#frasesprofundas #frases #reflexion #frasesparareflexionar #nostalgia"
TXT_PERSONAJE = "Tenía el plan entero para este personaje. Tres capítulos después, hizo justo lo contrario de lo que yo había decidido.\n\nY tenía razón.\n\n¿Os ha pasado leyendo, que un personaje se os escapa del libro que creíais que era?\n\n#escribir #escritores #procesocreativo #escrituracreativa #vidadeescritor"

# 2026-07-08: hueco completo en threads/bluesky/pinterest
create("threads", "2026-07-08T09:00:00", [NOVERIS], TXT_NOVERIS)
create("bluesky", "2026-07-08T12:00:00", [NOVERIS], TXT_NOVERIS)
create("threads", "2026-07-08T21:00:00", [ESTANTERIA], TXT_ESTANTERIA)
create("bluesky", "2026-07-08T22:00:00", [ESTANTERIA], TXT_ESTANTERIA)
create("pinterest", "2026-07-08T13:30:00", [ESTANTERIA], TXT_ESTANTERIA, {
    "pinterestData": {"boardId": BOARD_ID, "pinTitle": "Mi sistema para ordenar la estantería", "pinLink": "https://davidportodiaz.com", "pinNewFormat": False}
})
create("pinterest", "2026-07-08T17:30:00", [NOVERIS], TXT_NOVERIS, {
    "pinterestData": {"boardId": BOARD_ID, "pinTitle": "Glosario de Noveris: los Gorx", "pinLink": "https://davidportodiaz.com", "pinNewFormat": False}
})

# 2026-07-09: hueco completo en threads/bluesky/pinterest
create("threads", "2026-07-09T10:00:00", [SILLAS], TXT_SILLAS)
create("bluesky", "2026-07-09T13:00:00", [SILLAS], TXT_SILLAS)
create("threads", "2026-07-09T22:00:00", [PERSONAJE], TXT_PERSONAJE)
create("bluesky", "2026-07-09T23:00:00", [PERSONAJE], TXT_PERSONAJE)
create("pinterest", "2026-07-09T15:00:00", [SILLAS], TXT_SILLAS, {
    "pinterestData": {"boardId": BOARD_ID, "pinTitle": "Hay sillas que se quedan vacías", "pinLink": "https://davidportodiaz.com", "pinNewFormat": False}
})
create("pinterest", "2026-07-09T19:00:00", [PERSONAJE], TXT_PERSONAJE, {
    "pinterestData": {"boardId": BOARD_ID, "pinTitle": "Cuando un personaje se escapa del plan", "pinLink": "https://davidportodiaz.com", "pinNewFormat": False}
})
