# -*- coding: utf-8 -*-
"""
Actualiza P27-P31 (Jul 23-25) con las imagenes _v3 reales + captions de alto impacto.
Pattern ganador: confesion + detalle especifico + participacion directa.
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout

import os
os.chdir(r"C:\GIT\RRSS_DavidPorto\tools")
from metricool_client import call_tool

BLOG_ID = "6435452"
TZ = "Europe/Madrid"
BASE = "https://davidportodiaz.com/assets"
SITE = "https://davidportodiaz.com"

NET_KEY = {
    "instagram": "instagramData",
    "facebook": "facebookData",
    "tiktok": "tiktokData",
    "threads": "threadsData",
    "bluesky": "blueskyData",
    "pinterest": "pinterestData",
}

# =====================================================================
# PIEZAS: imagen + IDs de posts + captions por red
# =====================================================================

PIECES = [
    {
        "name": "P27 - No queremos leer, queremos parecer lectores",
        "image": f"{BASE}/1000106609_v3.png",
        "tiktok_title": "Queremos parecer lectores, no leer",
        "pin_title": "El libro como atrezo de identidad cultural",
        "pin_link": SITE,
        "ids": {345573183, 345573185, 345573194, 345573201, 345573204, 345573206},
        "captions": {
            "tiktok": (
                "El primer libro que compre para caerle bien a alguien... nunca lo abri. "
                "Pero lo tengo muy visible en la estanteria.\n\n"
                "Cuantos tienes tu asi?\n\n"
                "#libros #lectores #booktok #lectura #librosenespanol "
                "#booktokesp #librosencastellano #parati"
            ),
            "instagram": (
                "Tengo libros en la mesilla que cumplen anyos ahi. "
                "Uno lleva tanto tiempo que ya tiene sitio fijo.\n\n"
                "Cual es el tuyo? El que llevas meses prometiendote que ya lo empiezas "
                "y sigue igual de nuevo.\n\n"
                "En comentarios\n\n"
                "#bookstagram #libros #lectoresdeinstagram #librosenespanol #lectura "
                "#bibliofilo #leersies #instalibros #librosencastellano"
            ),
            "facebook": (
                "El libro mas valioso de tu estanteria: el que mas has subrayado "
                "o el que mejor queda cuando alguien entra a casa?\n\n"
                "Se honesto. En comentarios\n\n"
                f"{SITE}"
            ),
            "threads": (
                "Reconocer el problema es el primer paso. El segundo es comprar otro.\n\n"
                "Cuantos libros de decoracion tienes tu?"
            ),
            "bluesky": (
                "Comprar libros y leerlos son dos aficiones distintas. "
                "Yo las tengo las dos. Una la disfruto mas que la otra.\n\nY tu?"
            ),
            "pinterest": (
                "El libro como identidad cultural - lectores que compran mas de lo que leen - davidportodiaz.com"
            ),
        },
    },
    {
        "name": "P28 - Leer a veces es esto: 4 dias / 3 semanas / una noche",
        "image": f"{BASE}/1000106601_v3.png",
        "tiktok_title": "Las tres velocidades del lector",
        "pin_title": "Las tres velocidades de los lectores",
        "pin_link": SITE,
        "ids": {345573210, 345573211, 345573214, 345573217, 345573220, 345573221},
        "captions": {
            "tiktok": (
                "Hay un libro que llevas semanas a punto de empezar. "
                "Y otro que terminaste en una noche que ni recuerdas cuando fue.\n\n"
                "Cual fue ese ultimo?\n\n"
                "#libros #lectores #booktok #lectura #parati #booktokesp #librosenespanol"
            ),
            "instagram": (
                "Hay libros que te piden una pagina mas a las 2 de la manyana. "
                "Llegas al amanecer sin entender como.\n\n"
                "Cual fue el ultimo que te hizo eso?\n\n"
                "Nombre en comentarios (y cuantas horas dormiste despues)\n\n"
                "#bookstagram #libros #lectoresdeinstagram #librosenespanol #lectura "
                "#nochesdeleer #instalibros #librosencastellano #lectoresnocturnos"
            ),
            "facebook": (
                "Cual fue el ultimo libro que terminaste en una noche sin querer?\n\n"
                "El que ibas a leer solo un rato y cerro contigo a las 5 de la manyuana.\n\n"
                f"Cuentalo en comentarios\n\n{SITE}"
            ),
            "threads": (
                "Hay libros de 4 dias. Hay libros de 3 semanas. "
                "Y hay libros de una noche que no puedes explicar.\n\n"
                "Cual fue el tuyo de esta ultima categoria?"
            ),
            "bluesky": (
                "El libro que terminaste sin querer, en una noche, sin haberlo planeado. "
                "Como se llamaba?"
            ),
            "pinterest": (
                "Las tres categorias de lectores - leer en una noche - libros que enganchan - davidportodiaz.com"
            ),
        },
    },
    {
        "name": "P29 - Me fui cuando querer empezo a doler mas que quedarse",
        "image": f"{BASE}/1000106605_v3.png",
        "tiktok_title": "Dos voces sobre el mismo dolor",
        "pin_title": "Dos voces sobre querer y quedarse",
        "pin_link": SITE,
        "ids": {345573224, 345573227, 345573232, 345573237, 345573240, 345573245},
        "captions": {
            "tiktok": (
                "La primera vez que lei esto lo guarde sin reenviar. "
                "Porque era demasiado mio.\n\n"
                "Con cual de las dos voces has estado alguna vez?\n\n"
                "#emociones #citas #reflexiones #lectores #booktok "
                "#librosenespanol #parati #frases"
            ),
            "instagram": (
                "A veces la decision mas valiente no es quedarse.\n\n"
                "Con cual de las dos voces te has sentido mas identificado/a alguna vez?\n\n"
                "Sin nombre si quieres. Solo la voz. En comentarios\n\n"
                "#frases #reflexiones #emociones #bookstagram #libros "
                "#librosenespanol #citas #pensamientos #lectores"
            ),
            "facebook": (
                "Dos voces sobre el mismo dolor. Dos respuestas distintas.\n\n"
                f"Con cual te has encontrado alguna vez?\n\n{SITE}"
            ),
            "threads": (
                '"Me fui cuando querer empezo a doler mas que quedarse."\n'
                '"A veces duele porque todavia tiene nombre."\n\n'
                "Con cual has estado tu?"
            ),
            "bluesky": (
                "Dos voces sobre el mismo dolor. Dos decisiones distintas. "
                "Con cual has estado tu."
            ),
            "pinterest": (
                "Frases sobre querer y quedarse - dos voces sobre el mismo dolor - davidportodiaz.com"
            ),
        },
    },
    {
        "name": "P30 - Cuando alguien sabe quedarse mientras intentas explicarte",
        "image": f"{BASE}/1000106606_v3.png",
        "tiktok_title": "Cuando alguien sabe quedarse",
        "pin_title": "Cuando alguien sabe quedarse mientras te explicas",
        "pin_link": SITE,
        "ids": {345573247, 345573250, 345573252, 345573257, 345573259, 345573265},
        "captions": {
            "tiktok": (
                "Hay una persona concreta en tu vida que encaja exactamente en esto. "
                "Que ha aguantado una conversacion a medias sin pedirte que termines.\n\n"
                "Cuando fue la ultima vez que se lo dijiste?\n\n"
                "#emociones #relaciones #reflexiones #parati #frases #conexiones #booktok"
            ),
            "instagram": (
                "Hay una persona concreta en tu vida que encaja en esto.\n\n"
                "No todo el mundo tiene a alguien que se queda cuando no sabes "
                "como terminar la frase.\n\n"
                "Cuando fue la ultima vez que se lo dijiste? "
                "En comentarios (o etiquetalx directamente)\n\n"
                "#relaciones #emociones #bookstagram #conexiones #frases "
                "#reflexiones #librosenespanol #lectores #amistad"
            ),
            "facebook": (
                "No todo el mundo tiene a alguien asi. "
                "Los que lo tienen raramente se lo dicen.\n\n"
                f"Tienes a esa persona? Se lo has dicho?\n\n{SITE}"
            ),
            "threads": (
                "No pasa nada. Sigue.\n\n"
                "Hay personas que saben decir eso. Y cambiar todo con ello.\n\n"
                "Tienes a alguien asi?"
            ),
            "bluesky": (
                '"No se decirlo bien." / "No pasa nada. Sigue."\n\n'
                "Las palabras que mas cuestan. Tienes a alguien que las diga?"
            ),
            "pinterest": (
                "Cuando alguien sabe quedarse - conexiones emocionales reales - davidportodiaz.com"
            ),
        },
    },
    {
        "name": "P31 - No puedo sacarte de la niebla pero puedo quedarme",
        "image": f"{BASE}/1000106604_v3.png",
        "tiktok_title": "Quedarse hasta que amanezca",
        "pin_title": "No sacarte de la niebla, solo quedarme",
        "pin_link": SITE,
        "ids": {345573266, 345573267, 345573269, 345573273, 345573275, 345573276},
        "captions": {
            "tiktok": (
                "Hay alguien que necesita leer esto hoy. "
                "Sabes exactamente quien es.\n\n"
                "#emociones #apoyo #amistad #parati #reflexiones #frases #conexiones #booktok"
            ),
            "instagram": (
                "Hay alguien que necesita leer esto hoy.\n\n"
                "Sabes exactamente quien es.\n\n"
                "#emociones #apoyo #amistad #bookstagram #reflexiones "
                "#frases #conexiones #librosenespanol #lectores"
            ),
            "facebook": (
                "A veces no se puede arreglar nada. Solo estar.\n\n"
                f"Tienes a alguien asi en tu vida?\n\n{SITE}"
            ),
            "threads": (
                "A veces no se puede arreglar nada. Solo estar.\n\n"
                "Tienes a alguien que sepa hacer eso?"
            ),
            "bluesky": (
                "No sacarte de la niebla. Solo quedarse hasta que amanezca. "
                "Tienes a alguien asi?"
            ),
            "pinterest": (
                "Quedarse sin poder arreglarlo - apoyo emocional real - frases que importan - davidportodiaz.com"
            ),
        },
    },
]


def get_posts_jul23_25():
    r = call_tool("getScheduledPosts", {
        "brandId": BLOG_ID,
        "fromDate": "2026-07-23T00:00:00Z",
        "toDate": "2026-07-25T23:59:59Z",
        "timezone": TZ,
    })
    content = r.get("content", [])
    text = content[0].get("text", "") if content else ""
    try:
        data = json.loads(text)
        return data.get("data", [])
    except Exception:
        print(f"ERROR parsing posts: {text[:200]}")
        return []


def upd(p, new_image_url, new_caption, tiktok_title=None, pin_title=None, pin_link=None):
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")

    info = {
        "autoPublish": True,
        "draft": False,
        "text": new_caption,
        "media": [new_image_url],
        "providers": p.get("providers", []),
        "publicationDate": p.get("publicationDate", {}),
        "descendants": [],
        "firstCommentText": "",
        "hasNotReadNotes": False,
        "shortener": False,
        "smartLinkData": {"ids": []},
    }

    # Copy existing network-specific data
    ck = NET_KEY.get(net)
    if ck and ck in p:
        info[ck] = p[ck]

    # Override TikTok title
    if net == "tiktok" and tiktok_title:
        info["tiktokData"] = info.get("tiktokData", {})
        info["tiktokData"]["title"] = tiktok_title

    # Override Pinterest data
    if net == "pinterest" and pin_title:
        info["pinterestData"] = {
            "boardId": "1096626646706067804",
            "pinTitle": pin_title,
            "pinLink": pin_link or SITE,
        }

    r = call_tool("updateScheduledPost", {
        "blogId": BLOG_ID,
        "id": str(p["id"]),
        "uuid": p.get("uuid", ""),
        "info": json.dumps(info, ensure_ascii=False),
    })

    ok = not (isinstance(r, dict) and r.get("isError"))
    if not ok:
        content = r.get("content", [])
        err = content[0].get("text", str(r))[:150] if content else str(r)[:150]
        print(f"    ERROR {net}: {err}")
    return ok


def main():
    print("Obteniendo posts Jul 23-25...")
    all_posts = get_posts_jul23_25()
    print(f"Total posts: {len(all_posts)}\n")

    for piece in PIECES:
        print(f"=== {piece['name']} ===")
        piece_posts = [p for p in all_posts if p.get("id") in piece["ids"]]
        print(f"  Posts encontrados: {len(piece_posts)}/6")

        for p in piece_posts:
            net = next((pr.get("network") for pr in p.get("providers", [])), "?")
            caption = piece["captions"].get(net, "")
            if not caption:
                print(f"  {net:12} SKIP (no caption)")
                continue

            ok = upd(
                p,
                piece["image"],
                caption,
                tiktok_title=piece.get("tiktok_title"),
                pin_title=piece.get("pin_title"),
                pin_link=piece.get("pin_link"),
            )
            dt = p.get("publicationDate", {}).get("dateTime", "?")
            print(f"  {net:12} {dt[11:16]} -> {'OK' if ok else 'FAIL'}")

        print()

    print("Listo.")


if __name__ == "__main__":
    main()
