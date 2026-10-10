import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from metricool_client import call_tool

# IDs a MANTENER (del primer run con tildes correctas)
KEEP = {344481820, 344481823, 344481827, 344481832, 344482149}
# IDs a BORRAR como draft
DRAFT = [344482161, 344482171, 344482176, 344482179, 344482383]

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

# Primero leer info completa de los posts a draft
posts = get_posts_jul15()
post_map = {p["id"]: p for p in posts}

for pid in DRAFT:
    if pid not in post_map:
        print(f"id={pid}: no encontrado")
        continue
    p = post_map[pid]
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    print(f"Draftificando {net} id={pid}...", end=" ")

    # Preparar info para updateScheduledPost con draft=True
    info = {
        "autoPublish": False,
        "draft": True,
        "text": "[DUPLICADO] " + p.get("text", ""),
        "media": p.get("media", []),
        "providers": p.get("providers", []),
        "publicationDate": p.get("publicationDate", {}),
        "descendants": [],
        "firstCommentText": "",
        "hasNotReadNotes": False,
        "shortener": False,
        "smartLinkData": {"ids": []},
    }
    # Añadir networkData si existe
    for key in ["instagramData", "facebookData", "tiktokData", "threadsData", "blueskyData"]:
        if key in p:
            info[key] = p[key]

    r2 = call_tool("updateScheduledPost", {
        "blogId": "6435452",
        "id": str(pid),
        "uuid": p.get("uuid", ""),
        "info": json.dumps(info, ensure_ascii=False)
    })
    text2 = r2["content"][0]["text"] if r2.get("content") else ""
    err = r2.get("isError")
    if err:
        print(f"ERROR: {text2[:100]}")
    else:
        print("OK (draftificado)")

# Verificación final
print("\n=== Estado final DP-F0-070 el 15 jul ===")
posts2 = get_posts_jul15()
kindle = [p for p in posts2 if "Kindle" in p.get("text", "") or "kindle-con-polvo" in json.dumps(p.get("media", []))]
for p in kindle:
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    draft = p.get("draft")
    text_prev = p.get("text", "")[:40]
    print(f"  {net:12} id={p.get('id')} draft={draft} text={text_prev}")
