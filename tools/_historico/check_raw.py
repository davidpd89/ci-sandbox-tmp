import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

r = call_tool("getScheduledPosts", {
    "brandId": "6435452",
    "fromDate": "2026-07-15T09:00:00+02:00",
    "toDate": "2026-07-15T12:00:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"] if r.get("content") else ""
print(f"Response len: {len(text)}")
print(f"First 500 chars: {text[:500]}")
print(f"...")
print(f"Last 200 chars: {text[-200:]}")
