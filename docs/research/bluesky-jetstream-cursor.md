# Bluesky / Jetstream: checkpoint y replay seguro (PR #11)

Consulta técnica: **2026-10-09**. Repositorios: mirror público `davidpd89/ci-sandbox-tmp` (rama `research/01-bluesky-atproto`); oficial privado `davidpd89/rrss-davidporto-CODE` (solo lectura; no se transfieren datos, tokens ni historiales).

## Problema reproducido y alcance elegido

`tools/bluesky_jetstream_collect.py` consumía commits Jetstream v2 (`seq`) y los insertaba/actualizaba/borraba en `posts` (SQLite), pero:

1. Inicializaba `last_seq=None` incluso si existía `state.last_seq` persistido. El primer replay inclusivo se podía aplicar de nuevo.
2. Actualizaba `cursor` **antes** de llamar a `store_event`; una secuencia anterior recibida tras reconexión podía hacer retroceder el cursor y resucitar una entrada borrada o sobrescribir una actualización.
3. Algunos `db.commit()` se ejecutaban sin escribir a la vez `state.last_seq`. Los checkpoints periódicos solo guardaban estado cada 250 frames, mientras que la caché podía quedar confirmada antes.

**Reproducción sintética, sin red:** aplicar create (seq 100) y delete (seq 102) al mismo `at://did:plc:synthetic/app.bsky.feed.post/synthetic`, y después reentregar create (seq 101). Con `store_event` sin barrera hay **1** post resucitado; con `_apply_frame` hay **0**. El fixture mide integridad, **no rendimiento, crecimiento ni resultados de marketing**.

Se corrige **solo la ingesta v2 en el mirror**. No se amplían acciones sobre cuentas, ni se altera `bluesky_execute.py`/`action_ledger.py`, ni se porta automáticamente a producción privada.

## Ruta técnica auditada

`tools/bluesky_growth_flow.py prepare --deep N` -> subproceso `bluesky_jetstream_collect.py` -> filtros `load_terms/match_terms` y comprobación de idioma/política -> `store_event` -> SQLite `posts` + `state` -> `bluesky_growth_scan._consume_jetstream_cache` -> `read_recent_matches`/`read_active_authors` -> hidratación `getPosts/getProfiles` (DID estable, handle mutable) -> `growth_state.json`/`growth_ai.json` -> `bluesky_build_plan.py` -> aprobación humana -> `bluesky_execute.py` -> confirmación remota/ledger/registro/métricas.

El collector no ejecuta follows, likes ni respuestas. Fallos del collector con código distinto de cero bloquean el `prepare --deep`; errores recuperables de socket acumulan `connection_errors` y se reintentan. Queda riesgo residual de error remoto persistente con salida 0 al terminar la ventana, incluso sin eventos: ver **Bloqueos**.

La rama oficial privada contiene `tools/bluesky_jetstream_collect.py` en `main` (blob `eac9df2155ebdca7f5a89ccc3feff8fc94b95df5`) y tests propios; su estado no es idéntico al mirror (blob inicial `d1ea5f111880356638bfd88ad76811d6027089cf`). El uso de la versión oficial debe verificarse contra sus tests y HEAD vigentes al portar.

## Alternativas estudiadas

| Alternativa | Licencia / revisión verificable | Ventaja | Coste o riesgo | Decisión |
| --- | --- | --- | --- | --- |
| Baseline: `websockets>=12,<16` + SQLite | Dependencia actual en mirror; versión instalada y licencia transitiva no auditadas aquí | Sin runtime adicional, actual interfaz de consumidores, sin nuevos permisos | Checkpoint y replay propio frágiles | **Elegida: patrón C (corrección local acotada)** |
| SDK Python `MarshalX/atproto` | MIT; commit [4c17895](https://github.com/MarshalX/atproto/tree/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8) (2026-10-02) | **Sí incorpora** `AsyncJetstreamClient` v2, reconexión, dedupe, cursor y `snapshot`/`replay` de archivo, además de DID, rich text y XRPC | `client.py` actualiza cursor **antes** del callback de persistencia y descarta ciertos frames que no logra decodificar; no garantiza nuestro checkpoint SQLite. Añade `pydantic`, `cryptography`, `zstandard`, `libipld`, etc. Archivo exige credencial. | No integrar en #11; evaluar adaptador/handoff en #94 |
| `@bsky/jetstream` (TypeScript) | Proyecto Bluesky dual MIT/Apache-2.0, repo [bc6737a](https://github.com/bluesky-social/bsky/tree/bc6737a4b52dd2458c7aecbc296ec660e068af89) (2026-10-08) | Reconexión, cursores y abstracciones mantenidas | Node.js/TS y puente entre procesos hacia SQLite de Python; distinto contrato v1/v2 | No integrar |
| Cliente Go del Jetstream oficial | MIT/Apache-2.0; [f42df08](https://github.com/bluesky-social/jetstream/tree/f42df08ba0ca9e4287020139aefbcfe24506d1ef) (2026-10-09) | Referencia de cursor inclusivo, resync v2 y dedupe | Nuevo binario, empaquetado Windows/Linux y capa IPC | No integrar |

Se adaptó conceptualmente el patrón de **high-water monotónico, replay idempotente y checkpoint atómico**; **no se copió código fuente ni fixtures ajenos**. Coste de librerías nuevas: **cero**. Se mantienen `websockets`, `sqlite3` y la interfaz de `read_recent_matches`. No se inventan tiempos ni ahorros de CPU; no hay benchmark de throughput reproducido con el entorno de producción.

## Licencias y procedencia

Fuente primaria: https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/docs/README.md
Fecha de consulta: 2026-10-09
Licencia SPDX: MIT
Referencia inmutable: https://github.com/bluesky-social/jetstream/tree/f42df08ba0ca9e4287020139aefbcfe24506d1ef

La referencia oficial Go tiene licencia alternativa `MIT OR Apache-2.0`.
El SDK Python `MarshalX/atproto` es MIT, admite Python 3.11 y Windows
(Python independiente de SO) pero incorpora dependencias transitivas
(`httpx`, `pydantic`, `cryptography`, `libipld`, `zstandard`).
`@bsky/jetstream` depende de Node.js y requiere puente de persistencia
para este proceso Python. Se comprueba actividad pública reciente en los
commits fijos indicados arriba; no se incorpora código ni fixture extranjero.
El patrón reutilizado es el contrato de cursor inclusivo e idempotencia
más checkpoint durable, no una implementación copiada. La compatibilidad
real con Windows/Python 3.11 se contrasta con CI propio; los SDK descartados
no se instalaron ni sometieron a tests ejecutables.

## Decisión implementada

- `_apply_frame` rechaza secuencia v2 inexistente, no positiva o previamente consumida; solo entonces invoca `store_event`. El valor de retorno distingue `matched`, high-water y `replayed`.
- Se inicializa `last_seq` con la marca persistida: un replay inclusivo tras reinicio no vuelve a mutar `posts`.
- Los HTTP 400/401/403/404/410 de handshake v2 se detienen con error explícito, sin resetear un cursor posiblemente obsoleto ni fingir éxito; 429/5xx conservan la recuperación por backoff.
- La marca de cursor v2 no retrocede después de un frame viejo; si el arranque fue mediante `time_us` legacy, se cambia al primer `seq` válido en lugar de hacer un `max` entre unidades incompatibles.
- Cada commit periódico, cada 250 eventos **o** pasados cinco segundos de procesamiento, guarda `last_seq` y `last_time_us` en la **misma** transacción que `posts` (incluidos deletes y eventos no coincidentes). `finally` confirma estado al cierre ordinario.

Rollback: revertir los commits de la PR #11 que cambian `tools/bluesky_jetstream_collect.py` y tests; el esquema SQLite no cambia y no hay migración irreversible. La versión anterior reintroduce el riesgo; preferible parar el collector si se observa incompatibilidad. No tocar ni reconstruir manualmente una SQLite de producción sin copia/control del propietario.

## Pruebas y medición: resultados verificables

Archivo `tests/test_bluesky_jetstream_collect.py`, casos añadidos:

- `test_v2_replay_does_not_resurrect_deleted_post`: baseline 1 fila vs corrección 0 filas, comprobación real con `sqlite3`.
- `test_v2_restart_uses_persisted_high_water_and_skips_inclusive_replay`: cierre/apertura reales de SQLite, contenido más nuevo conservado.
- `test_v2_invalid_seq_does_not_mutate_cache_or_checkpoint`: no avance ante cursor 0, -1 o ausente.
- `test_v1_still_accepts_timestamp_based_replays`: v1 mantiene su semántica de timestamps.
- `test_v2_rejects_http_400_without_retry_or_cursor_reset`: handshake HTTP 400 fatal tras un intento, 429 sigue clasificado como recuperable.
- `test_v2_stream_reconnect_skip_inclusive_duplicate_and_apply_delete`: WebSocket sintético con caídas, reconexión, replay inclusivo, delete y persistencia; cliente y mensajes reproducen el contrato v2 sin contactar con Bluesky.

CI del mirror usa Python 3.11 en Ubuntu y Windows, instala `requirements-ci.txt`, ejecuta `python -m compileall -q tools tests` y `python -m pytest tests -q -p no:cacheprovider` con exclusiones **ya configuradas** en el workflow `.github/workflows/validate-social-tools.yml`. El guard de red `tests/conftest.py` impide tráfico saliente durante pytest. Evidencia de cada ejecución: [Actions de la PR](https://github.com/davidpd89/ci-sandbox-tmp/actions/workflows/validate-social-tools.yml?query=branch%3Aresearch%2F01-bluesky-atproto). **No equiparar el éxito del subconjunto a una prueba end-to-end con autenticación real.**

Resultados CI confirmados en [run 37978832148](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978832148), SHA `5a935d59931c6a7664484e95397519bc0871282f`: **Ubuntu 1694 passed, 8 skipped, 8 deselected, 665 subtests passed (22,56 s); Windows 1697 passed, 5 skipped, 8 deselected, 665 subtests passed (39,14 s)**. Dos warnings ajenos de escapes inválidos en `tools/android_shell.py`; no modificados por #11.


## Autorrevisión adversarial

1. **Reenvío de una operación antigua después de delete/update.** Antes la clave primaria deduplicaba filas, pero no versiones. Se evita mutar cuando `seq <= last_seq`; tests create/delete/replay y replay tras reinicio.
2. **El collector se cae entre post y cursor.** Una transacción puede retroceder íntegra; el siguiente replay restaura el trabajo no confirmado. Se pone el high-water en el mismo checkpoint SQLite que la caché. Limitación: fallos físicos del disco/corrupción quedan fuera de la prueba actual.
3. **La sesión v2 empieza con cursor timestamp v1.** Mezclar orden numérico entre `time_us` y `seq` impediría seguir el stream; tras el primer frame válido, sustituir por `seq`. Persistir el modo del endpoint sería un endurecimiento posterior si se permiten fuentes alternativas.
4. **No coincidencias durante la escucha.** Un socket lleno de posts descartados también debe hacer avanzar el cursor; el checkpoint ya no depende de `matched`.
5. **ID DID/handle.** El collector construye claves `at://did/collection/rkey`; la resolución mutable del handle ocurre posteriormente en scan. No añadir manejo de alias ni introducir identificadores reales en fixtures.
6. **Regresión transversal.** No se toca `scan_common`, `action_ledger` ni `reply_writer`; los contratos compartidos permanecen. La suite global offline del mirror debe terminar en ambos sistemas para considerarlo apto.

## Segunda revisión adversarial: origen y locks del collector (09-10-2026)

Se identificaron dos huecos adicionales al revisar el código contra Jetstream
v2 y la rama privada `integracion/crecimiento-2026-10`:

1. **Secuencia de otra instancia**: `seq` pertenece al servidor que lo emite.
   El cache ahora guarda `last_seq_stream` (origen `wss://host/path`,
   sin parámetros ni credenciales) con el mismo commit de posts/cursor y
   rechaza una reutilización contra otro origen antes de podar datos.
   Los caches antiguos sin ese campo no pueden reconstruir su procedencia:
   se asocian solo tras aceptar un evento nuevo del host consultado; ese
   primer reinicio requiere supervisión si se cambió de host previamente.
   La igualdad de URL no demuestra por sí sola igualdad física de instancia
   si el proveedor reasigna su infraestructura.
2. **Transacción abierta durante inactividad/caída del socket**: además del
   lote de 250 eventos o cinco segundos de trabajo, el collector guarda
   estado en SQLite al vencimiento del tiempo de lectura (cinco segundos),
   tras cierre limpio y antes de reintentar una caída. No desconecta por
   silencio. La prueba con dos conexiones SQLite observa checkpoint previo
   al cierre de una ventana, y otra comprueba rollback de posts+state.
   Coste: comprobación de socket cada cinco segundos, sin dependencia nueva.

**Tests nuevos:** `test_stream_identity_is_canonical_and_contains_no_credentials`,
`test_v2_refuses_foreign_seq_without_pruning_existing_posts`,
`test_v2_checkpoint_rollback_never_advances_state_alone` y
`test_v2_idle_checkpoint_visible_to_second_reader_without_reconnect`.
Son pruebas sintéticas; no prueban cambio de instancia tras DNS, servidores
vivos, dos writers simultáneos ni corrupción física.

**Retirada y compatibilidad:** no se altera el esquema de tablas, solo se
añade la clave opcional `state.last_seq_stream`. Versiones antiguas ignoran
esa clave, pero también ignoran la nueva barrera de identidad. La reversión
consiste en revertir commits de collector/tests y revalidar la SQLite en
entorno supervisado antes de reactivar; no borrar manualmente la marca para
forzar un cambio de host. Sin canarios vivos ni acciones sobre cuentas.

## Coordinación PR hermanas (números de ci-sandbox-tmp)

| PR | Estado consultado 09-10-2026 | Zona con posible colisión | Acuerdo de alcance |
| --- | --- | --- | --- |
| [#21](https://github.com/davidpd89/ci-sandbox-tmp/pull/21) | Abierta, solo ficha `tasks/11-...` | `bluesky_growth_scan.py`, ranking, fuentes | No cambiar ranking; reutilizar caché por contrato actual |
| [#22](https://github.com/davidpd89/ci-sandbox-tmp/pull/22) | Abierta, solo ficha `tasks/12-...` | Selección de respuestas, memoria | No modificar writers ni conversación |
| [#26](https://github.com/davidpd89/ci-sandbox-tmp/pull/26) | Abierta, solo ficha `tasks/16-...` | SQLite, ledger, idempotencia | La caché de lectura no sustituye el ledger de escrituras; no crear una cola general |
| [#41](https://github.com/davidpd89/ci-sandbox-tmp/pull/41) | Abierta, solo ficha `tasks/31-...` | Parsers/cursores ATProto, drift | Esta PR prueba un contrato concreto; #41 puede reutilizar los fixtures sin reemplazar el lector |

Orden sugerido: #11 primero para fijar el contrato v2, luego #41 si toca parser de la misma ruta; #26 es independiente mientras no reestructure la SQLite del collector. #21/#22 pueden seguir en paralelo con adaptadores existentes. Verificar diffs/HEAD de nuevo inmediatamente antes de integrar.

## Seguridad, permisos, acceso y riesgos residuales / BLOQUEOS PARA CLAUDE

- **No se ha probado tráfico vivo** (expresamente prohibido en este encargo); no se requieren tokens ni app passwords. La escucha de posts públicos requiere minimizar su retención, no subir la SQLite, no incluir capturas ni mensajes identificables en documentación y respetar los límites/condiciones de los hosts.
- **Cursor v2 obsoleto**: la documentación del servidor señala ventana limitada (36 h por defecto) y `CursorTooOld` en v2. Este parche falla explícitamente ante HTTP 400 sin resetear el cursor; **no implementa** resync/backfill ni recuperación de brechas. Antes de producción hay que definir cómo notificar y recuperar un hueco de más de 36 h, sin declarar ingesta completa.
- **Cambiar de endpoint**: la nueva barrera compara origen de cursores v2 ya vinculados. No proporciona namespace por host ni migra automáticamente entre instancias. Los estados antiguos sin procedencia no se pueden verificar retrospectivamente; ante dudas usar caché independiente y comprobar cobertura.
- **Dos escritores simultáneos y corrupción de SQLite**: se mantiene la serialización prevista en `bluesky_growth_flow.py` y timeout/WAL. No hay test multiproceso con bloqueo exclusivo del collector; el endurecimiento concurrente pertenece principalmente a #26 y requiere acuerdo para no duplicar.
- **Windows/Linux**: usar resultados reales del workflow. El acceso privado oficial no implica autorización para publicar su historial en el mirror; no se ha transferido material privado.
- **Rate limits / TOS**: la escucha no autentica ni elude límites; el código no debe reintentar 429 sin respetar condiciones del proveedor. La ejecución de follows/replies tiene su propio preflight y aprobación humana.
- **Supply chain**: no se añade dependencia. Al actualizar `websockets` o adoptar SDK, auditar licencias/deps transitivas y advisories antes de bloquear una versión (OWASP).

**Pasos mínimos para Claude/revisor:** (1) consultar HEAD/diff de la PR #11 y `docs/research/bluesky-jetstream-cursor.md`; (2) validar Ubuntu y Windows en el último SHA; (3) ejecutar `python -m pytest tests/test_bluesky_jetstream_collect.py tests/test_bluesky_reply_dedupe.py tests/test_bluesky_write_confirmations.py -q -p no:cacheprovider` sobre checkout aislado (sin credenciales); (4) revisar comportamiento ante `CursorTooOld`, endpoint switch y reinicio forzado; (5) comprobar contra HEAD privado oficial y su suite equivalente antes de cualquier port; (6) confirmar reviews, branch protection y checks; nunca merge automático.

## Matriz de aceptación verificable

| Criterio PR #11 | Prueba, fuente o inspección | Estado a 09-10-2026 |
| --- | --- | --- |
| Ingesta v2 offline y reconexión | `test_v2_stream_reconnect_skip_inclusive_duplicate_and_apply_delete` | PASA en CI Ubuntu; verificar último Windows |
| Checkpoints, reinicio, replay y delete | `test_v2_replay_does_not_resurrect_deleted_post`, `test_v2_restart_uses_persisted_high_water_and_skips_inclusive_replay` | PASA en CI Ubuntu |
| Time_us v1 frente a seq v2 | `test_v1_still_accepts_timestamp_based_replays`, `test_saved_seq_beats_lookback_on_v2` | PASA en CI Ubuntu |
| Errores, 400 fatal y 429 no fatal | `test_v2_invalid_seq_does_not_mutate_cache_or_checkpoint`, `test_v2_rejects_http_400_without_retry_or_cursor_reset` | PASA en CI Ubuntu; falta simulación Retry-After largo |
| DID / handle | `_post_uri` usa DID; `_consume_jetstream_cache` hidrata DID por getProfiles | INSPECCIÓN; falta test de cambio de handle sobre la misma DID |
| No duplicar follows / respuestas | `tests/test_bluesky_reply_dedupe.py`, `test_bluesky_write_confirmations.py` + `action_ledger.py` (sin cambios) | Regresión global Ubuntu, no prueba de ejecución real |
| Compatibilidad Windows/Linux | `validate-social-tools.yml`: Python 3.11 + pytest en ambos | Ubuntu PASA; Windows en comprobación |
| Dos procesos, fallos de disco, caída forzada y brecha >36h | Hay rollback transaccional sintético, no doble escritor ni backfill | PENDIENTE parcial; bloqueo explícito |
| Redes hermanas / contratos compartidos | Diff limitado a collector, tests, ficha y estudio | PASA por inspección del diff; CI global independiente |
| Revisión de reglas TOS, privacidad, licencias | AT Protocol, repositorios con commit fijado, datos sintéticos | PASA documental; sin credenciales ni interacciones |
| Aptitud de merge real | Checks completos, reviews y validación del padre | BLOQUEADA por gate de campaña (ver debajo) |

### Incidencia de CI ajena al frente #11

La ejecución de [campaign gate (PR #11)](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978606460) falló en Ubuntu/Windows aunque sus **15 pruebas internas de metadatos y privacidad pasaron**. El comando `python tools/validate_open_source_campaign.py` devuelve (traza del job):

```text
campaign: 76 children; 3 errors; 0 warnings
FAIL: expected 46 children, got 76
FAIL: missing, extra or duplicate PR numbers
FAIL: protocol index is incomplete or duplicated
```

El gate fallido se ejecutó sobre el *merge ref* anterior; la rama padre avanzó posteriormente hasta `8fa01e6456160d1a01db895290fb288e8d475f83`, cuya versión de `tools/validate_open_source_campaign.py` **ya admite como mínimo 46 hijas originales y un índice continuo de más PR**. El re-run (attempt 2) de [37978839286](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978839286) **volvió a usar el merge ref anterior `c3fcf6f`**, por lo que repitió los tres errores; no sirve como validación de la corrección del padre. Se requiere un **nuevo evento de validación** con una base/merge ref actualizada y revisar su SHA. No corregir el protocolo ni el validador aquí: corresponde a PR #10 actualizar el índice/contrato tras el aumento de hijas y repetir el gate. La rama #11 mantiene `base=research/public-reuse-parent` y no se ha mergeado. `mergeable=true` no implica readiness.

## Retirada, pendientes y aceptación

La incorporación se limita al collector del mirror y sus fixtures; no añade
paquetes, credenciales ni escrituras sociales. Revertir los commits de código
es suficiente para restaurar la interfaz anterior, pero el fallback antiguo
volvería a admitir cursores ajenos y transacciones largas. La clave
`last_seq_stream` puede permanecer en SQLite sin afectar a lectores
anteriores. **Pendientes reales antes de port oficial**: verificar CI exacta
del último HEAD en Windows/Ubuntu, resolver el gate padre #10, simular
desconexiones persistentes y compatibilidad con scheduler privado, además de
diseñar recuperación de `CursorTooOld` y cambios de instancia detrás del
mismo hostname.

## Tercera revisión adversarial: salud de conexión y errores de parseo

Fecha de consulta: 2026-10-09. La segunda lectura detectó que un fallo
permanente de handshake o recv podía acabar devolviendo exit=0 al agotarse la
ventana. En `bluesky_growth_flow.py prepare --deep` eso convierte una sesión
sin ingesta fiable en un paso aparentemente correcto.

Se incorpora `unrecovered_stream_error`: cualquier excepción transitoria
lo activa, una lectura o periodo de conexión estable lo limpia, y si al finalizar
sigue activo el collector termina con código de error. La base de datos mantiene
el último checkpoint, sin ejecutar escrituras remotas. Los HTTP 429/5xx siguen
con reintentos, pero nunca enmascaran una caída no recuperada como éxito.
Se prueba tanto outage permanente como recuperación posterior.

El JSON inválido, secuencia inválida y errores SQLite ya no producen reintentos
infinitos hasta acabar la ventana: `StreamProtocolError` detiene la sesión
sin incluir contenido del frame en el mensaje público; una escritura SQLite
fallida hace rollback y detiene. Los logs de errores de socket conservan solo
la clase, nunca URL ni cuerpo de respuesta. Las excepciones fatales HTTP se
relanzan sin encadenar cuerpo/headers, para no publicar inadvertidamente
información del transporte.

La protección nueva es específica de lectura Bluesky; la lección transversal
es que cada worker WEB/API/MOBILE debe distinguir explícitamente
`sin eventos`, `transitorio recuperado` y `incompleto/no recuperado`.
No se cambia un contrato genérico desde esta PR por no interferir con trabajos
independientes de colas, ledger y observabilidad.

**Tests offline añadidos**:
`test_v2_persistent_handshake_outage_marks_window_incomplete`,
`test_v2_bad_json_fails_with_protocol_error_without_echoing_raw`,
`test_v2_recovery_after_drop_does_not_fail_window`.
La prueba con WebSocket sustituido por transporte sintético no equivale
a validar la infraestructura de Bluesky; el valor es la señal de error y
persistencia verificables. Compatibilidad y retirada idénticas a sección
anterior, sin dependencia adicional.

**Alternativas adicionales revisadas**:
- `skyware-js/jetstream` (TS) quedó archivado el 18-02-2026:
  https://github.com/skyware-js/jetstream. No es candidato de adopción.
- La biblioteca `@bsky/jetstream` mantiene reconexión, señal de error y
  `idleTimeoutMs`, pero exige Node.js e integración ajena a SQLite de Python:
  https://github.com/bluesky-social/bsky/blob/bc6737a4b52dd2458c7aecbc296ec660e068af89/packages/jetstream/README.md.
- El cliente Go oficial registra `Batch.LastCursor` para guardar cursores
  tras persistir el lote y puede hacer transición archive→live. Aporta diseño,
  no un reemplazo Python/Windows sin IPC adicional:
  https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/client.go.
- El problema del cliente Go con cursores timestamp reinterpretados como seq
  fue documentado en issue `#349` (20-09-2026), reforzando pruebas mixtas
  v1/v2: https://github.com/bluesky-social/jetstream/issues/349.

**Hueco no resuelto por esta PR**: integración archive/backfill cuando el
cursor sea demasiado antiguo (`CursorTooOld`) o cambie la infraestructura
v2 detrás del mismo hostname. No reiniciar silenciosamente desde el presente:
se perdería cobertura. Seguirá como trabajo separado con fixtures y
reconciliación auditables. El estado v2 de caches heredadas sin
`last_seq_stream` solo se puede vincular tras observar el primer frame nuevo;
no existe prueba retrospectiva de la instancia que generó el valor.

## Referencias primarias y procedencia

- AT Protocol, [Event Stream](https://atproto.com/specs/event-stream): secuencias monotónicas, cursor tras procesamiento exitoso, errores y HTTP 429 (consultado 09-10-2026).
- Jetstream actual, [especificación v1/v2](https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/docs/README.md): cursor inclusivo, v2 secuencia, v1 microsegundos, ventana de 36 h; [licencia dual](https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/LICENSE-DUAL).
- Jetstream legacy, [README](https://github.com/bluesky-social/jetstream-legacy/blob/8a65de4eda28bed1cafcbcf25b0cd46ac6f2148b/README.md): cursor temporal y recomendaciones de solapamiento.
- Cliente oficial TS, [README](https://github.com/bluesky-social/bsky/blob/bc6737a4b52dd2458c7aecbc296ec660e068af89/packages/jetstream/README.md): no intercambiar cursores v1/v2.
- SDK Python, [pyproject](https://github.com/MarshalX/atproto/blob/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8/pyproject.toml): licencia MIT, matriz de Python y dependencias.
- [OWASP Software Supply Chain Security](https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html), [GitHub Protected Branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).


## Cuarta revisión adversarial: avisos v2 de pérdida de continuidad (09-10-2026)

**Hallazgo respaldado por la lexicon oficial fijada**:
[subscribeEvents.json](https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/lexicons/network/bsky/jetstream/subscribeEvents.json)
y [contrato de cursor](https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/docs/README.md#52-the-v2-stream-networkbskyjetstreamsubscribeevents).

Un cursor heredado en microsegundos puede resultar anterior a la ventana
disponible y **ser recortado sin HTTP 400**: el servidor envía un mensaje
`#info` con `name=OutdatedCursor`. Asimismo un cursor `seq` futuro
puede comenzar directamente en live tras `#info FutureCursor`. El collector
anterior ignoraba ambos avisos porque no eran commits; podía finalizar
satisfactoriamente a pesar de un salto. Los frames terminales
`{"$type":"error", ...}` tampoco eran interpretados explícitamente y
una envoltura legacy v1 podía procesarse a través del endpoint v2.

**Corrección localizada y sin librerías nuevas:** el endpoint v2 exige la
envoltura `message/payload`, rechaza con `StreamProtocolError` ambos
avisos de discontinuidad y los frames `error` terminales, sin incorporar
mensajes remotos a logs. No asume que un socket conectado implique
continuidad. El cursor y los posts válidos ya procesados conservan
checkpoint transaccional; un aviso no adelanta la secuencia. El endpoint
legacy v1 conserva su contrato.

**Pruebas offline, con WebSocket sintético:**
`test_v2_cursor_notices_and_errors_fail_loud_without_mutation` cubre
OutdatedCursor, FutureCursor, error terminal y envoltura v1 imprevista,
verificando ausencia de mutación y de filtración del mensaje remoto.
`test_v2_valid_commit_before_terminal_error_is_checkpointed` verifica
durabilidad del frame válido anterior al error.

**Generalización:** las demás redes deben exponer estados equivalentes
`OK | GAP_DETECTED | TERMINAL_ERROR` para discovery y observabilidad,
pero su parser y sus cursores pertenecen al adaptador de plataforma.
La PR #95 de taste puede importar esta validación v2 o extraer un
módulo Jetstream compartido; no copiar el mismo parser en paralelo.
Mantener separada la máquina de resultados general, que debe ser
independiente del protocolo ATProto.

**Pendiente:** un error explícito no repara el hueco: backfill y handoff
archive→live corresponden a #94. La reversión de estos commits no
requiere migración, pero reintroduce pérdidas silenciosas. Los CI
anteriores no acreditan esta nueva cobertura: revisar el HEAD
final en ambos workflows, Linux y Windows.

## Quinta revisión independiente: salud de reconexión y commits incompletos (10-10-2026)

**Fallo detectado:** al recibir un `asyncio.TimeoutError` de lectura, el collector
ponía `unrecovered_stream_error=False` aunque el WebSocket reconectado
no hubiera entregado ni un frame. Secuencia reproducible sin red:
primera conexión → `OSError`; segunda conexión → abierta pero sin frames
hasta acabar la ventana. Antes informaba éxito; ahora termina con
`ingesta incompleta` y checkpoint conservado. Un stream que nace y
permanece silencioso sin caída previa sigue siendo válido: no se exige
actividad artificial si no existe evidencia de fallo.

**Segundo fallo:** la envoltura v2 de tipo `#commit` se comprobaba, pero
`_normalize_frame` permitía suplir un `payload.seq` ausente con
`message.cursor` y avanzar aunque faltasen DID, tiempo, operación,
colección, rkey o registro necesario. Se validan ahora los campos
esenciales de procesamiento antes de invocar `store_event`, usando
`StreamProtocolError` sin imprimir datos del evento. El contrato
público v2 exige estos campos:
https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/lexicons/network/bsky/jetstream/subscribeEvents.json.
La validación no pretende sustituir un validador completo del lexicon.

**Nuevas pruebas:** `test_v2_reconnect_without_any_frame_is_not_successful_recovery`
y `test_v2_malformed_commits_never_advance_checkpoint`, además de
ajustar `test_v2_recovery_after_drop_does_not_fail_window` para que
la recuperación emita realmente un commit. Todas usan WebSocket/SQLite
sintéticos; no representan prueba viva del servidor ni de un cliente
de Bluesky autenticado.

**Regla reutilizable:** en cualquier red, distinguir `CONNECTED` de
`RECOVERED` o `STREAM_CAUGHT_UP`; ni un timeout de lectura ni una
respuesta parcial justifican que el planificador marque completa una
fuente previamente interrumpida. Implementar esa semántica en el
contrato común de observabilidad y adaptar cada fuente a su mecanismo
de confirmación. No copiar el parser AT Protocol a otras redes.

**Despliegue:** sin esquema nuevo, paquetes nuevos, secretos ni escrituras
sociales. Reversión mediante revert de código/tests/documentación,
sabiendo que ello reintroduce el falso éxito. Comprobar los checks
del SHA final antes de autorizar merge; comparar contra la rama
privada oficial inmediatamente antes de portar. Las PR #94 (backfill)
y #95 (taste) siguen separadas; no abrir derivadas duplicadas.

## Sexta revisión de reutilización: SDK Python Jetstream v2 (10-10-2026)

**Alternativa reevaluada en el mismo commit ya citado de MarshalX/atproto:**
la implementación *sí* incluye un cliente Python nativo Jetstream v2,
`AsyncJetstreamClient`, así como `snapshot()` y `replay()` sobre el
archivo, lo cual no quedaba reflejado en la comparativa inicial.
Fuentes inmutables:
[cliente y cursor](https://github.com/MarshalX/atproto/blob/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8/packages/atproto_jetstream/client.py),
[API archive→live](https://github.com/MarshalX/atproto/blob/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8/packages/atproto_jetstream/jetstream.py)
y [dependencias/licencia](https://github.com/MarshalX/atproto/blob/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8/pyproject.toml).
El paquete integrado `atproto` es MIT y declara Python 3.11/Windows;
no debe confundirse con la distribución homónima independiente
`atproto_jetstream` de otro mantenedor en PyPI.

**Comparación aplicada:** `_JetstreamClientMixin._decode_frame()`
invoca `_track_cursor(seq)` **antes** de entregar el mensaje al consumidor.
Una excepción posterior del callback SQLite podría dejar el cursor interno
más avanzado que los datos durables, por lo que reemplazar el collector
actual sin un adaptador de confirmación/rollback reproduciría una pérdida
que precisamente corrige #11. El SDK también tolera algunos fallos de
decodificación para continuar: esta política no equivale a nuestra detección
explícita de ingestión incompleta. Su ventaja es reducir la cantidad de
código propio de transporte, reconexión y backfill; su coste es mayor árbol
de dependencias (entre ellas `websockets>=15,<18`) y un contrato nuevo de
entrega/ACK. La lectura del archivo exige credencial separada; no se usa
ni configura aquí.

**Decisión:** conservar `websockets + SQLite` y los tests de esta PR,
sin añadir paquetes o mecanismos de cuentas. **En #94**, comparar un
adaptador del SDK para `snapshot/replay` con cliente Go y HTTP/stream
propios mediante fixture offline: commits/delete, brecha de secuencia,
handoff archive→live, excepción del callback entre evento y checkpoint,
reanudación tras reinicio y compatibilidad real Python 3.11/Windows.
Solo adoptar si no adelanta cursor durable por encima de datos escritos
y aporta una mejora verificable de mantenimiento. Evitar abrir otra PR
para lo mismo.

La semántica compartida es **confirmación durable antes de declarar
progreso**, independiente de Bluesky; cada red implementa su ACK en
el adaptador. Ninguna evaluación anterior o actual incluye credenciales
ni acciones reales en redes.
