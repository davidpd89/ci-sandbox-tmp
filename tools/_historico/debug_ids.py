# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout
import os; os.chdir(r"C:\GIT\RRSS_DavidPorto\tools")
from metricool_client import call_tool

r = call_tool("getScheduledPosts", {
    "brandId": "6435452",
    "fromDate": "2026-07-23T00:00:00Z",
    "toDate": "2026-07-25T23:59:59Z",
    "timezone": "Europe/Madrid",
})
content = r.get("content", [])
text = content[0].get("text", "") if content else ""
data = json.loads(text).get("data", [])
print(f"Total posts: {len(data)}")
for p in data:
    pid = p.get("id")
    dt = p.get("publicationDate", {}).get("dateTime", "?")
    nets = [pr.get("network", "?") for pr in p.get("providers", [])]
    media = p.get("media", [])
    url_short = str(media[0])[:50] if media else "(no media)"
    print(f"  id={pid} type={type(pid).__name__} {dt} nets={nets}")
    print(f"    media: {url_short}")
