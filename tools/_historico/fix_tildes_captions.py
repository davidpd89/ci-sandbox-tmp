# -*- coding: utf-8 -*-
"""
Corrige los 30 captions de P27-P31: tildes, ¿, ñ correctos.
Busca posts por fecha+rango de hora (robusto a cambios de ID).
REGLA CRITICA: SIEMPRE revisar tildes antes de updateScheduledPost.
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout
import os; os.chdir(r"C:\GIT\RRSS_DavidPorto\tools")
from metricool_client import call_tool

BLOG_ID = "6435452"
TZ = "Europe/Madrid"
SITE = "https://davidportodiaz.com"

NET_KEY = {
    "instagram": "instagramData",
    "facebook": "facebookData",
    "tiktok": "tiktokData",
    "threads": "threadsData",
    "bluesky": "blueskyData",
    "pinterest": "pinterestData",
}

# Piezas: date_prefix + hora_inicio + hora_fin para filtrar posts del rango
# (excluye el lote de "spoiler" que está a las 19:00-21:30 del 23 jul)

PIECES = [
    {
        "name": "P27 — No queremos leer, queremos parecer lectores",
        "date": "2026-07-23",
        "t_start": "09:00", "t_end": "13:00",
        "captions": {
            "tiktok": (
                "El primer libro que compré para caerle bien a alguien... nunca lo abrí. "
                "Pero lo tengo muy visible en la estantería.\n\n"
                "¿Cuántos tienes tú así?\n\n"
                "#libros #lectores #booktok #lectura #librosenespañol "
                "#booktokesp #librosencastellano #parati"
            ),
            "instagram": (
                "Tengo libros en la mesilla que cumplen años ahí. "
                "Uno lleva tanto tiempo que ya tiene sitio fijo.\n\n"
                "¿Cuál es el tuyo? El que llevas meses prometiéndote que 'ya lo empiezas' "
                "y sigue igual de nuevo.\n\n"
                "En comentarios 👇\n\n"
                "#bookstagram #libros #lectoresdeinstagram #librosenespañol #lectura "
                "#bibliófilo #leersies #instalibros #librosencastellano"
            ),
            "facebook": (
                "El libro más valioso de tu estantería: ¿el que más has subrayado "
                "o el que mejor queda cuando alguien entra a casa?\n\n"
                "Sé honesto. En comentarios 👇\n\n"
                f"{SITE}"
            ),
            "threads": (
                "Reconocer el problema es el primer paso. El segundo es comprar otro.\n\n"
                "¿Cuántos libros de 'decoración' tienes tú?"
            ),
            "bluesky": (
                "Comprar libros y leerlos son dos aficiones distintas. "
                "Yo las tengo las dos. Una la disfruto más que la otra.\n\n¿Y tú?"
            ),
            "pinterest": (
                "El libro como identidad cultural · lectores que compran más de lo que leen · davidportodiaz.com"
            ),
        },
        "tiktok_title": "Queremos parecer lectores, no leer",
    },
    {
        "name": "P28 — Leer a veces es esto: 4 días / 3 semanas / una noche",
        "date": "2026-07-24",
        "t_start": "07:00", "t_end": "11:00",
        "captions": {
            "tiktok": (
                "Hay un libro que llevas semanas 'a punto de empezar'. "
                "Y otro que terminaste en una noche que ni recuerdas cuándo fue.\n\n"
                "¿Cuál fue ese último?\n\n"
                "#libros #lectores #booktok #lectura #parati #booktokesp #librosenespañol"
            ),
            "instagram": (
                "Hay libros que te piden 'una página más' a las 2 de la mañana. "
                "Llegas al amanecer sin entender cómo.\n\n"
                "¿Cuál fue el último que te hizo eso?\n\n"
                "Nombre en comentarios 👇 (y cuántas horas dormiste después)\n\n"
                "#bookstagram #libros #lectoresdeinstagram #librosenespañol #lectura "
                "#nochesdeleer #instalibros #librosencastellano #lectoresnocturnos"
            ),
            "facebook": (
                "¿Cuál fue el último libro que terminaste en una noche sin querer?\n\n"
                "El que ibas a leer 'solo un rato' y cerró contigo a las 5 de la mañana.\n\n"
                f"Cuéntalo en comentarios 👇\n\n{SITE}"
            ),
            "threads": (
                "Hay libros de 4 días. Hay libros de 3 semanas. "
                "Y hay libros de una noche que no puedes explicar.\n\n"
                "¿Cuál fue el tuyo de esta última categoría?"
            ),
            "bluesky": (
                "El libro que terminaste sin querer, en una noche, sin haberlo planeado. "
                "¿Cómo se llamaba?"
            ),
            "pinterest": (
                "Las tres velocidades de los lectores · leer en una noche · libros que enganchan · davidportodiaz.com"
            ),
        },
        "tiktok_title": "Las tres velocidades del lector",
    },
    {
        "name": "P29 — Me fui cuando querer empezó a doler más que quedarse",
        "date": "2026-07-24",
        "t_start": "15:00", "t_end": "19:00",
        "captions": {
            "tiktok": (
                "La primera vez que leí esto lo guardé sin reenviar. "
                "Porque era demasiado mío.\n\n"
                "¿Con cuál de las dos voces has estado alguna vez?\n\n"
                "#emociones #citas #reflexiones #lectores #booktok "
                "#librosenespañol #parati #frases"
            ),
            "instagram": (
                "A veces la decisión más valiente no es quedarse.\n\n"
                "¿Con cuál de las dos voces te has sentido más identificado/a alguna vez?\n\n"
                "Sin nombre si quieres. Solo la voz. En comentarios 👇\n\n"
                "#frases #reflexiones #emociones #bookstagram #libros "
                "#librosenespañol #citas #pensamientos #lectores"
            ),
            "facebook": (
                "Dos voces sobre el mismo dolor. Dos respuestas distintas.\n\n"
                f"¿Con cuál te has encontrado alguna vez?\n\n{SITE}"
            ),
            "threads": (
                '"Me fui cuando querer empezó a doler más que quedarse."\n'
                '"A veces duele porque todavía tiene nombre."\n\n'
                "¿Con cuál has estado tú?"
            ),
            "bluesky": (
                "Dos voces sobre el mismo dolor. Dos decisiones distintas. "
                "¿Con cuál has estado tú?"
            ),
            "pinterest": (
                "Frases sobre querer y quedarse · dos voces sobre el mismo dolor · davidportodiaz.com"
            ),
        },
        "tiktok_title": "Dos voces sobre el mismo dolor",
    },
    {
        "name": "P30 — Cuando alguien sabe quedarse mientras intentas explicarte",
        "date": "2026-07-25",
        "t_start": "07:00", "t_end": "11:00",
        "captions": {
            "tiktok": (
                "Hay una persona concreta en tu vida que encaja exactamente en esto. "
                "Que ha aguantado una conversación a medias sin pedirte que termines.\n\n"
                "¿Cuándo fue la última vez que se lo dijiste?\n\n"
                "#emociones #relaciones #reflexiones #parati #frases #conexiones #booktok"
            ),
            "instagram": (
                "Hay una persona concreta en tu vida que encaja en esto.\n\n"
                "No todo el mundo tiene a alguien que se queda cuando no sabes "
                "cómo terminar la frase.\n\n"
                "¿Cuándo fue la última vez que se lo dijiste? "
                "En comentarios 👇 (o etiquétala directamente)\n\n"
                "#relaciones #emociones #bookstagram #conexiones #frases "
                "#reflexiones #librosenespañol #lectores #amistad"
            ),
            "facebook": (
                "No todo el mundo tiene a alguien así. "
                "Los que lo tienen raramente se lo dicen.\n\n"
                f"¿Tienes a esa persona? ¿Se lo has dicho?\n\n{SITE}"
            ),
            "threads": (
                "No pasa nada. Sigue.\n\n"
                "Hay personas que saben decir eso. Y cambiar todo con ello.\n\n"
                "¿Tienes a alguien así?"
            ),
            "bluesky": (
                '"No sé decirlo bien." / "No pasa nada. Sigue."\n\n'
                "Las palabras que más cuestan. ¿Tienes a alguien que las diga?"
            ),
            "pinterest": (
                "Cuando alguien sabe quedarse · conexiones emocionales reales · davidportodiaz.com"
            ),
        },
        "tiktok_title": "Cuando alguien sabe quedarse",
    },
    {
        "name": "P31 — No puedo sacarte de la niebla pero puedo quedarme",
        "date": "2026-07-25",
        "t_start": "14:00", "t_end": "18:00",
        "captions": {
            "tiktok": (
                "Hay alguien que necesita leer esto hoy. "
                "Sabes exactamente quién es.\n\n"
                "#emociones #apoyo #amistad #parati #reflexiones #frases #conexiones #booktok"
            ),
            "instagram": (
                "Hay alguien que necesita leer esto hoy.\n\n"
                "Sabes exactamente quién es.\n\n"
                "#emociones #apoyo #amistad #bookstagram #reflexiones "
                "#frases #conexiones #librosenespañol #lectores"
            ),
            "facebook": (
                "A veces no se puede arreglar nada. Solo estar.\n\n"
                f"¿Tienes a alguien así en tu vida?\n\n{SITE}"
            ),
            "threads": (
                "A veces no se puede arreglar nada. Solo estar.\n\n"
                "¿Tienes a alguien que sepa hacer eso?"
            ),
            "bluesky": (
                "No sacarte de la niebla. Solo quedarse hasta que amanezca. "
                "¿Tienes a alguien así?"
            ),
            "pinterest": (
                "Quedarse sin poder arreglarlo · apoyo emocional real · frases que importan · davidportodiaz.com"
            ),
        },
        "tiktok_title": "Quedarse hasta que amanezca",
    },
]


def get_all_posts():
    r = call_tool("getScheduledPosts", {
        "brandId": BLOG_ID,
        "fromDate": "2026-07-23T00:00:00Z",
        "toDate": "2026-07-25T23:59:59Z",
        "timezone": TZ,
    })
    content = r.get("content", [])
    text = content[0].get("text", "") if content else ""
    try:
        return json.loads(text).get("data", [])
    except Exception:
        return []


def posts_in_window(all_posts, date, t_start, t_end):
    matched = []
    for p in all_posts:
        dt = p.get("publicationDate", {}).get("dateTime", "")
        if not dt.startswith(date):
            continue
        t = dt[11:16]  # "HH:MM"
        if t_start <= t <= t_end:
            matched.append(p)
    return matched


def upd_caption(p, new_caption, tiktok_title=None):
    net = next((pr.get("network") for pr in p.get("providers", [])), "?")
    media = p.get("media", [])

    info = {
        "autoPublish": True,
        "draft": False,
        "text": new_caption,
        "media": media,
        "providers": p.get("providers", []),
        "publicationDate": p.get("publicationDate", {}),
        "descendants": [],
        "firstCommentText": "",
        "hasNotReadNotes": False,
        "shortener": False,
        "smartLinkData": {"ids": []},
    }
    ck = NET_KEY.get(net)
    if ck and ck in p:
        info[ck] = p[ck]

    if net == "tiktok" and tiktok_title:
        info["tiktokData"] = info.get("tiktokData", {})
        info["tiktokData"]["title"] = tiktok_title

    if net == "pinterest":
        info["pinterestData"] = {
            "boardId": "1096626646706067804",
            "pinTitle": new_caption[:80],
            "pinLink": SITE,
        }

    r = call_tool("updateScheduledPost", {
        "blogId": BLOG_ID,
        "id": str(p["id"]),
        "uuid": p.get("uuid", ""),
        "info": json.dumps(info, ensure_ascii=False),
    })
    ok = not (isinstance(r, dict) and r.get("isError"))
    if not ok:
        ct = r.get("content", [])
        err = ct[0].get("text", str(r))[:150] if ct else str(r)[:150]
        print(f"    ERR {net}: {err}")
    return ok


def main():
    print("Obteniendo posts Jul 23-25...")
    all_posts = get_all_posts()
    print(f"Total: {len(all_posts)}\n")

    for piece in PIECES:
        print(f"=== {piece['name']} ===")
        window = posts_in_window(all_posts, piece["date"], piece["t_start"], piece["t_end"])
        print(f"  Posts en ventana: {len(window)}")

        for p in window:
            net = next((pr.get("network") for pr in p.get("providers", [])), "?")
            caption = piece["captions"].get(net)
            if not caption:
                print(f"  {net:12} SKIP (sin caption definida)")
                continue
            ok = upd_caption(p, caption, piece.get("tiktok_title"))
            dt = p.get("publicationDate", {}).get("dateTime", "?")
            print(f"  {net:12} {dt[11:16]} -> {'OK ✓' if ok else 'FAIL'}")
        print()

    print("Captions actualizados con tildes y ¿ correctos.")


if __name__ == "__main__":
    main()
