# Crecimiento orgánico del nicho lector en Mastodon y Fediverso

Fuente: informe de Perplexity (https://www.perplexity.ai/search/53228cff-b42f-4c61-96cb-1596216e512e), generado 10/10/2026.

Investigación: descubrimiento, priorización y engagement en Mastodon/Fediverso para fantasía/romantasy en español

Resumen: Para Mastodon, la base técnica más sólida es Mastodon.py como cliente API, mastodon-social-graph para descubrir perfiles conexos y mastodon-to-sqlite como referencia de persistencia local. El crecimiento real en el Fediverso depende menos de automatización masiva y más de descubrimiento por hashtags específicos, participación conversacional, boosts con valor añadido y perfiles claros; el sistema debe priorizar posts y cuentas con señales de relevancia y engagement, no ejecutar acciones indiscriminadas.
github
+4

Hallazgos
Hallazgo	Repo / fuente	Licencia	Qué reutilizar	Integración en nuestro sistema	Riesgos técnicos	Tests
Cliente API completo para Mastodon, compatible con Python 3.7+ y con la API pública hasta Mastodon 4.5.8; 958 estrellas y 172 forks.	
halcy/Mastodon.py
 
github
	Incluye LICENSE; proyecto publicado y documentado en PyPI. 
pypi
	Autenticación OAuth, registro de app, paginación, publicación, timelines, búsqueda, follows, replies y boosts.	Capa MastodonAdapter común: discover(), rank_candidates(), act(), log_result().	Diferencias de configuración y búsqueda entre instancias; límites de API. 
joinmastodon
	Mocks de API; prueba de OAuth; paginación; reintento ante 429.
Búsqueda unificada de cuentas, estados y hashtags; los hashtags y cuentas son buscables por defecto, mientras que la búsqueda de estados depende de ElasticSearch y autenticación.	
Mastodon Search API
 
joinmastodon
	Documentación oficial.	Consultas q, type=accounts/hashtags/statuses, resolve, limit, max_id y min_id.	Módulo discovery/queries.py con consultas en español: “fantasía”, “romantasy”, “lectura fantasia”, “autores fantasía”, etc.	La búsqueda de estados puede no estar disponible en todas las instancias. 
joinmastodon
	Unit tests por tipo de búsqueda; test de instancias sin full-text search.
Grafo social con SQLite, caché en memoria y scraper bajo demanda; útil para encontrar cuentas vecinas a autores, lectores y comunidades relevantes.	
volfpeter/mastodon-social-graph
 
github
	MIT. 
github
	Carga de nodos, vecinos, persistencia SQL y espera ante rate limit.	Seed accounts → vecinos → scoring de afinidad temática; alimenta candidatos de follow y listas de vigilancia.	Proyecto pequeño, 11 estrellas; no usar para rastreo masivo de seguidores. 
github
	Test de vecinos; test de caché; test de límite de profundidad.
Exporta seguidores, seguidos, estados, marcadores y favoritos a SQLite.	
myles/mastodon-to-sqlite
 
github
	Apache-2.0. 
github
	Modelo de almacenamiento, comandos CLI y autenticación local.	Base rrss.db: accounts, posts, interactions, hashtags, action_queue, results.	Repositorio poco activo; reutilizar el patrón, no depender del paquete como núcleo. 
github
	Migraciones SQLite; idempotencia de import; integridad referencial.
Los hashtags son la principal superficie de descubrimiento; usuarios pueden seguir hashtags y las publicaciones públicas aparecen en timelines locales, federadas y de hashtag.	
fedi.tips
 
fedi
, 
SocialKit
 
socialk
	Guías públicas.	Estrategia de 2–5 hashtags específicos, CamelCase y rotación de etiquetas.	Diccionario de hashtags por idioma y subnicho: #Fantasia, #Romantasy, #LecturaFantasia, #AutoresIndie, #EscribirFantasia.	Etiquetas demasiado amplias generan ruido; el abuso de hashtags daña reputación. 
fediview
+1
	Validador de hashtags; test de relevancia semántica; métrica de CTR/boost por etiqueta.
El crecimiento se apoya en responder de forma genuina, boostear contenido valioso, participar en comunidades y aportar antes de promocionar.	
Brandghost
 
brandghost
, 
Stackmatix
 
stackmatix
	Guías públicas.	Plantillas de respuesta contextual, criterios de boost y ritmo de publicación.	ReplyComposer con variantes humanas y BoostPolicy que exige comentario o motivo editorial.	Riesgo de sonar robótico si las respuestas son genéricas. 
brandghost
	Test anti-plantilla; diversidad léxica; revisión humana previa opcional.
Ejemplo reutilizable de bot que monitoriza menciones, lee contexto del hilo y responde con LLM local mediante Ollama.	
jeffehobbs/mastodonreplybot
 
github
	Verificar licencia en el repo antes de copiar código.	Arquitectura de escucha de menciones, contexto de hilo y generación de respuesta.	Adaptar a un modo “borrador asistido”: propone respuesta, el sistema valida tono y el usuario aprueba o se publica con política estricta.	Dependencia de Ollama y calidad variable del LLM; puede generar respuestas irrelevantes. 
github
	Tests de contexto; filtro de alucinaciones; test de tono en español.
Ejemplo simple de bot de publicación programada para una cuenta personal autoalojada.	
Crell/mastobot
 
github
	Verificar licencia en el repo.	Programador de posts y estructura de automatización individual.	Base para scheduler.py en Windows Task Scheduler, con cola SQLite y ventana horaria.	Enfocado a publicación, no a descubrimiento ni ranking. 
github
	Test de zona horaria; test de cola; test de fallo y reintento.
Búsqueda multi-instancia de estados por palabra clave, hashtag, cuentas y metadatos de hashtags.	
OSoMe Mastodon Search
 
osome.iu
	Servicio de investigación, no repo de integración directa.	Idea de ampliar descubrimiento a varias instancias y comparar actividad por etiqueta.	Módulo opcional multi_instance_scout para medir qué instancias concentran conversación en español.	Dependencia externa y disponibilidad variable; no como dependencia crítica. 
osome.iu
	Fallback a API nativa; test de instancias caídas.
Qué hacen bien las cuentas que crecen

Perfil legible y posicionado: bio que explica qué publica la cuenta, enlace al sitio o newsletter y expectativa clara de contenido; esto facilita el follow tras descubrir un post.
stackmatix

Hashtags específicos, no genéricos: en Mastodon, 2–5 etiquetas relevantes funcionan mejor que muros de hashtags; etiquetas como #Romantasy o #LecturaFantasia son más accionables que #Libros.
socialk
+1

Participación antes que difusión: responder preguntas, recomendar lecturas, comentar procesos creativos y boostear a otros autores/lectores genera confianza y visibilidad indirecta.
brandghost
+1

Boosts con criterio: el boost amplifica contenido a los seguidores propios; añadir una frase breve de contexto —por ejemplo, una escena, un tropo o una recomendación— convierte el repost en una intervención útil.
brandghost

Constancia y comunidades: publicar con regularidad, entrar en grupos del Fediverso y participar en presentaciones y conversaciones de nicho crea presencia reconocible.
fedi

Medición simple: seguir respuestas, boosts, favoritos, nuevos seguidores y tráfico con UTM permite saber qué formatos y hashtags atraen lectores reales.
stackmatix

Recomendación

Construir un Mastodon Growth Engine propio, modular y local, en Python 3.11 para Windows, usando Mastodon.py como única dependencia crítica de API. Reutilizar ideas de mastodon-social-graph para expansión de perfiles y de mastodon-to-sqlite para persistencia, pero mantener el esquema de base de datos y el ranking bajo nuestro control.

El flujo debe ser:

Descubrir: hashtags en español + búsqueda de cuentas + vecinos de cuentas semilla.

Puntuar: relevancia temática, idioma, actividad reciente, relación con fantasía/romantasy, señales de engagement y calidad del post.

Encolar: follows, respuestas y boosts como acciones independientes, con presupuesto diario y revisión humana inicial.

Actuar: publicar solo acciones de alta puntuación, con variación real y contexto.

Aprender: registrar resultado a 24 h, 72 h y 7 días; ajustar pesos por hashtag, tipo de post y tipo de cuenta.

Plan de implementación en PR pequeñas
PR 1 — Núcleo y configuración

Crear mastodon/adapter.py con Mastodon.py, carga de credenciales desde .env, timeout, logging y ratelimit_method="wait".

Añadir config/mastodon.yaml con instancia, idioma objetivo, hashtags semilla y presupuestos diarios.

Tests: conexión, credenciales inválidas, límite de peticiones.

PR 2 — Descubrimiento por hashtags

Implementar discovery/hashtag_scout.py.

Consultar timelines de hashtags: #Fantasia, #Romantasy, #FantasiaEpica, #LecturaFantasia, #AutoresIndie, #EscribirFantasia.

Guardar posts, autor, idioma estimado, engagement y URL en SQLite.

Tests: deduplicación, filtrado por español, paginación y posts sin métricas.

PR 3 — Descubrimiento de perfiles

Implementar discovery/account_scout.py con /api/v2/search.

Añadir expansión ligera inspirada en mastodon-social-graph: solo 1–2 niveles desde cuentas semilla.

Calcular niche_score con palabras clave: fantasía, romantasy, dragones, magia, lectura, reseñas, editorial, escritura.

Tests: puntuación, exclusión de cuentas irrelevantes y control de profundidad.

PR 4 — Ranking de oportunidades

Crear ranking/scorer.py.

Fórmula inicial:

𝑠
𝑐
𝑜
𝑟
𝑒
=
0.35
⋅
𝑟
𝑒
𝑙
𝑒
𝑣
𝑎
𝑛
𝑐
𝑖
𝑎
+
0.25
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
0.20
⋅
𝑓
𝑟
𝑒
𝑠
𝑐
𝑢
𝑟
𝑎
+
0.10
⋅
𝑎
𝑓
𝑖
𝑛
𝑖
𝑑
𝑎
𝑑
_
𝑎
𝑢
𝑡
𝑜
𝑟
+
0.10
⋅
𝑝
𝑜
𝑡
𝑒
𝑛
𝑐
𝑖
𝑎
𝑙
_
𝑐
𝑜
𝑛
𝑣
𝑒
𝑟
𝑠
𝑎
𝑐
𝑖
𝑜
𝑛
score=0.35⋅relevancia+0.25⋅engagement+0.20⋅frescura+0.10⋅afinidad_autor+0.10⋅potencial_conversacion

Priorizar posts con pregunta, opinión, recomendación, fragmento, tropo o petición de lecturas; penalizar spam, reposts vacíos y cuentas inactivas.

Tests deterministas con fixtures JSON.

PR 5 — Respuestas humanas y variadas

Crear actions/reply.py con plantillas por intención: recomendación, pregunta, celebración de tropo, comentario de escena, apoyo a autor indie.

Exigir mínimo 2 variables contextuales: tema del post, detalle concreto y tono.

Generar 3 borradores; publicar solo el aprobado o el que supere un umbral alto de calidad.

Tests: longitud, idioma, prohibición de frases repetidas y diversidad de apertura.

PR 6 — Follows y boosts responsables

Implementar actions/follow.py y actions/boost.py.

Follow solo si niche_score >= umbral, bio relevante y actividad reciente.

Boost solo posts de fantasía/romantasy con valor para lectores; opcionalmente añadir comentario propio.

Tests: presupuesto diario, antiduplicación y reversibilidad registrada.

PR 7 — Aprendizaje y panel

Crear analytics/results.py: boosts recibidos, respuestas, favoritos, nuevos seguidores y clics UTM.

Añadir informe semanal Markdown: mejores hashtags, mejores horas, mejores formatos y cuentas con mayor reciprocidad.

Tests: cálculo de métricas y detección de acciones sin resultado.

Aplicación a las demás redes

X, Threads, Bluesky y Mastodon: compartir el mismo motor de intención —descubrir, puntuar, responder, boost/repost— con adaptadores específicos.

Facebook y Reddit: priorizar grupos, páginas y hilos; la acción principal debe ser comentario útil, no follow masivo.

Pinterest e Instagram: convertir los posts ganadores en pins, carruseles y Reels; el “boost” equivale a guardar, compartir o comentar con contexto visual.

TikTok: detectar tendencias y cuentas de lectores; el sistema debe proponer ganchos narrativos y comentarios, no automatizar publicación sin revisión.

Mastodon como laboratorio: al ser más transparente por hashtags, timelines y API, es la mejor red para validar qué temas, formatos y frases interesan antes de replicarlos en X, Threads o Bluesky.
socialk
+1

Fuentes

Mastodon.py en GitHub
github

Mastodon.py en PyPI
pypi

Documentación de Mastodon.py
mastodonpy

Mastodon Search API
joinmastodon

Entidad Search de Mastodon
joinmastodon

mastodon-social-graph
github

mastodon-to-sqlite
github

mastodonreplybot
github

mastobot
github

fedi.tips: descubrimiento en Mastodon
fedi

Mastodon Content Strategy
brandghost

Mastodon Marketing Guide
stackmatix

Guía de hashtags Mastodon 2026
fediview

OSoMe Mastodon Search
osome.iu
