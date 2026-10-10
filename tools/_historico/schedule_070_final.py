import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

BLOG_ID = "6435452"
VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-070-kindle-con-polvo/reel.mp4"

POSTS = [
    {
        "name": "TikTok",
        "date": "2026-07-15T10:00:00+02:00",
        "providers": [{"network": "tiktok"}],
        "text": "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está.\n\n¿Cuál llevas meses prometiéndote leer?\n\n#booktok #booktokespañol #libros #lectores #frasesdelibros #kindle #leoporquequiero #parati",
        "extra": {"tiktokData": {"title": "Me compré el Kindle para leer más", "privacy": "PUBLIC_TO_EVERYONE", "disableDuet": False, "disableStitch": False, "disableComments": False}},
    },
    {
        "name": "Instagram",
        "date": "2026-07-15T11:00:00+02:00",
        "providers": [{"network": "instagram"}],
        "text": "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está.\n\n¿Qué llevas meses prometiéndote leer? Te leo en comentarios 👇\n\n#booktok #bookstagram #librosenespañol #lectores #frasesdelibros #booktokespañol #kindle #lectoresreales #bloqueoloctor",
        "extra": {"instagramData": {"type": "REEL", "showReelOnFeed": True}},
    },
    {
        "name": "Facebook",
        "date": "2026-07-15T12:30:00+02:00",
        "providers": [{"network": "facebook"}],
        "text": "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está.\n\n¿Qué llevas meses prometiéndote leer?\n\nhttps://davidportodiaz.com",
        "extra": {"facebookData": {"type": "REEL"}},
    },
    {
        "name": "Threads",
        "date": "2026-07-15T19:00:00+02:00",
        "providers": [{"network": "threads"}],
        "text": "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está.\n\n¿Qué llevas meses prometiéndote leer? #Lectura",
        "extra": {"threadsData": {}},
    },
    {
        "name": "Bluesky",
        "date": "2026-07-15T21:15:00+02:00",
        "providers": [{"network": "bluesky"}],
        "text": "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está. ¿Qué llevas meses prometiéndote leer?",
        "extra": {"blueskyData": {}},
    },
]

created_ids = []
for post in POSTS:
    info = {
        "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
        "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
        "media": [VIDEO_URL],
        "providers": post["providers"],
        "text": post["text"],
        "publicationDate": {"dateTime": post["date"][:19], "timezone": "Europe/Madrid"},
    }
    info.update(post["extra"])

    print(f"\n{post['name']} @ {post['date'][:16]}...", end=" ")
    r = call_tool("createScheduledPost", {
        "blogId": BLOG_ID,
        "date": post["date"],
        "info": json.dumps(info, ensure_ascii=False)
    })
    text = r["content"][0]["text"] if r.get("content") else ""
    is_err = r.get("isError") or (text and json.loads(text).get("isError") if text.startswith("{") else False)
    if is_err or not text:
        print(f"ERROR: {text[:150]}")
    else:
        try:
            raw = json.loads(text)
            pid = (raw.get("id") or raw.get("post", {}).get("id") or
                   next((v for k, v in raw.items() if "id" in k.lower() and isinstance(v, (int, str))), "?"))
            print(f"OK id={pid}")
            created_ids.append(pid)
        except Exception as e:
            print(f"OK (parse error: {e}) raw={text[:100]}")

# Verificar
print("\n=== Verificando posts creados ===")
r = call_tool("getScheduledPosts", {
    "brandId": BLOG_ID,
    "fromDate": "2026-07-14T22:00:00+02:00",
    "toDate": "2026-07-15T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"]
raw = json.loads(text)
posts_found = raw if isinstance(raw, list) else raw.get("posts", [])
dp070 = [p for p in posts_found if not p.get("draft") and VIDEO_URL in json.dumps(p.get("media", []))]
print(f"Posts con video DP-F0-070 encontrados: {len(dp070)}")
for p in dp070:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    print(f"  {net:15} {p.get('date','')[:16]} id={p.get('id')}")
