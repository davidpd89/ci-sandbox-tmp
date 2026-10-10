import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

BRAND_ID = "6435452"
VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-070-kindle-con-polvo/reel.mp4"

# Primero verificar si los posts ya existen
print("=== Verificando posts ya creados el 15 jul ===")
r = call_tool("getScheduledPosts", {
    "brandId": BRAND_ID,
    "fromDate": "2026-07-15T00:00:00+02:00",
    "toDate": "2026-07-15T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"] if r.get("content") else ""
print(f"Response len: {len(text)}")
if text:
    raw = json.loads(text)
    posts = raw if isinstance(raw, list) else raw.get("posts", [])
    print(f"Posts el 15 jul: {len(posts)}")
    for p in posts:
        net = next((pr.get("network") for pr in p.get("providers", [])), "?")
        print(f"  {net:15} {p.get('date','')[:16]} id={p.get('id')} draft={p.get('draft')}")

# Intentar crear solo el de Instagram con debug completo
print("\n=== Creando Instagram ===")
info = {
    "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
    "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
    "media": [VIDEO_URL],
    "providers": [{"network": "instagram"}],
    "text": "Me compré el Kindle para leer más. ¿Qué llevas meses prometiéndote leer? 👇 #booktok #bookstagram #librosenespañol #lectores",
    "publicationDate": {"dateTime": "2026-07-15T11:00:00", "timezone": "Europe/Madrid"},
    "instagramData": {"type": "REEL", "showReelOnFeed": True}
}

r2 = call_tool("createScheduledPost", {
    "brandId": BRAND_ID,
    "date": "2026-07-15T11:00:00+02:00",
    "info": json.dumps(info, ensure_ascii=False)
})
print(f"isError: {r2.get('isError')}")
print(f"content: {r2.get('content', [])}")
if r2.get("content"):
    print(f"text: {r2['content'][0]['text'][:500]}")
