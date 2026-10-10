"""Obtiene métricas de Instagram Reels, Posts y TikTok desde el inicio."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

# IG Reels con texto
r1 = call_tool("getAnalyticsDataByMetrics", {
    "brandId": "6435452",
    "from": "2026-06-21T00:00:00+02:00",
    "to": "2026-07-02T23:59:00+02:00",
    "metrics": ["IGRE01","IGRE03","IGRE10","IGRE11","IGRE23","IGRE27","IGRE28"]
})
raw1 = json.loads(r1["content"][0]["text"])
print("=== IG REELS (por retención 3s) ===")
rows = sorted(raw1.get("rows",[]), key=lambda x: float(x[6] or 0), reverse=True)
for row in rows:
    fecha, texto, likes, alc, views, ret, p3s = row[0],(row[1] or "")[:55],row[2],row[3],row[4],row[5],row[6]
    print(f"{fecha} likes={likes} alc={alc} views={views} 3s%={p3s}")
    print(f"  {texto}")

# TikTok
r2 = call_tool("getAnalyticsDataByMetrics", {
    "brandId": "6435452",
    "from": "2026-06-21T00:00:00+02:00",
    "to": "2026-07-02T23:59:00+02:00",
    "metrics": ["TKPO01","TKPO05","TKPO07","TKPO08","TKPO10"]
})
raw2 = json.loads(r2["content"][0]["text"])
print("\n=== TIKTOK (por views) ===")
for row in sorted(raw2.get("rows",[]), key=lambda x: int(x[2] or 0), reverse=True)[:8]:
    fecha, desc, views, likes, shares = row[0],(row[1] or "")[:55],row[2],row[3],row[4]
    print(f"{fecha} v={views} l={likes} s={shares}")
    print(f"  {desc}")

# Mejor hora TikTok
r3 = call_tool("getBestTimeToPostByNetwork", {
    "brandId":"6435452","fromDate":"2026-06-21T00:00:00+02:00",
    "toDate":"2026-07-02T23:59:00+02:00","timezone":"Europe/Madrid","socialNetwork":"tiktok"
})
raw3 = json.loads(r3["content"][0]["text"])
days = {7:"Dom",1:"Lun",2:"Mar",3:"Mie",4:"Jue",5:"Vie",6:"Sab"}
print("\n=== MEJORES HORAS TIKTOK ===")
for dd in raw3.get("data",[]):
    dow = dd["dayOfWeek"]
    top5 = sorted(dd["bestTimesByHour"], key=lambda x: x["value"], reverse=True)[:3]
    print(f"  {days.get(dow,'?')} ({dow}): " + " | ".join(f"{h['hourOfDay']:02d}h={h['value']}" for h in top5))
