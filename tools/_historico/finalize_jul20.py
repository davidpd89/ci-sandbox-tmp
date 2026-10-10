"""Mueve el Pinterest de capítulos al 20 y ajusta horas de todos los posts."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
NET_KEY = {"instagram":"instagramData","facebook":"facebookData","tiktok":"tiktokData",
           "threads":"threadsData","bluesky":"blueskyData","pinterest":"pinterestData"}

def get_posts(fd, td):
    r = call_tool("getScheduledPosts",{"brandId":BLOG_ID,"fromDate":fd,"toDate":td,"timezone":"Europe/Madrid"})
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text) if text else {}
    posts = raw.get("data") or raw.get("posts") or []
    return [p for p in posts if not p.get("draft")]

def move(post, new_date, new_time):
    net = next((pr.get("network") for pr in post.get("providers",[])), "?")
    info = {
        "autoPublish":True,"draft":False,"text":post.get("text",""),
        "media":post.get("media",[]),"providers":post.get("providers",[]),
        "publicationDate":{"dateTime":f"{new_date}T{new_time}:00","timezone":"Europe/Madrid"},
        "descendants":[],"firstCommentText":"","hasNotReadNotes":False,
        "shortener":False,"smartLinkData":{"ids":[]},
    }
    ck = NET_KEY.get(net)
    if ck and ck in post: info[ck] = post[ck]
    r = call_tool("updateScheduledPost",{"blogId":BLOG_ID,"id":str(post["id"]),
        "uuid":post.get("uuid",""),"info":json.dumps(info,ensure_ascii=False)})
    text = r["content"][0]["text"] if r.get("content") else ""
    if r.get("isError"): return f"ERR:{text[:50]}"
    try: return f"OK id={json.loads(text).get('data',{}).get('id','?')}"
    except: return "OK"

# Mover Pinterest capítulos que quedó en Jul 19
posts_19 = get_posts("2026-07-19T00:00:00+02:00","2026-07-19T23:59:00+02:00")
cap_pi_19 = [p for p in posts_19 if p.get("id") in {344580418} or
             ("conocen la sensación" in p.get("text","") or "cerrar un libro antes" in p.get("text",""))]
for p in cap_pi_19:
    print(f"Pinterest capítulos → Jul 20 21:00: {move(p,'2026-07-20','21:00')}")

# Ajustar horas en Jul 20 (spread a lo largo del día)
posts_20 = get_posts("2026-07-20T00:00:00+02:00","2026-07-20T23:59:00+02:00")
print(f"\nJul 20 actual: {len(posts_20)} posts")

# Horario objetivo para Jul 20 (bien espaciado)
# Jul 20 solo tiene DP-F0-076 capítulos
target_times = {
    "instagram": "16:00", "threads": "17:00", "bluesky": "17:30",
    "tiktok": "18:30", "facebook": "20:00", "pinterest": "21:00"
}
for p in posts_20:
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    target = target_times.get(net)
    if not target: continue
    cur_time = p.get("date","")[11:16]
    if cur_time != target:
        print(f"  {net:12} {cur_time} → {target}: {move(p,'2026-07-20',target)}")
    else:
        print(f"  {net:12} {cur_time} OK")

# Estado final
print("\n=== Jul 19 FINAL ===")
for p in sorted(get_posts("2026-07-19T00:00:00+02:00","2026-07-19T23:59:00+02:00"),key=lambda x:x.get("date","")):
    net = next((pr.get("network") for pr in p.get("providers",[])),  "?")
    print(f"  {net:12} {p.get('date','')[11:16]} {p.get('text','')[:30]}")
print("\n=== Jul 20 FINAL ===")
for p in sorted(get_posts("2026-07-20T00:00:00+02:00","2026-07-20T23:59:00+02:00"),key=lambda x:x.get("date","")):
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    print(f"  {net:12} {p.get('date','')[11:16]} {p.get('text','')[:30]}")
