import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

BLOG_ID = "6435452"

# Posts activos DP-F0-070 en Jul 15 → mover al 17 con horas bien espaciadas
# Jul 17 existentes: 10:15, 11:00, 12:30, 16:30, 18:45, 21:15
# Nuevas horas elegidas para no coincidir y estar bien repartidas:
MOVES = [
    {"id": 344482149, "net": "tiktok",     "new_date": "2026-07-17T09:00:00+02:00"},
    {"id": 344481820, "net": "instagram",  "new_date": "2026-07-17T13:30:00+02:00"},
    {"id": 344481823, "net": "facebook",   "new_date": "2026-07-17T17:00:00+02:00"},
    {"id": 344481827, "net": "threads",    "new_date": "2026-07-17T19:30:00+02:00"},
    {"id": 344481832, "net": "bluesky",    "new_date": "2026-07-17T22:00:00+02:00"},
]

# Leer posts actuales para extraer la info completa
r = call_tool("getScheduledPosts", {
    "brandId": BLOG_ID,
    "fromDate": "2026-07-15T00:00:00+02:00",
    "toDate": "2026-07-15T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"]
raw = json.loads(text)
posts = raw.get("data") or raw.get("posts") or []
post_map = {p["id"]: p for p in posts}

new_ids = []
for move in MOVES:
    pid = move["id"]
    net = move["net"]
    new_date = move["new_date"]
    new_dt = new_date[:19].replace("+", "")  # strip tz for publicationDate

    if pid not in post_map:
        print(f"id={pid} ({net}): no encontrado en Jul 15")
        continue

    p = post_map[pid]
    print(f"Moviendo {net} id={pid} → {new_date[:16]}...", end=" ")

    # Construir info preservando todo excepto la fecha
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
    # Añadir networkData específico del network
    net_key_map = {
        "tiktok": "tiktokData",
        "instagram": "instagramData",
        "facebook": "facebookData",
        "threads": "threadsData",
        "bluesky": "blueskyData",
        "pinterest": "pinterestData",
    }
    net_key = net_key_map.get(net)
    if net_key and net_key in p:
        info[net_key] = p[net_key]

    r2 = call_tool("updateScheduledPost", {
        "blogId": BLOG_ID,
        "id": str(pid),
        "uuid": p.get("uuid", ""),
        "info": json.dumps(info, ensure_ascii=False)
    })
    text2 = r2["content"][0]["text"] if r2.get("content") else ""
    err = r2.get("isError")
    if err:
        print(f"ERROR: {text2[:120]}")
    else:
        try:
            resp = json.loads(text2)
            new_pid = (resp.get("data", {}).get("id") or resp.get("id") or "?")
            print(f"OK → nuevo id={new_pid}")
            new_ids.append({"net": net, "id": new_pid, "hora": new_date[11:16]})
        except Exception:
            print(f"OK (parse err) raw={text2[:80]}")

# Verificar
print("\n=== DP-F0-070 en Jul 17 ===")
r3 = call_tool("getScheduledPosts", {
    "brandId": BLOG_ID,
    "fromDate": "2026-07-17T00:00:00+02:00",
    "toDate": "2026-07-17T23:59:00+02:00",
    "timezone": "Europe/Madrid"
})
text3 = r3["content"][0]["text"]
raw3 = json.loads(text3)
posts3 = raw3.get("data") or raw3.get("posts") or []
active3 = [p for p in posts3 if not p.get("draft")]
print(f"Total posts activos el 17 jul: {len(active3)}")
for p in sorted(active3, key=lambda x: x.get("date", "")):
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    kindle = " [KINDLE]" if "Kindle" in p.get("text", "") else ""
    print(f"  {net:12} {p.get('date','')[:16]} id={p.get('id')}{kindle}")
