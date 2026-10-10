"""
Mueve DP-F0-076 (capitulos que no terminas) del 19 al 20 de julio
y lo que hubiera en el 20 lo pone en el 19.
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"

def get_posts(from_d, to_d):
    r = call_tool("getScheduledPosts", {"brandId": BLOG_ID, "fromDate": from_d, "toDate": to_d, "timezone": "Europe/Madrid"})
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text) if text else {}
    posts = raw.get("data") or raw.get("posts") or []
    return [p for p in posts if not p.get("draft")]

# Leer todo el 19 y el 20
posts_19 = get_posts("2026-07-19T00:00:00+02:00", "2026-07-19T23:59:00+02:00")
posts_20 = get_posts("2026-07-20T00:00:00+02:00", "2026-07-20T23:59:00+02:00")

print(f"Jul 19: {len(posts_19)} posts activos")
for p in sorted(posts_19, key=lambda x: x.get("date","")):
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    cap = "CAPÍTULOS" if "capítulos" in p.get("text","").lower() or "capitulos" in p.get("text","").lower() else "enemies"
    print(f"  {net:12} {p.get('date','')[11:16]} id={p.get('id')} [{cap}]")

print(f"\nJul 20: {len(posts_20)} posts activos")
for p in sorted(posts_20, key=lambda x: x.get("date","")):
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    print(f"  {net:12} {p.get('date','')[11:16]} id={p.get('id')}")

# Los IDs de DP-F0-076 (capítulos) que mover del 19 al 20
dp076_ids = {344580398, 344580403, 344580408, 344580411, 344580414, 344580418}
dp076_posts = [p for p in posts_19 if p.get("id") in dp076_ids]

print(f"\nMoviendo {len(dp076_posts)} posts de DP-F0-076 del 19 al 20...")

def update_date(post, new_date_base):
    """Actualiza un post cambiando solo la fecha, manteniendo la hora."""
    old_date = post.get("date", "")
    old_time = old_date[11:19] if len(old_date) >= 19 else "12:00:00"
    new_date_full = f"{new_date_base}T{old_time}+02:00"

    info = {
        "autoPublish": True, "draft": False,
        "text": post.get("text", ""),
        "media": post.get("media", []),
        "providers": post.get("providers", []),
        "publicationDate": {"dateTime": f"{new_date_base}T{old_time}", "timezone": "Europe/Madrid"},
        "descendants": [], "firstCommentText": "", "hasNotReadNotes": False,
        "shortener": False, "smartLinkData": {"ids": []},
    }
    # Añadir networkData
    for key in ["instagramData", "facebookData", "tiktokData", "threadsData", "blueskyData", "pinterestData"]:
        if key in post:
            info[key] = post[key]

    r = call_tool("updateScheduledPost", {
        "blogId": BLOG_ID, "id": str(post["id"]),
        "uuid": post.get("uuid", ""),
        "info": json.dumps(info, ensure_ascii=False)
    })
    text = r["content"][0]["text"] if r.get("content") else ""
    if r.get("isError"): return False, text[:80]
    try:
        new_id = json.loads(text).get("data", {}).get("id", "?")
        return True, new_id
    except Exception:
        return True, "?"

# Mover DP-F0-076 del 19 → 20
moved_076 = []
for p in dp076_posts:
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    ok, new_id = update_date(p, "2026-07-20")
    print(f"  {net:12} 19→20: {'OK' if ok else 'ERR'} (nuevo id={new_id})")
    if ok: moved_076.append(new_id)

# Si hay posts en el 20, moverlos al 19
if posts_20:
    print(f"\nMoviendo {len(posts_20)} posts existentes del 20 → 19...")
    for p in posts_20:
        net = next((pr.get("network") for pr in p.get("providers",[])), "?")
        ok, new_id = update_date(p, "2026-07-19")
        print(f"  {net:12} 20→19: {'OK' if ok else 'ERR'} (nuevo id={new_id})")
else:
    print("\nJul 20 estaba vacío — nada que mover al 19.")

# Verificar resultado
print("\n=== Verificación final ===")
for day, fd, td in [("Jul 19", "2026-07-19T00:00:00+02:00", "2026-07-19T23:59:00+02:00"),
                    ("Jul 20", "2026-07-20T00:00:00+02:00", "2026-07-20T23:59:00+02:00")]:
    ps = get_posts(fd, td)
    print(f"\n{day}: {len(ps)} posts")
    for p in sorted(ps, key=lambda x: x.get("date","")):
        net = next((pr.get("network") for pr in p.get("providers",[])), "?")
        txt = p.get("text","")[:30]
        print(f"  {net:12} {p.get('date','')[11:16]} {txt}")
