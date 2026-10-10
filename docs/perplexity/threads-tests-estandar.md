# Tests y estandarización en Threads

Fuente: informe de Perplexity (https://www.perplexity.ai/search/058b043a-702c-44ed-ab62-696d88474b94), generado 10/10/2026.

Pruebas, contratos y fixtures para el adaptador de Threads — informe revisado

He revisado el informe contra el código real de davidpd89/ci-sandbox-tmp. La corrección más importante es que tools/candidate_identity.py todavía no admite Threads: sólo valida identidades de Bluesky y Mastodon. Por tanto, la propuesta correcta es ampliar ese módulo con un contrato explícito de Threads, no afirmar que ya existe. También he eliminado los SDK no oficiales de Threads como dependencias recomendables: están archivados, reversos o no aplican al adaptador oficial basado en graph.threads.net.
developers.facebook
+1

Resumen

El adaptador de Threads debe probar cuatro capas: contrato HTTP, identidad y referencia remota, ciclo de publicación en dos pasos y política de errores/colas. El código existente ya cubre parte del ciclo con tools/threads_api.py, pero necesita fixtures canónicos, mock HTTP determinista y tests de regresión para los fallos que pueden causar duplicados o acciones perdidas.
developers.facebook
+1

Threads publica mediante creación de contenedor y después threads_publish; una respuesta usa reply_to_id. El punto crítico es que un fallo después de crear el contenedor no permite reintentar a ciegas, porque la respuesta puede haberse publicado.
outstand
+1

Hallazgos verificables
Área	Estado actual en el repo	Referencia pública recomendada	Qué añadir
Mock HTTPX	No hay un fake central de Threads; los tests existentes prueban funciones y flujos concretos.	lundberg/respx, activo: último push 2026-07-21, 838 estrellas, BSD-3-Clause.	ThreadsAPIFake con respx, rutas por endpoint y respuestas JSON versionadas.
Grabación HTTP	No hay cassettes ni grabaciones.	kevin1024/vcrpy, activo: último push 2026-09-15, 3.019 estrellas, MIT.	Cassettes anonimizados sólo como regresión, nunca como contrato primario.
Contrato API	threads_api.py define BASE, api_get, api_post, publish_reply y check_reply_text.	
Meta Threads API
. 
developers.facebook
	Esquema JSON y tests de campos obligatorios por endpoint.
Publicación	publish_reply() ya separa fallo de creación y fallo de publicación.	
Outstand: Threads API failure modes
. 
outstand
	Máquina de estados y test de idempotencia tras timeout.
Identidad	candidate_identity.py sólo admite bluesky y mastodon.	Código propio del repo.	Añadir threads con user_id, username y post_id; sin fallbacks entre redes.
Reintentos	http_retry.py reintenta sólo GET, 5xx, timeouts y cortes; no escrituras ni 429.	Código propio del repo.	Mantener esa política; añadir clasificador específico de errores de Threads.
Fechas	threads_api.py usa timestamp de la API y fechas ISO para el token, pero no hay normalizador central de fechas de candidatos.	Documentación Meta y código propio.	Normalizar a UTC y validar zona horaria antes de persistir.
Fuzzing de contrato	No hay fuzzing dirigido al adaptador.	schemathesis/schemathesis, activo: último push 2026-10-10, 3.658 estrellas, MIT.	Fuzzing sólo contra un servidor local/OpenAPI propio; no contra la API real de Meta.
Límites	Existen test_threads_scale.py, test_volume_ramp.py y test_volume_shape.py.	Documentación y código propio.	Separar presupuesto de publicaciones y respuestas; no inventar límites si no están configurados en el sistema.

respx es la mejor base para pruebas offline porque está diseñado específicamente para HTTPX, admite patrones de petición y efectos secundarios, y sigue activo. VCR.py complementa, pero debe usarse con cautela: los cassettes pueden quedar obsoletos y no deben sustituir al contrato explícito. schemathesis es útil para fuzzing de un OpenAPI propio, no para atacar Meta directamente.
developers.facebook
+1

Código existente que conviene reutilizar tal cual
1. Publicación de respuesta y separación de fallos

Este bloque ya resuelve el caso más peligroso: distinguir entre “no se creó el contenedor” y “puede haberse publicado”. No debe duplicarse ni reescribirse; los tests deben rodearlo.

python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/threads_api.py
REPLY_MAX = 500


def api_post(path, token, **params):
    return mc.graph_post(BASE, path, token, **params)


class ReplyNotCreated(RuntimeError):
    """Fallo ANTES de publicar: no hay respuesta en Threads, se puede reintentar o usar el navegador."""


def check_reply_text(text):
    text = (text or "").strip()
    if not text:
        raise ValueError("respuesta vacia")
    if len(text) > REPLY_MAX:
        raise ValueError(f"{len(text)} caracteres (max {REPLY_MAX})")
    return text


def publish_reply(token, user_id, reply_to_id, text):
    """Responde a `reply_to_id` (ID de la API). Crea el contenedor y lo publica; un fallo al crear
    lanza ReplyNotCreated (nada publicado). Si falla el publicado se lanza RuntimeError normal:
    puede haberse publicado, no reintentar a ciegas."""
    text = check_reply_text(text)
    try:
        container = api_post(f"{user_id}/threads", token, media_type="TEXT", text=text, reply_to_id=reply_to_id)
    except RuntimeError as exc:
        raise ReplyNotCreated(str(exc)) from None
    published = api_post(f"{user_id}/threads_publish", token, creation_id=container["id"])
    return published["id"]

Tests que faltan alrededor de este código:

python
# Propuesto: tests/test_threads_publish_contract.py
import pytest

from tools.threads_api import ReplyNotCreated, check_reply_text, publish_reply


def test_text_vacio_se_rechaza():
    with pytest.raises(ValueError):
        check_reply_text("   ")


def test_texto_de_501_caracteres_se_rechaza():
    with pytest.raises(ValueError, match="max 500"):
        check_reply_text("a" * 501)


def test_texto_de_500_caracteres_se_acepta():
    assert check_reply_text("a" * 500) == "a" * 500


def test_fallo_al_crear_contenedor_no_reintenta_publicacion(fake_threads):
    fake_threads.fail_create_container()
    with pytest.raises(ReplyNotCreated):
        publish_reply("token", "user", "post", "Hola")
    assert fake_threads.publish_calls == []


def test_fallo_en_publish_no_reintenta_automaticamente(fake_threads):
    fake_threads.success_create_container()
    fake_threads.fail_publish()
    with pytest.raises(RuntimeError):
        publish_reply("token", "user", "post", "Hola")
    assert fake_threads.publish_calls == 1
2. Reintentos seguros: sólo lecturas

http_retry.py ya tiene la política correcta para un sistema multired: no reintenta escrituras porque podrían duplicar acciones, y deja el 429 a la lógica de cuota de cada cliente. Ese principio debe conservarse también en Threads.

python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/http_retry.py
"""Reintentos de GET ante fallos transitorios (03/10).

Una ronda programada sin supervision no puede morir por un 500 puntual de la API (visto el
03/10: `listRecords` devolvio un Internal Server Error y el `prepare` entero cayo en 5 s).
Solo se reintentan LECTURAS (idempotentes): 5xx, timeouts y cortes de conexion, con espera
creciente y algo de azar. Los 429 NO se reintentan aqui (los gestiona cada cliente con su
logica de cuota) y las escrituras nunca (podrian duplicar una accion).
"""
import random
import time

import requests

TRANSIENT_STATUS = {500, 502, 503, 504}
DEFAULT_DELAYS = (1.5, 4.0, 9.0)


def get_with_retry(url, *, get=None, delays=DEFAULT_DELAYS, sleeper=time.sleep, rng=random, **kwargs):
    """requests.get con hasta len(delays) reintentos. Devuelve la ultima respuesta; si hubo
    excepcion en todos los intentos, relanza la ultima."""
    get = get or requests.get
    last_exc = None
    for attempt in range(len(delays) + 1):
        try:
            response = get(url, **kwargs)
            if response.status_code not in TRANSIENT_STATUS or attempt == len(delays):
                return response
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt == len(delays):
                raise
        sleeper(delays[attempt] * rng.uniform(0.8, 1.3))
    raise last_exc  # inalcanzable salvo bucle vacio

Regla que debe añadirse al contrato de Threads: get_with_retry sirve para me, me/threads, {post}/replies y consultas de estado; publish_reply y cualquier otra escritura no deben pasar por un reintento genérico.

3. Identidad: ampliar, no duplicar

El módulo actual es una buena base porque rechaza identificadores inseguros y no mezcla redes. Sin embargo, no soporta Threads; hay que extender AUTHOR_FIELD, resolve_author() y resolve_post_ref().

python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/candidate_identity.py
"""R1 / F11: identidad mínima explícita de candidatos, sin dependencias externas.

Solo se admiten dos esquemas verificados en el código del escáner API:
Mastodon (`acct`) y Bluesky (`handle`). Otras redes quedan fuera
hasta comprobar sus datos y conectarlas en sus propios ejecutores.
NO convierte un id de post, nombre o DID en un usuario/handle.
Los adaptadores deben llamar a resolve_author antes de tomar acciones sobre
una cuenta. Una identidad inválida se omite con alerta, nunca como None.
"""
from __future__ import annotations

from collections.abc import Mapping
import re

AUTHOR_FIELD = {
    "bluesky": "handle",  # bluesky_growth_scan.py _build_output: shortlist.append
    "mastodon": "acct",  # mastodon_growth_scan.py _build_output: shortlist.append
}

# IDs de posición que genera el scanner, NO IDs remotos de Mastodon.
_SCAN_ORDINAL = re.compile(r"^[GM][0-9]{3,}-P[0-9]+$", re.I)


def is_scan_ordinal(value):
    return isinstance(value, str) and _SCAN_ORDINAL.fullmatch(value) is not None


class CandidateIdentityError(ValueError):
    """No existe un identificador seguro de destinatario para la red."""


def resolve_author(network: str, candidate: Mapping) -> str:
    """Resuelve la identidad exacta de esta red, o falla con motivo legible.

    Sin fallback entre redes: un 'handle' auxiliar en Mastodon no sustituye
    a 'acct', y un 'acct' no sustituye al handle de Bluesky.
    Esta función no normaliza handles según convenciones de cada red.
    """
    if network not in AUTHOR_FIELD:
        raise CandidateIdentityError(f"red_no_admitida:{network}")
    if not isinstance(candidate, Mapping):
        raise CandidateIdentityError(f"{network}:candidato_no_es_mapa")
    field = AUTHOR_FIELD[network]
    value = candidate.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CandidateIdentityError(f"{network}:falta_{field}")
    author = value.strip()
    if "\n" in author or "\r" in author:
        raise CandidateIdentityError(f"{network}:{field}_contiene_salto_de_linea")
    if network == "bluesky":
        handle_pattern = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?"
        if author.casefold() == "handle.invalid" or not re.fullmatch(handle_pattern, author.casefold()):
            raise CandidateIdentityError("bluesky:handle_invalido")
    elif not re.fullmatch(r"[a-z0-9_][a-z0-9_.-]*(?:@[a-z0-9.-]+)?", author.casefold()) or len(author) > 320:
        raise CandidateIdentityError("mastodon:acct_invalido")
    return author.casefold()


def resolve_post_ref(network, post):
    """Referencia remota estable, no el ID ordinal del scan."""
    if network not in AUTHOR_FIELD or not isinstance(post, Mapping):
        raise CandidateIdentityError("red_o_post_invalido")
    if network == "bluesky":
        uri = post.get("uri")
        if not isinstance(uri, str) or not re.fullmatch(r"at://did:[a-z0-9]+:[A-Za-z0-9._:%-]+/app\.bsky\.feed\.post/[A-Za-z0-9._~-]+", uri):
            raise CandidateIdentityError("bluesky:uri_post_invalida")
        return uri
    status_id = post.get("status_id")
    if isinstance(status_id, bool) or not isinstance(status_id, (str, int)) or not str(status_id).strip():
        raise CandidateIdentityError("mastodon:status_id_invalido")
    value = str(status_id)
    if len(value) > 256 or any(ch.isspace() for ch in value) or is_scan_ordinal(value):
        raise CandidateIdentityError("mastodon:status_id_invalido")
    return value

Ampliación propuesta, sin copiar código de terceros:

python
# Propuesto: parche mínimo para tools/candidate_identity.py
AUTHOR_FIELD = {
    "bluesky": "handle",
    "mastodon": "acct",
    "threads": "username",
}


def resolve_author(network: str, candidate: Mapping) -> str:
    # ... conservar el código actual ...
    if network == "threads":
        if not re.fullmatch(r"[a-z0-9._]{1,30}", author.casefold()):
            raise CandidateIdentityError("threads:username_invalido")
    return author.casefold()


def resolve_post_ref(network, post):
    # ... conservar el código actual ...
    if network == "threads":
        post_id = post.get("id")
        if isinstance(post_id, bool) or not isinstance(post_id, (str, int)):
            raise CandidateIdentityError("threads:post_id_invalido")
        value = str(post_id).strip()
        if not value or len(value) > 256 or any(ch.isspace() for ch in value):
            raise CandidateIdentityError("threads:post_id_invalido")
        return value

Tests de identidad Threads:

python
# Propuesto: tests/test_threads_candidate_identity.py
import pytest

from tools.candidate_identity import CandidateIdentityError, resolve_author, resolve_post_ref


@pytest.mark.parametrize(
    "candidate",
    [
        {"username": "davidporto"},
        {"username": "David.Porto"},
        {"username": "david_porto"},
    ],
)
def test_username_threads_valido(candidate):
    assert resolve_author("threads", candidate) == candidate["username"].casefold()


@pytest.mark.parametrize(
    "candidate",
    [
        {},
        {"username": ""},
        {"username": "  "},
        {"username": "david porto"},
        {"username": "david\nporto"},
        {"username": "@davidporto"},
        {"username": "x" * 31},
    ],
)
def test_username_threads_invalido(candidate):
    with pytest.raises(CandidateIdentityError):
        resolve_author("threads", candidate)


def test_post_id_valido():
    assert resolve_post_ref("threads", {"id": "179284402"}) == "179284402"


@pytest.mark.parametrize("post", [{}, {"id": ""}, {"id": "   "}, {"id": "12 34"}, {"id": True}])
def test_post_id_invalido(post):
    with pytest.raises(CandidateIdentityError):
        resolve_post_ref("threads", post)
Contrato de fixtures

Crear tests/fixtures/threads/ con archivos pequeños, deterministas y sin datos personales:

json
// tests/fixtures/threads/container_created.json
{
  "id": "threads_container_1",
  "status": "IN_PROGRESS"
}
json
// tests/fixtures/threads/container_ready.json
{
  "id": "threads_container_1",
  "status": "FINISHED"
}
json
// tests/fixtures/threads/container_error.json
{
  "id": "threads_container_1",
  "status": "ERROR",
  "error_message": "The container failed to complete the publishing process."
}
json
// tests/fixtures/threads/publish_success.json
{
  "id": "threads_published_1"
}
json
// tests/fixtures/threads/reply_candidate.json
{
  "id": "threads_post_1",
  "text": "¿Qué novelas de fantasía española recomendáis para este otoño?",
  "username": "lector_fantasia",
  "timestamp": "2026-10-10T10:15:00+0000",
  "permalink": "https://www.threads.com/@lector_fantasia/post/threads_post_1"
}

La fecha debe normalizarse antes de guardarla. El formato +0000 es válido en muchos contextos, pero el almacén interno debería usar UTC ISO-8601 con Z o +00:00, y conservar el original sólo como evidencia.

Fake de Threads con respx

respx permite definir rutas y respuestas sin red. Este es un esqueleto propuesto; no copia código de terceros, sólo usa su API pública.

python
# Propuesto: tests/fakes/threads_api_fake.py
from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

FIXTURES = Path(__file__).parents[1] / "fixtures" / "threads"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ThreadsAPIFake:
    def __init__(self) -> None:
        self.create_calls = 0
        self.publish_calls = 0
        self.fail_create_container = False
        self.fail_publish = False
        self.router = respx.mock(base_url="https://graph.threads.net/v1.0")
        self._register()

    def _register(self) -> None:
        @self.router.post("/me/threads")
        def create_container(request: httpx.Request) -> httpx.Response:
            self.create_calls += 1
            if self.fail_create_container:
                return httpx.Response(500, json={"error": {"message": "container creation failed"}})
            return httpx.Response(200, json=load("container_created.json"))

        @self.router.post("/me/threads_publish")
        def publish_container(request: httpx.Request) -> httpx.Response:
            self.publish_calls += 1
            if self.fail_publish:
                return httpx.Response(500, json={"error": {"message": "publish failed"}})
            return httpx.Response(200, json=load("publish_success.json"))

Este fake debe usarse con respx como dependencia de test, no en producción. La ventaja frente a mocks manuales es que valida método, ruta y parámetros, y permite reproducir el mismo escenario en todas las redes.

Casos límite obligatorios
Identidad

username vacío, con espacios, con @, con saltos de línea o demasiado largo.

user_id y post_id como int, str, None, booleano o ID ordinal del escáner.

Mismo username con distinto user_id: no deben colisionar.

Mismo user_id con username cambiado: la identidad operativa no debe romperse.

Permalink con parámetros de seguimiento: se guarda URL canónica, pero la clave de dedupe es post_id.

Fechas

2026-10-10T10:15:00+0000 se normaliza a 2026-10-10T10:15:00+00:00.

2026-10-10T12:15:00+02:00 se normaliza a 2026-10-10T10:15:00+00:00.

Fecha sin zona horaria: rechazar o marcar como invalid_timestamp; nunca asumir UTC silenciosamente.

Fecha futura: rechazar como dato corrupto.

Fecha con milisegundos: aceptar y normalizar sin perder precisión.

Texto y respuesta

Texto vacío o sólo espacios.

Exactamente 500 caracteres.

501 caracteres.

Emoji al final: no debe romper el recorte ni el recuento.

URL larga: no debe truncarse a mitad.

Mención o hashtag: debe conservarse íntegro.

Pregunta en un seguimiento: el código actual la rechaza salvo allow_question; ese comportamiento debe tener test de regresión.

Publicación

Creación de contenedor falla: ReplyNotCreated, cero llamadas a threads_publish.

threads_publish falla: una sola llamada, sin reintento automático.

Timeout entre creación y publicación: estado unknown, no failed; requiere comprobación posterior.

Contenedor en IN_PROGRESS: no publicar.

Contenedor en FINISHED: publicar una vez.

Contenedor en ERROR o EXPIRED: no reintentar publicación.

Respuesta a un post eliminado o sin acceso: skipped, con motivo auditado.

Errores típicos y clasificación
Error	Clase	Política
5xx al leer respuestas	Transitorio	get_with_retry()
Timeout o corte de conexión al leer	Transitorio	get_with_retry()
429	Cuota	No reintento genérico; el planificador aplica espera/presupuesto
Token inválido o expirado	Terminal	Renovación o parada controlada; sin reintento de escritura
Fallo al crear contenedor	Recuperable	Puede reintentarse como nueva creación
Fallo en threads_publish	Desconocido/riesgo de duplicado	No reintento automático; conciliar estado
Contenedor ERROR	Terminal	Marcar fallo y registrar causa
Contenedor EXPIRED	Terminal	Descartar y auditar
Post eliminado o privado	Terminal para esa acción	skipped
Texto vacío o >500	Validación previa	No llamar a la API

La documentación oficial de Meta describe errores de publicación y estados de contenedor; por eso la clasificación debe basarse en el par status + error_message, no sólo en el código HTTP.
outstand

Plan de PR pequeñas

PR 1 — Fixtures y esquema: añadir tests/fixtures/threads/, tests/contracts/test_threads_contract.py y validación de campos obligatorios.

PR 2 — Fake respx: añadir tests/fakes/threads_api_fake.py, respx a dependencias de test y tests de publish_reply().

PR 3 — Identidad Threads: extender candidate_identity.py con threads, username y post_id; añadir tests de casos límite.

PR 4 — Fechas: crear tools/time_normalization.py o añadir funciones a growth_common.py; tests de UTC, DST, milisegundos y fechas inválidas.

PR 5 — Estados de publicación: añadir container_status, published_id, attempts y error_class al ledger/cola; tests de idempotencia.

PR 6 — Errores: clasificar errores de Threads y conectar con circuit_breaker.py; garantizar que las escrituras no se reintentan automáticamente.

PR 7 — Regresión de fuentes: ampliar test_threads_sources.py con duplicados, posts propios, antigüedad, perfiles inválidos y URLs con parámetros.

PR 8 — Paridad multired: parametrizar identidad, fechas, deduplicación y errores para X, Bluesky, Mastodon, Facebook, Instagram, Pinterest, Reddit y TikTok.

Correcciones respecto al informe anterior

Eliminado: recomendar junhoyeo/threads-py o dmytrostriletskyi/threads-net como referencia operativa. El primero está archivado y el segundo es un wrapper no oficial; no deben entrar en el sistema.

Eliminado: vcrpy-unittest, porque está archivado desde 2020.

Corregido: candidate_identity.py no admite Threads hoy; hay que ampliarlo.

Corregido: los límites concretos de 250 publicaciones y 1.000 respuestas no deben hardcodearse como contrato del sistema sin confirmarlos en la configuración vigente y en la documentación oficial; deben ser parámetros de presupuesto.

Añadido: schemathesis para fuzzing de un contrato OpenAPI propio, no contra la API real de Meta.

Añadido: código exacto y URLs de origen de las piezas ya existentes que deben protegerse con tests.

Fuentes

Meta, Threads API: 
https://developers.facebook.com/documentation/threads
developers.facebook

Meta, Threads API Troubleshooting: 
https://developers.facebook.com/documentation/threads/troubleshooting

Outstand, Threads API: posting, replies, rate limits and failure modes: 
https://www.outstand.so/blog/threads-api
outstand

Postproxy, Post to Threads via API: 
https://postproxy.dev/blog/how-to-post-to-threads-via-api/
postproxy

lundberg/respx: https://github.com/lundberg/respx

lundberg/pytest-httpx2: https://github.com/lundberg/pytest-httpx2

kevin1024/vcrpy: https://github.com/kevin1024/vcrpy

schemathesis/schemathesis: https://github.com/schemathesis/schemathesis

davidpd89/ci-sandbox-tmp, tools/threads_api.py: https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/threads_api.py

davidpd89/ci-sandbox-tmp, tools/candidate_identity.py: https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/candidate_identity.py

davidpd89/ci-sandbox-tmp, tools/http_retry.py: https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/http_retry.py
