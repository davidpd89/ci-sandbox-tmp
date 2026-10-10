"""Programa DP-F0-071 en Metricool para el 18 de julio 2026."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-071-resaca-libro/reel.mp4"

# Jul 18 — horarios bien repartidos sin solapamiento entre redes
POSTS = [
    {
        "name": "TikTok 08:30",
        "date": "2026-07-18T08:30:00+02:00",
        "providers": [{"network": "tiktok"}],
        "text": "Terminé el libro. El libro no terminó conmigo.\n\n¿Qué libro te dejó así? Te leo en comentarios 👇\n\n#booktok #resacaliteraria #bookworm #humorlector #librosenespañol #bookreels #leoporquequiero #parati",
        "extra": {"tiktokData": {"title": "Terminé el libro. El libro no terminó conmigo.", "privacy": "PUBLIC_TO_EVERYONE", "disableDuet": False, "disableStitch": False, "disableComments": False}},
    },
    {
        "name": "Instagram 10:00",
        "date": "2026-07-18T10:00:00+02:00",
        "providers": [{"network": "instagram"}],
        "text": "Terminé el libro. El libro no terminó conmigo.\n\n¿Qué libro te dejó de luto? Te leo en comentarios 👇\n\n#booktok #resacaliteraria #bookish #bookworm #librosenespañol #frasesdelibros #happyreader #bookreels",
        "extra": {"instagramData": {"type": "REEL", "showReelOnFeed": True}},
    },
    {
        "name": "Facebook 12:00",
        "date": "2026-07-18T12:00:00+02:00",
        "providers": [{"network": "facebook"}],
        "text": "Hay libros que cierras pero que no terminan contigo.\n\n¿Cuál fue el tuyo?\n\nhttps://davidportodiaz.com",
        "extra": {"facebookData": {"type": "REEL"}},
    },
    {
        "name": "Threads 09:00",
        "date": "2026-07-18T09:00:00+02:00",
        "providers": [{"network": "threads"}],
        "text": "Terminé el libro. Volví a mi vida normal. Mentira.\n\n¿Qué libro te dejó así? #Lectura",
        "extra": {"threadsData": {}},
    },
    {
        "name": "Bluesky 21:30",
        "date": "2026-07-18T21:30:00+02:00",
        "providers": [{"network": "bluesky"}],
        "text": "Terminé el libro. El libro no terminó conmigo. Lo cerré. Lo puse en la mesita. Seguí con mi vida. Mentira. ¿Qué libro te dejó así?",
        "extra": {"blueskyData": {}},
    },
    {
        "name": "Pinterest 15:00",
        "date": "2026-07-18T15:00:00+02:00",
        "providers": [{"network": "pinterest"}],
        "text": "La resaca lectora: ese momento en que cierras el libro pero sigues dentro de él. Una pieza para lectores que se quedan de luto cuando acaban una buena historia.",
        "extra": {"pinterestData": {"boardId": "1081178560003791073", "title": "Cuando terminas el libro pero el libro no te termina a ti", "link": "https://davidportodiaz.com"}},
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
        continue
    try:
        raw = json.loads(text)
        pid = raw.get("data", {}).get("id") or raw.get("id", "?")
        print(f"OK id={pid}")
        created.append({"net": post["name"], "id": pid})
    except Exception as e:
        print(f"OK (parse: {e})")

print(f"\nCreados: {len(created)}/6")

# Verificar
r = call_tool("getScheduledPosts", {
    "brandId": BLOG_ID,
    "fromDate": "2026-07-18T00:00:00+02:00",
    "toDate": "2026-07-18T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"]
raw = json.loads(text)
posts = raw.get("data") or raw.get("posts") or []
resaca = [p for p in posts if not p.get("draft") and "resaca" in json.dumps(p.get("media", [])).lower() or "Terminé" in p.get("text", "")]
print(f"Posts DP-F0-071 activos Jul 18: {len(resaca)}")
for p in sorted(resaca, key=lambda x: x.get("date","")):
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    print(f"  {net:12} {p.get('date','')[11:16]} id={p.get('id')}")
