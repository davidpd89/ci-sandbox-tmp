"""Fuerza a Metricool a re-descargar los vídeos actualizados usando la misma URL."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
BASE = "https://davidpd89.github.io/rrss-davidporto-media/videos"
NET_KEY = {"instagram":"instagramData","facebook":"facebookData","tiktok":"tiktokData",
           "threads":"threadsData","bluesky":"blueskyData","pinterest":"pinterestData"}

def get_posts(fd, td):
    r = call_tool("getScheduledPosts",{"brandId":BLOG_ID,"fromDate":fd,"toDate":td,"timezone":"Europe/Madrid"})
    content = r.get("content",[])
    if not content: return []
    text = content[0].get("text","")
    if not text: return []
    try:
        raw = json.loads(text)
        posts = raw.get("data") or raw.get("posts") or (raw if isinstance(raw,list) else [])
        return [p for p in posts if not p.get("draft")]
    except: return []

def force_redownload(p, new_url, new_text=None):
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    info = {
        "autoPublish": True, "draft": False,
        "text": new_text if new_text else p.get("text",""),
        "media": [new_url], "providers": p.get("providers",[]),
        "publicationDate": p.get("publicationDate",{}),
        "descendants":[],"firstCommentText":"","hasNotReadNotes":False,
        "shortener":False,"smartLinkData":{"ids":[]},
    }
    ck = NET_KEY.get(net)
    if ck and ck in p: info[ck] = p[ck]
    r = call_tool("updateScheduledPost",{"blogId":BLOG_ID,"id":str(p["id"]),
        "uuid":p.get("uuid",""),"info":json.dumps(info,ensure_ascii=False)})
    text_r = r["content"][0]["text"] if r.get("content") else ""
    if r.get("isError"): print(f"  {net:12} ERR: {text_r[:60]}"); return False
    print(f"  {net:12} OK"); return True

posts_20 = get_posts("2026-07-20T00:00:00+02:00","2026-07-20T23:59:00+02:00")
posts_21 = get_posts("2026-07-21T00:00:00+02:00","2026-07-21T23:59:00+02:00")
posts_22 = get_posts("2026-07-22T00:00:00+02:00","2026-07-22T23:59:00+02:00")

# Textos correctos para DP-F0-082 (concepto cambiado)
TEXTS_082 = {
    "instagram": "Véndeme tu libro favorito.\n\nSolo tres palabras. Sin 'adictivo'. Sin 'te atrapa'.\n\nLas tuyas en comentarios 👇\n\n#librosqueamo #lectoresreales #cosasdelectores #comunidadlectora #bookstagrammer #instalibros #librosenespañol #booktok",
    "facebook": "Véndeme tu libro favorito. Solo tres palabras. Sin 'adictivo'.\n\n¿Las tuyas?\n\nhttps://davidportodiaz.com",
    "tiktok": "Véndeme tu libro favorito. Solo tres palabras.\n\n#librosqueamo #lectoresreales #cosasdelectores #booktok #instalibros #comunidadlectora #parati",
    "threads": "Véndeme tu libro favorito. Solo tres palabras. Sin 'adictivo'. Las tuyas. #Lectura",
    "bluesky": "Véndeme tu libro favorito. Solo tres palabras. Sin 'adictivo'. Las tuyas. Empieza.",
    "pinterest": "Para lectores que saben exactamente cómo describir lo que les cambió un libro.",
}

# Identificar posts por texto clave
def group_by_text(posts, keywords):
    return [p for p in posts if any(k.lower() in p.get("text","").lower() for k in keywords)]

grp_081 = group_by_text(posts_20, ["leí veinte","misma escena"])
grp_077 = group_by_text(posts_21, ["libro ya vivió","pasó por otras","traía una nota"])
grp_082 = group_by_text(posts_21, ["no enseño","no presto","guardo","véndeme"])
grp_078 = group_by_text(posts_22, ["olvidé el final","quedé quieto"])
grp_083 = group_by_text(posts_22, ["protagonista","secundario"])

print(f"Grupos: 081={len(grp_081)} 077={len(grp_077)} 082={len(grp_082)} 078={len(grp_078)} 083={len(grp_083)}")

for label, grp, url, texts in [
    ("DP-F0-081 Jul20", grp_081, f"{BASE}/DP-F0-081-misma-escena/reel.mp4", None),
    ("DP-F0-077 Jul21", grp_077, f"{BASE}/DP-F0-077-libro-ya-vivio/reel.mp4", None),
    ("DP-F0-082 Jul21", grp_082, f"{BASE}/DP-F0-082-libro-que-no-enseno/reel.mp4", TEXTS_082),
    ("DP-F0-078 Jul22", grp_078, f"{BASE}/DP-F0-078-olvide-el-final/reel.mp4", None),
    ("DP-F0-083 Jul22", grp_083, f"{BASE}/DP-F0-083-secundario-roba-novela/reel.mp4", None),
]:
    print(f"\n=== {label} ===")
    for p in grp:
        net = next((pr.get("network") for pr in p.get("providers",[])), "?")
        new_text = texts.get(net) if texts else None
        force_redownload(p, url, new_text)

print("\nListo.")
