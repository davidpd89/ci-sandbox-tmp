# Tests y estandarización en Bluesky

Fuente: informe de Perplexity (https://www.perplexity.ai/search/2848bd96-b019-46f8-927a-9950a75f56b5), generado 10/10/2026.

Informe mejorado: pruebas, contratos y fixtures para el adaptador de Bluesky
Resumen

El informe anterior sobrestimaba la necesidad de crear una suite Bluesky desde cero. Tras revisar davidpd89/ci-sandbox-tmp en main, el sistema ya tiene una base de tests Bluesky muy amplia: rate limit, Jetstream, deduplicación de respuestas, TTL de reposts, URL de posts, RichText, preflight, confirmaciones de escritura, pool, notificaciones y auditoría propia.

La mejora correcta no es duplicar esos tests, sino añadir tres capas que hoy no están cubiertas de forma explícita: contrato multired, vectores oficiales de sintaxis AT Protocol y replay determinista de fixtures HTTP/WebSocket. La fuente más valiosa y directamente reutilizable es 
bluesky-social/atproto-interop-tests
, que publica datos neutrales de interoperabilidad bajo CC0.
github

Limitación importante: el conector GitHub devolvió los metadatos y SHA de conftest.py y test_recordings.py de truewire-dev/bluesky, pero no el texto íntegro de esos archivos. Por ello no incluyo fragmentos presentados falsamente como copias literales; en su lugar, dejo enlaces exactos a los archivos originales y proporciono código adaptado, listo para copiar en nuestro repositorio.
bsky
+1

Hallazgos
Área	Estado en el espejo	Referencia pública más útil	Acción recomendada
Rate limit	Ya existe tests/test_bluesky_rate_limit.py	
Rate Limits de Bluesky
	No duplicar; añadir contrato común de Retry-After, RateLimit-Reset y clasificación de error
Jetstream	Ya existe tests/test_bluesky_jetstream_collect.py	bluesky-social/jetstream	Añadir replay offline y test de recuperación por secuencia/cursor
Deduplicación de replies	Ya existe tests/test_bluesky_reply_dedupe.py	
truewire-dev/bluesky
	Elevar la clave de idempotencia a contrato multired
Identidad y sintaxis	Existen tests de URL y candidate identity, pero no vectores oficiales	atproto-interop-tests/syntax	Incorporar vectores DID, handle, AT-URI, CID, datetime, NSID y record key
Fechas	Hay tests de dominio, pero no una matriz oficial de fechas inválidas/válidas	datetime_syntax_valid.txt	Parametrizar parser propio con los vectores oficiales
Grabaciones y replay	Los tests actuales parecen mayoritariamente unitarios/offline	truewire-dev/bluesky/test_recordings.py	Adoptar grabaciones versionadas y mock HTTP/WebSocket
Contrato multired	Hay tests por red, pero no una suite de paridad común	
atproto-interop-tests
	Crear contrato común ejecutable contra todos los adaptadores

El árbol de tests/ confirma que ya existen más de 30 archivos específicos de Bluesky, incluidos test_bluesky_build_plan.py, test_bluesky_execute_preflight.py, test_bluesky_jetstream_collect.py, test_bluesky_rate_limit.py, test_bluesky_reply_dedupe.py, test_bluesky_repost_ttl.py, test_bluesky_richtext_search.py y test_bluesky_write_confirmations.py. Por tanto, cualquier PR nueva debe declarar qué regresión añade y qué test existente extiende, no crear un paralelo.

Qué eliminar del informe anterior

“Crear SocialAdapter con todos los métodos”: no como primer PR. El sistema ya tiene flujos separados de scan, preflight, ejecución, confirmaciones y auditoría; imponer de golpe una interfaz única podría chocar con esa arquitectura.

“Fixtures JSON grabados de perfiles, posts y threads” como prioridad inmediata: es útil, pero antes conviene adoptar los vectores oficiales de sintaxis, que son estables, pequeños y de licencia CC0.
github

“Usar MarshalX/atproto como referencia principal”: puede ser una dependencia práctica, pero no es la mejor referencia para contratos y fixtures; los vectores oficiales y las grabaciones de truewire-dev/bluesky resuelven mejor ese problema.
github

“Copiar el feed generator”: no aplica directamente. Su valor es conceptual —keyset y cursores—, pero nuestro sistema ya tiene tests de Jetstream y recolección; no conviene introducir otro subsistema de feed.

Vectores oficiales reutilizables

bluesky-social/atproto-interop-tests
 es el hallazgo menos obvio y más aprovechable: contiene archivos JSON y de texto “sencillos, autodescriptivos” para probar interoperabilidad y cumplimiento de especificación de AT Protocol. Está publicado con licencia CC0, por lo que sus vectores pueden copiarse al repositorio y versionarse como fixtures.
github

Vector	Archivo oficial	Uso en nuestro sistema
Handles válidos	syntax/handle_syntax_valid.txt	Normalización y validación de autor/autoría
Handles inválidos	syntax/handle_syntax_invalid.txt	Rechazo temprano antes de llamar a AppView
DIDs válidos	syntax/did_syntax_valid.txt	Identidad canónica por DID
DIDs inválidos	syntax/did_syntax_invalid.txt	invalid_identity, sin reintento
AT-URI válidas	syntax/aturi_syntax_valid.txt	Referencia canónica de post
AT-URI inválidas	syntax/aturi_syntax_invalid.txt	invalid_target, sin reintento
Fechas válidas	syntax/datetime_syntax_valid.txt	created_at, orden temporal y ventanas de frescura
Fechas inválidas	syntax/datetime_syntax_invalid.txt	Rechazo controlado y alerta de contrato
CID válidos/inválidos	syntax/cid_syntax_valid.txt, invalid	Validación de referencias a registros y medios
NSID y record keys	syntax/nsid_syntax_valid.txt, syntax/recordkey_syntax_valid.txt	Validación de colecciones y claves de registro

La existencia de archivos separados para sintaxis válida e inválida permite convertirlos directamente en tests parametrizados, sin inventar casos ni mantener dos fuentes de verdad.
github

Código reutilizable
1. Cargar vectores oficiales

Este módulo permite usar los ficheros CC0 como fixtures sin duplicar sus contenidos en Python.

python
# tests/bluesky_syntax_loader.py
# Adaptación propia para consumir los vectores de:
# https://github.com/bluesky-social/atproto-interop-tests/tree/main/syntax
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "atproto-interop-tests" / "syntax"


@dataclass(frozen=True)
class SyntaxVector:
    kind: str
    value: str
    source_file: str


def _read_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def syntax_vectors(kind: str) -> list[SyntaxVector]:
    valid = _read_lines(FIXTURES / f"{kind}_syntax_valid.txt")
    invalid = _read_lines(FIXTURES / f"{kind}_syntax_invalid.txt")
    return [
        SyntaxVector(kind, value, f"{kind}_syntax_valid.txt")
        for value in valid
    ] + [
        SyntaxVector(kind, value, f"{kind}_syntax_invalid.txt")
        for value in invalid
    ]


@pytest.fixture(scope="session")
def aturi_vectors() -> list[SyntaxVector]:
    return syntax_vectors("aturi")


@pytest.fixture(scope="session")
def datetime_vectors() -> list[SyntaxVector]:
    return syntax_vectors("datetime")

Los archivos originales están en bluesky-social/atproto-interop-tests/syntax, con pares explícitos *_valid.txt y *_invalid.txt para AT-URI, datetime, DID, handle, CID, NSID y record key.
github

2. Test de sintaxis parametrizado
python
# tests/test_bluesky_syntax_contract.py
# Valida el normalizador propio contra los vectores CC0 de:
# https://github.com/bluesky-social/atproto-interop-tests/tree/main/syntax
import pytest

from growth.bluesky.identity import (
    normalize_datetime,
    normalize_post_ref,
)


@pytest.mark.parametrize("vector", "aturi_vectors")
def test_aturi_contract(aturi_vectors, vector):
    if vector.value in _invalid_values(aturi_vectors):
        with pytest.raises(ValueError, match="invalid_at_uri"):
            normalize_post_ref(vector.value)
    else:
        ref = normalize_post_ref(vector.value)
        assert ref.did.startswith("did:")
        assert ref.collection == "app.bsky.feed.post"
        assert ref.rkey


@pytest.mark.parametrize("vector", "datetime_vectors")
def test_datetime_contract(datetime_vectors, vector):
    if vector.value in _invalid_values(datetime_vectors):
        with pytest.raises(ValueError, match="invalid_datetime"):
            normalize_datetime(vector.value)
    else:
        parsed = normalize_datetime(vector.value)
        assert parsed.tzinfo is not None


def _invalid_values(vectors):
    return {
        vector.value
        for vector in vectors
        if vector.source_file.endswith("_invalid.txt")
    }

Este test convierte los vectores oficiales en una regresión de contrato: si el adaptador acepta una AT-URI o fecha inválida, falla antes de que la anomalía llegue a discovery, ranking o ejecución.

3. Contrato multired mínimo

No propongo reemplazar los módulos actuales. Propongo un contrato de entrada/salida y errores, que cada adaptador puede implementar sin cambiar su arquitectura interna.

python
# tests/contracts/social_adapter_contract.py
# Contrato común propuesto para todos los adaptadores del sistema.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal


class ErrorClass(StrEnum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    NOT_FOUND = "not_found"
    INVALID_TARGET = "invalid_target"
    FORBIDDEN = "forbidden"
    NETWORK = "network"
    UPSTREAM = "upstream"
    CONTRACT_VIOLATION = "contract_violation"


@dataclass(frozen=True)
class PostCandidate:
    network: str
    external_id: str
    author_id: str
    author_handle: str | None
    text: str
    post_url: str
    created_at: datetime
    canonical_ref: str
    raw: dict


@dataclass(frozen=True)
class ActionResult:
    network: str
    intent_id: str
    target_ref: str
    action: Literal["reply", "like", "repost", "follow"]
    status: Literal["succeeded", "duplicate", "failed", "skipped"]
    external_id: str | None
    error_class: ErrorClass | None
    retry_after_seconds: int | None

La regla es que canonical_ref sea estable aunque cambie el handle. En Bluesky debe derivarse del DID, la colección y el record key; no del handle visible en la URL.

4. Taxonomía de errores

Bluesky documenta que las peticiones que superan un límite reciben normalmente HTTP 429 y que los servicios exponen cabeceras de rate limit; también señala que los límites varían por endpoint y pueden aplicar por IP o por cuenta. Por tanto, el contrato debe conservar las cabeceras, no solo el código HTTP.
bsky

python
# tests/contracts/error_mapping.py
# Mapa de errores propuesto; las cabeceras provienen de la documentación oficial:
# https://bsky.network/docs/rate-limits/
from tests.contracts.social_adapter_contract import ErrorClass

STATUS_TO_ERROR = {
    400: "invalid_target",
    401: "auth",
    403: "forbidden",
    404: "not_found",
    429: "rate_limit",
}


def classify(status_code: int, payload: dict | None = None) -> str:
    if status_code in STATUS_TO_ERROR:
        return STATUS_TO_ERROR[status_code]
    if 500 <= status_code <= 599:
        return "upstream"
    if payload and payload.get("error") == "RateLimitExceeded":
        return "rate_limit"
    return "contract_violation"


def retryable(error_class: str) -> bool:
    return error_class in {"rate_limit", "network", "upstream"}


def retry_after(headers: dict[str, str]) -> int | None:
    value = headers.get("Retry-After") or headers.get("retry-after")
    return int(value) if value and value.isdigit() else None

No reintentes invalid_target, not_found ni forbidden: son decisiones definitivas sobre un candidato o una acción. Para rate_limit, prioriza Retry-After; si no existe, usa backoff exponencial con tope y jitter.

5. Idempotencia de acciones

El repositorio ya contiene test_bluesky_reply_dedupe.py, test_bluesky_repost_ttl.py y test_bluesky_write_confirmations.py; el nuevo test debe verificar el contrato, no reimplementar esas protecciones.

python
# tests/contracts/test_action_idempotency.py
# Contrato común: un reintento tras una respuesta perdida no repite la acción.
from tests.contracts.social_adapter_contract import ActionResult


def test_retry_does_not_duplicate_action(adapter, recorded_action):
    first = adapter.execute(recorded_action)
    second = adapter.execute(recorded_action)

    assert first.status in {"succeeded", "duplicate"}
    assert second.status == "duplicate"
    assert first.external_id == second.external_id
    assert adapter.count_external_writes(recorded_action.intent_id) == 1

La clave mínima debe ser:

python
idempotency_key = (
    f"{network}:{action}:{canonical_target_ref}:"
    f"{intent_id}:{author_did_or_account_id}"
)

Esto es aplicable a Bluesky, Mastodon, X, Threads, Reddit y cualquier otra red donde una respuesta perdida pueda provocar un reintento.

Grabaciones y replay

truewire-dev/bluesky
 es especialmente relevante porque sus tests reproducen grabaciones HTTP y WebSocket mediante un mock local, sin tocar la red; además, su pipeline valida esquemas, código generado, pytest, tipado y linting en cada PR. El archivo clave es packages/python/test/test_recordings.py, complementado por conftest.py, record_jetstream.py y test_no_leaked_secrets.py.
bsky
+2

No copies su cliente ni su mock: adopta el patrón. Nuestro repositorio debe tener:

text
tests/fixtures/bluesky/
  recordings/
    search_posts.page1.http.json
    search_posts.page2.json
    get_post_thread.ok.json
    get_post_thread.deleted_parent.json
    create_reply.ok.json
    create_reply.conflict.json
    rate_limit_429.json
  jetstream/
    post.created.jsonl
    post.duplicate.jsonl
    reconnect.cursor.jsonl

Cada fixture debe declarar schema_version, captured_at, redacted=true y source_url. Antes de fusionar, un test debe impedir tokens, cookies, correos, DIDs privados sensibles y texto personal no necesario.

Errores y límites

La documentación oficial de Bluesky recoge límites por PDS, por IP y por cuenta; por ejemplo, 3.000 peticiones globales cada cinco minutos por IP en el límite general, además de límites más estrictos para operaciones concretas como actualización de handle o creación de sesión. El sistema debe modelar esos límites como política de adaptador, no como excepciones anónimas.
bsky

Tests mínimos:

HTTP 429 con Retry-After: 30 produce espera de 30 segundos y un único reintento planificado.

HTTP 429 sin Retry-After activa backoff exponencial con tope y jitter.

HTTP 403 en login no se clasifica automáticamente como rate limit; se audita como auth o forbidden según el payload.

Una ráfaga de 429 abre el circuit breaker y detiene nuevas acciones, en vez de agotar reintentos.

Las cabeceras RateLimit-Limit, RateLimit-Remaining y RateLimit-Reset se persisten para observabilidad.

Plan de PR pequeñas

PR 1 — Importar vectores CC0

Copiar syntax/*_valid.txt y syntax/*_invalid.txt a tests/fixtures/atproto-interop-tests/syntax/.

Mantener LICENSE-CC0 y un SOURCES.md con commit/SHA de origen.

Añadir test_bluesky_syntax_contract.py para AT-URI, datetime, DID y handle.

PR 2 — Contrato común

Crear tests/contracts/social_adapter_contract.py.

Definir PostCandidate, ActionResult, ErrorClass y idempotency_key.

No modificar todavía adaptadores de producción.

PR 3 — Errores y rate limit

Extraer la lógica común de clasificación y reintento.

Hacer que test_bluesky_rate_limit.py valide el contrato común.

Añadir fixtures 429 con y sin Retry-After.

PR 4 — Replay de Bluesky

Añadir grabaciones versionadas y mock HTTP/WebSocket.

Cubrir búsqueda, thread, respuesta, post eliminado y reconexión Jetstream.

Reutilizar el enfoque de truewire-dev/bluesky, sin acoplarse a su cliente.

PR 5 — Paridad multired

Ejecutar el contrato común contra Bluesky, Mastodon, X y Threads.

Publicar en CI una matriz de métodos soportados, fixtures disponibles y semántica de errores.

Marcar explícitamente capacidades no aplicables, en vez de fingir paridad total.

Fuentes

Repositorio espejo revisado: davidpd89/ci-sandbox-tmp, rama main; contiene una suite extensa de tests Bluesky y multired.

Vectores oficiales reutilizables: 
bluesky-social/atproto-interop-tests
, con datos neutrales para interoperabilidad y especificación, bajo CC0.
github

Documentación oficial de límites: 
https://bsky.network/docs/rate-limits/
.
bsky

Patrón de grabación/replay: 
truewire-dev/bluesky
, activo y con tests que reproducen HTTP y WebSocket sin acceso a red.
bsky
+2

Cliente Python tipado y validado: 
truewire-dev/bluesky
, generado desde ejemplos de wire grabados.
github

Servicio Jetstream: bluesky-social/jetstream, relevante para eventos, reconexión y recuperación.
