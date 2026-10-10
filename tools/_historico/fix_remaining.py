import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

def get_posts_jul15():
    r = call_tool("getScheduledPosts", {
        "brandId": "6435452",
        "fromDate": "2026-07-15T00:00:00+02:00",
        "toDate": "2026-07-15T23:59:00+02:00",
        "timezone": "Europe/Madrid"
    })
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text)
    return raw.get("data") or raw.get("posts") or []

posts = get_posts_jul15()
post_map = {p["id"]: p for p in posts}

DRAFT_IDS = [344482171, 344482176, 344482179]

for pid in DRAFT_IDS:
    if pid not in post_map:
        print(f"id={pid}: no encontrado")
        continue
    p = post_map[pid]
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    print(f"Draftificando {net} id={pid}...", end=" ")

    # Info mínima sin networkData para evitar conflicto cross-network
    info = {
        "autoPublish": False,
        "draft": True,
        "text": "[DUPLICADO] " + p.get("text", "")[:30],
        "media": p.get("media", []),
        "providers": p.get("providers", []),
        "publicationDate": p.get("publicationDate", {}),
        "descendants": [],
        "firstCommentText": "",
        "hasNotReadNotes": False,
        "shortener": False,
        "smartLinkData": {"ids": []},
    }
    # Solo añadir el networkData correcto para este network
    net_key = f"{net}Data"
    if net_key in p:
        info[net_key] = p[net_key]

    r2 = call_tool("updateScheduledPost", {
        "blogId": "6435452",
        "id": str(pid),
        "uuid": p.get("uuid", ""),
        "info": json.dumps(info, ensure_ascii=False)
    })
    text2 = r2["content"][0]["text"] if r2.get("content") else ""
    err = r2.get("isError")
    if err:
        print(f"ERROR: {text2[:150]}")
    else:
        print("OK")

# Estado final
print("\n=== DP-F0-070 Estado Final ===")
posts2 = get_posts_jul15()
kindle = [p for p in posts2 if "Kindle" in p.get("text", "")]
active = [p for p in kindle if not p.get("draft")]
drafts = [p for p in kindle if p.get("draft")]
print(f"Posts activos: {len(active)}")
for p in active:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    print(f"  {net:12} {p.get('date','')[:16]} id={p.get('id')} ✓")
print(f"Drafts (inactivos): {len(drafts)}")
for p in drafts:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    print(f"  {net:12} id={p.get('id')} [DRAFT]")
