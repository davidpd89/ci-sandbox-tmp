import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
VIDEO_URL = "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-071-resaca-libro/reel.mp4"

# Verificar si Facebook ya existe
r = call_tool("getScheduledPosts", {
    "brandId": BLOG_ID,
    "fromDate": "2026-07-18T11:00:00+02:00",
    "toDate": "2026-07-18T13:00:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"]
raw = json.loads(text)
posts = raw.get("data") or []
fb_posts = [p for p in posts if any(pr.get("network") == "facebook" for pr in p.get("providers", []))]
print(f"Facebook posts 11-13h Jul 18: {len(fb_posts)}")
for p in fb_posts:
    print(f"  id={p.get('id')} draft={p.get('draft')} text={p.get('text','')[:40]}")

# Crear Pinterest con el formato correcto
print("\nCreando Pinterest...")
info_pi = {
    "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
    "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
    "media": [VIDEO_URL],
    "providers": [{"network": "pinterest"}],
    "text": "La resaca lectora: ese momento en que cierras el libro pero sigues dentro de él.",
    "publicationDate": {"dateTime": "2026-07-18T15:00:00", "timezone": "Europe/Madrid"},
    "pinterestData": {
        "boardId": "1081178560003791073",
        "pinTitle": "Cuando terminas el libro pero el libro no te termina a ti",
        "pinLink": "https://davidportodiaz.com"
    }
}
r2 = call_tool("createScheduledPost", {
    "blogId": BLOG_ID,
    "date": "2026-07-18T15:00:00+02:00",
    "info": json.dumps(info_pi, ensure_ascii=False)
})
text2 = r2["content"][0]["text"] if r2.get("content") else ""
if r2.get("isError") or (text2 and "error" in text2.lower()):
    print(f"Pinterest ERROR: {text2[:150]}")
else:
    try:
        pid = json.loads(text2).get("data", {}).get("id", "?")
        print(f"Pinterest OK id={pid}")
    except Exception:
        print(f"Pinterest OK: {text2[:80]}")
