import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

def posts(fd, td):
    r = call_tool("getScheduledPosts",{"brandId":"6435452","fromDate":fd,"toDate":td,"timezone":"Europe/Madrid"})
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text) if text else {}
    all_p = raw.get("data") or raw.get("posts") or []
    return [p for p in all_p if not p.get("draft")]

for day, fd, td in [
    ("Jul 3",  "2026-07-03T00:00:00+02:00","2026-07-03T23:59:00+02:00"),
    ("Jul 19", "2026-07-19T00:00:00+02:00","2026-07-19T23:59:00+02:00"),
    ("Jul 20", "2026-07-20T00:00:00+02:00","2026-07-20T23:59:00+02:00"),
    ("Jul 21", "2026-07-21T00:00:00+02:00","2026-07-21T23:59:00+02:00"),
    ("Jul 22", "2026-07-22T00:00:00+02:00","2026-07-22T23:59:00+02:00"),
]:
    ps = posts(fd, td)
    print(f"\n{day}: {len(ps)} posts")
    for p in sorted(ps, key=lambda x: x.get("date","")):
        net = next((pr.get("network") for pr in p.get("providers",[])), "?")
        txt = p.get("text","")[:40]
        print(f"  {net:12} {p.get('date','')[11:16]} id={p.get('id')} | {txt}")
