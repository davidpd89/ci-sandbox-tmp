import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

r = call_tool("getBestTimeToPostByNetwork", {
    "brandId": "6435452",
    "fromDate": "2026-06-21T00:00:00+02:00",
    "toDate": "2026-07-02T23:59:00+02:00",
    "timezone": "Europe/Madrid",
    "socialNetwork": "tiktok"
})
raw = json.loads(r["content"][0]["text"])
days = {7:"Dom",1:"Lun",2:"Mar",3:"Mie",4:"Jue",5:"Vie",6:"Sab"}
print("=== TIKTOK MEJORES HORAS (valor = engagement score) ===")
for day_data in raw["data"]:
    dow = day_data["dayOfWeek"]
    hours = sorted(day_data["bestTimesByHour"], key=lambda x: x["value"], reverse=True)[:5]
    top = [(h["hourOfDay"], h["value"]) for h in hours]
    print(f"{days.get(dow,'?')} ({dow}): " + " | ".join(f"{h[0]:02d}h={h[1]}" for h in top))
