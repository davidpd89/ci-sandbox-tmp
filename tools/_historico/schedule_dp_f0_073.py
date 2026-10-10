"""Programa DP-F0-073 'Enemies to lovers' para el 19 de julio 2026."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-073-enemies-to-lovers/reel.mp4"

POSTS = [
    {
        "name": "Threads 08:00",
        "date": "2026-07-19T08:00:00+02:00",
        "providers": [{"network": "threads"}],
        "text": "Si se odian demasiado, ya sospecho. Y yo ya he comprado el arroz. ¿Qué enemies to lovers te tuvo así? #Lectura",
        "extra": {"threadsData": {}},
    },
    {
        "name": "TikTok 09:30",
        "date": "2026-07-19T09:30:00+02:00",
        "providers": [{"network": "tiktok"}],
        "text": "Si se odian demasiado, ya sospecho.\n\nY yo ya he comprado el arroz. ¿Qué enemies to lovers te tuvo así?\n\n#booktok #slowburn #enemiestolovers #romantasy #librosenespañol #humorlector #bookish #parati",
        "extra": {"tiktokData": {"title": "Si se odian demasiado, ya sospecho.", "privacy": "PUBLIC_TO_EVERYONE", "disableDuet": False, "disableStitch": False, "disableComments": False}},
    },
    {
        "name": "Bluesky 10:30",
        "date": "2026-07-19T10:30:00+02:00",
        "providers": [{"network": "bluesky"}],
        "text": "Si se odian demasiado, ya sospecho. Discuten. Se miran. Miran para otro lado. Y yo ya he comprado el arroz. ¿Cuál fue el tuyo?",
        "extra": {"blueskyData": {}},
    },
    {
        "name": "Instagram 11:00",
        "date": "2026-07-19T11:00:00+02:00",
        "providers": [{"network": "instagram"}],
        "text": "Si se odian demasiado, ya sospecho.\n\nY yo ya he comprado el arroz. ¿Qué enemies to lovers te tuvo así? 👇\n\n#booktok #slowburn #enemiestolovers #romantasy #librosenespañol #humorlector #lectores #bookish",
        "extra": {"instagramData": {"type": "REEL", "showReelOnFeed": True}},
    },
    {
        "name": "Facebook 12:30",
        "date": "2026-07-19T12:30:00+02:00",
        "providers": [{"network": "facebook"}],
        "text": "Hay libros en los que sabes cómo va a acabar desde el capítulo 3.\n\nY los lees igual. Los 400 páginas.\n\n¿Cuál fue el tuyo?\n\nhttps://davidportodiaz.com",
        "extra": {"facebookData": {"type": "REEL"}},
    },
    {
        "name": "Pinterest 15:30",
        "date": "2026-07-19T15:30:00+02:00",
        "providers": [{"network": "pinterest"}],
        "text": "Para lectores que ya han comprado el arroz antes de llegar al capítulo 10.",
        "extra": {"pinterestData": {"boardId": "1081178560003791073", "pinTitle": "Si se odian demasiado, ya sospecho — enemies to lovers", "pinLink": "https://davidportodiaz.com"}},
    },
]

created = []
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
    print(f"{post['name']}...", end=" ")
    r = call_tool("createScheduledPost", {
        "blogId": BLOG_ID,
        "date": post["date"],
        "info": json.dumps(info, ensure_ascii=False)
    })
    text = r["content"][0]["text"] if r.get("content") else ""
    if not text or r.get("isError"):
        print(f"ERROR: {text[:80]}")
    else:
        try:
            raw = json.loads(text)
            pid = raw.get("data", {}).get("id", "?")
            print(f"OK id={pid}")
            created.append({"net": post["name"], "id": pid})
        except Exception as e:
            print(f"OK ({e})")

print(f"\nCreados: {len(created)}/6")
for c in created:
    print(f"  {c['net']:25} id={c['id']}")
