# -*- coding: utf-8 -*-
"""Actualiza los 3 posts Instagram fallidos con los videos cortos de imagen."""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout
import os; os.chdir(r"C:\GIT\RRSS_DavidPorto\tools")
from metricool_client import call_tool

BLOG_ID = "6435452"
TZ = "Europe/Madrid"
BASE_VID = "https://davidpd89.github.io/rrss-davidporto-media/videos"
SITE = "https://davidportodiaz.com"

NET_KEY = {
    "instagram": "instagramData",
    "facebook": "facebookData",
    "tiktok": "tiktokData",
    "threads": "threadsData",
    "bluesky": "blueskyData",
    "pinterest": "pinterestData",
}

FIXES = [
    {
        "id": 345573185,
        "uuid": "-5226623624832791745",
        "video": f"{BASE_VID}/reel_dp_p27_ig.mp4",
        "caption": (
            "Tengo libros en la mesilla que cumplen anyos ahi. "
            "Uno lleva tanto tiempo que ya tiene sitio fijo.\n\n"
            "Cual es el tuyo? El que llevas meses prometiendote que ya lo empiezas "
            "y sigue igual de nuevo.\n\n"
            "En comentarios\n\n"
            "#bookstagram #libros #lectoresdeinstagram #librosenespanol #lectura "
            "#bibliofilo #leersies #instalibros #librosencastellano"
        ),
        "date": "2026-07-23T11:00:00",
        "label": "P27 Instagram",
    },
    {
        "id": 345573227,
        "uuid": "-3978476135114849268",
        "video": f"{BASE_VID}/reel_dp_p29_ig.mp4",
        "caption": (
            "A veces la decision mas valiente no es quedarse.\n\n"
            "Con cual de las dos voces te has sentido mas identificado/a alguna vez?\n\n"
            "Sin nombre si quieres. Solo la voz. En comentarios\n\n"
            "#frases #reflexiones #emociones #bookstagram #libros "
            "#librosenespanol #citas #pensamientos #lectores"
        ),
        "date": "2026-07-24T17:00:00",
        "label": "P29 Instagram",
    },
    {
        "id": 345573267,
        "uuid": "-6259646760837169085",
        "video": f"{BASE_VID}/reel_dp_p31_ig.mp4",
        "caption": (
            "Hay alguien que necesita leer esto hoy.\n\n"
            "Sabes exactamente quien es.\n\n"
            "#emociones #apoyo #amistad #bookstagram #reflexiones "
            "#frases #conexiones #librosenespanol #lectores"
        ),
        "date": "2026-07-25T16:00:00",
        "label": "P31 Instagram",
    },
]

print("Esperando 30s para que GitHub Pages despliegue los videos...")
time.sleep(30)

# Get current post data
def get_posts():
    r = call_tool("getScheduledPosts", {
        "brandId": BLOG_ID,
        "fromDate": "2026-07-23T00:00:00Z",
        "toDate": "2026-07-25T23:59:59Z",
        "timezone": TZ,
    })
    content = r.get("content", [])
    text = content[0].get("text", "") if content else ""
    try:
        return json.loads(text).get("data", [])
    except Exception:
        return []

all_posts = get_posts()
post_map = {p["id"]: p for p in all_posts}

for fix in FIXES:
    pid = fix["id"]
    p = post_map.get(pid)
    if not p:
        print(f"  {fix['label']}: POST NOT FOUND (id={pid})")
        continue

    net = "instagram"
    info = {
        "autoPublish": True,
        "draft": False,
        "text": fix["caption"],
        "media": [fix["video"]],
        "providers": p.get("providers", []),
        "publicationDate": {"dateTime": fix["date"], "timezone": TZ},
        "descendants": [],
        "firstCommentText": "",
        "hasNotReadNotes": False,
        "shortener": False,
        "smartLinkData": {"ids": []},
        "instagramData": {"autoPublish": True, "type": "REEL"},
    }

    r = call_tool("updateScheduledPost", {
        "blogId": BLOG_ID,
        "id": str(pid),
        "uuid": fix["uuid"],
        "info": json.dumps(info, ensure_ascii=False),
    })
    ok = not (isinstance(r, dict) and r.get("isError"))
    if not ok:
        content = r.get("content", [])
        err = content[0].get("text", str(r))[:200] if content else str(r)[:200]
        print(f"  {fix['label']}: FAIL — {err}")
    else:
        print(f"  {fix['label']}: OK")

print("\nListo.")
