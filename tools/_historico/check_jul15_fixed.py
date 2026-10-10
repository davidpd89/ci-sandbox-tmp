import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

def get_posts(from_date, to_date):
    r = call_tool("getScheduledPosts", {
        "brandId": "6435452",
        "fromDate": from_date,
        "toDate": to_date,
        "timezone": "Europe/Madrid"
    })
    text = r["content"][0]["text"] if r.get("content") else ""
    if not text: return []
    raw = json.loads(text)
    # Respuesta puede ser lista, dict con "posts" o dict con "data"
    if isinstance(raw, list):
        return raw
    return raw.get("data") or raw.get("posts") or []

posts = get_posts("2026-07-15T00:00:00+02:00", "2026-07-15T23:59:00+02:00")
print(f"Posts el 15 jul: {len(posts)}")
kindle_posts = []
other_posts = []
for p in posts:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    media = json.dumps(p.get("media", []))
    is_kindle = "kindle-con-polvo" in media or "Kindle para leer" in p.get("text", "")
    is_draft = p.get("draft", False)
    mark = " [KINDLE]" if is_kindle else (" [DRAFT]" if is_draft else "")
    print(f"  {net:12} {p.get('date','')[:16]} id={p.get('id')}{mark}")
    if is_kindle:
        kindle_posts.append(p)
    else:
        other_posts.append(p)

print(f"\nPosts Kindle (DP-F0-070): {len(kindle_posts)}")
print(f"Otros posts: {len(other_posts)}")

# Verificar test post creado (344482383)
print("\n=== Buscar test post id=344482383 ===")
for p in posts:
    if str(p.get("id")) == "344482383":
        print(f"Encontrado: {p.get('date','')[:16]} net={next((pr.get('network') for pr in p.get('providers',[])),'')} text={p.get('text','')[:50]}")
