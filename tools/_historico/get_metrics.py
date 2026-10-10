import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from metricool_client import call_tool

# Best time to post - correct schema
print("=== MEJOR HORA INSTAGRAM ===")
r = call_tool("getBestTimeToPostByNetwork", {
    "brandId": "6435452",
    "fromDate": "2026-06-21T00:00:00+02:00",
    "toDate": "2026-07-02T23:59:00+02:00",
    "timezone": "Europe/Madrid",
    "socialNetwork": "instagram"
})
print(json.dumps(r, ensure_ascii=False, indent=2)[:4000])

print("\n=== MEJOR HORA TIKTOK ===")
r2 = call_tool("getBestTimeToPostByNetwork", {
    "brandId": "6435452",
    "fromDate": "2026-06-21T00:00:00+02:00",
    "toDate": "2026-07-02T23:59:00+02:00",
    "timezone": "Europe/Madrid",
    "socialNetwork": "tiktok"
})
print(json.dumps(r2, ensure_ascii=False, indent=2)[:4000])

# Instagram account evolution (followers)
print("\n=== IG EVOLUCION SEGUIDORES ===")
r3 = call_tool("getAnalyticsDataByMetrics", {
    "brandId": "6435452",
    "from": "2026-06-21T00:00:00+02:00",
    "to": "2026-07-02T23:59:00+02:00",
    "metrics": ["IGEV01", "IGEV03", "IGEV04", "IGEV22"]
})
raw3 = json.loads(r3["content"][0]["text"])
print(json.dumps(raw3, ensure_ascii=False, indent=2)[:3000])
