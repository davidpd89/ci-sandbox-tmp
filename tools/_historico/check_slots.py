import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

r = call_tool("getScheduledPosts", {
    "brandId": "6435452",
    "fromDate": "2026-07-15T00:00:00+02:00",
    "toDate": "2026-07-19T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
raw_text = r["content"][0]["text"]
raw = json.loads(raw_text)
posts = raw if isinstance(raw, list) else raw.get("posts", [])
by_day = {}
for p in posts:
    if p.get("draft") or not p.get("autoPublish", True):
        continue
    d = p.get("date", "")[:10]
    net = next((pr.get("network", "") for pr in p.get("providers", [])), "")
    by_day.setdefault(d, {}).setdefault(net, []).append(p.get("date", "")[11:16])
print(f"Total posts (non-draft): {sum(len(v) for dd in by_day.values() for v in dd.values())}")
for d in sorted(by_day):
    print(d)
    for net, times in sorted(by_day[d].items()):
        print(f"  {net}: {times}")
