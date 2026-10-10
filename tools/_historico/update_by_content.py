"""Actualiza posts de Jul 20-22 buscando por contenido actual, no IDs hardcoded."""
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
    if r.get("isError"):
        print(f"  {net:12} ERR: {text_r[:80]}")
        return False
    print(f"  {net:12} OK")
    return True

posts_20 = get_posts("2026-07-20T00:00:00+02:00","2026-07-20T23:59:00+02:00")
posts_21 = get_posts("2026-07-21T00:00:00+02:00","2026-07-21T23:59:00+02:00")
posts_22 = get_posts("2026-07-22T00:00:00+02:00","2026-07-22T23:59:00+02:00")

# Identificar grupos por hora/texto de cada pieza
def get_group(posts, time_prefix=None, text_kw=None):
    """Filtra posts por hora o palabra clave en texto."""
    result = []
    for p in posts:
        t = p.get("date","")
        txt = p.get("text","").lower()
        if time_prefix and time_prefix in t: result.append(p)
        elif text_kw and any(k in txt for k in text_kw): result.append(p)
    return result

# Jul 20: DP-F0-076 (capítulos, 16:00+) y DP-F0-081 (misma escena, 08:30-15:00)
grp_081 = get_group(posts_20, text_kw=["leí veinte", "misma escena"])
grp_082 = get_group(posts_21, text_kw=["no enseño", "no presto", "guardo"])
grp_077 = [p for p in posts_21 if p not in grp_082]  # los otros 6 de Jul 21
grp_083 = get_group(posts_22, text_kw=["protagonista", "secundario"])
grp_078 = [p for p in posts_22 if p not in grp_083]

# Textos nuevos para 082 (concepto cambiado)
TEXTS_082 = {
    "instagram": "Véndeme tu libro favorito.\n\nSolo tres palabras. Sin 'adictivo'. Sin 'te atrapa'.\n\nLas tuyas en comentarios 👇\n\n#librosqueamo #lectoresreales #cosasdelectores #comunidadlectora #bookstagrammer #instalibros #librosenespañol #booktok",
    "facebook": "Véndeme tu libro favorito. Solo tres palabras. Sin 'adictivo'.\n\nLas tuyas en comentarios 👇\n\nhttps://davidportodiaz.com",
    "tiktok": "Véndeme tu libro favorito. Solo tres palabras.\n\n#librosqueamo #lectoresreales #cosasdelectores #booktok #instalibros #comunidadlectora #parati",
    "threads": "Véndeme tu libro favorito. Solo tres palabras. Sin 'adictivo'. Las tuyas. #Lectura",
    "bluesky": "Véndeme tu libro favorito. Solo tres palabras. Sin 'adictivo'. Las tuyas. Empieza.",
    "pinterest": "Para lectores que saben exactamente cómo describir lo que les cambió un libro.",
}

print(f"\nGrupos identificados:")
print(f"  DP-F0-081 (misma escena) Jul20: {len(grp_081)}")
print(f"  DP-F0-077 (libro ya vivió) Jul21: {len(grp_077)}")
print(f"  DP-F0-082 (véndeme tu libro) Jul21: {len(grp_082)}")
print(f"  DP-F0-078 (olvidé el final) Jul22: {len(grp_078)}")
print(f"  DP-F0-083 (secundario) Jul22: {len(grp_083)}")

print(f"\n=== DP-F0-081 Jul20 → reel_v2 ===")
for p in grp_081: upd(p, f"{BASE}/DP-F0-081-misma-escena/reel_v2.mp4")

print(f"\n=== DP-F0-077 Jul21 → reel_v3 ===")
for p in grp_077: upd(p, f"{BASE}/DP-F0-077-libro-ya-vivio/reel_v3.mp4")

print(f"\n=== DP-F0-082 Jul21 → reel_v2 + texto nuevo ===")
for p in grp_082:
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    upd(p, f"{BASE}/DP-F0-082-libro-que-no-enseno/reel_v2.mp4", TEXTS_082.get(net))

print(f"\n=== DP-F0-078 Jul22 → reel_v3 ===")
for p in grp_078: upd(p, f"{BASE}/DP-F0-078-olvide-el-final/reel_v3.mp4")

print(f"\n=== DP-F0-083 Jul22 → reel_v2 ===")
for p in grp_083: upd(p, f"{BASE}/DP-F0-083-secundario-roba-novela/reel_v2.mp4")

print("\nListo.")
