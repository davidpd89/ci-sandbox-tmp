# Ranking de cuentas y posts en TikTok

Fuente: informe de Perplexity (https://www.perplexity.ai/search/dd073b0d-b485-4395-aa52-bafd9a371cb5), generado 10/10/2026.

Informe mejorado: señales y repositorios para priorizar follows y respuestas en TikTok

He revisado el informe anterior contra el código real de davidpd89/ci-sandbox-tmp y he eliminado las propuestas que no encajan con el stack actual: jpfefferlab/tiktokscraper y 5H1M4/Tiktok_Osint_Scraper_With_Python por depender de Selenium cuando el sistema ya tiene un flujo móvil propio; drawrowfly/tiktok-scraper por requerir Node.js; y HasData/tiktok-scraping o EnsembleData porque son ejemplos/servicios comerciales, no piezas directamente reutilizables. La recomendación central se mantiene: enriquecer el descubrimiento TikTok existente con señales de reciprocidad, idioma, actividad, frescura y conversación, sin crear un segundo descubridor.
hasdata

Resumen

El sistema ya puntúa candidatos TikTok por afinidad de nicho, recurrencia en contextos independientes, relación conocida/seguida y lane community/creator/acquisition; además, reciprocity.py ya define clasificación recíproca, bonus por bio de follow-back y observación de contadores.

La mejora prioritaria es añadir un enriquecedor de señales que complete cada candidato con: seguidores/siguiendo cuando estén disponibles, bio, último post, antigüedad del post, idioma, comentarios recientes y señal de que el autor responde. Así el ranking deja de favorecer únicamente la coincidencia temática y pasa a favorecer perfiles y posts con mayor probabilidad real de reciprocidad y conversación.

Lo que ya existe y no debe duplicarse

tools/tiktok_growth_scan.py ya implementa:

Descubrimiento desde inbox, user_search, video_search, seed_comments, for_you y following.

Filtro de anuncios, spam, cuentas descartadas y falta de afinidad.

Agrupación por handle y bonificación por aparición en fuentes o contextos independientes.

Shortlist con follow, like y comment; auto-plan mecánico para follow/like y decisión de comentario reservada a la IA.

Frontier: los mejores perfiles nuevos se convierten en semillas para minar sus comentaristas.

tools/reciprocity.py ya aporta el núcleo multiplataforma:

classify(followers, following, statuses) distingue super, reciprocal y None.

affinity_bonus() asigna +2,0 a cuentas recíprocas y +1,0 a hubs.

declares_followback() detecta bios como “sigo de vuelta”, “sdv”, “follow back”, “te sigo si me sigues”, etc.

observe() guarda contadores, idioma y declaración de follow-back en 00_OPERATIVO/perfiles_contadores.csv.

select_hubs() promueve hubs recíprocos como semillas.

Por tanto, no propongo un nuevo módulo de descubrimiento ni un nuevo registro de reciprocidad; propongo conectar TikTok a ese núcleo común y añadir las señales que hoy faltan.

Señales recomendadas
Señal	Por qué importa	Implementación
Relación seguidores/siguiendo	Es la señal más directa de cultura de follow-back.	Reutilizar reciprocity.classify() y affinity_bonus().
Follow-back declarado	La bio declara explícitamente que devuelve el follow.	Reutilizar declares_followback() y su bonus de +2,5.
Idioma español	Evita comentarios fuera de audiencia y mejora afinidad real.	Reutilizar text_common.looks_spanish() / other_language() ya usados por reciprocity.observe().
Actividad reciente	Una cuenta activa tiene más probabilidad de ver e interactuar.	Calcular last_post_at y bonificar últimos 7/30 días.
Antigüedad del post	Responder a un post de hace horas es mucho más probable que genere conversación que responder a uno antiguo.	Calcular post_age_hours desde createTime y priorizar <24 h y <72 h. 
hasdata

Conversación abierta	Preguntas, peticiones de recomendaciones y opiniones invitan a respuesta.	Detectar patrones en caption y comentarios.
Autor que responde	Es la mejor señal observada de que un comentario puede recibir réplica.	Detectar respuestas del autor en comentarios recientes.
Afinidad de alta intención	“Fantasía”, “romantasy”, “lectura”, “recomiéndame” valen más que una mención genérica.	Separar high_intent_terms de niche_terms en growth_config.json.
Hallazgos: repositorios y fuentes
Repositorio / fuente	Estado y encaque	Qué aprovechar	Integración	Decisión

davidteather/TikTok-Api
	Activo; documentación indica versión 7.3.3 y actividad reciente; Python, open source y sin rutas autenticadas. 
github
+1
	Obtención de perfil, vídeos, comentarios y búsqueda; ejemplos oficiales de user, video y comment. 
github
	Proveedor opcional TikTokExternalSignals, desactivado por defecto, para completar perfil y metadatos de post.	Integrar como proveedor opcional.

robbytables/TikTok-Comment-Scraper
	Python; orientado a investigación; recoge comentarios, respuestas, metadatos, usuario y asociación a vídeo. 
davidteather
	Patrón de extracción de comentarios con timestamp, likes, respuestas y autor.	Alimentar comment_count, latest_comment_at, has_question y author_replies_recently.	Aprovechar patrón, no dependencia directa.

data-scrape/tiktok-comments-scraper
	Actualizado en agosto de 2026; MIT; extrae comentarios y respuestas con filtrado por fecha, palabra y engagement.	Filtrado temporal y de palabras clave de comentarios.	Añadir comentarios recientes en español como señal de post conversacional.	Aprovechar patrón de filtrado.

ChocoData-com/tiktok-profile-scraper
	Actualizado en 2026; extrae uniqueId, nickname, signature, verified, followerCount, followingCount, heartCount, videoCount y createTime.	Esquema de campos de perfil y mapeo a reciprocity.observe().	Poblar followers, following, bio, video_count y last_post_at.	Aprovechar esquema de campos.

kopong25/social-media-analytics
	MIT; análisis multiplataforma con TikTok, Instagram, YouTube y X; incluye fórmulas de engagement y calidad. 
github
	Fórmulas de Comment Rate y Quality Score ponderado.	Usar como referencia para un conversation_score acotado, no como dependencia.	Aprovechar fórmulas, no integrar repo.

tiktok/tiktok-research-api-wrapper
	Oficial; Python/R; cubre vídeos, user info, comentarios, seguidores, seguidos y reposts.	Fuente estable de métricas si se dispusiera de acceso Research.	Implementar como proveedor preferente futuro; no como ruta inmediata.	Vigilar; no integrar ahora.

HMI-99/TikTok-Live-Engagement-Analysis
	Notebook y dataset de métricas de TikTok Live. 
github
	No resuelve descubrimiento ni ranking de perfiles/posts.	—	Descartar.

kavindu-udara/tiktok-comment-scraper
	Flask + React; actualizado en 2024. 
github
	Añadiría backend y frontend innecesarios.	—	Descartar.

apivault-labs/tiktok-profile-scraper-python
	Cliente de actor de Apify de pago. 
github
	No es código autónomo reutilizable.	—	Descartar.
Código reutilizable e integración

Los bloques siguientes son adaptaciones listas para ci-sandbox-tmp, basadas en las interfaces y campos públicos de los repos citados; cada bloque indica el archivo de origen exacto del que procede el patrón o el campo. No copian ejecutores ni automatizaciones de terceros.

1. Contrato de señales
python
# Adaptación para davidpd89/ci-sandbox-tmp
# Campos de perfil basados en: https://github.com/ChocoData-com/tiktok-profile-scraper
# Campos de comentario basados en: https://github.com/robbytables/TikTok-Comment-Scraper
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ProfileSignals:
    handle: str
    followers: Optional[int] = None
    following: Optional[int] = None
    video_count: Optional[int] = None
    bio: str = ""
    last_post_at: Optional[datetime] = None
    is_spanish: bool = False
    declares_followback: bool = False
    reciprocity_class: Optional[str] = None
    affinity_bonus: float = 0.0


@dataclass
class PostSignals:
    url: str
    create_time: Optional[datetime] = None
    comment_count: int = 0
    latest_comment_at: Optional[datetime] = None
    has_question: bool = False
    author_replies_recently: bool = False
    is_spanish: bool = False

    @property
    def post_age_hours(self) -> Optional[float]:
        if not self.create_time:
            return None
        return max(0.0, (datetime.now().timestamp() - self.create_time.timestamp()) / 3600)
2. Enriquecedor de reciprocidad TikTok

Este módulo reutiliza el núcleo común existente en lugar de duplicarlo.

python
# Adaptación para davidpd89/ci-sandbox-tmp/tools/tiktok_reciprocity_signals.py
# Núcleo reutilizado de: https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/reciprocity.py
from __future__ import annotations
from typing import Optional

import reciprocity


def enrich_profile(profile: dict) -> dict:
    followers = profile.get("followers")
    following = profile.get("following")
    statuses = profile.get("video_count")
    bio = profile.get("bio") or ""

    kind = reciprocity.classify(followers, following, statuses)
    return {
        **profile,
        "reciprocity_class": kind,
        "affinity_bonus": reciprocity.affinity_bonus(followers, following, statuses),
        "declares_followback": reciprocity.declares_followback(bio),
        "followback_bonus": reciprocity.declared_bonus(bio),
    }
3. Frescura y conversación del post
python
# Adaptación para davidpd89/ci-sandbox-tmp/tools/tiktok_post_freshness.py
# Campo temporal basado en createTime documentado para perfiles/vídeos TikTok:
# https://github.com/ChocoData-com/tiktok-profile-scraper
# Patrón de comentarios con timestamp y respuestas:
# https://github.com/robbytables/TikTok-Comment-Scraper
from __future__ import annotations
import re
from datetime import datetime
from typing import Iterable, Optional

QUESTION_RE = re.compile(
    r"\b(qué|que|cuál|cual|cómo|como|quién|quien|dónde|donde|recomiéndame|recomiendame|"
    r"recomendaciones|opinión|opinion|pensáis|piensan|habéis leído|habéis leido)\b",
    re.IGNORECASE,
)


def post_age_hours(create_time: Optional[datetime]) -> Optional[float]:
    if not create_time:
        return None
    return max(0.0, (datetime.now().timestamp() - create_time.timestamp()) / 3600)


def freshness_bonus(age_hours: Optional[float]) -> float:
    if age_hours is None:
        return 0.0
    if age_hours < 24:
        return 2.5
    if age_hours < 72:
        return 1.5
    if age_hours < 24 * 7:
        return 0.5
    return 0.0


def conversation_bonus(caption: str, comments: Iterable[dict]) -> float:
    score = 0.0
    if QUESTION_RE.search(caption or ""):
        score += 1.0
    comments = list(comments or [])
    if comments:
        score += 0.5
        if any(c.get("author_is_video_author") for c in comments):
            score += 1.5
    return score
4. Puntuación final compatible con el ranking actual
python
# Adaptación para davidpd89/ci-sandbox-tmp/tools/tiktok_signal_enricher.py
# Integración con el score existente de:
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/tiktok_growth_scan.py
# Clasificación y bonus reutilizados de:
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/reciprocity.py
from __future__ import annotations
from typing import Optional

import tiktok_post_freshness as fresh


def score_candidate(
    base_score: float,
    *,
    reciprocity_class: Optional[str],
    followback_bonus: float,
    spanish_bonus: float,
    profile_activity_bonus: float,
    post_age_hours: Optional[float],
    conversation_bonus: float,
) -> tuple[float, dict]:
    reciprocity_bonus = {"reciprocal": 2.0, "super": 1.0}.get(reciprocity_class or "", 0.0)
    age_bonus = fresh.freshness_bonus(post_age_hours)

    breakdown = {
        "base": base_score,
        "reciprocity": reciprocity_bonus,
        "followback": followback_bonus,
        "spanish": spanish_bonus,
        "activity": profile_activity_bonus,
        "freshness": age_bonus,
        "conversation": conversation_bonus,
    }
    final = sum(breakdown.values())
    return round(final, 2), breakdown
5. Proveedor externo opcional
python
# Adaptación para davidpd89/ci-sandbox-tmp/tools/tiktok_external_signals.py
# API y ejemplos oficiales de:
# https://github.com/davidteather/TikTok-Api/blob/main/examples/user_example.py
# https://github.com/davidteather/TikTok-Api/blob/main/examples/comment_example.py
from __future__ import annotations
import os
from typing import Optional

from TikTokApi import TikTokApi


class TikTokExternalSignals:
    """Proveedor opcional. Debe permanecer desactivado por defecto."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled and bool(os.getenv("TIKTOK_EXTERNAL_SIGNALS_ENABLED"))
        self._api: Optional[TikTokApi] = None

    def _ensure_api(self) -> TikTokApi:
        if self._api is None:
            self._api = TikTokApi()
        return self._api

    def profile_signals(self, handle: str) -> dict:
        if not self.enabled:
            return {}
        user = self._ensure_api().user(username=handle.lstrip("@"))
        info = user.info()
        return {
            "handle": handle,
            "followers": info.get("followerCount"),
            "following": info.get("followingCount"),
            "video_count": info.get("videoCount"),
            "bio": info.get("signature") or "",
        }

    def post_signals(self, video_id: str) -> dict:
        if not self.enabled:
            return {}
        video = self._ensure_api().video(id=video_id)
        info = video.info()
        comments = list(video.comments(count=20))
        latest = max(
            (c.get("create_time") for c in comments if c.get("create_time")),
            default=None,
        )
        return {
            "url": f"https://www.tiktok.com/@x/video/{video_id}",
            "create_time": info.get("createTime"),
            "comment_count": info.get("commentCount"),
            "latest_comment_at": latest,
            "comments": comments,
        }
Cambios concretos en tiktok_growth_scan.py
Ranking de perfiles

En _compact_shortlist(), el orden actual es:

python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/tiktok_growth_scan.py
ranked = sorted(
    grouped.values(),
    key=lambda item: (
        -item["score"],
        item["known"],
        -len(item["sources"]),
        item["handle"].casefold(),
    ),
)

Propuesta de sustitución, tras enriquecer cada item:

python
# Adaptación: orden por probabilidad de reciprocidad y frescura
ranked = sorted(
    grouped.values(),
    key=lambda item: (
        -item.get("score_final", item["score"]),
        -item.get("freshness_bonus", 0.0),
        0 if item.get("is_spanish") else 1,
        0 if item.get("reciprocity_class") else 1,
        item["handle"].casefold(),
    ),
)
Ranking de posts

Actualmente los posts se ordenan solo por score:

python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/tiktok_growth_scan.py
posts.append({
    "id": f"{cid}-P{pi}",
    ...
    "score": row["niche_hits"],
})

Propuesta:

python
# Adaptación: priorizar posts recientes y conversacionales
post_score = (
    row["niche_hits"]
    + fresh.freshness_bonus(row.get("post_age_hours"))
    + fresh.conversation_bonus(row.get("caption"), row.get("comments"))
)

posts.append({
    "id": f"{cid}-P{pi}",
    ...
    "score": round(post_score, 2),
    "post_age_hours": row.get("post_age_hours"),
})

Y el orden interno:

python
# Adaptación: frescura antes que afinidad cuando ambas son comparables
sorted(
    item["posts"],
    key=lambda p: (-p["score"], p.get("post_age_hours") or 10**9),
)[:2]
Umbrales y política de decisión
Decisión	Condición propuesta
follow automático	score_final >= 8 —manteniendo auto_follow_score_min— y (reciprocity_class no nulo o declares_followback).
follow a revisión IA	score_final >= 6, español, actividad en 30 días y afinidad de nicho.
like automático	Mantener auto_like_score_min = 3, pero elegir el post más reciente con URL.
comment propuesto	Post con menos de 72 horas, español, no cierre conversacional y candidato no descartado.
Descartar comentario	Post de más de 7 días, salvo candidato community con conversación activa.
No seguir	Cuenta sin actividad en 90 días, sin señal de reciprocidad y sin afinidad fuerte.
Plan de PR pequeñas
PR 1 — Esquema y compatibilidad

Añadir tools/tiktok_signal_schema.py con ProfileSignals y PostSignals.

Añadir campos opcionales al shortlist sin alterar el orden.

Tests: JSON serializable, valores nulos, retrocompatibilidad con shortlist actual.

PR 2 — Reciprocidad TikTok

Añadir tools/tiktok_reciprocity_signals.py.

Reutilizar classify(), affinity_bonus(), declares_followback() y declared_bonus() de reciprocity.py.

Si TikTok móvil solo expone seguidores, guardar seguidores y devolver reciprocity_class=None.

Tests: reciprocal, super, sin following, bio follow-back, cuenta no española.

PR 3 — Frescura

Añadir tools/tiktok_post_freshness.py.

Calcular post_age_hours desde createTime cuando esté disponible.

Ordenar posts por score_final y antigüedad.

Tests: fronteras de 24 h, 72 h y 7 días; timezone; post sin fecha.

PR 4 — Idioma y afinidad

Calcular is_spanish con bio, caption y comentarios.

Añadir high_intent_terms a growth_config.json.

Tests: español con tildes, inglés, texto mixto, campos vacíos.

PR 5 — Proveedor externo opcional

Añadir tools/tiktok_external_signals.py con TikTok-Api.

Activación explícita por variable de entorno; fallback completo al flujo móvil si falla.

Tests con fixtures; test de circuit breaker con tools/circuit_breaker.py.

PR 6 — Observabilidad y aprendizaje

Guardar score_breakdown, señales usadas, decisión y resultado.

Conectar con growth_attribution.py y reciprocity_stats.py.

Medir semanalmente: follow-backs, respuestas recibidas, respuestas del autor y conversaciones de más de un turno.

Tests: trazabilidad del score, reproducibilidad y no regresión del auto-plan.

Aplicación a las demás redes
Red	Reutilización	Adaptación
Bluesky	reciprocity.py, hubs, semillas y vocabulario ya operativos.	Añadir frescura y señal de autor que responde.
Mastodon	Núcleo común y contadores fiables.	Priorizar posts recientes y conversaciones abiertas.
X	reciprocity.py ya contempla seguidores y seguidos observados.	Añadir antigüedad del post y detección de preguntas.
Threads	Mismo núcleo; puede faltar following.	Usar bio, idioma y actividad como proxies.
Instagram	Mismo esquema de señales y lanes.	Priorizar Reels recientes y comentarios del autor.
Facebook	Reutilizar idioma, frescura y afinidad.	Priorizar interacciones previas sobre ratio de follows.
Pinterest	Reutilizar afinidad, idioma y frescura.	Priorizar pines recientes y guardados/comentarios; el follow es menos conversacional.
Reddit	Reutilizar idioma, frescura y afinidad.	Sustituir follow-back por karma, actividad reciente y calidad de comentario.
Fuentes

Código actual del sistema: tools/tiktok_growth_scan.py y tools/reciprocity.py.

davidteather/TikTok-Api
: wrapper Python activo para datos públicos; documentación oficial y ejemplos de usuario, vídeo y comentarios.
hasdata
+1

robbytables/TikTok-Comment-Scraper
: comentarios, respuestas, timestamps, likes y metadatos de usuario.
davidteather

data-scrape/tiktok-comments-scraper
: comentarios y respuestas con filtrado temporal, por palabra y engagement; MIT.

ChocoData-com/tiktok-profile-scraper
: campos de perfil, incluidos seguidores, seguidos, bio, vídeos y createTime; actualizado en 2026.

kopong25/social-media-analytics
: fórmulas MIT de engagement, comment rate y calidad ponderada.
github

tiktok/tiktok-research-api-wrapper
: wrapper oficial de investigación para vídeos, usuario, comentarios, seguidores y seguidos.

Guía técnica de scraping TikTok 2026: confirma campos createTime, followers, follows, friends y estructura de comentarios con create_time, autor y comment_language; también confirma actividad reciente de TikTokApi.
hasdata
