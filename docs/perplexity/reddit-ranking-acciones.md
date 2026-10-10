# Ranking de cuentas y posts en Reddit

Fuente: informe de Perplexity (https://www.perplexity.ai/search/2a06c721-e5e7-4dda-b7d8-bfd98ebfbb0f), generado 10/10/2026.

Informe mejorado: señales y repos para puntuar perfiles y posts de Reddit
Resumen

El informe anterior era correcto en la arquitectura, pero mezclaba piezas poco reutilizables —analizadores de personalidad, predictores de engagement basados en ML y proyectos de análisis histórico— con lo que realmente conviene copiar. La versión mejorada se centra en señales observables, código verificable y módulos encajables en reddit_scan.py, reciprocity.py, reply_queue.py y growth_attribution.py del repo espejo.
github

La conclusión operativa es: en Reddit, no priorices “seguir” como acción principal; prioriza responder posts y comentarios con alta probabilidad de conversación. El follow puede existir como acción secundaria, pero el ratio seguidores/siguiendo tiene mucho menos valor que en X, Bluesky o Mastodon.

Hallazgos
Necesidad	Repositorio o componente	Estado / utilidad	Qué copiar	Integración	Riesgos
Acceso estructurado a posts, comentarios y autores	
praw-dev/praw
	Activo y es la base más segura para Python	Patrón de acceso a submission.score, num_comments, author, created_utc y comentarios	Adaptador de entrada para reddit_scan.py; no duplicar ejecución	Rate limits; campos nulos; comentarios colapsados
Edad de cuenta, karma y validación básica	redditraffler/redditraffler	Fragmento verificado en el archivo fuente	Cálculo de edad de cuenta y lectura de comment_karma / link_karma	Señales account_age_days, karma_total para el score de perfil	El karma no implica afinidad ni reciprocidad
Edad de cuenta + suma de karmas como filtro	nathaniel-ortiz/redditswapbot	Fragmento verificado en el archivo fuente	Cálculo simple de antigüedad y karma agregado	Umbral mínimo de calidad antes de puntuar afinidad	Muy básico: debe completarse con actividad reciente
Perfil: karma, antigüedad, subreddits, frecuencia	
wrhilton/Reddit-User-Analysis
	Útil como referencia de features; revisar actividad antes de copiar masivamente	Ideas de frecuencia de publicación, repetición de contenido y keywords	Inspiración para reddit_profile_score.py, no copia directa	Enfocado a detectar bots, no a oportunidades de conversación 
github

Perfil: karma, horas activas, subreddits, respuestas	
Rafficer/reddit-analyzer
	Proyecto antiguo (2018), pero su desglose de features es muy útil	Métricas: actividad por hora/día, subreddits principales, score medio, personas a las que responde	Diseño del perfil temporal y de afinidad	Dependencias y código posiblemente desactualizados 
github

Perfil con LLM	
RaymonDev/AI-Reddit-Profiler
	Interesante, pero no recomendado como núcleo	Solo la extracción previa de karma, fecha de creación, subreddits y actividad	Opcional: resumen cualitativo posterior, nunca decisión automática	Inferencias psicológicas no sirven para ranking accionable 
github

Patrones de actividad sin backend	
servika/reddit-profile-analyzer
	Referencia de producto, no dependencia	Métricas visuales de actividad	Panel interno opcional	No es una librería integrable directamente 
github

Qué temas generan engagement	analytics-ak/reddit-engagement-analysis	Análisis publicado sobre 4,5 M de posts	Metodología de comparar temas, lenguaje y resultados	Validar los términos de nicho de discovery_terms.py	Es un estudio, no un módulo ejecutable 
github
+1

Predicción de engagement	
Anitej05/reddit-engagement-predictor
	Útil solo como referencia metodológica	No copiar el modelo ahora	Tras acumular datos propios, evaluar un modelo simple	Riesgo de sobreajuste y falta de datos 
github

Relación tiempo/título/volumen y score	
Hong-Jin-UoB/reddit-engagement-data-analysis
	Referencia de análisis	Variables: volumen de discusión, longitud del título, hora	Features del score de post	Snapshot pequeño; no generalizar 
github
Código verificado para reutilizar
Edad de cuenta y karmas

Este fragmento es directamente aprovechable como base de las señales de antigüedad y karma. Procede de redditraffler/redditraffler, archivo app/util/raffler.py, en el commit bfae4be3ea4885a3ceefcb2c91d7af8b833b68ee.

python
# https://github.com/redditraffler/redditraffler/blob/bfae4be3ea4885a3ceefcb2c91d7af8b833b68ee/app/util/raffler.py
age=Raffler._account_age_days(author.created_utc),
comment_karma=author.comment_karma,
link_karma=author.link_karma,

En vuestro sistema, convierte esto en un extractor defensivo, porque PRAW puede devolver None cuando el autor fue eliminado o suspendido:

python
# Nuevo archivo propuesto: tools/reddit_candidate_score.py
from datetime import datetime, timezone

def account_age_days(created_utc):
    if not created_utc:
        return 0
    return max(0, (datetime.now(timezone.utc).timestamp() - created_utc) / 86400)

def profile_quality_signals(author):
    if author is None or getattr(author, "name", None) in (None, "[deleted]"):
        return {"account_age_days": 0, "comment_karma": 0, "link_karma": 0, "valid": False}

    comment_karma = getattr(author, "comment_karma", 0) or 0
    link_karma = getattr(author, "link_karma", 0) or 0
    age = account_age_days(getattr(author, "created_utc", None))

    return {
        "account_age_days": age,
        "comment_karma": comment_karma,
        "link_karma": link_karma,
        "karma_total": comment_karma + link_karma,
        "valid": True,
    }
Antigüedad y karma agregado

Este segundo patrón, de nathaniel-ortiz/redditswapbot, archivo flair.py, confirma la combinación mínima útil: antigüedad de cuenta más suma de karmas.

python
# https://github.com/nathaniel-ortiz/redditswapbot/blob/79f8bbdc991177922ab72821adc28b156566a5da/flair.py
age = (datetime.utcnow() - datetime.utcfromtimestamp(item.author.created_utc)).days
karma = item.author.link_karma + item.author.comment_karma

Adaptación recomendada para Python 3.11 y datos incompletos:

python
# tools/reddit_candidate_score.py
def passes_minimum_quality(signals, min_age_days=30, min_karma=50):
    return (
        signals.get("valid", False)
        and signals.get("account_age_days", 0) >= min_age_days
        and signals.get("karma_total", 0) >= min_karma
    )
Score de perfil

No uses el karma como señal principal. Úsalo como filtro de calidad y prioriza actividad reciente, afinidad, idioma y reciprocidad.

python
# tools/reddit_candidate_score.py
def score_profile(
    *,
    recent_activity_7d,
    reciprocity_events,
    topic_affinity,
    spanish_probability,
    account_age_days,
    karma_total,
):
    activity = min(recent_activity_7d / 5.0, 1.0)
    reciprocity = min(reciprocity_events / 3.0, 1.0)
    affinity = max(0.0, min(topic_affinity, 1.0))
    language = max(0.0, min(spanish_probability, 1.0))
    maturity = min(account_age_days / 365.0, 1.0)
    karma = min(karma_total / 1000.0, 1.0)

    return round(
        0.30 * activity
        + 0.25 * reciprocity
        + 0.20 * affinity
        + 0.15 * language
        + 0.07 * maturity
        + 0.03 * karma,
        4,
    )
Señales concretas

Actividad reciente: número de posts o comentarios públicos en los últimos 7 días.

Reciprocidad: respuestas recibidas de ese autor, interacciones previas y participación posterior en vuestros hilos; debe salir de reciprocity.py y reciprocity_stats.py, no calcularse otra vez desde cero.
github

Afinidad temática: coincidencias con fantasía, romantasy, lectura, escritura, libros en español, autores independientes y comunidades lectoras.

Idioma: probabilidad de español; debe reutilizar check_language_variety.py y spellcheck_es.py.
github

Madurez: antigüedad de la cuenta y karma agregado, solo como filtro mínimo.

Score de post
python
# tools/reddit_candidate_score.py
from math import exp

def freshness_score(age_hours, half_life_hours=24.0):
    if age_hours < 0:
        return 0.0
    return exp(-age_hours / half_life_hours)

def score_post(
    *,
    age_hours,
    comment_count,
    question_or_request,
    topic_affinity,
    spanish_probability,
    author_active_recently,
):
    freshness = freshness_score(age_hours)
    conversation = 1.0 if question_or_request else min(comment_count / 10.0, 1.0)
    affinity = max(0.0, min(topic_affinity, 1.0))
    language = max(0.0, min(spanish_probability, 1.0))
    author_available = 1.0 if author_active_recently else 0.3

    return round(
        0.30 * freshness
        + 0.25 * conversation
        + 0.20 * affinity
        + 0.15 * language
        + 0.10 * author_available,
        4,
    )
Señales concretas

Frescura: decaimiento exponencial con vida media de 24 horas; un post de 1 hora vale mucho más que uno de 3 días.

Conversación: pregunta abierta, petición de recomendaciones, opinión discutible o comentarios recientes.

Afinidad: subreddit, título, cuerpo y términos del nicho.

Idioma: español detectable; descartar o penalizar candidatos no españoles.

Disponibilidad del autor: actividad reciente del autor; evita responder hilos abandonados.

Integración sin duplicar el sistema
python
# Pseudocódigo de integración en tools/reddit_scan.py
from reddit_candidate_score import (
    profile_quality_signals,
    passes_minimum_quality,
    score_profile,
    score_post,
)

def enrich_reddit_candidate(item, reciprocity_data, language_detector, topic_matcher):
    author_signals = profile_quality_signals(item.get("author"))

    if not passes_minimum_quality(author_signals):
        return None

    profile_score = score_profile(
        recent_activity_7d=item.get("author_recent_activity_7d", 0),
        reciprocity_events=reciprocity_data.get("reciprocity_events", 0),
        topic_affinity=topic_matcher.score(item.get("text", "")),
        spanish_probability=language_detector.spanish_probability(item.get("text", "")),
        account_age_days=author_signals["account_age_days"],
        karma_total=author_signals["karma_total"],
    )

    post_score = score_post(
        age_hours=item["age_hours"],
        comment_count=item.get("num_comments", 0),
        question_or_request=item.get("is_question_or_request", False),
        topic_affinity=topic_matcher.score(item.get("text", "")),
        spanish_probability=language_detector.spanish_probability(item.get("text", "")),
        author_active_recently=item.get("author_recent_activity_7d", 0) > 0,
    )

    return {
        "submission_id": item["submission_id"],
        "comment_id": item.get("comment_id"),
        "author": item.get("author_name"),
        "profile_score": profile_score,
        "post_score": post_score,
        "action_type": "reply" if post_score >= 0.55 else "none",
        "features": {
            **author_signals,
            "age_hours": item["age_hours"],
            "comment_count": item.get("num_comments", 0),
        },
    }

La salida debe alimentar reply_queue.py, mientras que growth_attribution.py debe guardar features, score, action_type y resultado real. Así podréis comparar si los candidatos con score alto generan más respuestas, upvotes o conversación.
github

Qué elimino del informe anterior

Predictores de engagement por ML: no copiarlos ahora. Sin dataset propio etiquetado, añaden complejidad sin beneficio demostrado.
github

Análisis de sentimiento: no es una señal fiable de reciprocidad ni de oportunidad de conversación; queda fuera del núcleo.
github

Perfiles psicológicos con LLM: no deben influir en el ranking. Solo puede aprovecharse la extracción previa de datos públicos.
github

Follow como acción prioritaria en Reddit: se degrada a acción excepcional. La reciprocidad en Reddit proviene sobre todo de responder bien y a tiempo, no de acumular follows.

Ratio seguidores/siguiendo como señal principal: se conserva solo como metadato secundario; en Reddit no predice bien la disposición a conversar.

Plan de implementación en PR pequeñas

PR 1 — Extractor de señales: tools/reddit_candidate_score.py con profile_quality_signals, account_age_days y passes_minimum_quality. Tests con autor válido, eliminado y sin karma.

PR 2 — Score de perfil: implementar score_profile con actividad, reciprocidad, afinidad, idioma, madurez y karma. Tests deterministas con fixtures.

PR 3 — Score de post: añadir freshness_score y score_post. Tests para 1 h, 6 h, 24 h, 72 h y 7 días.

PR 4 — Conexión con escáner: llamar al scorer desde reddit_scan.py sin alterar su contrato actual; añadir --score-candidates.

PR 5 — Cola de respuestas: filtrar por post_score y profile_score, deduplicar por submission_id + comment_id y respetar presupuesto diario.

PR 6 — Atribución: registrar features, scores y resultados en growth_attribution.py; crear un informe de conversión por decil de score.
github

PR 7 — Calibración: tras 2–4 semanas de datos, ajustar pesos y umbrales; solo entonces considerar un mecanismo de exploración controlada.

Fuentes

Repo espejo y componentes reutilizados: davidpd89/ci-sandbox-tmp, especialmente tools/reddit_scan.py, tools/reddit_interact.py, tools/reciprocity.py, tools/reciprocity_stats.py, tools/reply_queue.py, tools/growth_attribution.py, tools/discovery_terms.py, tools/check_language_variety.py y tools/spellcheck_es.py.
github

Código verificado de edad y karma: redditraffler/redditraffler — app/util/raffler.py y nathaniel-ortiz/redditswapbot — flair.py.

Base técnica recomendada: 
praw-dev/praw
.
github

Referencias de features de perfil: 
Reddit-User-Analysis
, 
reddit-analyzer
 y 
reddit-profile-analyzer
.
github
+2

Referencias de engagement y afinidad temática: reddit-engagement-analysis, 
reddit-engagement-data-analysis
 y 
reddit-engagement-predictor
.
github
+2
