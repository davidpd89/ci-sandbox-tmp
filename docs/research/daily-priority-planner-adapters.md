# PR #103 — Adaptadores read-only de prioridad relacional (10-10-2026)

## Alcance y contratos observados

- Repositorio oficial privado inspeccionado **solo mediante conector** en la rama `integracion/crecimiento-2026-10` (árbol `5449513d9b545d0a6a72abf066ab6a779bfdad71`). No se han trasladado cuentas, bases, tokens ni históricos. Se inspeccionaron `tools/x_build_plan.py`, `threads_build_plan.py`, `instagram_build_plan.py`, `pinterest_growth.py`, `loyalty_events.py`, `reciprocity.py`, `post_age_policy.py`, `network_policy_contracts.py`, `round_queue.py` y otros constructores nativos. Las nueve redes existen, pero **no son equivalentes** sus rutas ejecutables: `network_capabilities.py` ni siquiera incluye Instagram en el inventario general de ocho.
- El contrato del score se toma de [PR #71, commit fijado](https://github.com/davidpd89/ci-sandbox-tmp/blob/a8b3330b444090a871bbf7b53d26585525ad2450/tools/relationship_priority.py). El score acepta `network,lane,handle,actor_id,affinity,reciprocity,inbound,last_*_at,outbound_30d,reply_target_at,latest_post_at` y flags; devuelve propuestas `reply|follow|reactivate|visit`. **No reimplementamos ni recalculamos** las puntuaciones ni inventamos `repost` o `like` dentro de #71.
- `tools/loyalty_events.py` oficial confirma esquema `verified_inbound(network,event_id,author_id,handle,kind,day,...)` para X/Threads. Este puente solo lee esa tabla en modo SQLite de solo lectura. Las otras siete redes requieren que #69 u otro productor suministre eventos con procedencia comprobada: no se les atribuye reciprocidad ficticia ni se equiparan las filas legacy día-cuenta-tipo con eventos únicos.
- La máquina de estados #60, reciprocidad #65, candidatos #66/#100, inbound #69 y fecha de origen #61/#62 son dependencias de integración. Si aún no hay evidencia comprobable, quedan señales a cero/no conocidas y acciones no habilitadas. El score jamás anula el preflight del ejecutor.

## Entrega efectiva

- `tools/relationship_planner_adapters.py`: interfaz `build_snapshot(sources,outbound,inbound,today)`, `plan_dry_run(...,scorer=rank_daily)` y CLI con `--manifest` y `--today`. Únicamente lee JSON, CSV de acciones **confirmadas** y SQLite verified inbound. No hay credenciales, conexión de red, estado persistente, comentario generado, automatización o ejecución.
- Adaptadores de entrada de nueve redes: listas nativas, `candidates`, `actors`, Pinterest `authors/pins` y TikTok `posts` anidados. No deducimos «follow» si el productor no declara esa acción. La cola es **declarada** por el productor: en la prueba 9x3 se simulan todas las combinaciones, **no** se afirma que 27 canales reales estén conectados.
- Un mismo `actor_id` dentro de una red solo ocupa una plaza entre colas por el deduplicador de #71; los alias contradictorios se descartan antes. Cada entrada fallida se aísla con diagnóstico; no consume presupuesto de otras redes.
- La ventana de comentario exige fecha de destino explícita y válida de máximo **3 días** conforme a `post_age_policy.MAX_AGE_DAYS` de la rama oficial. `created_at` del trabajo no sirve como fecha del destino. Texto únicamente tras `thread_verified`, `comment_allowed` externo confirmado y balance de comentarios confirmado frente a entradas deduplicadas. Follow solo con estado de seguimiento verificado. Bloqueos y cuentas propias no entran en el ranking.
- X nunca recibe recomendaciones automáticas `like`; `repost` queda fuera de este score, sin alterar el trabajo del ejecutor. Las recomendaciones son etiquetas y scores, no JSON ejecutable por motores nativos. Todas las rutas de ejecución deben mantener sus propias comprobaciones inmediatas (estado, fecha, bloqueo y límites).
- Sin valor fiable de afinidad, usamos `0.0` **como límite inferior para el algoritmo**, registrando desconocimiento. Reciprocidad sin evidencia se mantiene `null`; jamás se presenta como valor observado.

### Invocación offline

```sh
python tools/relationship_planner_adapters.py --manifest fixtures_sinteticos/manifest.json --today 2026-10-10
```

El manifiesto contiene `{"sources":[{"network":"x","lane":"WEB","path":".../candidatos.json"}],"outbound_csvs":{"x":".../registro.csv"},"verified_inbound_sqlite":".../inbound.sqlite"}`. Todas las rutas se suministran explícitamente; no busca ni modifica bases de producción. Si el módulo #71 no está en Python path, se produce un error claro en vez de usar otro score. `preflight.checked_at` debe ser el día solicitado, y nunca autoriza ejecutar la salida.

## Comparación de reutilización pública (verificada 10-10-2026)

| Candidato | Revisión inmutable | SPDX / Python | Evaluación |
| --- | --- | --- | --- |
| [APScheduler](https://github.com/agronholm/apscheduler) | [`a660860d`](https://github.com/agronholm/apscheduler/commit/a660860d841c5426ec3b7ed2d4ada8fe168710f1) | MIT, 3.11; desarrollo activo; versiones v4 preliminares | Excelente para temporización real, **no** transforma snapshots ni prueba elegibilidad. Depender de él para esta etapa read-only agregaría reloj y runtime sin beneficios. No se copia código. |
| [sqlite-durable-workflow](https://github.com/eatdrop/sqlite-durable-workflow) | [`d9de9524`](https://github.com/eatdrop/sqlite-durable-workflow/commit/d9de9524e4533727383ff937ccf0522c3739b7ea) | MIT; librería Python sin dependencias runtime; actividad reciente | Su cola idempotente/durable es candidata a ejecución futura, no a este lector que **no** reserva ni escribe trabajo. No se copia código. |
| Código ya existente de #71 y `sqlite3` de Python 3.11 | [#71 commit](https://github.com/davidpd89/ci-sandbox-tmp/commit/a8b3330b444090a871bbf7b53d26585525ad2450) | Código del proyecto y stdlib | Mejor ajuste: conservar scoring probado, usar adaptador pequeño sin librerías externas ni runtime multihilo. |

Ningún archivo de tercero fue copiado; la licencia permite reutilizar pero el criterio técnico aconseja no introducir dependencias. El sondeo no certifica mantenimiento perpetuo ni compatibilidad de futuras revisiones.

## Verificación, dos pasadas y limitaciones

- Prueba offline dedicada: `python -m unittest discover -s tests -p test_relationship_planner_adapters.py -v`. La prueba de integración usa #71 **anclado** al commit citado, en CI aislado Windows/Ubuntu Python 3.11. `python -m py_compile tools/relationship_planner_adapters.py`.
- Fixture **sintético 9x3** (27 observaciones, 9 actores): deduplicación entre colas, X sin auto-like, rechazos aislados, cuatro formas de fecha, 3 días antinecropost, historia confirmada frente a intentos, un único evento por ID, conflicto de IDs, bloqueo/follow, aliases contradictorios, SQLite readonly, Pinterest y TikTok nativos.
- Microbenchmark **sintético**, no producción: 1350 candidatos, medido por `time.perf_counter()` en el test sin prometer tiempos universales. No reproduce tiempo de Playwright, APIs o teléfonos.
- **Revisión adversarial 1:** el primer CI aislado detectó un test TikTok con acción del actor no declarada (corregido declarándola) y en Windows un descriptor SQLite del **fixture** que `with sqlite3.connect()` no cerraba (corregido con `contextlib.closing`). Ambos estaban descubiertos por tests reales, no inferidos.
- **Revisión adversarial 2:** verificar todavía coherencia de estado ante alias cambiados, cambios de nombre y distintos `actor_id` para una misma cuenta; el puente descarta conflictos visibles pero **no resuelve identidades remotas históricas** (#85/#109). La política de comentarios oficial usa todo el historial de acciones confirmadas: un CSV truncado puede sobreofertar; el ejecutor debe reevaluar su ledger completo.
- Límites explícitos: Instagram no está certificado en el pipeline multired general; el scanner Reddit puede requerir adaptación específica; X/Threads son los únicos respaldados por el esquema actual de `loyalty_events.py`. No se han probado cuentas, Edge real, Windows de escritorio, Android, sesiones, ni canario supervisado. Los tests son offline, no canarios. **Claude debe comprobar los productores reales en el repo privado y el estado actual de las dependencias antes del merge.**

### Migración y rollback

No se actualiza ningún planificador ni estado persistente. Para desactivar el puente, retirar su invocación o revertir los commits de esta PR; los planes nativos anteriores permanecen sin cambios. Integración futura por flags y modo shadow primero, con lectura de snapshots *y* preflights frescos; canario supervisado solo con permiso explícito y responsabilidad del ejecutor. Nunca hacer merge de esta PR antes de incorporar #71 y reconciliar contratos de #69/#60/#65.

## Registro de segunda revisión

- Revisión de funciones con entrada hostil: rechazos por tipo, fecha futura, desconocimiento de cuenta propia, score externo sin validar y colisiones de eventos.
- Auditado que el código no importa clientes de redes, no crea archivos ni escribe SQLite. `plan_dry_run` invoca directamente al score #71 sin añadir acciones.
- Pendiente de validar la segunda pasada de CI y el gate de privacidad con este informe incluido; no se declara aptitud de merge hasta comprobar resultados.
