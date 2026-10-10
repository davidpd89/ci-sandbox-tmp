"""Fuerza a Metricool a releer los vídeos actualizados de DP-F0-077 y 078."""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool
import urllib.request

BLOG_ID = "6435452"
NET_KEY = {"instagram":"instagramData","facebook":"facebookData","tiktok":"tiktokData",
           "threads":"threadsData","bluesky":"blueskyData","pinterest":"pinterestData"}

# Esperar a que GitHub Pages esté listo
URLS = [
    "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-077-libro-ya-vivio/reel.mp4",
    "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-078-olvide-el-final/reel.mp4",
]
print("Verificando URLs...")
for url in URLS:
    for _ in range(20):
        try:
            req = urllib.request.Request(url, method="HEAD")
            resp = urllib.request.urlopen(req, timeout=5)
            if resp.status == 200:
                print(f"  LIVE: {url[-50:]}")
                break
        except Exception:
            time.sleep(5)

def get_posts(fd, td):
    r = call_tool("getScheduledPosts",{"brandId":BLOG_ID,"fromDate":fd,"toDate":td,"timezone":"Europe/Madrid"})
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text) if text else {}
    posts = raw.get("data") or raw.get("posts") or []
    return [p for p in posts if not p.get("draft")]

# IDs Jul 21 (DP-F0-077) y Jul 22 (DP-F0-078)
IDS_077 = {344601101, 344601107, 344601111, 344601114, 344601117, 344601122}
IDS_078 = {344601129, 344601138, 344601143, 344601148, 344601153, 344601157}

URL_077 = URLS[0]
URL_078 = URLS[1]

posts_21 = get_posts("2026-07-21T00:00:00+02:00","2026-07-21T23:59:00+02:00")
posts_22 = get_posts("2026-07-22T00:00:00+02:00","2026-07-22T23:59:00+02:00")

def force_update(posts, target_ids, new_url):
    for p in posts:
        if p.get("id") not in target_ids: continue
        net = next((pr.get("network") for pr in p.get("providers",[])), "?")
        info = {
            "autoPublish": True, "draft": False,
            "text": p.get("text",""),
            "media": [new_url],  # forzar nuevo URL
            "providers": p.get("providers",[]),
            "publicationDate": p.get("publicationDate",{}),
            "descendants":[],"firstCommentText":"","hasNotReadNotes":False,
            "shortener":False,"smartLinkData":{"ids":[]},
        }
        ck = NET_KEY.get(net)
        if ck and ck in p: info[ck] = p[ck]
        r = call_tool("updateScheduledPost",{"blogId":BLOG_ID,"id":str(p["id"]),
            "uuid":p.get("uuid",""),"info":json.dumps(info,ensure_ascii=False)})
        ok = not r.get("isError")
        print(f"  {net:12} id={p['id']}: {'OK' if ok else 'ERR'}")

print("\nActualizando DP-F0-077 (Jul 21)...")
force_update(posts_21, IDS_077, URL_077)
print("\nActualizando DP-F0-078 (Jul 22)...")
force_update(posts_22, IDS_078, URL_078)
print("\nListo.")
