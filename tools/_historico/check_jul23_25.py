import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
os.chdir(r"C:\GIT\RRSS_DavidPorto\tools")
from metricool_client import call_tool

r = call_tool("getScheduledPosts", {
    "brandId": "6435452",
    "fromDate": "2026-07-23T00:00:00+02:00",
    "toDate": "2026-07-26T00:00:00+02:00",
    "timezone": "Europe/Madrid"
})
txt = r["content"][0]["text"]
data = json.loads(txt)
posts = data["data"] if isinstance(data, dict) and "data" in data else data
print(f"{len(posts)} posts programados Jul 23-25:")
for p in posts:
    pid = p.get("id")
    pdate = str(p.get("publicationDate",""))[:16]
    nets = [x.get("network","?") for x in p.get("providers", [])]
    media_raw = p.get("media", [])
    media = [m.get("url","")[-40:] if isinstance(m, dict) else str(m)[-40:] for m in media_raw]
    print(f"  {pid}  {pdate}  {nets}  media={media}")
