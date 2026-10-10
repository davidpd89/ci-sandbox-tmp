import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

def get_posts(from_d, to_d):
    r = call_tool("getScheduledPosts", {"brandId":"6435452","fromDate":from_d,"toDate":to_d,"timezone":"Europe/Madrid"})
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text) if text else {}
    posts = raw.get("data") or raw.get("posts") or []
    return [p for p in posts if not p.get("draft")]

for day, fd, td in [
    ("Jul 18", "2026-07-18T00:00:00+02:00", "2026-07-18T23:59:00+02:00"),
    ("Jul 19", "2026-07-19T00:00:00+02:00", "2026-07-19T23:59:00+02:00"),
]:
    posts = get_posts(fd, td)
    by_net = {}
    for p in posts:
        net = next((pr.get("network") for pr in p.get("providers",[])), "?")
        by_net.setdefault(net, []).append(p.get("date","")[11:16])
    print(f"\n{day}: {len(posts)} posts activos")
    for net, times in sorted(by_net.items()):
        print(f"  {net:12} {times}")
    # Redes sin posts
    all_nets = ["instagram","facebook","tiktok","threads","bluesky","pinterest"]
    missing = [n for n in all_nets if n not in by_net]
    if missing:
        print(f"  VACÍAS: {missing}")
