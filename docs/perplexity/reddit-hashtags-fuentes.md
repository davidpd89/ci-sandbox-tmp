# Hashtags, fuentes y comunidades en Reddit

Fuente: informe de Perplexity (https://www.perplexity.ai/search/645ea256-d875-4407-a3ab-9747ae5fe85e), generado 10/10/2026.

Informe mejorado — Descubrimiento Reddit para fantasía / romantasy / lectura en español
Resumen

El informe anterior era correcto en la dirección, pero mezclaba repos poco contrastados y proponía piezas que ya están cubiertas por el sistema. Tras revisar davidpd89/ci-sandbox-tmp, la base existente ya incluye reddit_scan.py, reddit_interact.py, reddit_comments.py, reddit_execute.py, reddit_publish.py, reddit_survey.py, además de discovery_terms.py, growth_core.py, score_hook.py, action_ledger.py y check_duplicate_phrase.py; por tanto, no debe añadirse otro scraper general ni otro motor de comentarios. La mejora correcta es un módulo pequeño de fuentes y consultas de descubrimiento que alimente el pipeline Reddit ya existente.

Los repos públicos más útiles y verificables a fecha de hoy son YARS, URS y ScrapiReddit. YARS es ligero y usa endpoints .json sin OAuth; URS es el más maduro y completo, basado en PRAW; ScrapiReddit es el más cercano a una integración limpia porque ofrece búsqueda, paginación, reintentos, caché reanudable y exportación JSON/CSV.
github
+2

Hallazgos verificados
Repositorio / fuente	Estado comprobado	Qué aporta	Decisión para nuestro sistema

datavorous/yars
	Activo; 235 estrellas, 45 forks, rama main, 68 commits. 
github
	Búsqueda global, posts por subreddit con hot/new/top, datos de usuario, detalles de post e imágenes mediante .json; solo requests y Pygments. 
github
	Copiar patrones, no instalar como dependencia: su API es sencilla, pero el propio README advierte de riesgo de bloqueo por IP sin proxies. 
github


JosephLai241/URS
	Muy activo; 1.000 estrellas, 126 forks, 1.360 commits, rama master. 
github
	Scraping/archivado por CLI con PRAW: subreddits, usuarios, comentarios, livestream, frecuencias de palabras y wordclouds. 
github
	Referencia, no dependencia directa: es potente pero demasiado amplio para nuestro caso; copiar ideas de livestream y análisis de vocabulario. 
github


vewaxio/ScrapiReddit
	Activo; 16 estrellas, 7 forks, rama main, 12 commits; Python 3.9+, MIT. 
github
	Búsqueda global o por subreddit, tipos post/comment/sr/user, orden, ventana temporal, comentarios, caché reanudable, backoff y export JSON/CSV. 
github
	Mejor candidato para adaptar: su build_search_target() y ListingTarget encajan casi directamente con un nuevo reddit_discovery_sources.py. 
github


praw-dev/praw
	Mantenido; documentación y quick start vigentes. 
github
+1
	Cliente OAuth estable para búsqueda, listados, comentarios, usuarios y streams. 
github
+1
	Usarlo solo si el sistema ya tiene credenciales Reddit; para descubrimiento pasivo, los endpoints .json son suficientes. 
reddit

Reddit API oficial	Documentación pública vigente.	Listados, búsqueda, paginación after/before, limit, count; búsqueda global y por subreddit.	Base normativa técnica de las consultas; implementar directamente en nuestro adaptador.

Eliminado del informe anterior: mothivenkatesh/reddit-scraper y mdfarhantanvir/Reddit-Scraper. Aportan menos que YARS/URS/ScrapiReddit, tienen menor trazabilidad de actividad y no justifican añadir más dependencias. También elimino abkds/r-ecommender: es un recomendador de subreddits interesante conceptualmente, pero data de 2019 y no está alineado con un pipeline de crecimiento actual.
github
+3

Fuentes Reddit del nicho
Subreddits prioritarios
Comunidad	Prioridad	Motivo	Consultas iniciales
r/libros	Alta	Comunidad en español; ya alberga discusiones sobre fantasía escrita en español.	fantasía, romantasy, fantasía española, lectura actual
r/es_bookclub	Alta	Club de lectura en español; mejor encaje para conversación auténtica.	fantasía, romance, lectura mensual, recomendaciones
r/Fantasy	Alta	Comunidad grande y activa; mantiene hilos diarios de recomendaciones en 2026.	Spanish fantasy, romantasy, fantasy romance, Latin American fantasy
r/fantasybooks	Alta	Lectores específicos de fantasía y recomendaciones.	romantasy, Spanish fantasy, fantasy romance, book stack
r/Romantasy	Alta	Comunidad temática directa del subgénero.	recommendations, tropes, Spanish, translated
r/romancebooks	Media-alta	Romance con fuerte solapamiento con romantasy.	fantasy romance, romantasy, enemies to lovers fantasy
r/suggestmeabook	Media-alta	Peticiones explícitas de recomendación; lenguaje real del lector.	fantasy romance, romantasy, Spanish fantasy, books like
r/YAlit	Media	Fantasía juvenil y lectores jóvenes.	YA fantasy, romantasy YA, Spanish YA fantasy
r/books	Media	Alcance amplio; filtrar con términos específicos.	fantasía española, romantasy, Spanish fantasy author
r/bookclub	Media	Discusiones de lectura comunitaria.	fantasy, romantasy, Spanish language book
Cuentas y perfiles semilla

En Reddit conviene descubrir autores dinámicamente en lugar de mantener una lista fija de cuentas. Los perfiles semilla deben ser patrones, no usernames congelados:

Autores independientes en español que publican portadas, lanzamientos o procesos de escritura en r/libros, r/es_bookclub y r/Fantasy.

Autores de romantasy angloparlantes activos en r/Fantasy, r/Romantasy y r/romancebooks; sirven para detectar tropes, lanzamientos y vocabulario.

Usuarios que abren hilos de “¿qué leo después?”, “recomendaciones de fantasía” o “fantasía en español”.

Usuarios recurrentes en hilos semanales de recomendaciones; en r/Fantasy estos hilos siguen publicándose de forma regular.

Moderadores y creadores de hilos semanales, útiles como nodos de descubrimiento más que como destinatarios automáticos de interacción.

Búsquedas recomendadas

Español — alta prioridad

text
fantasía en español
fantasía española
autores españoles fantasía
novela fantástica español
romantasy español
romantasy en español
fantasía romántica
fantasía juvenil español
libros fantasía recomendación
lectura actual fantasía
fantasía latinoamericana
romance fantasía libros
Laura Gallego
Memorias de Idhún

Inglés — vigilancia de tendencias

text
romantasy
fantasy romance recommendation
YA fantasy romance
Spanish fantasy author
translated fantasy
Latin American fantasy
enemies to lovers fantasy
fantasy book stack

La búsqueda global se realiza contra https://www.reddit.com/search.json; la búsqueda dentro de una comunidad usa https://www.reddit.com/r/{subreddit}/search.json?restrict_sr=1. Ambas admiten q, sort, t, limit y paginación con after.

Código reutilizable
1. Búsqueda, subreddit y usuario con YARS

Este bloque es el ejemplo completo publicado en el README de YARS; sirve como referencia directa para búsqueda, post, usuario y listado por subreddit.
github

python
# https://github.com/datavorous/yars#complete-code-example
from yars import YARS
from utils import display_results, download_image

miner = YARS()

# Search for posts related to "OpenAI"
search_results = miner.search_reddit("OpenAI", limit=3)
display_results(search_results, "SEARCH")

# Scrape post details using its permalink
permalink = "https://www.reddit.com/r/getdisciplined/comments/1frb5ib/what_single_health_test_or_practice_has/".split('reddit.com')[1]

post_details = miner.scrape_post_details(permalink)
if post_details:
    display_results(post_details, "POST DATA")
else:
    print("Failed to scrape post details.")

# Fetch recent activity of user "iamsecb"
user_data = miner.scrape_user_data("iamsecb", limit=2)

display_results(user_data, "USER DATA")

# Fetch top posts from the subreddit "generative" from the past week
subreddit_posts = miner.fetch_subreddit_posts("generative", limit=11, category="top", time_filter="week")
display_results(subreddit_posts, "EarthPorn SUBREDDIT New Posts")

# Download images from the fetched posts
for z in range(3):
    try:
        image_url = subreddit_posts[z]["image_url"]
    except:
        image_url = subreddit_posts[z]["thumbnail_url"]
    download_image(image_url)

Adaptación: sustituir "OpenAI" por las queries en español, "generative" por libros, Fantasy, Romantasy, etc., y eliminar la descarga de imágenes salvo para auditoría visual de portadas.

2. Búsqueda y listados con ScrapiReddit

Este es el patrón más útil para nuestro sistema: define un target de listado y otro de búsqueda, con orden, ventana temporal, comentarios opcionales, caché y export.
github

python
# https://github.com/rodneykeilson/ScrapiReddit#python-api
from pathlib import Path
from scrapi_reddit import build_session
from scrapi_reddit import ScrapeOptions
from scrapi_reddit import ListingTarget, build_search_target, process_listing

session = build_session("your-app-name/0.1", verify=True)

options = ScrapeOptions(
    output_root=Path("./scrapes"),
    listing_limit=250,
    comment_limit=0, # auto-expand to 500
    delay=3.0,
    time_filter="day",
    output_formats={"json", "csv"},
    fetch_comments=True,
    resume=True, # reuse cached JSON/media on reruns
    download_media=True,
    media_filters={"video", ".mp4"},
)

target = ListingTarget(
    label="r/python top (day)",
    output_segments=("subreddits", "python", "top_day"),
    url="https://www.reddit.com/r/python/top/.json",
    params={"t": "day"},
    context="python",
)

process_listing(target, session=session, options=options)

search_target = build_search_target(
    "python asyncio",
    search_types=["comment"],
    sort="new",
    time_filter="day",
)

process_listing(search_target, session=session, options=options)

Adaptación recomendada: usar download_media=False, fetch_comments=False en la primera pasada y search_types=["post"]; los comentarios solo deben recuperarse para los posts que superen el filtro de relevancia.

3. Lectura de comentarios con PRAW

PRAW documenta el acceso a comentarios planos de un submission; es útil solo para analizar en profundidad los pocos posts seleccionados, no para rastrear masivamente.
github

python
# https://github.com/praw-dev/praw/blob/main/docs/getting_started/quick_start.rst
top_level_comments = list(submission.comments)
all_comments = submission.comments.list()

Adaptación: aplicar después de seleccionar un post prometedor; extraer preguntas, tropes, autoras mencionadas y lenguaje de recomendación para alimentar discovery_terms.py y el corpus de respuestas.

Configuración propuesta

Crear config/reddit_discovery.yaml:

text
# config/reddit_discovery.yaml
version: 1
language_priority: ["es", "en"]

subreddits:
  - name: libros
    weight: 1.0
    language: es
  - name: es_bookclub
    weight: 1.0
    language: es
  - name: Fantasy
    weight: 0.9
    language: en
  - name: fantasybooks
    weight: 0.9
    language: en
  - name: Romantasy
    weight: 0.9
    language: en
  - name: romancebooks
    weight: 0.8
    language: en
  - name: suggestmeabook
    weight: 0.8
    language: en
  - name: YAlit
    weight: 0.7
    language: en
  - name: books
    weight: 0.6
    language: en
  - name: bookclub
    weight: 0.6
    language: en

queries_es:
  - "fantasía en español"
  - "fantasía española"
  - "autores españoles fantasía"
  - "romantasy español"
  - "romantasy en español"
  - "fantasía romántica"
  - "fantasía juvenil español"
  - "libros fantasía recomendación"
  - "lectura actual fantasía"
  - "fantasía latinoamericana"

queries_en:
  - "romantasy"
  - "fantasy romance recommendation"
  - "YA fantasy romance"
  - "Spanish fantasy author"
  - "translated fantasy"
  - "Latin American fantasy"
  - "enemies to lovers fantasy"

search:
  global_sort: ["new", "top"]
  subreddit_sort: ["new", "top"]
  time_filter: ["day", "week"]
  limit: 50
  fetch_comments: false
  download_media: false
  delay_seconds: 3.0

relevance:
  required_any_es:
    - "fantas"
    - "romantasy"
    - "romance"
    - "libro"
    - "lectura"
    - "recomendación"
  required_any_en:
    - "fantasy"
    - "romantasy"
    - "romance"
    - "book"
    - "reading"
    - "recommendation"
Integración sin duplicar el sistema
Pieza nueva	Relación con el repo actual
config/reddit_discovery.yaml	Fuente declarativa única de subreddits, queries, pesos y filtros.
tools/reddit_discovery_sources.py	Solo descubre candidatos; delega interacción en reddit_interact.py y publicación en reddit_publish.py.
tools/discovery_terms.py	Recibe las queries y términos extraídos de posts/comentarios; no se sustituye.
tools/reddit_scan.py	Consume los candidatos normalizados; no se duplica su lógica de escaneo.
tools/score_hook.py	Puntúa por subreddit, idioma, antigüedad, engagement y coincidencia temática.
tools/action_ledger.py	Evita repetir la misma URL, autor o comentario.
tools/check_duplicate_phrase.py	Evita frases repetidas en comentarios y publicaciones.
tools/growth_attribution.py	Mide qué subreddit, query o tipo de hilo produce mejores resultados.
Plan de implementación en PR pequeñas
PR	Entregable	Tests
PR 1	config/reddit_discovery.yaml y validador de esquema.	YAML válido; sin subreddits duplicados; queries no vacías; pesos entre 0 y 1.
PR 2	tools/reddit_discovery_sources.py con búsqueda global y por subreddit mediante .json.	Mocks de respuestas; campos id, title, selftext, author, subreddit, permalink, created_utc, score, num_comments.
PR 3	Normalización y deduplicación hacia el pipeline existente.	Misma URL no entra dos veces; autor repetido se marca; candidatos sin idioma/relevancia se descartan.
PR 4	Filtro de español, inglés y relevancia temática.	Casos positivos, negativos, mixtos y posts de alta puntuación pero fuera de nicho.
PR 5	Informe semanal: mejores subreddits, queries, autores y posts.	CSV/Markdown generado; campos obligatorios presentes; totales coherentes.
PR 6	Ampliación mensual de comunidades mediante /subreddits/search.json.	Límite de altas nuevas; descarte de comunidades inactivas o irrelevantes.
Aplicación multired

X, Threads, Bluesky y Mastodon: reutilizar las queries como términos de búsqueda y hashtags; los hilos de Reddit revelan lenguaje y tropes con intención de compra/lectura.

Instagram y TikTok: convertir términos como romantasy, booktok, fantasía juvenil y nombres de autoras en hashtags, sonidos y cuentas semilla.

Facebook: usar subreddits y queries como semillas para localizar grupos y páginas de lectores en español.

Pinterest: transformar queries en búsquedas de tableros, pins y palabras clave visuales.

Reddit: es la fuente principal de intención explícita, porque los lectores piden recomendaciones directamente; ese vocabulario debe alimentar los corpus de comentarios de todas las redes.

Fuentes

Repo espejo inspeccionado: davidpd89/ci-sandbox-tmp; módulos Reddit y herramientas de crecimiento existentes.

YARS — búsqueda, posts, usuarios y subreddits sin OAuth: 
https://github.com/datavorous/yars
github

URS — scraper universal basado en PRAW, con livestream y análisis: 
https://github.com/JosephLai241/URS
github

ScrapiReddit — búsqueda, listados, caché, reintentos y export JSON/CSV: 
https://github.com/rodneykeilson/ScrapiReddit
github

PRAW — quick start y acceso a comentarios: 
https://github.com/praw-dev/praw/blob/main/docs/getting_started/quick_start.rst
github

PRAW — repositorio y ejemplos de uso: 
https://github.com/praw-dev/praw
reddit

Reddit API oficial — listings, búsqueda y paginación: 
https://www.reddit.com/dev/api/

Búsqueda pública JSON de Reddit: https://www.reddit.com/search.json

Tema GitHub reddit-scraper, con 184 repos públicos y URS/YARS destacados: 
https://github.com/topics/reddit-scraper
github

Hilo activo de recomendaciones diarias en r/Fantasy: 
https://www.reddit.com/r/Fantasy/comments/1wjo9s1/rfantasy_daily_recommendations_and_simple/

Hilo en r/libros sobre fantasía escrita en español: 
https://www.reddit.com/r/libros/comments/1kiel4q/libros_de_fantas%C3%ADa_escritos_en_espa%C3%B1ol/
