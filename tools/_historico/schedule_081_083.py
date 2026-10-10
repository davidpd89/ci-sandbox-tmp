"""Programa DP-F0-081, 082, 083 como segundas piezas del 20, 21, 22 julio."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"

PIECES = [
    {
        "id": "DP-F0-081", "day": "2026-07-20",
        "url": "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-081-misma-escena/reel.mp4",
        # Jul 20 pieza 1 (capítulos) usa: 16:00 IG, 17:00 TH, 17:30 BS, 18:30 TT, 20:00 FB, 21:00 PI
        # Pieza 2: 4+ horas de separación
        "posts": [
            {"net":"threads",   "time":"08:30", "text":"La leí veinte veces. La misma escena. No me cansa. ¿Cuál es la tuya? #Lectura"},
            {"net":"bluesky",   "time":"09:00", "text":"La leí veinte veces. La misma escena. ¿Cuál es la tuya?"},
            {"net":"tiktok",    "time":"10:00", "title":"La leí veinte veces. La misma escena.", "text":"La leí veinte veces. La misma escena.\n\nNo me cansa. ¿Cuál es la tuya?\n\n#librosquereleo #lectoresreales #librosqueamo #cosasdelectores #comunidadlectora #instalibros #booktok #parati"},
            {"net":"instagram", "time":"11:30", "text":"La leí veinte veces. La misma escena.\n\n¿Cuál es la tuya? Dímela en comentarios 👇\n\n#librosquereleo #lectoresreales #librosqueamo #cosasdelectores #comunidadlectora #instalibros #librosenespañol #booktok"},
            {"net":"facebook",  "time":"13:00", "text":"Hay escenas que no cansas de releer. La misma página, la misma emoción, siempre.\n\n¿Cuál es la tuya?\n\nhttps://davidportodiaz.com"},
            {"net":"pinterest", "time":"15:00", "text":"Para lectores que vuelven siempre a la misma escena.", "pin_title":"La leí veinte veces. La misma escena.", "pin_link":"https://davidportodiaz.com"},
        ]
    },
    {
        "id": "DP-F0-082", "day": "2026-07-21",
        "url": "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-082-libro-que-no-enseno/reel.mp4",
        # Jul 21 pieza 1 (libro ya vivió) usa: 08:30 TH, 09:00 BS, 10:00 TT, 11:30 IG, 13:00 FB, 16:00 PI
        "posts": [
            {"net":"threads",   "time":"17:00", "text":"Hay libros que no enseño. No los presto. Los guardo. ¿Tienes uno así? #Lectura"},
            {"net":"bluesky",   "time":"17:30", "text":"Hay libros que no enseño. No los presto. Los guardo. ¿Tienes uno así?"},
            {"net":"tiktok",    "time":"18:30", "title":"Hay libros que no enseño.", "text":"Hay libros que no enseño. No los presto. Los guardo.\n\n¿Tienes uno así?\n\n#librosqueguardo #lectoresreales #cosasdelectores #libroslibroslibros #bookstagrammer #librosqueamo #instalibros #parati"},
            {"net":"instagram", "time":"16:30", "text":"Hay libros que no enseño.\n\n¿Tienes uno así? Cuéntame en comentarios 👇\n\n#librosqueguardo #lectoresreales #cosasdelectores #libroslibroslibros #bookstagrammer #librosqueamo #instalibros #booktok"},
            {"net":"facebook",  "time":"19:00", "text":"Hay libros que guardas solo para ti. No los prestas, no los recomiendas en voz alta.\n\n¿Tienes uno así?\n\nhttps://davidportodiaz.com"},
            {"net":"pinterest", "time":"21:00", "text":"Para lectores con libros que no prestan a nadie.", "pin_title":"Hay libros que no enseño.", "pin_link":"https://davidportodiaz.com"},
        ]
    },
    {
        "id": "DP-F0-083", "day": "2026-07-22",
        "url": "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-083-secundario-roba-novela/reel.mp4",
        # Jul 22 pieza 1 (olvidé el final) usa: 08:30 TH, 09:30 BS, 10:00 TT, 11:00 IG, 12:30 FB, 16:30 PI
        "posts": [
            {"net":"threads",   "time":"14:00", "text":"El protagonista, bien. El secundario, todo. Solo yo. ¿A quién defiendes tú? #Lectura"},
            {"net":"bluesky",   "time":"17:00", "text":"El protagonista, bien. El secundario, todo. ¿A quién defiendes tú?"},
            {"net":"tiktok",    "time":"18:00", "title":"El protagonista, bien. El secundario, todo.", "text":"El protagonista, bien. El secundario, todo.\n\n¿A quién defiendes tú?\n\n#personajessecundarios #bookstagrammer #comunidadlectora #lectoresunidos #librosqueamo #booktok #librosenespañol #parati"},
            {"net":"instagram", "time":"16:00", "text":"El protagonista, bien. El secundario, todo.\n\n¿A quién defiendes tú? Dime en comentarios 👇\n\n#personajessecundarios #bookstagrammer #comunidadlectora #lectoresunidos #librosqueamo #booktok #librosenespañol #cosasdelectores"},
            {"net":"facebook",  "time":"19:30", "text":"El protagonista cumple. El secundario te roba el corazón sin avisar.\n\n¿A quién defiendes tú?\n\nhttps://davidportodiaz.com"},
            {"net":"pinterest", "time":"21:00", "text":"Para lectores que saben que el secundario siempre lo hace mejor.", "pin_title":"El protagonista, bien. El secundario, todo.", "pin_link":"https://davidportodiaz.com"},
        ]
    },
]

NET_KEY = {"instagram":"instagramData","facebook":"facebookData","tiktok":"tiktokData",
           "threads":"threadsData","bluesky":"blueskyData","pinterest":"pinterestData"}

total = 0
for piece in PIECES:
    print(f"\n{piece['id']} — {piece['day']}")
    for post in piece["posts"]:
        net = post["net"]
        date_str = f"{piece['day']}T{post['time']}:00+02:00"
        info = {
            "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
            "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
            "media": [piece["url"]], "providers": [{"network": net}], "text": post["text"],
            "publicationDate": {"dateTime": f"{piece['day']}T{post['time']}:00", "timezone": "Europe/Madrid"},
        }
        if net == "instagram": info["instagramData"] = {"type": "REEL", "showReelOnFeed": True}
        elif net == "facebook": info["facebookData"] = {"type": "REEL"}
        elif net == "tiktok": info["tiktokData"] = {"title": post.get("title", post["text"][:50]), "privacy": "PUBLIC_TO_EVERYONE", "disableDuet": False, "disableStitch": False, "disableComments": False}
        elif net == "threads": info["threadsData"] = {}
        elif net == "bluesky": info["blueskyData"] = {}
        elif net == "pinterest": info["pinterestData"] = {"boardId": "1081178560003791073", "pinTitle": post.get("pin_title", post["text"][:50]), "pinLink": post.get("pin_link", "https://davidportodiaz.com")}

        print(f"  {net:12} {post['time']}...", end=" ")
        r = call_tool("createScheduledPost", {"blogId": BLOG_ID, "date": date_str, "info": json.dumps(info, ensure_ascii=False)})
        text = r["content"][0]["text"] if r.get("content") else ""
        if not text or r.get("isError"): print(f"ERR: {text[:60]}")
        else:
            try:
                pid = json.loads(text).get("data", {}).get("id", "?")
                print(f"OK id={pid}")
                total += 1
            except: print("OK")

print(f"\nTotal: {total}/18")
