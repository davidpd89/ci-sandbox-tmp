"""Programa DP-F0-077, 078, 079 para Jul 21 y 22."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
NET_KEY = {"instagram":"instagramData","facebook":"facebookData","tiktok":"tiktokData",
           "threads":"threadsData","bluesky":"blueskyData","pinterest":"pinterestData"}

PIECES = [
    {
        "id": "DP-F0-077", "day": "2026-07-21",
        "url": "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-077-libro-ya-vivio/reel.mp4",
        "posts": [
            {"net":"threads",   "time":"08:30", "text":"Este libro ya vivió en otras manos antes que en las mías. Y traía una nota dentro. ¿La abrirías? #Lectura"},
            {"net":"bluesky",   "time":"09:00", "text":"Este libro ya vivió. Traía una nota dentro. ¿La abrirías?"},
            {"net":"tiktok",    "time":"10:00", "title":"Este libro ya vivió", "text":"Este libro ya vivió. Traía una nota. ¿La abrirías?\n\n#librosusados #librosegundamano #instalibros #booktok #leeresvivir #amoleer #bibliophile #parati"},
            {"net":"instagram", "time":"11:30", "text":"Este libro ya vivió en otras manos antes que en las mías.\n\nY traía una nota dentro. ¿La abrirías? 👇\n\n#librosusados #librosegundamano #historiasdepapel #librosconalma #instalibros #leeresvivir #booktok #librosenespañol"},
            {"net":"facebook",  "time":"13:00", "text":"Sostener un libro que ya pasó por otras manos. Imaginar quién lo leyó, qué marcó, por qué lo vendió.\n\n¿Abrirías una nota encontrada dentro?\n\nhttps://davidportodiaz.com"},
            {"net":"pinterest", "time":"16:00", "text":"Para lectores que se preguntan por las vidas que vivieron sus libros de segunda mano.", "pin_title":"Este libro ya vivió. Traía una nota dentro.", "pin_link":"https://davidportodiaz.com"},
        ]
    },
    {
        "id": "DP-F0-078", "day": "2026-07-22",
        "url": "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-078-olvide-el-final/reel.mp4",
        "posts": [
            {"net":"threads",   "time":"08:30", "text":"Olvidé el final. Pero sé que me dolió. ¿Con qué libro? #Lectura"},
            {"net":"bluesky",   "time":"09:30", "text":"Olvidé el final. Sé que me dolió. ¿Con qué libro te ha pasado?"},
            {"net":"tiktok",    "time":"10:00", "title":"Olvidé el final. Sé que me dolió.", "text":"Olvidé el final. Sé que me dolió. ¿Con qué libro?\n\n#memorialectora #booktok #lecturasquequedan #librosenespañol #amoleer #instalibros #parati"},
            {"net":"instagram", "time":"11:00", "text":"Olvidé el final. Pero sé que me dolió.\n\n¿Con qué libro te ha pasado? 👇\n\n#memorialectora #lecturasquequedan #librosqueamo #instalibros #leeresvivir #amoleer #lecturarecomendada #literaturahispana"},
            {"net":"facebook",  "time":"12:30", "text":"Hay libros que no recuerdas por la trama, sino por lo que te dejaron en el cuerpo.\n\n¿Con cuál te ha pasado?\n\nhttps://davidportodiaz.com"},
            {"net":"pinterest", "time":"16:30", "text":"Para lectores que recuerdan el golpe emocional aunque hayan olvidado el argumento.", "pin_title":"Olvidé el final. Sé que me dolió.", "pin_link":"https://davidportodiaz.com"},
        ]
    },
    {
        "id": "DP-F0-079", "day": "2026-07-22",
        "url": "https://davidpd89.github.io/rrss-davidporto-media/videos/DP-F0-079-doce-euros-bolsillo/reel.mp4",
        "posts": [
            {"net":"threads",   "time":"14:00", "text":"Doce euros bolsillo. Treinta si brilla. ¿Cuál fue tu mayor sablazo lector? #Lectura"},
            {"net":"bluesky",   "time":"17:00", "text":"Doce euros bolsillo. Treinta si brilla. ¿También te dolió?"},
            {"net":"tiktok",    "time":"18:00", "title":"Doce euros bolsillo. Treinta si brilla.", "text":"Doce euros bolsillo. Treinta si brilla. ¿También te dolió?\n\n#libroscaros #librosfisicos #booktok #lectores #noseadondevamidinero #parati"},
            {"net":"instagram", "time":"16:30", "text":"Doce euros bolsillo. Treinta si brilla. Y los compramos igual.\n\n¿Cuál fue tu mayor sablazo lector? 👇\n\n#libroscaros #librosfisicos #prioridades #noseadondevamidinero #librosrecomendados #leer #instalibros #booktok"},
            {"net":"facebook",  "time":"19:00", "text":"Doce euros el de bolsillo. Treinta si tiene la cubierta especial. Y lo compramos igual.\n\n¿Cuál fue tu mayor sablazo lector?\n\nhttps://davidportodiaz.com"},
            {"net":"pinterest", "time":"20:00", "text":"Para lectores que conocen el dolor de elegir entre el libro y el bolsillo.", "pin_title":"Doce euros bolsillo. Treinta si brilla.", "pin_link":"https://davidportodiaz.com"},
        ]
    },
]

total = 0
for piece in PIECES:
    print(f"\n{piece['id']} — {piece['day']}")
    for post in piece["posts"]:
        net = post["net"]
        date_str = f"{piece['day']}T{post['time']}:00+02:00"
        info = {
            "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
            "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
            "media": [piece["url"]],
            "providers": [{"network": net}],
            "text": post["text"],
            "publicationDate": {"dateTime": f"{piece['day']}T{post['time']}:00", "timezone": "Europe/Madrid"},
        }
        # NetworkData específico
        if net == "instagram":
            info["instagramData"] = {"type": "REEL", "showReelOnFeed": True}
        elif net == "facebook":
            info["facebookData"] = {"type": "REEL"}
        elif net == "tiktok":
            info["tiktokData"] = {"title": post.get("title", post["text"][:50]), "privacy": "PUBLIC_TO_EVERYONE", "disableDuet": False, "disableStitch": False, "disableComments": False}
        elif net == "threads":
            info["threadsData"] = {}
        elif net == "bluesky":
            info["blueskyData"] = {}
        elif net == "pinterest":
            info["pinterestData"] = {"boardId": "1081178560003791073", "pinTitle": post.get("pin_title", post["text"][:50]), "pinLink": post.get("pin_link", "https://davidportodiaz.com")}

        print(f"  {net:12} {post['time']}...", end=" ")
        r = call_tool("createScheduledPost", {"blogId": BLOG_ID, "date": date_str, "info": json.dumps(info, ensure_ascii=False)})
        text = r["content"][0]["text"] if r.get("content") else ""
        if not text or r.get("isError"):
            print(f"ERR: {text[:60]}")
        else:
            try:
                pid = json.loads(text).get("data", {}).get("id", "?")
                print(f"OK id={pid}")
                total += 1
            except Exception:
                print("OK")

print(f"\nTotal programados: {total}/18")
