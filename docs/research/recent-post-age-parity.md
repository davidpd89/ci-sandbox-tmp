# CI 61 — antigüedad de posts: ventanas comunes y telemetría

Revisión: 10-10-2026. Rama: research/51-recent-post-age-parity.
Solo observabilidad de la edad del POST DESTINO: no se ejecutan acciones sociales.

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
- Procedencia explícita: target_created_at/post_created_at; fechas en post,
  record, status o media; Reddit created_utc; TikTok create_time. Created_at en
  raíz solo con source_kind=post. El campo created_at de una ACCIÓN,
  indexedAt, observed_at, queued_at y first_seen_at no autorizan antigüedad.
  Conflictos mayores de un segundo no seleccionan la fecha más reciente.
- Relojes: datetimes con UTC offset, epoch seconds/milliseconds inequívocos,
  comparación en UTC, 5 min de tolerancia a deriva; futuros lejanos y fechas
  locales sin huso se apartan explícitamente.
- audit_recent_plans: snapshots de las ocho rutas registradas en el código
  privado; Reddit figura como sin_ruta_verificada, no cero. Archivos ausentes,
  antiguos, corruptos o mayores de 4 MB son estados separados. Sin accesos
  de red, credenciales o modificación de colas.
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
planes presentes, no la totalidad de resultados de descubrimiento.

## Validación offline

python -m compileall -q tools tests

python -m pytest tests/test_post_age_distribution.py -q -p no:cacheprovider

python -m pytest tests -q -p no:cacheprovider (con las ocho deselecciones
enumeradas en .github/workflows/validate-social-tools.yml del espejo).

Fixtures generados dentro de la suite: nueve redes, bordes exactos y segundo
posterior a 24/72/168h, offsets y DST, timestamp Unix Reddit/TikTok, fechas
anidadas, cola vs publicación, fechas contradictorias, futuro, JSON roto,
plan enorme, plan ausente, CLI sin filtrar URLs ni rutas.

## Segunda revisión adversarial

Se ha buscado deliberadamente: un created_at de cola interpretado como post;
indexedAt confundido con createdAt; DST / fecha sin offset; falso cero cuando
falta plan; contradicciones entre metadatos; ID federado Mastodon / TID de
Bluesky como supuesto reloj certificado; futuro inverosímil; ficheros
corruptos y fugas en salida. El módulo no infiere nada a partir de IDs:
el gate de #8 es más específico. La telemetría **no autoriza publicaciones**.

## Pendiente de integración y reversibilidad

Claude debe validar que los escáneres nutren fechas originales en cada
snapshot, ejecutar Windows/Edge/Android real y cualquier canario supervisado;
no se afirma que las pruebas offline cubran esos entornos. La ruta de planes
Reddit requiere verificación antes de declararla cubierta. Para retirar la
integración, eliminar el hook en daily_review.extra_sections, el módulo y sus
tests; no existen migraciones de base de datos ni nuevos estados.

PRs próximas ya existentes: #8 (gate), #62 (procedencia), #49 (DST),
#24 (observabilidad). No abrir una PR derivada que duplique esos alcances.
