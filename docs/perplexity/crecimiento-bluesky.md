# Crecimiento orgánico del nicho lector en Bluesky y AT Protocol

Fuente: informe de Perplexity (https://www.perplexity.ai/search/baa6e704-9e49-4a3c-8dd1-52a957fc7ecc), generado 10/10/2026.

Investigación: descubrimiento y priorización de posts/perfiles en Bluesky para fantasía/romantasy en español
Resumen

Bluesky es la red más adecuada del stack multired para construir un motor de descubrimiento y engagement medible: su API pública de AT Protocol permite buscar posts por texto, idioma, fecha y etiquetas, leer métricas visibles (respuestas, reposts, likes) y paginar resultados. La base técnica recomendada es el SDK Python atproto (MIT), complementado con un repositorio de feed generator para crear un feed propio de “lectores fantasy ES” y un módulo de ranking propio.
atproto
+3

La palanca de crecimiento no es publicar más, sino responder pronto y con valor en conversaciones activas del nicho; las guías recientes sitúan las respuestas como la métrica más importante y señalan un rango especialmente útil de posts con 5–20 respuestas y autores de tamaño medio.
teract
+1

Hallazgos
Hallazgo	Repo / fuente	Licencia	Qué reutilizar	Integración en el sistema	Riesgos técnicos	Tests
SDK oficial de la comunidad para AT Protocol en Python: cliente XRPC, modelos generados, Firehose/Jetstream, identidad y helpers de Bluesky.	
MarshalX/atproto
 
github
	MIT 
github
	Autenticación, search_posts, obtención de perfiles, follows, replies, reposts, paginación y suscripción a Jetstream.	Núcleo bluesky_adapter: descubrimiento, acciones y persistencia de resultados.	El protocolo evoluciona rápido; fijar versión en pyproject.toml y aislar llamadas XRPC. 
pypi
+1
	Unit tests con respuestas grabadas; test de paginación; test de creación de reply con root/parent.
Búsqueda nativa de posts con q, lang, since, until, sort, tag, limit y cursor.	
app.bsky.feed.searchPosts
 
atproto
	Documentación pública	Consultas como “fantasía” OR romantasy, filtro lang=es, ventana temporal y orden latest/top.	Generador de candidatos: múltiples queries en español, normalización de texto, dedupe por AT URI y extracción de autor, métricas y contexto.	La sintaxis de búsqueda no está completamente especificada; validar empíricamente cada query. 
atproto
	Golden set de 50 posts reales; aserciones de idioma, dedupe, fecha y campos de métricas.
Feed generator en Python, con filtro y algoritmos personalizables.	
MarshalX/bluesky-feed-generator
 
github
	MIT 
github
	Estructura de servicio, filtrado en data_filter.py, algoritmos en server/algos y publicación del feed.	Crear “Fantasía y romantasy ES”: posts en español con señales de lectura, escritura, reseñas, tropes, portadas y comunidad.	Requiere servicio público accesible para funcionar como feed; separar el feed del bot para poder operar aunque falle. 
github
	Test de filtro por idioma/términos; test de ranking determinista; test de getFeedSkeleton.
Starter kit oficial de feed generators.	
bluesky-social/feed-generator
 
github
	MIT / Apache 2.0 en el repo principal de AT Protocol 
github
	Contrato getFeedSkeleton, formato de URIs y metadatos.	Referencia para validar que nuestro feed devuelve URIs correctas y compatibles con la hidratación de Bluesky.	Es un punto de partida, no una solución completa. 
github
	Contract test del endpoint; test de URIs inválidas y posts eliminados.
Herramienta Python de inteligencia de perfiles: búsqueda de usuarios, keywords, monitorización, timelines, seguidores y patrones de respuesta.	
OSINTCabal/OSINTSky
 
github
	MIT 
github
	Descubrimiento de perfiles, análisis de actividad, comparación de redes de seguidores y detección de patrones de interacción.	Módulo profile_scorer: detectar autores, lectores, reseñadores y comunidades activas en español; evitar perfiles dormidos o irrelevantes.	Está orientado a OSINT; reutilizar solo los bloques de análisis y no recopilar datos sensibles.	Test de scoring de autor; test de detección de inactividad; test de límites de peticiones.
Bot/analytics que monitoriza Jetstream y ordena posts por engagement.	
brainsnorkel/hourstats-bsky
 
github
	Verificar licencia en el repo antes de copiar código	Patrón de consumo en tiempo real y ranking por replies + likes + reposts.	Inspiración para un trend_detector: detectar temas y conversaciones que están subiendo en las últimas 1–6 horas.	Consumir Jetstream continuamente puede ser costoso; empezar por polling cada 10–30 minutos. 
github
	Test de ventana temporal; test de normalización de métricas; test de alertas.
Scheduler Python que publica desde Google Sheets y automatiza follows a partir de búsquedas recientes.	
pwillia7/Bsky_Spreadsheet_Poster
 
github
	Verificar licencia en el repo antes de reutilizar código	Patrón de cola de acciones, control por hoja de cálculo, dedupe de usuarios seguidos y actualización de estadísticas.	Reemplazar Google Sheets por SQLite/Postgres; conservar la idea de cola con estado (pending, done, skipped) y dedupe permanente.	El follow automático masivo es frágil y poco selectivo; adaptarlo a follows de muy baja velocidad y alto criterio. 
github
	Test de idempotencia; test de dedupe; test de presupuesto diario.
Directorios y starter packs en español y de autores/lectores.	
Escritoras y escritores de fantasía
, 
Autores autopublicados
, 
Starter packs en español
 
blueskydirectory
+2
	Datos públicos; revisar condiciones de cada directorio	Semillas iniciales de perfiles, comunidades y términos del nicho.	Cargar una lista semilla curada, clasificar perfiles y ampliar mediante co-ocurrencia de seguidores e interacciones.	Las listas pueden contener cuentas inactivas o fuera de nicho.	Test de clasificador de nicho; revisión humana de una muestra semanal.
BookSky: ecosistema de feeds literarios para lectores y escritores, con feeds por géneros incluidos fantasía, romance y ciencia ficción.	
BookSky
 
booksky
	Servicio público; no es un repo reutilizable	Fuente de descubrimiento y validación de temas; observar qué posts reciben respuestas reales.	Añadir feed_source=booksky al crawler para aprender qué formatos y temas funcionan.	Depende de un servicio externo.	Monitor de disponibilidad; test de parseo de posts.
Qué hacen bien las cuentas que más crecen

Responden antes de promocionar. Las respuestas son la principal señal conversacional en Bluesky; una guía de crecimiento de 2026 recomienda dedicar tiempo diario a responder posts con 5–20 respuestas y autores de 500–5.000 seguidores, donde la visibilidad no queda sepultada ni el hilo está muerto.
teract
+1

Publican poco, pero con identidad clara. La bio específica —por ejemplo, “fantasía juvenil y romantasy en español | proceso creativo y lecturas”— convierte mejor que una bio genérica; el mismo estudio reporta un salto de 12% a 41% en conversión a follow tras reescribirla. 
teract

Participan en feeds de nicho. Los feeds personalizados concentran audiencias temáticas; la recomendación práctica es identificar feeds relevantes, interactuar allí y, más adelante, crear un feed propio que posicione a la cuenta como curadora.
bsky
+1

Fijan su mejor contenido. Anclar el post más valioso —no el más reciente— ayuda a que quien visita el perfil entienda de inmediato la propuesta.
teract

Miden conversación, no solo likes. En Bluesky las respuestas pesan más como indicador de comunidad que los likes; conviene trackear respuestas por post, follows atribuidos a replies y ratio de respuesta por autor objetivo.
sproutsocial
+1

Responden en la primera hora. La actividad temprana sostiene la velocidad de interacción y facilita que el post sea recogido por feeds; las guías recientes recomiendan estar activo durante los primeros 60 minutos.
socialchamp

Para David, la versión de nicho es: responder a lectores que hablan de tropes, finales, portadas, reseñas, “book hangovers”, romantasy, fantasy juvenil, autoedición y recomendaciones en español; no responder solo a otros autores.

Arquitectura recomendada
text
bluesky_growth/
├─ adapters/
│  └─ bluesky.py          # SDK atproto: auth, search, profile, follow, reply, repost
├─ discovery/
│  ├─ queries.py          # queries ES + filtros lang/fecha/tag
│  ├─ seeds.py            # starter packs, BookSky, perfiles semilla
│  └─ jetstream_poller.py # opcional, fase 3
├─ ranking/
│  ├─ post_score.py       # oportunidad de reply
│  └─ profile_score.py    # oportunidad de follow
├─ actions/
│  ├─ queue.py            # SQLite: pending / done / skipped / cooldown
│  └─ composer.py         # plantillas variables, no spam
├─ analytics/
│  └─ outcomes.py         # likes, reposts, replies, follows atribuidos
└─ tests/
Fórmula inicial de priorización

Para cada post candidato:

𝑆
𝑐
𝑜
𝑟
𝑒
=
2
𝑅
+
1.5
𝑄
+
1
𝐿
+
3
𝐴
+
2
𝑁
−
𝑃
Score=2R+1.5Q+1L+3A+2N−P

Donde:

𝑅
R: respuestas recibidas.

𝑄
Q: quote posts.

𝐿
L: likes.

𝐴
A: antigüedad favorable, máxima entre 30 minutos y 6 horas.

𝑁
N: afinidad de nicho detectada por palabras clave y autor.

𝑃
P: penalización por exceso de respuestas, autor demasiado grande, spam, idioma incorrecto o post promocional.

El objetivo no es “responder al post más viral”, sino encontrar conversaciones donde una respuesta específica pueda aportar valor y ser vista.

Señales de perfil para follow

Prioriza perfiles que cumplan varios criterios:

Bio en español con lectores, reseñadores, bookstagrammers, libreros, editoriales pequeñas o autores.

Actividad en los últimos 7–30 días.

Respuestas propias, no solo publicaciones.

Intereses explícitos en fantasía, romantasy, YA, romance, lectura o escritura.

Tamaño medio: normalmente más accesibles que cuentas enormes y más vivas que cuentas abandonadas.

Aparición en starter packs de fantasía, autores autopublicados o listas en español.
blueskydirectory
+2

Plan de implementación en PR pequeñas
PR 1 — Base del adaptador Bluesky

Añadir atproto como dependencia fijada.

Implementar cliente con credenciales desde variables de entorno.

Crear modelos BlueskyPost, BlueskyProfile y ActionCandidate.

Guardar todo en SQLite.

Tests con fixtures JSON.

Criterio de aceptación: puede autenticarse, buscar 25 posts en español y guardarlos sin duplicados.
atproto
+1

PR 2 — Descubrimiento por búsqueda

Implementar 15–25 queries iniciales: romantasy, fantasía juvenil, lectura fantasía, reseña fantasía, autores fantasia, booktok español, recomendacion romantasy, etc.

Usar lang="es", since, until, sort y cursor.

Normalizar texto, extraer hashtags, menciones, enlaces y métricas.

Tests de dedupe, idioma y paginación.

Criterio de aceptación: el sistema descubre al menos 200 posts útiles por ejecución diaria sin duplicar candidatos.
atproto
+1

PR 3 — Ranking de posts y respuestas

Implementar la fórmula de score.

Filtrar posts con 0 respuestas, hilos saturados, cuentas inactivas y contenido puramente promocional.

Generar 3 variantes de respuesta por candidato, con longitud, tono y enfoque distintos.

Exigir revisión humana durante las primeras 2 semanas.

Criterio de aceptación: cada respuesta propuesta cita un elemento concreto del post original y no repite plantillas idénticas.

PR 4 — Follows de alta calidad

Implementar profile_score con actividad, nicho, idioma, respuestas y tamaño.

Límite duro diario, por ejemplo 5–15 follows.

Cooldown por perfil y registro permanente para no repetir.

Nunca seguir cuentas solo porque aparecen en una búsqueda.

Criterio de aceptación: el sistema propone follows con motivo explicado y permite aprobarlos por lotes.

PR 5 — Reposts y quotes útiles

Repostear recomendaciones, hilos de lectores, novedades editoriales y convocatorias literarias relevantes.

Priorizar quote posts cuando se pueda añadir contexto: una opinión breve, una recomendación complementaria o una pregunta.

Evitar repostear autopromoción masiva.

Criterio de aceptación: cada repost/quote tiene categoría, motivo y métrica posterior.

PR 6 — Analítica de resultados

Medir por acción: impresiones si están disponibles, likes, reposts, respuestas, nuevos seguidores y respuestas recibidas.

Atribuir follows a la acción que precedió en 72 horas.

Generar informe semanal: mejores queries, mejores autores, mejores horas, mejores formatos y tasa de respuesta.

Las guías coinciden en que la conversación —no el volumen— es la señal que hay que optimizar.
sproutsocial
+1

Criterio de aceptación: dashboard o CSV con ranking semanal de queries, posts, perfiles y plantillas.

PR 7 — Feed propio “Fantasía y romantasy ES”

Reutilizar la estructura de bluesky-feed-generator.
github

Filtrar por español, temas literarios y calidad mínima de interacción.

Incluir autores, lectores, reseñas, portadas, tropes, novedades y conversaciones.

Publicar el feed solo cuando tenga suficientes posts de calidad.

Criterio de aceptación: el feed devuelve posts relevantes, ordenados y sin spam.
github
+1

Aplicación a las demás redes
Red	Pieza transferible	Adaptación
X	Ranking por respuestas, antigüedad y afinidad; colas con dedupe.	Búsqueda y métricas mediante API oficial; límites y costes más restrictivos.
Threads	Detección de conversaciones y respuestas tempranas.	Menos API pública; priorizar observación manual asistida y plantillas de respuesta.
Facebook	Grupos, páginas y eventos de lectura/fantasía.	El “post candidato” pasa a ser grupo, hilo o evento; el follow pasa a unirse/interactuar.
Pinterest	Pines de portadas, aesthetics, quotes y tableros de lectura.	El ranking debe premiar guardados, clics y relevancia visual, no respuestas.
Reddit	Subreddits, hilos y comentarios de lectura/fantasy en español.	Reutiliza ranking de hilos, pero la acción principal es comentario contextual, no follow.
Mastodon	Búsqueda por hashtags, instancias y perfiles.	Muy parecido a Bluesky: adaptador con API distinta y federación por instancia.
TikTok	Comentarios, sonidos, hashtags y creadores de BookTok.	Prioriza comentarios en vídeos recientes y detección de tendencias; el repost se sustituye por duet/stitch o guardado.
Instagram	Comentarios, Stories, Reels, hashtags y perfiles de Bookstagram.	Prioriza comentarios y relaciones; el repost se convierte en compartir Stories o colaboraciones.
Recomendación

Implementa primero PR 1–4: búsqueda en español, ranking, cola de acciones y follows selectivos. Con eso ya tienes un sistema medible sin depender de infraestructura externa. Después añade el feed propio, porque es la pieza que convierte la cuenta en un punto de encuentro del nicho y no solo en otra cuenta que responde.
github
+1

La combinación más eficiente es:

atproto como SDK principal, MIT y Python.
github

searchPosts como motor de descubrimiento.
atproto

bluesky-feed-generator como base del feed de nicho.
github

Starter packs en español y BookSky como semillas iniciales.
blueskydirectory
+2

Ranking propio basado en respuestas, recencia, afinidad y calidad del autor.
teract
+1

Fuentes

atproto SDK en PyPI
pypi

MarshalX/atproto en GitHub
github

Estrategia de crecimiento en Bluesky 2026
teract

bluesky-social/atproto
github

Sprout Social: estadísticas y estrategia en Bluesky
sproutsocial

AT Protocol SDKs oficiales
atproto

Bluesky HTTP API Reference
endpoints.bsky

Custom feeds de Bluesky
bsky

Posts en profundidad: replies y quote posts
bsky

app.bsky.feed.searchPosts
atproto

Ejemplo Python de búsqueda y paginación
davidgasquez

MarshalX/bluesky-feed-generator
github

bluesky-social/feed-generator
github

OSINTCabal/OSINTSky
github

brainsnorkel/hourstats-bsky
github

pwillia7/Bsky_Spreadsheet_Poster
github

BookSky
booksky

Starter pack: escritoras y escritores de fantasía
blueskydirectory

Starter pack: autoras y autores autopublicados
blueskydirectory

Starter packs en español
blueskystarterpack

Métricas y engagement en Bluesky
theblue

Análisis de engagement 2026
useagentsky
