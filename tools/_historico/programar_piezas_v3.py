"""
Programa las 5 piezas de las imagenes _v3 en Metricool.
Jul 23 (1 pieza) + Jul 24 (2 piezas) + Jul 25 (2 piezas).
Excluye YouTube y Google Business segun instruccion de David.

Redes por defecto para imagen/foto:
  TikTok · Instagram · Facebook · Threads · Bluesky · Pinterest

Horarios diseñados con variedad real:
  Jul 23: manana (10:00-12:00) — ya hay pieza 26 en tarde (19:00-21:30)
  Jul 24: manana (09:00-11:00) + tarde (16:00-18:00)
  Jul 25: manana (08:00-10:00) + tarde (15:00-17:30)
"""
import sys
import json
sys.stdout.reconfigure(encoding="utf-8")

import os
os.chdir(r"C:\GIT\RRSS_DavidPorto\tools")
from metricool_client import call_tool

BLOG_ID = "6435452"
TZ = "Europe/Madrid"
BASE = "https://davidportodiaz.com/assets/"

def img(name):
    return BASE + name

def post(date_str, text, networks_providers, media_list, networks_data=None):
    """
    date_str: ISO con offset, ej '2026-07-23T10:00:00+02:00'
    networks_providers: lista de dicts [{"network": "tiktok"}, ...]
    media_list: lista de URLs
    networks_data: dict con campos especificos de red (tiktokData, instagramData, etc.)
    """
    info = {
        "text": text,
        "providers": networks_providers,
        "media": media_list,
        "publicationDate": {"dateTime": date_str[:19], "timezone": TZ},
        "descendants": [],
    }
    if networks_data:
        info.update(networks_data)

    r = call_tool("createScheduledPost", {
        "date": date_str,
        "blogId": BLOG_ID,
        "info": json.dumps(info),
    })
    if isinstance(r, dict):
        content = r.get("content", [])
        text_out = content[0].get("text", "{}") if content else "{}"
    else:
        text_out = str(r)

    is_error = isinstance(r, dict) and r.get("isError", False)
    if is_error:
        print(f"  ERROR: {text_out[:120]}", flush=True)
        return None

    try:
        result = json.loads(text_out)
        pid = result.get("id") or (result.get("data") or {}).get("id")
        return pid
    except Exception:
        print(f"  PARSE ERROR: {text_out[:120]}", flush=True)
        return None

def log(net, date, pid):
    status = f"id={pid}" if pid else "FAIL"
    print(f"  {net:12} {date[11:16]} -> {status}", flush=True)

# =====================================================================
# PIEZA 27 — Jul 23 mañana
# Imagen: 1000106609_v3.png (editorial bookstore B&W)
# Tema: identificacion lectora / "entro solo a mirar"
# Hashtags grupo 2 (bookstagram/humor lector) — rotan respecto a pieza 26
# =====================================================================
print("\n=== PIEZA 27 — Jul 23 editorial bookstore ===")

cap27_ig = (
    "Entro 'solo a mirar'.\n\n"
    "Nunca ha sido verdad, ni una sola vez.\n\n"
    "¿Cuánto tardas tú en soltar la promesa de que no compras nada?\n\n"
    "Guarda si te ha pasado · Comparte con quien también miente 👇\n\n"
    "#bookstagram #libros #lectores #librosenespañol #lectura "
    "#bookstagramers #booklovers #librosaddict #leoporquequiero"
)
cap27_tiktok_title = "Entro 'solo a mirar'. Nunca ha sido verdad."
cap27_tiktok = (
    "Entro 'solo a mirar'. Salgo con dos libros que no buscaba.\n"
    "¿A ti también? Comenta tu marca personal 👇\n"
    "#bookstagram #lectores #libros #booktokespañol #librosenespañol"
)
cap27_fb = (
    "Entro a la librería 'solo a mirar'. Siempre miento.\n\n"
    "¿Cuánto tardas en rendirte? Cuéntamelo en comentarios 👇\n\n"
    "#libros #lectores"
)
cap27_threads = (
    "Entro 'solo a mirar'. Salgo con tres libros y la culpa feliz "
    "del que sabe exactamente lo que ha hecho. "
    "¿Cuánto te ha durado la promesa hoy?"
)
cap27_bluesky = (
    "Entro 'solo a mirar'. Siempre miento.\n"
    "¿Cuánto te ha durado la promesa?\n"
    "#bookstagram #libros #lectores"
)
cap27_pinterest = (
    "La librería solo a mirar — cada vez el mismo cuento | "
    "La experiencia lectora más honesta | Guarda si te ha pasado"
)

# TikTok 10:00
pid = post("2026-07-23T10:00:00+02:00", cap27_tiktok,
           [{"network": "tiktok"}],
           [img("1000106609_v3.png")],
           {"tiktokData": {"title": cap27_tiktok_title}})
log("TikTok", "2026-07-23T10:00", pid)

# Instagram 11:00
pid = post("2026-07-23T11:00:00+02:00", cap27_ig,
           [{"network": "instagram"}],
           [img("1000106609_v3.png")],
           {"instagramData": {"type": "IMAGE"}})
log("Instagram", "2026-07-23T11:00", pid)

# Facebook 11:30
pid = post("2026-07-23T11:30:00+02:00", cap27_fb,
           [{"network": "facebook"}],
           [img("1000106609_v3.png")])
log("Facebook", "2026-07-23T11:30", pid)

# Threads 12:00
pid = post("2026-07-23T12:00:00+02:00", cap27_threads,
           [{"network": "threads"}],
           [img("1000106609_v3.png")])
log("Threads", "2026-07-23T12:00", pid)

# Bluesky 10:30
pid = post("2026-07-23T10:30:00+02:00", cap27_bluesky,
           [{"network": "bluesky"}],
           [img("1000106609_v3.png")])
log("Bluesky", "2026-07-23T10:30", pid)

# Pinterest 11:45
pid = post("2026-07-23T11:45:00+02:00", cap27_pinterest,
           [{"network": "pinterest"}],
           [img("1000106609_v3.png")],
           {"pinterestData": {"boardId": "1096626646706067804",
                              "title": "Entro solo a mirar — la librería y sus mentiras"}})
log("Pinterest", "2026-07-23T11:45", pid)

# =====================================================================
# PIEZA 28 — Jul 24 mañana — Carrusel 3 slides
# Slides: 1000106605_v3 (Kafka/Dostoevsky escritores) + 1000106610_v3 (acantilado/amor) + CTA
# Tema: dualidades literarias / frases que duelen
# Hashtags grupo 1 (frases de libros) + grupo 3 (frases profundas)
# =====================================================================
print("\n=== PIEZA 28 — Jul 24 carrusel escritores ===")

cap28_ig = (
    "Hay escritores que te consuelan.\nY escritores que te rompen el cómodo.\n\n"
    "¿Cuál necesitas más hoy?\n\n"
    "Guarda para cuando necesites elegir · Comparte con alguien que lo entienda 👇\n\n"
    "#frasesdelibros #literatura #libros #escritores #citasliterarias "
    "#frasesprofundas #reflexion #lectura #librosenespañol"
)
cap28_tiktok_title = "Escritores que consuelan vs escritores que rompen."
cap28_tiktok = (
    "Hay escritores que te consuelan. Y otros que te rompen el cómodo.\n"
    "¿Cuál necesitas más hoy? Comenta 👇\n"
    "#frasesdelibros #literatura #escritores #booktokespañol #citasliterarias"
)
cap28_fb = (
    "Hay escritores que te consuelan y escritores que te incomodan.\n"
    "Los dos son necesarios.\n\n¿Cuál necesitas más hoy?\n\n#literatura #frases"
)
cap28_threads = (
    "Hay escritores que te consuelan. Y otros que te rompen el cómodo. "
    "Los dos son necesarios, pero no siempre en el mismo momento. ¿Cuál necesitas hoy?"
)
cap28_bluesky = (
    "Escritores que consuelan vs escritores que incomodan.\n"
    "¿Cuál lees cuando necesitas romperte un poco?\n"
    "#literatura #frasesdelibros #lectura"
)
cap28_pinterest = (
    "Escritores que consuelan vs escritores que rompen | "
    "Dualidades literarias para lectores con criterio | "
    "Guarda si los dos te son necesarios"
)

slides_28 = [
    img("1000106605_v3.png"),
    img("1000106610_v3.png"),
    img("cta_final.png"),
]

# Instagram carrusel 09:00
pid = post("2026-07-24T09:00:00+02:00", cap28_ig,
           [{"network": "instagram"}],
           slides_28)
log("Instagram", "2026-07-24T09:00", pid)

# Facebook 09:30
pid = post("2026-07-24T09:30:00+02:00", cap28_fb,
           [{"network": "facebook"}],
           slides_28)
log("Facebook", "2026-07-24T09:30", pid)

# TikTok (solo primer slide como foto) 08:00
pid = post("2026-07-24T08:00:00+02:00", cap28_tiktok,
           [{"network": "tiktok"}],
           [img("1000106605_v3.png")],
           {"tiktokData": {"title": cap28_tiktok_title}})
log("TikTok", "2026-07-24T08:00", pid)

# Threads 09:45
pid = post("2026-07-24T09:45:00+02:00", cap28_threads,
           [{"network": "threads"}],
           [img("1000106605_v3.png")])
log("Threads", "2026-07-24T09:45", pid)

# Bluesky 08:30
pid = post("2026-07-24T08:30:00+02:00", cap28_bluesky,
           [{"network": "bluesky"}],
           [img("1000106605_v3.png")])
log("Bluesky", "2026-07-24T08:30", pid)

# Pinterest 09:15 (carrusel)
pid = post("2026-07-24T09:15:00+02:00", cap28_pinterest,
           [{"network": "pinterest"}],
           slides_28,
           {"pinterestData": {"boardId": "1096626646706067804",
                              "title": "Escritores que consuelan vs que rompen — dualidades literarias"}})
log("Pinterest", "2026-07-24T09:15", pid)

# =====================================================================
# PIEZA 29 — Jul 24 tarde — Imagen humor lector
# Imagen: 1000106601_v3.png (mujer con libro meme / BookTok)
# Tema: bookstagram humor — pila de pendientes / comprar vs leer
# Hashtags grupo 2 (bookstagram/humor)
# =====================================================================
print("\n=== PIEZA 29 — Jul 24 tarde humor lector ===")

cap29_ig = (
    "Comprar libros y leer libros son aficiones distintas.\n\n"
    "No pienso pedir perdón por ello.\n\n"
    "¿Cuántos tienes en la pila de los 'lo leo cuando pueda'? "
    "Cuéntalo en comentarios sin mentirte 👇\n\n"
    "Guarda si te defines aquí · Comparte con tu cómplice de pendientes\n\n"
    "#bookstagram #libros #lectores #librosenespañol #bookaddicted "
    "#leoporquequiero #diariodeunlector #bookstagramespaña #readingcommunity"
)
cap29_tiktok_title = "Comprar libros y leer libros son aficiones distintas."
cap29_tiktok = (
    "Comprar libros y leer libros son aficiones distintas. "
    "No pienso pedir perdón.\n"
    "¿Cuántos en tu pila de pendientes? Comenta sin mentirte 👇\n"
    "#bookstagram #lectores #libros #booktokespañol #bookaddicted"
)
cap29_fb = (
    "Comprar libros y leer libros son aficiones distintas.\n\n"
    "No pienso pedir perdón.\n\n"
    "¿Cuántos llevas en la pila de los que 'ya leeré'? #libros #lectores"
)
cap29_threads = (
    "Comprar libros y leer libros son aficiones distintas. "
    "No pienso pedir perdón por ello. "
    "¿Cuántos tienes en la pila de los que 'ya leeré cuando tenga tiempo'?"
)
cap29_bluesky = (
    "Comprar libros y leer libros son aficiones distintas.\n"
    "No pienso pedir perdón.\n"
    "¿Cuántos en tu pila de pendientes?\n"
    "#bookstagram #libros #lectores"
)
cap29_pinterest = (
    "Comprar libros vs leer libros — dos aficiones distintas | "
    "La pila de pendientes que nunca para de crecer | "
    "Guarda si eres de los que no pide perdón"
)

# TikTok 16:00
pid = post("2026-07-24T16:00:00+02:00", cap29_tiktok,
           [{"network": "tiktok"}],
           [img("1000106601_v3.png")],
           {"tiktokData": {"title": cap29_tiktok_title}})
log("TikTok", "2026-07-24T16:00", pid)

# Instagram 17:00
pid = post("2026-07-24T17:00:00+02:00", cap29_ig,
           [{"network": "instagram"}],
           [img("1000106601_v3.png")],
           {"instagramData": {"type": "IMAGE"}})
log("Instagram", "2026-07-24T17:00", pid)

# Facebook 17:30
pid = post("2026-07-24T17:30:00+02:00", cap29_fb,
           [{"network": "facebook"}],
           [img("1000106601_v3.png")])
log("Facebook", "2026-07-24T17:30", pid)

# Threads 18:00
pid = post("2026-07-24T18:00:00+02:00", cap29_threads,
           [{"network": "threads"}],
           [img("1000106601_v3.png")])
log("Threads", "2026-07-24T18:00", pid)

# Bluesky 16:30
pid = post("2026-07-24T16:30:00+02:00", cap29_bluesky,
           [{"network": "bluesky"}],
           [img("1000106601_v3.png")])
log("Bluesky", "2026-07-24T16:30", pid)

# Pinterest 17:15
pid = post("2026-07-24T17:15:00+02:00", cap29_pinterest,
           [{"network": "pinterest"}],
           [img("1000106601_v3.png")],
           {"pinterestData": {"boardId": "1096626646706067804",
                              "title": "Comprar libros vs leer libros — la distinción más honesta"}})
log("Pinterest", "2026-07-24T17:15", pid)

# =====================================================================
# PIEZA 30 — Jul 25 mañana — Imagen emocional
# Imagen: 1000106608_v3.png (Mafalda-style / face-down emocional)
# Tema: autoironia / introspección / frases que duelen
# Hashtags grupo 3 (frases que duelen / introspección)
# =====================================================================
print("\n=== PIEZA 30 — Jul 25 mañana emocional ===")

cap30_ig = (
    "Sentirme mal por haberle hecho sentir mal "
    "al que me hizo sentir mal primero.\n\n"
    "El ciclo más agotador que conozco.\n\n"
    "¿A quién le mandas esto? 👇\n\n"
    "Guarda para releerlo cuando lo necesites · Comparte si te ha pasado\n\n"
    "#frasesprofundas #reflexion #reflexiones #frasesparareflexionar "
    "#amorpropio #nostalgia #frasesdevida #frasesdelalma #pensamientosprofundos"
)
cap30_tiktok_title = "El ciclo más agotador: sentirme mal por haberle hecho sentir mal."
cap30_tiktok = (
    "Sentirme mal por haberle hecho sentir mal al que me hizo sentir mal primero.\n"
    "El ciclo más agotador. ¿A quién se lo mandas? 👇\n"
    "#frasesprofundas #reflexion #amorpropio #booktokespañol #frasesdevida"
)
cap30_fb = (
    "Sentirme mal por haberle hecho sentir mal al que me hizo sentir mal primero.\n\n"
    "El ciclo más agotador que conozco. ¿Te ha pasado?\n\n"
    "#reflexion #frasesprofundas #amorpropio"
)
cap30_threads = (
    "Sentirme mal por haberle hecho sentir mal al que me hizo sentir mal primero. "
    "El ciclo más agotador que conozco. "
    "¿A quién se lo mandas sin que sepa que eres tú?"
)
cap30_bluesky = (
    "Sentirme mal por haberle hecho sentir mal al que me hizo sentir mal primero.\n"
    "El ciclo más agotador.\n"
    "#reflexion #frasesprofundas #amorpropio"
)
cap30_pinterest = (
    "El ciclo más agotador que conozco — para quien también lo ha vivido | "
    "Introspección sin filtro | Guarda si necesitas verlo escrito para entenderlo"
)

# TikTok 08:00
pid = post("2026-07-25T08:00:00+02:00", cap30_tiktok,
           [{"network": "tiktok"}],
           [img("1000106608_v3.png")],
           {"tiktokData": {"title": cap30_tiktok_title}})
log("TikTok", "2026-07-25T08:00", pid)

# Instagram 09:00
pid = post("2026-07-25T09:00:00+02:00", cap30_ig,
           [{"network": "instagram"}],
           [img("1000106608_v3.png")],
           {"instagramData": {"type": "IMAGE"}})
log("Instagram", "2026-07-25T09:00", pid)

# Facebook 09:30
pid = post("2026-07-25T09:30:00+02:00", cap30_fb,
           [{"network": "facebook"}],
           [img("1000106608_v3.png")])
log("Facebook", "2026-07-25T09:30", pid)

# Threads 10:00
pid = post("2026-07-25T10:00:00+02:00", cap30_threads,
           [{"network": "threads"}],
           [img("1000106608_v3.png")])
log("Threads", "2026-07-25T10:00", pid)

# Bluesky 08:30
pid = post("2026-07-25T08:30:00+02:00", cap30_bluesky,
           [{"network": "bluesky"}],
           [img("1000106608_v3.png")])
log("Bluesky", "2026-07-25T08:30", pid)

# Pinterest 09:15
pid = post("2026-07-25T09:15:00+02:00", cap30_pinterest,
           [{"network": "pinterest"}],
           [img("1000106608_v3.png")],
           {"pinterestData": {"boardId": "1096626646706067804",
                              "title": "El ciclo más agotador — introspección para lectores"}})
log("Pinterest", "2026-07-25T09:15", pid)

# =====================================================================
# PIEZA 31 — Jul 25 tarde — Carrusel dualidad/caos
# Slides: 1000106606_v3 (dos mujeres/orden-caos) + 1000106602_v3 (muñeca/humor)
# + CTA slide
# Tema: dualidad de personalidad lectora / humor bookstagram
# Hashtags: grupo 2 (bookstagram/humor) + grupo 3 (frases profundas)
# =====================================================================
print("\n=== PIEZA 31 — Jul 25 tarde dualidad ===")

cap31_ig = (
    "La planificadora de lecturas que soy en teoría "
    "vs la lectora caótica que soy en realidad.\n\n"
    "¿Cuál de las dos reconoces?\n\n"
    "Guarda si eres las dos · Comparte con tu alter ego lector 👇\n\n"
    "#bookstagram #libros #lectores #librosenespañol #bookaddicted "
    "#booklovers #readingcommunity #diariodeunlector #leoporquequiero"
)
cap31_tiktok_title = "La planificadora vs la lectora caótica. ¿Cuál eres tú?"
cap31_tiktok = (
    "La planificadora de lecturas que soy en teoría "
    "vs la lectora caótica que soy en realidad.\n"
    "¿Cuál eres tú? Comenta sin mentirte 👇\n"
    "#bookstagram #lectores #libros #booktokespañol #readingcommunity"
)
cap31_fb = (
    "La planificadora de lecturas que soy en teoría "
    "vs la lectora caótica que soy en realidad.\n\n"
    "¿Cuál reconoces? Cuéntamelo 👇\n\n"
    "#libros #lectores #bookstagram"
)
cap31_threads = (
    "La planificadora de lecturas que soy en teoría "
    "vs la lectora caótica que soy en realidad. "
    "¿Cuál de las dos gana en tu casa?"
)
cap31_bluesky = (
    "La planificadora vs la lectora caótica.\n"
    "¿Cuál de las dos reconoces?\n"
    "#bookstagram #libros #lectores"
)
cap31_pinterest = (
    "La planificadora lectora vs la caótica — las dos coexisten | "
    "Dualidades del mundo lector | Guarda si eres las dos a la vez"
)

slides_31 = [
    img("1000106606_v3.png"),
    img("1000106602_v3.png"),
    img("cta_final.png"),
]

# TikTok 15:00
pid = post("2026-07-25T15:00:00+02:00", cap31_tiktok,
           [{"network": "tiktok"}],
           [img("1000106606_v3.png")],
           {"tiktokData": {"title": cap31_tiktok_title}})
log("TikTok", "2026-07-25T15:00", pid)

# Instagram 16:00
pid = post("2026-07-25T16:00:00+02:00", cap31_ig,
           [{"network": "instagram"}],
           slides_31)
log("Instagram", "2026-07-25T16:00", pid)

# Facebook 16:30
pid = post("2026-07-25T16:30:00+02:00", cap31_fb,
           [{"network": "facebook"}],
           slides_31)
log("Facebook", "2026-07-25T16:30", pid)

# Threads 17:00
pid = post("2026-07-25T17:00:00+02:00", cap31_threads,
           [{"network": "threads"}],
           [img("1000106606_v3.png")])
log("Threads", "2026-07-25T17:00", pid)

# Bluesky 15:30
pid = post("2026-07-25T15:30:00+02:00", cap31_bluesky,
           [{"network": "bluesky"}],
           [img("1000106606_v3.png")])
log("Bluesky", "2026-07-25T15:30", pid)

# Pinterest 16:15
pid = post("2026-07-25T16:15:00+02:00", cap31_pinterest,
           [{"network": "pinterest"}],
           slides_31,
           {"pinterestData": {"boardId": "1096626646706067804",
                              "title": "La planificadora vs la lectora caótica — dualidades del mundo lector"}})
log("Pinterest", "2026-07-25T16:15", pid)

print("\n=== TODAS LAS PIEZAS PROGRAMADAS ===")
