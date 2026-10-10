import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

# Check July 10-12 (should have posts from previous sessions)
r = call_tool("getScheduledPosts", {
    "brandId": "6435452",
    "fromDate": "2026-07-10T00:00:00+02:00",
    "toDate": "2026-07-12T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"] if r.get("content") else ""
raw = json.loads(text) if text else {}
posts = raw if isinstance(raw, list) else raw.get("posts", [])
print(f"Jul 10-12: {len(posts)} posts")
for p in posts[:5]:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    print(f"  {net:12} {p.get('date','')[:16]} id={p.get('id')}")

# Check via the error in the previous session - maybe schema changed
r2 = call_tool("getScheduledPosts", {
    "brandId": "6435452",
    "fromDate": "2026-07-15T09:00:00+02:00",
    "toDate": "2026-07-15T12:00:00+02:00",
    "timezone": "Europe/Madrid"
})
text2 = r2["content"][0]["text"] if r2.get("content") else ""
print(f"\nJul 15 09-12: response len={len(text2)}")
if text2:
    raw2 = json.loads(text2)
    posts2 = raw2 if isinstance(raw2, list) else raw2.get("posts", [])
    print(f"Posts: {len(posts2)}")
