# Herramientas y código abierto en Pinterest

Fuente: informe de Perplexity (https://www.perplexity.ai/search/33f1b088-3665-48ba-9884-9d812b11c39d), generado 10/10/2026.

Investigación Pinterest: repos, SDK y agentes útiles (10/10/2026)
Resumen

Tu repo ya tiene una base Pinterest sólida y no conviene sustituirla: pinterest_growth.py ya implementa descubrimiento por búsquedas, filtrado en español/nicho, asignación de tableros, planificación, ejecución con Playwright/CDP, comentarios vía reply_queue, registro anti-duplicado y detención ante avisos. La mejora de mayor valor no es otro bot de interacción, sino añadir medición oficial de resultados, descubrimiento de keywords/tendencias, y una capa de ranking/aprendizaje que use las métricas reales para reordenar consultas, formatos y tableros.
pypi
+2

Estado actual del espejo

El repositorio davidpd89/ci-sandbox-tmp contiene un ecosistema Pinterest ya integrado: pinterest_growth.py, pinterest_daily_pins.py, pinterest_publish.py, pinterest_boards.py, pinterest_api_audit.py, pinterest_profile_audit.py y pinterest_scan.py.
pypi

pinterest_growth.py cubre:

Búsqueda de pines por un pool rotatorio de consultas en español, con 8 consultas por ronda y 8 pines por consulta.
pypi

Filtrado por idioma, nicho literario/fantasía, contenido comercial y señales de bots.
pypi

Acciones de reaccionar, guardar, seguir y comentar, con registro CSV y exclusiones de acciones ya realizadas.
pypi

Asignación automática de tablero según el contenido del pin: fantasía juvenil, lugares literarios, recursos para escritores y lecturas.
pypi

Ejecución sobre Edge mediante Playwright CDP en 127.0.0.1:9223, con pausas humanas y parada ante captcha o avisos.
pypi

Por tanto, no propondría duplicar scraping básico, publicación simple, creación de tableros ni un nuevo ejecutor de interacciones. Lo que falta es convertir el sistema en un bucle de aprendizaje medible.

Hallazgos aprovechables
Hallazgo	Repo / fuente	Qué copiar	Integración en el sistema	Riesgos técnicos	Tests
SDK oficial Python de Pinterest	
pinterest/pinterest-python-sdk
	Cliente OAuth, gestión de tokens, errores y llamadas a la API v5. El SDK oficial se centra hoy en gestión de campañas y autenticación. 
github
+1
	Crear tools/pinterest_official_client.py como adaptador fino: cargar token desde variables de entorno, refrescar token y exponer funciones de analítica. No acoplarlo al ejecutor de navegador.	El SDK oficial no cubre todavía todo el flujo orgánico; su README indica que funcionalidades orgánicas, shopping y analítica se irán añadiendo. 
github
+1
	test_oauth_refresh, test_api_error_mapping, test_no_token_in_logs
Cliente generado API v5	
pinterest/pinterest-python-generated-api-client
	Modelos y métodos generados: PinsApi, BoardsApi, UserAnalyticsApi, PinsApi.pins_analytics, multi_pins_analytics y KeywordsApi. 
github
	Copiar solo los modelos/llamadas necesarios para leer métricas de pines propios y métricas de keywords; envolverlas en pinterest_metrics.py.	Es un cliente generado, más verbose que el SDK; Pinterest recomienda usar su SDK como capa principal. 
github
	Fixture JSON de respuesta; test de parsing de impresiones, guardados, clics salientes y fecha
Quickstart oficial	
pinterest/api-quickstart
	Ejemplos de OAuth, autorización y patrones de llamada en Python. 
github
	Usarlo como referencia para pinterest_auth.py y para un comando pinterest_growth.py metrics.	Es material de ejemplo, no una librería lista para producción. 
github
	Smoke test con token de prueba; test de expiración
Scraper estructurado de pines, tableros y perfiles	
data-scrape/pinterest-scraper
	Esquema de campos y exportación: pin_id, título, descripción, imagen, tablero, autor, repins, saves, enlace y fecha. 
github
	No copiar el scraper completo: tu scan_common.py y pinterest_growth.py ya hacen descubrimiento. Copiar el modelo de datos para enriquecer pinterest_candidates.json con métricas públicas y metadatos de imagen.	Dependencia de selectores cambiantes; puede chocar con tu detección de avisos si se usa otro navegador. 
github
	Test de normalización de campos; test de deduplicación por pin_id
Scraper Scrapy con spiders separados	
Simple-Python-Scrapy-Scrapers/pinterest-scrapy-scraper
	Separación en spiders de búsqueda, pin individual y tablero; export CSV; campos de engagement, etiquetas, categorías y color dominante. 
github
	Inspirarse en su descomposición para dividir tu cmd_scan() en discover, enrich, classify y rank, sin migrar a Scrapy.	Scrapy añade dependencias y proxies; no encaja con tu arquitectura Playwright/CDP actual. 
github
	Tests unitarios por spider lógico; test de max_results y export
Automatización de publicación masiva	
SoCloseSociety/PinterestBulkPostBot
	Diseño de importación CSV, cola de pins, campos de tablero/título/descripción/enlace y programación. Licencia MIT según su README. 
github
	Añadir un formato pins_queue.csv compatible con pinterest_daily_pins.py, pero reutilizando tu validación de idioma, nicho y duplicados.	Usa Selenium; tu stack ya es Playwright, así que solo copiar el modelo de datos y la lógica de cola, no el navegador. 
github
	Test de CSV inválido; test de programación; test de duplicados
Ejemplo oficial de creación programada de pins	
9-shen/pinterest-pin-creator-go
	Formato de planificación: created;timestamp;board;title;description;filePath;link. 
github
	Adoptar un esquema equivalente en JSON/CSV para pinterest_daily_pins.py, conservando tu validación editorial.	Está en Go y usa API v5; sirve como referencia de contrato, no como código a portar directamente. 
github
	Test de campos obligatorios; test de fecha futura/pasada
MCP de publicación Pinterest	
postoncehq/pinterest-mcp
	Patrón de herramientas MCP para publicar, programar y gestionar pins, carruseles y vídeos mediante API oficial. 
github
	Opcional a medio plazo: exponer create_pin, schedule_pin, list_boards y get_pin_metrics como herramientas internas para que ChatGPT/Codex pueda operar Pinterest sin tocar el navegador.	Repositorio con muy pocas estrellas; mejor tomar el patrón de interfaz que depender del código. 
github
	Test de contrato MCP; test de autorización; test de idempotencia
Descubrimiento de tendencias y tableros	
awesomelistsio/awesome-pinterest
	Referencia de herramientas oficiales: Pinterest Trends y Pinterest Analytics. 
github
	Añadir pinterest_trends.py para registrar semanalmente tendencias y mapearlas a tus tableros y consultas.	No es código ejecutable, sino un índice curado. 
github
	Test de normalización de términos; test de asignación a tablero
Comparativa
Opción	Mantenimiento / encaje	Valor para David	Veredicto
pinterest-python-sdk oficial	Repositorio oficial; actualizado en 2026 según el índice de temas. 
github
	Alta para auth, errores y futuras métricas oficiales.	Adoptar como capa API.
pinterest-python-generated-api-client	Última versión listada: 0.1.10, marzo de 2025. 
github
	Alta para leer analítica de pines y keywords sin implementar REST a mano.	Adoptar selectivamente.
pinterest-api de PyPI	Publicado originalmente en 2019; versión 0.0.8. 
pypi
	Baja: API antigua y mantenimiento dudoso frente al SDK oficial.	Descartar.
py3-pinterest	Cliente no oficial “fully fledged”, pero con origen en 2019. 
github
	Baja para producción; puede servir como referencia de endpoints no oficiales.	Descartar como dependencia.
data-scrape/pinterest-scraper	Actualizado en agosto de 2026 y enfocado a extracción estructurada. 
github
	Media-alta para enriquecer candidatos con metadatos y métricas públicas.	Copiar esquema, no integrar completo.
PinterestBulkPostBot	Actualizado en junio de 2026; Python + Selenium, MIT. 
github
+1
	Media para colas y publicación masiva.	Copiar contrato CSV/cola, no Selenium.
pinterest-mcp	Muy reciente pero con solo 2 estrellas. 
github
	Media futura para agentes de código.	Vigilar; adoptar patrón, no dependencia.
Recomendación

Implementar una arquitectura de cuatro capas, reutilizando lo existente:

Descubrimiento: mantener pinterest_growth.py scan, pero ampliar los candidatos con métricas públicas, color dominante, formato, idioma, tablero y consulta de origen.

Publicación: mantener pinterest_daily_pins.py y pinterest_publish.py; estandarizar la cola en un esquema único compatible con CSV y JSON.

Medición oficial: añadir pinterest_metrics.py sobre el SDK/cliente generado, para guardar diariamente impresiones, guardados, clics salientes y resultados por pin.

Ranking y aprendizaje: añadir pinterest_ranker.py, que puntúe consultas, tableros, formatos y horarios según resultados reales, y alimente de vuelta el QUERY_POOL y el plan del día.

La clave es que Pinterest deje de ejecutar acciones “a ciegas”: cada pin publicado debe tener un content_id, y cada interacción debe poder relacionarse después con métricas oficiales.

Plan de implementación en PR pequeñas
PR 1 — Contrato de datos Pinterest

Crear tools/pinterest_schema.py.

Definir dataclasses o TypedDict para PinterestCandidate, PinterestAction, PinterestPublishedPin y PinterestMetrics.

Campos mínimos: pin_id, url, title, description, board, author, query, language, niche, format, image_url, published_at, metrics.

No cambiar todavía el comportamiento de pinterest_growth.py.

Tests: validación de esquema, campos obligatorios, URLs duplicadas y normalización de texto en español.

PR 2 — Métricas oficiales

Crear tools/pinterest_metrics.py.

Instalar pinterest-api-sdk solo si la versión disponible cubre los endpoints necesarios; si no, usar el cliente generado como referencia de contratos.
github
+1

Comandos:

python tools/pinterest_metrics.py fetch --since 7d

python tools/pinterest_metrics.py sync

Guardar salida en SISTEMA_DIARIO_PINTEREST/metricas_oficiales.jsonl.

Relacionar cada registro con pin_id, board, query, format y campaña/contenido.

Tests: mock de API, token ausente, token expirado, respuesta parcial y idempotencia del JSONL.

PR 3 — Ranking de consultas y tableros

Crear tools/pinterest_ranker.py.

Puntuación inicial:

𝑠
𝑐
𝑜
𝑟
𝑒
=
0.35
⋅
𝑠
𝑎
𝑣
𝑒
𝑠
+
0.30
⋅
𝑜
𝑢
𝑡
𝑏
𝑜
𝑢
𝑛
𝑑
_
𝑐
𝑙
𝑖
𝑐
𝑘
𝑠
+
0.20
⋅
𝑖
𝑚
𝑝
𝑟
𝑒
𝑠
𝑠
𝑖
𝑜
𝑛
𝑠
+
0.15
⋅
𝑐
𝑙
𝑜
𝑠
𝑒
𝑢
𝑝
_
𝑟
𝑎
𝑡
𝑒
score=0.35⋅saves+0.30⋅outbound_clicks+0.20⋅impressions+0.15⋅closeup_rate

Agrupar por query, board, format y franja horaria.

Generar SISTEMA_DIARIO_PINTEREST/ranking.json.

Modificar day_queries() para priorizar, sin eliminar, las consultas con mejor histórico: por ejemplo, 60% consultas ganadoras, 30% exploración y 10% nuevas.

Tests: ranking determinista con datos sintéticos, empates, consultas sin métricas y rotación mínima.

PR 4 — Cola de publicación unificada

Crear tools/pinterest_queue_schema.py.

Unificar la entrada de pinterest_daily_pins.py y pinterest_publish.py en SISTEMA_DIARIO_PINTEREST/pins_queue.jsonl.

Campos: scheduled_at, board, title, description, image_path, link, alt_text, source, content_id, status.

Añadir validación previa: español, nicho, no comercial, imagen existente, tablero válido y ausencia de duplicado por hash de imagen o título normalizado.

Tests: CSV/JSONL válido e inválido, duplicados, imagen inexistente, fecha pasada y tablero desconocido.

PR 5 — Auditoría semanal automática

Ampliar pinterest_api_audit.py o crear pinterest_weekly_review.py.

Informe semanal en Markdown:

Mejores consultas.

Mejores tableros.

Mejores formatos: imagen estática, carrusel, vídeo.

Pines con mejor CTR y guardados.

Consultas que deben rotarse fuera.

Acciones sugeridas para la siguiente semana.

Guardar en SISTEMA_DIARIO_PINTEREST/informes/.

Tests: generación de informe con datos vacíos, datos incompletos y varias semanas.

Aplicación a las demás redes

El mismo patrón es directamente reutilizable:

X, Threads, Bluesky y Mastodon: sustituir “pin” por post; medir impresiones, respuestas, reposts/boosts, clics y seguidores nuevos; rankear consultas, formatos y horarios.

Facebook e Instagram: usar meta_insights.py ya existente como fuente de métricas y aplicar el mismo ranker por formato: carrusel, reel, story o post estático.

Reddit: rankear subreddits, tipos de post y horarios; el equivalente al guardado de Pinterest es la tasa de upvotes/comentarios.

TikTok: rankear hooks, duraciones, formatos y sonidos; el descubrimiento debe alimentar un banco de hooks validados.

Pinterest: es la red donde el ciclo es más natural porque el pin tiene vida larga; una buena métrica debe ponderar resultados a 7, 30 y 90 días, no solo el primer día.

Fuentes

Repo espejo inspeccionado: davidpd89/ci-sandbox-tmp, carpeta tools/ y tools/pinterest_growth.py.
pypi

SDK oficial Python: 
https://github.com/pinterest/pinterest-python-sdk
github

Documentación oficial del SDK: 
https://developers.pinterest.com/docs/developer-tools/sdk/
developers.pinterest

Cliente generado API v5: 
https://github.com/pinterest/pinterest-python-generated-api-client
github

Quickstart oficial: 
https://github.com/pinterest/api-quickstart
github

Scraper estructurado: 
https://github.com/data-scrape/pinterest-scraper
github

Scraper Scrapy: 
https://github.com/Simple-Python-Scrapy-Scrapers/pinterest-scrapy-scraper
github

Bot de publicación masiva: 
https://github.com/SoCloseSociety/PinterestBulkPostBot
github

Tema pinterest-automation: 
https://github.com/topics/pinterest-automation
github

Índice de herramientas y tendencias: 
https://github.com/awesomelistsio/awesome-pinterest
github
