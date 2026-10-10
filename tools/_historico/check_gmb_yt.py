import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"

def get_posts(fd, td):
    r = call_tool("getScheduledPosts",{"brandId":BLOG_ID,"fromDate":fd,"toDate":td,"timezone":"Europe/Madrid"})
    content = r.get("content", [])
    if not content: return []
    text = content[0].get("text","")
    if not text: return []
    try:
        raw = json.loads(text)
        posts = raw.get("data") or raw.get("posts") or (raw if isinstance(raw, list) else [])
        return [p for p in posts if not p.get("draft")]
    except Exception:
        return []

# Google Business: 1 por semana (cadencia)
print("=== GOOGLE BUSINESS (gmb) — cadencia 1/semana ===")
for label, fd, td in [
    ("Jul 3-9",   "2026-07-03T00:00:00+02:00","2026-07-09T23:59:00+02:00"),
    ("Jul 10-16", "2026-07-10T00:00:00+02:00","2026-07-16T23:59:00+02:00"),
    ("Jul 17-23", "2026-07-17T00:00:00+02:00","2026-07-23T23:59:00+02:00"),
    ("Jul 24-30", "2026-07-24T00:00:00+02:00","2026-07-30T23:59:00+02:00"),
]:
    posts = get_posts(fd, td)
    gmb = [p for p in posts if any(pr.get("network")=="gmb" for pr in p.get("providers",[]))]
    mark = "✓" if gmb else "✗ FALTA"
    print(f"  {label}: {len(gmb)} posts {mark}")
    for p in gmb:
        print(f"    {p.get('date','')[:10]}: {p.get('text','')[:60]}")

# YouTube
print("\n=== YOUTUBE ===")
for label, fd, td in [
    ("Jul 3-9",   "2026-07-03T00:00:00+02:00","2026-07-09T23:59:00+02:00"),
    ("Jul 10-16", "2026-07-10T00:00:00+02:00","2026-07-16T23:59:00+02:00"),
    ("Jul 17-23", "2026-07-17T00:00:00+02:00","2026-07-23T23:59:00+02:00"),
    ("Jul 24-30", "2026-07-24T00:00:00+02:00","2026-07-30T23:59:00+02:00"),
]:
    posts = get_posts(fd, td)
    yt = [p for p in posts if any(pr.get("network")=="youtube" for pr in p.get("providers",[]))]
    mark = "✓" if yt else "✗ VACÍO"
    print(f"  {label}: {len(yt)} YouTube {mark}")
    for p in yt:
        data = p.get("youtubeData",{})
        print(f"    {p.get('date','')[5:10]}: {data.get('title','?')} — {p.get('text','')[:40]}")
