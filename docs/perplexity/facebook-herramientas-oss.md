# Herramientas y código abierto en Facebook (páginas y grupos)

Fuente: informe de Perplexity (https://www.perplexity.ai/search/d1800ad7-50d0-47d9-9ae5-ce267a6efcdc), generado 10/10/2026.

Informe mejorado: repos, SDK y agentes para Facebook con Python en Windows
Resumen

He revisado el informe anterior y he eliminado o degradado lo que no aporta a davidpd89/ci-sandbox-tmp: repos archivados, scrapers sin mantenimiento real y automatización de grupos basada en Selenium. La base recomendada sigue siendo el SDK oficial 
facebook/facebook-python-business-sdk
, complementado por dos repos públicos activos y con licencia clara: SSujitX/facebook-pages-scraper y sns-sdks/python-facebook.

No incluyo bloques presentados como “copiables tal cual” de archivos cuyo contenido no he podido verificar íntegramente en esta pasada: sería fabricar código. En su lugar, dejo las URL exactas de los archivos fuente, su estado, la parte exacta que conviene copiar y un esqueleto de integración propio para el adaptador Facebook.

Correcciones al informe anterior
Elemento anterior	Decisión	Motivo
kevinzg/facebook-scraper	Eliminado como dependencia	Proyecto muy citado, pero el panorama de 2026 lo describe como parcialmente roto o desactualizado; no es base fiable para producción. 
thunderbit

Mahdi-hasan-shuvo/facebook-automation-python	Degradado a referencia conceptual	Aunque aparece activo en topics de GitHub, su enfoque de automatización de grupos, invitaciones y scraping no encaja con un sistema homogéneo, medible y basado en adaptadores.
devForTheFuture/Facebook-Auto-Pilot	Eliminado	Publicación masiva en Pages y grupos; no resuelve descubrimiento, evidencia, ranking ni aprendizaje.
LorenzoMonti/facebook_page_group_comments	Eliminado	Última actualización en 2020; solo tenía valor histórico.
passivebot/facebook-marketplace-scraper	Eliminado	Está archivado y su dominio es Marketplace, no crecimiento editorial en Pages/grupos.
mobolic/facebook-sdk	Degradado	Tiene 2.798 estrellas y licencia Apache-2.0, pero su último push fue en agosto de 2024; es útil como referencia, no como base principal.
facebook-python-business-sdk	Confirmado como base	SDK oficial, con actualización automática mostrada en septiembre de 2026 y release 26.0.1 en agosto de 2026. 
github
Hallazgos verificados
Repositorio	Actividad verificada	Licencia	Qué resolver	Qué copiar	URL clave

facebook/facebook-python-business-sdk
	Commit automático mostrado en septiembre de 2026; release 26.0.1, agosto de 2026. 
github
	Licencia del propio Meta	Cliente oficial de Graph/Marketing API	Objetos de Pages, autenticación, paginación y versionado de API	
Repo

SSujitX/facebook-pages-scraper	Push el 29 de septiembre de 2026; 63 estrellas; MIT; no archivado.	MIT	Descubrimiento y observación de Pages sin webdriver	page_post_info.py, page_info.py, request_handler.py y normalización JSON	facebook_page_scraper/
sns-sdks/python-facebook	Push el 10 de febrero de 2026; 380 estrellas; no archivado.	MIT	Wrapper Graph API ligero, con soporte Facebook e Instagram	client.py, recursos de Facebook y patrones de paginación	pyfacebook/api/facebook/client.py
wael-sudo2/facebook-page-info-scraper	Push el 29 de agosto de 2026; 68 estrellas; MIT.	MIT	Metadatos y enriquecimiento de Pages	Solo el modelo de campos y exportación; no su capa de scraping como dependencia	Repo
HackUnderway/meta_scan	Push el 20 de agosto de 2026; 52 estrellas; MIT.	MIT	OSINT y consulta de Pages mediante API externa	Estructura CLI y normalización de resultados; no la dependencia de RapidAPI	Repo
shaikhsajid1111/facebook_page_scraper	Último push en julio de 2024; 282 estrellas; MIT.	MIT	Esquema de posts y exportación CSV/JSON	Solo esquema de datos y tests de normalización	Repo
minimaxir/facebook-ad-library-scraper	Último push en 2019; 144 estrellas; MIT.	MIT	Vigilancia competitiva mediante Ad Library API	Patrón de consulta a Ad Library, no mantenimiento del repo	Repo

SSujitX/facebook-pages-scraper es el hallazgo menos obvio más útil: está activo, usa Python, tiene tests, pyproject.toml, licencia MIT y módulos separados para información de Page, posts y peticiones. Su último push es del 29 de septiembre de 2026. sns-sdks/python-facebook sigue siendo útil como cliente Graph ligero, con push en febrero de 2026.

Piezas de código a reutilizar
1. Cliente oficial Meta

Archivo fuente:

https://github.com/facebook/facebook-python-business-sdk

Qué copiar: la forma de instanciar el cliente y los objetos de Page; no copiar configuraciones de anuncios que no usemos.

python
# tools/facebook/meta_client.py
# Integración propia para ci-sandbox-tmp; usa facebook-python-business-sdk.
# Fuente oficial: https://github.com/facebook/facebook-python-business-sdk

import os
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.page import Page

class MetaClient:
    def __init__(
        self,
        access_token: str | None = None,
        page_id: str | None = None,
        api_version: str | None = None,
    ):
        self.access_token = access_token or os.environ["FACEBOOK_ACCESS_TOKEN"]
        self.page_id = page_id or os.environ["FACEBOOK_PAGE_ID"]
        self.api_version = api_version or os.environ.get("FACEBOOK_GRAPH_API_VERSION", "v26.0")

        FacebookAdsApi.init(
            access_token=self.access_token,
            api_version=self.api_version,
        )

    def page(self) -> Page:
        return Page(self.page_id)

    def get_page_fields(self, fields: list[str]) -> dict:
        return self.page().api_get(fields=fields).export_all_data()

    def get_posts(self, fields: list[str], limit: int = 25) -> list[dict]:
        posts = self.page().get_posts(fields=fields, limit=limit)
        return [post.export_all_data() for post in posts]

Tests mínimos:

python
# tests/facebook/test_meta_client.py
from tools.facebook.meta_client import MetaClient

def test_client_requires_token(monkeypatch):
    monkeypatch.delenv("FACEBOOK_ACCESS_TOKEN", raising=False)
    try:
        MetaClient()
        assert False
    except KeyError:
        assert True
2. Normalización de posts de Page

Archivo fuente recomendado como referencia:
https://github.com/SSujitX/facebook-pages-scraper/blob/master/facebook_page_scraper/page_post_info.py

Qué copiar: la separación entre petición, extracción y normalización; no copiar el scraper como dependencia de producción.

python
# tools/facebook/normalize.py
# Normaliza posts de Facebook al formato común del sistema.
# Referencia de campos: https://github.com/SSujitX/facebook-pages-scraper/blob/master/facebook_page_scraper/page_post_info.py

from datetime import datetime, timezone

def normalize_post(raw: dict) -> dict:
    return {
        "network": "facebook",
        "destination_type": "page_post",
        "external_id": raw.get("id"),
        "page_id": raw.get("page_id"),
        "created_at": raw.get("created_time"),
        "text": raw.get("message") or "",
        "permalink": raw.get("permalink_url"),
        "shares": (raw.get("shares") or {}).get("count", 0),
        "comments": (raw.get("comments") or {}).get("summary", {}).get("total_count", 0),
        "reactions": (raw.get("reactions") or {}).get("summary", {}).get("total_count", 0),
        "raw": raw,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }

def is_actionable(post: dict, max_age_days: int = 7) -> bool:
    if not post.get("external_id") or not post.get("text"):
        return False
    created = post.get("created_at")
    if not created:
        return False
    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - created_dt).days
    return age_days <= max_age_days
3. Descubrimiento de Pages del nicho

Archivo fuente de referencia:
https://github.com/SSujitX/facebook-pages-scraper/blob/master/facebook_page_scraper/page_info.py

Qué copiar: la idea de obtener metadatos estructurados de una Page antes de decidir si es un destino válido.

python
# tools/facebook/niche_discovery.py
# Descubrimiento de Pages candidatas para el nicho de fantasía/romantasy en español.

from dataclasses import dataclass

@dataclass
class PageCandidate:
    page_id: str
    name: str
    url: str
    category: str | None
    followers: int | None
    relevance: float

KEYWORDS = [
    "fantasía juvenil",
    "romantasy",
    "novela fantástica",
    "autores independientes",
    "lectura fantástica",
    "booktok español",
]

def score_page(page: dict) -> float:
    score = 0.0
    text = " ".join(
        str(page.get(field, "")).lower()
        for field in ("name", "category", "about", "description")
    )
    score += sum(2.0 for keyword in KEYWORDS if keyword in text)
    followers = page.get("followers_count") or 0
    score += min(followers / 10000, 5.0)
    return round(score, 3)

def to_candidate(page: dict) -> PageCandidate:
    return PageCandidate(
        page_id=page["id"],
        name=page.get("name", ""),
        url=page.get("link", ""),
        category=page.get("category"),
        followers=page.get("followers_count"),
        relevance=score_page(page),
    )
4. Ranking de acciones reutilizable

No duplicar el ranking existente del repo. Este módulo solo añade rasgos específicos de Facebook y debe alimentar el ranking global.

python
# tools/facebook/action_ranking.py
# Ranking específico de Facebook; se integra con el ranking global existente.

def facebook_features(candidate: dict, post: dict) -> dict:
    return {
        "destination_type": candidate.get("destination_type", "page_post"),
        "post_age_days": candidate.get("post_age_days", 999),
        "engagement": (
            post.get("reactions", 0)
            + post.get("comments", 0)
            + post.get("shares", 0)
        ),
        "has_question": "?" in post.get("text", ""),
        "is_spanish": any(
            word in post.get("text", "").lower()
            for word in ("libro", "lectura", "fantasía", "autor", "novela")
        ),
    }

def rank_facebook_actions(items: list[dict]) -> list[dict]:
    def score(item: dict) -> float:
        features = facebook_features(item["candidate"], item["post"])
        base = features["engagement"] / 100
        recency = max(0, 7 - features["post_age_days"]) / 7
        relevance = 2.0 if features["is_spanish"] else 0.0
        question_bonus = 1.5 if features["has_question"] else 0.0
        return base + recency + relevance + question_bonus

    return sorted(items, key=score, reverse=True)
Integración con ci-sandbox-tmp

El repo ya contiene tools/, tests/, requirements-ci.txt y carpetas por red, incluida publicaciones Facebook GPT. También existen ramas previas de Facebook para comentarios humanos, hashtags/fuentes, ranking de acciones y tests estándar, además de ramas transversales de colas, idempotencia, atribución y agentes.

Por tanto, la integración correcta es:

tools/facebook/meta_client.py: único acceso a Graph API.

tools/facebook/normalize.py: conversión al registro común multired.

tools/facebook/page_posts_ingest.py: ingesta de posts de Page.

tools/facebook/comments_ingest.py: ingesta de comentarios.

tools/facebook/niche_discovery.py: candidatos de Pages y grupos.

tools/facebook/action_ranking.py: rasgos Facebook para el ranking global.

tools/facebook/metrics_export.py: exportación de resultados y atribución.

Plan de PR pequeñas

PR 1 — Cliente Meta oficial: añadir facebook-business, tools/facebook/meta_client.py y tests de token, versión y errores.

PR 2 — Normalización: añadir normalize.py, esquema común y tests de deduplicación.

PR 3 — Ingesta de Page posts: page_posts_ingest.py, exportación JSONL/CSV y tests de campos opcionales.

PR 4 — Ingesta de comentarios: comments_ingest.py, deduplicación por comment_id y tests de hilos.

PR 5 — Descubrimiento: niche_discovery.py, scoring reproducible y tests de keywords en español.

PR 6 — Ranking: action_ranking.py, integración con ranking global y tests de estabilidad.

PR 7 — Métricas: metrics_export.py, lineage de evidencia y tests de idempotencia.

Aplicación multired

El mismo patrón se aplica a las demás redes:

X, Threads, Bluesky, Mastodon, Reddit: candidato → evidencia → intención → acción → resultado.

Instagram y TikTok: añadir media_type, duration, visual_score y señales de comentarios.

Pinterest: añadir pin_id, board_id, keywords y guardados.

Facebook: mantener destination_type=page|group|page_post|comment, porque es la red con mayor heterogeneidad de destinos.

Fuentes

SDK oficial Meta Python
github

Meta Graph API v26

SSujitX/facebook-pages-scraper

sns-sdks/python-facebook

wael-sudo2/facebook-page-info-scraper

HackUnderway/meta_scan

shaikhsajid1111/facebook_page_scraper

minimaxir/facebook-ad-library-scraper

Estado de scrapers de Facebook en 2026
thunderbit

GitHub topic facebook-automation Python
