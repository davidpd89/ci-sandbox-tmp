#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige el fallo de "gancho al final" detectado por David: reordena el texto
quemado en 11 piezas para que la frase mas fuerte aparezca en el primer
segundo, no en el ultimo. Mismos captions/hashtags que ya estaban bien,
solo cambia el video (media) para forzar a Metricool a releer el nuevo.
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


def update_tiktok(pid, uuid, date, video, title, text):
    info = {
        "autoPublish": True, "draft": False,
        "media": [video],
        "providers": [{"network": "tiktok"}],
        "publicationDate": {"dateTime": date, "timezone": "Europe/Madrid"},
        "text": text,
        "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": title, "photoCoverIndex": 0},
    }
    return mcp_call("updateScheduledPost", {"blogId": BRAND_ID, "id": pid, "uuid": uuid, "info": json.dumps(info)})


def update_ig_reel(pid, uuid, date, video, text):
    info = {
        "autoPublish": True, "draft": False,
        "media": [video],
        "providers": [{"network": "instagram"}],
        "publicationDate": {"dateTime": date, "timezone": "Europe/Madrid"},
        "text": text,
        "instagramData": {"autoPublish": True, "type": "REEL", "showReelOnFeed": True},
    }
    return mcp_call("updateScheduledPost", {"blogId": BRAND_ID, "id": pid, "uuid": uuid, "info": json.dumps(info)})


def update_fb_reel(pid, uuid, date, video, text):
    info = {
        "autoPublish": True, "draft": False,
        "media": [video],
        "providers": [{"network": "facebook"}],
        "publicationDate": {"dateTime": date, "timezone": "Europe/Madrid"},
        "text": text,
        "facebookData": {"type": "REEL"},
    }
    return mcp_call("updateScheduledPost", {"blogId": BRAND_ID, "id": pid, "uuid": uuid, "info": json.dumps(info)})


# === TikTok solo (TT-003, 004 ya regeneradas completas; 006-010 solo texto) ===
TIKTOK_JOBS = [
    ("340498033", "-7833594401711176138", "2026-06-26T20:30:00",
     f"{BASE}/TT-003-proteges-v2/TT-003-proteges-v2.mp4", "Hay libros que proteges",
     "Hay libros que no recomiendas. Los proteges. No es vergüenza, es que algunos son demasiado tuyos.\n\n#frasesdelibros #bookstagram #booktok #fyp"),
    ("340498038", "-6177529568378270896", "2026-06-27T19:00:00",
     f"{BASE}/TT-004-personajes-v2/TT-004-personajes-v2.mp4", "Personajes que se salen del plan",
     "Los personajes que más quiero son los que se salieron del plan que tenía para ellos.\n\n#escribir #escritoresdeinstagram #procesocreativo #booktok #fyp"),
    ("341575203", "1083719962820822078", "2026-06-25T08:30:00",
     f"{BASE}/TT-006-villano-v3/TT-006-villano-v3.mp4", "El villano que tenia demasiada razon",
     "Los villanos con razón son los que más me incomodan. ¿A ti cuál te ha hecho dudar de quién tenía razón?\n\n#fantasiaespañola #worldbuilding #bookstagram #booktok #fyp"),
    ("341575208", "-3562286430676955615", "2026-06-25T22:00:00",
     f"{BASE}/TT-007-subraya-v3/TT-007-subraya-v3.mp4", "La frase que te subraya a ti",
     "Hay frases que no olvidas aunque no las subrayaste. Mi turno: la dejo en comentarios, dime la tuya.\n\n#frasesdelibros #bookstagram #frases #booktok #fyp"),
    ("341575213", "4049477313369360838", "2026-06-26T08:00:00",
     f"{BASE}/TT-008-viaje-v3/TT-008-viaje-v3.mp4", "El heroe que no queria el viaje",
     "El elegido que acepta el viaje sin dudar me aburre un poco. El que no quería irse y aun así se quedó, ese sí me interesa. ¿Tienes uno?\n\n#fantasiaespañola #worldbuilding #librosdefantasia #booktok #fyp"),
    ("341575216", "-9183002557269127774", "2026-06-27T07:30:00",
     f"{BASE}/TT-009-mapa-v3/TT-009-mapa-v3.mp4", "El mapa que promete mas de lo que da",
     "Confieso: miro el mapa antes de leer aunque sé que casi nunca cumple lo que promete. ¿Solo me pasa a mí?\n\n#fantasiaespañola #worldbuilding #bookstagram #fyp"),
    ("341575219", "-2862938440900785441", "2026-06-28T06:45:00",
     f"{BASE}/TT-010-abandonos-v3/TT-010-abandonos-v3.mp4", "Mi marcapaginas sabe mas que mis amigos",
     "Cada marcapáginas de mi casa marca un libro sin terminar. No es una crisis, es un archivo activo. ¿Cuántos tienes tú ahora mismo?\n\n#bookstagram #bookishhumor #leoporquequiero #fyp"),
]

# === DP-F0-031 a 034: IG + FB + TikTok, mismo video v3 en los 3 ===
MULTI_JOBS = [
    {
        "name": "DP-F0-031-gato-v3",
        "ig": ("341466511", "739136510287102666", "2026-07-01T11:00:00",
               "¿Cuál fue la última excusa real que te impidió terminar un capítulo? Cuéntamela, voy anotando motivos.\n\n#bookstagram #bookishhumor #bookaddicted #bookhumor #leoporquequiero"),
        "fb": ("341466513", "2978024106177613562", "2026-07-01T12:30:00",
               "¿Qué fue lo último que te interrumpió justo en la mejor parte de un libro? Cuéntame.\n\nhttps://davidportodiaz.com\n\n#bookstagram"),
        "tt": ("341466517", "-7991878127491266050", "2026-07-01T19:30:00",
               "¿Qué te interrumpe siempre justo en la mejor parte de un libro? Te leo en comentarios \U0001f447\n\n#bookstagram #booktokespañol #leoporquequiero #fyp", "Capitulo cancelado por el gato"),
    },
    {
        "name": "DP-F0-032-silla-v3",
        "ig": ("341457898", "-2146632047314124707", "2026-07-02T11:00:00",
               "¿Hay alguien a quien todavía le guardas la silla sin pensarlo? Cuéntamelo, si quieres.\n\n#frasesprofundas #frasesparareflexionar #amorpropio #textosquesanan #nostalgia"),
        "fb": ("341457905", "-175544440078644090", "2026-07-02T12:30:00",
               "¿Hay alguien a quien todavía le guardas la silla sin pensarlo, aunque ya no venga?\n\nhttps://davidportodiaz.com\n\n#frasesprofundas"),
        "tt": ("341457909", "-433806369394702247", "2026-07-02T19:30:00",
               "¿A quién le sigues guardando la silla sin pensarlo? Te leo en comentarios \U0001f447\n\n#frasesprofundas #reflexion #textosquesanan #fyp", "La silla que sigue vacia"),
    },
    {
        "name": "DP-F0-033-disciplina-v3",
        "ig": ("341460138", "299987280716578909", "2026-07-04T11:00:00",
               "¿Tú también escribes (o haces lo tuyo) los días sin ganas, o esperas a que llegue la chispa? Cuéntamelo.\n\n#escribir #escritores #autopublicacion #procesocreativo #vidadeescritor"),
        "fb": ("341460140", "-308403776898318052", "2026-07-04T12:30:00",
               "¿Tú también haces lo tuyo los días sin ganas, o esperas a que llegue la chispa?\n\nhttps://davidportodiaz.com\n\n#escribir"),
        "tt": ("341460147", "-1119698325392110643", "2026-07-04T19:30:00",
               "¿Esperas la inspiración o te sientas igual? Te leo en comentarios \U0001f447\n\n#escribir #escritoresdeinstagram #procesocreativo #fyp", "La disciplina no es inspiracion"),
    },
    {
        "name": "DP-F0-034-nocturno-v3",
        "ig": ("341462623", "7443562922604382519", "2026-07-05T11:00:00",
               "¿A qué hora te has rendido tú la última vez? Cuéntamela, quiero comparar récords.\n\n#bookstagram #bookishhumor #bookaddicted #leoporquequiero #booktokespañol"),
        "fb": ("341462626", "4151238352603728307", "2026-07-05T12:30:00",
               "¿A qué hora te rendiste tú la última vez leyendo \"solo un poco más\"?\n\nhttps://davidportodiaz.com\n\n#bookstagram"),
        "tt": ("341462629", "1670364744101937754", "2026-07-05T19:30:00",
               "¿A qué hora te rendiste tú la última vez? Te leo en comentarios \U0001f447\n\n#booktok #booktokespañol #leoporquequiero #fyp", "Solo un capitulo mas a las 23:50"),
    },
]

for pid, uuid, date, video, title, text in TIKTOK_JOBS:
    print(f"=== TikTok {title} ===")
    r = update_tiktok(pid, uuid, date, video, title, text)
    print(json.dumps(r, ensure_ascii=False)[:200])

for job in MULTI_JOBS:
    video_url = f"{BASE}/{job['name']}/{job['name']}.mp4"
    print(f"=== {job['name']} IG ===")
    pid, uuid, date, text = job["ig"]
    print(json.dumps(update_ig_reel(pid, uuid, date, video_url, text), ensure_ascii=False)[:200])
    print(f"=== {job['name']} FB ===")
    pid, uuid, date, text = job["fb"]
    print(json.dumps(update_fb_reel(pid, uuid, date, video_url, text), ensure_ascii=False)[:200])
    print(f"=== {job['name']} TT ===")
    pid, uuid, date, text, title = job["tt"]
    print(json.dumps(update_tiktok(pid, uuid, date, video_url, title, text), ensure_ascii=False)[:200])
