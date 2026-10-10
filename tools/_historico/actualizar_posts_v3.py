"""
Actualiza los 28 posts estáticos que se programaron mal
con el contenido de verdad: reels animados + carruseles estilizados.

IDs a actualizar (los 28 posts de la sesión anterior):
Pieza 27 (Jul 23, estática): 345570733 TikTok, 345570845 IG, 345570735 FB, 345570736 Threads, 345570737 BS, 345570848 Pinterest
Pieza 28 (Jul 24 mañana): 345570746 TikTok, 345570742 IG, 345570745 FB, 345570747 Threads, 345570748 BS, 345570851 Pinterest
Pieza 29 (Jul 24 tarde): 345570750 TikTok, 345570846 IG, 345570752 FB, 345570753 Threads, 345570754 BS, 345570854 Pinterest
Pieza 30 (Jul 25 mañana): 345570755 TikTok, 345570847 IG, 345570758 FB, 345570759 Threads, 345570760 BS, 345570855 Pinterest
Pieza 31 (Jul 25 tarde): 345570761 TikTok, 345570773 IG, 345570776 FB, 345570777 Threads, 345570778 BS, 345570857 Pinterest

Nuevos formatos:
- Jul 23: REEL (video Ken Burns bookstore)
- Jul 24 mañana: CARRUSEL escritores (7 slides PIL) — ya es carrusel, ok
- Jul 24 tarde: REEL (video Ken Burns humor)
- Jul 25 mañana: CARRUSEL dualidad (5 slides PIL) — ya es carrusel, ok
- Jul 25 tarde: REEL (video Ken Burns emocional)
"""
import sys
import json
import time
import os
sys.stdout.reconfigure(encoding="utf-8")
os.chdir(r"C:\GIT\RRSS_DavidPorto\tools")
from metricool_client import call_tool

BLOG_ID = "6435452"
TZ = "Europe/Madrid"
IMG_BASE = "https://davidportodiaz.com/assets/"
VID_BASE = "https://davidpd89.github.io/rrss-davidporto-media/videos/"
BOARD = "1096626646706067804"

def img(name): return IMG_BASE + name
def vid(name): return VID_BASE + name


UUID_MAP = {
    345570733: "-8165562240401062193",
    345570735: "8879571577200331549",
    345570736: "1275974677111981096",
    345570737: "-1603967259593455092",
    345570742: "1278372295262683259",
    345570745: "8128964415692426206",
    345570746: "6447171036731822023",
    345570747: "7784940479853642303",
    345570748: "456588147462193467",
    345570750: "5764420723622759172",
    345570752: "-2819452801987359115",
    345570753: "8625933818138349285",
    345570754: "-7798873416946204101",
    345570755: "-4684430779441919649",
    345570758: "1771693631580947536",
    345570759: "2696992746925474578",
    345570760: "-8578076449825667556",
    345570761: "-8714703851585909581",
    345570773: "-6259646760837169085",
    345570776: "9064034896209527978",
    345570777: "-5637771651016537692",
    345570778: "-4359317319541700943",
    345570845: "-5226623624832791745",
    345570846: "-3978476135114849268",
    345570847: "5756279103237277454",
    345570848: "-8376208835629528952",
    345570851: "-481996021296184294",
    345570854: "2818614363554859879",
    345570855: "-7886619804121939757",
    345570857: "6762761287768294588",
}

def update_post(post_id, date_str, text, providers, media_list, extra=None):
    info = {
        "text": text,
        "providers": providers,
        "media": media_list,
        "publicationDate": {"dateTime": date_str[:19], "timezone": TZ},
        "descendants": [],
    }
    if extra:
        info.update(extra)
    r = call_tool("updateScheduledPost", {
        "id": str(post_id),
        "uuid": UUID_MAP[post_id],
        "blogId": BLOG_ID,
        "info": json.dumps(info),
    })
    if isinstance(r, dict):
        content = r.get("content", [])
        txt = content[0].get("text", "{}") if content else "{}"
    else:
        txt = str(r)
    is_error = isinstance(r, dict) and r.get("isError", False)
    if is_error:
        print(f"  ERROR id={post_id}: {txt[:100]}", flush=True)
        return False
    print(f"  OK id={post_id}", flush=True)
    return True


# ─────────────────────────────────────────────────────────────
# PIEZA 27 — Jul 23 — REEL bookstore (antes foto estatica)
# ─────────────────────────────────────────────────────────────
print("\n=== PIEZA 27 — Jul 23 REEL bookstore ===")
REEL1 = vid("reel_bookstore_jul23.mp4")
TITLE1 = "Entro solo a mirar. Nunca es verdad."

cap_tt1 = (
    "Entro solo a mirar. Lo digo de verdad.\n"
    "Veinte minutos despues: tres libros bajo el brazo.\n"
    "Cara de culpable. Ningun arrepentimiento.\n"
    "#bookstagram #lectores #libros #booktokespanol #librerias"
)
cap_ig1 = (
    "Entro 'solo a mirar'.\n\n"
    "Lo digo cada vez con la misma conviccion.\n"
    "Lo creo cada vez con la misma ingenuidad.\n\n"
    "Veinte minutos despues: tres libros. Cara de culpable. Cero arrepentimiento.\n\n"
    "Cuantos tardas tu en soltar la promesa? Cuenta en comentarios\n\n"
    "Guarda si eres igual de mentiroso/a\n\n"
    "#bookstagram #libros #lectores #librosenespanol #lectura "
    "#librerias #booklovers #librosaddict #leoporquequiero"
)
cap_fb1 = (
    "Entro 'solo a mirar'. Siempre miento.\n\n"
    "Tres libros despues, la culpa dura menos que el placer de llevarlos.\n\n"
    "Cuantos tardas en rendirte? #libros #lectores #librerias"
)
cap_threads1 = (
    "Entro 'solo a mirar'. Salgo con tres libros y la felicidad culpable "
    "del que sabe exactamente lo que ha hecho. "
    "Cuanto te ha durado la promesa hoy?"
)
cap_bs1 = (
    "Entro solo a mirar. Siempre miento.\n"
    "Cuanto te dura la promesa?\n"
    "#bookstagram #libros #lectores"
)
cap_pin1 = (
    "La libreria y su trampa eterna — entro a mirar, salgo sin dinero | "
    "La experiencia lectora mas honesta del mundo | Guarda si te ha pasado hoy"
)

# TikTok 10:00
update_post(345570733, "2026-07-23T10:00:00+02:00", cap_tt1,
            [{"network": "tiktok"}], [REEL1],
            {"tiktokData": {"title": TITLE1}})
time.sleep(1)

# Instagram 11:00 — REEL
update_post(345570845, "2026-07-23T11:00:00+02:00", cap_ig1,
            [{"network": "instagram"}], [REEL1],
            {"instagramData": {"type": "REEL"}})
time.sleep(1)

# Facebook 11:30
update_post(345570735, "2026-07-23T11:30:00+02:00", cap_fb1,
            [{"network": "facebook"}], [REEL1])
time.sleep(1)

# Threads 12:00
update_post(345570736, "2026-07-23T12:00:00+02:00", cap_threads1,
            [{"network": "threads"}], [REEL1])
time.sleep(1)

# Bluesky 10:30
update_post(345570737, "2026-07-23T10:30:00+02:00", cap_bs1,
            [{"network": "bluesky"}], [REEL1])
time.sleep(1)

# Pinterest 11:45 — Reels no encajan bien en Pinterest, usar primer frame (imagen)
# Para Pinterest usamos la imagen original _v3 (no el video)
update_post(345570848, "2026-07-23T11:45:00+02:00", cap_pin1,
            [{"network": "pinterest"}], [img("1000106609_v3.png")],
            {"pinterestData": {"boardId": BOARD,
                               "pinTitle": "Entro solo a mirar — la libreria y sus mentiras",
                               "pinLink": "https://davidportodiaz.com"}})
time.sleep(1)


# ─────────────────────────────────────────────────────────────
# PIEZA 28 — Jul 24 mañana — CARRUSEL citas escritores
# ─────────────────────────────────────────────────────────────
print("\n=== PIEZA 28 — Jul 24 CARRUSEL citas escritores ===")
SLIDES28 = [
    img("quote_00_intro.png"),
    img("quote_01_franz.png"),
    img("quote_02_jorge.png"),
    img("quote_03_virginia.png"),
    img("quote_04_julio.png"),
    img("quote_05_fiodor.png"),
    img("quote_cta.png"),
]

cap_tt28 = (
    "Kafka, Borges, Woolf, Cortazar, Dostoievski.\n"
    "5 frases que te cambian algo por dentro si las lees de verdad.\n"
    "Cual es la tuya? Comenta #booktokespanol #frasesliterarias #escritores #literatura"
)
cap_ig28 = (
    "Hay escritores que te consuelan.\nY escritores que te rompen el comodo.\n\n"
    "Ambos son necesarios. Nunca al mismo tiempo.\n\n"
    "Desliza y queda con la que necesitas hoy.\n\n"
    "Guarda para volver cuando la necesites "
    "· Comenta quien te ha roto mas de estos cinco\n\n"
    "#frasesdelibros #literatura #escritores #citasliterarias "
    "#frasesprofundas #reflexion #libros #lectura #librosenespanol"
)
cap_fb28 = (
    "Kafka, Borges, Woolf, Cortazar, Dostoievski.\n"
    "5 frases. Una para cada estado de animo.\n\n"
    "Cual es la tuya de hoy?\n\n#literatura #frasesliterarias #libros"
)
cap_threads28 = (
    "5 escritores, 5 formas de romperte algo por dentro. "
    "Desliza y elige la que mas te ha costado leer sin detenerte. "
    "Cual es?"
)
cap_bs28 = (
    "Kafka, Borges, Woolf, Cortazar, Dostoievski.\n"
    "5 frases que te cambian algo si las dejas.\n"
    "Cual es la tuya?\n"
    "#frasesliterarias #literatura #libros"
)
cap_pin28 = (
    "Frases de escritores que te cambian algo — Kafka, Borges, Woolf, Cortazar, Dostoievski | "
    "Citas literarias para releer | Guarda la que necesitas hoy"
)

# TikTok 08:00 — solo primer slide
update_post(345570746, "2026-07-24T08:00:00+02:00", cap_tt28,
            [{"network": "tiktok"}], [img("quote_01_franz.png")],
            {"tiktokData": {"title": "5 frases de escritores que te cambian algo."}})
time.sleep(1)

# Instagram 09:00 — carrusel completo
update_post(345570742, "2026-07-24T09:00:00+02:00", cap_ig28,
            [{"network": "instagram"}], SLIDES28)
time.sleep(1)

# Facebook 09:30 — carrusel
update_post(345570745, "2026-07-24T09:30:00+02:00", cap_fb28,
            [{"network": "facebook"}], SLIDES28)
time.sleep(1)

# Threads 09:45 — imagen sola
update_post(345570747, "2026-07-24T09:45:00+02:00", cap_threads28,
            [{"network": "threads"}], [img("quote_02_jorge.png")])
time.sleep(1)

# Bluesky 08:30 — imagen sola
update_post(345570748, "2026-07-24T08:30:00+02:00", cap_bs28,
            [{"network": "bluesky"}], [img("quote_03_virginia.png")])
time.sleep(1)

# Pinterest 09:15 — intro + 3 slides
update_post(345570851, "2026-07-24T09:15:00+02:00", cap_pin28,
            [{"network": "pinterest"}], SLIDES28[:4],
            {"pinterestData": {"boardId": BOARD,
                               "pinTitle": "Frases de escritores que te cambian — Kafka, Borges, Woolf",
                               "pinLink": "https://davidportodiaz.com"}})
time.sleep(1)


# ─────────────────────────────────────────────────────────────
# PIEZA 29 — Jul 24 tarde — REEL humor lector
# ─────────────────────────────────────────────────────────────
print("\n=== PIEZA 29 — Jul 24 tarde REEL humor ===")
REEL2 = vid("reel_humor_jul24.mp4")
TITLE2 = "Comprar libros y leer libros son aficiones distintas."

cap_tt29 = (
    "Comprar libros. Y leer libros. Son aficiones distintas.\n"
    "Una para el presente. Otra para el yo futuro que nunca llega.\n"
    "Y aun asi: otro libro.\n"
    "#bookstagram #lectores #libros #booktokespanol #bookaddicted"
)
cap_ig29 = (
    "Comprar libros y leer libros son aficiones distintas.\n\n"
    "Una la practico a diario. La otra, en teoria.\n\n"
    "El yo futuro que iba a leer toda esa pila sigue sin aparecer.\n"
    "Pero el yo presente ya tiene otro encargo.\n\n"
    "Cuantos llevas en la pila? Cuenta sin mentirte\n\n"
    "Guarda si te defines aqui\n\n"
    "#bookstagram #libros #lectores #librosenespanol #bookaddicted "
    "#leoporquequiero #diariodeunlector #readingcommunity #booklovers"
)
cap_fb29 = (
    "Comprar libros y leer libros son aficiones distintas.\n\n"
    "El yo futuro que iba a leer toda esa pila lleva meses sin aparecer.\n\n"
    "Cuantos tienes en la tuya? #libros #lectores #bookstagram"
)
cap_threads29 = (
    "Comprar libros y leer libros son aficiones distintas. "
    "Una la practico a diario. La otra, en teoria. "
    "El yo futuro que iba a leer toda la pila sigue sin aparecer."
)
cap_bs29 = (
    "Comprar libros y leer libros: aficiones distintas.\n"
    "El yo futuro sigue sin aparecer a leer la pila.\n"
    "#bookstagram #lectores #libros"
)
cap_pin29 = (
    "Comprar libros vs leer libros — la distincion mas honesta | "
    "La pila de pendientes que crece sin parar | Guarda si eres igual"
)

update_post(345570750, "2026-07-24T16:00:00+02:00", cap_tt29,
            [{"network": "tiktok"}], [REEL2],
            {"tiktokData": {"title": TITLE2}})
time.sleep(1)

update_post(345570846, "2026-07-24T17:00:00+02:00", cap_ig29,
            [{"network": "instagram"}], [REEL2],
            {"instagramData": {"type": "REEL"}})
time.sleep(1)

update_post(345570752, "2026-07-24T17:30:00+02:00", cap_fb29,
            [{"network": "facebook"}], [REEL2])
time.sleep(1)

update_post(345570753, "2026-07-24T18:00:00+02:00", cap_threads29,
            [{"network": "threads"}], [REEL2])
time.sleep(1)

update_post(345570754, "2026-07-24T16:30:00+02:00", cap_bs29,
            [{"network": "bluesky"}], [REEL2])
time.sleep(1)

update_post(345570854, "2026-07-24T17:15:00+02:00", cap_pin29,
            [{"network": "pinterest"}], [img("1000106601_v3.png")],
            {"pinterestData": {"boardId": BOARD,
                               "pinTitle": "Comprar libros vs leer libros — la distincion mas honesta",
                               "pinLink": "https://davidportodiaz.com"}})
time.sleep(1)


# ─────────────────────────────────────────────────────────────
# PIEZA 30 — Jul 25 mañana — CARRUSEL dualidad
# ─────────────────────────────────────────────────────────────
print("\n=== PIEZA 30 — Jul 25 mañana CARRUSEL dualidad ===")
SLIDES30 = [
    img("dualidad_00_portada.png"),
    img("dualidad_01_teoria.png"),
    img("dualidad_02_realidad.png"),
    img("dualidad_03_verdad.png"),
    img("dualidad_cta.png"),
]

cap_tt30 = (
    "La lectora que soy en teoria vs la que soy en realidad.\n"
    "Desliza. Te veo.\n"
    "#bookstagram #lectores #libros #booktokespanol #readingcommunity"
)
cap_ig30 = (
    "La lectora que soy en teoria vs la que soy en realidad.\n\n"
    "En teoria: orden, planificacion, pila respetada.\n"
    "En realidad: las 3am, otro libro sin terminar el anterior, "
    "ningun arrepentimiento.\n\n"
    "Desliza hasta el final.\n\n"
    "Guarda para enviarselo a tu complice de lecturas "
    "· Comenta tu realidad en una frase\n\n"
    "#bookstagram #libros #lectores #booklovers "
    "#diariodeunlector #librosenespanol #readingcommunity "
    "#bookstagramespa #leoporquequiero"
)
cap_fb30 = (
    "La lectora en teoria vs la lectora en realidad.\n\n"
    "Desliza. Y comenta si la realidad gana siempre.\n\n"
    "#libros #lectores #bookstagram"
)
cap_threads30 = (
    "La lectora que soy en teoria: orden, planificacion, pila respetada. "
    "La lectora que soy en realidad: las 3am, capitulo numero X, ningun arrepentimiento. "
    "Desliza."
)
cap_bs30 = (
    "Yo en teoria: lectora ordenada, pila respetada.\n"
    "Yo en realidad: las 3am, sin remordimiento.\n"
    "#bookstagram #lectores #libros"
)
cap_pin30 = (
    "La lectora en teoria vs en realidad — las dos coexisten y las dos somos | "
    "Dualidad lectora para compartir con tu complice | Guarda si te ves aqui"
)

update_post(345570755, "2026-07-25T08:00:00+02:00", cap_tt30,
            [{"network": "tiktok"}], [img("dualidad_01_teoria.png")],
            {"tiktokData": {"title": "La lectora en teoria vs en realidad."}})
time.sleep(1)

update_post(345570847, "2026-07-25T09:00:00+02:00", cap_ig30,
            [{"network": "instagram"}], SLIDES30)
time.sleep(1)

update_post(345570758, "2026-07-25T09:30:00+02:00", cap_fb30,
            [{"network": "facebook"}], SLIDES30)
time.sleep(1)

update_post(345570759, "2026-07-25T10:00:00+02:00", cap_threads30,
            [{"network": "threads"}], [img("dualidad_00_portada.png")])
time.sleep(1)

update_post(345570760, "2026-07-25T08:30:00+02:00", cap_bs30,
            [{"network": "bluesky"}], [img("dualidad_00_portada.png")])
time.sleep(1)

update_post(345570855, "2026-07-25T09:15:00+02:00", cap_pin30,
            [{"network": "pinterest"}], SLIDES30[:4],
            {"pinterestData": {"boardId": BOARD,
                               "pinTitle": "La lectora en teoria vs en realidad — dualidad lectora",
                               "pinLink": "https://davidportodiaz.com"}})
time.sleep(1)


# ─────────────────────────────────────────────────────────────
# PIEZA 31 — Jul 25 tarde — REEL emocional
# ─────────────────────────────────────────────────────────────
print("\n=== PIEZA 31 — Jul 25 tarde REEL emocional ===")
REEL3 = vid("reel_emocional_jul25.mp4")
TITLE3 = "Hay libros que te encuentran. Y ya no puedes volver al que eras."

cap_tt31 = (
    "Hay libros que te encuentran. No los eliges tu.\n"
    "Y ya no puedes volver al que eras antes de leerlos.\n"
    "#frasesdelibros #libros #literatura #booktokespanol #lectura"
)
cap_ig31 = (
    "Hay libros que te encuentran.\n\n"
    "No los buscas. Aparecen cuando algo en ti\n"
    "necesita ser dicho por alguien que no eres tu.\n\n"
    "Y ya no puedes volver al que eras antes de leerlo.\n\n"
    "A quien le mandas esto sin escribir nada mas?\n\n"
    "Guarda para releerlo cuando lo necesites\n\n"
    "#frasesdelibros #literatura #libros #lectura #librosenespanol "
    "#citasliterarias #reflexion #frasesprofundas #bookstagram"
)
cap_fb31 = (
    "Hay libros que te encuentran cuando algo en ti necesita ser dicho "
    "por alguien que no eres tu.\n\n"
    "Y ya no puedes volver al que eras antes de leerlo.\n\n"
    "A quien le mandas esto?\n\n#libros #literatura #frasesliterarias"
)
cap_threads31 = (
    "Hay libros que te encuentran. No los eliges tu — aparecen. "
    "Y cuando los lees, algo en ti se dice en voz alta "
    "por primera vez. Ya no puedes volver al que eras antes."
)
cap_bs31 = (
    "Hay libros que te encuentran.\n"
    "Y ya no puedes volver al que eras antes de leerlos.\n"
    "#literatura #libros #frasesliterarias"
)
cap_pin31 = (
    "Los libros que te encuentran — no los buscas, aparecen | "
    "Ya no puedes volver al que eras antes | Guarda si ha pasado alguna vez"
)

update_post(345570761, "2026-07-25T15:00:00+02:00", cap_tt31,
            [{"network": "tiktok"}], [REEL3],
            {"tiktokData": {"title": TITLE3}})
time.sleep(1)

update_post(345570773, "2026-07-25T16:00:00+02:00", cap_ig31,
            [{"network": "instagram"}], [REEL3],
            {"instagramData": {"type": "REEL"}})
time.sleep(1)

update_post(345570776, "2026-07-25T16:30:00+02:00", cap_fb31,
            [{"network": "facebook"}], [REEL3])
time.sleep(1)

update_post(345570777, "2026-07-25T17:00:00+02:00", cap_threads31,
            [{"network": "threads"}], [REEL3])
time.sleep(1)

update_post(345570778, "2026-07-25T15:30:00+02:00", cap_bs31,
            [{"network": "bluesky"}], [REEL3])
time.sleep(1)

update_post(345570857, "2026-07-25T16:15:00+02:00", cap_pin31,
            [{"network": "pinterest"}], [img("1000106610_v3.png")],
            {"pinterestData": {"boardId": BOARD,
                               "pinTitle": "Los libros que te encuentran — ya no puedes volver",
                               "pinLink": "https://davidportodiaz.com"}})

print("\n=== TODOS LOS POSTS ACTUALIZADOS ===")
