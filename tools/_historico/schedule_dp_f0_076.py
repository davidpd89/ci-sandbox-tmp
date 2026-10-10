"""Programa DP-F0-076 'Hay capítulos que no terminas' — Jul 19, segunda pieza."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-076-capitulos-que-no-terminas/reel.mp4"

# Hashtags nuevos que no hemos usado aún
HT_IG = "#clubdelectura #librosymaslibros #bookstagrammer #cosasdelectores #lectoresunidos #librosenespañol #booktok #lectores #maniaslectoras"
HT_TT = "#clubdelectura #bookstagrammer #booktok #lectores #librosenespañol #cosasdelectores #lectoresunidos #parati"

# Jul 19 — DP-F0-073 ocupa: 08:00 Th, 09:30 TT, 10:30 BS, 11:00 IG, 12:30 FB, 15:30 Pi
POSTS = [
    {"name": "Threads 17:00",   "date": "2026-07-19T17:00:00+02:00", "providers": [{"network": "threads"}],
     "text": "Hay capítulos que no terminas. Los cierras. ¿Cuál fue el tuyo? #Lectura",
     "extra": {"threadsData": {}}},
    {"name": "Bluesky 17:30",   "date": "2026-07-19T17:30:00+02:00", "providers": [{"network": "bluesky"}],
     "text": "Hay capítulos que no terminas. Los cierras. ¿Cuál fue el tuyo?",
     "extra": {"blueskyData": {}}},
    {"name": "Instagram 16:00", "date": "2026-07-19T16:00:00+02:00", "providers": [{"network": "instagram"}],
     "text": f"Hay capítulos que no terminas.\n\n¿Cuál fue el tuyo? Dímelo en comentarios 👇\n\n{HT_IG}",
     "extra": {"instagramData": {"type": "REEL", "showReelOnFeed": True}}},
    {"name": "TikTok 18:30",    "date": "2026-07-19T18:30:00+02:00", "providers": [{"network": "tiktok"}],
     "text": f"Hay capítulos que no terminas. Los cierras.\n\n¿Cuál fue el tuyo?\n\n{HT_TT}",
     "extra": {"tiktokData": {"title": "Hay capítulos que no terminas", "privacy": "PUBLIC_TO_EVERYONE", "disableDuet": False, "disableStitch": False, "disableComments": False}}},
    {"name": "Facebook 20:00",  "date": "2026-07-19T20:00:00+02:00", "providers": [{"network": "facebook"}],
     "text": "Hay capítulos que no terminas. Los cierras para que no te vean la cara.\n\n¿Cuál fue el tuyo?\n\nhttps://davidportodiaz.com",
     "extra": {"facebookData": {"type": "REEL"}}},
    {"name": "Pinterest 21:00", "date": "2026-07-19T21:00:00+02:00", "providers": [{"network": "pinterest"}],
     "text": "Para los lectores que conocen la sensación de cerrar un libro antes de tiempo porque no pueden.",
     "extra": {"pinterestData": {"boardId": "1081178560003791073", "pinTitle": "Hay capítulos que no terminas. Los cierras.", "pinLink": "https://davidportodiaz.com"}}},
]

created = []
for post in POSTS:
    info = {"autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
            "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
            "media": [VIDEO_URL], "providers": post["providers"], "text": post["text"],
            "publicationDate": {"dateTime": post["date"][:19], "timezone": "Europe/Madrid"}}
    info.update(post["extra"])
    print(f"{post['name']}...", end=" ")
    r = call_tool("createScheduledPost", {"blogId": BLOG_ID, "date": post["date"], "info": json.dumps(info, ensure_ascii=False)})
    text = r["content"][0]["text"] if r.get("content") else ""
    try:
        pid = json.loads(text).get("data", {}).get("id", "?")
        print(f"OK id={pid}")
        created.append(pid)
    except Exception:
        print(f"ERR: {text[:60]}")

print(f"\nDP-F0-076 programado: {len(created)}/6")
print("\nHorario completo Jul 19:")
print("  08:00 Threads      — DP-F0-073 Enemies to lovers")
print("  09:30 TikTok       — DP-F0-073")
print("  10:30 Bluesky      — DP-F0-073")
print("  11:00 Instagram    — DP-F0-073")
print("  12:30 Facebook     — DP-F0-073")
print("  15:30 Pinterest    — DP-F0-073")
print("  16:00 Instagram    — DP-F0-076 Capítulos")
print("  17:00 Threads      — DP-F0-076")
print("  17:30 Bluesky      — DP-F0-076")
print("  18:30 TikTok       — DP-F0-076")
print("  20:00 Facebook     — DP-F0-076")
print("  21:00 Pinterest    — DP-F0-076")
