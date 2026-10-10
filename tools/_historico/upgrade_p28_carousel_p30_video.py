# -*- coding: utf-8 -*-
"""
Actualiza P28 con carrusel de autores y P30 con video animado.
P28: slides en Instagram (multi-imagen), portada en el resto.
P30: video con zoom+musica en Instagram, imagen en el resto.
"""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout
import os; os.chdir(r"C:\GIT\RRSS_DavidPorto\tools")
from metricool_client import call_tool

BLOG_ID = "6435452"
TZ = "Europe/Madrid"
SITE = "https://davidportodiaz.com"
ASSETS = "https://davidportodiaz.com/assets"
MEDIA_BASE = "https://davidpd89.github.io/rrss-davidporto-media/videos"

# P28 carousel slides
P28_SLIDES = [
    f"{ASSETS}/p28-citas-escritores/slide_00_portada.png",
    f"{ASSETS}/p28-citas-escritores/slide_01_kafka.png",
    f"{ASSETS}/p28-citas-escritores/slide_02_woolf.png",
    f"{ASSETS}/p28-citas-escritores/slide_03_cortazar.png",
    f"{ASSETS}/p28-citas-escritores/slide_04_dostoievski.png",
    f"{ASSETS}/p28-citas-escritores/slide_05_borges.png",
    f"{ASSETS}/p28-citas-escritores/slide_06_cta_v2.png",
]
P28_PORTADA = P28_SLIDES[0]

# P30 video
P30_VIDEO = f"{MEDIA_BASE}/reel_dp_p30_ig.mp4"
P30_IMAGE = f"{ASSETS}/1000106606_v3.png"

NET_KEY = {
    "instagram": "instagramData",
    "facebook": "facebookData",
    "tiktok": "tiktokData",
    "threads": "threadsData",
    "bluesky": "blueskyData",
    "pinterest": "pinterestData",
}


def get_posts():
    r = call_tool("getScheduledPosts", {
        "brandId": BLOG_ID,
        "fromDate": "2026-07-24T00:00:00Z",
        "toDate": "2026-07-25T23:59:59Z",
        "timezone": TZ,
    })
    content = r.get("content", [])
    text = content[0].get("text", "") if content else ""
    try:
        return json.loads(text).get("data", [])
    except Exception:
        return []


def posts_in_window(all_posts, date, t_start, t_end):
    result = []
    for p in all_posts:
        dt = p.get("publicationDate", {}).get("dateTime", "")
        if not dt.startswith(date):
            continue
        t = dt[11:16]
        if t_start <= t <= t_end:
            result.append(p)
    return result


def update_post(p, new_media, ig_type=None, extra_data=None):
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    info = {
        "autoPublish": True,
        "draft": False,
        "text": p.get("text", ""),
        "media": new_media,
        "providers": p.get("providers", []),
        "publicationDate": p.get("publicationDate", {}),
        "descendants": [],
        "firstCommentText": "",
        "hasNotReadNotes": False,
        "shortener": False,
        "smartLinkData": {"ids": []},
    }
    ck = NET_KEY.get(net)
    if ck and ck in p:
        info[ck] = p[ck]

    # Para P30 Instagram: cambiar a REEL si se especifica
    if ig_type and net == "instagram":
        if "instagramData" not in info:
            info["instagramData"] = {}
        info["instagramData"]["type"] = ig_type

    if extra_data and net in extra_data:
        nk = NET_KEY.get(net)
        if nk:
            if nk not in info:
                info[nk] = {}
            info[nk].update(extra_data[net])

    # Pinterest siempre necesita boardId
    if net == "pinterest":
        info["pinterestData"] = {
            "boardId": "1096626646706067804",
            "pinTitle": (p.get("text", "") or "")[:80],
            "pinLink": SITE,
        }

    r = call_tool("updateScheduledPost", {
        "blogId": BLOG_ID,
        "id": str(p["id"]),
        "uuid": p.get("uuid", ""),
        "info": json.dumps(info, ensure_ascii=False),
    })
    ok = not (isinstance(r, dict) and r.get("isError"))
    if not ok:
        ct = r.get("content", [])
        err = ct[0].get("text", str(r))[:200] if ct else str(r)[:200]
        print(f"    ERR {net}: {err}")
    return ok, net


def main():
    print("Esperando 90s para GitHub Pages...")
    time.sleep(90)

    print("\nObteniendo posts Jul 24-25...")
    all_posts = get_posts()
    print(f"Total: {len(all_posts)}")

    # --- P28: Jul 24 07:00-11:00 ---
    print("\n=== P28 carrusel autores (Jul 24 manana) ===")
    p28_posts = posts_in_window(all_posts, "2026-07-24", "07:00", "11:00")
    print(f"  Posts encontrados: {len(p28_posts)}")

    for p in p28_posts:
        net = next((pr.get("network") for pr in p.get("providers", [])), "?")
        dt = p.get("publicationDate", {}).get("dateTime", "?")[11:16]

        if net == "instagram":
            # Carrusel multi-slide
            media = P28_SLIDES
            ok, _ = update_post(p, media)
        else:
            # Portada sola en el resto de redes
            media = [P28_PORTADA]
            ok, _ = update_post(p, media)

        print(f"  {net:12} {dt} -> {'OK' if ok else 'FAIL'} ({len(media)} media)")

    # --- P30: Jul 25 07:00-11:00 ---
    print("\n=== P30 video animado (Jul 25 manana) ===")
    p30_posts = posts_in_window(all_posts, "2026-07-25", "07:00", "11:00")
    print(f"  Posts encontrados: {len(p30_posts)}")

    for p in p30_posts:
        net = next((pr.get("network") for pr in p.get("providers", [])), "?")
        dt = p.get("publicationDate", {}).get("dateTime", "?")[11:16]

        if net == "instagram":
            # Video reel con musica triste
            media = [P30_VIDEO]
            ok, _ = update_post(p, media, ig_type="REEL")
        elif net in ("tiktok", "facebook"):
            # Video tambien en TikTok y Facebook
            media = [P30_VIDEO]
            ok, _ = update_post(p, media)
        else:
            # Threads, Bluesky, Pinterest: imagen estatica
            media = [P30_IMAGE]
            ok, _ = update_post(p, media)

        print(f"  {net:12} {dt} -> {'OK' if ok else 'FAIL'}")

    print("\nActualizacion P28+P30 completada.")


if __name__ == "__main__":
    main()
