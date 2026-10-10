# Ranking de cuentas y posts en Mastodon

Fuente: informe de Perplexity (https://www.perplexity.ai/search/9744bbe3-ddeb-49c4-a2a3-87438ba1b6a5), generado 10/10/2026.

Informe mejorado: señales y repos para puntuar follows y respuestas en Mastodon

He revisado el informe anterior con criterio de auditoría: he eliminado referencias poco aplicables o archivadas, he verificado actividad reciente de los repos candidatos y he reducido el plan a piezas realmente reutilizables para davidpd89/ci-sandbox-tmp. El núcleo sigue siendo un motor de scoring con dos salidas: perfiles a seguir y posts a responder; no propongo automatizar follows, likes ni boosts sin cola de revisión.

Resumen

El módulo existente SISTEMA_DIARIO_MASTODON/growth_config.json ya contiene la base de nicho, hashtags y configuración de crecimiento; la mejora correcta es añadir descubrimiento, normalización, scoring y registro de resultados, sin duplicar esa configuración. Las señales con mejor relación señal/ruido en Mastodon son: relación existente, actividad reciente, ratio de seguimiento, afinidad temática, idioma, antigüedad del post y capacidad real de conversación.
docs.joinmastodon
+2

He descartado russss/polybot como dependencia: sigue teniendo código útil, pero está archivado y su último push fue en marzo de 2026; puede inspirar arquitectura, pero no debe integrarse como dependencia activa. También descarto los bots genéricos de publicación periódica: resuelven cross-posting, no descubrimiento ni ranking de reciprocidad.
memalign.github

Hallazgos verificados
Hallazgo	Repo / fuente	Estado a 10/10/2026	Qué aprovechar	Integración	Riesgo	Test mínimo
Cliente API completo	
halcy/Mastodon.py
	Activo; documentación estable y wrapper completo	Autenticación, búsqueda, timelines, cuentas, relaciones y estados	Capa única mastodon_client.py	No sustituye la lógica de nicho	Mock de red y smoke test
Campos de perfil	
docs.joinmastodon.org/entities/Account
	Documentación oficial vigente	followers_count, following_count, statuses_count, last_status_at, note, fields	profile_scorer.py	last_status_at puede ser fecha sin hora	Fixtures de perfil
Relaciones y deduplicación	
docs.joinmastodon.org/methods/accounts
	Documentación oficial vigente	relationships, following, followed_by, IDs	Evitar seguir duplicados; bonus por relación previa	Requiere token de lectura	Test de lotes de IDs
Estados y conversación	
docs.joinmastodon.org/methods/statuses
	Documentación oficial vigente	replies_count, reblogs_count, favourites_count, created_at, language, content, tags	post_scorer.py	HTML en content; idioma a veces nulo	Limpieza HTML e idioma
Tendencias como semilla	
docs.joinmastodon.org/methods/trends
	Documentación oficial vigente	trends/tags, trends/statuses, trends/links	Semilla de descubrimiento, nunca acción directa	Puede salir del nicho	Filtro temático
Bot activo con configuración y publicación	palewire/muckrockbot	Push el 10/10/2026; Python, GPL-3.0	Estructura de bot, configuración por entorno y publicación	Patrón de ejecución y configuración	No puntúa ni descubre	Carga de config
Bot activo multiplataforma	questionlp/podcast-bot	Push el 01/10/2026; Python, MIT	Patrón de publicación en Mastodon y Bluesky	Referencia para adaptador común	Enfocado a podcasts	No copiar lógica de feeds
Bot activo de traducción federada	Riverfount/translate-bot	Push el 14/08/2026; Python, MIT, FastAPI	Manejo de menciones, ActivityPub y respuestas	Referencia para responder a menciones	No es un ranker	Test de menciones
Bot activo con GitHub Actions	askfredbv/bluesky-bot	Push el 08/10/2026; Python, MIT	CI programado, secretos y ejecución diaria	Plantilla de workflow	Enfocado a RSS/Bluesky	Workflow dry-run
Bot activo de datos públicos	hugovk/bitsofpluto	Push el 05/10/2026; Python, MIT	Estructura sencilla, pruebas y publicación	Referencia menor de robustez	Poco relevante al nicho	No integrar directamente

Los repos más recientes y activos encontrados son palewire/muckrockbot, questionlp/podcast-bot, Riverfount/translate-bot y askfredbv/bluesky-bot; todos tienen pushes en 2026 y licencias claras.
github
+3

Qué quitar del informe anterior

russss/polybot: archivado; no usar como dependencia ni como base activa.
memalign.github

andrlik/ewtwitterbot: archivado y orientado a quotes/Markov; no aporta al objetivo.
memalign.github

franceshunt90/mastodon_follow_like_bot: la idea de filtros es válida, pero el follow-back automático no encaja con un sistema que debe medir afinidad y reciprocidad; se elimina como repositorio a integrar.

Sari95/Mastodon-Bot-with-Python: demasiado básico y orientado a reblog; se elimina como referencia principal.

VitexSoftware/mastodon-mcp-server: útil para exploración manual, pero añade una capa innecesaria al pipeline diario; se elimina del plan de PR.

La fórmula inicial con peso fijo de “novedad relativa”: se simplifica. El tamaño del perfil no debe penalizarse por sí mismo; lo importante es actividad, idioma, afinidad y relación previa.

Señales definitivas
Perfil: a quién seguir
text
profile_score =
  0.30 * actividad
+ 0.25 * reciprocidad_potencial
+ 0.25 * afinidad_tematica
+ 0.20 * idioma_es

Actividad: statuses_count alto no basta; last_status_at debe ser reciente. La API expone ambos campos.
docs.joinmastodon
+1

Reciprocidad potencial: following_count / max(followers_count, 1); priorizar perfiles activos que siguen a otras cuentas, sin premiar ratios extremos.

Afinidad temática: coincidencias en note, fields, hashtags y últimos statuses con fantasía, romantasy, lectura, escritura, libros y autores.

Idioma: priorizar es; usar bio, campos y últimos posts como evidencia cuando language esté ausente.

Post: a qué responder
text
reply_score =
  0.30 * capacidad_conversacion
+ 0.25 * afinidad_tematica
+ 0.20 * actividad_autor
+ 0.15 * idioma_es
+ 0.10 * frescura

Capacidad de conversación: replies_count, preguntas, recomendaciones solicitadas y contexto; es más útil que el número de boosts.
docs.joinmastodon

Afinidad: coincidencia con hashtags, bio y temas del perfil; reutiliza las listas ya presentes en growth_config.json.
docs.joinmastodon

Actividad del autor: descartar autores inactivos aunque el post tenga engagement.

Idioma: language es un código ISO 639-1, pero puede ser nulo; complementar con heurística textual.
docs.joinmastodon
+1

Frescura: priorizar 24–72 horas; usar created_at y paginación min_id / max_id.

Código reutilizable
1. Configuración de scoring
json
// URL de integración:
// https://github.com/davidpd89/ci-sandbox-tmp/blob/60aa837fcbe2933928ee69aa395806a3bd5a74d1/SISTEMA_DIARIO_MASTODON/growth_config.json
{
  "mastodon_scoring": {
    "profile_weights": {
      "actividad": 0.30,
      "reciprocidad_potencial": 0.25,
      "afinidad_tematica": 0.25,
      "idioma_es": 0.20
    },
    "reply_weights": {
      "capacidad_conversacion": 0.30,
      "afinidad_tematica": 0.25,
      "actividad_autor": 0.20,
      "idioma_es": 0.15,
      "frescura": 0.10
    },
    "limits": {
      "max_follows_per_day": 10,
      "max_replies_per_day": 8,
      "min_profile_score": 0.62,
      "min_reply_score": 0.60,
      "max_post_age_hours": 72,
      "max_account_inactivity_days": 90
    },
    "languages": ["es"],
    "topics": [
      "fantasia", "romantasy", "fantasia juvenil",
      "libros", "lectura", "escritura", "autoras", "autores"
    ]
  }
}
2. Normalización y scoring de perfil
python
# Adaptación propia para davidpd89/ci-sandbox-tmp.
# Campos fuente: https://docs.joinmastodon.org/entities/Account/
# API fuente: https://docs.joinmastodon.org/methods/accounts/

from datetime import datetime, timezone
from urllib.parse import urlparse

def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def days_since(value):
    dt = parse_dt(value)
    if not dt:
        return 9999
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)

def activity_score(account, max_inactive_days=90):
    days = days_since(account.get("last_status_at"))
    if days > max_inactive_days:
        return 0.0
    posts = int(account.get("statuses_count") or 0)
    if posts < 10:
        return 0.2
    return min(1.0, 0.5 + 0.5 * (1 - min(days / max_inactive_days, 1)))

def reciprocity_score(account):
    followers = max(int(account.get("followers_count") or 0), 1)
    following = int(account.get("following_count") or 0)
    ratio = following / followers
    if ratio <= 0:
        return 0.0
    if ratio > 10:
        return 0.2
    return min(1.0, ratio / 2)

def affinity_score(account, topics):
    text = " ".join([
        account.get("note") or "",
        account.get("display_name") or "",
        " ".join(str(f.get("value", "")) for f in account.get("fields") or []),
    ]).lower()
    hits = sum(1 for topic in topics if topic.lower() in text)
    return min(1.0, hits / max(1, len(topics) // 3))

def language_score(account, allowed=("es",)):
    locale = (account.get("locale") or "").lower()
    if locale in allowed:
        return 1.0
    text = (account.get("note") or "").lower()
    spanish_markers = ("español", "espanol", "escribe en español", "libros en español")
    return 1.0 if any(marker in text for marker in spanish_markers) else 0.0

def score_profile(account, config, relationship=None):
    weights = config["mastodon_scoring"]["profile_weights"]
    limits = config["mastodon_scoring"]["limits"]
    topics = config["mastodon_scoring"]["topics"]

    score = (
        weights["actividad"] * activity_score(account, limits["max_account_inactivity_days"])
        + weights["reciprocidad_potencial"] * reciprocity_score(account)
        + weights["afinidad_tematica"] * affinity_score(account, topics)
        + weights["idioma_es"] * language_score(account, tuple(config["mastodon_scoring"]["languages"]))
    )

    if relationship:
        if relationship.get("following"):
            score += 0.05
        if relationship.get("followed_by"):
            score += 0.10

    return round(min(score, 1.0), 4)
3. Scoring de posts
python
# Adaptación propia para davidpd89/ci-sandbox-tmp.
# Campos fuente: https://docs.joinmastodon.org/methods/statuses/
# Entidad Status: https://docs.joinmastodon.org/entities/Status/

import html
import re
from datetime import datetime, timezone

TAG_RE = re.compile(r"<[^>]+>")

def clean_content(status):
    raw = status.get("content") or ""
    text = html.unescape(TAG_RE.sub(" ", raw))
    return re.sub(r"\s+", " ", text).strip()

def conversation_score(status):
    replies = int(status.get("replies_count") or 0)
    favourites = int(status.get("favourites_count") or 0)
    boosts = int(status.get("reblogs_count") or 0)
    text = clean_content(status).lower()

    question_bonus = 0.2 if "?" in text else 0.0
    recommendation_bonus = 0.2 if any(
        word in text for word in ("recomend", "qué leo", "que leo", "sugerencia")
    ) else 0.0

    engagement = min(1.0, (replies * 2 + favourites + boosts) / 20)
    return min(1.0, engagement + question_bonus + recommendation_bonus)

def post_affinity(status, topics):
    text = clean_content(status).lower()
    tags = " ".join(t.get("name", "") for t in status.get("tags") or []).lower()
    haystack = f"{text} {tags}"
    hits = sum(1 for topic in topics if topic.lower() in haystack)
    return min(1.0, hits / max(1, len(topics) // 3))

def freshness_score(status, max_age_hours=72):
    created = status.get("created_at")
    if not created:
        return 0.0
    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
    age_hours = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
    if age_hours > max_age_hours:
        return 0.0
    return 1 - (age_hours / max_age_hours)

def score_post(status, config):
    weights = config["mastodon_scoring"]["reply_weights"]
    limits = config["mastodon_scoring"]["limits"]
    topics = config["mastodon_scoring"]["topics"]

    language = (status.get("language") or "").lower()
    language_score = 1.0 if language in config["mastodon_scoring"]["languages"] else 0.0

    account = status.get("account") or {}
    author_activity = activity_score(account, limits["max_account_inactivity_days"])

    return round(min(1.0, (
        weights["capacidad_conversacion"] * conversation_score(status)
        + weights["afinidad_tematica"] * post_affinity(status, topics)
        + weights["actividad_autor"] * author_activity
        + weights["idioma_es"] * language_score
        + weights["frescura"] * freshness_score(status, limits["max_post_age_hours"])
    )), 4)
4. Cliente mínimo
python
# Adaptación propia para davidpd89/ci-sandbox-tmp.
# Librería fuente: https://github.com/halcy/Mastodon.py
# Documentación: https://mastodonpy.readthedocs.io/

from mastodon import Mastodon

def build_client(base_url, access_token):
    return Mastodon(
        access_token=access_token,
        api_base_url=base_url,
    )

def discover_candidates(client, hashtags, limit=40):
    seen = {}
    for tag in hashtags:
        for status in client.timeline_hashtag(tag, limit=limit):
            if status.get("reblog"):
                continue
            seen[status["id"]] = status
    return list(seen.values())

def relationships_for(client, account_ids, batch_size=40):
    out = {}
    for i in range(0, len(account_ids), batch_size):
        chunk = account_ids[i:i + batch_size]
        for relationship in client.account_relationships(chunk):
            out[str(relationship["id"])] = relationship
    return out
Plan de implementación en PR pequeñas
PR 1 — Configuración y esquema

Añadir SISTEMA_DIARIO_MASTODON/scoring_config.json.

No modificar claves existentes de growth_config.json.

Añadir docs/mastodon_scoring.md.

Test: carga JSON, validación de pesos que sumen 1.0 y compatibilidad Python 3.11 / Windows.

PR 2 — Cliente y descubrimiento

Añadir mastodon_client.py.

Métodos: timeline_hashtag, search, account_lookup, account_statuses, account_relationships.

Guardar respuestas crudas en data/mastodon/raw/YYYY-MM-DD/.

Test: mocks; ningún acceso real desde CI.

PR 3 — Scoring de perfiles

Añadir profile_scorer.py.

Generar data/mastodon/candidates_profiles.json.

Incluir score, reasons, language, last_status_at, ratio y relationship.

Test: perfiles activos, inactivos, fuera de nicho, ya seguidos y con follow-back.

PR 4 — Scoring de posts

Añadir post_scorer.py.

Generar data/mastodon/candidates_replies.json.

Incluir extracto limpio, autor, antigüedad, idioma, hashtags y score.

Test: posts recientes, antiguos, en español, en inglés, con respuestas y duplicados.

PR 5 — Aprendizaje de reciprocidad

Añadir outcome_tracker.py.

Registrar por candidato: followed, follow_back, reply_received, boost_received, favourite_received, responded.

Recalcular pesos cada 7 días con datos observados.

Test: dataset sintético con resultados positivos, negativos y sin respuesta.

PR 6 — Informe diario

Generar informe_mastodon_YYYY-MM-DD.md.

Incluir top 20 perfiles, top 20 posts, motivos de descarte y métricas de reciprocidad.

Publicarlo como artefacto de CI; sin acciones automáticas.

Test: informe determinista desde fixtures.

Aplicación a las demás redes

La arquitectura común debe ser:

text
discovery -> normalize -> profile_score -> post_score -> action_queue -> outcome_tracker

Bluesky: followersCount, followsCount, postsCount, search y feeds.

X: seguidores, siguiendo, bio, actividad, replies y listas.

Threads: bio, temas, interacciones y comentarios; menos campos públicos.

Facebook: grupos, páginas, comentarios y reacciones.

Pinterest: pins recientes, tableros, guardados y repins.

Reddit: subreddits, karma temático, comentarios, antigüedad y reglas del hilo.

TikTok / Instagram: bio, hashtags, comentarios recientes, guardados y afinidad visual.

Mastodon es el mejor piloto porque expone directamente las señales necesarias: perfil, relación, estados, idioma, antigüedad e interacciones.
docs.joinmastodon
+2

Fuentes

Repo espejo y configuración existente: SISTEMA_DIARIO_MASTODON/growth_config.json.
docs.joinmastodon

Entidad Account: 
https://docs.joinmastodon.org/entities/Account/
docs.joinmastodon

Métodos de cuentas y relaciones: 
https://docs.joinmastodon.org/methods/accounts/
docs.joinmastodon

Métodos de estados: 
https://docs.joinmastodon.org/methods/statuses/
docs.joinmastodon

Tendencias: 
https://docs.joinmastodon.org/methods/trends/

Búsqueda: 
https://documentation.sig.gy/methods/search/

Cliente Python: 
https://github.com/halcy/Mastodon.py

Bot activo de referencia: https://github.com/palewire/muckrockbot
github

Bot activo multiplataforma: https://github.com/questionlp/podcast-bot
martinheinz

Bot activo de menciones y ActivityPub: https://github.com/Riverfount/translate-bot
blog.tomaszdunia

Bot activo con GitHub Actions: https://github.com/askfredbv/bluesky-bot
