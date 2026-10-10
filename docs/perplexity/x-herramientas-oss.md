# Herramientas y código abierto en X (Twitter)

Fuente: informe de Perplexity (https://www.perplexity.ai/search/899673b4-f8aa-4e2f-bfaa-337bb6c6cd3c), generado 10/10/2026.

Informe mejorado: repos, SDK, skills y agentes para X con Python en Windows

He vuelto a revisar el informe contra el código real de davidpd89/ci-sandbox-tmp y contra los metadatos actuales de GitHub. He eliminado o degradado las recomendaciones dudosas: XActions no apareció en la búsqueda verificada de repos activos y su enfoque de automatización masiva no encaja con la arquitectura existente; MiloAgent tampoco se pudo verificar como repositorio activo, así que desaparece. También retiro la recomendación de adoptar Agent-Reach, porque depende de cookies y no aporta una pieza lo bastante sólida para nuestro pipeline.

Importante sobre el código: intenté recuperar los archivos fuente completos para pegarlos tal cual, pero la extracción de contenido bruto falló en esta sesión. Para no inventar código ajeno, incluyo adaptaciones propias, cortas y copiables, con la URL exacta del archivo o documentación de origen indicada; no las presento como copias literales.

Resumen

El sistema ya tiene discovery, interacción, publicación, colas, ledger, atribución y auditoría para X. La mejora correcta no es instalar un agente externo, sino añadir: una fachada API oficial, un discovery opcional con twscrape, métricas estructuradas y herramientas MCP de solo lectura/encolado.
github

Los repos verificados y activos hoy son ihuzaifashoukat/x-use (push 2026-10-09, MIT, 171 estrellas), vladkens/twscrape (push 2026-10-05, MIT, 2.851 estrellas), d60/twikit (push 2026-03-10, MIT, 4.718 estrellas), Altimis/Scweet (push 2026-09-29, MIT, 1.641 estrellas), mahrtayyab/tweety (push 2026-09-13, 669 estrellas) y shaikhsajid1111/twitter-scraper-selenium (push 2026-08-17, MIT, 346 estrellas).
github
+2

Hallazgos verificados
Repositorio	Estado verificado	Qué copiar	Integración	Decisión
ihuzaifashoukat/x-use	Python, MIT, 171 estrellas, push 2026-10-09; MCP-ready y basado en Selenium. 
github
	Patrón de herramientas MCP: acciones atómicas, sesión de navegador y estado local.	Crear tools/x_agent_tools.py que exponga search_candidates, get_thread_context, draft_reply, validate_reply y queue_action; reutiliza browser_pool.py, reply_queue.py y action_ledger.py.	Adoptar arquitectura, no dependencia.
vladkens/twscrape	Python, MIT, 2.851 estrellas, push 2026-10-05; multi-cuenta, rotación y rate limits. 
scrapfly
	Pool de cuentas, backoff, CLI y consultas de búsqueda/perfiles/respuestas.	tools/x_discovery_scrape.py, desactivado por defecto; normaliza resultados al esquema de x_scan.py y scan_common.py.	Adoptar como discovery opcional.
d60/twikit	Python, MIT, 4.718 estrellas, push 2026-03-10; cliente sin API key. 
opensourcealternatives
	Ejemplos de búsqueda, timeline y operaciones de lectura.	Solo como referencia de modelado de resultados; no como motor principal, porque tiene 160 issues abiertas. 
opensourcealternatives
	Referencia, no dependencia.
Altimis/Scweet	Python, MIT, 1.641 estrellas, push 2026-09-29; scraping async, proxies y pool multi-cuenta. 
scrapfly
	Arquitectura async y pool de cuentas.	Alternativa a twscrape si se necesita concurrencia; mismo adaptador de salida.	Reserva técnica.
mahrtayyab/tweety	Python, 669 estrellas, push 2026-09-13. 
scrapfly
	Modelado de objetos tweet/perfil.	No integrar directamente; usar como referencia de campos y normalización.	Descartar como dependencia.
shaikhsajid1111/twitter-scraper-selenium	Python, MIT, 346 estrellas, push 2026-08-17. 
scrapfly
	Scraping por Selenium y export CSV/JSON.	Redundante: el repo ya tiene Selenium, pool, CDP y auditoría propias.	Descartar.
tweepy/tweepy	SDK Python maduro para X API; 11,2k estrellas según índice de temas.	Cliente oficial, OAuth, paginación y errores.	tools/x_api_client.py como única fachada API.	Adoptar.
xdevplatform/samples	Ejemplos oficiales X API v2; 3,2k estrellas.	Contratos de endpoints y ejemplos Python.	Fixtures y tests de contrato en tests/.	Adoptar como referencia.
Código copiable para integrar
1. Fachada API X

Adaptación propia para tools/x_api_client.py, inspirada en los patrones de tweepy/tweepy y xdevplatform/samples.

python
# Origen de patrones: https://github.com/tweepy/tweepy y https://github.com/xdevplatform/samples
# Archivo destino: tools/x_api_client.py
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import tweepy


@dataclass
class XApiConfig:
    bearer_token: str
    max_retries: int = 3
    backoff_seconds: float = 2.0


class XApiClient:
    """Fachada mínima y testeable para X API v2."""

    def __init__(self, config: XApiConfig | None = None):
        token = config.bearer_token if config else os.environ["X_BEARER_TOKEN"]
        self._client = tweepy.Client(bearer_token=token, wait_on_rate_limit=False)
        self._max_retries = config.max_retries if config else 3
        self._backoff = config.backoff_seconds if config else 2.0

    def search_recent(self, query: str, max_results: int = 25):
        return self._with_retry(
            lambda: self._client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=["created_at", "public_metrics", "lang", "author_id"],
                expansions=["author_id"],
                user_fields=["username", "name", "public_metrics"],
            )
        )

    def get_tweet(self, tweet_id: str):
        return self._with_retry(
            lambda: self._client.get_tweet(
                tweet_id,
                tweet_fields=["created_at", "public_metrics", "conversation_id", "lang"],
                expansions=["author_id"],
                user_fields=["username", "public_metrics"],
            )
        )

    def _with_retry(self, fn):
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return fn()
            except tweepy.TooManyRequests as error:
                last_error = error
                time.sleep(self._backoff * (2 ** (attempt - 1)))
        raise last_error

Por qué encaja: x_recent_api.py ya existe, pero esta fachada centraliza credenciales, reintentos y campos; evita que cada módulo repita lógica de API.
github

2. Discovery opcional con twscrape

Adaptación propia para tools/x_discovery_scrape.py, basada en la API documentada de vladkens/twscrape.
scrapfly

python
# Origen/documentación: https://github.com/vladkens/twscrape
# Archivo destino: tools/x_discovery_scrape.py
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

from twscrape import AccountsPool, API


@dataclass
class XCandidate:
    tweet_id: str
    author_username: str
    text: str
    created_at: str
    source: str
    network: str = "x"


async def discover_candidates(
    query: str,
    limit: int = 50,
    accounts_csv: str = "accounts.csv",
) -> list[XCandidate]:
    pool = AccountsPool()
    await pool.login(accounts_csv)

    api = API(pool)
    candidates: list[XCandidate] = []

    async for tweet in api.search(query, limit=limit):
        candidates.append(
            XCandidate(
                tweet_id=str(tweet.id),
                author_username=tweet.user.username,
                text=tweet.rawContent,
                created_at=tweet.date.isoformat(),
                source="twscrape",
            )
        )

    return candidates


if __name__ == "__main__":
    print(asyncio.run(discover_candidates("fantasía juvenil lang:es -is:retweet", 50)))

Regla de integración: el resultado nunca se publica ni comenta directamente; pasa por deduplicación, filtros de edad/idioma/nicho y luego a la cola existente.
github

3. Herramientas MCP para el agente X

Adaptación propia para tools/x_agent_tools.py, inspirada en el patrón MCP de ihuzaifashoukat/x-use.
github

python
# Origen/patrón: https://github.com/ihuzaifashoukat/x-use
# Archivo destino: tools/x_agent_tools.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class AgentToolResult:
    ok: bool
    action: str
    data: dict | None = None
    error: str | None = None


class XAgentTools:
    """Herramientas seguras para un agente: lee, propone y encola; nunca publica."""

    def __init__(self, scanner, reply_writer, action_ledger):
        self.scanner = scanner
        self.reply_writer = reply_writer
        self.ledger = action_ledger

    def search_candidates(self, query: str, limit: int = 20) -> AgentToolResult:
        try:
            candidates = self.scanner.search(query=query, limit=limit)
            return AgentToolResult(True, "search_candidates", {"candidates": candidates})
        except Exception as error:
            return AgentToolResult(False, "search_candidates", error=str(error))

    def draft_reply(self, tweet_id: str, voice: str = "david_porto") -> AgentToolResult:
        try:
            draft = self.reply_writer.draft(tweet_id=tweet_id, voice=voice)
            return AgentToolResult(True, "draft_reply", {"draft": draft})
        except Exception as error:
            return AgentToolResult(False, "draft_reply", error=str(error))

    def queue_action(
        self,
        tweet_id: str,
        draft: str,
        kind: Literal["reply", "like"] = "reply",
    ) -> AgentToolResult:
        try:
            action_id = self.ledger.enqueue(
                network="x",
                tweet_id=tweet_id,
                kind=kind,
                payload={"draft": draft},
            )
            return AgentToolResult(True, "queue_action", {"action_id": action_id})
        except Exception as error:
            return AgentToolResult(False, "queue_action", error=str(error))

Por qué encaja: el agente no obtiene permiso para publicar; solo consulta, redacta y encola. La ejecución real permanece en x_execute.py, con idempotencia y trazabilidad en action_ledger.py.
github

4. Contrato de métricas

Adaptación propia para tools/x_metrics_collector.py, alineada con growth_attribution.py y action_ledger.py del repo.
github

python
# Archivo destino: tools/x_metrics_collector.py
# Integración con: tools/growth_attribution.py y tools/action_ledger.py
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class XMetricObservation:
    action_id: str
    tweet_id: str
    network: str
    impressions: int
    likes: int
    replies: int
    reposts: int
    profile_visits: int | None
    observed_at: str
    source: str


def build_observation(
    action_id: str,
    tweet_id: str,
    metrics: dict,
    source: str = "x_api_v2",
) -> XMetricObservation:
    public = metrics.get("public_metrics", {})
    return XMetricObservation(
        action_id=action_id,
        tweet_id=tweet_id,
        network="x",
        impressions=int(public.get("impression_count", 0)),
        likes=int(public.get("like_count", 0)),
        replies=int(public.get("reply_count", 0)),
        reposts=int(public.get("retweet_count", 0)),
        profile_visits=metrics.get("profile_visits"),
        observed_at=datetime.now(timezone.utc).isoformat(),
        source=source,
    )


def observation_to_row(observation: XMetricObservation) -> dict:
    return asdict(observation)
Qué he quitado del informe anterior

XActions: lo retiro como recomendación de adopción. No apareció en la búsqueda verificada de repos activos y su propuesta de follow/unfollow, likes y comentarios automáticos masivos duplicaría y complicaría x_interact.py, volume_ramp.py, action_ledger.py y los mecanismos de presupuesto ya existentes.
github

MiloAgent: lo elimino porque no pude verificar su repositorio ni actividad en esta pasada.

Agent-Reach: lo elimino como dependencia; su valor es conceptual y ya podemos lograr el mismo objetivo con adaptadores propios de solo lectura.

“Copiar tal cual” sin verificación: no incluyo bloques presentados como copias literales si no pude extraer el archivo fuente completo. Los bloques anteriores son adaptaciones propias, con URLs de origen señaladas.

Plan de PR pequeñas
PR 1 — x_api_client.py

Añadir fachada Tweepy, variables de entorno y tests con respuestas simuladas.

Reutilizar http_retry.py, exec_common.py y network_capabilities.py.

Criterio: ningún módulo nuevo accede a la API sin pasar por esta clase.

PR 2 — x_metrics_collector.py

Añadir observaciones por action_id, tweet_id, timestamp, fuente y métricas.

Integrar con growth_attribution.py y daily_review.py.

Tests: idempotencia, campos ausentes, deduplicación y agregación diaria.

PR 3 — x_discovery_scrape.py

Añadir twscrape como dependencia opcional.

Flag --enabled, desactivado por defecto.

Normalizar salida al esquema de x_scan.py.

Tests: duplicados, idioma español, edad del post, fallo de cuenta y rate limit.

PR 4 — x_agent_tools.py

Exponer herramientas de lectura, borrador y encolado.

Prohibir publicación directa desde el agente.

Tests: JSON de salida, idempotencia, presupuesto y trazabilidad en ledger.

PR 5 — Experimentos multired

Crear tools/experiment_runner.py, no solo x_experiment_runner.py.

Dimensiones obligatorias: network, action_kind, variant, cohort, action_id.

Reutilizar growth_attribution.py, action_ledger.py y daily_review.py.

Tests: asignación determinista, métricas por variante y condiciones de parada.

Aplicación a las demás redes

La fachada x_api_client.py debe convertirse en un patrón común: bluesky_api_client.py, mastodon_api_client.py, threads_api_client.py, facebook_api_client.py, instagram_api_client.py, pinterest_api_client.py, reddit_api_client.py y tiktok_api_client.py.

XMetricObservation debe generalizarse a MetricObservation, con network obligatorio.

XAgentTools debe convertirse en NetworkAgentTools, con adaptadores por red pero el mismo contrato: search_candidates, get_context, draft_reply, validate_reply, queue_action, record_result.

twscrape es específico de X; para el resto de redes se mantienen los módulos nativos ya presentes en el repo y se añaden adaptadores de solo lectura cuando aporte cobertura real.
github

Fuentes

x-use — repositorio y metadatos
github

twscrape — repositorio y metadatos
scrapfly

twikit — repositorio y metadatos
opensourcealternatives

Scweet — repositorio y metadatos
scrapfly

tweety — repositorio y metadatos
scrapfly

twitter-scraper-selenium — repositorio y metadatos
scrapfly

Tweepy — índice GitHub Topics

XDeveloper Platform samples

Estructura del repo espejo, rama research/perplexity-crecimiento-x
github
