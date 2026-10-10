# CI 61 — antigüedad de posts: ventanas comunes y telemetría

Revisión: 10-10-2026. Rama: research/51-recent-post-age-parity.
Solo observabilidad de la edad del POST DESTINO: no se ejecutan acciones sociales.

## Problema

La política de antigüedad del post destino ya existe en el repositorio privado
y en PR #8 del espejo, pero no había distribución agregada común 24/72/168 h
en el informe diario, ni distinción explícita entre desconocido y plan ausente.

## Alternativas

Se compararon dateparser, python-dateutil, Arrow y datetime de CPython 3.11;
el detalle de actividad, dependencias y compatibilidad está en la tabla inferior.

## Licencias y procedencia

Fuente primaria: https://github.com/python/cpython
Fecha de consulta: 2026-10-10
Licencia SPDX: Python-2.0
Referencia inmutable: https://github.com/python/cpython/releases/tag/v3.11.14

CPython stdlib es la opción incorporada; no se copia código de las otras
bibliotecas. Para los repositorios públicos comparados, consultar enlaces de
SHA, autores y licencias en la tabla del mismo documento.

## Decisión

Añadir medidor offline sin un segundo gate, manteniendo la autorización
en PR #8 y post_age_policy.py del privado. No requiere librerías externas.

## Pruebas

La suite sintética tests/test_post_age_distribution.py y los dos jobs offline
de GitHub Actions verifican límites y procedencia. Comprobar el HEAD actual,
no una ejecución de un commit anterior.

## Retirada

Borrar el hook en tools/daily_review.py, el módulo y su suite; no hay migración.


## Contexto comprobado

Se comparó el espejo con el repo privado davidpd89/rrss-davidporto-CODE
(rama integracion/crecimiento-2026-10), concretamente:
- tools/post_age_policy.py (blob 0c9f99fe12bd8447dfcfbe11dfb890b44e071852);
- tools/conversation_turn_policy.py (blob 3faa3bbb590cf4fbdb9cb9972ff87c16557e8e23);
- tests/test_post_age_policy.py y tests/test_pr153_post_age_audit.py;
- tools/daily_review.py del espejo.

La base de este espejo no tiene post_age_policy.py, pero [PR #8](https://github.com/davidpd89/ci-sandbox-tmp/pull/8)
ya introduce la regla común y la integra en nueve ejecutores, con propagación
de fechas en planes. En el repositorio privado ya existe la política.
[PR #62](https://github.com/davidpd89/ci-sandbox-tmp/pull/62)
aborda los orígenes fiables de fecha. **No duplicar** en #61 ese trabajo:
esta PR agrega la medición, sin ser un segundo filtro de autorización.

El código privado establece límites distintos de las ventanas de observación:
texto 3 días; follow-up 7 días; boost/repost 7 días; reacciones 21 días.
No se altera ese criterio; la decisión de escritura la toma el gate común.

## Investigación pública y elección (10-10-2026)

| Alternativa | SHA / actividad comprobada | Licencia y dependencias | Python 3.11/Windows | Resultado |
| --- | --- | --- | --- | --- |
| [dateparser](https://github.com/scrapinghub/dateparser/commit/fed9cf94e9d8a1128b396f01ca66f4a303f03ee4) | fed9cf94, 05-10-2026, PyPI 1.4.3 de 03-09-2026 | BSD-3-Clause; añade dependencias y parsing natural | Wheel universal, compatible | No: demasiado tolerante para fuente de API |
| [python-dateutil](https://github.com/dateutil/dateutil/commit/2642afacc33fb839c404b75b230fff58b79793f2) | 2642afac, 26-09-2026, PyPI 2.9.0.post0 | BSD-3-Clause / Apache-2.0 según contribución; six | Compatible | No: la stdlib cubre ISO/epoch |
| [Arrow](https://github.com/arrow-py/arrow/commit/2224255c4acc594d734cef0bbc83360452a67983) | 2224255c, 30-04-2026 | Apache-2.0, dateutil; actividad espaciada | Compatible | No: sobrecoste innecesario |
| datetime (stdlib) + política privada | Python 3.11 y blob oficial arriba | PSF y código propio, cero pip nuevo | Compatible | **Elegido** |

No se ha copiado código de proyectos públicos, por lo que no hay nuevas
licencias que redistribuir. Se reutilizan los esquemas y convenciones del
código privado; no se introduce una dependencia nueva ni un nuevo gate.

## Entrega y contratos

- tools/post_age_distribution.py: calcula de forma homogénea en nueve redes
  las ventanas acumuladas e inclusivas de 24, 72 y 168 horas; rangos disjuntos
  0–24, (24–72], (72–168], >168 y clases unknown/future/conflict.
  **Excluye acciones sobre perfiles** (`follow`, `follow_external`, `followback`,
  `unfollow`) del denominador de posts y las cuenta aparte. Esto evita que un
  plan Instagram compuesto solo por follows genere falsos «posts sin fecha».
- Procedencia conservadora revisada: en **acciones de planes** solo se aceptan
  target_created_at/post_created_at; los campos genéricos de post/record/status/media
  (también Reddit created_utc y TikTok create_time) se leen **solo en payloads
  sin acción** declarados source_kind=post. La marca source_kind por sí sola NO
  acredita el objetivo si hay kind de acción. El campo created_at de una ACCIÓN,
  indexedAt, observed_at, queued_at y first_seen_at no autorizan antigüedad.
  Conflictos mayores de un segundo entre fechas declaradas del mismo post
  se apartan; no se elige silenciosamente la más reciente.
- Relojes: datetimes con UTC offset, epoch seconds/milliseconds inequívocos,
  comparación en UTC, 5 min de tolerancia a deriva; futuros lejanos y fechas
  locales sin huso se apartan explícitamente.
- audit_recent_plans: snapshots de las ocho rutas registradas en el código
  privado; Reddit figura como sin_ruta_verificada, no cero. Si está disponible
  post_age_policy.PLAN_SNAPSHOTS del gate de #8/privado, se utiliza directamente
  en vez de repetir las rutas; el fallback local sirve solo para el espejo
  independiente. Contratos con redes incompletas provocan error visible.
  Archivos ausentes, antiguos, corruptos o mayores de 4 MB se diferencian
  de planes válidos. Sin accesos de red, credenciales o modificación de colas.
- tools/daily_review.py: la sección nueva imprime solo contadores para nueve
  redes. No imprime URLs, textos, handles ni ID. Para reproducir:
  python tools/post_age_distribution.py --root .
  o python tools/post_age_distribution.py --sample fichero_sintetico.json
  (JSON red -> lista de candidatos).
- tests/test_post_age_distribution.py: sintéticos, aislados y deterministas
  salvo CLI que toma now UTC del reloj actual.

**Antes/después**: no había distribución transversal en el informe diario;
ahora existen nueve estados, tres contadores acumulados y siete rangos por
red. Coste O(n) por candidatos, O(1) memoria del agregado, excluida la lectura
JSON. No hay cifras reales ni supuesta mejora de conversión. Solo mide los
planes presentes, no la totalidad de resultados de descubrimiento. `total`
contabiliza destinos de post (no acciones de perfil); el agregado expone
`acciones_perfil_excluidas` separadamente. Otros tipos sin fecha acreditada
siguen siendo `unknown` hasta demostrar su procedencia.

## Validación offline

python -m compileall -q tools tests

python -m pytest tests/test_post_age_distribution.py -q -p no:cacheprovider

python -m pytest tests -q -p no:cacheprovider (con las ocho deselecciones
enumeradas en .github/workflows/validate-social-tools.yml del espejo).

Fixtures generados dentro de la suite: nueve redes, bordes exactos y segundo
posterior a 24/72/168h, offsets y DST, timestamp Unix Reddit/TikTok, fechas
anidadas, cola vs publicación, fechas contradictorias, futuro, JSON roto,
plan enorme, plan ausente, CLI sin filtrar URLs ni rutas, y planes mixtos
con follows en las nueve redes (incluido Instagram de solo follows).

## Segunda revisión adversarial

Se ha buscado deliberadamente: un created_at de cola interpretado como post;
indexedAt confundido con createdAt; DST / fecha sin offset; falso cero cuando
falta plan; contradicciones entre metadatos; ID federado Mastodon / TID de
Bluesky como supuesto reloj certificado; futuro inverosímil; ficheros
corruptos y fugas en salida. Un caso nuevo mostró que post/record/status/media
de una **acción** podían ser wrappers recientes no pertenecientes al post
destino: ahora esos campos solo se aceptan en payloads sin acción identificados
source_kind=post. En las acciones sin fecha acreditada se informa unknown; se
añadió regresión por nueve redes y test de preferencia por el contrato
PLAN_SNAPSHOTS del gate oficial. El módulo no infiere nada a partir de IDs:
el gate de #8 es más específico. La telemetría **no autoriza publicaciones**.

## Pendiente de integración y reversibilidad

Claude debe validar que los escáneres propagan target_created_at/post_created_at
certificados hasta los planes, especialmente si antes se usaban campos genéricos:
esta mitigación prioriza unknown frente a falsos posts recientes. Validar
source_kind=post solo para documentos auténticos de post, no envoltorios.
Ejecutar Windows/Edge/Android real y cualquier canario supervisado;
no se afirma que las pruebas offline cubran esos entornos. La ruta de planes
Reddit requiere verificación antes de declararla cubierta. Para retirar la
integración, eliminar el hook en daily_review.extra_sections, el módulo y sus
tests; no existen migraciones de base de datos ni nuevos estados.

PRs próximas ya existentes: #8 (gate), #62 (procedencia), #49 (DST),
#24 (observabilidad). No abrir una PR derivada que duplique esos alcances.
