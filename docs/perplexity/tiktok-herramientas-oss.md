# Herramientas y código abierto en TikTok

Fuente: informe de Perplexity (https://www.perplexity.ai/search/221921f3-1398-4fa3-bb5f-3dc12a150d21), generado 10/10/2026.

Informe mejorado: repos, SDK, skills y agentes para TikTok con Python en Windows
Resumen

He revisado de nuevo davidpd89/ci-sandbox-tmp y he descartado las recomendaciones débiles del informe anterior: auto-tiktok, TikTokAutoUploader, los dashboards antiguos de Streamlit y los MCP de pago como HasData/tiktok-mcp no aportan suficiente valor frente a tu sistema actual o dependen de servicios externos de pago. La apuesta mejorada se centra en archivo y watchlist con Evil0ctal, discovery MCP ligero con terrylinhaochen/tiktok_mcp, métricas de Ads con el SDK/MCP oficial, y producción de clips con autoclip o MoneyPrinterTurbo.
business-api.tiktok
+1

Tu repo ya resuelve discovery, interacción, comentarios, publicación, auditoría, recíproca, colas, rampas y atribución; por tanto, ninguna propuesta siguiente duplica esas funciones: todas se integran como fuentes de datos, adaptadores o productores de assets que alimentan tiktok_growth_scan, tiktok_discovery, action_ledger y growth_attribution.

Hallazgos verificados
Repositorio / SDK	Estado comprobado	Qué resuelve	Qué copiar o integrar	Veredicto

Evil0ctal/Douyin_TikTok_Download_API
	Activo; Apache-2.0; Python 3.12, FastAPI, PostgreSQL/TimescaleDB, Docker y MCP documentados.	Archivo histórico de posts, perfiles, comentarios, búsqueda, métricas y watchlist autoalojada.	Patrón de API de datos, snapshots periódicos, identidad pool y MCP; no su consola web.	Prioridad 1

terrylinhaochen/tiktok_mcp
	Activo; MIT; incluye servidor MCP, tests, Docker y configuración Smithery. 
github
	Búsqueda por hashtag, tendencias, metadatos, engagement, proxy, rate limit y health check.	Cliente de búsqueda por hashtag y esquema de respuesta con views, likes, shares y comments.	Prioridad 2

tiktok/tiktok-business-api-sdk
	SDK oficial; paquete PyPI tiktok-business-api-sdk-official 1.1.3, publicado el 27 de febrero de 2026.	Reporting, campañas, anuncios, audiencias y medición oficial de TikTok Ads.	Solo clientes de reporting/medición; activarlo únicamente si hay Ads.	Condicional
AdsMCP/tiktok-ads-mcp-server	Activo; 51 estrellas; actualizado el 9 de octubre de 2026; Python y MCP.	Expone la TikTok Ads Marketing API a agentes mediante MCP.	Patrón de herramientas MCP para campañas, informes y creativos; no sustituye al SDK oficial para producción.	Condicional
davidteather/TikTok-Api	v7.3.3 publicada en abril de 2026; commits hasta agosto de 2026; requiere Playwright, ms_token y normalmente proxies.	Lectura ligera de tendencias, usuarios y contenido público.	Normalización de respuestas, reintentos y manejo de ms_token; no como base principal.	Fallback

MEOMcGill/pytok
	Activo como alternativa basada en Camoufox sobre la idea de TikTokApi; automatiza resolución de captcha mediante navegador. 
pypi
	Feeds de hashtag, búsqueda y sonidos con enfoque de navegador.	Patrón de iteradores asíncronos por feed y manejo de navegador/Camoufox.	Fallback robusto

scrapfly/scrapfly-scrapers
	Activo; incluye guía y scraper TikTok con comentarios, búsqueda, hashtags y canales.	Patrones de extracción y normalización de comentarios, hashtags y búsqueda.	Selectores, normalizadores y casos de prueba; no depender de su API comercial.	Referencia
zhouxiaoka/autoclip	Muy activo; 9.298 estrellas; actualizado hoy, 10 de octubre de 2026; Python, MCP y escritorio.	Convierte vídeos largos en clips verticales con subtítulos, portada y copy para TikTok, Reels y Shorts.	Pipeline de segmentación, subtítulos, portada y copy; conectar su salida a content_queue.	Prioridad 3
harry0703/MoneyPrinterTurbo	Muy activo; 129.417 estrellas; actualizado hoy; Python, FFmpeg, LLM, TTS y flujo de vídeo corto.	Genera vídeos verticales desde tema o keyword, con subtítulos y voz.	Plantillas de composición, FFmpeg, subtítulos y automatización; útil para clips promocionales de fantasía.	Prioridad 3
masterFuf/taktik-bot	Activo; 156 estrellas; actualizado hoy; Python, uiautomator2 y ADB sobre Android real.	Automatización en dispositivo Android real: likes, follows, DMs y scraping.	Solo patrones de estabilidad móvil, detección de UI y límites; tu tiktok_mobile_* ya cubre la ejecución.	Referencia

Taisly Agent Kit
	Activo; MIT; SDK, CLI, SKILL.md y MCP para publicar en TikTok, Reels, Shorts, X y Facebook.	Publicación agéntica multiplataforma mediante contrato JSON/MCP.	Diseño de SKILL.md, esquemas JSON y adaptador de publicación; requiere videoUrl público para publicación remota.	Opcional
3441293738/creatorhub	Activo; 2.241 estrellas; actualizado hoy; FastAPI, Playwright y monitorización multiplataforma.	Panel de monitorización y recolección multiplataforma.	Arquitectura de monitorización y colas; no copiar su flujo de “reposteo”.	Referencia

Eliminado del informe anterior: auto-tiktok y TikTokAutoUploader como recomendaciones, porque duplican publicación que ya tienes en tiktok_execute.py y tiktok_mobile_execute.py; smaranjitghose/TikTok_Analytics y vivek8031/TikTokAnalytics, porque son proyectos antiguos y de menor mantenimiento; HasData/tiktok-mcp, porque es un servicio hosted con coste por créditos.
pypi
+2

Código reutilizable
1. Discovery por hashtag con pytok

Este fragmento es literal del README de pytok y muestra el patrón de iteración asíncrona por feed de hashtag, búsqueda y sonidos:

python
# https://github.com/MEOMcGill/pytok
async for video in api.hashtag(name="funny").videos(count=100):
    ...

async for video in api.search("news").videos(count=100):
    ...

Fuente exacta: README de MEOMcGill/pytok.
pypi

Integración: úsalo solo como fallback de tiktok_discovery.py; convierte cada video al contrato TikTokPost y envíalo al ranking; no lo uses para acciones.

2. Cliente de archivo Evil0ctal — adaptación para tu repo

Código de integración propio, basado en el patrón REST/MCP documentado por Evil0ctal; copiable tal cual en tools/tiktok_archive_client.py:

python
# Adaptación propia para davidpd89/ci-sandbox-tmp.
# Patrón y endpoints basados en: https://github.com/Evil0ctal/Douyin_TikTok_Download_API/blob/main/documents/en/12-mcp.md
import os
from typing import Any
import httpx

from tools.http_retry import request_with_retry


class TikTokArchiveClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.getenv("TIKTOK_ARCHIVE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("TIKTOK_ARCHIVE_API_KEY", "")
        if not self.base_url:
            raise ValueError("TIKTOK_ARCHIVE_URL no está configurada")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_post(self, video_id: str) -> dict[str, Any]:
        return request_with_retry(
            "GET",
            f"{self.base_url}/api/tiktok/video/{video_id}",
            headers=self._headers(),
            timeout=30,
        ).json()

    def get_user_posts(self, sec_uid: str, cursor: str = "", count: int = 20) -> dict[str, Any]:
        return request_with_retry(
            "GET",
            f"{self.base_url}/api/tiktok/user/posts",
            headers=self._headers(),
            params={"secUid": sec_uid, "cursor": cursor, "count": count},
            timeout=30,
        ).json()

    def get_comments(self, video_id: str, cursor: str = "", count: int = 20) -> dict[str, Any]:
        return request_with_retry(
            "GET",
            f"{self.base_url}/api/tiktok/video/comments",
            headers=self._headers(),
            params={"video_id": video_id, "cursor": cursor, "count": count},
            timeout=30,
        ).json()

Nota: antes de fusionar, sustituye las rutas por las expuestas por tu instancia concreta de Evil0ctal; su documentación MCP define las herramientas de lectura y los límites de uso.

3. Ranking de candidatos — adaptación para growth_attribution

Código propio, compatible con la idea de snapshots históricos y atribución que ya implementan growth_attribution.py y action_ledger.py:

python
# Adaptación propia para davidpd89/ci-sandbox-tmp.
# Se integra con tools/action_ledger.py y tools/growth_attribution.py.
from dataclasses import dataclass


@dataclass(frozen=True)
class TikTokCandidate:
    video_id: str
    author_id: str
    views: int
    likes: int
    comments: int
    shares: int
    follower_delta: int
    age_hours: float
    spanish_score: float
    booktok_score: float


def rank_tiktok_candidate(c: TikTokCandidate) -> float:
    engagement = (c.likes + 3 * c.comments + 5 * c.shares) / max(c.views, 1)
    freshness = 1 / (1 + c.age_hours / 24)
    growth = min(c.follower_delta / 100, 1.0)
    niche = 0.6 * c.spanish_score + 0.4 * c.booktok_score
    return round(0.40 * engagement + 0.25 * freshness + 0.20 * growth + 0.15 * niche, 6)

Integración: calcula spanish_score con check_language_variety.py y booktok_score con tus términos de discovery_terms.py; registra la acción y su puntuación en action_ledger.py.

4. Cliente de métricas de Ads — adaptación condicional

Código propio para tools/tiktok_ads_metrics.py; solo debe activarse si tienes acceso a TikTok Ads:

python
# Adaptación propia para davidpd89/ci-sandbox-tmp.
# SDK oficial: https://github.com/tiktok/tiktok-business-api-sdk
import os
from tiktokapify import ApiClient  # Sustituir por el cliente exacto del SDK instalado

from tools.action_ledger import record_action


def fetch_campaign_report(advertiser_id: str, report_range: str) -> dict:
    client = ApiClient()
    client.configuration.access_token = os.environ["TIKTOK_ACCESS_TOKEN"]
    response = client.reporting_api.report(
        advertiser_id=advertiser_id,
        report_type="BASIC",
        data_level="AUCTION_CAMPAIGN",
        dimensions=["campaign_id"],
        metrics=["impressions", "clicks", "spend", "conversion"],
        start_date=report_range[0],
        end_date=report_range[1],
    )
    payload = response.to_dict()
    record_action(
        platform="tiktok",
        action="ads_report_fetch",
        target_id=advertiser_id,
        result="ok",
        metadata={"rows": len(payload.get("data", {}).get("list", []))},
    )
    return payload

Nota: el nombre exacto del cliente puede variar según la versión instalada del SDK; verifica la firma en el paquete tiktok-business-api-sdk-official antes de fusionar.

Qué no copiar

No copies núcleos de follow, like, comment o publish de taktik-bot, TikTokAutoUploader o auto-tiktok: tu sistema ya tiene ejecutores móviles, navegador, políticas humanas, colas y auditoría.

No copies dashboards antiguos como TikTok_Analytics o TikTokAnalytics: son de 2021–2023 y no añaden capacidad frente a tus informes diarios y atribución.
pypi
+1

No dependas de MCP hosted de pago como HasData para el núcleo: añade dependencia externa y coste por consulta.
github

No uses el SDK oficial para discovery orgánico: está orientado a Business/Ads, no a explorar contenido de terceros.

Plan de implementación en PR pequeñas
PR 1 — Contrato común de datos

Crear tools/social_post_contract.py con SocialPost, SocialAuthor, SocialComment y MetricSnapshot.

Añadir platform: Literal["tiktok", "instagram", "x", "threads", "facebook", "pinterest", "reddit", "bluesky", "mastodon"].

Validar con validate_contracts.py.

Tests: IDs únicos, fechas ISO, métricas no negativas y normalización de hashtags.

PR 2 — Servicio Evil0ctal

Añadir tools/tiktok_archive_client.py con el código de la sección anterior.

Levantar Evil0ctal en Windows mediante Docker Compose; su proyecto documenta despliegue con Docker y MCP.

Conectar tiktok_discovery.py y tiktok_growth_scan.py como consumidores.

Tests: mock HTTP, reintentos, 401/403/429, paginación e idempotencia.

PR 3 — Watchlist y snapshots

Crear tools/tiktok_watchlist.py con autores, hashtags, posts y frecuencia.

Guardar snapshots diarios por post y autor.

Alimentar tiktok_candidate_rank.py y growth_attribution.py.

Tests: deltas correctos, candidatos duplicados, TTL y candidatos sin métricas previas.

PR 4 — Discovery MCP ligero

Añadir tools/tiktok_mcp_discovery.py para consultas por hashtag usando terrylinhaochen/tiktok_mcp.

Reutilizar su manejo de proxy, rate limit y health check como referencia.
github

Tests: hashtag vacío, límite de resultados, timeout, respuestas sin engagement y deduplicación por video_id.

PR 5 — Producción de clips

Crear tools/clip_pipeline.py que acepte un capítulo, escena o extracto y llame a autoclip o MoneyPrinterTurbo.

Guardar salida en publicaciones TikTok GPT/<fecha>/ y registrar el asset en validate_assets_registry.py.

Tests: vídeo vertical, subtítulos presentes, duración dentro de rango, metadatos y no sobrescritura.

PR 6 — Ads opcional

Añadir tools/tiktok_ads_metrics.py solo si existe TIKTOK_ACCESS_TOKEN.

Cruzar impresiones, clics y conversiones con crecimiento orgánico en growth_attribution.py.

Tests con respuestas simuladas del SDK; sin credenciales, el módulo debe desactivarse limpiamente.

Aplicación a las demás redes

Bluesky y Mastodon: ya tienes escaneo, interacción, colas y auditoría; añade watchlist y snapshots con el mismo contrato SocialPost.

X, Threads, Facebook e Instagram: reutiliza SocialPost y MetricSnapshot; el ranking debe ponderar replies, reposts, guardados o comentarios según la red.

Pinterest y Reddit: la watchlist sirve para pins, boards, subreddits e hilos; el engagement debe usar guardados, clics salientes, upvotes y respuestas.

TikTok, Reels y Shorts: autoclip y MoneyPrinterTurbo producen assets reutilizables; Taisly puede publicarlos mediante un contrato común, pero mantenlo opcional.

Todas las redes: cada acción debe quedar en action_ledger.py con candidato, fuente, puntuación, resultado y ventana temporal para que el ranking aprenda de resultados reales.

Fuentes

Repo espejo revisado: davidpd89/ci-sandbox-tmp, commit 60aa837.

Evil0ctal/Douyin_TikTok_Download_API
.

Documentación MCP de Evil0ctal
.

terrylinhaochen/tiktok_mcp
.
github

tiktok/tiktok-business-api-sdk
.

tiktok-business-api-sdk-official en PyPI
.

TikTok API for Business
.

AdsMCP/tiktok-ads-mcp-server.

davidteather/TikTok-Api.

MEOMcGill/pytok.
pypi

scrapfly/scrapfly-scrapers
.

Guía Scrapfly para TikTok
.

zhouxiaoka/autoclip.

harry0703/MoneyPrinterTurbo.

masterFuf/taktik-bot.

Taisly Agent Kit
.

3441293738/creatorhub.
