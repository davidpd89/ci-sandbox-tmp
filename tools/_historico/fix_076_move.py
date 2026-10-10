"""Mueve los 5 posts restantes de DP-F0-076 del 19 al 20, sin cross-networkData."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
NET_KEY = {"instagram": "instagramData", "facebook": "facebookData", "tiktok": "tiktokData",
           "threads": "threadsData", "bluesky": "blueskyData", "pinterest": "pinterestData"}

def get_posts(from_d, to_d):
    r = call_tool("getScheduledPosts", {"brandId": BLOG_ID, "fromDate": from_d, "toDate": to_d, "timezone": "Europe/Madrid"})
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text) if text else {}
    posts = raw.get("data") or raw.get("posts") or []
    return [p for p in posts if not p.get("draft")]

posts_19 = get_posts("2026-07-19T00:00:00+02:00", "2026-07-19T23:59:00+02:00")
dp076_remaining = [p for p in posts_19 if "capítulos" in p.get("text","").lower() or "capitulos" in p.get("text","").lower()]
print(f"Posts DP-F0-076 aún en Jul 19: {len(dp076_remaining)}")

for p in dp076_remaining:
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    old_time = p.get("date","")[11:19] or "12:00:00"
    new_dt = f"2026-07-20T{old_time}"
    print(f"  {net:12} → Jul 20 {old_time[:5]}...", end=" ")

    # Construir info SOLO con la networkData correcta para este network
    info = {
        "autoPublish": True, "draft": False,
        "text": p.get("text", ""),
        "media": p.get("media", []),
        "providers": p.get("providers", []),
        "publicationDate": {"dateTime": new_dt, "timezone": "Europe/Madrid"},
        "descendants": [], "firstCommentText": "", "hasNotReadNotes": False,
        "shortener": False, "smartLinkData": {"ids": []},
    }
    # Solo la networkData del network correcto
    correct_key = NET_KEY.get(net)
    if correct_key and correct_key in p:
        info[correct_key] = p[correct_key]

    r = call_tool("updateScheduledPost", {
        "blogId": BLOG_ID, "id": str(p["id"]),
        "uuid": p.get("uuid", ""),
        "info": json.dumps(info, ensure_ascii=False)
    })
    text = r["content"][0]["text"] if r.get("content") else ""
    if r.get("isError"): print(f"ERR: {text[:80]}")
    else:
        try: print(f"OK id={json.loads(text).get('data',{}).get('id','?')}")
        except: print("OK")

print("\n=== Jul 19 ===")
for p in sorted(get_posts("2026-07-19T00:00:00+02:00","2026-07-19T23:59:00+02:00"), key=lambda x: x.get("date","")):
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    print(f"  {net:12} {p.get('date','')[11:16]} {p.get('text','')[:30]}")
print("\n=== Jul 20 ===")
for p in sorted(get_posts("2026-07-20T00:00:00+02:00","2026-07-20T23:59:00+02:00"), key=lambda x: x.get("date","")):
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    print(f"  {net:12} {p.get('date','')[11:16]} {p.get('text','')[:30]}")
