# Tests y estandarización en TikTok

Fuente: informe de Perplexity (https://www.perplexity.ai/search/05708917-218a-481f-ab15-910bc5295a71), generado 10/10/2026.

Informe mejorado: pruebas, contratos y fixtures para el adaptador de TikTok
Resumen

El sistema ya tiene una base TikTok considerable en davidpd89/ci-sandbox-tmp: hay pruebas específicas de descubrimiento, crecimiento, interacción móvil, navegación, captcha/challenge, pausas, auditoría de reciprocidad y planes de acción. Por tanto, no propongo duplicar esas suites: la mejora correcta es añadir una capa delgada de contrato normalizado, fixtures offline y regresiones de identidad/fecha/error, reutilizable por todas las redes.
github

He eliminado del informe anterior las recomendaciones demasiado genéricas o no verificadas como código copiable, y he priorizado repos activos, con licencia conocida y piezas concretas: davidteather/TikTok-Api para el modelo de datos y timestamps, pytest-freezer para tiempo determinista, responses para HTTP offline y check-jsonschema para validar fixtures en CI.
github
+3

Hallazgos
Necesidad	Repositorio público	Estado y utilidad	Pieza a aprovechar
Modelo de video, autor, timestamp y métricas	davidteather/TikTok-Api	Activo: último push el 24 de agosto de 2026; 6.680 estrellas; MIT. 
github
	TikTokApi/api/video.py: create_time, statsV2/stats. 
github

Descarga y metadatos TikTok/Douyin	JoeanAmier/TikTokDownloader	Muy activo: push el 22 de septiembre de 2026; 16.646 estrellas; GPL-3.0. 
github
	Referencia de campos y formatos de salida; no copiar código GPL en un repo privado sin revisar compatibilidad de licencia.
SDK asíncrono multiplataforma	TikHub/TikHub-API-Python-SDK	Activo: push el 3 de octubre de 2026; 909 estrellas; Apache-2.0. 
github
	Referencia de contratos API y manejo de respuestas; no depende de un proveedor externo en nuestro sistema.
Tiempo congelado en pytest	
pytest-dev/pytest-freezer
	Mantenido por pytest-dev; proporciona fixture freezer. 
github
	Fixture para fechas relativas, recencia y TTL.
HTTP simulado sin red	
getsentry/responses
	Utilidad madura para mockear requests; requiere Python 3.8+ y requests >= 2.30.0. 
github
	Fixtures de 429, 5xx, timeout y respuestas malformadas.
Validación de esquemas en CI	
python-jsonschema/check-jsonschema
	CLI y hook de pre-commit construido sobre jsonschema. 
github
	Validación automática de tests/fixtures/tiktok/*.json.
Validación JSON Schema en Python	
python-jsonschema/jsonschema
	Implementación de JSON Schema para Python. 
github
	Validación en tests unitarios de los objetos normalizados.

Descartes respecto al informe anterior:

python-humanize/humanize: lo mantengo solo como referencia, no como dependencia obligatoria; los textos relativos de TikTok en español deben tener su propio parser y tests, porque “hace 2 horas” no es un formato estable ni oficial.

factory_boy: útil, pero no es imprescindible para la primera PR; los fixtures JSON estáticos son más auditables y evitan dependencia extra.

requests-mock: lo elimino para evitar dos bibliotecas que resuelven lo mismo; usaremos responses.

TikTokLive: no aplica al objetivo actual de descubrimiento, comentarios y acciones de crecimiento; es para eventos de directos.
github

Contrato normalizado

El contrato debe ser común a todas las redes, con TikTok como adaptador. La clave es separar identidad estable, URL canónica, fecha UTC y métricas tipadas.

python
# Propuesta propia para davidpd89/rrss-davidporto-CODE
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class SocialItem:
    network: Literal["tiktok", "x", "threads", "facebook", "pinterest",
                     "reddit", "bluesky", "mastodon", "instagram"]
    kind: Literal["post", "profile", "comment"]
    external_id: str
    author_handle: str
    author_id: str | None
    canonical_url: str
    created_at: datetime | None
    text: str | None
    metrics: dict[str, int]
    raw: dict

Reglas:

external_id es obligatorio y estable.

author_handle se guarda sin @.

canonical_url es absoluta, HTTPS y sin parámetros de tracking.

created_at es datetime con zona horaria o None; nunca una fecha falsa por defecto.

metrics admite solo enteros no negativos.

raw conserva la respuesta original para reparseo y auditoría.

Para TikTok, añadiríamos campos específicos opcionales:

python
# Propuesta propia para davidpd89/rrss-davidporto-CODE
@dataclass(frozen=True)
class TikTokIdentity:
    author_handle: str
    author_id: str | None = None
    sec_uid: str | None = None
    canonical_profile_url: str | None = None

La deduplicación debe usar, en este orden: author_id > sec_uid > canonical_profile_url > author_handle normalizado en minúsculas.

Código reutilizable tal cual
Timestamp y métricas de TikTok

Este fragmento es relevante porque confirma que TikTok entrega create_time como timestamp y que las métricas pueden llegar en statsV2 o en el campo legacy stats. Es exactamente el tipo de variante que nuestros fixtures deben cubrir.
github

python
# https://github.com/davidteather/TikTok-Api/blob/main/TikTokApi/api/video.py
        self.create_time = datetime.fromtimestamp(timestamp)
        self.stats = data.get("statsV2") or data.get("stats")

Advertencia de integración: no copiar esta línea directamente en producción. datetime.fromtimestamp(timestamp) usa la zona horaria local; nuestro contrato exige UTC. La pieza útil es la detección de statsV2 con fallback a stats, y el hecho de que create_time procede de un timestamp.

Tiempo congelado en pytest

Para fechas relativas como “hace 2 horas”, “ayer” o “hace 3 días”, los tests no deben depender del reloj real. pytest-freezer ofrece el fixture freezer, con move_to() y tick().
github

python
# https://github.com/pytest-dev/pytest-freezer#readme
def test_frozen_date(freezer):
    now = datetime.now()
    time.sleep(1)
    later = datetime.now()
    assert now == later
python
# https://github.com/pytest-dev/pytest-freezer#readme
def test_freezer_methods(freezer):
    freezer.move_to("2022-10-17")
    assert datetime.now() == datetime(2022, 10, 17)
    freezer.tick()
    assert datetime.now() == datetime(2022, 10, 17, 0, 0, 1)
    freezer.tick(delta=12)
    assert datetime.now() == datetime(2022, 10, 17, 0, 0, 13)
HTTP offline y errores

responses permite registrar respuestas HTTP deterministas sin red; su documentación indica que una URL no registrada produce ConnectionError, comportamiento útil para detectar llamadas accidentales en tests offline.
github
+1

python
# https://github.com/getsentry/responses#responses
# using context manager

Para la integración con pytest, la propia documentación remite a pytest-responses, que exporta responses como fixture de pytest.
github

bash
# https://github.com/getsentry/responses#integration-with-unit-test-frameworks
pip install pytest-responses
Validación de fixtures en CI

check-jsonschema puede validar un archivo contra un esquema local y también integrarse como hook de pre-commit.
github

bash
# https://github.com/python-jsonschema/check-jsonschema#readme
check-jsonschema --schemafile schema.json instance.json
text
# https://github.com/python-jsonschema/check-jsonschema#readme
- repo: https://github.com/python-jsonschema/check-jsonschema
  rev: 0.38.2
  hooks:
  - id: check-github-workflows
    args: ["--verbose"]

Para nuestro caso, el hook debe validarse contra schemas/tiktok_normalized.schema.json, no contra el esquema de GitHub Workflows.

Fixtures concretos

Crear tests/fixtures/tiktok/ con estos archivos mínimos:

json
// tests/fixtures/tiktok/post_full.json
{
  "network": "tiktok",
  "kind": "post",
  "external_id": "7412345678901234567",
  "author_handle": "autorfantasia",
  "author_id": "7001234567890123456",
  "sec_uid": "MS4wLjABAAAA_example",
  "canonical_url": "https://www.tiktok.com/@autorfantasia/video/7412345678901234567",
  "created_at": "2026-10-10T13:16:00+00:00",
  "text": "Primer capítulo disponible: una ciudad suspendida sobre las nubes.",
  "metrics": {
    "views": 12500,
    "likes": 842,
    "comments": 63,
    "shares": 121,
    "saves": 210
  },
  "raw": {
    "id": "7412345678901234567",
    "createTime": 1760104560,
    "statsV2": {
      "playCount": "12500",
      "diggCount": "842",
      "commentCount": "63",
      "shareCount": "121",
      "collectCount": "210"
    }
  }
}
json
// tests/fixtures/tiktok/post_legacy_stats.json
{
  "network": "tiktok",
  "kind": "post",
  "external_id": "7412345678901234568",
  "author_handle": "AutorFantasia",
  "author_id": null,
  "sec_uid": null,
  "canonical_url": "https://www.tiktok.com/@autorfantasia/video/7412345678901234568",
  "created_at": "2026-10-10T13:16:00+00:00",
  "text": null,
  "metrics": {
    "views": 100,
    "likes": 10,
    "comments": 1,
    "shares": 0,
    "saves": 0
  },
  "raw": {
    "id": "7412345678901234568",
    "createTime": 1760104560000,
    "stats": {
      "playCount": "100",
      "diggCount": "10",
      "commentCount": "1"
    }
  }
}
json
// tests/fixtures/tiktok/error_challenge.json
{
  "network": "tiktok",
  "kind": "error",
  "error_code": "challenge_detected",
  "recoverable": false,
  "expected_action": "stop_round",
  "raw": {
    "page": "mobile_feed",
    "signal": "captcha_or_challenge"
  }
}
Tests de regresión recomendados
Identidad
python
# tests/test_tiktok_identity_contract.py
# Propuesta propia para davidpd89/rrss-davidporto-CODE
import pytest

from growth.adapters.tiktok.normalize import normalize_identity


@pytest.mark.tiktok
@pytest.mark.contract
@pytest.mark.parametrize(
    ("handle", "expected"),
    [
        ("@autorfantasia", "autorfantasia"),
        ("AutorFantasia", "AutorFantasia"),
        ("autor.fantasia", "autor.fantasia"),
    ],
)
def test_handle_normalization(handle, expected):
    identity = normalize_identity(handle=handle)
    assert identity.author_handle == expected


@pytest.mark.tiktok
@pytest.mark.contract
def test_same_author_is_deduplicated_by_id():
    a = normalize_identity(handle="autorfantasia", author_id="7001")
    b = normalize_identity(handle="AutorFantasia", author_id="7001")
    assert a.dedupe_key() == b.dedupe_key()


@pytest.mark.tiktok
@pytest.mark.contract
def test_missing_sec_uid_does_not_fail():
    identity = normalize_identity(
        handle="autorfantasia",
        author_id="7001",
        sec_uid=None,
    )
    assert identity.sec_uid is None
    assert identity.dedupe_key() == "tiktok:author_id:7001"
Fechas y timestamps
python
# tests/test_tiktok_time_contract.py
# Propuesta propia para davidpd89/rrss-davidporto-CODE
from datetime import datetime, timezone

import pytest

from growth.adapters.tiktok.normalize import normalize_created_at


@pytest.mark.tiktok
@pytest.mark.contract
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1760104560, datetime(2025, 10, 10, 13, 16, tzinfo=timezone.utc)),
        ("2026-10-10T15:16:00+02:00", datetime(2026, 10, 10, 13, 16, tzinfo=timezone.utc)),
        ("2026-10-10T15:16:00Z", datetime(2026, 10, 10, 15, 16, tzinfo=timezone.utc)),
    ],
)
def test_created_at_normalization(value, expected):
    assert normalize_created_at(value) == expected


@pytest.mark.tiktok
@pytest.mark.contract
def test_invalid_date_returns_none():
    assert normalize_created_at(None) is None
    assert normalize_created_at("") is None
    assert normalize_created_at("no-es-fecha") is None

Corrección importante: el ejemplo de epoch debe ajustarse al valor real del fixture. No debe asumirse que 1760104560 corresponde a una fecha concreta sin calcularlo; en la PR, el test debe derivar el valor esperado con datetime.fromtimestamp(value, tz=timezone.utc) o usar un epoch conocido.

Errores y paradas seguras
python
# tests/test_tiktok_error_contract.py
# Propuesta propia para davidpd89/rrss-davidporto-CODE
import pytest

from growth.adapters.tiktok.errors import classify_tiktok_error


@pytest.mark.tiktok
@pytest.mark.contract
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"status_code": 429}, "rate_limited"),
        ({"status_code": 500}, "server_error"),
        ({"signal": "captcha"}, "challenge_detected"),
        ({"signal": "challenge"}, "challenge_detected"),
        ({"profile_visibility": "private"}, "profile_unavailable"),
        ({"body": ""}, "empty_response"),
    ],
)
def test_error_classification(payload, expected):
    assert classify_tiktok_error(payload) == expected


@pytest.mark.tiktok
@pytest.mark.contract
def test_challenge_blocks_actions():
    error = classify_tiktok_error({"signal": "captcha"})
    assert error.recoverable is False
    assert error.should_stop_round is True
Paridad multi-red
python
# tests/test_tiktok_network_parity.py
# Propuesta propia para davidpd89/rrss-davidporto-CODE
import json
from pathlib import Path

import pytest
from jsonschema import validate

FIXTURES = Path("tests/fixtures/tiktok")
SCHEMA = Path("schemas/tiktok_normalized.schema.json")


@pytest.mark.tiktok
@pytest.mark.contract
@pytest.mark.parametrize(
    "fixture_path",
    sorted((FIXTURES / "posts").glob("*.json")),
)
def test_tiktok_post_fixtures_match_contract(fixture_path):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    instance = json.loads(fixture_path.read_text(encoding="utf-8"))
    validate(instance=instance, schema=schema)

jsonschema expone validate para comprobar una instancia contra un esquema.
github

Plan de implementación en PR pequeñas
PR 1 — Esquema y fixtures base

Añadir schemas/tiktok_normalized.schema.json.

Añadir tests/fixtures/tiktok/posts/post_full.json y post_legacy_stats.json.

Añadir tests/test_tiktok_contract.py.

Instalar jsonschema y check-jsonschema solo como dependencias de desarrollo.

Criterio de aceptación: todos los fixtures validan contra el esquema.

PR 2 — Identidad y deduplicación

Añadir TikTokIdentity y dedupe_key().

Añadir fixtures de alias, mayúsculas, @, author_id, sec_uid y URL equivalente.

Crear tests/test_tiktok_identity_contract.py.

Criterio: el mismo autor no genera dos candidatos accionables.

PR 3 — Fechas, timestamps y recencia

Añadir pytest-freezer como dependencia de desarrollo.

Crear fixtures ISO-8601, epoch en segundos y epoch en milisegundos.

Crear tests/test_tiktok_time_contract.py.

Criterio: ninguna fecha relativa depende del reloj real; los posts fuera de ventana no entran en rondas.

PR 4 — Errores y detención segura

Añadir responses o pytest-responses solo si el adaptador hace llamadas HTTP directas.

Crear fixtures de 429, 5xx, timeout, HTML inesperado, challenge, perfil privado y respuesta vacía.

Crear tests/test_tiktok_error_contract.py.

Criterio: un challenge o captcha detiene la ronda y no se registra como “sin candidatos”.

PR 5 — Paridad con el sistema multi-red

Crear tests/test_tiktok_network_parity.py.

Reutilizar los guardas existentes de capacidades, objetivos multi-red, presupuesto y rampa.
github

Criterio: TikTok pasa las mismas invariantes que Bluesky, Mastodon, Threads, Pinterest, Reddit y X.

Riesgos técnicos
Riesgo	Mitigación
TikTok devuelve métricas como cadenas	Convertir a int en la frontera y rechazar valores negativos.
statsV2 y stats coexisten	Preferir statsV2; usar stats solo como fallback, como hace TikTok-Api. 
github

Timestamp interpretado en hora local	Convertir siempre con datetime.fromtimestamp(value, tz=timezone.utc).
Tests frágiles por tiempo real	Usar freezer y reloj inyectado. 
github

Cambios de UI móvil	Mantener tests de UI separados de los tests de contrato.
Dependencia de un scraper externo	Usar repos externos como referencia de formatos; el contrato y los fixtures deben ser propios.
Licencias incompatibles	TikTok-Api es MIT; TikTokDownloader es GPL-3.0, así que no copiar código de este último sin una decisión explícita de licencia. 
github
Fuentes

Repositorio espejo y suite existente: davidpd89/ci-sandbox-tmp/tests.
github

Tests TikTok existentes: test_tiktok_discovery.py, test_tiktok_growth_flow.py, test_tiktok_mobile_interact.py, test_tiktok_captcha_stop.py.
github

Contratos transversales: test_r1_candidate_identity.py, test_multinetwork_target_guards.py, test_network_capabilities.py.
github

davidteather/TikTok-Api, MIT, activo; archivo TikTokApi/api/video.py.
github

JoeanAmier/TikTokDownloader, GPL-3.0, activo.
github

TikHub/TikHub-API-Python-SDK, Apache-2.0, activo.
github

pytest-dev/pytest-freezer
: fixture freezer, move_to() y tick().
github

getsentry/responses
: mockeo de requests, Python 3.8+ y requests >= 2.30.0.
github

python-jsonschema/check-jsonschema
: validación de esquemas en CLI y pre-commit.
github

python-jsonschema/jsonschema
: implementación Python de JSON Schema.
github
