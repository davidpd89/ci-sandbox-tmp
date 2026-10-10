# Ranking de cuentas y posts en Threads

Fuente: informe de Perplexity (https://www.perplexity.ai/search/0de17812-263d-4407-9926-f62f17b949c4), generado 10/10/2026.

Informe mejorado: señales y repos para priorizar follows y respuestas en Threads
Resumen

He revisado el informe anterior contra el código real de davidpd89/ci-sandbox-tmp y he eliminado lo dudoso o redundante: no conviene copiar analizadores genéricos de Instagram, ni introducir Vowpal Wabbit ahora, ni depender de repos archivados como Danie1/threads-api. El sistema ya tiene threads_scan.py, threads_interact.py, threads_reply_queue.py, reciprocity.py, relationship_policy.py, growth_core.py y score_hook.py; la mejora correcta es una capa de señales y puntuación que alimente esos módulos.

He verificado actividad reciente de los repos candidatos mediante GitHub: Zeeshanahmad4/Threads-Scraper fue actualizado el 21 de agosto de 2026, tiene 137 estrellas y sigue activo; LlmKira/fast-langdetect fue actualizado el 25 de mayo de 2026, tiene 324 estrellas y licencia MIT.
pypi

Nota de verificación: el conector GitHub devolvió metadatos y SHA de los archivos, pero no el contenido legible de parser.py ni del README; la recuperación directa del raw.githubusercontent.com también falló. Por rigor, no incluyo fragmentos presentados falsamente como copias literales. Incluyo código copiable y autónomo, alineado con los contratos observados en el repo, indicando en la primera línea el archivo upstream exacto del que procede la idea o el contrato.

Hallazgos verificados
Hallazgo	Repo / fuente	Estado	Qué aprovechar	Integración	Decisión
Scraper de Threads con parser, exportador y utilidades	Zeeshanahmad4/Threads-Scraper	Activo: push 2026-08-21; 137 estrellas; Python.	Estructura de src/scraper/parser.py y src/scraper/exporter.py para separar adquisición, normalización y export.	Crear tools/threads_signal_source.py; no sustituir threads_scan.py.	Usar como referencia de arquitectura.
Detección rápida de idioma, MIT y Python moderno	LlmKira/fast-langdetect	Activo: push 2026-05-25; 324 estrellas; MIT. 
pypi
	Detección offline de idioma para filtrar candidatos en español.	Nuevo tools/language_signal.py.	Recomendado.
API oficial de Threads	Meta Threads API	Documentación oficial vigente. 
developers.facebook
	Responder, leer respuestas propias, moderar y consultar insights.	Ampliar threads_api.py y threads_reply_queue.py.	Usar para acciones y atribución.
Contextual bandits	VowpalWabbit/vowpal_wabbit	Activo, pero excesivo para la fase actual. 
vowpalwabbit
	Aprendizaje por contexto y recompensa.	Solo export futuro de eventos.	Aplazar.
Analizadores de seguidores de Instagram	ksek87/social-media-followers, developer-az/pyFollowerVsFollowing	Poco relevantes para Threads.	Solo concepto de ratio.	Ya cubierto por reciprocity.py.	Eliminado del plan.
Cliente no oficial archivado	Danie1/threads-api	Archivado en 2023.	Ninguno en producción.	—	Eliminado.
Scraper dependiente de Apify	PRO100CHOK/threads-net-posts-profiles-scraper-python	Depende de servicio externo.	Modos de búsqueda y respuestas.	Añadiría dependencia y coste.	Eliminado del plan inmediato.
Código copiable
1. Contrato de señales
python
# Referencia de contrato: https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/growth_core.py
# Archivo nuevo propuesto: tools/threads_signal_schema.py
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ThreadsProfileSignal:
    candidate_id: str
    handle: str
    followers: int = 0
    following: int = 0
    post_count: int = 0
    last_post_at: Optional[datetime] = None
    reply_count_30d: int = 0
    like_count_30d: int = 0
    bio: str = ""
    lang: Optional[str] = None
    lang_confidence: float = 0.0
    topic_score: float = 0.0
    captured_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.last_post_at:
            data["last_post_at"] = self.last_post_at.isoformat()
        data["captured_at"] = self.captured_at.isoformat()
        return data


@dataclass(slots=True)
class ThreadsPostSignal:
    post_id: str
    author_candidate_id: str
    text: str
    created_at: datetime
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    quote_count: int = 0
    is_reply: bool = False
    lang: Optional[str] = None
    lang_confidence: float = 0.0
    topic_score: float = 0.0
    captured_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["captured_at"] = self.captured_at.isoformat()
        return data
2. Detección de español
python
# Referencia upstream: https://github.com/LlmKira/fast-langdetect/blob/main/README.md
# Archivo nuevo propuesto: tools/language_signal.py
from __future__ import annotations

import re
from functools import lru_cache

try:
    from fast_langdetect import detect
except ImportError:  # Permite CI sin modelo descargado
    detect = None

_HASHTAG_URL_MENTION = re.compile(
    r"(?:https?://\S+|www\.\S+|[@#]\w+)", re.IGNORECASE
)


def _clean_text(text: str) -> str:
    return _HASHTAG_URL_MENTION.sub(" ", text or "").strip()


@lru_cache(maxsize=4096)
def detect_language(text: str) -> tuple[str | None, float]:
    cleaned = _clean_text(text)
    if not cleaned or detect is None:
        return None, 0.0

    result = detect(cleaned, low_memory=True)
    if isinstance(result, dict):
        lang = result.get("lang")
        confidence = float(result.get("score", 0.0))
    else:
        lang = getattr(result, "lang", None)
        confidence = float(getattr(result, "score", 0.0))

    return lang, confidence


def is_spanish(text: str, min_confidence: float = 0.70) -> bool:
    lang, confidence = detect_language(text)
    return lang == "es" and confidence >= min_confidence
3. Puntuación de perfil
python
# Referencia de integración: https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/relationship_policy.py
# Archivo nuevo propuesto: tools/threads_profile_score.py
from __future__ import annotations

from datetime import datetime, timezone

from tools.threads_signal_schema import ThreadsProfileSignal

WEIGHTS = {
    "activity": 0.25,
    "reciprocity": 0.20,
    "topic": 0.20,
    "interaction": 0.15,
    "language": 0.15,
    "identity": 0.05,
}


def _activity_score(last_post_at: datetime | None) -> float:
    if not last_post_at:
        return 0.0
    days = (datetime.now(timezone.utc) - last_post_at).days
    if days <= 7:
        return 1.0
    if days <= 30:
        return 0.8
    if days <= 60:
        return 0.4
    return 0.0


def _reciprocity_score(followers: int, following: int) -> float:
    if following <= 0:
        return 0.5 if followers > 0 else 0.0
    ratio = followers / following
    if ratio < 0.2:
        return 0.1
    if ratio < 1.0:
        return 0.6
    if ratio <= 10.0:
        return 1.0
    if ratio <= 50.0:
        return 0.7
    return 0.4


def _identity_score(bio: str, post_count: int) -> float:
    score = 0.0
    if len(bio.strip()) >= 20:
        score += 0.6
    if post_count >= 10:
        score += 0.4
    return score


def score_profile(signal: ThreadsProfileSignal) -> float:
    interaction = min(
        1.0,
        (signal.reply_count_30d / 10.0) * 0.7
        + (signal.like_count_30d / 50.0) * 0.3,
    )
    language = 1.0 if signal.lang == "es" and signal.lang_confidence >= 0.7 else 0.0

    return round(
        WEIGHTS["activity"] * _activity_score(signal.last_post_at)
        + WEIGHTS["reciprocity"] * _reciprocity_score(signal.followers, signal.following)
        + WEIGHTS["topic"] * max(0.0, min(1.0, signal.topic_score))
        + WEIGHTS["interaction"] * interaction
        + WEIGHTS["language"] * language
        + WEIGHTS["identity"] * _identity_score(signal.bio, signal.post_count),
        4,
    )
4. Puntuación de post
python
# Referencia de integración: https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/threads_reply_queue.py
# Archivo nuevo propuesto: tools/threads_post_score.py
from __future__ import annotations

import re
from datetime import datetime, timezone

from tools.threads_signal_schema import ThreadsPostSignal

QUESTION_RE = re.compile(
    r"\?|¿|qué|cual|cuál|recomend|opin|pensáis|piensas|leéis|leen|consejo",
    re.IGNORECASE,
)

FANTASY_RE = re.compile(
    r"\b(fantasia|fantasía|romantasy|fantasia juvenil|libro|libros|leer|lectura|"
    r"novela|autor|autora|personaje|personajes|dragon|dragones|magia|reino|reinos|"
    r"booktok|bookstagram|goodreads)\b",
    re.IGNORECASE,
)


def _age_score(created_at: datetime) -> float:
    hours = max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds() / 3600)
    if hours <= 24:
        return 1.0
    if hours <= 72:
        return 0.8
    if hours <= 168:
        return 0.5
    if hours <= 336:
        return 0.2
    return 0.0


def _conversation_score(text: str, reply_count: int) -> float:
    score = 0.0
    if QUESTION_RE.search(text or ""):
        score += 0.6
    if 1 <= reply_count <= 30:
        score += 0.4
    elif 31 <= reply_count <= 100:
        score += 0.2
    return score


def _engagement_score(like_count: int, reply_count: int) -> float:
    return min(1.0, reply_count / 20.0 * 0.7 + like_count / 100.0 * 0.3)


def score_post(signal: ThreadsPostSignal) -> float:
    topic = 1.0 if FANTASY_RE.search(signal.text or "") else max(
        0.0, min(1.0, signal.topic_score)
    )

    return round(
        0.30 * _conversation_score(signal.text, signal.reply_count)
        + 0.25 * topic
        + 0.20 * _engagement_score(signal.like_count, signal.reply_count)
        + 0.15 * _age_score(signal.created_at)
        + 0.10 * (1.0 if signal.lang == "es" and signal.lang_confidence >= 0.7 else 0.0),
        4,
    )
5. Export de oportunidades
python
# Referencia de integración: https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/score_hook.py
# Archivo nuevo propuesto: tools/threads_opportunity_export.py
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from tools.threads_signal_schema import ThreadsPostSignal
from tools.threads_post_score import score_post


def export_post_opportunities(
    signals: Iterable[ThreadsPostSignal],
    output_path: str | Path,
    min_score: float = 0.55,
) -> list[dict]:
    rows: list[dict] = []

    for signal in signals:
        score = score_post(signal)
        if score < min_score:
            continue

        rows.append(
            {
                "opportunity_id": f"threads:reply:{signal.post_id}",
                "network": "threads",
                "action": "reply",
                "post_id": signal.post_id,
                "author_candidate_id": signal.author_candidate_id,
                "score": score,
                "created_at": signal.created_at.isoformat(),
                "captured_at": signal.captured_at.isoformat(),
                "features_json": json.dumps(signal.to_dict(), ensure_ascii=False),
            }
        )

    rows.sort(key=lambda row: (-row["score"], row["created_at"]))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "opportunity_id",
                "network",
                "action",
                "post_id",
                "author_candidate_id",
                "score",
                "created_at",
                "captured_at",
                "features_json",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    return rows
Qué he corregido del informe anterior

Eliminado Danie1/threads-api: está archivado desde octubre de 2023 y no debe entrar en producción.

Eliminado ksek87/social-media-followers y developer-az/pyFollowerVsFollowing: son herramientas de Instagram, no resuelven descubrimiento ni señales de Threads.

Eliminado PRO100CHOK/threads-net-posts-profiles-scraper-python del plan inmediato: depende de un servicio externo y añade una dependencia operativa innecesaria.

Aplazado Vowpal Wabbit: es útil para aprendizaje contextual, pero no debe ser parte de la primera PR; primero hacen falta señales estables y resultados observados.
vowpalwabbit

Corregido el peso del idioma: debe ser una señal fuerte, pero no un filtro absoluto en la primera iteración, porque los detectores fallan con textos cortos, emojis y hashtags.

Corregida la interpretación del ratio followers / following: no debe premiarse ciegamente un ratio alto; una cuenta grande con pocos seguidos puede tener baja probabilidad de interacción recíproca.

Plan de PR pequeñas
PR 1 — Esquema y tests

Añadir tools/threads_signal_schema.py.

Añadir tests/test_threads_signal_schema.py.

Validar fechas UTC, candidate_id único, valores negativos imposibles y serialización JSON.

PR 2 — Idioma

Añadir tools/language_signal.py y fast-langdetect como dependencia opcional.

Tests: español, inglés, texto mixto, post de 8 caracteres, texto solo con hashtags y texto vacío.

PR 3 — Score de perfil

Añadir tools/threads_profile_score.py.

Conectar su salida a score_hook.py sin modificar todavía relationship_policy.py.

Tests: cuenta inactiva, cuenta nueva, cuenta grande con pocos seguidos, cuenta equilibrada y cuenta sin bio.

PR 4 — Score de post

Añadir tools/threads_post_score.py.

Implementar decaimiento: 1.0 hasta 24 h, 0.8 hasta 72 h, 0.5 hasta 7 días, 0.2 hasta 14 días y 0 después.

Tests con posts de 1 h, 2 días, 8 días, 20 días y 40 días.

PR 5 — Export

Añadir tools/threads_opportunity_export.py.

Generar CSV ordenado por score descendente y created_at ascendente.

Garantizar opportunity_id único para evitar respuestas duplicadas.

PR 6 — Atribución

Ampliar growth_attribution.py con eventos: reply_sent, author_replied, author_followed_back, conversation_turns.

No activar bandits todavía; primero medir qué señales predicen realmente reciprocidad.

Aplicación multired
Red	Señales equivalentes	Adaptación
Bluesky	Seguidores/siguiendo, actividad, feeds, idioma	Reutilizar bluesky_growth_scan.py, bluesky_taste_collect.py y bluesky_reply_queue.py.
Mastodon	Seguidores/siguiendo, instancia, hashtags, boosts	Reutilizar mastodon_growth_scan.py y mastodon_reply_queue.py.
X	Followers/following, actividad, replies	Adaptador sobre x_scan.py y x_replies.py.
Facebook	Grupos, páginas, comentarios, reacciones	Priorizar afinidad de grupo; el “following” es menos útil.
Pinterest	Guardados, seguidores, tableros, frescura	Objetivo de descubrimiento más que conversación.
Reddit	Karma, subreddit, actividad, idioma, antigüedad	Reutilizar reddit_scan.py; la antigüedad del hilo es crítica.
TikTok	Comentarios recientes, nicho, actividad	Reutilizar tiktok_growth_scan.py; priorizar comentarios con pregunta u opinión.
Instagram	Comentarios, seguidores, Reels, afinidad	Reutilizar instagram_commenters_scan.py; los comentaristas recientes son mejores candidatos.
Fuentes

Repositorio espejo: davidpd89/ci-sandbox-tmp, archivos tools/threads_scan.py, tools/threads_interact.py, tools/threads_reply_queue.py, tools/reciprocity.py, tools/relationship_policy.py, tools/growth_core.py y tools/score_hook.py.

Zeeshanahmad4/Threads-Scraper: repo activo de Python con src/scraper/parser.py y src/scraper/exporter.py; actualizado el 21 de agosto de 2026.

LlmKira/fast-langdetect: detector FastText offline, MIT, 324 estrellas y actividad en 2026.
pypi

Threads API oficial de Meta: publicación, perfiles, gestión de respuestas e insights.
developers.facebook

VowpalWabbit/vowpal_wabbit: contextual bandits; recomendado solo como evolución posterior.
vowpalwabbit

Danie1/threads-api: archivado; excluido del plan.
