# Herramientas y código abierto en Mastodon

Fuente: informe de Perplexity (https://www.perplexity.ai/search/3e3f4af8-6539-4f7f-9e84-d6d7c3831f5a), generado 10/10/2026.

Informe mejorado: repos, SDK, skills y agentes para Mastodon con Python
Resumen

He revisado el informe anterior y eliminado o rebajado las piezas que no aportan suficiente valor a nuestro sistema: polybot está archivado, LLM-Mastodon-Agent es un marco de investigación sin evidencia suficiente de mantenimiento, y scidsg/mastodon-scheduler no aporta una ventaja clara frente a una cola propia ligera más GitHub Actions. En su lugar, la base recomendada es Mastodon.py para API, mastodon_digest para ranking inicial de señales sociales, toot como referencia de CLI/autenticación y APScheduler sólo como runner opcional en Windows.
github

El repositorio espejo ya tiene SISTEMA_DIARIO_MASTODON/growth_config.json, pero la carpeta no contiene código Python; por tanto, el objetivo es añadir un adaptador Mastodon que lea esa configuración y comparta interfaces con las demás redes, sin duplicar configuración ni lógica de negocio.

Hallazgos verificados
Recurso	Actividad verificada	Valor para nuestro sistema	Qué reutilizar	Qué descartar
halcy/Mastodon.py	958 estrellas; último push el 7 de octubre de 2026; licencia MIT; no archivado.	SDK principal para autenticación, publicación, timelines, búsqueda, relaciones y notificaciones.	Cliente, modelos y patrones de paginación.	No reimplementar llamadas HTTP ni OAuth.
hodgesmr/mastodon_digest	432 estrellas; último push el 6 de octubre de 2026; licencia BSD-3-Clause; no archivado.	Agrega posts recientes y populares del timeline; ideal como base de ranking por señales sociales.	Ponderación, agregación temporal y selección de posts relevantes.	Su salida tipo “digest”; nosotros necesitamos candidatos para comentar.
ihabunek/toot	1.325 estrellas; último push el 12 de septiembre de 2026; Python; no archivado.	CLI/TUI maduro para Mastodon; útil como referencia de configuración, autenticación y comandos.	Estructura de comandos, manejo de credenciales y experiencia de diagnóstico.	Su TUI y dependencias de interfaz; no encajan en un pipeline headless.
kimusan/mastui	91 estrellas; último push el 7 de octubre de 2026; licencia MIT; activo.	Cliente TUI moderno basado en Textual; referencia de patrones de UI y acceso a la API.	Patrones de normalización de estados y manejo de cuentas.	La interfaz TUI completa; no aporta al pipeline automatizado.

mauforonda/mastodon_digest_bookmarkfeed
	Fork especializado de mastodon_digest; usa parámetros como -n 24 -s SimpleWeighted -t lax. 
docs.joinmastodon
	Muestra cómo adaptar el algoritmo original a un flujo continuo y personalizado.	Idea de ventana temporal, estrategia de pesos y umbral de selección.	Su finalidad de bookmark feed; no es nuestro caso.

mauforonda/mastodon_email_digest
	Fork de mastodon_digest que selecciona posts no vistos y populares. 
github
	Útil para entender deduplicación entre ejecuciones y selección de novedades.	Estado de “ya visto”, ventana temporal y ranking.	Envío por correo; no forma parte del sistema.

adamghill/fediview
	Proyecto que emplea un fork de mastodon_digest para su algoritmo. 
docs.joinmastodon
	Confirma que el algoritmo de digest es reutilizable como componente independiente.	Separación entre recolección, ranking y presentación.	Su producto final; no lo necesitamos.

DocTocToc/doctoctocbot
	Bot Mastodon/Twitter con backend Django y tareas Celery. 
github
	Referencia de arquitectura para tareas asíncronas y colas.	Concepto de tareas separadas de la API.	Django + Celery: excesivo para nuestro pipeline actual.

VladUZH/harken
	Social listening autoalojado; admite token de Mastodon mediante HARKEN_MASTODON_ACCESS_TOKEN. 
github
	Referencia para social listening y configuración de acceso por token.	Modelo de fuentes, alertas y configuración por entorno.	Despliegue completo del producto; no es necesario.
bm-github/owasp-social-osint-agent	103 estrellas; último push el 25 de abril de 2026; MIT; no archivado.	Agente multiplataforma con análisis de contenido y mapeo de red.	Ideas de extracción de señales y análisis asistido por LLM.	Enfoque OSINT/reconnaissance; no aplica a crecimiento editorial.

agronholm/apscheduler
	Biblioteca Python de scheduling y colas; soporta cron, intervalos y calendario.	Runner opcional en Windows para ejecuciones locales.	Triggers y reintentos.	No usar como scheduler único si CI ya programa los jobs.

Sari95/Mastodon-Bot-with-Python
	Bot reciente, actualizado en agosto de 2026; registro, publicación y reblog por hashtag; documentación para Windows y Task Scheduler.	Referencia sencilla para registro inicial, .env, publicación y automatización en Windows.	Patrón de configuración y registro de aplicación.	Reblog automático sin scoring ni contexto.
Correcciones al informe anterior

He retirado estas recomendaciones porque eran dudosas o no aplicaban:

russss/polybot: aunque su descripción encaja con un sistema multired, el repositorio está archivado; no debe usarse como dependencia ni como base activa.

cl-trier/LLM-Mastodon-Agent: es un marco de investigación, pero no he verificado actividad, calidad de mantenimiento ni compatibilidad suficiente; lo sustituyo por un agente propio, acotado y testeable.

scidsg/mastodon-scheduler: no aporta una capacidad que no podamos implementar mejor con una cola JSONL/SQLite y GitHub Actions; lo elimino como dependencia.

Horhik/Instagram2Fedi y cquest/tootbot: resuelven cross-posting, no descubrimiento, ranking ni aprendizaje; no son prioritarios para este módulo.

laggykiller/sticker-convert y Lynnesbian/OCRbot: útiles para casos concretos de multimedia, pero no para el núcleo de crecimiento social.

Código reutilizable
1. Cliente Mastodon normalizado

Este módulo centraliza el acceso a la API y permite sustituir el cliente real por un doble de pruebas. Está basado en el patrón de Mastodon.py; el archivo original del SDK es mastodon/Mastodon.py: <https://github.com/halcy/Mastodon.py/blob/master/mastodon/Mastodon.py>.

python
# Fuente: https://github.com/halcy/Mastodon.py/blob/master/mastodon/Mastodon.py
# Adaptación para el sistema multired de David Porto.
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mastodon import Mastodon


@dataclass(frozen=True)
class MastodonCredentials:
    api_base_url: str
    access_token: str


class MastodonClient(Protocol):
    def timeline_hashtag(self, hashtag: str, limit: int = 20): ...
    def search_v2(self, q: str, result_type: str | None = None, limit: int = 20): ...
    def status_post(self, status: str, **kwargs): ...
    def status_favourite(self, status_id: str): ...
    def status_reblog(self, status_id: str): ...
    def account_follow(self, account_id: str): ...
    def notifications(self, **kwargs): ...


def build_mastodon_client(credentials: MastodonCredentials) -> MastodonClient:
    return Mastodon(
        api_base_url=credentials.api_base_url,
        access_token=credentials.access_token,
    )
2. Descubrimiento por hashtag con cursor incremental

La API de Mastodon permite leer timelines por hashtag; Mastodon.py expone timeline_hashtag y admite paginación mediante min_id, max_id y since_id.

python
# Fuente: https://mastodonpy.readthedocs.io/en/stable/07_timelines.html
# Adaptación para descubrimiento incremental en Mastodon.
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass
class DiscoveredPost:
    network: str
    post_id: str
    author_id: str
    author_handle: str
    content: str
    url: str
    created_at: str
    language: str | None
    favourites: int
    reblogs: int
    replies: int
    hashtags: list[str]
    source: str


def discover_hashtag(
    client,
    hashtag: str,
    *,
    since_id: str | None = None,
    limit: int = 40,
) -> tuple[list[DiscoveredPost], str | None]:
    statuses = client.timeline_hashtag(
        hashtag=hashtag,
        limit=limit,
        since_id=since_id,
    )

    posts: list[DiscoveredPost] = []
    newest_id: str | None = None

    for status in statuses:
        post = DiscoveredPost(
            network="mastodon",
            post_id=str(status["id"]),
            author_id=str(status["account"]["id"]),
            author_handle=status["account"]["acct"],
            content=status.get("content", ""),
            url=status.get("url", ""),
            created_at=status.get("created_at", ""),
            language=status.get("language"),
            favourites=int(status.get("favourites_count", 0)),
            reblogs=int(status.get("reblogs_count", 0)),
            replies=int(status.get("replies_count", 0)),
            hashtags=[tag["name"] for tag in status.get("tags", [])],
            source=f"hashtag:{hashtag}",
        )
        posts.append(post)

        if newest_id is None or int(post.post_id) > int(newest_id):
            newest_id = post.post_id

    return posts, newest_id


def serialize_posts(posts: Iterable[DiscoveredPost]) -> list[dict]:
    return [asdict(post) for post in posts]
3. Ranking inicial basado en señales sociales

mastodon_digest agrega posts recientes y populares del timeline; su enfoque es aprovechable como inspiración para un ranking transparente por interacciones y frescura.
docs.joinmastodon

python
# Fuente: https://github.com/hodgesmr/mastodon_digest
# Adaptación: ranking de candidatos para interacción contextual.
from __future__ import annotations

import math
from datetime import datetime, timezone


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _age_hours(created_at: str) -> float:
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return 999.0

    now = datetime.now(timezone.utc)
    return max(0.0, (now - created).total_seconds() / 3600)


def score_post(
    post,
    *,
    topic_match: float,
    author_relevance: float,
    seen_before: bool = False,
) -> float:
    if seen_before:
        return 0.0

    engagement = (
        _safe_int(post.favourites)
        + 2 * _safe_int(post.reblogs)
        + 3 * _safe_int(post.replies)
    )

    # Logaritmo evita que un post viral domine todo el ranking.
    engagement_score = math.log1p(engagement)

    age = _age_hours(post.created_at)
    freshness = max(0.0, 1.0 - min(age / 48.0, 1.0))

    language_bonus = 0.15 if post.language == "es" else 0.0

    return round(
        0.35 * topic_match
        + 0.25 * engagement_score
        + 0.20 * freshness
        + 0.10 * author_relevance
        + language_bonus,
        4,
    )
4. Acción con idempotencia y auditoría

Mastodon.py admite publicación con parámetros como visibilidad, idioma, programación, medios y idempotency_key; el ejemplo público de GitHub Actions usa status_post y un token almacenado como secreto.

python
# Fuente: https://buerviper.github.io/blog/2024/writing-a-mastodon-bot-in-python/
# Adaptación: publicación segura, trazable y reanudable.
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass
class CommentAction:
    post_id: str
    author_id: str
    comment: str
    visibility: str = "public"
    language: str = "es"


def action_idempotency_key(action: CommentAction) -> str:
    payload = json.dumps(
        {
            "network": "mastodon",
            "post_id": action.post_id,
            "author_id": action.author_id,
            "comment": action.comment,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def publish_comment(client, action: CommentAction, *, dry_run: bool = True) -> dict:
    key = action_idempotency_key(action)

    if dry_run:
        return {
            "status": "dry_run",
            "idempotency_key": key,
            "post_id": action.post_id,
        }

    result = client.status_post(
        status=action.comment,
        in_reply_to_id=action.post_id,
        visibility=action.visibility,
        language=action.language,
        idempotency_key=key,
    )

    return {
        "status": "published",
        "idempotency_key": key,
        "mastodon_status_id": str(result["id"]),
        "post_id": action.post_id,
    }
5. Workflow CI seguro

Este patrón procede de un ejemplo público de bot Mastodon con GitHub Actions: instala Python, utiliza secretos y ejecuta el bot mediante Mastodon.status_post.

text
# Fuente: https://buerviper.github.io/blog/2024/writing-a-mastodon-bot-in-python/
# Adaptación: pipeline de crecimiento para Mastodon.
name: Mastodon growth

on:
  workflow_dispatch:
  schedule:
    - cron: "15 7,13,19 * * *"

jobs:
  growth:
    runs-on: ubuntu-latest
    env:
      MASTODON_API_BASE_URL: ${{ secrets.MASTODON_API_BASE_URL }}
      MASTODON_ACCESS_TOKEN: ${{ secrets.MASTODON_ACCESS_TOKEN }}
      DRY_RUN: "true"
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-ci.txt

      - name: Discovery and ranking
        run: python -m growth.mastodon discover --limit 100

      - name: Draft actions
        run: python -m growth.mastodon draft --max-actions 5

      - name: Publish approved actions
        if: env.DRY_RUN == 'false'
        run: python -m growth.mastodon publish --max-actions 5
Arquitectura recomendada
Módulos mínimos

adapters/mastodon/client.py: única dependencia de Mastodon.py.

adapters/mastodon/discovery.py: hashtags, búsqueda y timelines.

ranking/mastodon_scorer.py: afinidad, engagement, frescura, idioma y relevancia del autor.

compose/mastodon_comments.py: variantes de comentario contextual en español.

actions/mastodon.py: comentario, seguimiento selectivo y reblog de alta confianza.

learning/mastodon_feedback.py: lectura diferida de favoritos, reblogs, respuestas y nuevos seguidores.

storage/seen_posts.py: deduplicación persistente entre ejecuciones.

Reglas de acción

La prioridad debe ser:

Comentario contextual en español.

Seguimiento de perfiles claramente afines.

Reblog sólo de posts excepcionalmente relevantes.

Ninguna acción si el post es ambiguo, antiguo, duplicado o fuera de nicho.

El reblog automático por hashtag, presente en el bot de referencia, no debe copiarse tal cual: debe convertirse en una acción condicionada por score, contexto y presupuesto diario.

Plan de PR pequeñas
PR 1 — Base del adaptador

Añadir adapters/mastodon/client.py, modelos normalizados y tests con cliente falso. Usar Mastodon.py como única librería de API.

Tests: inicialización, errores de credenciales y normalización de estados.

PR 2 — Descubrimiento

Implementar hashtags, /api/v2/search y timelines; guardar since_id y posts vistos. La búsqueda oficial admite cuentas, estados y hashtags, aunque la búsqueda de estados depende de que la instancia tenga Elasticsearch.

Tests: paginación, deduplicación, idioma y fallback si no hay resultados de estados.

PR 3 — Ranking

Implementar el scorer con pesos configurables en growth_config.json. Empezar con afinidad, engagement logarítmico, frescura, idioma y relevancia de autor.

Tests: casos de posts nuevos, virales, antiguos, duplicados y fuera de tema.

PR 4 — Comentarios

Crear generador de comentarios con plantillas variadas, límite de longitud y verificación de contexto. Cada comentario debe referirse a un elemento identificable del post original.

Tests: diversidad, español, longitud, no repetición consecutiva y bloqueo sin contexto.

PR 5 — Acciones seguras

Implementar publicación con idempotency_key, language="es", visibilidad configurable, dry-run y auditoría.

Tests: idempotencia, reintentos, presupuesto diario y modo dry-run.

PR 6 — Aprendizaje

Leer notificaciones y métricas 24–72 horas después de cada acción; actualizar pesos por hashtag, autor, hora y plantilla.

Tests: atribución, actualización incremental y reproducibilidad.

PR 7 — CI y Windows

Añadir workflow GitHub Actions y script opcional para Windows con APScheduler. No ejecutar CI y APScheduler sobre la misma cola simultáneamente.

Tests: dry-run, validación de secrets y ejecución local simulada.

Aplicación multi-red

El adaptador Mastodon debe implementar interfaces comunes para que X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram compartan discovery, ranking, composición, acciones y aprendizaje.

Capa	Contrato común	Especialización Mastodon
Discovery	discover(config) -> list[SocialPost]	Hashtags, búsqueda, timelines y listas
Ranking	score(post, context) -> float	Engagement, frescura, idioma y afinidad
Composición	compose(post, context) -> list[str]	Comentarios en español, máx. 500 caracteres
Acción	execute(action) -> ActionOutcome	Reply, follow, reblog
Learning	collect_outcomes(action) -> ActionOutcome	Favoritos, reblogs, respuestas y seguidores
Fuentes

halcy/Mastodon.py — SDK Python activo, MIT, 958 estrellas y push reciente.

Mastodon.py — documentación
 — referencia de API, timelines y publicación.

hodgesmr/mastodon_digest — ranking de posts populares, BSD-3, activo.

mauforonda/mastodon_digest_bookmarkfeed
 — adaptación con ventana temporal y pesos.
docs.joinmastodon

mauforonda/mastodon_email_digest
 — deduplicación y selección de novedades.
github

ihabunek/toot — CLI/TUI Python activo para Mastodon.

kimusan/mastui — cliente TUI activo y moderno.

Mastodon Search API
 — búsqueda oficial de cuentas, estados y hashtags.

Mastodon.py — Timelines
 — acceso y paginación de timelines.

Sari95/Mastodon-Bot-with-Python
 — referencia reciente para Windows y Task Scheduler.

Ejemplo de bot Mastodon con GitHub Actions
 — patrón de CI, secrets y publicación.

agronholm/apscheduler
 — scheduling Python para Windows.

VladUZH/harken
 — social listening autoalojado con soporte Mastodon.
github

DocTocToc/doctoctocbot
 — referencia de bot multiplataforma con tareas asíncronas.
github
