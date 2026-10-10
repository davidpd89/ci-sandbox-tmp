# PR #103 — Adaptadores read-only de prioridad relacional (10-10-2026)

Fuente primaria: https://github.com/agronholm/apscheduler
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/agronholm/apscheduler/commit/a660860d841c5426ec3b7ed2d4ada8fe168710f1

## Problema
Prioridad pura #71 sin adaptadores secos a los nueve productores, con información relacional desigual entre fuentes y tres colas que no deben pisarse.

## Alternativas
Se contrastan APScheduler, sqlite-durable-workflow y la continuidad #71 + biblioteca estándar; véase la comparativa y commits fijados más abajo.

## Licencias y procedencia
Los candidatos de terceros analizados son MIT. No se incorpora código ni dependencia de terceros; el único componente invocado es el score propio de #71.

## Decisión
Adaptador ligero de solo lectura, preflight explícito, deduplicación por #71 y ninguna acción social.

## Pruebas
Pruebas sintéticas 9x3, 21 tests offline con ejecución en Ubuntu y Windows 3.11, revisión adversarial y benchmark local de lectura; detalles y runs en la sección inferior.

## Retirada
Revertir commits de la PR o no conectar su invocación. No hay migraciones ni modificaciones persistentes.

## Alcance y contratos observados

- Repositorio oficial privado inspeccionado **solo mediante conector** en la rama `integracion/crecimiento-2026-10` (árbol `5449513d9b545d0a6a72abf066ab6a779bfdad71`). No se han trasladado cuentas, bases, tokens ni históricos. Se inspeccionaron `tools/x_build_plan.py`, `threads_build_plan.py`, `instagram_build_plan.py`, `pinterest_growth.py`, `loyalty_events.py`, `reciprocity.py`, `post_age_policy.py`, `network_policy_contracts.py`, `round_queue.py` y otros constructores nativos. Las nueve redes existen, pero **no son equivalentes** sus rutas ejecutables: `network_capabilities.py` ni siquiera incluye Instagram en el inventario general de ocho.
- El contrato del score se toma de [PR #71, commit fijado](https://github.com/davidpd89/ci-sandbox-tmp/blob/a8b3330b444090a871bbf7b53d26585525ad2450/tools/relationship_priority.py). El score acepta `network,lane,handle,actor_id,affinity,reciprocity,inbound,last_*_at,outbound_30d,reply_target_at,latest_post_at` y flags; devuelve propuestas `reply|follow|reactivate|visit`. **No reimplementamos ni recalculamos** las puntuaciones ni inventamos `repost` o `like` dentro de #71.
- `tools/loyalty_events.py` oficial confirma esquema `verified_inbound(network,event_id,author_id,handle,kind,day,...)` para X/Threads. Este puente solo lee esa tabla en modo SQLite de solo lectura. Las otras siete redes requieren que #69 u otro productor suministre eventos con procedencia comprobada: no se les atribuye reciprocidad ficticia ni se equiparan las filas legacy día-cuenta-tipo con eventos únicos.
- La máquina de estados #60, reciprocidad #65, candidatos #66/#100, inbound #69 y fecha de origen #61/#62 son dependencias de integración. Si aún no hay evidencia comprobable, quedan señales a cero/no conocidas y acciones no habilitadas. El score jamás anula el preflight del ejecutor.

## Entrega efectiva

- `tools/relationship_planner_adapters.py`: interfaz `build_snapshot(sources,outbound,inbound,today)`, `plan_dry_run(...,scorer=rank_daily)` y CLI con `--manifest` y `--today`. Únicamente lee JSON, CSV de acciones **confirmadas** y SQLite verified inbound. No hay credenciales, conexión de red, estado persistente, comentario generado, automatización o ejecución.
- Adaptadores de entrada de nueve redes: listas nativas, `candidates`, `actors`, Pinterest `authors/pins` y TikTok `posts` anidados. **No se inventan acciones desde el tipo de contenedor:** un `author` de Pinterest no equivale a `follow`, ni un `pin` o `post` a `comment/reply`. Cada fila o post anidado debe declarar `kind`/`actions`; las acciones de un actor TikTok no se heredan en sus posts. Corregido en la revisión independiente con regresión offline. La cola es **declarada** por el productor: en la prueba 9x3 se simulan todas las combinaciones, **no** se afirma que 27 canales reales estén conectados.
- Un mismo `actor_id` dentro de una red solo ocupa una plaza entre colas por el deduplicador de #71; los alias contradictorios se descartan antes. Cada entrada fallida se aísla con diagnóstico; no consume presupuesto de otras redes.
- El historial outbound para proponer reply requiere certificado declarado de cobertura integral por red (desde antes de abrirse la cuenta hasta el día evaluado), más CSV realmente suministrado; sin él, `reply_eligible=False`. La certificación es un **contrato del productor**, no prueba criptográfica de que el CSV esté completo. Los inbound cuentan solo los últimos 30 días inclusivos (hoy a hoy−29), con deduplicación por evento; si no hay eventos recientes, el campo `inbound` se omite y el scorer lo trata como desconocido, no como cero observado. Los vetos por bloqueo/cuenta propia y estado de follow positivo prevalecen entre WEB/API/MOBILE para un mismo ID.
- La ventana de comentario exige fecha de destino explícita y válida de máximo **3 días** conforme a `post_age_policy.MAX_AGE_DAYS` de la rama oficial. `created_at` del trabajo no sirve como fecha del destino. Texto únicamente tras `thread_verified`, `comment_allowed` externo confirmado y balance de comentarios confirmado frente a entradas deduplicadas. Follow solo con estado de seguimiento verificado. Bloqueos y cuentas propias no entran en el ranking.
- X nunca recibe recomendaciones automáticas `like`; `repost` queda fuera de este score, sin alterar el trabajo del ejecutor. Las recomendaciones son etiquetas y scores, no JSON ejecutable por motores nativos. Todas las rutas de ejecución deben mantener sus propias comprobaciones inmediatas (estado, fecha, bloqueo y límites).
- Sin valor fiable de afinidad, usamos `0.0` **como límite inferior para el algoritmo**, registrando desconocimiento. Reciprocidad sin evidencia se mantiene `null`; jamás se presenta como valor observado.

### Invocación offline

```sh
python tools/relationship_planner_adapters.py --manifest fixtures_sinteticos/manifest.json --today 2026-10-10
```

El manifiesto contiene `{"sources":[{"network":"x","lane":"WEB","path":".../candidatos.json"}],"outbound_csvs":{"x":".../registro.csv"},"verified_inbound_sqlite":".../inbound.sqlite","outbound_coverage":{"x":{"status":"complete","from":"2020-01-01","account_since":"2020-01-01","through":"2026-10-10"}}}`. Las fechas de cobertura son ejemplos sintéticos y **deben ser emitidas por un exportador confiable**; no basta con introducir `status=complete` manualmente. Todas las rutas se suministran explícitamente; no busca ni modifica bases de producción. Si el módulo #71 no está en Python path, se produce un error claro en vez de usar otro score. `preflight.checked_at` debe ser el día solicitado, y nunca autoriza ejecutar la salida.

## Comparación de reutilización pública (verificada 10-10-2026)

| Candidato | Revisión inmutable | SPDX / Python | Evaluación |
| --- | --- | --- | --- |
| [APScheduler](https://github.com/agronholm/apscheduler) | [`a660860d`](https://github.com/agronholm/apscheduler/commit/a660860d841c5426ec3b7ed2d4ada8fe168710f1) | MIT, 3.11; desarrollo activo; versiones v4 preliminares | Excelente para temporización real, **no** transforma snapshots ni prueba elegibilidad. Depender de él para esta etapa read-only agregaría reloj y runtime sin beneficios. No se copia código. |
| [sqlite-durable-workflow](https://github.com/eatdrop/sqlite-durable-workflow) | [`d9de9524`](https://github.com/eatdrop/sqlite-durable-workflow/commit/d9de9524e4533727383ff937ccf0522c3739b7ea) | MIT; librería Python sin dependencias runtime; actividad reciente | Su cola idempotente/durable es candidata a ejecución futura, no a este lector que **no** reserva ni escribe trabajo. No se copia código. |
| Código ya existente de #71 y `sqlite3` de Python 3.11 | [#71 commit](https://github.com/davidpd89/ci-sandbox-tmp/commit/a8b3330b444090a871bbf7b53d26585525ad2450) | Código del proyecto y stdlib | Mejor ajuste: conservar scoring probado, usar adaptador pequeño sin librerías externas ni runtime multihilo. |

Ningún archivo de tercero fue copiado; la licencia permite reutilizar pero el criterio técnico aconseja no introducir dependencias. El sondeo no certifica mantenimiento perpetuo ni compatibilidad de futuras revisiones.

## Verificación, dos pasadas y limitaciones

- Prueba offline dedicada: `python -m unittest discover -s tests -p test_relationship_planner_adapters.py -v`. La prueba de integración usa `relationship_priority.py` de la base sincronizada, en CI Windows/Ubuntu Python 3.11; no usa el commit antiguo fijado de #71. `python -m py_compile tools/relationship_planner_adapters.py`.
- Fixture **sintético 9x3** (27 observaciones, 9 actores): deduplicación entre colas, X sin auto-like, rechazos aislados, cuatro formas de fecha, 3 días antinecropost, historia confirmada frente a intentos, un único evento por ID, conflicto de IDs, bloqueo/follow, aliases contradictorios, SQLite readonly, Pinterest y TikTok nativos.
- Microbenchmark **sintético**, no producción: 1350 candidatos, medido por `time.perf_counter()` en el test sin prometer tiempos universales. Ejecución previa en CI: 0,018 s Ubuntu y 0,019 s Windows (hardware alojado, no garantía). No reproduce tiempo de Playwright, APIs o teléfonos.
- **Revisión adversarial 1:** el primer CI aislado detectó un test TikTok con acción del actor no declarada (corregido declarándola) y en Windows un descriptor SQLite del **fixture** que `with sqlite3.connect()` no cerraba (corregido con `contextlib.closing`). Ambos estaban descubiertos por tests reales, no inferidos.
- **Revisión adversarial 2:** corregida la propagación de fallos de rutas de entrada de una red a las demás, validación de cabeceras de CSV y captura de Unix epoch; quedan por validar los alias cambiados, cambios de nombre y distintos `actor_id` para una misma cuenta; el puente descarta conflictos visibles pero **no resuelve identidades remotas históricas** (#85/#109). La política de comentarios oficial usa todo el historial de acciones confirmadas: un CSV truncado puede sobreofertar; el ejecutor debe reevaluar su ledger completo.
- Límites explícitos: Instagram no está certificado en el pipeline multired general; el scanner Reddit puede requerir adaptación específica; X/Threads son los únicos respaldados por el esquema actual de `loyalty_events.py`. No se han probado cuentas, Edge real, Windows de escritorio, Android, sesiones, ni canario supervisado. Los tests son offline, no canarios. **Claude debe comprobar los productores reales en el repo privado y el estado actual de las dependencias antes del merge.**

### Migración y rollback

No se actualiza ningún planificador ni estado persistente. Para desactivar el puente, retirar su invocación o revertir los commits de esta PR; los planes nativos anteriores permanecen sin cambios. Integración futura por flags y modo shadow primero, con lectura de snapshots *y* preflights frescos; canario supervisado solo con permiso explícito y responsabilidad del ejecutor. Nunca hacer merge de esta PR antes de incorporar #71 y reconciliar contratos de #69/#60/#65.

## Registro de segunda revisión

- Revisión de funciones con entrada hostil: rechazos por tipo, fecha futura, desconocimiento de cuenta propia, score externo sin validar y colisiones de eventos.
- Auditado que el código no importa clientes de redes, no crea archivos ni escribe SQLite. `plan_dry_run` invoca directamente al score #71 sin añadir acciones.
- La rama se sincronizó con la base `737fc011`, que ya contiene `tools/relationship_priority.py`; CI103 lo prueba directamente sin checkout obsoleto. Suite específica: 21 pruebas Windows/Ubuntu con los nuevos casos de cobertura, rolling 30 días, colas y vetos. La integración ya no se omite por falta del scorer. **Bloqueo externo:** el validador de campaña comunica `#103: child absent from parent manifest` para la rama padre `research/public-reuse-parent`; el controlador deberá sincronizar `children.json`/índice en la PR padre sin modificar esta rama. No es fallo del puente ni permite afirmar merge listo.

### Hallazgos de revisión independiente pendientes

- **Historial de salida y preflight:** `read_manifest` acepta CSV ausentes por red y `build_snapshot` interpreta un `outbound` vacío como ausencia de interacción. Antes de habilitar sugerencias de comentario en integración real, exigir una prueba positiva de cobertura del ledger completo por red/actor; falta de fuente o truncamiento no es equivalente a cero. El preflight fechado solo al día no es prueba de frescura en tiempo real; cada ejecutor revalida antes de actuar.
- **Integración nativa:** estas funciones crean snapshots offline, pero ningún planificador de producción importa o invoca aún el puente. El objetivo de nueve redes requiere un contrato exportador por cada productor realmente conectado, más fixtures nativos reales anonimizados y pruebas en modo shadow; la prueba sintética 9x3 no certifica esa integración.
- **Dependencia #71:** el ranking elige una única cola por actor antes de aplicar límites por cola; hay que probar el caso de un mismo actor en dos colas cuando su cola ganadora tiene cupo cero o está agotada. La corrección de selección, si procede, pertenece al scorer común, no a este adaptador.

Estas pendientes no quedan resueltas por la regresión de acciones explícitas. El código sigue siendo un lector sin efectos sobre cuentas.


## Control final sobre base sincronizada (10-10-2026)

- HEAD de base incorporada: `737fc011c7985b1d7a2f9092611656308de8884d`; el adaptador es nuevo y no sustituye `tools/relationship_priority.py`, `relationship_policy.py`, `relationship_event_ledger.py` ni preflights nativos existentes.
- Regresión 30 días: 75 likes antiguos + 2 comentarios recientes por red en las nueve redes nunca equivalen a 75 likes recientes; día de corte inclusivo, IDs duplicados entre colectores y fechas futuras descartadas. Los IDs antiguos siguen sirviendo para detectar conflictos de identidad.
- Un CSV ausente o una cobertura parcial ya no permiten recomendar un reply, aunque `comment_allowed` y `thread_verified` estén a true. Sin `outbound_coverage` declarado y CSV disponible, no hay sugerencia de respuesta. Estado de cobertura por red en `diagnostics.outbound_coverage`.
- Invariante de vetos entre colas: un preflight bloqueado o cuenta propia de cualquier origen impide que una segunda observación del mismo `actor_id` escape a ese veto; un follow observado en otra cola no se vuelve a proponer.
- Corregida la regresión de cupos señalada en #71 por el priorizador **ya presente en la base**: matching con capacidad disponible, `WEB=0,API=1` asigna API una sola vez. No se copia ni bifurca el scorer.
- Gates de la PR: CI103 Ubuntu/Windows verde en HEAD de tests `02325d14`; gate de campaña Ubuntu falla únicamente en chequeo live `#103: child absent from parent manifest` aunque gate offline y privacidad pasan. Corregir ese manifiesto **en la rama padre**, no en este lector.
- **Pendiente de aceptación, sin certificar nueve ejecutores:** conectar exportadores y 9 fixtures nativos, producir evidencia verificable de completitud (incluida reconciliación de `actor_id` y renombres en outbound), probar shadow diffs contra planes reales y suite completa en repo privado. Falta garantizar que los certificados declarados sean generados desde ledger autoritativo y no introducidos por un consumidor; hasta entonces, bloqueo del merge. Integración nunca autoriza acciones sin preflight fresco.

### Comandos para controlador

```sh
python -m unittest discover -s tests -p test_relationship_planner_adapters.py -v
python -m pytest tests/test_relationship_planner_adapters.py -q
python -m pytest -q
python -m py_compile tools/relationship_planner_adapters.py tests/test_relationship_planner_adapters.py
python tools/validate_open_source_campaign.py
python tools/validate_open_source_campaign.py --live --child-number 103
```

En Windows nativo ejecutar los mismos comandos con `py -3.11 -m unittest...` / `py -3.11 -m pytest...`. Edge, CDP y Android deben usar pruebas supervisadas locales del repo oficial; no se han conectado cuentas ni realizado acciones sociales en esta PR.
