# Descubrimiento masivo de posts y perfiles del nicho lector en las nueve redes

Fuente: informe de Perplexity (https://www.perplexity.ai/search/09c0ad2d-b7c4-4fe5-aa4e-fd372891f0ce), generado 10/10/2026.

Investigación: descubrimiento masivo de lectores y autores de fantasía/romantasy en español
Resumen

La vía más eficiente no es “escrapear todo”: es construir un pipeline de descubrimiento por capas —semillas de perfiles y comunidades → consultas normalizadas → candidatos → scoring → cola de interacción— con APIs públicas donde existen (Bluesky, Mastodon, Reddit) y fuentes de descubrimiento/observación en las redes cerradas (X, Threads, Facebook, Pinterest, TikTok, Instagram). Bluesky ofrece búsqueda pública y un flujo en vivo filtrable; Mastodon permite buscar estados, cuentas y hashtags; Reddit permite buscar posts, comunidades y usuarios; TikTok Creative Center expone tendencias y hashtags por región e industria.
joinmastodon
+3

Para el nicho de David Porto, el objetivo operativo es alimentar una base discovery_candidates con miles de posts, perfiles, comunidades y hashtags en español, priorizando señales de afinidad real: lectura activa, reseñas, bookstagram/booktok, fandom, escritura, autoedición y conversación sobre fantasía/romantasy.

Hallazgos
Red	Mejor fuente de descubrimiento	Consultas / semillas recomendadas	Herramienta o API aprovechable	Licencia / estado	Parte reutilizable
X	Listas públicas de autores/lectores, búsquedas avanzadas, seguidores de cuentas semilla	"fantasía" (recomiendo OR leo OR reseña) -filter:replies, "romantasy" español, from:autor_semillia, list:usuario/lista	snscrape como referencia de consultas y estructuras; para producción, usar las superficies nativas de X y exportaciones/manuales controlados	snscrape es open source, pero la superficie de X cambia con frecuencia; verificar antes de integrar	Parser de consultas, normalización de tweets, deduplicación y scoring
Threads	Búsqueda interna por palabras clave y hashtags; perfiles derivados de interacciones	#Bookstagram, #Romantasy, #FantasíaJuvenil, lectores de fantasía, autores independientes	No hay API pública madura equivalente; usar descubrimiento asistido y exportación estructurada	Cerrado; evitar dependencia de scrapers frágiles	Modelo común de candidato, plantillas de consulta y scoring
Facebook	Páginas y grupos públicos de lectura, fantasía, romantasy, autoedición y bookstagram	grupos lectura fantasía, romantasy español, autores independientes fantasía, club de lectura romantasy	facebook-pages-scraper para metadatos públicos de páginas y último post; Python 3.11+, MIT 
pypi
	MIT, paquete reciente 
pypi
	Descubrimiento de páginas y último post; no usar como base de interacción automática
Pinterest	Búsqueda de pins, tableros y cuentas de estética literaria	romantasy books, fantasía juvenil libros, book aesthetic español, portadas fantasía, bookstagram	social-media-profile-scrapers incluye módulos de Pinterest, Instagram, X, Reddit y más; verificar licencia y mantenimiento antes de reutilizar 
github
	Repositorio agregador; revisar licencia por módulo	Extractor de pins/tableros como proveedor opcional; adaptador de normalización
Reddit	Subreddits, búsqueda global y búsqueda dentro de comunidades	r/fantasy, r/Fantasy_Writing, r/selfpublish, r/books, r/libros, r/lectores, búsquedas: romantasy español, fantasía juvenil recomendaciones, autor español fantasía	API oficial: búsqueda de posts por subreddit o global, con sort, t, paginación y límite hasta 100; también búsqueda de comunidades y usuarios 
docs.redditapis
+1
	Documentación oficial; usar OAuth oficial	Cliente de búsqueda, ingesta de posts/comentarios, detección de comunidades y usuarios
Bluesky	Búsqueda pública de posts y firehose/Jetstream filtrable	romantasy, fantasía, booktok, bookstagram, lectura fantástica, escritura fantástica, recomendaciones libros	app.bsky.feed.searchPosts público; Jetstream permite suscribirse a app.bsky.feed.post en JSON 
endpoints.bsky
+1
	AT Protocol público; Jetstream es proyecto oficial de Bluesky 
jakelazaroff
	Búsqueda histórica, stream en vivo, filtros por idioma/hashtag y construcción de perfiles
Mastodon	Búsqueda federada por hashtag, estado y cuenta; instancias literarias	#fantasía, #romantasy, #bookstadon, #escritura, #amWriting, #libros, #lectura	API /api/v2/search para cuentas, estados y hashtags; los estados requieren backend Elasticsearch y token autenticado en muchos servidores 
joinmastodon
	API oficial de Mastodon	Cliente multi-instancia, cursor min_id/max_id, ingesta de hashtags y autores
TikTok	Creative Center Trends, hashtags relacionados, comentarios y creadores detectados	#romantasy, #booktok, #booktokenespañol, #fantasíajuvenil, #librosrecomendados, #escritora	TikTok Creative Center muestra hashtags en tendencia, analítica, popularidad regional y hashtags relacionados 
ads.tiktok
+1
	Superficie oficial de tendencias	Exportación manual/semiautomática de hashtags y creadores; enriquecimiento de candidatos
Instagram	Hashtags, exploración, cuentas semilla, seguidores y comentarios de bookstagram	#bookstagram, #bookstagrammer, #romantasy, #fantasíajuvenil, #lectores, #autoresindies, #recomendacionesliterarias	Instaloader, MIT, para metadatos y descarga de contenido público de perfiles 
github
	MIT 
github
	Ingesta de perfiles/captions, detección de hashtags co-ocurrentes y construcción de grafos de afinidad
Repos y fuentes de código reutilizables
Repo / fuente	Licencia	Qué reutilizar	Integración propuesta	Riesgos técnicos	Tests
bluesky-social/jetstream	Proyecto oficial de Bluesky	Consumo JSON del firehose mediante WebSocket; filtrado por wantedCollections, p. ej. app.bsky.feed.post 
jakelazaroff
	Servicio bluesky_stream_worker que guarda posts candidatos en Postgres/SQLite y aplica filtros de idioma, palabras clave y hashtags	Volumen alto; necesitas filtros tempranos, cursor persistente y control de backpressure	Reconexión, cursor, filtrado por lang, deduplicación por URI/CID

ruggsea/bluesky-firehose-py
	Verificar licencia en el repo	Librería/CLI Python para conectar a Jetstream y archivar posts y eventos 
github
	Base para un worker Python 3.11 en Windows; adaptar salida a nuestro esquema social_posts	Mantenimiento y cobertura de eventos pueden ser limitados	Smoke test de conexión, persistencia y reanudación

instaloader/instaloader
	MIT 
github
	Descarga de posts públicos, captions y metadatos de Instagram 
github
	Adaptador instagram_discovery para perfiles semilla y extracción de hashtags/captions	Rate limits, cambios de Instagram y necesidad de sesión para algunas operaciones	Rate limiter, reintentos, parseo de captions y detección de idioma

facebook-pages-scraper
	MIT; Python 3.11+ 
pypi
	Metadatos públicos de páginas y último post sin navegador ni API key 
pypi
	Descubrimiento de páginas y grupos públicos; enriquecer pages y latest_post	Cobertura limitada y fragilidad frente a cambios de Facebook	Test con páginas conocidas, campos vacíos y errores HTTP
Reddit API oficial	Documentación oficial	/subreddits/search, /r/{subreddit}/search, listados hot/new/top/rising, búsqueda de usuarios y comunidades 
reddit
+1
	Adaptador reddit_discovery con colas por subreddit y ventana temporal	OAuth, límites de tasa y cambios de precios/políticas de acceso	Paginación after, rate limit, normalización de posts y comentarios
Mastodon API oficial	Documentación oficial	/api/v2/search para cuentas, estados y hashtags; paginación con min_id y limit 
joinmastodon
	Adaptador mastodon_discovery multi-instancia	La búsqueda completa de estados depende de Elasticsearch y autenticación por instancia 
joinmastodon
	Tests por instancia, token, tipos de búsqueda y cursores
TikTok Creative Center	Superficie oficial	Hashtags en tendencia, analítica, popularidad regional, hashtags relacionados y audiencia 
ads.tiktok
+1
	Fuente de expansión de hashtags y detección de creadores; no sustituye a la observación de posts	No es una API de datos abierta; requiere revisión periódica	Validación de exportaciones y detección de duplicados
OSoMe Mastodon Search	Servicio académico	Búsqueda de estados por palabra clave o hashtag en varias instancias 
osome.iu
	Alternativa de validación cruzada cuando la búsqueda local de una instancia es limitada	Dependencia externa y disponibilidad variable	Contrato de respuesta y comparación con la API nativa
Sistema de consultas del nicho
Núcleo temático

Usa estas familias de consultas en todas las redes, adaptando sintaxis:

romantasy

fantasía juvenil

fantasía épica

alta fantasía

fantasía oscura

booktok

bookstagram

lectura fantástica

recomendaciones fantasía

autores independientes

autoedición fantasía

escritura fantástica

mundos fantásticos

saga de fantasía

novela romantasy

Expansión por intención
Intención	Consultas	Señal de calidad
Lectores activos	leo fantasía, estoy leyendo, recomendadme fantasía, romantasy recomendaciones	Menciona libros, autores o sagas; usa español natural
Reseñistas	reseña fantasía, reseña romantasy, book review español, opinión novela	Publica reseñas, puntuaciones o análisis
Bookstagram / BookTok	#bookstagram, #booktok, #booktokenespañol, #romantasy, #fantasíajuvenil	Contenido visual, hashtags recurrentes y comunidad activa
Autores	mi novela, escribo fantasía, autor independiente, autoedición, WIP fantasía	Bio, enlaces a tienda/Newsletter y publicaciones propias
Comunidades	club de lectura, recomendaciones libros, lectores fantasía, book club español	Grupos, subreddits, páginas o cuentas con participación real
Tropes y subgéneros	enemigos a amantes, elegido, dragones, magia, academia mágica, fae, vampiros	Afinidad alta con romantasy y fantasía juvenil
Operadores por red

X: combinar términos, exclusiones, idioma y filtros de interacción; las listas son especialmente útiles para vigilar grupos curados de autores y lectores; snscrape documenta el uso de listas mediante list:ID o usuario/lista.
stackoverflow

Bluesky: usar app.bsky.feed.searchPosts con q, limit, since y until; la referencia pública confirma que muchos endpoints app.bsky.* GET son accesibles sin autenticación.
endpoints.bsky
+1

Mastodon: buscar primero hashtags y cuentas; después ampliar con estados cuando la instancia tenga búsqueda de texto habilitada.
joinmastodon

Reddit: restringir por subreddit, ordenar por new para descubrimiento y por top para validación de interés; la API admite sort, t, limit y cursor after.
docs.redditapis

TikTok: comenzar en Creative Center por región España, revisar hashtags relacionados y derivar creadores desde los posts más representativos.
ads.tiktok
+1

Pinterest: buscar conceptos visuales y tropes, no solo títulos; los pins y tableros revelan estéticas, sagas y comunidades de lectores.

Facebook: partir de páginas públicas y grupos temáticos; facebook-pages-scraper puede aportar metadatos de página y último post, pero conviene tratarlo como fuente de descubrimiento, no como motor de interacción.
pypi

Instagram: usar perfiles semilla y co-ocurrencia de hashtags; Instaloader permite obtener captions y metadatos de contenido público.
github

Modelo de datos mínimo

Crea una tabla única multi-red para que el descubrimiento sea homogéneo:

sql
CREATE TABLE discovery_candidates (
  id TEXT PRIMARY KEY,
  network TEXT NOT NULL,
  kind TEXT NOT NULL,              -- post | profile | community | hashtag | page | board
  external_id TEXT NOT NULL,
  handle TEXT,
  display_name TEXT,
  url TEXT,
  language TEXT,
  text TEXT,
  hashtags TEXT[],
  mentions TEXT[],
  author_external_id TEXT,
  metrics JSONB,                   -- likes, comments, shares, followers, etc.
  seed_source TEXT,
  query TEXT,
  discovered_at TIMESTAMPTZ,
  affinity_score REAL,
  action_priority REAL,
  status TEXT DEFAULT 'new'
);

CREATE UNIQUE INDEX ux_discovery_network_external
ON discovery_candidates (network, kind, external_id);
Ranking inicial
𝑠
𝑐
𝑜
𝑟
𝑒
=
0.30
⋅
𝑎
𝑓
𝑖
𝑛
𝑖
𝑑
𝑎
𝑑
+
0.20
⋅
𝑟
𝑒
𝑐
𝑒
𝑛
𝑐
𝑖
𝑎
+
0.15
⋅
𝑒
𝑛
𝑔
𝑎
𝑔
𝑒
𝑚
𝑒
𝑛
𝑡
+
0.15
⋅
𝑡
𝑎
𝑚
𝑎
𝑛
𝑜
_
𝑎
𝑢
𝑑
𝑖
𝑒
𝑛
𝑐
𝑖
𝑎
+
0.10
⋅
𝑖
𝑑
𝑖
𝑜
𝑚
𝑎
_
𝑒
𝑠
+
0.10
⋅
𝑠
𝑒
𝑛
𝑎
𝑙
_
𝑎
𝑢
𝑡
𝑜
𝑟
score=0.30⋅afinidad+0.20⋅recencia+0.15⋅engagement+0.15⋅tamano_audiencia+0.10⋅idioma_es+0.10⋅senal_autor

Afinidad: coincidencias con fantasía, romantasy, tropes, libros, lectura y escritura.

Recencia: posts de las últimas 24–72 h para interacción; perfiles con actividad en 30 días para seguimiento.

Engagement: comentarios y respuestas pesan más que likes.

Señal de autor: bio, enlace, menciones a manuscrito, saga, tienda, newsletter o autoedición.

Idioma español: detectar con langdetect o fastText, con revisión manual de una muestra.

Recomendación

Implementa primero un núcleo multi-red de descubrimiento, no nueve scrapers independientes:

Bluesky como motor principal: búsqueda pública + Jetstream; es la fuente más abierta y técnicamente escalable.
endpoints.bsky
+1

Reddit como fuente de comunidades e intención: subreddits, posts y comentarios permiten detectar lectores con necesidades concretas.
docs.redditapis
+1

Mastodon como red federada complementaria: hashtags, cuentas y estados mediante /api/v2/search.
joinmastodon

Instagram, TikTok y Pinterest como capas de afinidad visual y tendencias: detectan bookstagram, booktok, estéticas, tropes y hashtags emergentes.
ads.tiktok
+2

X, Threads y Facebook como capas de descubrimiento semiautomático: listas, búsquedas, páginas y grupos; usa adaptadores tolerantes a fallos y revisión humana.

Un solo scorer y una sola cola de acciones: todas las redes deben alimentar el mismo discovery_candidates, el mismo ranking y el mismo registro de resultados.

Plan de implementación en PR pequeñas
PR 1 — Esquema y contratos

Crear discovery_candidates, discovery_queries, discovery_runs y action_queue.

Definir NetworkAdapter con métodos: search, fetch_profile, normalize, health_check.

Añadir tests de esquema, deduplicación y validación de JSON.

PR 2 — Semillas del nicho

Cargar 100–200 semillas: autores españoles/latinoamericanos de fantasía, bookstagrammers, booktokers, reseñistas, editoriales independientes y comunidades.

Guardar semillas con kind, network, url, reason y priority.

Añadir comando python -m growth.seeds validate.

PR 3 — Adaptador Bluesky

Implementar búsqueda con app.bsky.feed.searchPosts, filtros since/until, idioma y hashtags.
endpoints.bsky
+1

Persistir posts, autores y hashtags.

Tests: búsqueda básica, paginación, filtrado por español, deduplicación y errores de red.

PR 4 — Worker Jetstream

Consumir app.bsky.feed.post desde Jetstream.
jakelazaroff

Aplicar filtros tempranos: español, términos del nicho, hashtags y longitud mínima.

Guardar cursor y reconectar automáticamente.

Tests: reconexión, cursor, backpressure y volumen.

PR 5 — Adaptador Reddit

Buscar en r/fantasy, r/Fantasy_Writing, r/selfpublish, r/books, r/libros y comunidades detectadas.

Usar sort=new para oportunidades y sort=top para validación.
docs.redditapis

Extraer posts, autores, subreddits y comentarios relevantes.

Tests: OAuth, rate limit, paginación y normalización.

PR 6 — Adaptador Mastodon

Implementar cliente multi-instancia para /api/v2/search.
joinmastodon

Descubrir hashtags, cuentas y estados; guardar instancia de origen.

Tests: instancias con y sin búsqueda de estados, tokens, cursores y errores federados.

PR 7 — Instagram y Pinterest

Integrar Instaloader para perfiles y captions públicos; respetar límites y sesiones.
github

Añadir proveedor Pinterest para pins, tableros y hashtags.

Extraer co-ocurrencias de hashtags para ampliar el diccionario del nicho.

Tests: captions, hashtags, deduplicación y rate limiting.

PR 8 — TikTok y Facebook

Incorporar exportaciones o capturas estructuradas de TikTok Creative Center para hashtags, regiones y creadores.
ads.tiktok
+1

Usar facebook-pages-scraper solo para descubrir páginas públicas y su último post.
pypi

Marcar estos orígenes como semi_auto y exigir confirmación antes de crear acciones.

PR 9 — Scoring y cola

Calcular affinity_score y action_priority.

Generar cola diaria: comentarios prioritarios, perfiles a seguir, comunidades a vigilar y hashtags a testear.

Registrar resultado por acción: respuesta, like, guardado, clic, nuevo seguidor, conversación iniciada.

PR 10 — Panel y aprendizaje

Añadir consultas: mejores hashtags por red, mejores comunidades, mejores horas, perfiles con mayor reciprocidad y consultas con mayor conversión.

Retirar consultas sin candidatos útiles tras 7–14 días.

Ampliar automáticamente el diccionario con hashtags y términos co-ocurrentes de alto rendimiento.

Aplicación transversal

Un diccionario global: términos, tropes, autores, sagas, hashtags y patrones de intención compartidos por todas las redes.

Adaptadores pequeños: cada red solo traduce su formato al esquema común.

Dos modos: discovery para ampliar universo y monitoring para vigilar semillas de alta calidad.

Muestreo humano: revisar 20–50 candidatos nuevos al día durante las primeras dos semanas para ajustar reglas y evitar ruido.

Métricas por red: candidatos nuevos, candidatos relevantes, tasa de respuesta, perfiles descubiertos, comunidades activas y conversaciones iniciadas.

Fuentes

Bluesky HTTP API y endpoints públicos: 
https://endpoints.bsky.app/
endpoints.bsky

Bluesky firehose: 
https://bsky.network/docs/consuming-the-firehose/
bsky

Jetstream, proyecto oficial de Bluesky: https://github.com/bluesky-social/jetstream
jakelazaroff

bluesky-firehose-py: 
https://github.com/ruggsea/bluesky-firehose-py
github

Mastodon Search API: 
https://docs.joinmastodon.org/methods/search/
joinmastodon

OSoMe Mastodon Search: 
https://osome.iu.edu/tools/mastodon/apidocumentation
osome.iu

Reddit Developer API: 
https://www.reddit.com/dev/api/
reddit

Reddit Search API: 
https://docs.redditapis.com/docs/listings/search
docs.redditapis

TikTok Creative Center Trends: 
https://ads.tiktok.com/resources/help/article/how-to-use-trends
ads.tiktok

TikTok Creative Center: 
https://ads.tiktok.com/resources/help/article/creative-center?lang=en
ads.tiktok

Instaloader: 
https://github.com/instaloader/instaloader
github

facebook-pages-scraper: 
https://pypi.org/project/facebook-pages-scraper/
pypi

social-media-profile-scrapers: 
https://github.com/topics/facebook-scraper
github

Uso de listas en snscrape: 
https://stackoverflow.com/questions/75289435/how-do-i-scrape-a-twitter-list-using-snscrape
stackoverflow
