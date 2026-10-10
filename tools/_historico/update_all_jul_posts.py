"""Actualiza todos los posts de Jul 20-22 con los nuevos vídeos y textos."""
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

def upd(p, new_url, new_text=None):
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    info = {
        "autoPublish": True, "draft": False,
        "text": new_text if new_text else p.get("text",""),
        "media": [new_url],
        "providers": p.get("providers",[]),
        "publicationDate": p.get("publicationDate",{}),
        "descendants":[],"firstCommentText":"","hasNotReadNotes":False,
        "shortener":False,"smartLinkData":{"ids":[]},
    }
    ck = NET_KEY.get(net)
    if ck and ck in p: info[ck] = p[ck]
    r = call_tool("updateScheduledPost",{"blogId":BLOG_ID,"id":str(p["id"]),
        "uuid":p.get("uuid",""),"info":json.dumps(info,ensure_ascii=False)})
    return not r.get("isError")

posts_20 = get_posts("2026-07-20T00:00:00+02:00","2026-07-20T23:59:00+02:00")
posts_21 = get_posts("2026-07-21T00:00:00+02:00","2026-07-21T23:59:00+02:00")
posts_22 = get_posts("2026-07-22T00:00:00+02:00","2026-07-22T23:59:00+02:00")

# URLs nuevas
URL_081 = f"{BASE}/DP-F0-081-misma-escena/reel_v2.mp4"
URL_077 = f"{BASE}/DP-F0-077-libro-ya-vivio/reel_v3.mp4"
URL_082 = f"{BASE}/DP-F0-082-libro-que-no-enseno/reel_v2.mp4"
URL_078 = f"{BASE}/DP-F0-078-olvide-el-final/reel_v3.mp4"
URL_083 = f"{BASE}/DP-F0-083-secundario-roba-novela/reel_v2.mp4"

# Textos para DP-F0-082 (concepto nuevo)
TEXTS_082 = {
    "instagram": "Véndeme tu libro favorito.\n\nSolo tres palabras. Sin 'adictivo'. Sin 'te atrapa'.\n\nLas tuyas. Las que a ti te cambió. En comentarios 👇\n\n#librosqueamo #lectoresreales #cosasdelectores #comunidadlectora #bookstagrammer #libroslibroslibros #instalibros #booktok",
    "facebook":  "Véndeme tu libro favorito. Solo tres palabras. Sin 'adictivo'.\n\nLas tuyas. Las que a ti te cambió. En comentarios 👇\n\nhttps://davidportodiaz.com",
    "tiktok":    "Véndeme tu libro favorito. Solo tres palabras.\n\n#librosqueamo #lectoresreales #cosasdelectores #booktok #instalibros #comunidadlectora #parati",
    "threads":   "Véndeme tu libro favorito. Solo tres palabras. Sin 'adictivo'. Las tuyas. En comentarios 👇 #Lectura",
    "bluesky":   "Véndeme tu libro favorito. Solo tres palabras. Sin 'adictivo'. Las tuyas. Empieza.",
    "pinterest": "Para lectores que saben exactamente cómo describir lo que les cambió un libro.",
}

# IDs por pieza (extraídos de la programación anterior)
IDS_081 = {344630303,344630312,344630318,344630322,344630329,344630335}
IDS_077 = {344601101,344601107,344601111,344601114,344601117,344601122}
IDS_082 = {344630341,344630346,344630354,344630359,344630365,344630370}
IDS_078 = {344601129,344601138,344601143,344601148,344601153,344601157}
IDS_083 = {344630384,344630390,344630392,344630399,344630406,344630412}

def update_batch(posts, ids, url, texts=None, label=""):
    matched = [p for p in posts if p.get("id") in ids]
    print(f"\n{label} ({len(matched)} posts):")
    for p in matched:
        net = next((pr.get("network") for pr in p.get("providers",[])), "?")
        new_text = texts.get(net) if texts else None
        ok = upd(p, url, new_text)
        print(f"  {net:12} {'OK' if ok else 'ERR'}")

update_batch(posts_20, IDS_081, URL_081, label="DP-F0-081 Jul20")
update_batch(posts_21, IDS_077, URL_077, label="DP-F0-077 Jul21")
update_batch(posts_21, IDS_082, URL_082, TEXTS_082, label="DP-F0-082 Jul21 (nuevo texto)")
update_batch(posts_22, IDS_078, URL_078, label="DP-F0-078 Jul22")
update_batch(posts_22, IDS_083, URL_083, label="DP-F0-083 Jul22")
print("\nListo.")
