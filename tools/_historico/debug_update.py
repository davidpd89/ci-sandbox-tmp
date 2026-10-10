import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
BASE = "https://davidpd89.github.io/rrss-davidporto-media/videos"
NET_KEY = {"instagram":"instagramData","facebook":"facebookData","tiktok":"tiktokData",
           "threads":"threadsData","bluesky":"blueskyData","pinterest":"pinterestData"}

def get_posts(fd, td):
    r = call_tool("getScheduledPosts",{"brandId":BLOG_ID,"fromDate":fd,"toDate":td,"timezone":"Europe/Madrid"})
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text) if text else {}
    posts = raw.get("data") or raw.get("posts") or []
    return [p for p in posts if not p.get("draft")]

# Ver posts reales y sus IDs actuales
for day, fd, td in [
    ("Jul20","2026-07-20T00:00:00+02:00","2026-07-20T23:59:00+02:00"),
    ("Jul21","2026-07-21T00:00:00+02:00","2026-07-21T23:59:00+02:00"),
    ("Jul22","2026-07-22T00:00:00+02:00","2026-07-22T23:59:00+02:00"),
]:
    posts = get_posts(fd, td)
    print(f"\n{day}: {len(posts)} posts")
    for p in sorted(posts, key=lambda x: x.get("date","")):
        net = next((pr.get("network") for pr in p.get("providers",[])), "?")
        media = (p.get("media") or [""])[0][-40:]
        print(f"  {net:12} id={p.get('id')} | {media}")

# Probar un update simple en el primer post encontrado
posts_20 = get_posts("2026-07-20T00:00:00+02:00","2026-07-20T23:59:00+02:00")
if posts_20:
    p = posts_20[0]
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    print(f"\nProbando update en: id={p['id']} net={net}")
    info = {
        "autoPublish": True, "draft": False,
        "text": p.get("text",""),
        "media": [f"{BASE}/DP-F0-081-misma-escena/reel_v2.mp4"],
        "providers": p.get("providers",[]),
        "publicationDate": p.get("publicationDate",{}),
        "descendants":[],"firstCommentText":"","hasNotReadNotes":False,
        "shortener":False,"smartLinkData":{"ids":[]},
    }
    ck = NET_KEY.get(net)
    if ck and ck in p: info[ck] = p[ck]
    r = call_tool("updateScheduledPost",{"blogId":BLOG_ID,"id":str(p["id"]),
        "uuid":p.get("uuid",""),"info":json.dumps(info,ensure_ascii=False)})
    text = r["content"][0]["text"] if r.get("content") else ""
    print(f"  isError: {r.get('isError')} | text: {text[:100]}")
