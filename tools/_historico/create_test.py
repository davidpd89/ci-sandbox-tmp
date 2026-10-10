import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-070-kindle-con-polvo/reel.mp4"
info = {
    "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
    "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
    "media": [VIDEO_URL],
    "providers": [{"network": "instagram"}],
    "text": "Me compre el Kindle para leer mas. Que llevas meses prometiendote leer? #booktok #lectores",
    "publicationDate": {"dateTime": "2026-07-15T11:00:00", "timezone": "Europe/Madrid"},
    "instagramData": {"type": "REEL", "showReelOnFeed": True}
}
r = call_tool("createScheduledPost", {
    "blogId": "6435452",
    "date": "2026-07-15T11:00:00+02:00",
    "info": json.dumps(info, ensure_ascii=False)
})
print("isError:", r.get("isError"))
print("content len:", len(r.get("content", [])))
if r.get("content"):
    text = r["content"][0]["text"]
    print(f"text ({len(text)} chars): {text[:800]}")
