import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

# Buscar en rango amplio de fechas para ver todos los posts pendientes recientes
for start, end in [
    ("2026-07-13T00:00:00+02:00", "2026-07-16T23:59:00+02:00"),
    ("2026-07-14T09:00:00+00:00", "2026-07-16T09:00:00+00:00"),  # UTC
]:
    print(f"\n--- {start[:10]} a {end[:10]} ---")
    r = call_tool("getScheduledPosts", {
        "brandId": "6435452",
        "fromDate": start,
        "toDate": end,
        "timezone": "Europe/Madrid"
    })
    text = r["content"][0]["text"] if r.get("content") else ""
    if not text:
        print("Sin respuesta")
        continue
    raw = json.loads(text)
    posts = raw if isinstance(raw, list) else raw.get("posts", [])
    print(f"Posts: {len(posts)}")
    for p in posts[:10]:
        net = next((pr.get("network") for pr in p.get("providers", [])), "?")
        print(f"  {net:12} {p.get('date','')[:16]} id={p.get('id')} draft={p.get('draft')}")
