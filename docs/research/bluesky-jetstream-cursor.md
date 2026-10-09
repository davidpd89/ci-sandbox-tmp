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
| SDK Python `MarshalX/atproto` | MIT; commit [4c17895](https://github.com/MarshalX/atproto/tree/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8) (2026-10-02) | Identidad DID, rich text, XRPC, firehose | Añade `pydantic`, `cryptography`, `libipld`, `zstandard`, etc.; **no elimina** el deber transaccional local | No integrar |
| `@bsky/jetstream` (TypeScript) | Proyecto Bluesky dual MIT/Apache-2.0, repo [bc6737a](https://github.com/bluesky-social/bsky/tree/bc6737a4b52dd2458c7aecbc296ec660e068af89) (2026-10-08) | Reconexión, cursores y abstracciones mantenidas | Node.js/TS y puente entre procesos hacia SQLite de Python; distinto contrato v1/v2 | No integrar |
| Cliente Go del Jetstream oficial | MIT/Apache-2.0; [f42df08](https://github.com/bluesky-social/jetstream/tree/f42df08ba0ca9e4287020139aefbcfe24506d1ef) (2026-10-09) | Referencia de cursor inclusivo, resync v2 y dedupe | Nuevo binario, empaquetado Windows/Linux y capa IPC | No integrar |

Se adaptó conceptualmente el patrón de **high-water monotónico, replay idempotente y checkpoint atómico**; **no se copió código fuente ni fixtures ajenos**. Coste de librerías nuevas: **cero**. Se mantienen `websockets`, `sqlite3` y la interfaz de `read_recent_matches`. No se inventan tiempos ni ahorros de CPU; no hay benchmark de throughput reproducido con el entorno de producción.

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

## Autorrevisión adversarial

1. **Reenvío de una operación antigua después de delete/update.** Antes la clave primaria deduplicaba filas, pero no versiones. Se evita mutar cuando `seq <= last_seq`; tests create/delete/replay y replay tras reinicio.
2. **El collector se cae entre post y cursor.** Una transacción puede retroceder íntegra; el siguiente replay restaura el trabajo no confirmado. Se pone el high-water en el mismo checkpoint SQLite que la caché. Limitación: fallos físicos del disco/corrupción quedan fuera de la prueba actual.
3. **La sesión v2 empieza con cursor timestamp v1.** Mezclar orden numérico entre `time_us` y `seq` impediría seguir el stream; tras el primer frame válido, sustituir por `seq`. Persistir el modo del endpoint sería un endurecimiento posterior si se permiten fuentes alternativas.
4. **No coincidencias durante la escucha.** Un socket lleno de posts descartados también debe hacer avanzar el cursor; el checkpoint ya no depende de `matched`.
5. **ID DID/handle.** El collector construye claves `at://did/collection/rkey`; la resolución mutable del handle ocurre posteriormente en scan. No añadir manejo de alias ni introducir identificadores reales en fixtures.
6. **Regresión transversal.** No se toca `scan_common`, `action_ledger` ni `reply_writer`; los contratos compartidos permanecen. La suite global offline del mirror debe terminar en ambos sistemas para considerarlo apto.

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
- **Cambiar de endpoint**: no se añade todavía namespace por host/versión al valor `last_seq`. No reutilizar una SQLite entre servidores con secuencias no comparables sin una estrategia de migración segura.
- **Dos escritores simultáneos y corrupción de SQLite**: se mantiene la serialización prevista en `bluesky_growth_flow.py` y timeout/WAL. No hay test multiproceso con bloqueo exclusivo del collector; el endurecimiento concurrente pertenece principalmente a #26 y requiere acuerdo para no duplicar.
- **Windows/Linux**: usar resultados reales del workflow. El acceso privado oficial no implica autorización para publicar su historial en el mirror; no se ha transferido material privado.
- **Rate limits / TOS**: la escucha no autentica ni elude límites; el código no debe reintentar 429 sin respetar condiciones del proveedor. La ejecución de follows/replies tiene su propio preflight y aprobación humana.
- **Supply chain**: no se añade dependencia. Al actualizar `websockets` o adoptar SDK, auditar licencias/deps transitivas y advisories antes de bloquear una versión (OWASP).

**Pasos mínimos para Claude/revisor:** (1) consultar HEAD/diff de la PR #11 y `docs/research/bluesky-jetstream-cursor.md`; (2) validar Ubuntu y Windows en el último SHA; (3) ejecutar `python -m pytest tests/test_bluesky_jetstream_collect.py tests/test_bluesky_reply_dedupe.py tests/test_bluesky_write_confirmations.py -q -p no:cacheprovider` sobre checkout aislado (sin credenciales); (4) revisar comportamiento ante `CursorTooOld`, endpoint switch y reinicio forzado; (5) comprobar contra HEAD privado oficial y su suite equivalente antes de cualquier port; (6) confirmar reviews, branch protection y checks; nunca merge automático.

## Referencias primarias y procedencia

- AT Protocol, [Event Stream](https://atproto.com/specs/event-stream): secuencias monotónicas, cursor tras procesamiento exitoso, errores y HTTP 429 (consultado 09-10-2026).
- Jetstream actual, [especificación v1/v2](https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/docs/README.md): cursor inclusivo, v2 secuencia, v1 microsegundos, ventana de 36 h; [licencia dual](https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/LICENSE-DUAL).
- Jetstream legacy, [README](https://github.com/bluesky-social/jetstream-legacy/blob/8a65de4eda28bed1cafcbcf25b0cd46ac6f2148b/README.md): cursor temporal y recomendaciones de solapamiento.
- Cliente oficial TS, [README](https://github.com/bluesky-social/bsky/blob/bc6737a4b52dd2458c7aecbc296ec660e068af89/packages/jetstream/README.md): no intercambiar cursores v1/v2.
- SDK Python, [pyproject](https://github.com/MarshalX/atproto/blob/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8/pyproject.toml): licencia MIT, matriz de Python y dependencias.
- [OWASP Software Supply Chain Security](https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html), [GitHub Protected Branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
