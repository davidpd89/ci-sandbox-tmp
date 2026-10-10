#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

from metricool_auth import get_valid_token
import urllib.request

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

tools = mcp("tools/list").get("result", {}).get("tools", [])

# Print schema for analytics/besttime tools
target_keywords = ["best", "analytic", "metric", "schedule", "post"]
for t in tools:
    name = t.get("name","")
    if any(k in name.lower() for k in target_keywords):
        print(f"\n=== {name} ===")
        print(json.dumps(t.get("inputSchema", {}), indent=2, ensure_ascii=False))
