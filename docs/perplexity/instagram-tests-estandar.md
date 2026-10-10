# Tests y estandarización en Instagram

Fuente: informe de Perplexity (https://www.perplexity.ai/search/d9a934c5-4bd0-43ee-8748-d2f5bee977ac), generado 10/10/2026.

Informe mejorado: pruebas, contratos y fixtures para el adaptador de Instagram
Resumen

Tras revisar el espejo davidpd89/ci-sandbox-tmp, la propuesta anterior era correcta en su núcleo, pero incluía elementos poco accionables: Schemathesis no es prioritario porque Instagram no ofrece un OpenAPI estable para generar contratos, e instagrapi no encaja con el sistema porque implementa un cliente no oficial distinto del flujo Graph API/Meta ya presente en el repo. La vía correcta es reforzar los tests Instagram existentes con un contrato JSON Schema propio, fixtures deterministas, responses para errores y pytest-recording para regresiones HTTP offline.

El repositorio ya contiene test_instagram_commenters_scan.py, test_instagram_paused.py, test_instagram_query_trials.py, test_meta_apis.py, test_meta_publish.py, test_r1_candidate_identity.py, test_r9_reply_cache_identity.py, test_network_capabilities.py y test_no_public_network.py; por tanto, los PR nuevos deben extender esas piezas, no duplicarlas.

Hallazgos verificables
Necesidad	Repositorio / fuente	Estado y utilidad	Qué copiar	Integración
Mock HTTP de errores y parsing	
getsentry/responses
	Activo; 4,3k estrellas, 836 commits, Apache-2.0; requiere Python 3.8+ y requests >= 2.30.	Decorador @responses.activate, matchers de query/body y callbacks	Tests de contrato y errores sin red
Grabación y replay HTTP	
kiwicom/pytest-recording
	Activo; 616 estrellas, 207 commits, MIT; soporta CPython 3.10–3.15.	@pytest.mark.vcr, vcr_config, --record-mode, --block-network	Regresiones de lectura de Graph API
Validación de contrato	
python-jsonschema/jsonschema
	Activo; 5k estrellas, 3.143 commits; soporta Draft 2020-12. 
github
	validate(instance, schema)	Validar candidatos, acciones y errores
Cliente Meta/Instagram de referencia	
facebook/facebook-python-business-sdk
	SDK oficial; sus tests unitarios no requieren token ni red. 
developers.facebook
	Patrón de separación entre cliente, modelos y tests	Referencia de estructura, no copia directa del cliente
Wrapper Graph Facebook/Instagram	
sns-sdks/python-facebook
	Cubre Graph API de Facebook, Instagram Business y Basic Display. 
github
	Nombres de campos y organización de edges	Comparar mapeos de media/comentarios
Extracción normalizada de identidad	
soxoj/socid-extractor
	Interfaz uniforme extract() para Instagram, Reddit, TikTok, Bluesky, etc.; exige tests e2e y unitarios con fixtures inline. 
github
	Patrón de salida plana y tests por esquema	Inspiración para el contrato multired
Errores oficiales	
Meta: Instagram Platform error codes
	Documentación oficial de códigos y subcodes; incluye ejemplo con code 3600 y subcode 2207004.	Tabla de clasificación de errores	Router de reintentos y fallos permanentes

Eliminado del informe anterior: schemathesis como pieza central, porque no hay un esquema OpenAPI público y estable de Instagram sobre el que generar pruebas; e instagrapi, porque resuelve otro problema —automatización no oficial mediante emulación de app— y no aporta al contrato Graph API del adaptador.

Contrato interno obligatorio

Usa un contrato propio versionado, no un “contrato de Instagram” genérico. El objeto mínimo debe ser idéntico en todas las redes, con campos específicos de Instagram como media_id, comment_id y container_id.

json
{
  "network": "instagram",
  "candidate_type": "post|comment|profile",
  "external_id": "17895695668004550",
  "canonical_key": "instagram:media:17895695668004550",
  "author": {
    "user_id": "17841400000000000",
    "username": "lector_fantasia",
    "permalink": "https://www.instagram.com/lector_fantasia/"
  },
  "media": {
    "media_id": "17895695668004550",
    "media_type": "IMAGE|VIDEO|CAROUSEL_ALBUM",
    "permalink": "https://www.instagram.com/p/ABC123/",
    "timestamp": "2026-10-10T13:44:00+0000"
  },
  "parent_comment_id": null,
  "text": "Me encanta la ambientación de tu novela.",
  "captured_at": "2026-10-10T13:44:00Z",
  "signals": {
    "like_count": 12,
    "reply_count": 3
  },
  "action": {
    "kind": "like|comment|follow",
    "eligible": true,
    "reason": "context_match"
  }
}

Reglas no negociables:

user_id es identidad estable; username es presentación y puede cambiar.

media_id, comment_id y container_id son identificadores distintos.

canonical_key debe ser determinista: instagram:media:{media_id} o instagram:comment:{comment_id}.

timestamp y captured_at se normalizan a UTC antes de calcular frescura, TTL o deduplicación.

Toda acción se registra con action_id, candidate_key, attempted_at, outcome y error_code, en línea con el ledger ya existente.

Código reutilizable
1. Esquema de candidato y validación

Este bloque es una adaptación directa del patrón de validación de jsonschema; el original muestra validate(instance, schema) y el fallo con ValidationError.
github

python
# https://github.com/python-jsonschema/jsonschema#jsonschema
from jsonschema import validate

IG_CANDIDATE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "network",
        "candidate_type",
        "external_id",
        "canonical_key",
        "author",
        "captured_at",
    ],
    "properties": {
        "network": {"const": "instagram"},
        "candidate_type": {"enum": ["post", "comment", "profile"]},
        "external_id": {"type": "string", "minLength": 1},
        "canonical_key": {
            "type": "string",
            "pattern": r"^instagram:(media|comment|profile):[A-Za-z0-9_:-]+$",
        },
        "author": {
            "type": "object",
            "required": ["user_id"],
            "properties": {
                "user_id": {"type": "string", "minLength": 1},
                "username": {"type": ["string", "null"]},
                "permalink": {"type": ["string", "null"]},
            },
        },
        "media": {
            "type": ["object", "null"],
            "properties": {
                "media_id": {"type": "string"},
                "media_type": {
                    "enum": ["IMAGE", "VIDEO", "CAROUSEL_ALBUM"]
                },
                "permalink": {"type": ["string", "null"]},
                "timestamp": {"type": ["string", "null"]},
            },
        },
        "parent_comment_id": {"type": ["string", "null"]},
        "text": {"type": ["string", "null"]},
        "captured_at": {"type": "string"},
        "signals": {"type": "object"},
        "action": {
            "type": "object",
            "required": ["kind", "eligible"],
            "properties": {
                "kind": {"enum": ["like", "comment", "follow"]},
                "eligible": {"type": "boolean"},
                "reason": {"type": "string"},
            },
        },
    },
}


def validate_instagram_candidate(candidate: dict) -> None:
    validate(instance=candidate, schema=IG_CANDIDATE_SCHEMA)
2. Normalización de fechas e identidad

Este bloque es nuevo y específico para el adaptador; resuelve los dos riesgos más frecuentes: handles mutables y fechas con offset.

python
# Nuevo código para davidpd89/ci-sandbox-tmp
# Ubicación sugerida: tools/instagram_contract.py
from datetime import datetime, timezone


def normalize_instagram_timestamp(value) -> str:
    if value in (None, ""):
        raise ValueError("instagram timestamp is empty")

    if isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def instagram_canonical_key(
    *,
    candidate_type: str,
    external_id: str,
) -> str:
    if candidate_type not in {"media", "comment", "profile"}:
        raise ValueError(f"unsupported candidate_type: {candidate_type}")
    if not external_id:
        raise ValueError("external_id is required")
    return f"instagram:{candidate_type}:{external_id}"


def instagram_identity(user_id: str, username: str | None = None) -> dict:
    if not user_id:
        raise ValueError("user_id is the stable identity and is required")
    return {
        "user_id": str(user_id),
        "username": username,
    }
3. Fixture de errores con responses

El siguiente test sigue el patrón oficial de responses: registrar una respuesta, ejecutar la petición y comprobar status/cuerpo; el repositorio documenta además query_param_matcher, respuestas múltiples y callbacks.

python
# Adaptado de:
# https://github.com/getsentry/responses#main-interface
# y https://github.com/getsentry/responses#query-parameters-matcher
import pytest
import requests
import responses
from responses import matchers

GRAPH = "https://graph.facebook.com/v21.0"


@responses.activate
def test_instagram_media_parses_timestamp_and_identity():
    responses.get(
        f"{GRAPH}/17895695668004550",
        json={
            "id": "17895695668004550",
            "media_type": "IMAGE",
            "permalink": "https://www.instagram.com/p/ABC123/",
            "timestamp": "2026-10-10T13:44:00+0000",
            "username": "lector_fantasia",
        },
        status=200,
        match=[matchers.query_param_matcher({"fields": "id,media_type,permalink,timestamp,username"})],
    )

    response = requests.get(
        f"{GRAPH}/17895695668004550",
        params={"fields": "id,media_type,permalink,timestamp,username"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "17895695668004550"
    assert payload["timestamp"] == "2026-10-10T13:44:00+0000"


@responses.activate
def test_instagram_rate_limit_is_classified_without_retry():
    responses.get(
        f"{GRAPH}/17895695668004550/comments",
        json={
            "error": {
                "message": "Application request limit reached",
                "type": "OAuthException",
                "code": 4,
                "fbtrace_id": "test-trace",
            }
        },
        status=429,
    )

    response = requests.get(f"{GRAPH}/17895695668004550/comments")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == 4
4. Configuración VCR para regresiones offline

Este bloque reproduce el uso recomendado de pytest-recording: marca @pytest.mark.vcr, configuración mediante vcr_config, filtrado de cabeceras sensibles y bloqueo global de red.

python
# Adaptado de:
# https://github.com/kiwicom/pytest-recording#usage
# y https://github.com/kiwicom/pytest-recording#configuration
import pytest
import requests


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": ["authorization"],
        "filter_query_parameters": ["access_token"],
    }


@pytest.mark.vcr("tests/fixtures/instagram/cassettes/media_read.yaml")
def test_instagram_media_read_replay():
    response = requests.get(
        "https://graph.facebook.com/v21.0/17895695668004550",
        params={
            "fields": "id,media_type,permalink,timestamp,username",
            "access_token": "REDACTED",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "17895695668004550"

Ejecución recomendada en CI:

bash
# Adaptado de:
# https://github.com/kiwicom/pytest-recording#blocking-network-access
pytest tests/test_instagram_http_replay.py --record-mode=none --block-network

pytest-recording usa por defecto record-mode=none, precisamente para impedir peticiones accidentales; para regenerar un cassette hay que ejecutar explícitamente con --record-mode=once o --record-mode=rewrite.

5. Fixture JSON de comentario
json
{
  "meta": {
    "contract_version": "instagram-adapter-v1",
    "network": "instagram",
    "source": "synthetic",
    "captured_at": "2026-10-10T13:44:00Z"
  },
  "request": {
    "method": "GET",
    "url": "https://graph.facebook.com/v21.0/17895695668004550/comments",
    "params": {
      "fields": "id,text,timestamp,username,from",
      "limit": 25
    }
  },
  "response": {
    "status": 200,
    "body": {
      "data": [
        {
          "id": "17899990000000001",
          "text": "La tensión del capítulo final es brutal.",
          "timestamp": "2026-10-10T12:30:00+0000",
          "username": "lectora_rpg",
          "from": {
            "id": "17841400000000001",
            "username": "lectora_rpg"
          }
        }
      ],
      "paging": {
        "cursors": {
          "after": "CURSOR_2"
        },
        "next": "https://graph.facebook.com/v21.0/17895695668004550/comments?after=CURSOR_2"
      }
    }
  },
  "expectation": {
    "canonical_key": "instagram:comment:17899990000000001",
    "author_user_id": "17841400000000001",
    "media_id": "17895695668004550",
    "normalized_timestamp": "2026-10-10T12:30:00Z"
  }
}
Casos límite y regresiones
Identidad
Caso	Resultado exigido
Mismo user_id, username distinto	Mismo candidato; actualiza username, no crea duplicado
Mismo username, user_id distinto	Candidatos separados
Comentario duplicado en dos scans	Misma canonical_key; segunda aparición se descarta
Respuesta anidada	Conserva parent_comment_id y media_id raíz
Autor privado, bloqueado o eliminado	eligible=false; no interrumpe el lote
Autor igual a la cuenta propia	Exclusión previa a encolar acción
Fechas
Entrada	Resultado exigido
2026-10-10T13:44:00+0000	2026-10-10T13:44:00Z
2026-10-10T15:44:00+02:00	2026-10-10T13:44:00Z
Epoch numérico	Fecha UTC válida
null, "", texto inválido	Error controlado y registro de parse_error
Fecha futura o demasiado antigua	Fuera de ventana; sin acción
Contenedor EXPIRED	No reutilizar contenedor; nueva creación o fallo permanente
Errores y resiliencia
Fixture	Clasificación	Política
HTTP 401/403 con error de token	auth_required	Sin reintento ciego
HTTP 403 de permisos	permission_required	Marca cuenta/capacidad no publicable
HTTP 429 o código de límite	rate_limited	Detiene ola y registra cooldown
HTTP 500/502/503	transient	Backoff limitado
HTTP 200 con JSON inválido	parse_error	Sin acción ni escritura de candidato
paging.next inválido	partial_success	Conserva lote parcial
Contenedor IN_PROGRESS	pending	Revalidación posterior
Contenedor EXPIRED	failed_permanent	No reintento con el mismo contenedor

Meta documenta códigos y subcodes de Instagram; el router debe decidir por code y subcode, nunca por el texto del mensaje.

Plan de implementación en PR pequeñas
PR	Archivos	Objetivo	Criterio
PR 1	docs/contracts/instagram_adapter.md, tools/instagram_contract.py	Contrato y normalización	Sin red; cubre identidad y timestamps
PR 2	tests/fixtures/instagram/*.json	Fixtures sintéticos	Todos los JSON validan contra el esquema
PR 3	tests/test_instagram_contract_schema.py	Validación de contrato	Rechaza IDs vacíos, red incorrecta y claves duplicadas
PR 4	tests/test_instagram_timestamp_normalization.py	Fechas	ISO 8601, offsets, epoch y errores controlados
PR 5	tests/test_instagram_error_routing.py	Errores	Token, permisos, 429, 5xx, JSON roto y paginación
PR 6	tests/test_instagram_commenters_edge_cases.py	Descubrimiento	Extiende test_instagram_commenters_scan.py sin duplicarlo
PR 7	tests/test_instagram_capabilities_contract.py	Capacidades	Instagram declara solo acciones con executor/verificación
PR 8	tests/test_instagram_publish_lifecycle.py	Publicación	Contenedor, estados, publicación y permalink
PR 9	tests/test_instagram_http_replay.py, tests/fixtures/instagram/cassettes/	Regresión HTTP	Cassettes sanitizados; CI con --block-network
PR 10	tests/test_instagram_round_regression.py	Integración	Ledger, pausa, dedupe y fallo parcial no corrompen estado
Aplicación multired

X, Threads, Bluesky y Mastodon: reutiliza identidad estable + handle mutable, normalización UTC, canonical_key, errores de token/rate limit y deduplicación.

Facebook: comparte familia Meta con Instagram; separa explícitamente page_id, post_id, comment_id y permalink.

Pinterest: usa pin_id, board_id y URL canónica; aprovecha los tests existentes de schedule y revalidación en vez de crear otro ciclo de publicación.

Reddit: usa fullname/ID, subreddit y permalink; añade errores de comentario, voto y contenido eliminado.

TikTok: conserva el patrón ya presente de challenge/captcha/pausa; no lo mezcles con el contrato de publicación Graph API.

Mastodon: la identidad federada debe ser user@instance; el handle no es globalmente único.

Fuentes

Repositorio espejo y tests existentes: https://github.com/davidpd89/ci-sandbox-tmp/tree/60aa837fcbe2933928ee69aa395806a3bd5a74d1/tests

getsentry/responses: 
https://github.com/getsentry/responses

kiwicom/pytest-recording: 
https://github.com/kiwicom/pytest-recording

python-jsonschema/jsonschema: 
https://github.com/python-jsonschema/jsonschema
github

facebook/facebook-python-business-sdk: 
https://github.com/facebook/facebook-python-business-sdk
developers.facebook

sns-sdks/python-facebook: 
https://github.com/sns-sdks/python-facebook
github

soxoj/socid-extractor: 
https://github.com/soxoj/socid-extractor
github

Meta, códigos de error de Instagram: 
https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/error-codes/
