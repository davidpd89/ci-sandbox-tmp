# Ranking de cuentas y posts en Facebook (páginas y grupos)

Fuente: informe de Perplexity (https://www.perplexity.ai/search/c7edb240-d5aa-445e-b6da-be119c717a07), generado 10/10/2026.

Investigación: señales para priorizar perfiles y posts en Facebook
Resumen

Para Facebook, el sistema ya tiene una base sólida de escaneo, cola, reciprocidad y auditoría; la mejora más rentable no es otro scraper, sino un módulo de puntuación específico para páginas y grupos que combine señales observables —tamaño y actividad del perfil, recencia del post, idioma español, afinidad temática y probabilidad de respuesta— con el action_ledger y reciprocity_stats existentes. El repo espejo ya contiene facebook_scan.py, facebook_interact.py, facebook_api.py, reciprocity.py, reply_queue.py, growth_attribution.py y score_hook.py, por lo que la propuesta debe ser un adaptador que alimente esos componentes, no una arquitectura paralela.
developers.facebook

La vía técnica más robusta es usar la Graph API oficial para páginas y posts cuando haya acceso disponible, y tratar los scrapers públicos como fuente de descubrimiento complementaria, con normalización posterior al esquema interno. La Graph API expone campos de página como followers_count y fan_count, y edges de posts y comentarios; en cambio, la API de grupos fue retirada en 2024, por lo que los grupos requieren un flujo de descubrimiento y lectura distinto.
developers.facebook
+3

Estado del repo espejo

El repo davidpd89/ci-sandbox-tmp está organizado por red y por herramientas compartidas; incluye módulos Facebook dedicados y una capa transversal de crecimiento.
developers.facebook

Componente existente	Qué aporta	Cómo debe usarse en la propuesta
tools/facebook_scan.py	Descubrimiento y normalización de candidatos de Facebook.	Ampliar con campos de scoring; no crear otro descubridor. 
developers.facebook

tools/facebook_interact.py	Interacción y ejecución de acciones.	Recibir solo candidatos ya priorizados por el nuevo ranking. 
developers.facebook

tools/facebook_api.py y meta_common.py	Capa Meta/API y utilidades comunes.	Añadir consultas de campos y edges con caché y reintentos. 
developers.facebook

tools/reciprocity.py, reciprocity_stats.py	Medición de reciprocidad.	Incorporar respuesta a comentarios, likes y follows como señal de aprendizaje. 
developers.facebook

tools/action_ledger.py, growth_attribution.py	Registro y atribución de acciones.	Guardar score, señales, acción, resultado y ventana temporal. 
developers.facebook

tools/reply_queue.py, conversation_followups.py	Cola y seguimiento conversacional.	Alimentar con posts de alta probabilidad de conversación, no solo alta viralidad. 
developers.facebook

tools/check_language_variety.py, spellcheck_es.py	Control lingüístico en español.	Reutilizarlos como filtro duro antes de proponer comentarios. 
developers.facebook

tools/score_hook.py, growth_policy.py	Puntuación y política de crecimiento.	Extender con pesos por red, sin duplicar la lógica de decisión. 
developers.facebook
Hallazgos y repositorios reutilizables
Hallazgo	Repo / fuente	Qué copiar o adaptar	Integración en el sistema	Riesgos técnicos	Tests
Cliente Python genérico para Graph API de Facebook, Instagram, páginas, grupos y eventos	
sns-sdks/python-facebook
 
github
	Patrón de cliente Graph API, manejo de objetos y edges; no sustituir facebook_api.py, solo inspirar su extensión.	Crear tools/facebook_signals.py que use la capa existente para pedir followers_count, fan_count, posts{created_time,message,comments.summary(true),reactions.summary(true)}. 
developers.facebook
+1
	Permisos y disponibilidad de campos varían por tipo de token y objeto. 
developers.facebook
+1
	Mock de Graph API; comprobar campos ausentes, paginación y errores 4xx/5xx.
Referencia oficial de Page: seguidores, fans, about y posts públicos	
Meta: Page Graph API
 
developers.facebook
	Esquema de señales de página: followers_count, fan_count, about, category, posts.	FacebookPageSignals.from_graph(payload) produce un registro normalizado compatible con facebook_scan.py.	fan_count y followers_count no son equivalentes; guardar ambos por separado. 
developers.facebook
	Unit tests con páginas grandes, pequeñas, sin about y sin posts.
Referencia oficial de comentarios: texto, autor, respuestas, likes y fecha	
Meta: Comment Graph API
 
developers.facebook
	Señales de conversación: comment_count, like_count, created_time, autor y posibilidad de respuesta.	El ranking de posts debe premiar comentarios recientes y autores activos, enviándolos a reply_queue.py.	Los datos de usuario requieren permisos adecuados y tokens de página en ciertos casos. 
developers.facebook
	Test de comentarios anidados, comentarios vacíos y autores sin nombre público.
Scraper clásico de páginas y grupos, con posts, comentarios, reacciones y hora	
kevinzg/facebook-scraper
 
github
	Estructura de campos y flujo de extracción: post_text, time, likes, comments, post_id; opciones comments y reactors.	Usarlo solo como fuente de descubrimiento; mapear a un FacebookCandidate común antes del scoring.	Proyecto antiguo y frágil frente a cambios de Facebook; no debe ser dependencia crítica. 
thunderbit
+1
	Tests de contrato: cada item scrapeado debe tener source, post_id, created_at, text, métricas opcionales.
Scraper de posts y comentarios con GraphQL, GUI, reintentos y exportación JSON	
mohdtalal3/facebook_post_comment_scraper
 
github
	Ideas de reintentos, exportación JSON y extracción de comentarios anidados.	Adaptar la lógica de normalización y persistencia; no incorporar GUI ni dependencias pesadas.	Dependencia de sesión autenticada y fragilidad de selectores/GraphQL. 
github
	Tests de export JSON, deduplicación por post_id y comentarios repetidos.
Detección rápida de idioma basada en FastText, con buen rendimiento para español	
zafercavdar/fasttext-langdetect
 
github
	Detección offline de idioma; recall de español 0,986 en el benchmark del repo.	Añadir language y language_confidence al candidato; descartar o degradar no-español antes de generar comentario.	Textos muy cortos, hashtags y nombres propios pueden confundir el detector. 
github
+1
	Tests con frases españolas, mezcla español-inglés, posts de menos de 20 caracteres y hashtags.
Analizador de engagement con características normalizadas y modelo de clasificación	
anujeshify/Social-Media-Engagement-Analyzer
 
github
	Idea de features: sentimiento, likes, compartidos, hashtags y normalización; no copiar el modelo inicial.	Crear features observables y medir su correlación con respuestas reales antes de usar ML.	Riesgo de sobreajuste con poco histórico; empezar con reglas explicables.	Backtest con datos del ledger: precision@K, recall@K y tasa de respuesta a 24/72 horas.
Analizadores de seguidores/siguiendo y cuentas no recíprocas	
developer-az/pyFollowerVsFollowing
, ridwaanhall/instagram-following-followers 
github
+1
	Concepto de ratio y detección de reciprocidad; Facebook no ofrece el mismo par seguidores/siguiendo para páginas.	Adaptar el concepto a señales disponibles: ratio entre actividad propia y engagement recibido, y respuestas históricas.	No extrapolarel “follow-back” de Instagram a páginas de Facebook. 
github
+1
	Tests de ratio con división por cero, cuentas nuevas y perfiles sin actividad.
Señales recomendadas
Señales de perfil o página

Para una página, el objetivo no es “follow-back”, sino identificar cuentas con audiencia real, actividad reciente y probabilidad de interactuar. La Graph API distingue fan_count —usuarios que dan like a la página— de followers_count; conviene registrar ambos y no mezclarlos.
developers.facebook

Señal	Fórmula o umbral inicial	Peso sugerido	Motivo
Tamaño de audiencia	log1p(followers_count)	0,10	Prioriza alcance potencial sin favorecer cuentas gigantes e inaccesibles. 
developers.facebook

Actividad reciente	Posts en 7/30 días	0,20	Una página activa ofrece más oportunidades de aparición y conversación.
Engagement por post	(reactions + comments + shares) / posts_recientes	0,20	Mide si la audiencia responde, no solo si publica.
Ratio de conversación	comments / max(1, reactions)	0,15	Los posts con muchos comentarios respecto a reacciones son mejores para responder.
Español	language == "es"	0,15	Filtra candidatos útiles para comentarios humanos en español. 
github

Afinidad temática	Coincidencia con fantasía, romantasy, lectura, escritura, libros	0,15	Evita comentarios genéricos y mejora contextualidad.
Historial de reciprocidad	Respuestas, likes o follows tras acciones previas	0,05 inicial	Aprende de resultados reales mediante growth_attribution.py. 
developers.facebook
Señales de post
Señal	Cálculo	Peso sugerido	Motivo
Frescura	Decaimiento exponencial por horas desde created_time	0,25	Los posts recientes tienen más probabilidad de que el autor vea la respuesta. La Graph API expone created_time en posts y comentarios. 
developers.facebook
+1

Comentarios recientes	Comentarios en las últimas 24–72 horas	0,20	Indica hilo vivo y autor probablemente atento. 
developers.facebook

Pregunta o apertura	Interrogación, petición de recomendaciones, “¿qué leyendo?”, etc.	0,15	Favorece respuesta conversacional en vez de like pasivo.
Afinidad semántica	Similitud con léxico de fantasía, romantasy, YA, libros	0,15	Permite comentarios específicos y humanos.
Idioma español	Detección FastText	0,10	Alineado con la estrategia de comentarios en español. 
github

Engagement moderado	Ni cero interacciones ni viralidad extrema	0,10	Los posts con participación moderada suelen ofrecer mejor ventana de visibilidad.
No respondido	Ausencia en action_ledger / cola	Filtro duro	Evita repetir acciones sobre el mismo post. 
developers.facebook
Fórmula inicial
𝑆
𝑐
𝑜
𝑟
𝑒
=
0,25
𝐹
+
0,20
𝐶
+
0,15
𝐴
+
0,15
𝑇
+
0,10
𝐿
+
0,10
𝐸
+
0,05
𝑅
Score=0,25F+0,20C+0,15A+0,15T+0,10L+0,10E+0,05R

Donde 
𝐹
F es frescura, 
𝐶
C conversación reciente, 
𝐴
A apertura conversacional, 
𝑇
T afinidad temática, 
𝐿
L idioma, 
𝐸
E engagement moderado y 
𝑅
R reciprocidad histórica. Los pesos deben vivir en growth_policy.py o en un JSON de configuración versionado, para poder ajustarlos sin tocar la lógica de ejecución.
developers.facebook

Facebook Pages frente a Groups
Dimensión	Páginas	Grupos
Descubrimiento	Más viable mediante Graph API y datos públicos de página. 
developers.facebook
	La Graph API de grupos fue retirada; el descubrimiento debe apoyarse en fuentes externas o sesiones controladas. 
upload-post
+1

Señales de perfil	followers_count, fan_count, categoría, descripción y posts. 
developers.facebook
	Nombre, tema, actividad observable y calidad de hilos; sin equivalente fiable de seguidores/siguiendo.
Señales de post	created_time, reacciones, comentarios y respuestas. 
developers.facebook
+1
	Texto, fecha, comentarios y actividad del hilo; normalizar al mismo esquema interno.
Acción prioritaria	Comentar posts recientes de páginas afines y responder comentarios propios.	Responder hilos nuevos con preguntas o recomendaciones; evitar publicar primero.
Integración	facebook_api.py + facebook_scan.py.	facebook_scan.py como ingestor y reply_queue.py como salida; sin asumir API de grupos. 
upload-post
Recomendación

Implementar un Facebook Opportunity Scorer como módulo nuevo, no como sustitución de los scripts actuales:

Nuevo archivo: tools/facebook_opportunity_scorer.py.

Entrada: candidatos procedentes de facebook_scan.py, ya sea desde Graph API o de fuentes de descubrimiento.

Salida: JSON/SQLite con profile_score, post_score, action_type, reasons, language, topic_affinity, freshness_hours y reciprocity_history.

Integración: el scorer alimenta facebook_build_plan.py y facebook_interact.py; los resultados se registran en action_ledger.py y se analizan con reciprocity_stats.py y growth_attribution.py.
developers.facebook

Prioridad de acción: primero responder comentarios propios y preguntas ajenas; después comentar posts de 0–48 horas; por último, seguir o interactuar con páginas afines activas.

Plan de implementación en PR pequeñas
PR 1 — Contrato de candidato

Crear tools/facebook_opportunity_schema.py con dataclasses o TypedDicts para FacebookProfileCandidate y FacebookPostCandidate.

Incluir campos: network="facebook", surface="page"|"group", profile_id, post_id, text, created_at, language, metrics, topic_tags, already_actioned.

Tests: validación de campos obligatorios, fechas ISO y valores nulos.

PR 2 — Señales de página y post

Crear tools/facebook_opportunity_scorer.py.

Implementar freshness_score, conversation_score, topic_affinity_score, language_score y engagement_balance_score.

Reutilizar discovery_terms.py, text_common.py y check_language_variety.py en lugar de duplicar vocabulario o validaciones.
developers.facebook

Tests: casos con post recién publicado, post de 7 días, post sin comentarios y post en inglés.

PR 3 — Ingesta Graph API para páginas

Extender facebook_api.py con una función de lectura de página y posts, con field packing y paginación.

Guardar tanto fan_count como followers_count, porque son conceptos distintos en la documentación oficial.
developers.facebook

Tests con respuestas simuladas, errores de permisos y paginación incompleta.

PR 4 — Ingesta de grupos y normalización

Añadir un adaptador de descubrimiento para grupos que produzca el mismo FacebookPostCandidate, sin acoplar el sistema a una API de grupos inexistente.

Usar kevinzg/facebook-scraper solo como referencia de campos y como fuente opcional; el sistema debe funcionar aunque la extracción falle.
github
+1

Tests de contrato y deduplicación por post_id.

PR 5 — Ranking y cola

Conectar el scorer a facebook_build_plan.py, reply_queue.py y conversation_followups.py.

Establecer límites por ronda: por ejemplo, 10 respuestas, 5 comentarios en páginas y 3 interacciones de perfil, ajustables por growth_policy.py.
developers.facebook

Tests: no duplicar post_id, respetar presupuesto diario y priorizar posts frescos.

PR 6 — Aprendizaje medido

Registrar en action_ledger.py: score previo, señales, acción, post, autor y resultado observado.

Añadir a reciprocity_stats.py métricas: respuesta del autor en 24/72 horas, like al comentario, nuevo seguidor y continuación del hilo.
developers.facebook

Crear un informe semanal con precision@10, tasa de respuesta y correlación de cada señal con resultados.

Aplicación a las demás redes

El mismo contrato debe servir para X, Threads, Bluesky, Mastodon, Instagram, Pinterest, Reddit y TikTok:

Perfil: antigüedad, actividad reciente, idioma, afinidad, ratio de interacción y reciprocidad previa.

Post: frescura, formato conversacional, engagement moderado, idioma y ausencia de acción previa.

Diferencia por red: en Pinterest prioriza guardados y afinidad visual; en Reddit, preguntas y normas del subreddit; en TikTok, comentarios recientes y creadores pequeños/medianos; en X, replies y autores activos; en Bluesky/Mastodon, interacción mutua y temas de nicho.

Beneficio: un único OpportunityScorer por señal, con adaptadores por red, evita duplicar lógica y permite comparar qué señales predicen mejor conversación en cada plataforma.

Fuentes

Repo espejo davidpd89/ci-sandbox-tmp — módulos Facebook, reciprocidad, cola de respuestas y ledger.
developers.facebook

Meta Graph API: Page
 — followers_count, fan_count, posts y metadatos.
developers.facebook

Meta Graph API: Post Comments
 — ordenación y lectura de comentarios.
developers.facebook

Meta Graph API: Comment
 — autor, texto, fecha, respuestas y likes.
developers.facebook

sns-sdks/python-facebook
 — wrapper Python para Graph API.
github

kevinzg/facebook-scraper
 — extracción de páginas, grupos, posts, comentarios y reacciones.
github

zafercavdar/fasttext-langdetect
 — detección de idioma offline con alto recall para español.
github

anujeshify/Social-Media-Engagement-Analyzer
 — referencia de features y normalización de engagement.
github

developer-az/pyFollowerVsFollowing
 y ridwaanhall/instagram-following-followers — referencia conceptual de reciprocidad y ratios.
github
+1
