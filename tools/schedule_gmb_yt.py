"""
Programa Google Business (1/semana) y YouTube Shorts (3/semana) para todo julio.
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
BASE = "https://davidpd89.github.io/rrss-davidporto-media/videos"

def create(date, info):
    r = call_tool("createScheduledPost",{"blogId":BLOG_ID,"date":date,"info":json.dumps(info,ensure_ascii=False)})
    text = r["content"][0]["text"] if r.get("content") else ""
    if r.get("isError"): return f"ERR:{text[:60]}"
    try: return f"OK id={json.loads(text).get('data',{}).get('id','?')}"
    except: return "OK"

# =====================================================
# GOOGLE BUSINESS — 1 post/semana, contenido real
# Tipo Update: actividad real del autor
# =====================================================
print("=== GOOGLE BUSINESS ===")
GMB_POSTS = [
    ("2026-07-03T10:00:00+02:00",
     "El primer capítulo de Samuel entre mundos es gratuito. Lee cómo empieza esta historia de fantasía juvenil española en davidportodiaz.com",
     "https://davidportodiaz.com"),
    ("2026-07-10T10:00:00+02:00",
     "Samuel entre mundos ya disponible para leer. Fantasía juvenil española, sin elegido clásico ni magia sin consecuencias. Más información en la web.",
     "https://davidportodiaz.com/samuel-entre-mundos"),
    ("2026-07-17T10:00:00+02:00",
     "Siguiendo el proyecto de Samuel entre mundos en redes sociales. El primer capítulo gratis sigue disponible para cualquier lector interesado en fantasía española.",
     "https://davidportodiaz.com"),
    ("2026-07-24T10:00:00+02:00",
     "David Porto Díaz, escritor de fantasía juvenil española. Samuel entre mundos publicado en 2026. Capítulo gratuito disponible en davidportodiaz.com",
     "https://davidportodiaz.com"),
]
for date, text, url in GMB_POSTS:
    info = {
        "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
        "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
        "providers": [{"network": "gmb"}],
        "text": text, "media": [],
        "publicationDate": {"dateTime": date[:19], "timezone": "Europe/Madrid"},
        "gmbData": {"callToAction": {"actionType": "LEARN_MORE", "url": url}}
    }
    print(f"  {date[5:10]}: {create(date, info)}")

# =====================================================
# YOUTUBE SHORTS — 3/semana, reutilizar reels existentes
# =====================================================
print("\n=== YOUTUBE SHORTS ===")
# Mapeo: (fecha, hora, url, título SEO, descripción)
YT_SHORTS = [
    # Semana Jul 3-9 (jue, sab, lun)
    ("2026-07-03T18:00:00+02:00", f"{BASE}/DP-F0-052-resistes-de-pie/reel.mp4",
     "Cuando solo ganas seguir de pie — fantasía juvenil", "¿Cuánto tiempo llevas aguantando? #fantasiajuvenil #librosenespañol"),
    ("2026-07-05T12:00:00+02:00", f"{BASE}/DP-F0-069-uno-mas-era-mentira/reel.mp4",
     "Un capítulo más a las 3 de la madrugada — lectores", "¿Cuál fue tu noche más larga leyendo? #booktok #lectores"),
    ("2026-07-07T18:00:00+02:00", f"{BASE}/DP-F0-054-libros-que-avisan/reel.mp4",
     "Los libros que te avisan antes de que lleguen — recomendaciones", "¿Qué libro te dejó sin dormir? #librosenespañol #booktok"),
    # Semana Jul 10-16 (jue, sab, lun)
    ("2026-07-10T18:00:00+02:00", f"{BASE}/DP-F0-070-kindle-con-polvo/reel.mp4",
     "El Kindle con polvo — lector honesto", "Nueve meses y ahí está. ¿El tuyo también? #lectoresreales #librosenespañol"),
    ("2026-07-12T12:00:00+02:00", f"{BASE}/DP-F0-056-dragon-guardian/reel.mp4",
     "Hasta los dragones necesitan algo que leer — fantasía", "¿Qué leería un dragón? #fantasiaespañola #librosfantasia"),
    ("2026-07-14T18:00:00+02:00", f"{BASE}/DP-F0-055-piscina-verano/reel.mp4",
     "Leyendo en la piscina — plan perfecto de verano", "¿Cuál es tu plan perfecto de verano? #librosdeverano #leer"),
    # Semana Jul 17-23 (jue, sab, lun)
    ("2026-07-17T18:00:00+02:00", f"{BASE}/DP-F0-075-se-me-fue-el-bus/reel.mp4",
     "Se me fue el bus por leer — lector sin excusas", "¿A qué llegas tarde tú? #lectoresreales #cosasdelectores"),
    ("2026-07-19T12:00:00+02:00", f"{BASE}/DP-F0-071-resaca-libro/reel.mp4",
     "Resaca de libro — cuando cierras el libro pero sigues dentro", "¿Qué libro te dejó así? #booktok #librosenespañol"),
    ("2026-07-21T18:00:00+02:00", f"{BASE}/DP-F0-076-capitulos-que-no-terminas/reel.mp4",
     "Hay capítulos que no terminas — los cierras", "¿Cuál fue el tuyo? #lectores #librosqueamo"),
    # Semana Jul 24-30 (jue, sab, lun)
    ("2026-07-24T18:00:00+02:00", f"{BASE}/DP-F0-073-enemies-to-lovers/reel.mp4",
     "Si se odian demasiado, ya sospecho — romantasy", "¿Qué enemies to lovers te tuvo así? #romantasy #booktok"),
    ("2026-07-26T12:00:00+02:00", f"{BASE}/DP-F0-077-libro-ya-vivio/reel_v3.mp4",
     "Este libro ya vivió — libros de segunda mano con historia", "¿Abrirías la nota? #librosusados #instalibros"),
    ("2026-07-28T18:00:00+02:00", f"{BASE}/DP-F0-081-misma-escena/reel_v2.mp4",
     "La leí veinte veces — la misma escena", "¿Cuál es la tuya? #lectoresreales #librosqueamo"),
]

for date, url, title, desc in YT_SHORTS:
    info = {
        "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
        "hasNotReadNotes": False, "shortener": False, "smartLinkData": {"ids": []},
        "providers": [{"network": "youtube"}],
        "text": desc, "media": [url],
        "publicationDate": {"dateTime": date[:19], "timezone": "Europe/Madrid"},
        "youtubeData": {"title": title, "audience": "NOT_MADE_FOR_KIDS", "type": "SHORT"}
    }
    result = create(date, info)
    print(f"  {date[5:10]}: {result} | {title[:50]}")

print("\nListo.")
