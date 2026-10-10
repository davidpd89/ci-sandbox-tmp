"""Corrige el spacing del 17 jul: Instagram muy cerca (2h30) y Bluesky (45min)."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

BLOG_ID = "6435452"

# Correcciones necesarias:
# Instagram 344488178: de 13:30 → 15:30 (4h30 tras DP-F0-069 IG a las 11:00)
# Bluesky 344488187: de 22:00 → 08:00 (13h antes de DP-F0-069 BS a las 21:15)
FIXES = [
    {"id": 344488178, "net": "instagram", "new_date": "2026-07-17T15:30:00+02:00"},
    {"id": 344488187, "net": "bluesky",   "new_date": "2026-07-17T08:00:00+02:00"},
]

# Leer posts actuales del 17
r = call_tool("getScheduledPosts", {
    "brandId": BLOG_ID,
    "fromDate": "2026-07-17T00:00:00+02:00",
    "toDate": "2026-07-17T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"]
raw = json.loads(text)
posts = raw.get("data") or raw.get("posts") or []
post_map = {p["id"]: p for p in posts}

for fix in FIXES:
    pid = fix["id"]
    net = fix["net"]
    new_date = fix["new_date"]

    if pid not in post_map:
        print(f"id={pid}: no encontrado")
        continue

    p = post_map[pid]
    print(f"Ajustando {net} id={pid} → {new_date[11:16]}...", end=" ")

    info = {
        "autoPublish": True,
        "draft": False,
        "text": p.get("text", ""),
        "media": p.get("media", []),
        "providers": p.get("providers", []),
        "publicationDate": {"dateTime": new_date[:19], "timezone": "Europe/Madrid"},
        "descendants": [],
        "firstCommentText": p.get("firstCommentText", ""),
        "hasNotReadNotes": False,
        "shortener": False,
        "smartLinkData": {"ids": []},
    }
    net_key_map = {"instagram": "instagramData", "facebook": "facebookData",
                   "tiktok": "tiktokData", "threads": "threadsData", "bluesky": "blueskyData"}
    nk = net_key_map.get(net)
    if nk and nk in p:
        info[nk] = p[nk]

    r2 = call_tool("updateScheduledPost", {
        "blogId": BLOG_ID, "id": str(pid), "uuid": p.get("uuid", ""),
        "info": json.dumps(info, ensure_ascii=False)
    })
    err = r2.get("isError")
    text2 = r2["content"][0]["text"] if r2.get("content") else ""
    print("ERROR: " + text2[:80] if err else "OK")

# Verificación final con horario completo
print("\n=== Horario completo Jul 17 ===")
r3 = call_tool("getScheduledPosts", {
    "brandId": BLOG_ID,
    "fromDate": "2026-07-17T00:00:00+02:00",
    "toDate": "2026-07-17T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text3 = r3["content"][0]["text"]
raw3 = json.loads(text3)
posts3 = raw3.get("data") or raw3.get("posts") or []
active3 = sorted([p for p in posts3 if not p.get("draft")], key=lambda x: x.get("date",""))
for p in active3:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    tag = " ← KINDLE" if "Kindle" in p.get("text", "") else ""
    print(f"  {p.get('date','')[11:16]}  {net:12}{tag}")
