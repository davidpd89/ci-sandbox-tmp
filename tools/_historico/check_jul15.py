import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

# Buscar en un rango amplio
r = call_tool("getScheduledPosts", {
    "brandId": "6435452",
    "fromDate": "2026-07-14T22:00:00+02:00",
    "toDate": "2026-07-16T02:00:00+02:00",
    "timezone": "Europe/Madrid"
})
text = r["content"][0]["text"]
raw = json.loads(text)
posts = raw if isinstance(raw, list) else raw.get("posts", [])
print(f"Posts 14-16 jul: {len(posts)}")
kindle_posts = []
for p in posts:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    media = json.dumps(p.get("media", []))
    is_kindle = "kindle-con-polvo" in media or "9490058692061156992" in media
    if is_kindle:
        kindle_posts.append(p)
    marker = " <<< KINDLE" if is_kindle else ""
    print(f"  {net:15} {p.get('date','')[:16]} id={p.get('id')} draft={p.get('draft')}{marker}")

print(f"\nPosts de Kindle encontrados: {len(kindle_posts)}")
