# -*- coding: utf-8 -*-
"""Reintenta P28 carrusel con espera para GitHub Pages."""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout
import os; os.chdir(r"C:\GIT\RRSS_DavidPorto\tools")
from metricool_client import call_tool
import urllib.request

BLOG_ID = "6435452"
TZ = "Europe/Madrid"
SITE = "https://davidportodiaz.com"
MEDIA = "https://davidpd89.github.io/rrss-davidporto-media/images/p28"

P28_SLIDES = [
    f"{MEDIA}/slide_00_portada.png",
    f"{MEDIA}/slide_01_kafka.png",
    f"{MEDIA}/slide_02_woolf.png",
    f"{MEDIA}/slide_03_cortazar.png",
    f"{MEDIA}/slide_04_dostoievski.png",
    f"{MEDIA}/slide_05_borges.png",
    f"{MEDIA}/slide_06_cta_v2.png",
]
P28_PORTADA = P28_SLIDES[0]

NET_KEY = {
    "instagram": "instagramData", "facebook": "facebookData",
    "tiktok": "tiktokData", "threads": "threadsData",
    "bluesky": "blueskyData", "pinterest": "pinterestData",
}


def check_url(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def get_posts():
    r = call_tool("getScheduledPosts", {
        "brandId": BLOG_ID,
        "fromDate": "2026-07-24T00:00:00Z",
        "toDate": "2026-07-24T12:00:00Z",
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


def update_post(p, new_media):
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    info = {
        "autoPublish": True, "draft": False,
        "text": p.get("text", ""),
        "media": new_media,
        "providers": p.get("providers", []),
        "publicationDate": p.get("publicationDate", {}),
        "descendants": [], "firstCommentText": "",
        "hasNotReadNotes": False, "shortener": False,
        "smartLinkData": {"ids": []},
    }
    ck = NET_KEY.get(net)
    if ck and ck in p:
        info[ck] = p[ck]
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
    return ok


def main():
    # Esperar hasta que la URL de portada este accesible (max 8 min)
    print("Comprobando disponibilidad de GitHub Pages...")
    for i in range(16):
        if check_url(P28_PORTADA):
            print(f"  OK — slide_00_portada.png accesible ({i*30}s espera)")
            break
        print(f"  Aun no disponible, esperando... ({i*30}s)")
        time.sleep(30)
    else:
        print("  TIMEOUT — intentando igualmente...")

    all_posts = get_posts()
    p28 = posts_in_window(all_posts, "2026-07-24", "07:00", "11:00")
    print(f"\nP28 posts: {len(p28)}")

    for p in p28:
        net = next((pr.get("network") for pr in p.get("providers", [])), "?")
        dt = p.get("publicationDate", {}).get("dateTime", "?")[11:16]
        if net == "gmb":
            print(f"  {net:12} {dt} SKIP (Google My Business no relevante)")
            continue
        media = P28_SLIDES if net == "instagram" else [P28_PORTADA]
        ok = update_post(p, media)
        print(f"  {net:12} {dt} -> {'OK' if ok else 'FAIL'} ({len(media)} slides)")

    print("\nReintentar P28 completado.")


if __name__ == "__main__":
    main()
