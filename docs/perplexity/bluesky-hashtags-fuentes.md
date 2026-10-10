# Hashtags, fuentes y comunidades en Bluesky

Fuente: informe de Perplexity (https://www.perplexity.ai/search/54f6d94b-764d-451e-b541-0debc240abf2), generado 10/10/2026.

Informe mejorado: descubrimiento lector en Bluesky

He revisado el informe anterior contra el repo davidpd89/ci-sandbox-tmp y contra fuentes públicas actuales. La corrección principal es reducir la lista de cuentas semilla no verificadas, eliminar recursos desactualizados o de enfoque OSINT como base de implementación, y sustituir recomendaciones genéricas por piezas concretas: búsqueda AppView con since/until/lang, snowballing mediante menciones y respuestas, y Jetstream para vigilancia en vivo.

El repo ya contiene SISTEMA_DIARIO_BLUESKY/, además de ramas específicas como research/bluesky-feed-appview-visibility, research/jetstream-v2-archive-recovery, research/hashtag-observation-adapters y research/native-target-candidate-ingest. Por ello, cualquier nueva capacidad debe entrar como fuente de candidatos y evidencia para esas colas, no como un segundo sistema de descubrimiento.

Resumen

La mejor arquitectura es un pipeline de tres fuentes complementarias:

Búsqueda AppView: posts recientes por hashtags, frases y términos de intención, con filtros de idioma y fecha.

Snowballing: a partir de posts relevantes, extraer autores, mencionados y participantes de respuestas para descubrir perfiles afines.

Jetstream: vigilancia continua de términos de alta intención y cuentas semilla confirmadas.

Esta combinación está mejor respaldada por el repositorio brianckeegan/bluesky-datascience, que documenta búsqueda, archivo deduplicado, expansión por menciones/respuestas y análisis de redes; es más útil como referencia de implementación que los directorios de starter packs, que solo resuelven la parte de cuentas.
bsky
+1

Correcciones al informe previo
Elemento anterior	Decisión	Motivo
@fedkukso.bsky.social como semilla prioritaria	Eliminar	Es una cuenta de divulgación científica y curación general; no es una semilla fiable del nicho lector
awesome-bluesky como fuente principal	Degradar a referencia histórica	El propio repositorio indica que ya no se mantiene; su último commit del README es de septiembre de 2025. 
github

OSINTCabal/OSINTSky como herramienta a copiar	No recomendar para copiar	Tiene solo 2 estrellas, 6 commits y enfoque OSINT/vigilancia; es útil únicamente para confirmar endpoints, no como base del sistema. 
github

Listas cerradas de cuentas semilla	Sustituir por semillas dinámicas	Las cuentas y packs cambian; el sistema debe validar idioma, actividad, tema y calidad antes de priorizar
Starter packs como fuente principal	Mantener como fuente secundaria	Sirven para arrancar, pero no garantizan actividad, idioma ni afinidad temática
“Feeds” sin método de selección	Sustituir por validación previa	Un feed debe demostrar volumen, español y relevancia antes de automatizarse

awesome-bluesky sigue siendo útil para localizar categorías de herramientas —feeds, directorios, analítica y firehose—, pero no debe tratarse como un catálogo vivo ni como dependencia operativa.
github

Hallazgos reutilizables
Necesidad	Mejor recurso público	Estado / utilidad	Qué aprovechar
Búsqueda, archivo y expansión de red	
brianckeegan/bluesky-datascience
	Activo como material de referencia; 38 commits, notebooks Python y R, licencia presente. 
github
	Patrón de búsqueda con since/until, deduplicación, facetas, snowballing y rehidratación de posts
Streaming y recuperación	
bluesky-social/jetstream
	Repositorio oficial; servicio de archivo, replay y streaming para AT Protocol.	Filtrado por colección/DID, cursor de reanudación, replay y snapshot
Feed generator propio	bluesky-social/feed-generator	Referencia oficial para crear feeds personalizados. 
github
	Arquitectura de un feed generado desde consultas propias; útil solo si queremos un feed público de descubrimiento
Búsqueda avanzada	
lukeslp/skymarshal-js
	Actualizado en enero de 2026; implementa búsqueda con operadores. 
blueskystarterpack
	Diseño de consultas con frase exacta, exclusión e inclusión; no copiar por ser JavaScript
Directorio de herramientas	
fishttp/awesome-bluesky
	1.1k estrellas, pero el proyecto declara que no se mantiene. 
github
	Localizar herramientas; verificar cada una antes de usarla
Starter packs	
blueskystarterpack.com/espanol
 y 
versión spanish
	Directorios con decenas/cientos de packs en español.	Descubrimiento inicial de perfiles; siempre validar DID, actividad y tema
Directorio alterno	Bluesky Directory	Directorio público de packs; útil como segunda fuente.	Cruzar packs y detectar duplicados
Curación social	
Skypacks
	Cuenta que recopila y comparte starter packs y feeds.	Señal de packs/feeds nuevos; no semilla de comentario
Validación manual de feeds	Skyfeed	Herramienta con constructor de feeds por términos, idioma, tipo de post y usuarios. 
reddit
	Probar reglas antes de automatizarlas
Referencia de endpoints	Documentación AppView searchPosts	Endpoint oficial de búsqueda de posts. 
github
	Parámetros q, sort, since, until, lang y paginación
Hashtags y búsquedas
Consultas núcleo

Estas consultas deben ejecutarse de forma programada, con sort=latest, filtro de español y ventana temporal reciente:

text
#BookTok lang:es
#Bookstagram lang:es
#Lectura lang:es
#Lectores lang:es
#Lectora lang:es
#RecomendacionesLiterarias lang:es
#QuéLeo lang:es
#LeoEnEspañol lang:es
#Fantasía lang:es
#Fantasia lang:es
#Romantasy lang:es
#FantasíaJuvenil lang:es
#LiteraturaJuvenil lang:es

No conviene tratar lang:es como filtro absoluto: algunos posts relevantes pueden no declarar idioma. El pipeline debe usar langs del post como señal fuerte, más detección de idioma sobre texto, bio e interacciones.

Romantasy y subgéneros
text
#Romantasy lang:es
#RomanceFantasy lang:es
#FantasíaÉpica lang:es
#AltaFantasía lang:es
#DarkRomance lang:es
#RomanceOscuro lang:es
#FaeRomance lang:es
#EnemiesToLovers lang:es
#AcademiaDeMagia lang:es
#FantasíaOscura lang:es
#FantasíaRomántica lang:es
#Dragones lang:es
#Hadas lang:es
#Vampiros lang:es

#Romantasy, #DarkRomance, #FaeRomance y #EnemiesToLovers son útiles para afinidad, pero muchas apariciones serán en inglés. Deben quedar en una cola de revisión o requerir confirmación adicional de español.

Intención conversacional

Estas consultas son las más valiosas para seleccionar posts donde un comentario específico tiene sentido:

text
"recomendaciones fantasía" lang:es
"libros romantasy" lang:es
"novela fantástica" lang:es
"fantasía juvenil" lang:es
"qué leo ahora" lang:es
"necesito recomendaciones" lang:es
"busco libros de fantasía" lang:es
"recomendad libros" lang:es
"reseña fantasía" lang:es
"lecturas del mes" lang:es

Prioridad alta para posts que contengan una pregunta, una petición explícita, una lista, una reseña o una mención a un tropo concreto. Un hashtag por sí solo no justifica una acción.

Código reutilizable
Búsqueda AppView con fecha

Este comando es útil para validar manualmente una consulta y comprobar el formato de since/until. Está tomado tal cual de la discusión oficial de AT Protocol; consulta posts de una cuenta en un día concreto.
github

bash
# https://github.com/bluesky-social/atproto/discussions/2180
curl --location 'https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=from%3A%40mm-twitter-archive.bsky.social&since=2023-08-23T00%3A00%3A00.000Z&until=2023-08-23T23%3A59%3A59.000Z'

Para el nicho, la adaptación es directa: sustituir q por una consulta como q=%22recomendaciones%20fantas%C3%ADa%22 y añadir lang=es, sort=latest y una ventana de las últimas 24–72 horas.

Filtrado de un feed por idioma

Este pipeline curl + jq procede tal cual de un gist público y filtra los posts de un feed por idioma inglés; demuestra el patrón correcto de leer feed[].post, ordenar por createdAt y filtrar por record.langs.
github

bash
# https://gist.github.com/cmj/b17a37cd25e4759519dcc55af564bb1a
curl -s -H "authorization: Bearer ${API_KEY}" 'https://bsky.social/xrpc/app.bsky.feed.getFeed?feed=at%3A%2F%2Fdid%3Aplc%3Az72i7hdynmk6r22z27h6tvur%2Fapp.bsky.feed.generator%2Fhot-classic&limit=20' |
jq '[.feed[].post] |
sort_by(.record.createdAt) |
reverse |
.[] |
select(.record.langs[]=="en") |
"\(.author.handle) \(.record.createdAt) \(.uri) \(.record.text)\(if (.record.embed) then " [img]" else "" end)"'

Para nuestro caso, el cambio mínimo es select(.record.langs[]=="es"); no obstante, debe complementarse con detección de idioma porque langs puede estar vacío o ser impreciso.

Instalación de referencia OSINTSky

No recomiendo adoptar OSINTSky como base del sistema, pero sus comandos de instalación son correctos para una prueba aislada y confirman que emplea el SDK oficial atproto y los endpoints relevantes.
github

bash
# https://github.com/OSINTCabal/OSINTSky
git clone https://github.com/OSINTCabal/OSINTSky.git
cd OSINTSky
pip install -r requirements.txt
python3 blueskyosint.py
bash
# https://github.com/OSINTCabal/OSINTSky
pip install atproto colorama
python3 blueskyosint.py
Diseño del descubridor
Fuentes y pesos
Fuente	Peso sugerido	Señales
Búsqueda AppView	40%	Hashtag, frase, intención, recencia e idioma
Snowballing	25%	Autor relevante, mencionados, participantes de respuestas
Feeds validados	15%	Afinidad temática y volumen real en español
Starter packs	10%	Perfiles iniciales, sujetos a validación
Jetstream	10%	Alta intención inmediata y cuentas semilla confirmadas

La puntuación propuesta es:

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
0.25
⋅
𝑒
𝑠
𝑝
𝑎
𝑛
𝑜
𝑙
+
0.20
⋅
𝑖
𝑛
𝑡
𝑒
𝑛
𝑐
𝑖
𝑜
𝑛
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
0.10
⋅
𝑓
𝑟
𝑒
𝑠
𝑐
𝑢
𝑟
𝑎
score=0.30⋅afinidad+0.25⋅espanol+0.20⋅intencion+0.15⋅engagement+0.10⋅frescura

Un post debe entrar en la cola de acción solo si supera un umbral mínimo de afinidad, español e intención; si no, permanece como evidencia para ampliar perfiles y vocabulario.

Snowballing

El repositorio bluesky-datascience describe exactamente el enfoque adecuado: construir un archivo deduplicado mediante búsqueda por palabras/hashtags y, después, expandirlo por los vínculos de mención y respuesta presentes en los posts. También documenta los campos facets, embed, langs y la rehidratación mediante getPosts.
bsky
+1

Para cada post candidato, extraer:

author.did y author.handle

Menciones contenidas en facets

Autores de respuestas públicas

Hashtags presentes en facets

Idiomas declarados en langs

URI, CID, createdAt, likes, reposts y respuestas

Esto permite descubrir perfiles sin depender de que un starter pack esté actualizado.

Cuentas semilla

En lugar de una lista cerrada, el sistema debe mantener un archivo versionado con tres niveles:

text
# config/bluesky/seed_sources.yaml
seed_accounts:
  - handle: "skypacks.bsky.social"
    role: "curator"
    comment_eligible: false
    purpose: "discover_packs_and_feeds"

seed_queries:
  - "#Romantasy lang:es"
  - "#FantasíaJuvenil lang:es"
  - '"recomendaciones fantasía" lang:es'

seed_feeds:
  - "pending_manual_validation"

@skypacks.bsky.social sí es una semilla válida, pero con comment_eligible: false: sirve para descubrir packs y feeds, no como destinataria habitual de comentarios.

Las cuentas de autoras, lectoras, booktokers y editoriales deben incorporarse solo cuando el sistema haya verificado:

Actividad reciente.

Español predominante.

Afinidad real con fantasía, romantasy, YA o lectura.

Interacción pública no automatizada.

Ausencia de señales de spam o cuentas de promoción genérica.

Feeds y packs

Los feeds personalizados de Bluesky son streams generados por desarrolladores mediante el framework abierto de feed generators; pueden encontrarse desde la app y añadirse como pestañas. Skyfeed permite construir reglas con inclusiones/exclusiones, filtro de idioma, tipo de post, usuarios y ranking, por lo que es adecuado para validar manualmente una consulta antes de convertirla en un trabajo automático.
reddit
+1

Búsquedas manuales recomendadas:

text
feed lectura español
feed libros español
feed booktok español
feed fantasía
feed romantasy
feed literatura juvenil
starter pack lectura español
starter pack booktok español
starter pack fantasía español

Un feed solo debe automatizarse después de medir durante varios días:

Porcentaje de posts en español.

Porcentaje de posts realmente relacionados con lectura.

Volumen diario.

Proporción de posts con intención conversacional.

Duplicación frente a búsqueda AppView.

Plan de PR pequeñas
PR	Entregable	Relación con el repo
bluesky-discovery-taxonomy	config/bluesky/discovery_queries.yaml con hashtags, frases, exclusiones, idioma y pesos	No toca adaptadores de publicación
bluesky-seed-sources	config/bluesky/seed_sources.yaml con cuentas, feeds y packs; campos de validación y elegibilidad	Reutiliza el módulo Bluesky existente
bluesky-appview-query-runner	Job que consulta app.bsky.feed.searchPosts, pagina, filtra por idioma/fecha y guarda candidatos	Conecta con research/bluesky-feed-appview-visibility
bluesky-snowball-expansion	Extracción de autores, menciones y participantes de respuestas; deduplicación por DID	Conecta con research/native-target-candidate-ingest
bluesky-starter-pack-ingest	Ingesta de packs con trazabilidad de origen, DID y fecha de verificación	Fuente secundaria, con expiración y revalidación
bluesky-jetstream-listener	Consumidor filtrado con cursor, reconexión y cola de alta intención	Conecta con research/jetstream-v2-archive-recovery
bluesky-discovery-ranking-tests	Tests de deduplicación, idioma, intención, ranking, cursor y trazabilidad	Compatible con tests/
Tests mínimos

Deduplicación: el mismo post no debe entrar dos veces por búsqueda, feed y Jetstream.

Idioma: un post con langs=["en"] no debe clasificarse como español solo por contener #fantasía.

Fecha: since y until deben usar timestamps ISO completos, no solo fechas.

Snowballing: las menciones y respuestas deben generar candidatos de perfil, no acciones automáticas.

Trazabilidad: cada candidato debe conservar consulta, fuente, URL/URI, fecha de detección y puntuación.

Jetstream: tras una desconexión, el consumidor debe reanudar desde el último cursor sin duplicar eventos.

Seguridad de credenciales: usar app password; nunca persistir la contraseña principal ni subir credenciales al repo.

Fuentes

Repositorio espejo davidpd89/ci-sandbox-tmp

Jetstream — Bluesky Protocol Services

bluesky-social/jetstream — GitHub

brianckeegan/bluesky-datascience — GitHub

Documentación app.bsky.feed.searchPosts

Discusión ATProto sobre búsqueda por fechas

Gist: filtrado de feed por idioma

lukeslp/skymarshal-js — GitHub

bluesky-social/feed-generator — GitHub

fishttp/awesome-bluesky — GitHub

Starter Packs en español

Spanish Starter Packs

Bluesky Directory

Skypacks en Bluesky

Skyfeed
