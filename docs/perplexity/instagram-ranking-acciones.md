# Ranking de cuentas y posts en Instagram

Fuente: informe de Perplexity (https://www.perplexity.ai/search/142a7779-583e-49b9-816d-08502d88d69a), generado 10/10/2026.

Informe mejorado: señales para decidir a quién seguir y qué posts responder en Instagram

Resumen: El informe anterior incluía repos poco relevantes o de dudosa utilidad para este sistema. Esta versión los elimina —especialmente el scraper Selenium genérico y el analizador de engagement sin mantenimiento claro— y se centra en tres componentes públicos, activos y directamente aprovechables: Instaloader para señales de perfil/post, instagrapi para descubrimiento por hashtag y fasttext-langdetect para idioma. El repo espejo ya dispone de la mayor parte de la infraestructura necesaria, por lo que la mejora correcta es una capa común de puntuación, no un nuevo scanner.

Hallazgos
Repositorio	Estado y encaje	Qué copiar	Cómo integrarlo	Riesgos	Tests

instaloader/instaloader
	Activo: 13,5k estrellas, 1,6k forks, 976 commits; MIT. Expone perfiles, posts, captions, comentarios, hashtags y reanudación de descargas. 
github
	Patrones de ingesta incremental, metadatos de post y manejo de sesión; no conviene copiar su CLI completo.	Adaptador opcional instagram_signal_adapter.py que convierta perfiles/posts a un esquema común de señales.	Dependencia de sesión y cambios de Instagram; no debe acoplarse a la ejecución de comentarios.	Fixtures JSON de perfiles y posts; campos ausentes; deduplicación por shortcode/pk.

subzeroid/instagrapi
	Activo y mantenido; MIT. Expone hashtag_medias_recent(), hashtag_medias_top(), hashtag_medias_paginated(), perfiles, comentarios y seguidores. 
github
+2
	Llamadas de descubrimiento por hashtag y paginación con cursor.	Fuente complementaria para discovery_terms.py: obtener candidatos recientes y top, calcular antigüedad y afinidad antes de responder.	API privada; cantidades altas pueden provocar LoginRequired, según issues públicos. 
github
	Mock de cliente; límites de amount; posts sin caption; cursor inválido; reintento controlado.

zafercavdar/fasttext-langdetect
	Activo: 173 estrellas, 20 forks, MIT; Python 3.9–3.13 y Windows sin toolchain C++. 
instagrapi
	Detección de idioma offline mediante FastText lid.176.	Módulo language_signal.py para puntuar bio, caption y comentarios en español; complementa check_language_variety.py.	Textos muy cortos, hashtags y emojis pueden dar señales débiles; combinar varias fuentes textuales.	Español, inglés, portugués, texto vacío, texto mixto y posts sin caption.

LlmKira/fast-langdetect
	Alternativa rápida basada en FastText; soporta Python 3.9–3.14 y modelo offline ligero. 
github
+1
	Solo como alternativa si fasttext-langdetect diera problemas de dependencias.	Misma interfaz: detect_language(text) -> (lang, confidence).	Menos evidencia pública de adopción que la alternativa elegida.	Mismos tests de idioma; comparar precisión en captions cortos.

Descartes respecto al informe anterior:

xlastfire/Instagram-Hashtag-Scraper: se elimina. Usa Selenium y BeautifulSoup, pero su enfoque es frágil, depende de selectores y no aporta nada que instagram_scan.py, browser_common.py y browser_pool.py no puedan resolver mejor dentro del sistema.

anujeshify/Social-Media-Engagement-Analyzer: se elimina. Es un notebook de análisis, no una pieza reutilizable ni mantenida para producción; no aporta un mecanismo verificable de ranking de perfiles o posts.

Enlaces genéricos a topics de GitHub: se eliminan como “hallazgos”. Solo sirven para descubrimiento manual, no como componentes integrables.

Ratio seguidores/siguiendo como señal principal: se degrada. Es útil como filtro, pero no debe dominar el score: una cuenta puede tener un ratio aparentemente sano y seguir sin conversar ni publicar contenido afín.

Código reutilizable
Descubrimiento por hashtag

Este es el patrón más útil para encontrar posts recientes y top dentro del nicho. Debe alimentar una cola de candidatos, no ejecutar respuestas directamente.

python
# https://github.com/subzeroid/instagrapi — README / guía de uso
from instagrapi import Client

cl = Client()
cl.login(USERNAME, PASSWORD)
target_id = cl.user_id_from_username("target_user")
posts = cl.user_medias(target_id, amount=10)
for media in posts:
    # download photos to the current folder
    cl.photo_download(media.pk)

Fuente exacta: <https://github.com/subzeroid/instagrapi>.
subzeroid

Para descubrimiento, la parte relevante es la API de hashtags documentada por el proyecto:

python
# https://subzeroid.github.io/instagrapi/usage-guide/hashtag.html
hashtag_medias_top(name: str, amount: int = 9) -> List[Media]
hashtag_medias_recent(name: str, amount: int = 27) -> List[Media]
hashtag_medias_paginated(
    name: str,
    amount: int = 27,
    tab_key: str = "recent",
    end_cursor: str | None = None,
) -> Tuple[List[Media], str]

Fuente exacta: <https://subzeroid.github.io/instagrapi/usage-guide/hashtag.html>.
github

Antigüedad del post

La antigüedad debe calcularse siempre respecto de collected_at, no respecto de la fecha de ejecución posterior. Esto evita que un post recogido hace tres días parezca fresco si se procesa más tarde.

python
# Pieza nueva para tools/growth_signals_schema.py
from datetime import datetime, timezone
from typing import Any

def post_age_hours(post: dict[str, Any], now: datetime | None = None) -> float:
    """Calcula la antigüedad de un post en horas usando taken_at y collected_at."""
    now = now or datetime.now(timezone.utc)
    taken_at = datetime.fromisoformat(post["taken_at"]).astimezone(timezone.utc)
    collected_at = datetime.fromisoformat(post["collected_at"]).astimezone(timezone.utc)
    return max(0.0, (collected_at - taken_at).total_seconds() / 3600)

Esta función es nueva, pero resuelve una carencia real: el repo ya tiene ramas y trabajo previo sobre post-age, incluida ci/post-age-policy, por lo que debe integrarse con esa política en vez de duplicarla.

Idioma español

fasttext-langdetect es la opción más adecuada para Windows y Python 3.11: funciona offline, no requiere NumPy ni toolchain C++, y detecta español con recall de 0,986 en el benchmark publicado por el propio repositorio.
instagrapi

python
# https://github.com/zafercavdar/fasttext-langdetect — README
from ftlangdetect import detect

result = detect(text="Bugün hava çok güzel", low_memory=False)
print(result)
# {'lang': 'tr', 'score': 1.0}

result = detect(text="Bugün hava çok güzel", low_memory=True)
print(result)
# {'lang': 'tr', 'score': 0.9982126951217651}

Fuente exacta: <https://github.com/zafercavdar/fasttext-langdetect>.
instagrapi

Para texto bilingüe o mezclado —frecuente en captions de Bookstagram— conviene pedir varios candidatos:

python
# https://github.com/zafercavdar/fasttext-langdetect — README
from ftlangdetect import detect

text = "The quick brown fox. Le chat dort sur le canapé."
results = detect(text=text, low_memory=False, k=3)
print(results)
# [
#   {'lang': 'fr', 'score': 0.71},
#   {'lang': 'en', 'score': 0.27},
#   {'lang': 'de', 'score': 0.005},
# ]

Fuente exacta: <https://github.com/zafercavdar/fasttext-langdetect>.
instagrapi

Ingesta incremental

Instaloader es útil como referencia para no volver a procesar siempre los mismos perfiles: su modo --fast-update se detiene al encontrar contenido ya descargado y --latest-stamps guarda la última fecha de descarga por perfil.
github

bash
# https://github.com/instaloader/instaloader — README
instaloader --fast-update profile [profile ...]

instaloader --latest-stamps -- profile [profile ...]

Fuente exacta: <https://github.com/instaloader/instaloader>.
github

Para nuestro sistema, la idea aprovechable es el cursor de última ingesta por perfil y fuente, no el uso del binario CLI. instagram_scan.py debe guardar last_collected_at por source, hashtag o profile, y solo pedir contenido posterior.

Señales finales
Perfil para seguir
Señal	Peso	Regla práctica
Actividad reciente	25	Post en los últimos 7 días; 3–10 posts en 30 días es el intervalo óptimo
Reciprocidad previa	20	Ha comentado, reaccionado, respondido o seguido; usar reciprocity_stats.py
Afinidad temática	20	Fantasía, romantasy, YA, lectura, escritura, Bookstagram, tropes, personajes
Idioma español	15	Bio, captions y comentarios detectados como español
Relación seguidores/siguiendo	10	Filtro de sanidad; nunca criterio principal
Calidad conversacional	10	Comentarios largos, preguntas, réplicas y participación real

El sistema ya contiene reciprocity.py, reciprocity_stats.py, relationship_policy.py, candidate_identity.py, discovery_terms.py, growth_core.py, growth_policy.py y growth_attribution.py; por tanto, el nuevo módulo debe consumir esas señales, no reimplementarlas.

Post para responder
Señal	Peso	Regla práctica
Frescura	30	Prioridad a menos de 24–48 horas; decaimiento progresivo después
Afinidad	25	Caption relacionado con fantasía, romantasy, YA, libros o escritura en español
Capacidad de conversación	20	Pregunta, dilema, opinión, recomendación solicitada o comentario discutible
Engagement conversacional	15	Comentarios reales proporcionales a likes; los likes solos no bastan
Potencial de reciprocidad	10	Autor activo, respuestas previas o procedencia de una fuente con buena conversión
Recomendación

Crear tools/instagram_growth_score.py como única capa de decisión. Debe leer las salidas normalizadas de instagram_scan.py, instagram_commenters_scan.py, reciprocity_stats.py, discovery_terms.py y growth_attribution.py, y generar dos archivos priorizados:

follow_candidates.jsonl

reply_candidates.jsonl

Cada candidato debe incluir score, score_breakdown, reasons, language, post_age_hours, topic_affinity, reciprocity_state y source. Así se puede auditar por qué se siguió o respondió, y entrenar después el ranking con resultados reales.

Plan de PR pequeñas

PR 1 — Esquema común: tools/growth_signals_schema.py con ProfileSignals, PostSignals, InteractionSignals y OutcomeSignals; validación JSONL y tests.

PR 2 — Adaptador Instagram: tools/instagram_signal_adapter.py; normaliza la salida actual sin alterar la recogida.

PR 3 — Antigüedad: añadir post_age_hours, ventana de respuesta y decaimiento; conectar con la política existente de post-age.

PR 4 — Idioma: tools/language_signal.py usando fasttext-langdetect; priorizar español y registrar confianza.
instagrapi

PR 5 — Afinidad: ampliar discovery_terms.py con léxico de fantasía, romantasy, YA, lectura y escritura; calcular topic_affinity sobre bio, caption y comentarios.

PR 6 — Score explicables: tools/instagram_growth_score.py con follow_score y reply_score, pesos configurables y desglose auditable.

PR 7 — Ingesta por hashtag: adaptador opcional de instagrapi para hashtag_medias_recent y hashtag_medias_top, con deduplicación y cursor.
github

PR 8 — Aprendizaje: conectar resultados de growth_attribution.py al score y publicar KPI por cohorte: follow-back, respuesta recibida, comentario entrante y conversación de dos o más turnos.

Aplicación multired

El esquema debe ser común, pero los pesos cambian:

X, Threads, Bluesky y Mastodon: frescura, afinidad e interacción previa pesan igual; el social graph es más relevante que en TikTok.

Facebook: priorizar grupos, comentarios y reacciones; el ratio seguidores/siguiendo pesa menos.

Pinterest: sustituir “posts” por pins; priorizar boards del nicho, keywords, guardados y frescura.

Reddit: sustituir seguidores por karma, antigüedad, actividad en subreddit y calidad de comentarios.

TikTok: priorizar comentarios recientes, respuestas del creador y afinidad BookTok; el ratio de seguidores es poco fiable.

Instagram: conservar el equilibrio propuesto, porque combina actividad, idioma, afinidad, social graph y conversación.

Fuentes

Repo espejo davidpd89/ci-sandbox-tmp, rama main: módulos existentes de Instagram, reciprocidad, afinidad, idioma, antigüedad y atribución revisados mediante el conector GitHub.

instaloader/instaloader
: 13,5k estrellas, MIT, ingesta de perfiles, posts, captions, comentarios y hashtags; soporta actualización incremental.
github

subzeroid/instagrapi
: librería MIT para perfiles, media, comentarios, hashtags, seguidores y social graph.
subzeroid
+1

Documentación de hashtags de instagrapi
: hashtag_medias_recent, hashtag_medias_top y paginación.
github

zafercavdar/fasttext-langdetect
: detección offline de idioma, MIT, compatible con Windows y Python 3.9–3.13; recall de español 0,986.
instagrapi

LlmKira/fast-langdetect
: alternativa ligera y rápida basada en FastText, compatible con Python 3.9–3.14.
github

 #1576 — Issue de instagrapi sobre LoginRequired
: evidencia de que las peticiones masivas por hashtag requieren límites y sesión válida.
github
