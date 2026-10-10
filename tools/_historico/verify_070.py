import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

r = call_tool("getScheduledPosts", {
    "brandId": "6435452",
    "fromDate": "2026-07-15T00:00:00+02:00",
    "toDate": "2026-07-15T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"]
raw = json.loads(text)
posts = raw if isinstance(raw, list) else raw.get("posts", [])
print(f"Posts el 15 jul: {len(posts)}")
for p in posts:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    print(f"  {net:15} {p.get('date','')[:16]} id={p.get('id')} draft={p.get('draft')}")

# Intentar TikTok con videoUrl (diferente approach)
print("\n=== Intentando TikTok ===")
VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-070-kindle-con-polvo/reel.mp4"
info = {
    "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
    "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
    "media": [VIDEO_URL],
    "providers": [{"network": "tiktok"}],
    "text": "Me compré el Kindle para leer más. Eso fue hace nueve meses. Ahí está.\n\n¿Cuál llevas meses prometiéndote leer?\n\n#booktok #booktokespañol #libros #lectores #frasesdelibros #kindle #leoporquequiero #parati",
    "publicationDate": {"dateTime": "2026-07-15T10:00:00", "timezone": "Europe/Madrid"},
    "tiktokData": {"privacy": "PUBLIC_TO_EVERYONE", "disableDuet": False, "disableStitch": False, "disableComments": False}
}
r2 = call_tool("createScheduledPost", {
    "blogId": "6435452",
    "date": "2026-07-15T10:00:00+02:00",
    "info": json.dumps(info, ensure_ascii=False)
})
print(f"isError: {r2.get('isError')}")
text2 = r2["content"][0]["text"] if r2.get("content") else ""
print(f"response: {text2[:300]}")
