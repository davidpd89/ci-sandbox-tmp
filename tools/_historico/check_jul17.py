import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

r = call_tool("getScheduledPosts", {
    "brandId": "6435452",
    "fromDate": "2026-07-17T00:00:00+02:00",
    "toDate": "2026-07-17T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"] if r.get("content") else ""
raw = json.loads(text)
posts = raw.get("data") or raw.get("posts") or []
active = [p for p in posts if not p.get("draft")]
print(f"Posts activos el 17 jul: {len(active)}")
for p in active:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    print(f"  {net:12} {p.get('date','')[:16]} id={p.get('id')}")
