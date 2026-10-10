# Homogeneización de adaptadores entre redes

Fuente: informe de Perplexity (https://www.perplexity.ai/search/320c2596-e639-4adc-819e-cafddd83b9f1), generado 10/10/2026.

Arquitectura unificada multi-red para el sistema de crecimiento de David Porto

Resumen ejecutivo: la mejor base no es copiar un monolito completo, sino adoptar un núcleo propio en Python 3.11 con un contrato único de SocialAdapter, capacidades declaradas por red, DTOs normalizados y pruebas de paridad. Para inspiración directa, Postiz es el patrón de referencia más completo (proveedor + interfaz + gestor de integraciones), aunque es TypeScript y AGPL-3.0; Mixpost y social-media-kit ofrecen referencias más ligeras con licencias MIT; AdsLibrary demuestra un patrón muy útil de SourceCapabilities para declarar qué puede hacer cada adaptador.
deepwiki
+4

Resumen

El objetivo debe ser un sistema donde el orquestador nunca conozca detalles de X, Bluesky, Mastodon, Reddit, Threads, Instagram, TikTok, Pinterest o Facebook. Cada red se implementa como un adaptador que declara capacidades, traduce un SocialPost normalizado a su API nativa y devuelve un resultado uniforme: publicado, programado, rechazado, requiere revisión o error recuperable.
deepwiki
+1

Postiz implementa exactamente esta idea: cada red es una clase que implementa SocialProvider, extiende SocialAbstract y expone operaciones comunes como autenticación, publicación, refresco de token y límites/ajustes propios; un IntegrationManager registra los proveedores y permite añadir una red implementando la interfaz sin rewiring del núcleo.
deepwiki
+2

Para vuestro caso —comentarios humanos, descubrimiento de posts/perfiles, ranking y aprendizaje— el contrato debe cubrir más que publicación: búsqueda, lectura de posts, perfiles, comentarios, interacción y métricas. La clave es separar capacidad disponible de acción ejecutada: no todas las redes permiten lo mismo, pero todas deben responder con el mismo modelo de resultado.

Hallazgos
Repositorio / patrón	Licencia	Qué reutilizar	Aplicación al sistema	Riesgos

gitroomhq/postiz-app
	AGPL-3.0 
github
+1
	Patrón SocialProvider + SocialAbstract + IntegrationManager; errores tipados (refresh-token, bad-body, retry); adaptación de contenido y media por red. 
deepwiki
+1
	Copiar el diseño, no el código: BaseSocialAdapter, registro por identificador, errores clasificados y flujo de refresh/retry.	AGPL: no reutilizar código directamente en un servicio privado sin asumir obligaciones de copyleft; mejor inspiración arquitectónica. 
codeline
+1


inovector/mixpost
	MIT 
github
+1
	Modelo de producto: calendario, publicación multiplataforma, adaptación por canal, analítica; soporta Facebook, Instagram, X, TikTok, Pinterest, Threads, Bluesky y Mastodon. 
repocloud
+1
	Referencia para dominio de contenido: variantes por red, estados de publicación, calendario/cola y métricas.	Es PHP/Laravel; útil como diseño y modelo de datos, no como dependencia Python. 
github


terrytangyuan/social-media-kit
	MIT 
github
	Publicación multiplataforma a LinkedIn, X, Mastodon y Bluesky con OAuth y formateo cruzado. 
github
	Buen ejemplo pequeño de flujo “un contenido -> varias redes”, útil para validar vuestro pipeline de publicación.	Cobertura limitada: no incluye Reddit, Threads, Instagram, TikTok, Pinterest ni Facebook. 
github

soxoj/AdsLibrary	Verificar licencia en el repo antes de reutilizar código	Patrón AdSource + SourceCapabilities: cada fuente declara búsquedas, métricas, contactos y autenticación; los adaptadores mapean payloads a un modelo común. 
github.laiyagushi
	Modelo excelente para PlatformCapabilities: can_comment, can_search_posts, can_follow, max_text_length, media, rate_limit, auth.	Enfocado en ad libraries, no en interacción social general. 
github.laiyagushi

MarshalX/atproto	Verificar en el repo	SDK Python para Bluesky/AT Protocol. 
github
	Adaptador Bluesky nativo en Python; base para búsqueda, perfiles, posts y comentarios.	Debe encapsularse tras vuestro contrato, nunca filtrarse al orquestador. 
github


lundberg/respx
	Verificar en el repo	Mock de HTTPX con rutas, respuestas, errores, timeouts e historial de llamadas; compatible con pytest. 
github
+2
	Base ideal para pruebas offline de adaptadores: paridad de contrato, rate limits, refresh, errores HTTP y payloads anómalos.	Los mocks no detectan cambios reales de API; añadir suite reducida de contrato contra sandbox cuando exista. 
universopython


DimensionDev/Flare
	AGPL-3.0 
github
	Cliente unificado de Mastodon, Bluesky, X y otras fuentes: timeline común, cross-post y normalización de identidades. 
github
	Referencia de producto para unificación de lectura, perfiles y cross-posting.	Kotlin Multiplatform y AGPL; no es base práctica para un backend Python propio. 
github


Masterjx9/socialmediascheduler
	MIT 
github
	Integraciones de Instagram, X, Facebook, Threads, TikTok y YouTube con programación. 
github
	Ejemplo de cobertura de redes comerciales y de estados como “deshabilitado/sandbox”.	Repositorio pequeño; revisar mantenimiento, calidad y tests antes de tomar patrones concretos. 
github
Contrato recomendado

Usad Protocol + dataclasses congeladas en Python. Esto da tipado, testabilidad y sustitución fácil de adaptadores sin herencia rígida.

python
from typing import Protocol, Literal
from dataclasses import dataclass, field
from datetime import datetime

Network = Literal[
    "x", "bluesky", "mastodon", "reddit",
    "threads", "instagram", "tiktok",
    "pinterest", "facebook"
]

@dataclass(frozen=True)
class PlatformCapabilities:
    network: Network
    can_publish: bool
    can_comment: bool
    can_search_posts: bool
    can_search_profiles: bool
    can_follow: bool
    can_read_comments: bool
    can_read_metrics: bool
    supports_threads: bool
    supports_media: bool
    max_text_length: int
    requires_approval: bool = False

@dataclass(frozen=True)
class SocialPost:
    network: Network
    external_id: str
    author_handle: str
    text: str
    url: str | None
    created_at: datetime
    language: str | None = None
    media_urls: tuple[str, ...] = ()
    engagement: dict[str, int] = field(default_factory=dict)

@dataclass(frozen=True)
class ActionResult:
    ok: bool
    status: Literal[
        "published", "queued", "skipped",
        "needs_review", "rejected", "failed"
    ]
    external_id: str | None = None
    reason: str | None = None
    retryable: bool = False
    rate_limited: bool = False

class SocialAdapter(Protocol):
    network: Network
    capabilities: PlatformCapabilities

    async def publish(self, draft: "PostDraft") -> ActionResult: ...
    async def search_posts(self, query: "SearchQuery") -> list[SocialPost]: ...
    async def search_profiles(self, query: "ProfileQuery") -> list["SocialProfile"]: ...
    async def read_comments(self, post: SocialPost) -> list["SocialComment"]: ...
    async def comment(self, post: SocialPost, text: str) -> ActionResult: ...
    async def healthcheck(self) -> ActionResult: ...

Este contrato evita el error habitual de preguntar “¿puedo comentar en Pinterest?” en tiempo de ejecución: el planificador consulta capabilities antes de seleccionar la acción. El patrón de SourceCapabilities de AdsLibrary es una validación externa de este enfoque.
github.laiyagushi

Matriz de capacidades inicial
Red	Publicar	Comentar	Buscar posts	Buscar perfiles	Seguir	Métricas	Prioridad
X	Sí	Sí	Sí	Sí	Sí	Sí	Alta
Bluesky	Sí	Sí	Sí	Sí	Sí	Parcial	Alta
Mastodon	Sí	Sí	Sí	Sí	Sí	Parcial	Alta
Reddit	Sí	Sí	Sí	Sí	Limitado	Parcial	Alta
Threads	Sí	Sí	Limitado	Limitado	Limitado	Parcial	Media
Instagram	Sí	Sí	Limitado	Sí	Limitado	Sí	Media
TikTok	Sí	Sí	Limitado	Sí	Limitado	Parcial	Media
Pinterest	Sí	Limitado	Sí	Sí	Limitado	Parcial	Media
Facebook	Sí	Sí	Limitado	Sí	Limitado	Sí	Media

La matriz debe vivir en código, no en documentación estática: cada adaptador devuelve sus PlatformCapabilities, y los tests verifican que el registro global coincide con lo que cada adaptador declara. Postiz sigue un principio equivalente: cada proveedor declara identificadores, scopes, editor, refresco y comportamiento específico dentro de una interfaz común.
codeline

Recomendación

Recomiendo construir un paquete interno rrss_core, con estas capas:

Dominio común: SocialPost, SocialProfile, SocialComment, PostDraft, ActionResult, SearchQuery.

Contrato: SocialAdapter como Protocol y PlatformCapabilities como dataclass congelada.

Adaptadores: un módulo por red, con cliente HTTP aislado, mapper de payloads y errores tipados.

Registro: AdapterRegistry que impida dos adaptadores con el mismo network y exponga capacidades.

Orquestador: selecciona redes por capacidad, presupuesto, prioridad, estado de credenciales y resultado histórico.

Ranking: puntúa candidatos por relevancia de nicho, frescura, engagement, facilidad de acción, riesgo de repetición y rendimiento previo.

Observabilidad: cada acción guarda red, plantilla/variante, candidato, resultado, latencia, error y métricas posteriores.

No conviene adoptar Postiz como dependencia: es una plataforma completa en TypeScript/NestJS y su licencia AGPL-3.0 exige precaución si se modifica o distribuye como servicio de red. En cambio, su arquitectura de proveedores es la más cercana a lo que necesitáis y puede traducirse limpiamente a Python.
deepwiki
+4

Plan de implementación en PR pequeñas
PR 1 — Contrato y dominio

Crear rrss_core/domain.py, rrss_core/contracts.py y rrss_core/errors.py.

Definir DTOs inmutables, SocialAdapter, PlatformCapabilities y errores: AuthError, RateLimitError, ValidationError, TransientError, PermanentError.

Tests: creación de DTOs, serialización, validación de Network y capacidades coherentes.

PR 2 — Registro de adaptadores

Crear AdapterRegistry con register(), get(), all(), by_capability().

Impedir duplicados y adaptadores sin capacidades.

Tests: registro, duplicados, filtrado por can_comment, can_search_posts, etc.

PR 3 — Harness de pruebas de paridad

Crear tests/adapters/conftest.py con casos genéricos para todo adaptador.

Usar respx para HTTPX y pytest-asyncio para adaptadores async. RESPX permite definir rutas, respuestas, errores, timeouts e inspeccionar llamadas.
github
+2

Casos mínimos por red:

Publicación válida devuelve published y external_id.

Texto demasiado largo devuelve rejected antes de llamar a la API.

401 devuelve AuthError / needs_review.

429 devuelve rate_limited=True y retryable=True.

500 o timeout devuelve failed, retryable=True.

Payload inesperado no rompe el orquestador.

healthcheck() valida credenciales y permisos declarados.

PR 4 — Adaptadores de lectura: Bluesky y Mastodon

Implementar primero búsqueda de posts, perfiles y comentarios.

Integrar SDK AT Protocol para Bluesky.
github

Normalizar URI, autor, texto, fecha, media, engagement e idioma.

Tests de paridad con fixtures HTTP grabados o simulados.

PR 5 — Adaptadores de lectura: Reddit y X

Reddit: búsqueda por subreddits, posts, comentarios y perfiles.

X: búsqueda, perfiles, posts y métricas disponibles.

Añadir reglas de nicho: fantasía, romantasy, YA, autores, lectores, editoriales y comunidades de lectura.

Tests: paginación, vacío, rate limit, respuestas parciales y deduplicación.

PR 6 — Adaptadores de acción: Bluesky, Mastodon y Reddit

Implementar comment() y, si procede, follow().

Exigir plantillas con variantes y límite diario por red.

Guardar cada acción con hash de contexto para evitar comentarios repetidos.

Tests: selección de variante, longitud, deduplicación, fallo y reintento.

PR 7 — Adaptadores Meta: Threads, Instagram y Facebook

Implementar publicación y comentarios donde la API lo permita.

Centralizar OAuth, refresco de token y estados de aprobación.

Marcar capacidades no disponibles en vez de simularlas.

Tests de token expirado, permisos insuficientes, media inválida y publicación diferida.

PR 8 — Adaptadores TikTok, Pinterest y X de publicación

Implementar publicación con validación previa de formato, media, longitud y campos obligatorios.

Pinterest: priorizar pins, tableros, enlaces y descripciones.

TikTok: separar vídeo, caption, hashtags y estado de revisión.

X: hilos, media y límites de caracteres.

Tests: cada red debe pasar el mismo harness, con fixtures propios.

PR 9 — Ranking y aprendizaje

Crear ActionCandidate con expected_value, confidence, novelty, audience_fit, cost, risk y historical_performance.

Ranking inicial determinista y explicable; después, modelo aprendido con resultados reales.

Tests: sin datos históricos, ranking no debe depender de una red concreta; con datos, debe priorizar acciones con mejor resultado observado.

PR 10 — Observabilidad y tablero

Registrar cada intento: red, acción, candidato, plantilla, resultado, motivo, latencia y coste.

Crear métricas por red: tasa de publicación, tasa de comentarios aceptados, errores de auth, rate limits, engagement posterior y degradación de resultados.

Tests: eventos obligatorios, IDs únicos y agregaciones correctas.

Pruebas de paridad

La paridad no significa que todas las redes hagan lo mismo; significa que todas respondan al mismo contrato.

text
tests/
  adapters/
    base/
      test_publish_contract.py
      test_comment_contract.py
      test_search_contract.py
      test_error_contract.py
      test_capabilities_contract.py
    bluesky/
      fixtures/
      test_adapter.py
    mastodon/
      fixtures/
      test_adapter.py
    reddit/
      fixtures/
      test_adapter.py

Cada adaptador debe pasar:

Test de capacidades: lo declarado coincide con las operaciones implementadas.

Test de normalización: distintos payloads producen el mismo SocialPost lógico.

Test de errores: auth, validación, rate limit, fallo transitorio y fallo permanente.

Test de idempotencia: repetir una acción no duplica publicaciones ni comentarios cuando el sistema lo permita.

Test de no-filtración: el orquestador no importa SDKs de red; sólo conoce SocialAdapter.

Test de contrato real reducido: para redes con sandbox o credenciales de prueba, un conjunto pequeño y controlado detecta cambios externos; los mocks cubren el resto. RESPX documenta explícitamente que sus pruebas verifican el contrato simulado, no cambios del proveedor real.
universopython

Aplicación transversal

X, Bluesky y Mastodon: núcleo inicial de descubrimiento y comentarios; buen terreno para medir variantes de tono, longitud y hashtags.

Reddit: el adaptador debe priorizar contexto de subreddit, reglas visibles y calidad conversacional antes que frecuencia.

Threads, Instagram y Facebook: agruparlos como familia Meta en OAuth, tokens y errores, pero mantener adaptadores separados porque sus objetos, formatos y métricas difieren.

TikTok y Pinterest: más orientados a contenido visual; el PostDraft necesita media_plan, cover, alt_text, link y board/sound según red.

Todas: el mismo ActionCandidate debe poder convertirse en comentario, respuesta, pin, reel, post o hilo sin cambiar el orquestador.

Fuentes

Postiz — repositorio y licencia AGPL-3.0: 
https://github.com/gitroomhq/postiz-app
github
+1

Postiz — arquitectura de proveedores e interfaz SocialProvider: 
https://deepwiki.com/gitroomhq/postiz-app/4-social-media-platform-integrations
deepwiki

Análisis técnico de Postiz, interfaz, SocialAbstract, errores y IntegrationManager: 
https://www.codeline.co/thoughts/repo-review/2025/postiz-open-source-social-media-scheduler
codeline

Mixpost — repositorio MIT: 
https://github.com/inovector/mixpost
github
+1

Mixpost — cobertura de redes y producto: 
https://repocloud.io/details/Mixpost/
repocloud

social-media-kit — MIT y multiplataforma: 
https://github.com/terrytangyuan/social-media-kit
github

AdsLibrary — patrón AdSource y SourceCapabilities: https://github.com/soxoj/AdsLibrary
github.laiyagushi

RESPX — mock HTTPX para pruebas: 
https://github.com/lundberg/respx
github
+1

RESPX — guía de pruebas, errores y límites del mocking: 
https://lundberg.github.io/respx/guide/
lundberg
+1

AT Protocol SDK Python para Bluesky: https://github.com/MarshalX/atproto
github

Flare — cliente unificado multiplataforma, AGPL-3.0: 
https://github.com/DimensionDev/Flare
github

socialmediascheduler — MIT, integraciones múltiples: 
https://github.com/Masterjx9/socialmediascheduler
github
