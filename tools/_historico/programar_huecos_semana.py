#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rellena los huecos detectados en la review 26/06-05/07: faltaba 2a publicacion
diaria en TikTok el 30/06, y en IG+FB+TikTok del 01/07 al 05/07 (cada red solo
tenia 1 post/dia). 11 piezas nuevas (9 quote cards + 2 carruseles), variedad
de formato frente a la semana 100% video que habia en ese tramo.
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"
BASE = "https://davidportodiaz.com/assets"


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


def create_ig(date, media, text, is_carousel=False):
    info = {
        "autoPublish": True, "draft": False,
        "media": media,
        "providers": [{"network": "instagram"}],
        "publicationDate": {"dateTime": date, "timezone": "Europe/Madrid"},
        "text": text,
        "instagramData": {"autoPublish": True, "type": "CAROUSEL" if is_carousel else "POST"},
        "descendants": [],
    }
    return mcp_call("createScheduledPost", {"blogId": BRAND_ID, "date": date + "+02:00", "info": json.dumps(info)})


def create_fb(date, media, text):
    info = {
        "autoPublish": True, "draft": False,
        "media": media,
        "providers": [{"network": "facebook"}],
        "publicationDate": {"dateTime": date, "timezone": "Europe/Madrid"},
        "text": text,
        "descendants": [],
    }
    return mcp_call("createScheduledPost", {"blogId": BRAND_ID, "date": date + "+02:00", "info": json.dumps(info)})


def create_tiktok(date, media, text, title):
    info = {
        "autoPublish": True, "draft": False,
        "media": media,
        "providers": [{"network": "tiktok"}],
        "publicationDate": {"dateTime": date, "timezone": "Europe/Madrid"},
        "text": text,
        "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "title": title, "photoCoverIndex": 0},
        "descendants": [],
    }
    return mcp_call("createScheduledPost", {"blogId": BRAND_ID, "date": date + "+02:00", "info": json.dumps(info)})


IG_FB_JOBS = [
    ("2026-07-01T09:00:00", [f"{BASE}/dp-f0-035-quote-puerta-gratis.png"],
     "Una puerta gratis en fantasía siempre es sospechosa. ¿Escapatoria, peligro o descubrimiento? Dime qué crees que esconde.\n\n#fantasiaespañola #worldbuilding #librosdefantasia #bookstagram",
     "Una puerta gratis en fantasía siempre es sospechosa. ¿Escapatoria, peligro o descubrimiento?\n\nhttps://davidportodiaz.com\n\n#fantasiaespañola",
     False),
    ("2026-07-02T09:30:00", [f"{BASE}/dp-f0-036-carrusel-mapa-s{i}.png" for i in range(1, 6)],
     "¿Cuál de los tres eres tú con un mapa de fantasía delante? Dilo en comentarios, quiero saber cuántos sois de cada tipo.\n\n#fantasiaespañola #worldbuilding #bookstagram #librosdefantasia #booktokespañol",
     "¿Cuál de los tres eres tú con un mapa de fantasía delante?\n\nhttps://davidportodiaz.com\n\n#fantasiaespañola",
     True),
    ("2026-07-03T08:30:00", [f"{BASE}/dp-f0-037-quote-no-escapar.png"],
     "No leo fantasía para escapar. Leo para volver con peores preguntas. ¿A ti qué libro te ha devuelto peor, pero mejor?\n\n#fantasiaespañola #librosdefantasia #bookstagram #leoporquequiero",
     "No leo fantasía para escapar. Leo para volver con peores preguntas.\n\nhttps://davidportodiaz.com\n\n#fantasiaespañola",
     False),
    ("2026-07-04T20:00:00", [f"{BASE}/dp-f0-038-quote-premio-nacional.png"],
     "Hoy ha pasado algo que no esperaba: Top 10 finalista del Premio Nacional Juan Andrés Teno, con Samuel entre mundos. Sigo aprendiendo a que esto no me cambie la forma de escribir. Gracias por leer desde el principio.\n\n#DavidPortoDíaz #SamuelEntreMundos #FantasiaEspañola #VidaDeAutor",
     "Hoy ha pasado algo que no esperaba: Top 10 finalista del Premio Nacional Juan Andrés Teno, con Samuel entre mundos.\n\nhttps://davidportodiaz.com\n\n#SamuelEntreMundos",
     False),
    ("2026-07-05T16:30:00", [f"{BASE}/dp-f0-039-quote-libro-negocia.png"],
     "Un libro que vuelve a ti tres veces no está insistiendo: está negociando. ¿Tienes uno así en tu estantería ahora mismo?\n\n#frasesdelibros #bookstagram #libros #leoporquequiero",
     "Un libro que vuelve a ti tres veces no está insistiendo: está negociando.\n\nhttps://davidportodiaz.com\n\n#frasesdelibros",
     False),
]

TIKTOK_JOBS = [
    ("2026-06-30T08:00:00", [f"{BASE}/dp-f0-040-quote-respira-habitacion.png"],
     "No abandoné ese libro. Lo dejé respirando en otra habitación. ¿Tienes alguno así tú? Te leo en comentarios 👇\n\n#bookstagram #booktokespañol #leoporquequiero #fyp",
     "No abandone el libro, lo deje respirando"),
    ("2026-07-01T22:00:00", [f"{BASE}/dp-f0-041-quote-amanecer.png"],
     "Dije «un capítulo más» y el amanecer respondió. Cuéntame la última vez que te pasó esto.\n\n#booktok #bookishhumor #leoporquequiero #fyp",
     "Un capitulo mas y el amanecer respondio"),
    ("2026-07-02T07:00:00", [f"{BASE}/dp-f0-042-quote-lector-bateria.png"],
     "El lector al 4% de batería tiene más tensión que muchos thrillers. Dime que no soy el único al que le pasa esto.\n\n#bookishhumor #booktokespañol #fyp",
     "El lector al 4 por ciento de bateria"),
    ("2026-07-03T21:00:00", [f"{BASE}/dp-f0-043-quote-ventana.png"],
     "Si un libro me hace mirar por la ventana, ya gané. ¿Cuál fue el último que te hizo eso a ti?\n\n#frasesdelibros #leoporquequiero #booktokespañol #fyp",
     "Si me hace mirar por la ventana ya gane"),
    ("2026-07-04T07:30:00", [f"{BASE}/dp-f0-044-carrusel-villano-s{i}.png" for i in range(1, 5)],
     "¿Qué villano te hizo dudar de quién tenía razón? Te leo en comentarios 👇\n\n#fantasiaespañola #worldbuilding #booktokespañol #fyp",
     "Dos motivos por los que un villano razonable da mas miedo"),
    ("2026-07-05T08:00:00", [f"{BASE}/dp-f0-045-quote-releer.png"],
     "Releer es discutir con quien eras antes. ¿Hay un libro al que vuelves solo para ver en qué has cambiado?\n\n#frasesdelibros #leoporquequiero #booktokespañol #fyp",
     "Releer es discutir con quien eras antes"),
]

for date, media, text_ig, text_fb, is_carousel in IG_FB_JOBS:
    print(f"=== IG {date} ===")
    print(json.dumps(create_ig(date, media, text_ig, is_carousel), ensure_ascii=False)[:200])
    print(f"=== FB {date} ===")
    print(json.dumps(create_fb(date, media, text_fb), ensure_ascii=False)[:200])

for date, media, text, title in TIKTOK_JOBS:
    print(f"=== TikTok {date} ===")
    print(json.dumps(create_tiktok(date, media, text, title), ensure_ascii=False)[:200])
