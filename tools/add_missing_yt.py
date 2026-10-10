"""Añade los 2 YouTube Shorts de Jul 26 y 28 que fallaron antes."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
BASE = "https://davidpd89.github.io/rrss-davidporto-media/videos"

SHORTS = [
    ("2026-07-26T12:00:00+02:00", f"{BASE}/DP-F0-077-libro-ya-vivio/reel.mp4",
     "Este libro ya vivió — libros de segunda mano con historia",
     "Este libro ya vivió en otras manos. ¿Abrirías la nota? #librosusados #instalibros"),
    ("2026-07-28T18:00:00+02:00", f"{BASE}/DP-F0-081-misma-escena/reel.mp4",
     "La leí veinte veces — la misma escena favorita",
     "La leí veinte veces. La misma escena. ¿Cuál es la tuya? #lectoresreales #librosqueamo"),
]

for date, url, title, desc in SHORTS:
    info = {
        "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
        "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
        "providers": [{"network": "youtube"}],
        "text": desc, "media": [url],
        "publicationDate": {"dateTime": date[:19], "timezone": "Europe/Madrid"},
        "youtubeData": {"title": title, "audience": "NOT_MADE_FOR_KIDS", "type": "SHORT"}
    }
    r = call_tool("createScheduledPost", {"blogId": BLOG_ID, "date": date, "info": json.dumps(info, ensure_ascii=False)})
    text = r["content"][0]["text"] if r.get("content") else ""
    if r.get("isError"):
        print(f"ERR {date[5:10]}: {text[:80]}")
    else:
        try: print(f"OK {date[5:10]}: id={json.loads(text).get('data',{}).get('id','?')} | {title[:50]}")
        except: print(f"OK {date[5:10]}")
