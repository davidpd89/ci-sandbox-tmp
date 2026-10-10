# Tests y estandarización en Facebook (páginas y grupos)

Fuente: informe de Perplexity (https://www.perplexity.ai/search/b8a2b6c6-f666-4d64-8b31-b46eec2c7763), generado 10/10/2026.

Informe mejorado: pruebas, contratos y fixtures para el adaptador de Facebook

He revisado el informe anterior contra el código real del espejo y he eliminado referencias poco aprovechables. La conclusión revisada es más estricta: no conviene copiar scrapers ni SDKs completos; la pieza más valiosa y activa para copiar es el patrón de tests de airbytehq/airbyte para Facebook Marketing: mocks HTTP con requests_mock, fixtures de paginación, control del sleep y tests específicos de errores.
developers.facebook

Resumen

El sistema ya tiene tests de Facebook y Meta: test_facebook_build_plan.py, test_facebook_like_comments.py, test_facebook_pool.py, test_meta_apis.py, test_meta_publish.py, test_meta_inbox.py y test_meta_insights.py. También existen contratos transversales que deben reutilizarse: ledger de acciones, identidad de candidatos, capacidades de red, guardas offline, recuperación de colas y política de antigüedad.
developers.facebook

Por tanto, la mejora no es crear un “framework Facebook” paralelo, sino añadir un contrato de adaptador Facebook Pages + Groups con fixtures HTTP deterministas, normalización de fechas e identidad, y una tabla única de errores Graph API.

Qué he corregido del informe anterior
Punto anterior	Decisión revisada
Usar kevinzg/facebook-scraper como referencia de fixtures	Eliminado como dependencia o patrón principal. Es un scraper orientado a HTML público, con mantenimiento y fiabilidad variables; no encaja con un adaptador basado en Graph API y contratos estables. 
thunderbit

Usar SocialAPIsHub/facebook-scraper-python	Eliminado. Depende de un servicio externo y su valor principal es comercial, no un patrón de tests reutilizable para nuestro repo. 
github

Adoptar mobolic/facebook-sdk	Reducido a referencia histórica. Es útil para entender get_object, get_connections y put_object, pero no es la mejor base activa para tests modernos. 
github

Recomendar sns-sdks/python-facebook	Mantenido solo como referencia secundaria. Tiene tests, pero su cobertura y mantenimiento no superan al patrón de Airbyte para errores, paginación y mocks.
Tests basados solo en JSON de Graph	Reforzado. Los fixtures deben simular HTTP completo —status, headers, body y paginación—, no solo objetos JSON sueltos.
Hallazgos principales
Repositorio / fuente	Estado y utilidad	Qué copiar	Integración	Riesgos
airbytehq/airbyte — source-facebook-marketing	Activo, mantenido y con tests unitarios amplios para Facebook Graph/Marketing API.	conftest.py, test_errors.py, test_api.py, test_base_streams.py y fixtures HTTP.	Copiar el patrón, no el conector: requests_mock, fixtures con paging.cursors, control de time.sleep y clasificación de errores.	Está orientado a Marketing API; hay que adaptar endpoints a Pages y Groups.

facebook/facebook-python-business-sdk
	Oficial y activo; sus tests unitarios no requieren token ni red.	Validación de parámetros, objetos y errores del SDK.	Usar como referencia de contratos de Graph API, no como dependencia si ya existe cliente propio.	Cubre sobre todo Marketing API; no resuelve el flujo completo de grupos.

sns-sdks/python-facebook
	Repositorio con tests para Facebook e Instagram Graph API.	Casos de cliente, paginación y errores.	Extraer casos concretos a nuestros fixtures; no adoptar el paquete completo.	Mantenimiento y cobertura desiguales.

Meta: error handling
	Fuente oficial vigente.	Mapa de códigos, subcodes y políticas de recuperación.	Crear FACEBOOK_ERROR_CONTRACT compartido por Pages y Groups.	Los subcodes cambian la semántica; el code solo no basta.

Meta: eventos y fechas
	Fuente oficial vigente. 
developers.facebook
	created_time / updated_time en ISO 8601.	Normalizar todas las fechas a UTC consciente de zona horaria.	Pueden llegar offsets distintos, epoch o campos ausentes.
Código tal cual para reutilizar
1. Fixtures HTTP y control de reintentos

Este es el bloque más directamente aprovechable. Proviene del conector Facebook de Airbyte y muestra cómo aislar los tests de red, controlar los reintentos y simular paginación con cursores.

python
# https://github.com/airbytehq/airbyte/blob/master/airbyte-integrations/connectors/source-facebook-marketing/unit_tests/conftest.py
from datetime import timedelta

from facebook_business import FacebookAdsApi, FacebookSession
from pytest import fixture
from source_facebook_marketing.api import API


FB_API_VERSION = FacebookAdsApi.API_VERSION


@fixture(autouse=True)
def time_sleep_mock(mocker):
    time_mock = mocker.patch("time.sleep")
    yield time_mock


@fixture(scope="session", name="account_id")
def account_id_fixture():
    return "unknown_account"


@fixture(scope="session", name="some_config")
def some_config_fixture(account_id):
    return {
        "start_date": "2021-01-23T00:00:00Z",
        "account_ids": [f"{account_id}"],
        "access_token": "unknown_token",
    }


@fixture(autouse=True)
def mock_default_sleep_interval(mocker):
    mocker.patch(
        "source_facebook_marketing.streams.common.DEFAULT_SLEEP_INTERVAL",
        return_value=timedelta(seconds=5),
    )


@fixture(name="fb_account_response")
def fb_account_response_fixture(account_id):
    return {
        "json": {
            "data": [
                {
                    "account_id": account_id,
                    "id": f"act_{account_id}",
                }
            ],
            "paging": {
                "cursors": {
                    "before": "MjM4NDYzMDYyMTcyNTAwNzEZD",
                    "after": "MjM4NDYzMDYyMTcyNTAwNzEZD",
                }
            },
        },
        "status_code": 200,
    }


@fixture(name="api")
def api_fixture(some_config, requests_mock, fb_account_response):
    api = API(access_token=some_config["access_token"], page_size=100)

    requests_mock.register_uri(
        "GET",
        FacebookSession.GRAPH + f"/{FB_API_VERSION}/me/adaccounts",
        [fb_account_response],
    )
    requests_mock.register_uri(
        "GET",
        FacebookSession.GRAPH + f"/{FB_API_VERSION}/act_{some_config['account_ids'][0]}/",
        [fb_account_response],
    )
    return api


@fixture(name="config")
def config_fixture(requests_mock):
    config = {
        "account_ids": ["123"],
        "access_token": "ACCESS_TOKEN",
        "credentials": {
            "auth_type": "Service",
            "access_token": "ACCESS_TOKEN",
        },
        "start_date": "2019-10-10T00:00:00Z",
        "end_date": "2020-10-10T00:00:00Z",
    }
    requests_mock.register_uri(
        "GET",
        FacebookSession.GRAPH + f"/{FacebookAdsApi.API_VERSION}/me/business_users",
        json={"data": []},
    )
    requests_mock.register_uri(
        "GET",
        FacebookSession.GRAPH + f"/{FacebookAdsApi.API_VERSION}/act_123/",
        json={"account": 123},
    )
    return config

Adaptación a nuestro sistema: conservar time_sleep_mock, requests_mock.register_uri, la estructura {"json": ..., "status_code": ...} y los cursores before/after; sustituir FacebookSession.GRAPH, adaccounts y act_* por nuestros endpoints de Page/Group y nuestro cliente HTTP.

2. Tests de errores que sí conviene replicar

Airbyte mantiene un fichero específico de errores, test_errors.py, con 30 KB de casos; es la referencia más útil para probar errores Graph, reintentos y mensajes de diagnóstico. No copiar el fichero completo: copiar su estructura de test —respuesta HTTP + código/subcode + resultado esperado—.

python
# Patrón adaptado de:
# https://github.com/airbytehq/airbyte/blob/master/airbyte-integrations/connectors/source-facebook-marketing/unit_tests/test_errors.py
import pytest
import requests
from requests_mock import Mocker


GRAPH = "https://graph.facebook.com/v23.0"


@pytest.mark.parametrize(
    ("status_code", "payload", "expected_kind"),
    [
        (
            400,
            {
                "error": {
                    "message": "Invalid parameter",
                    "type": "OAuthException",
                    "code": 100,
                    "fbtrace_id": "trace-invalid-parameter",
                }
            },
            "invalid_request",
        ),
        (
            401,
            {
                "error": {
                    "message": "Error validating access token",
                    "type": "OAuthException",
                    "code": 190,
                    "fbtrace_id": "trace-auth",
                }
            },
            "auth",
        ),
        (
            403,
            {
                "error": {
                    "message": "Insufficient permission",
                    "type": "OAuthException",
                    "code": 200,
                    "fbtrace_id": "trace-permission",
                }
            },
            "permission",
        ),
        (
            400,
            {
                "error": {
                    "message": "Please reduce the amount of data",
                    "type": "OAuthException",
                    "code": 4,
                    "fbtrace_id": "trace-throttle",
                }
            },
            "throttle",
        ),
        (
            400,
            {
                "error": {
                    "message": "Duplicate Post",
                    "type": "OAuthException",
                    "code": 506,
                    "fbtrace_id": "trace-duplicate",
                }
            },
            "duplicate",
        ),
    ],
)
def test_facebook_error_contract(requests_mock: Mocker, status_code, payload, expected_kind):
    requests_mock.get(
        f"{GRAPH}/group_123/feed",
        status_code=status_code,
        json=payload,
    )

    response = requests.get(f"{GRAPH}/group_123/feed")
    body = response.json()

    assert response.status_code == status_code
    assert body["error"]["code"] in {100, 190, 200, 4, 506}
    assert expected_kind in {"invalid_request", "auth", "permission", "throttle", "duplicate"}

Nota: este bloque es un patrón adaptado, no una copia literal completa de test_errors.py; el fichero original es más extenso y está acoplado al conector de Airbyte.

Contrato del adaptador
python
# tests/contracts/facebook_adapter_contract.py
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional


FacebookSurface = Literal["page", "group"]


@dataclass(frozen=True)
class FacebookTarget:
    network: Literal["facebook"]
    surface: FacebookSurface
    external_id: str
    kind: Literal["post", "comment", "profile", "group_post"]
    canonical_url: Optional[str]
    parent_external_id: Optional[str]
    author_external_id: Optional[str]
    author_display_name: Optional[str]
    created_at_utc: Optional[datetime]
    text: str
    engagement: dict
    raw: dict

Reglas:

external_id debe ser el ID estable de Graph o un ID extraído y validado de URL; nunca el nombre, slug o URL completa.

created_at_utc debe ser datetime con zona horaria UTC o None; nunca una cadena sin normalizar.

raw conserva la respuesta original para auditoría y reprocesado.

Un comentario debe llevar parent_external_id con el ID del post; una respuesta debe llevar además el ID del comentario raíz cuando esté disponible.

La misma entidad obtenida por Graph, URL o fixture debe generar la misma candidate_key.

Esto se integra con los tests ya existentes de identidad de candidatos, ledger y guardas multinetwork, en lugar de duplicarlos.
developers.facebook

Fechas: contrato y código

Facebook documenta campos temporales como created_time y updated_time en formato ISO 8601. El adaptador debe aceptar las variantes reales y fallar de forma controlada ante formatos inválidos.
developers.facebook

python
# tests/contracts/facebook_datetime_contract.py
from datetime import datetime, timezone


def parse_facebook_datetime(value):
    """Normaliza created_time/updated_time de Facebook a UTC."""
    if value in (None, ""):
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    text = str(value).strip()

    # Facebook usa con frecuencia el offset sin dos puntos: +0000, +0200.
    normalized = text
    if len(text) >= 5 and text[-5] in "+-" and text[-3:].isdigit():
        normalized = f"{text[:-2]}:{text[-2:]}"

    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)

Casos de regresión:

python
# tests/test_facebook_datetime_contract.py
# Contrato propio del sistema; compatible con el formato ISO 8601 documentado por Meta.
from datetime import datetime, timezone

from tests.contracts.facebook_datetime_contract import parse_facebook_datetime


def test_accepts_offset_without_colon():
    assert parse_facebook_datetime("2026-10-10T10:30:00+0000") == datetime(
        2026, 10, 10, 10, 30, tzinfo=timezone.utc
    )


def test_accepts_z_suffix():
    assert parse_facebook_datetime("2026-10-10T10:30:00Z").tzinfo == timezone.utc


def test_converts_offset_to_utc():
    parsed = parse_facebook_datetime("2026-10-10T12:30:00+0200")
    assert parsed.hour == 10
    assert parsed.utcoffset().total_seconds() == 0


def test_accepts_epoch():
    assert parse_facebook_datetime(1760000000).tzinfo == timezone.utc


def test_null_and_empty_are_none():
    assert parse_facebook_datetime(None) is None
    assert parse_facebook_datetime("") is None


def test_invalid_date_raises():
    import pytest

    with pytest.raises(ValueError):
        parse_facebook_datetime("not-a-date")
Errores: contrato operativo

La tabla debe basarse en los códigos documentados por Meta y clasificarlos por efecto sobre la cola, no solo por tipo HTTP.

Código / situación	Clasificación	Acción del sistema	Test mínimo
1, 2	Transitorio	Retry con backoff, registrar intento	No marca el candidato como defectivo
4, 17, 341	Throttling	Pausa superficie, reduce volumen	No reintenta en la misma ronda
3, 10, 200-299	Permisos	Deshabilita acción o superficie concreta	No reintenta ciegamente
190, 102, 463, 467	Auth	Detiene escritura y exige reautenticación	No publica ni comenta
458, 459, 460, 464	Sesión/cuenta	Estado needs_human	No automatiza sobre sesión inválida
492	Rol Page insuficiente	Bloquea esa Page	No confunde con token global
368	Bloqueo temporal	Cooldown por cuenta/superficie	No reintenta de inmediato
506	Duplicado	No repite el mismo texto; marca resultado	Ledger registra intento y resultado
100	Parámetro inválido	Fallo de contrato; test rojo	Valida payload antes de enviar
HTTP 5xx / timeout	Transitorio	Retry limitado, idempotente	No duplica comentario ni publicación

El código 506 es crítico para comentarios: debe detectarse en preflight cuando sea posible y confirmarse en postflight; el resultado debe quedar en el ledger, no solo en logs.
developers.facebook

Fixtures recomendados
text
tests/fixtures/facebook/
  page_post_basic.json
  page_post_no_text.json
  page_post_shared.json
  page_comment_basic.json
  page_comment_nested.json
  page_comment_deleted_author.json
  group_post_basic.json
  group_post_membership_limited.json
  group_comment_basic.json
  graph_page_1.json
  graph_page_2.json
  graph_empty_results.json
  graph_error_auth.json
  graph_error_permission.json
  graph_error_throttle.json
  graph_error_duplicate_post.json
  graph_error_invalid_parameter.json

Cada fixture debe contener:

json
{
  "request": {
    "method": "GET",
    "url": "https://graph.facebook.com/v23.0/1234567890/feed",
    "query": {"limit": "25", "fields": "id,message,created_time,from,permalink_url"}
  },
  "response": {
    "status_code": 200,
    "json": {
      "data": [],
      "paging": {
        "cursors": {
          "before": "CURSOR_BEFORE",
          "after": "CURSOR_AFTER"
        }
      }
    }
  },
  "expected": {
    "candidate_count": 0,
    "has_next_page": false
  }
}

La estructura de paginación con paging.cursors debe seguir el patrón ya probado en Airbyte.

Plan de implementación en PR pequeñas

PR 1 — Contrato base y fechas
Añadir FacebookTarget, parse_facebook_datetime, fixtures de fecha y tests de normalización.

PR 2 — Fixtures HTTP de Pages y Groups
Crear tests/fixtures/facebook/ con respuestas completas: status, body, paginación y errores.

PR 3 — Contrato de errores Graph
Implementar FACEBOOK_ERROR_CONTRACT y tests parametrizados para 100, 190, 200, 4, 17, 506, 368 y 5xx.

PR 4 — Pages: comentarios y respuestas
Extender test_facebook_like_comments.py con comentario anidado, autor borrado, texto vacío, duplicado y error 506.
developers.facebook

PR 5 — Groups: descubrimiento y elegibilidad
Tests de post de grupo, antigüedad, permisos insuficientes, autor débil y contenido no accionable, reutilizando test_facebook_pool.py y la política de edad existente.
developers.facebook

PR 6 — Idempotencia y ledger
Tests de candidate_key, preflight, reintento, postflight y registro en ledger; reutilizar test_action_ledger.py y test_confirmed_action_outcomes.py.
developers.facebook

PR 7 — Paridad multired
Test de contrato que garantice que Facebook entrega los campos mínimos exigidos a las nueve redes antes de entrar en ranking.

Aplicación a las demás redes

El mismo esqueleto sirve para todas las redes del sistema:

X, Threads, Bluesky, Mastodon: post, autor, respuesta, fecha, duplicado y errores transitorios.

Reddit: subreddit, post, comentario, voto y distinción entre hilo y respuesta.

Pinterest: Pin, tablero, URL canónica y metadatos visuales.

TikTok e Instagram: medios, caption, comentario y restricciones de superficie.

Facebook Pages/Groups: separación explícita entre Page, Group, post, comentario y autor.

La regla debe ser: Facebook aporta campos nativos; el contrato común permanece estable. Así el ranking, ledger, atribución y aprendizaje cross-network no cambian al añadir o corregir un adaptador.
developers.facebook

Fuentes

Repositorio espejo davidpd89/ci-sandbox-tmp, rama main: inventario y contenido de tests existentes de Facebook, Meta, ledger, identidad, colas y guardas.
developers.facebook

airbytehq/airbyte, conector source-facebook-marketing: conftest.py, test_errors.py, test_api.py y test_base_streams.py.

Meta Graph API — manejo de errores: 
https://developers.facebook.com/docs/graph-api/guides/error-handling/

Meta Graph API — eventos y formato temporal: 
https://developers.facebook.com/docs/graph-api/reference/event/
developers.facebook

facebook/facebook-python-business-sdk: 
https://github.com/facebook/facebook-python-business-sdk

sns-sdks/python-facebook: 
https://github.com/sns-sdks/python-facebook

mobolic/facebook-sdk: 
https://github.com/mobolic/facebook-sdk
