#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

BRAND_ID = "6435452"
MCP = "https://ai.metricool.com/mcp"

def mcp(method, params={}):
    token = get_valid_token()
    body = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    req = urllib.request.Request(MCP, data=body,
        headers={"Authorization":"Bearer "+token,
                 "Content-Type":"application/json",
                 "Accept":"application/json, text/event-stream"},
        method="POST")
    raw = urllib.request.urlopen(req, timeout=30).read().decode()
    try:
        return json.loads(raw)
    except:
        for line in raw.split("\n"):
            if line.startswith("data:"):
                d = line[5:].strip()
                if d and d != "[DONE]":
                    return json.loads(d)
    return {"raw": raw}

def call_tool(name, args):
    r = mcp("tools/call", {"name": name, "arguments": args})
    return r.get("result", r)

# 1. Best time to post — Instagram
print("=== MEJOR HORA PARA PUBLICAR (Instagram) ===")
result = call_tool("getBestTimeToPostByNetwork", {
    "brandId": BRAND_ID,
    "fromDate": "2026-05-01T00:00:00+02:00",
    "toDate":   "2026-06-21T23:59:59+02:00",
    "timezone": "Europe/Madrid",
    "socialNetwork": "instagram"
})
print(json.dumps(result, indent=2, ensure_ascii=False))

print("\n=== MEJOR HORA PARA PUBLICAR (Facebook) ===")
result = call_tool("getBestTimeToPostByNetwork", {
    "brandId": BRAND_ID,
    "fromDate": "2026-05-01T00:00:00+02:00",
    "toDate":   "2026-06-21T23:59:59+02:00",
    "timezone": "Europe/Madrid",
    "socialNetwork": "facebook"
})
print(json.dumps(result, indent=2, ensure_ascii=False))

# 2. Posts programados actuales
print("\n=== POSTS PROGRAMADOS (junio) ===")
result = call_tool("getScheduledPosts", {
    "brandId": BRAND_ID,
    "fromDate": "2026-06-01T00:00:00+02:00",
    "toDate":   "2026-06-30T23:59:59+02:00",
    "timezone": "Europe/Madrid"
})
print(json.dumps(result, indent=2, ensure_ascii=False))

# 3. Metricas disponibles Instagram
print("\n=== METRICAS DISPONIBLES (Instagram posts) ===")
result = call_tool("getAnalyticsAvailableMetrics", {
    "network": "instagram",
    "connector": "posts"
})
print(json.dumps(result, indent=2, ensure_ascii=False))
