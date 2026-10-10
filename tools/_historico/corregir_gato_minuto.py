#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regenera DP-F0-031 (gato) y DP-F0-030 (minuto raro): de animacion con artefactos
(cara de gato distorsionada, libro de tapa lisa) a secuencia narrativa encadenada.
Mismos captions que ya estaban bien, solo cambia el video.
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


JOBS = [
    {
        "name": "DP-F0-031-gato-v4",
        "ig": ("341590744", "739136510287102666", "2026-07-01T11:00:00",
               "¿Cuál fue la última excusa real que te impidió terminar un capítulo? Cuéntamela, voy anotando motivos.\n\n#bookstagram #bookishhumor #bookaddicted #bookhumor #leoporquequiero"),
        "fb": ("341590746", "2978024106177613562", "2026-07-01T12:30:00",
               "¿Qué fue lo último que te interrumpió justo en la mejor parte de un libro? Cuéntame.\n\nhttps://davidportodiaz.com\n\n#bookstagram"),
        "tt": ("341590753", "-7991878127491266050", "2026-07-01T19:30:00",
               "¿Qué te interrumpe siempre justo en la mejor parte de un libro? Te leo en comentarios \U0001f447\n\n#bookstagram #booktokespañol #leoporquequiero #fyp", "Capitulo cancelado por el gato"),
    },
    {
        "name": "DP-F0-030-minuto-raro-v2",
        "ig": ("341338879", "-6345791228637069231", "2026-07-03T11:00:00",
               "¿Qué haces tú en ese minuto raro de después? Cuéntamelo en comentarios, tengo curiosidad real.\n\n#frasesprofundas #frasesparareflexionar #amorpropio #textosquesanan #nostalgia"),
        "fb": ("341339239", "7132809758192517471", "2026-07-03T12:30:00",
               "¿Qué haces tú en ese minuto raro de después de cerrar un libro? Cuéntame.\n\nhttps://davidportodiaz.com\n\n#bookstagram"),
        "tt": ("341339243", "7703035852254298176", "2026-07-03T19:30:00",
               "¿Qué haces tú en ese minuto raro de después de cerrar un libro? Te leo en comentarios \U0001f447\n\n#bookstagram #booktokespañol #leoporquequiero #fyp", "El minuto raro tras cerrar un libro"),
    },
]

for job in JOBS:
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
