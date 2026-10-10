"""Programa DP-F0-075 'Se me fue el bus' para el 18 de julio — segunda pieza del día."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-075-se-me-fue-el-bus/reel.mp4"

# Hashtags NUEVOS (nunca usados antes) + los que mejor funcionan
HT_IG = "#cosasdelectores #maniaslectoras #bookstagramespaña #comunidadlectora #librosenespañol #booktok #lectoresunidos #lectores #libroslibroslibros"
HT_TT = "#cosasdelectores #maniaslectoras #booktok #librosenespañol #lectores #comunidadlectora #libroslibroslibros #parati"

POSTS = [
    {
        "name": "Threads 14:00",
        "date": "2026-07-18T14:00:00+02:00",
        "providers": [{"network": "threads"}],
        "text": "Se me fue el bus. Estaba en lo importante. ¿A qué llegas tarde tú? #Lectura",
        "extra": {"threadsData": {}},
    },
    {
        "name": "Bluesky 14:30",
        "date": "2026-07-18T14:30:00+02:00",
        "providers": [{"network": "bluesky"}],
        "text": "Se me fue el bus. Estaba en lo importante. ¿A qué llegas tarde tú?",
        "extra": {"blueskyData": {}},
    },
    {
        "name": "Instagram 16:30",
        "date": "2026-07-18T16:30:00+02:00",
        "providers": [{"network": "instagram"}],
        "text": f"Se me fue el bus.\n\n¿A qué llegas tarde tú? Cuéntame en comentarios 👇\n\n{HT_IG}",
        "extra": {"instagramData": {"type": "REEL", "showReelOnFeed": True}},
    },
    {
        "name": "TikTok 18:00",
        "date": "2026-07-18T18:00:00+02:00",
        "providers": [{"network": "tiktok"}],
        "text": f"Se me fue el bus. Estaba en lo importante.\n\n¿A qué llegas tarde tú?\n\n{HT_TT}",
        "extra": {"tiktokData": {"title": "Se me fue el bus por leer", "privacy": "PUBLIC_TO_EVERYONE", "disableDuet": False, "disableStitch": False, "disableComments": False}},
    },
    {
        "name": "Facebook 20:00",
        "date": "2026-07-18T20:00:00+02:00",
        "providers": [{"network": "facebook"}],
        "text": "Se me fue el bus. Estaba en lo importante.\n\n¿A qué has llegado tarde tú por un libro?\n\nhttps://davidportodiaz.com",
        "extra": {"facebookData": {"type": "REEL"}},
    },
    {
        "name": "Pinterest 22:00",
        "date": "2026-07-18T22:00:00+02:00",
        "providers": [{"network": "pinterest"}],
        "text": "Cuando el libro es más importante que el transporte público. Para lectores que conocen bien la sensación.",
        "extra": {"pinterestData": {"boardId": "1081178560003791073", "pinTitle": "Se me fue el bus. Estaba en lo importante.", "pinLink": "https://davidportodiaz.com"}},
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
    r = call_tool("createScheduledPost", {"blogId": BLOG_ID, "date": post["date"], "info": json.dumps(info, ensure_ascii=False)})
    text = r["content"][0]["text"] if r.get("content") else ""
    if not text or r.get("isError"):
        print(f"ERROR: {text[:80]}")
    else:
        try:
            pid = json.loads(text).get("data", {}).get("id", "?")
            print(f"OK id={pid}")
            created.append(pid)
        except Exception:
            print("OK")

print(f"\nDP-F0-075 programado: {len(created)}/6 posts")
print("\nHorario completo Jul 18:")
print("  08:30 TikTok       — DP-F0-071 Resaca de libro")
print("  09:00 Threads      — DP-F0-071")
print("  10:00 Instagram    — DP-F0-071")
print("  12:00 Facebook     — DP-F0-071")
print("  14:00 Threads      — DP-F0-075 Bus")
print("  14:30 Bluesky      — DP-F0-075 Bus")
print("  15:00 Pinterest    — DP-F0-071")
print("  16:30 Instagram    — DP-F0-075 Bus")
print("  18:00 TikTok       — DP-F0-075 Bus")
print("  20:00 Facebook     — DP-F0-075 Bus")
print("  21:30 Bluesky      — DP-F0-071")
print("  22:00 Pinterest    — DP-F0-075 Bus")
