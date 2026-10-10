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

TARGET_IDS = {
    345570733, 345570845, 345570735, 345570736, 345570737, 345570848,
    345570746, 345570742, 345570745, 345570747, 345570748, 345570851,
    345570750, 345570846, 345570752, 345570753, 345570754, 345570854,
    345570755, 345570847, 345570758, 345570759, 345570760, 345570855,
    345570761, 345570773, 345570776, 345570777, 345570778, 345570857,
}

print("id -> uuid mapping:")
for p in posts:
    pid = p.get("id")
    if pid in TARGET_IDS:
        print(f'    {pid}: "{p.get("uuid", "NO-UUID")}", date={str(p.get("publicationDate",""))[:16]}, net={[x.get("network") for x in p.get("providers",[])]}')