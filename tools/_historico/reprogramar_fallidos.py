"""
Reprograma los posts que fallaron en la primera pasada:
- Instagram de piezas 27, 29, 30 (type IMAGE invalido — se omite instagramData)
- Pinterest de piezas 27, 28, 29, 30, 31 (faltaba pinTitle + pinLink)
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
SITE = "https://davidportodiaz.com"

def img(name):
    return BASE + name

def post(date_str, text, networks_providers, media_list, extra=None):
    info = {
        "text": text,
        "providers": networks_providers,
        "media": media_list,
        "publicationDate": {"dateTime": date_str[:19], "timezone": TZ},
        "descendants": [],
    }
    if extra:
        info.update(extra)

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
        print(f"  ERROR: {text_out[:140]}", flush=True)
        return None

    try:
        result = json.loads(text_out)
        pid = result.get("id") or (result.get("data") or {}).get("id")
        return pid
    except Exception:
        print(f"  PARSE ERROR: {text_out[:140]}", flush=True)
        return None

def log(net, date, pid):
    status = f"id={pid}" if pid else "FAIL"
    print(f"  {net:12} {date[11:16]} -> {status}", flush=True)

# =====================================================================
# Instagram piezas 27, 29, 30 — sin instagramData (imagen estatica)
# =====================================================================
print("\n--- INSTAGRAM fallidos (sin instagramData) ---")

cap27_ig = (
    "Entro 'solo a mirar'.\n\n"
    "Nunca ha sido verdad, ni una sola vez.\n\n"
    "¿Cuánto tardas tú en soltar la promesa de que no compras nada?\n\n"
    "Guarda si te ha pasado · Comparte con quien también miente 👇\n\n"
    "#bookstagram #libros #lectores #librosenespañol #lectura "
    "#bookstagramers #booklovers #librosaddict #leoporquequiero"
)
cap29_ig = (
    "Comprar libros y leer libros son aficiones distintas.\n\n"
    "No pienso pedir perdón por ello.\n\n"
    "¿Cuántos tienes en la pila de los 'lo leo cuando pueda'? "
    "Cuéntalo en comentarios sin mentirte 👇\n\n"
    "Guarda si te defines aquí · Comparte con tu cómplice de pendientes\n\n"
    "#bookstagram #libros #lectores #librosenespañol #bookaddicted "
    "#leoporquequiero #diariodeunlector #bookstagramespaña #readingcommunity"
)
cap30_ig = (
    "Sentirme mal por haberle hecho sentir mal "
    "al que me hizo sentir mal primero.\n\n"
    "El ciclo más agotador que conozco.\n\n"
    "¿A quién le mandas esto? 👇\n\n"
    "Guarda para releerlo cuando lo necesites · Comparte si te ha pasado\n\n"
    "#frasesprofundas #reflexion #reflexiones #frasesparareflexionar "
    "#amorpropio #nostalgia #frasesdevida #frasesdelalma #pensamientosprofundos"
)

pid = post("2026-07-23T11:00:00+02:00", cap27_ig,
           [{"network": "instagram"}], [img("1000106609_v3.png")])
log("Instagram27", "2026-07-23T11:00", pid)

pid = post("2026-07-24T17:00:00+02:00", cap29_ig,
           [{"network": "instagram"}], [img("1000106601_v3.png")])
log("Instagram29", "2026-07-24T17:00", pid)

pid = post("2026-07-25T09:00:00+02:00", cap30_ig,
           [{"network": "instagram"}], [img("1000106608_v3.png")])
log("Instagram30", "2026-07-25T09:00", pid)

# =====================================================================
# Pinterest piezas 27-31 — con pinTitle + pinLink obligatorios
# =====================================================================
print("\n--- PINTEREST fallidos (con pinTitle + pinLink) ---")

BOARD = "1096626646706067804"

def pin(board, title, link=SITE):
    return {"pinterestData": {"boardId": board, "pinTitle": title, "pinLink": link}}

# Pieza 27
cap27_pin = (
    "La librería solo a mirar — cada vez el mismo cuento | "
    "La experiencia lectora más honesta | Guarda si te ha pasado"
)
pid = post("2026-07-23T11:45:00+02:00", cap27_pin,
           [{"network": "pinterest"}], [img("1000106609_v3.png")],
           pin(BOARD, "Entro solo a mirar — la librería y sus mentiras"))
log("Pinterest27", "2026-07-23T11:45", pid)

# Pieza 28
cap28_pin = (
    "Escritores que consuelan vs escritores que rompen | "
    "Dualidades literarias para lectores con criterio | "
    "Guarda si los dos te son necesarios"
)
slides_28 = [img("1000106605_v3.png"), img("1000106610_v3.png"), img("cta_final.png")]
pid = post("2026-07-24T09:15:00+02:00", cap28_pin,
           [{"network": "pinterest"}], slides_28,
           pin(BOARD, "Escritores que consuelan vs que rompen — dualidades literarias"))
log("Pinterest28", "2026-07-24T09:15", pid)

# Pieza 29
cap29_pin = (
    "Comprar libros vs leer libros — dos aficiones distintas | "
    "La pila de pendientes que nunca para de crecer | "
    "Guarda si eres de los que no pide perdón"
)
pid = post("2026-07-24T17:15:00+02:00", cap29_pin,
           [{"network": "pinterest"}], [img("1000106601_v3.png")],
           pin(BOARD, "Comprar libros vs leer libros — la distinción más honesta"))
log("Pinterest29", "2026-07-24T17:15", pid)

# Pieza 30
cap30_pin = (
    "El ciclo más agotador que conozco — para quien también lo ha vivido | "
    "Introspección sin filtro | Guarda si necesitas verlo escrito para entenderlo"
)
pid = post("2026-07-25T09:15:00+02:00", cap30_pin,
           [{"network": "pinterest"}], [img("1000106608_v3.png")],
           pin(BOARD, "El ciclo más agotador — introspección para lectores"))
log("Pinterest30", "2026-07-25T09:15", pid)

# Pieza 31
cap31_pin = (
    "La planificadora lectora vs la caótica — las dos coexisten | "
    "Dualidades del mundo lector | Guarda si eres las dos a la vez"
)
slides_31 = [img("1000106606_v3.png"), img("1000106602_v3.png"), img("cta_final.png")]
pid = post("2026-07-25T16:15:00+02:00", cap31_pin,
           [{"network": "pinterest"}], slides_31,
           pin(BOARD, "La planificadora vs la lectora caótica — dualidades del mundo lector"))
log("Pinterest31", "2026-07-25T16:15", pid)

print("\n=== FIN ===")
