# Tests y estandarización en Pinterest

Fuente: informe de Perplexity (https://www.perplexity.ai/search/efd7b1c1-abe5-4c1e-b859-591dfea7d5c9), generado 10/10/2026.

Investigación: pruebas, contratos y fixtures para el adaptador de Pinterest
Resumen

El espejo ya tiene una base Pinterest considerable —pinterest_growth.py, pinterest_publish.py, pinterest_execute.py, pinterest_scan.py, pinterest_boards.py, pinterest_daily_pins.py, pinterest_api_audit.py y pinterest_profile_audit.py, con tests de crecimiento, programación, respuesta de schedule, SEO, auditoría de API y revalidación tras espera—. Por tanto, la prioridad no es crear un adaptador desde cero, sino añadir una capa de contrato y regresión homogénea que evite duplicar lógica ya probada y cubra los huecos de identidad, fechas, multimedia, errores y idempotencia.
pypi
+1

La referencia técnica más útil es la especificación pública de Pinterest API v5 y su cliente generado, complementada con vcrpy/pytest-recording para fixtures HTTP deterministas y freezegun para fechas.
github
+3

Hallazgos
Hallazgo	Repo / fuente	Qué copiar o reutilizar	Integración en nuestro sistema	Riesgos técnicos	Tests propuestos
Especificación v5 de POST /v5/pins, GET /v5/pins/{pin_id}, PATCH /v5/pins/{pin_id} y errores 400/401/403/404/429	pinterest/api-description	Contratos OpenAPI y patrones de pin_id; generar fixtures mínimos a partir de los esquemas	Crear tests/contracts/pinterest/*.json y un validador que compruebe request/response del adaptador contra esos esquemas	La especificación cambia; fijar versión/commit y regenerar fixtures con CI programado	Contrato de creación, lectura, actualización y error; pin_id inválido; campos desconocidos tolerados
SDK oficial de Pinterest en Python	
pinterest/pinterest-python-sdk
	Modelos de autenticación, manejo de errores y ejemplos de cliente; no copiar como dependencia si el repo ya usa su propio cliente	Usarlo como oráculo de contratos y, si conviene, para comparar serialización de payloads	El SDK está orientado sobre todo a campañas; su cobertura orgánica puede ser parcial	Paridad de nombres de campo entre nuestro adaptador y SDK; errores de OAuth y scopes
Quickstart oficial API v5, OAuth y refresco de token	
pinterest/api-quickstart
	Flujo de autorización, intercambio de código y refresh token en python/src/user_auth.py y access_token.py	Extraer únicamente casos de prueba y nombres de error; mantener nuestra capa http_retry y circuit_breaker existentes	No acoplar el flujo interactivo de navegador a tests unitarios	Token expirado, refresh correcto, refresh rechazado, scope insuficiente, token revocado
Grabación/replay HTTP determinista	
kevin1024/vcrpy
 y 
kiwicom/pytest-recording
	Cassettes YAML, filter_headers: ["authorization"], bloqueo de red y modo rewrite	Añadir pytest-recording a requirements-ci.txt; guardar cassettes en tests/fixtures/pinterest/vcr/	Cassettes con PII, tokens o URLs privadas; deben filtrarse y revisarse	Todas las pruebas de adaptador sin red; aserción de que no se filtra Authorization
Tiempo determinista para caducidad, TTL y ventanas	
spulec/freezegun
	freeze_time, offsets de zona horaria y control de datetime.now	Usarlo en pruebas de schedule, revalidación y envejecimiento de candidatos	utcnow() está obsoleto en Python moderno; preferir datetime.now(timezone.utc)	Fronteras de día, DST, medianoche UTC, timestamp futuro y reloj retrasado
Creación de pines: imagen, carrusel y vídeo	
Pinterest Developers: Pins create
	Estructura de board_id, title, description, link y media_source	Extender el contrato de pinterest_publish.py con tres tipos de pin y preflight por tipo	El vídeo exige registro, subida, sondeo y portada; un 2xx de subida no implica disponibilidad	Imagen válida, carrusel 2–5, vídeo procesado, vídeo sin procesar, portada ausente, URL de destino inválida
Errores y límites de Pinterest	
Pinterest Developers: Error codes
 y 
reports-stats
	Códigos 400, 401, 403, 404 y 429; semántica de rate limit	Conectar con http_retry.py y circuit_breaker.py: 429 y 5xx reintentables; 400/401/403 no reintentables salvo causa transitoria demostrable	Un 401 puede ser engañoso: hay casos documentados de vídeo sin cover_image_url que devuelven 401 en vez de 400	Matriz de errores, backoff, no reintento en error permanente, apertura/cierre de breaker
Identidad y URL canónica de pin	POST /v5/pins devuelve id, board_id, created_at y media; la URL pública es https://www.pinterest.com/pin/{id}/	Normalizador de identidad: pin_id, board_id, URL canónica y huella de contenido	Reutilizar el patrón de candidate_identity.py, test_r1_candidate_identity.py y test_r9_reply_cache_identity.py	Duplicados por URL con parámetros, pin_id numérico como string/int, o alias de tablero	Identidad estable, URL canónica, dedupe por pin_id, dedupe por contenido y colisiones
Fechas de Pinterest	created_at en respuestas de pin; la especificación v5 publica cambios y esquemas actualizados	Parser estricto ISO-8601 con zona horaria	Centralizar en growth_common.py o un nuevo tools/pinterest_time.py; no parsear fechas en cada módulo	Fechas sin zona, milisegundos, formatos RFC 2822 heredados y cambios de esquema	ISO con Z, offset +02:00, sin offset, fecha inválida, epoch numérico rechazado, normalización a UTC
Multimedia de vídeo en cuatro pasos	Guías técnicas de 2026 sobre POST /v5/media, subida prefirmada, sondeo y creación	Máquina de estados: registered -> uploaded -> processing -> succeeded/failed	Añadir contrato de estado y test de máquina de estados en el adaptador	La subida externa puede devolver XML y errores distintos de Pinterest; no tratarla como API JSON normal	Estados válidos, timeout, reintento seguro, fallo permanente, portada obligatoria
Regresiones ya cubiertas en el espejo	tests/test_pinterest_growth.py, test_pinterest_schedule.py, test_pinterest_schedule_response.py, test_pinterest_seo.py, test_pinterest_api_audit.py, test_r7_pinterest_post_wait_revalidation.py	No duplicar growth, schedule básico, SEO ni revalidación tras espera	Los nuevos tests deben importar fixtures y utilidades comunes, no repetir aserciones	Duplicación de fixtures y divergencia de expectativas	Inventario automático: cada fixture nuevo debe declarar el test que lo consume

Fuentes principales: especificación y errores oficiales de Pinterest; repos oficiales de Pinterest; herramientas de testing; evidencia de errores de vídeo y rate limit. El inventario del espejo confirma los módulos y tests Pinterest existentes.
pypi
+12

Contrato mínimo del adaptador

El adaptador debe exponer un contrato independiente del transporte:

python
@dataclass(frozen=True)
class PinterestPinCandidate:
    network: Literal["pinterest"]
    pin_id: str | None
    board_id: str
    canonical_url: str | None
    title: str
    description: str
    destination_url: str | None
    media_kind: Literal["image", "carousel", "video"]
    media_ref: str
    cover_image_url: str | None
    created_at: datetime | None
    payload_hash: str

@dataclass(frozen=True)
class PinterestAdapterResult:
    ok: bool
    pin_id: str | None
    canonical_url: str | None
    created_at: datetime | None
    error_code: str | None
    retryable: bool
    raw_status: int | None

Reglas de contrato:

pin_id siempre se normaliza a str; nunca a int.

canonical_url se construye sólo como https://www.pinterest.com/pin/{pin_id}/; no debe aceptarse una URL de pin no canónica como identidad primaria.

created_at se almacena como datetime consciente de zona horaria en UTC.

media_kind, media_ref y cover_image_url son obligatorios para vídeo; cover_image_url debe exigirse en preflight aunque la API lo documente como opcional, por los casos de error engañoso documentados.
pinterest

retryable debe derivarse de una tabla explícita: 429 y 5xx son reintentables; 400, 401, 403 y 404 no lo son por defecto.
developers.pinterest
+1

Fixtures recomendados

Crear tests/fixtures/pinterest/ con estos grupos:

pin_created_image.json: respuesta 201/200 con id, board_id, created_at, media y URL de imagen.

pin_created_video.json: respuesta con media_id, cover_image_url y estado de procesamiento correcto.

media_processing_pending.json, media_processing_succeeded.json, media_processing_failed.json: máquina de estados de vídeo.

error_400_invalid_body.json, error_401_token.json, error_403_denied.json, error_404_board.json, error_429_rate_limit.json: errores canónicos.

oauth_token_expired.json y oauth_refresh_success.json: refresco y caducidad.

board_list_mixed.json: tableros propios, colaborativos, archivados y sin permiso de escritura.

pin_list_pagination.json: bookmark, última página, página vacía y cursor inválido.

identity_duplicates.json: mismo pin_id con URL con parámetros, mayúsculas y trailing slash.

Los fixtures HTTP deben usar pytest-recording con filter_headers: ["authorization"]; VCR.py guarda interacciones en cassettes y permite pruebas rápidas, offline y deterministas.
github
+1

Casos límite obligatorios
Identidad

pin_id vacío, nulo, numérico, con espacios y con prefijo no estándar.

Misma URL con ?utm_source=..., #fragment, barra final y dominio móvil.

Doble creación con el mismo payload_hash: la segunda debe ser skip idempotente, no un segundo pin.

Cambio de tablero con el mismo contenido: debe registrarse como nueva acción sólo si la política lo permite.

Fechas

2026-10-10T12:00:00Z.

2026-10-10T14:00:00+02:00.

2026-10-10T12:00:00 sin zona: rechazar o asumir UTC de forma explícita, nunca mezclar criterios.

Fecha futura, fecha muy antigua, epoch numérico y cadena vacía.

Cambio de día a las 00:00 UTC frente a medianoche de Madrid.

Revalidación después de espera: un pin creado hace 1 minuto no debe tratarse igual que uno creado hace 48 horas.

freezegun permite congelar datetime.now, date.today, time.time y funciones relacionadas, por lo que es adecuado para estas fronteras temporales.
pypi
+1

Publicación

Imagen desde URL pública.

Imagen local con subida.

Carrusel con 2 imágenes, 5 imágenes, 1 imagen y 6 imágenes.

Vídeo registrado pero no procesado.

Vídeo procesado sin portada.

Vídeo con portada y media_id.

destination_url ausente, http://, URL con redirección y URL inválida.

Tablero inexistente, archivado, sin permisos o perteneciente a otra cuenta.

Errores y resiliencia

429 con Retry-After: un reintento, backoff y registro del motivo.

429 sin Retry-After: backoff exponencial acotado.

401: refresco una vez; si persiste, marcar cuenta como requiere reconexión.

403: no reintentar automáticamente.

404: invalidar candidato y eliminarlo de la cola.

5xx: reintento limitado y apertura de breaker.

JSON malformado, respuesta vacía, HTML en lugar de JSON y campo id ausente.

Respuesta 2xx sin pin_id: tratarla como resultado ambiguo, no como éxito confirmado.

Aplicación a todas las redes

Estos contratos no deben ser exclusivos de Pinterest. La misma arquitectura debe aplicarse a X, Threads, Facebook, Instagram, Reddit, Bluesky, Mastodon y TikTok:

Concepto Pinterest	Equivalente homogéneo
pin_id	object_id normalizado por red
URL pin/{id}	canonical_url por red
board_id	container_id o destino de publicación
created_at	created_at UTC consciente de zona horaria
Imagen / carrusel / vídeo	media_kind y media_ref
429 / 401 / 403	Tabla común de errores y retryable
Dedupe por payload_hash	Dedupe universal de acciones
Revalidación tras espera	Confirmación diferida común

Así, PinterestPinCandidate puede convertirse en una especialización de un SocialCandidate común, sin que Pinterest pierda sus particularidades de tablero, carrusel y procesamiento de vídeo.

Plan de implementación en PR pequeñas
PR 1 — Contrato y tipos

Añadir tools/pinterest_contract.py con PinterestPinCandidate y PinterestAdapterResult.

Añadir validadores de pin_id, URL canónica, media_kind y fechas UTC.

Tests: tests/test_pinterest_contract.py.

No tocar publicación ni ejecución.

PR 2 — Fixtures HTTP offline

Añadir pytest-recording y vcrpy a CI.

Crear tests/fixtures/pinterest/vcr/ con cassettes filtrados.

Tests: crear pin de imagen, leer pin, error 429 y error 401 sin red.

Añadir guard de que ningún cassette contiene Authorization.

PR 3 — Identidad y dedupe

Reutilizar candidate_identity.py y payload_hash.

Normalizar URL de pin y comparar por pin_id + hash.

Tests: duplicados, URL con parámetros, pin_id numérico y colisiones.

PR 4 — Fechas y schedule

Crear tools/pinterest_time.py con parser estricto ISO-8601.

Usar freezegun en test_pinterest_schedule* y revalidación.

Tests: ISO con Z, offset, sin zona, fecha futura, DST y medianoche UTC.

PR 5 — Matriz de errores

Integrar la tabla de errores con http_retry.py y circuit_breaker.py.

Tests: 400, 401, 403, 404, 429, 500, 503, JSON inválido y respuesta vacía.

Añadir aserción de que 401 dispara como máximo un refresco.

PR 6 — Multimedia y vídeo

Añadir máquina de estados registered -> uploaded -> processing -> succeeded/failed.

Exigir cover_image_url en preflight para vídeo.

Tests: carrusel 2–5, vídeo sin procesar, vídeo sin portada y fallo de subida externa.

PR 7 — Paridad multired

Extraer SocialCandidate, AdapterResult, canonical_url, created_at y retryable a un módulo común.

Migrar Pinterest primero; después adaptar Bluesky, Mastodon, X, Threads, Facebook, Instagram, Reddit y TikTok.

Tests de paridad: cada red debe pasar el mismo suite de identidad, fecha, error y dedupe.

Recomendación

Implementar primero PR 1 + PR 2 + PR 3: contrato, fixtures offline e identidad. Son la base que evita duplicar los tests Pinterest existentes y permite extender después a las demás redes sin reescribir adaptadores. La especificación oficial de Pinterest y api-description deben usarse como fuente de contratos; vcrpy, pytest-recording y freezegun como infraestructura de pruebas; y los tests actuales del espejo como límite claro de lo que no debe duplicarse.
pypi
+5

Fuentes

Repositorio espejo y tests existentes: davidpd89/ci-sandbox-tmp — tests/ y tools/.
pypi
+1

Pinterest API v5, creación de pines: 
https://developers.pinterest.com/docs/api/v5/pins-create/
developers.pinterest

Códigos de error de Pinterest: 
https://developers.pinterest.com/docs/reference/error-codes/
developers.pinterest

Rate limit en API v5: 
https://developers.pinterest.com/docs/api/v5/reports-stats/
developers.pinterest

Especificación OpenAPI de Pinterest: https://github.com/pinterest/api-description
github

SDK oficial Python: 
https://github.com/pinterest/pinterest-python-sdk
github

Quickstart oficial con OAuth: 
https://github.com/pinterest/api-quickstart
github

VCR.py: 
https://github.com/kevin1024/vcrpy
github

pytest-recording: 
https://github.com/kiwicom/pytest-recording
github

freezegun: 
https://github.com/spulec/freezegun
github

Caso documentado de vídeo sin portada que devuelve 401: 
https://community.pinterest.biz/t/401-unauthorized-on-v5-pin-creation-with-video-id-but-image-url-works/39679
pinterest
