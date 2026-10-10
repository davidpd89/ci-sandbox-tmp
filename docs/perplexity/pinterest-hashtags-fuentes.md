# Hashtags, fuentes y comunidades en Pinterest

Fuente: informe de Perplexity (https://www.perplexity.ai/search/bce49261-ca28-436a-8b30-a83192bbe7ae), generado 10/10/2026.

Informe mejorado: descubrimiento de lectores de fantasía/romantasy en español en Pinterest
Resumen

El informe anterior era correcto en su enfoque, pero contenía tres debilidades: mezclaba herramientas de descarga de imágenes con herramientas de descubrimiento de perfiles; proponía repos poco mantenidos o de utilidad marginal; y no incluía código verificado. Esta versión prioriza repos activos a octubre de 2026, con licencia abierta, compatibilidad Python 3.10+/3.11 y piezas concretas que pueden integrarse en pinterest_scan.py, discovery_terms.py y el ledger existente.

El repo espejo ya tiene una base Pinterest en research/perplexity-crecimiento-pinterest, con pinterest_niche.py, pinterest_scan.py, pinterest_growth.py, pinterest_boards.py, pinterest_daily_pins.py, pinterest_publish.py, discovery_terms.py y hashtag_research/. No se propone duplicar esas piezas: el objetivo es añadir fuentes de nicho, consultas en español, semillas verificadas y un adaptador de ingesta.

Correcciones al informe anterior
Elemento anterior	Decisión	Motivo
pinterest-scrapper en PyPI	Eliminado como recomendación principal	Es una alternativa válida, pero los repos activos identificados ahora ofrecen metadatos más útiles —creador, tablero, saves— y mejor encajan con descubrimiento.
xmokecursed/pinterest-scraper	Eliminado	No apareció entre los resultados activos y relevantes de la búsqueda actual; no conviene recomendarlo sin verificación de actividad.
data-scrape/pinterest-scraper	Sustituido	Existen alternativas más recientes, con licencia MIT y metadatos de pin/creador/tablero.
pinterest/api-quickstart	Conservado, con alcance reducido	Sirve para la cuenta propia y API v5, no para descubrir perfiles de terceros.
Lista inicial de hashtags	Ampliada y reorganizada	Pinterest funciona mejor con consultas temáticas y estéticas que con hashtags sueltos.
Semillas	Conservadas sólo las verificables	Se mantienen perfiles y tableros con URL pública comprobada.
Hallazgos principales
Repositorio / fuente	Actividad y licencia	Qué resolver	Qué copiar	Integración
EhsanShahbazii/Pinterest-Scraper	Python, MIT; creado el 3 de septiembre de 2026 y con último push el 8 de octubre de 2026; 11 estrellas.	Búsqueda, metadatos completos, deduplicación persistente, JSON/CSV, proxies y fingerprints.	scraper.py, dedupe.py, storage.py y config.py.	Adaptar la salida a Candidate; conservar pin_id, creator, board, saves, description y source_query.
iamatulsingh/pinscrape	Python, MIT; 153 estrellas; último push el 19 de agosto de 2026.	Búsqueda sencilla y descarga de imágenes por consulta.	pinscrape/pinscrape.py como referencia de flujo búsqueda → extracción → descarga.	Usar sólo la parte de búsqueda/extracción; descartar descarga masiva de imágenes salvo para análisis visual.
sean1832/pinterest-dl	Python, Apache-2.0; 207 estrellas; último push el 14 de julio de 2026; disponible en PyPI.	Descarga de medios y automatización con Selenium.	CLI y manejo de medios; no es la mejor base para ranking social.	Útil como respaldo para archivar referencias visuales, no como núcleo de descubrimiento.
mirusu400/Pinterest-infinite-crawler	Python, MIT; 95 estrellas; último push el 11 de mayo de 2026.	Crawler con scroll infinito.	Lógica de scroll y recolección progresiva.	Añadir límites por ronda y persistencia antes de reutilizar.
shaikhsajid1111/social-media-profile-scrapers	Python, Apache-2.0; 580 estrellas; último push el 15 de septiembre de 2026.	Scrapers multiplataforma, incluido Pinterest.	Patrón común de perfil/extractor multi-red.	Referencia para homogeneizar el esquema de candidato entre Pinterest y otras redes.

Pinterest Trends
	Fuente oficial, mercado España. 
trends.pinterest
	Tendencias reales por país.	No hay código que copiar; sí un origen de trending_terms.	Ingerir semanalmente términos y cruzarlos con el vocabulario de fantasía/lectura.

Pinterest Trends API
	API oficial para Trends & Insights; orientada a clientes Enterprise/partners. 
pypi
	Términos en crecimiento, volumen relativo y cambios semanales/mensuales/anuales.	Cliente oficial si se dispone de acceso.	Si no hay acceso, usar la web de Trends como fuente manual o semanal.
Código reutilizable verificado

No incluyo bloques presentados como “copiables tal cual” si no he podido extraer y verificar el texto exacto del archivo: el conector confirmó la existencia y SHA de los ficheros, pero no devolvió su contenido, y los intentos de lectura vía web fallaron. Para evitar introducir código inventado, dejo las rutas exactas y el patrón de integración; el código debe copiarse desde esos archivos concretos.

Pieza 1 — Scraper activo con metadatos

Repositorio: https://github.com/EhsanShahbazii/Pinterest-Scraper
Archivo recomendado: src/pinterest_scraper/scraper.py
Licencia: MIT.

python
# URL exacta del archivo de origen:
# https://github.com/EhsanShahbazii/Pinterest-Scraper/blob/main/src/pinterest_scraper/scraper.py
# Copiar desde el archivo original; este bloque es una guía de integración, no una reproducción verificada.

from dataclasses import dataclass

@dataclass
class PinterestCandidate:
    pin_id: str
    pin_url: str
    title: str | None
    description: str | None
    creator_username: str | None
    creator_url: str | None
    board_name: str | None
    board_url: str | None
    saves: int | None
    image_url: str | None
    source_query: str
    source_type: str  # search | board | idea | profile
    discovered_at: str

Integración: este modelo debe alimentar candidate_identity.py y action_ledger.py. El campo source_query es imprescindible para medir qué búsqueda produce mejores candidatos.

Pieza 2 — Deduplicación persistente

Repositorio: https://github.com/EhsanShahbazii/Pinterest-Scraper
Archivo recomendado: src/pinterest_scraper/dedupe.py
Licencia: MIT.

python
# URL exacta del archivo de origen:
# https://github.com/EhsanShahbazii/Pinterest-Scraper/blob/main/src/pinterest_scraper/dedupe.py
# Reutilizar la implementación original; aquí sólo se define el contrato que debe cumplir nuestro adaptador.

def is_new_candidate(pin_id: str, seen_store) -> bool:
    return not seen_store.contains(pin_id)

def mark_seen(pin_id: str, seen_store) -> None:
    seen_store.add(pin_id)

Integración: sustituir el almacenamiento en memoria por el mecanismo de estado ya existente en el repo, para evitar reprocesar pines entre rondas.

Pieza 3 — Flujo de búsqueda de pinscrape

Repositorio: https://github.com/iamatulsingh/pinscrape
Archivo recomendado: pinscrape/pinscrape.py
Licencia: MIT.

python
# URL exacta del archivo de origen:
# https://github.com/iamatulsingh/pinscrape/blob/main/pinscrape/pinscrape.py
# Consultar el archivo original para el código literal; este esqueleto define la integración.

def discover_by_query(query: str, limit: int = 25):
    """
    Entrada: consulta en español, por ejemplo 'romantasy libros español'.
    Salida: lista de pines con URL, imagen y metadatos disponibles.
    """
    ...

Integración: útil como fallback si el scraper principal cambia sus selectores. No debe usarse para descargar imágenes masivamente: el objetivo es descubrir perfiles, tableros y pines relevantes.

Vocabulario de descubrimiento en español
Consultas núcleo

romantasy libros

libros romantasy español

romantasy recomendaciones

fantasía juvenil libros

libros de fantasía en español

fantasía épica libros

libros de magia y romance

enemigos a amantes libros

romance oscuro libros

dark romance fantasía

libros de hadas y romance

fae romance libros

dragones y romance libros

libros de brujas romance

sagas de fantasía juvenil

libros parecidos a ACOTAR

libros parecidos a Crescent City

Comunidad lectora

reto de lectura 2026

recomendaciones libros 2026

TBR 2026

lista de libros pendientes

bookstagram español

booktok español

lectura juvenil recomendaciones

libros juveniles recomendados

novelas juveniles fantasía

club de lectura fantasía

reseñas de libros fantasía

frases de libros fantasía

citas de libros romantasy

Estética y formato Pinterest

wallpaper libros fantasía

estética libros fantasía

moodboard romantasy

fanart libros fantasía

ilustración de libro fantasía

citas literarias fantasía

marcadores de lectura diy

ideas para lectores

regalos para lectores

rincón de lectura fantasía

estantería libros aesthetic

Semillas verificadas
Tipo	Semilla	URL	Uso
Tablero	familiamzc/romantasy	
https://es.pinterest.com/familiamzc/romantasy/
	Romantasy, libros y club de lectura.
Tablero	inmasanchezrios/romantasy	
https://es.pinterest.com/inmasanchezrios/romantasy/
	Romantasy, fanart, ilustración y novelas.
Tablero	alejandram1215/romantasy	
https://ar.pinterest.com/alejandram1215/romantasy/
	Romantasy y lectura; validar idioma antes de priorizar.
Tablero	elidarodriguezs/libros	
https://es.pinterest.com/elidarodriguezs/libros/
	Libros y novelas; amplía hacia lectoras generalistas.
Tablero	csc31416/libros	
https://es.pinterest.com/csc31416/libros/
	Libros, novela histórica y lectura.
Tablero	liannekayauthor/romantasy-books-with-spice	
https://es.pinterest.com/liannekayauthor/romantasy-books-with-spice/
	Subnicho romantasy con contenido adulto; pasar por adult_filter.py.
Idea	“Libros Romantasy”	
https://es.pinterest.com/ideas/libros-romantasy/938706688404/
	Descubrimiento de tableros y términos conexos.
Idea	“Romantasy libros”	
https://es.pinterest.com/ideas/romantasy-libros/904984137497/
	Pines, listas y retos relacionados.
Idea	“Reto de lectura 2026”	
https://es.pinterest.com/ideas/reto-de-lectura-2026/894274813752/
	Lectores activos en retos anuales.
Trends	Pinterest Trends España	
https://trends.pinterest.com/?country=ES
	Tendencias oficiales del mercado español. 
trends.pinterest
Búsquedas para ampliar semillas

site:es.pinterest.com "romantasy" "libros"

site:es.pinterest.com "fantasía juvenil" "libros"

site:es.pinterest.com "bookstagram" "romantasy"

site:es.pinterest.com "booktok" "fantasía"

site:es.pinterest.com "reto de lectura" "fantasía"

site:es.pinterest.com "enemigos a amantes" "libros"

site:es.pinterest.com "libros de brujas" "romance"

site:es.pinterest.com "saga de fantasía" "español"

Recomendación

Implementar un adaptador de descubrimiento Pinterest en español con tres fuentes:

Búsqueda por consultas usando EhsanShahbazii/Pinterest-Scraper como referencia principal.

Tableros e ideas semilla para extraer autores, pines relacionados y tableros conexos.

Pinterest Trends España para refrescar términos con demanda real.

La pieza más valiosa es conservar, para cada candidato, la trazabilidad completa: query, seed, source_type, pin_id, creator, board, saves y fecha de descubrimiento. Sin esa trazabilidad, el ranking posterior no podrá aprender qué búsquedas producen interacciones reales.

Plan de implementación en PR pequeñas
PR 1 — Configuración de descubrimiento

Crear config/pinterest_discovery_es.yaml.

Incluir consultas, semillas, pesos y límites por ronda.

No modificar publicación ni interacción.

Tests: esquema YAML, URLs únicas, categorías permitidas y límite de consultas.

PR 2 — Modelo de candidato Pinterest

Crear tools/pinterest_candidate.py con PinterestCandidate.

Mapear campos hacia el modelo común de candidatos.

Tests: serialización, campos obligatorios y deduplicación por pin_id.

PR 3 — Ingesta desde búsquedas

Extender tools/pinterest_scan.py para aceptar source_type=search.

Integrar la salida del scraper activo como adaptador, no como dependencia rígida.

Tests: fixture HTML/JSON, campos mínimos, errores de red y límite de resultados.

PR 4 — Ingesta desde tableros e ideas

Añadir source_type=board|idea|profile.

Extraer creadores, tableros relacionados y pines conexos.

Tests: normalización de usernames, rechazo de perfiles fuera de nicho y control de profundidad.

PR 5 — Ranking y aprendizaje

Puntuar por: español detectado, relevancia de fantasía/romantasy, recencia, interacciones visibles y ausencia de acción previa.

Registrar en action_ledger.py la fuente y el score.

Tests: reproducibilidad, idempotencia y auditoría de decisiones.

Aplicación multi-red

El mismo archivo de descubrimiento puede alimentar las demás redes con esta estructura:

text
themes:
  romantasy:
    query_es: "romantasy libros"
    x: "romantasy libros español"
    threads: "romantasy libros"
    facebook: "grupos lectura romantasy"
    pinterest: "romantasy libros"
    reddit: "r/RomantasyBooks romantasy español"
    bluesky: "romantasy libros"
    mastodon: "romantasy libros"
    tiktok: "#BookTokEspañol romantasy"
    instagram: "#BookstagramEspañol romantasy"

Así se mantiene una única intención de nicho —“lectoras de romantasy en español”— y cada adaptador la traduce a su formato nativo.

Fuentes

Repo espejo y rama Pinterest: https://github.com/davidpd89/ci-sandbox-tmp/tree/research/perplexity-crecimiento-pinterest

EhsanShahbazii/Pinterest-Scraper: https://github.com/EhsanShahbazii/Pinterest-Scraper

iamatulsingh/pinscrape: https://github.com/iamatulsingh/pinscrape

sean1832/pinterest-dl: https://github.com/sean1832/pinterest-dl

mirusu400/Pinterest-infinite-crawler: https://github.com/mirusu400/Pinterest-infinite-crawler

shaikhsajid1111/social-media-profile-scrapers: https://github.com/shaikhsajid1111/social-media-profile-scrapers

Pinterest API v5: 
https://developers.pinterest.com/docs/api/v5/introduction/

Pinterest Trends API: 
https://developers.pinterest.com/docs/analytics-and-reports/trends/
pypi

Pinterest Trends España: 
https://trends.pinterest.com/?country=ES
trends.pinterest

Pinterest API quickstart: 
https://github.com/pinterest/api-quickstart

Idea “Libros Romantasy”: 
https://es.pinterest.com/ideas/libros-romantasy/938706688404/

Idea “Romantasy libros”: 
https://es.pinterest.com/ideas/romantasy-libros/904984137497/

Idea “Reto de lectura 2026”: 
https://es.pinterest.com/ideas/reto-de-lectura-2026/894274813752/

Tablero familiamzc/romantasy: 
https://es.pinterest.com/familiamzc/romantasy/

Tablero inmasanchezrios/romantasy: 
https://es.pinterest.com/inmasanchezrios/romantasy/

Tablero alejandram1215/romantasy: 
https://ar.pinterest.com/alejandram1215/romantasy/

Tablero elidarodriguezs/libros: 
https://es.pinterest.com/elidarodriguezs/libros/

Tablero csc31416/libros: 
https://es.pinterest.com/csc31416/libros/

Tablero liannekayauthor/romantasy-books-with-spice: 
https://es.pinterest.com/liannekayauthor/romantasy-books-with-spice/
