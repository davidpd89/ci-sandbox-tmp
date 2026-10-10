"""Programa DP-F0-070 (Kindle con polvo) en todas las redes para el 15 jul 2026."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

BRAND_ID = "6435452"
VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-070-kindle-con-polvo/reel.mp4"

# Copys
CAPTION_IG = (
    "Me compré el Kindle para leer más. Eso fue hace nueve meses. "
    "Ahí está.\n\n"
    "¿Qué llevas meses prometiéndote leer? Te leo en comentarios 👇\n\n"
    "#booktok #bookstagram #librosenespañol #lectores #frasesdelibros #booktokespañol #kindle #lectoresreales #bloqueoloctor"
)
CAPTION_FB = (
    "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está.\n\n"
    "¿Qué llevas meses prometiéndote leer?\n\n"
    "https://davidportodiaz.com"
)
CAPTION_TT = (
    "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está.\n\n"
    "¿Cuál llevas meses prometiéndote leer?\n\n"
    "#booktok #booktokespañol #libros #lectores #frasesdelibros #kindle #leoporquequiero #parati"
)
CAPTION_TH = (
    "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está.\n\n"
    "¿Qué llevas meses prometiéndote leer? #Lectura"
)
CAPTION_BS = (
    "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está. "
    "¿Qué llevas meses prometiéndote leer?"
)
CAPTION_PI_TITLE = "Me compré el Kindle para leer más"
CAPTION_PI_DESC = (
    "Un reel para lectores que se prometieron leer más y siguen sin abrir el Kindle. "
    "¿Te identificas? Frases reales de lectores de habla hispana."
)

# Posts a crear
POSTS = [
    {
        "name": "TikTok",
        "date": "2026-07-15T10:00:00+02:00",
        "info": {
            "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
            "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
            "media": [VIDEO_URL],
            "providers": [{"network": "tiktok"}],
            "text": CAPTION_TT,
            "publicationDate": {"dateTime": "2026-07-15T10:00:00", "timezone": "Europe/Madrid"},
            "tiktokData": {"privacy": "PUBLIC_TO_EVERYONE", "disableDuet": False, "disableStitch": False, "disableComments": False}
        }
    },
    {
        "name": "Instagram Reel",
        "date": "2026-07-15T11:00:00+02:00",
        "info": {
            "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
            "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
            "media": [VIDEO_URL],
            "providers": [{"network": "instagram"}],
            "text": CAPTION_IG,
            "publicationDate": {"dateTime": "2026-07-15T11:00:00", "timezone": "Europe/Madrid"},
            "instagramData": {"type": "REEL", "showReelOnFeed": True}
        }
    },
    {
        "name": "Facebook Reel",
        "date": "2026-07-15T12:30:00+02:00",
        "info": {
            "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
            "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
            "media": [VIDEO_URL],
            "providers": [{"network": "facebook"}],
            "text": CAPTION_FB,
            "publicationDate": {"dateTime": "2026-07-15T12:30:00", "timezone": "Europe/Madrid"},
            "facebookData": {"type": "REEL"}
        }
    },
    {
        "name": "Threads",
        "date": "2026-07-15T19:00:00+02:00",
        "info": {
            "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
            "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
            "media": [VIDEO_URL],
            "providers": [{"network": "threads"}],
            "text": CAPTION_TH,
            "publicationDate": {"dateTime": "2026-07-15T19:00:00", "timezone": "Europe/Madrid"},
            "threadsData": {}
        }
    },
    {
        "name": "Bluesky",
        "date": "2026-07-15T21:15:00+02:00",
        "info": {
            "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
            "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
            "media": [VIDEO_URL],
            "providers": [{"network": "bluesky"}],
            "text": CAPTION_BS,
            "publicationDate": {"dateTime": "2026-07-15T21:15:00", "timezone": "Europe/Madrid"},
            "blueskyData": {}
        }
    },
]

created = []
for post in POSTS:
    print(f"\nCreando: {post['name']} @ {post['date'][:16]}...", end=" ")
    r = call_tool("createScheduledPost", {
        "blogId": BRAND_ID,
        "date": post["date"],
        "info": json.dumps(post["info"], ensure_ascii=False)
    })
    text = r["content"][0]["text"] if r.get("content") else ""
    if not text or r.get("isError"):
        print(f"EMPTY/ERROR — comprobando si se creó...")
    else:
        try:
            raw = json.loads(text)
            if isinstance(raw, dict) and raw.get("isError"):
                print(f"ERROR: {raw}")
            else:
                pid = raw.get("id") or raw.get("post", {}).get("id", "?")
                print(f"OK id={pid}")
                created.append({"red": post["name"], "id": pid, "fecha": post["date"][:16]})
        except Exception as e:
            print(f"Parse error: {e} | text[:100]={text[:100]}")

print("\n=== POSTS CREADOS ===")
for c in created:
    print(f"  {c['red']:20} {c['fecha']} id={c['id']}")

# Verificar
print("\nVerificando...")
r = call_tool("getScheduledPosts", {
    "brandId": BRAND_ID,
    "fromDate": "2026-07-15T00:00:00+02:00",
    "toDate": "2026-07-15T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
raw = json.loads(r["content"][0]["text"])
posts = raw if isinstance(raw, list) else raw.get("posts", [])
for p in posts:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    draft = p.get("draft", False)
    print(f"  {net:15} {p.get('date','')[:16]} id={p.get('id')} draft={draft}")
