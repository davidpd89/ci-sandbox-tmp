#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actualiza los 4 posts pendientes de hoy de DP-F0-059 con reel_v2.mp4 (ritmo de texto corregido)."""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"
VIDEO = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-059-mundos-de-un-libro/reel_v2.mp4"


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


POSTS = [
    {"id": 342610486, "uuid": "-672681258757371449", "network": "instagram", "date": "2026-06-28T17:30:00",
     "text": "Cada página abre una puerta distinta. Y ninguna vuelve a cerrarse igual.\n\n¿Qué mundo te atraparía primero? Cuéntamelo 👇\n\n#fantasiaepica #mundosdefantasia #literaturafantastica #libroderecomendados #leerfantasia",
     "extra": {"instagramData": {"autoPublish": True, "type": "REEL", "showReelOnFeed": True}}},
    {"id": 342610488, "uuid": None, "network": "facebook", "date": "2026-06-28T21:30:00",
     "text": None, "extra": {"facebookData": {"type": "REEL"}}},
    {"id": 342610515, "uuid": None, "network": "threads", "date": "2026-06-28T20:30:00",
     "text": None, "extra": {}},
    {"id": 342610521, "uuid": None, "network": "bluesky", "date": "2026-06-28T22:00:00",
     "text": None, "extra": {}},
]


def get_post(pid):
    from metricool_client import call_tool
    r = call_tool("getScheduledPosts", {"brandId": BRAND_ID, "fromDate": "2026-06-28T00:00:00+02:00",
                                          "toDate": "2026-06-29T00:00:00+02:00", "timezone": "Europe/Madrid"})
    obj = json.loads(r["content"][0]["text"])
    for p in obj["data"]:
        if p["id"] == pid:
            return p
    return None


for spec in POSTS:
    full = get_post(spec["id"])
    if full is None:
        print(spec["id"], "NO ENCONTRADO")
        continue
    info = {
        "autoPublish": full.get("autoPublish", True),
        "draft": False,
        "media": [VIDEO],
        "providers": full["providers"],
        "publicationDate": full["publicationDate"],
        "text": full["text"],
    }
    info.update(spec["extra"])
    r = mcp_call("updateScheduledPost", {"blogId": BRAND_ID, "id": str(spec["id"]), "uuid": full["uuid"], "info": json.dumps(info)})
    print(spec["network"], spec["id"], str(r)[:300])
