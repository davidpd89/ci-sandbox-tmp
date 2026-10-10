"""Audita Google Business, YouTube y X para organizar contenido."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"

def get_posts(fd, td):
    r = call_tool("getScheduledPosts",{"brandId":BLOG_ID,"fromDate":fd,"toDate":td,"timezone":"Europe/Madrid"})
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text) if text else {}
    posts = raw.get("data") or raw.get("posts") or []
    return [p for p in posts if not p.get("draft")]

# Auditar Google Business (gmb) — cadencia: 1/semana
# Verificar desde hoy hasta fin de julio
print("=== GOOGLE BUSINESS (gmb) ===")
gmb_by_week = {}
for week_start, fd, td in [
    ("Sem Jul 3-9",   "2026-07-03T00:00:00+02:00","2026-07-09T23:59:00+02:00"),
    ("Sem Jul 10-16", "2026-07-10T00:00:00+02:00","2026-07-16T23:59:00+02:00"),
    ("Sem Jul 17-23", "2026-07-17T00:00:00+02:00","2026-07-23T23:59:00+02:00"),
    ("Sem Jul 24-30", "2026-07-24T00:00:00+02:00","2026-07-30T23:59:00+02:00"),
]:
    posts = get_posts(fd, td)
    gmb = [p for p in posts if any(pr.get("network") == "gmb" for pr in p.get("providers",[]))]
    status = "✓" if gmb else "✗ VACÍA"
    print(f"  {week_start}: {len(gmb)} posts GMB {status}")
    for p in gmb:
        print(f"    {p.get('date','')[:10]} {p.get('text','')[:50]}")

# Auditar YouTube (youtube)
print("\n=== YOUTUBE ===")
for period, fd, td in [
    ("Jul 3-10",  "2026-07-03T00:00:00+02:00","2026-07-10T23:59:00+02:00"),
    ("Jul 11-17", "2026-07-11T00:00:00+02:00","2026-07-17T23:59:00+02:00"),
    ("Jul 18-24", "2026-07-18T00:00:00+02:00","2026-07-24T23:59:00+02:00"),
    ("Jul 25-31", "2026-07-25T00:00:00+02:00","2026-07-31T23:59:00+02:00"),
]:
    posts = get_posts(fd, td)
    yt = [p for p in posts if any(pr.get("network") == "youtube" for pr in p.get("providers",[]))]
    print(f"  {period}: {len(yt)} YouTube {'✓' if yt else '✗'}")
    for p in yt:
        print(f"    {p.get('date','')[5:10]} {p.get('text','')[:50]}")
