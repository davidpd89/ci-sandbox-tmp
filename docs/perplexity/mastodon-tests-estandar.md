# Tests y estandarización en Mastodon

Fuente: informe de Perplexity (https://www.perplexity.ai/search/3c626b0a-5933-4b03-a36a-eac65999b710), generado 10/10/2026.

Informe mejorado: pruebas, contratos y fixtures para el adaptador de Mastodon
Resumen

El informe anterior era correcto en sus ejes, pero contenía dos imprecisiones que conviene eliminar: min_id no es equivalente a since_id y no debe presentarse como un cursor genérico intercambiable; además, mastodon_mock es muy reciente y tiene cero estrellas, por lo que es útil como referencia de diseño, pero no como dependencia crítica del sistema. El repo davidpd89/ci-sandbox-tmp ya cubre una parte importante de errores, presupuestos, pools, deduplicación y recuperación; la mejora debe centrarse en un contrato multi-red, fixtures canónicos y pruebas de identidad federada, fechas, paginación e idempotencia.
github

Hallazgos verificados
Necesidad	Repositorio o fuente	Estado comprobado	Qué reutilizar	Aplicación al sistema
Mock Mastodon con estado	matthewdeanmartin/mastodon_mock	Activo: último push el 1 de octubre de 2026; MIT; 0 estrellas. 
github
	Diseño de servidor falso con configuración, semillas, moderación, rate limit y utilidades de test.	Referencia para FakeMastodonServer; no incorporarlo como dependencia obligatoria todavía.
Mock HTTP de requests	getsentry/responses	Activo: último push el 6 de octubre de 2026; Apache-2.0; 4.343 estrellas. 
swirls
	Decorador @responses.activate, matchers de query string y respuestas HTTP controladas.	Tests unitarios de adaptador sin red, especialmente errores 429/401/404/422/5xx.
Integración pytest de responses	getsentry/pytest-responses	Activo: último push el 29 de junio de 2026; Apache-2.0; 95 estrellas. 
swirls
	Fixture responses para tests pytest.	Alternativa más idiomática que el decorador cuando el repo ya usa pytest.
Grabación y replay HTTP	kevin1024/vcrpy	Activo: último push el 15 de septiembre de 2026; MIT; 3.019 estrellas.	Cassettes para reproducir interacciones HTTP.	Solo para un conjunto pequeño de pruebas de integración anonimizadas; no para toda la suite.
Tiempo congelado	spulec/freezegun	Activo; freeze_time sigue siendo la API pública. 
qaskills
	Congelar reloj para TTL, antigüedad de posts, scheduled_at y reintentos.	Tests deterministas de envejecimiento, expiración de boosts y presupuestos temporales.
Cliente Mastodon Python	
halcy/Mastodon.py
	Referencia estable del ecosistema.	Contratos de entidades y paginación; no copiar el cliente completo.	Validadores y normalizadores de Status, Account y errores.
API oficial	
Documentación de Mastodon
	Fuente primaria vigente.	Formato de IDs, fechas, visibilidad, scheduled_at y errores.	Fixtures y contratos de adaptador.

Descartes respecto al informe anterior:

pubkitorg/pubkit: no lo recomiendo. Su último push es de agosto de 2023 y tiene 43 estrellas; sirve para diseñar objetos ActivityPub, no para probar un adaptador REST de Mastodon de forma robusta.
github

python-libfaketime: no lo incorporaría. Es una alternativa rápida a freezegun, pero su licencia GPL-2.0 y su dependencia nativa añaden fricción innecesaria frente a freezegun.

sleepfake: útil solo si el sistema usa mucho asyncio.sleep; no es una pieza central para el adaptador Mastodon.

Mastodon.py como dependencia directa: no lo propongo como sustituto del transporte actual. Copiaríamos únicamente criterios de normalización y tests; introducir otro cliente podría chocar con el transporte, la gestión de errores y el circuit breaker ya existentes.
github

Contrato homogéneo

El adaptador Mastodon debe devolver objetos normalizados, no respuestas crudas de la API. Así, discovery, ranking, colas, ledger y aprendizaje pueden funcionar igual para X, Bluesky, Threads, Reddit, Facebook, Pinterest, TikTok e Instagram.

python
# tests/contracts/network_adapter.py
from typing import Literal, Protocol
from dataclasses import dataclass
from datetime import datetime


Network = Literal[
    "x", "threads", "facebook", "pinterest",
    "reddit", "bluesky", "mastodon", "tiktok", "instagram",
]


@dataclass(frozen=True)
class PostRef:
    network: Network
    external_id: str
    instance: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class SocialAuthor:
    network: Network
    external_id: str
    handle: str
    display_name: str | None = None
    instance: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class SocialPost:
    network: Network
    external_id: str
    author: SocialAuthor
    text: str
    url: str
    created_at: datetime
    visibility: Literal["public", "unlisted", "private", "direct"]
    language: str | None = None
    in_reply_to_external_id: str | None = None
    reblog_of_external_id: str | None = None
    sensitive: bool = False
    raw: dict | None = None


class NetworkAdapter(Protocol):
    network: Network

    def discover(self, query: str, cursor: str | None = None) -> tuple[list[SocialPost], str | None]:
        ...

    def read_thread(self, post_ref: PostRef) -> list[SocialPost]:
        ...

Este contrato evita que Mastodon filtre id, created_at o acct directamente hacia el resto del sistema. La API oficial devuelve id como cadena y created_at en ISO-8601 UTC; ambos deben normalizarse en la frontera del adaptador.

Fixtures canónicos

Crear tests/fixtures/mastodon/ con JSON pequeños, deterministas y sin datos personales. Cada fixture representa un caso límite concreto y permite probar el adaptador sin depender de una instancia real.

json
// tests/fixtures/mastodon/status_public_minimal.json
{
  "id": "109900000000000001",
  "created_at": "2026-10-10T12:00:00.000Z",
  "in_reply_to_id": null,
  "in_reply_to_account_id": null,
  "sensitive": false,
  "spoiler_text": "",
  "visibility": "public",
  "language": "es",
  "uri": "https://mastodon.social/users/davidporto/statuses/109900000000000001",
  "url": "https://mastodon.social/@davidporto/109900000000000001",
  "replies_count": 0,
  "reblogs_count": 0,
  "favourites_count": 0,
  "content": "<p>Una escena de fantasía con una promesa imposible.</p>",
  "account": {
    "id": "100000000000000001",
    "username": "davidporto",
    "acct": "davidporto",
    "display_name": "David Porto",
    "url": "https://mastodon.social/@davidporto",
    "created_at": "2026-01-01T00:00:00.000Z"
  }
}
json
// tests/fixtures/mastodon/status_remote_author.json
{
  "id": "109900000000000002",
  "created_at": "2026-10-10T12:05:00.000Z",
  "visibility": "public",
  "url": "https://fosstodon.org/@autor/109900000000000002",
  "content": "<p>Recomendaciones de fantasía épica para este otoño.</p>",
  "account": {
    "id": "200000000000000002",
    "username": "autor",
    "acct": "autor@fosstodon.org",
    "display_name": "Autor remoto",
    "url": "https://fosstodon.org/@autor",
    "created_at": "2026-01-01T00:00:00.000Z"
  }
}
json
// tests/fixtures/mastodon/status_boost.json
{
  "id": "109900000000000003",
  "created_at": "2026-10-10T12:10:00.000Z",
  "visibility": "public",
  "reblog": {
    "id": "109900000000000002",
    "created_at": "2026-10-10T12:05:00.000Z",
    "visibility": "public",
    "url": "https://fosstodon.org/@autor/109900000000000002",
    "content": "<p>Recomendaciones de fantasía épica para este otoño.</p>",
    "account": {
      "id": "200000000000000002",
      "username": "autor",
      "acct": "autor@fosstodon.org",
      "url": "https://fosstodon.org/@autor"
    }
  },
  "account": {
    "id": "100000000000000001",
    "username": "davidporto",
    "acct": "davidporto",
    "url": "https://mastodon.social/@davidporto"
  }
}
Código reutilizable tal cual
Mock Mastodon: utilidad de test

mastodon_mock expone una utilidad de testing con servidor y semillas; es la pieza más interesante para inspirar un FakeMastodonServer propio. El proyecto está activo y publicado bajo MIT.
github

python
# https://github.com/matthewdeanmartin/mastodon_mock/blob/main/mastodon_mock/testing/sugar.py
from mastodon_mock.config import MastodonMockConfig, SeedConfig
from mastodon_mock.testing.server import MockServer

No copiaría el archivo completo: su valor está en el patrón de un servidor de pruebas con configuración y semillas, no en acoplar nuestro repo a una dependencia joven y sin comunidad.
github

Mock HTTP con responses

responses permite declarar respuestas HTTP y verificar peticiones sin red. Su uso con pytest está documentado mediante el decorador @responses.activate; el repositorio mantiene ejemplos en sus propios tests.
swirls

python
# https://github.com/getsentry/responses/blob/master/responses/tests/test_matchers.py
def test_query_string_matcher():
    @responses.activate
    def run():

Para nuestro adaptador, la versión útil es un test propio que use esa misma API:

python
# tests/test_mastodon_adapter_http.py
# Patrón de uso tomado de:
# https://github.com/getsentry/responses/blob/master/responses/tests/test_matchers.py
import json
from pathlib import Path

import pytest
import responses

from growth.adapters.mastodon import MastodonAdapter


FIXTURES = Path(__file__).parents[1] / "fixtures" / "mastodon"


@pytest.fixture
def adapter():
    return MastodonAdapter(instance="mastodon.social")


@responses.activate
def test_discovery_handles_rate_limit(adapter):
    responses.get(
        "https://mastodon.social/api/v1/timelines/tag/fantasy",
        json={"error": "Too many requests"},
        status=429,
        headers={"Retry-After": "30"},
    )

    result = adapter.discover("#fantasy")

    assert result.error.kind == "rate_limit"
    assert result.error.retryable is True
    assert result.error.retry_after_seconds == 30
Tiempo determinista con freezegun

freezegun permite congelar el reloj; su test oficial usa exactamente este patrón.
qaskills

python
# https://github.com/spulec/freezegun/blob/master/tests/test_uuid.py
import uuid
from freezegun import freeze_time


def test_uuid1():
    future_target = datetime.datetime(2056, 2, 6, 14, 3, 21)
    with freeze_time(future_target):
        assert time_from_uuid(uuid.uuid1()) == future_target

Adaptado a nuestro caso, sin copiar dependencias ajenas al dominio:

python
# tests/test_mastodon_post_age.py
# Patrón de freeze_time tomado de:
# https://github.com/spulec/freezegun/blob/master/tests/test_uuid.py
from datetime import datetime, timedelta, timezone
from freezegun import freeze_time

from growth.adapters.mastodon import parse_mastodon_datetime


@freeze_time("2026-10-10T12:00:00Z")
def test_post_age_uses_utc():
    created_at = parse_mastodon_datetime("2026-10-09T12:00:00.000Z")

    age = datetime.now(timezone.utc) - created_at

    assert age == timedelta(days=1)
Casos límite que sí debemos cubrir
Identidad federada

acct local: davidporto.

acct remoto: autor@fosstodon.org.

Dos cuentas con el mismo username en instancias distintas: identidades diferentes.

account.id y status.id siempre como cadenas.

Boost: el external_id de la acción es el del boost; el objetivo de comentario es el status original dentro de reblog.

Estado eliminado, suspendido o no visible: conservar trazabilidad, pero excluirlo de acciones.

Fechas

La API devuelve created_at en ISO-8601 UTC, por ejemplo 2016-03-16T14:44:31.580Z.

python
# tests/test_mastodon_datetime.py
import pytest
from datetime import datetime, timezone

from growth.adapters.mastodon import parse_mastodon_datetime


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-10-10T12:00:00Z", datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)),
        ("2026-10-10T12:00:00.000Z", datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)),
        ("2026-10-10T12:00:00+00:00", datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)),
    ],
)
def test_parse_mastodon_datetime(value, expected):
    assert parse_mastodon_datetime(value) == expected


def test_rejects_naive_datetime():
    with pytest.raises(ValueError):
        parse_mastodon_datetime("2026-10-10T12:00:00")
Paginación

La documentación oficial describe max_id, since_id, min_id y limit para GET /api/v1/accounts/:id/statuses; el límite máximo documentado es 40 statuses.

max_id: devuelve resultados anteriores a ese ID.

since_id: devuelve resultados posteriores a ese ID, sin incluirlo.

min_id: devuelve resultados inmediatamente posteriores al ID, orientado a obtener los elementos más nuevos.

limit: número solicitado de elementos; el máximo documentado es 40.

No hay que tratar since_id y min_id como sinónimos: pueden devolver conjuntos distintos según la implementación y el caso de uso. La prueba debe cubrir ambos cursores por separado.

python
# tests/test_mastodon_pagination.py
import json
from pathlib import Path

from growth.adapters.mastodon import MastodonAdapter


FIXTURES = Path(__file__).parents[1] / "fixtures" / "mastodon"


def test_pagination_splits_limit_above_40(fake_mastodon):
    adapter = MastodonAdapter(instance="mastodon.social", http=fake_mastodon)

    page = adapter.discover("#fantasy", limit=80)

    assert len(page.items) <= 40
    assert page.next_cursor is not None


def test_pagination_deduplicates_by_instance_and_status_id(fake_mastodon):
    adapter = MastodonAdapter(instance="mastodon.social", http=fake_mastodon)

    posts = adapter.discover("#fantasy", cursor="109900000000000010").items

    keys = [(post.instance, post.external_id) for post in posts]
    assert len(keys) == len(set(keys))
Contenido y visibilidad

visibility="private" y "direct": nunca candidatas a interacción pública.

sensitive=true: exigir política explícita antes de comentar.

spoiler_text no vacío: no interpretar el contenido como una conversación abierta.

content HTML: extraer texto plano conservando enlaces, menciones y hashtags.

language distinto de es: no comentar automáticamente salvo regla explícita.

reblog: no comentar el boost como si fuera contenido original.

Errores y recuperaciones

El repo ya contiene test_mastodon_5xx.py, test_http_retry.py, test_circuit_breaker.py, test_mastodon_budget.py, test_mastodon_reply_queue.py, test_r3_mastodon_stale_reply_pipeline.py y test_r4_mastodon_duplicate_preflight.py. Por tanto, no duplicaríamos esos tests: añadiríamos una taxonomía común y pruebas de frontera que los conecten.
github

Error	Clasificación	Comportamiento esperado
401	auth	Detener la cuenta; no reintentar
403	forbidden	Marcar acción bloqueada; no reintentar
404	not_found	Invalidar candidato; no reintentar
422	validation	Registrar causa; no reintentar sin corrección
429	rate_limit	Respetar Retry-After; reintentar después
500, 502, 503	server	Reintentar con backoff
Timeout	network	Mantener acción pendiente; nunca marcar éxito
JSON inválido	contract	Fallar rápido y registrar evidencia
Suite de regresión mínima
python
# tests/test_mastodon_adapter_contract.py
import json
from pathlib import Path

import pytest

from growth.adapters.mastodon import MastodonAdapter


FIXTURES = Path(__file__).parents[1] / "fixtures" / "mastodon"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "status_public_minimal.json",
        "status_public_with_html.json",
        "status_remote_author.json",
        "status_boost.json",
    ],
)
def test_status_fixture_matches_social_post_contract(fixture_name, adapter):
    payload = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
    post = adapter.normalize_status(payload)

    assert post.network == "mastodon"
    assert isinstance(post.external_id, str)
    assert post.author.external_id
    assert post.author.handle
    assert post.created_at.tzinfo is not None
    assert post.url.startswith("https://")
    assert post.visibility in {"public", "unlisted", "private", "direct"}


def test_remote_author_preserves_instance(adapter):
    payload = json.loads(
        (FIXTURES / "status_remote_author.json").read_text(encoding="utf-8")
    )
    post = adapter.normalize_status(payload)

    assert post.author.instance == "fosstodon.org"
    assert post.author.handle == "autor@fosstodon.org"


def test_boost_target_is_original_status(adapter):
    payload = json.loads(
        (FIXTURES / "status_boost.json").read_text(encoding="utf-8")
    )
    post = adapter.normalize_status(payload)

    assert post.reblog_of_external_id == "109900000000000002"
    assert post.external_id == "109900000000000003"
Plan de implementación en PR pequeñas

PR 1 — Contrato y fixtures base
Añadir PostRef, SocialAuthor, SocialPost, NetworkAdapter y ocho fixtures JSON. No modificar aún el adaptador de producción.

PR 2 — Normalización de identidad federada
Tests para acct, account_id, instancia, autor remoto, boost y cuentas no disponibles.

PR 3 — Fechas UTC y reloj inyectable
Parser estricto de ISO-8601, comparaciones UTC y validación de scheduled_at; usar freezegun solo en tests.

PR 4 — Paginación con cursores diferenciados
Cubrir max_id, since_id, min_id, limit, página vacía, duplicados y límite de 40.

PR 5 — Taxonomía de errores
MastodonError con kind, retryable, http_status y retry_after_seconds; conectarlo al circuit breaker ya existente.
github

PR 6 — Idempotencia de acciones
Clave determinista (network, action_type, target_external_id, content_hash) y pruebas de doble ejecución, crash y recuperación.

PR 7 — Integración HTTP grabada
Introducir responses para errores y contratos; reservar VCR.py para un número muy reducido de cassettes anonimizadas.
swirls

Aplicación multi-red
Concepto Mastodon	Contrato común
status_id y account_id como cadenas	external_id: str
acct@instancia	author.handle + author.instance
created_at ISO-8601 UTC	created_at: datetime con zona UTC
max_id, since_id, min_id	Cursor específico por red, nunca un cursor genérico
Boost	reblog_of_external_id / acción de recompartición
visibility	Enum común de visibilidad
429 y Retry-After	rate_limit con retry_after_seconds
Ledger de acciones	Misma estructura de auditoría para todas las redes
Fuentes

Repo espejo davidpd89/ci-sandbox-tmp, rama main; directorio tests/ con la cobertura Mastodon existente.
github

Documentación oficial de Mastodon: statuses
.

Documentación oficial de Mastodon: accounts/statuses
.

matthewdeanmartin/mastodon_mock.
github

getsentry/responses.
swirls

getsentry/pytest-responses.
swirls

kevin1024/vcrpy.

spulec/freezegun.
qaskills

halcy/Mastodon.py
.
