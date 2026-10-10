# PR #26 — Bandeja de intenciones, fences y recuperación

Fecha de comprobación: 2026-10-10. Alcance: **nueve redes; tres canales WEB, API y MOBILE**. Implementación opt-in, sin actividades en cuentas, sin migración de estado real.

## Problema

### Diagnóstico sobre código existente

Inspeccionados en el espejo `tools/action_ledger.py`, `tools/round_queue.py`, `tools/reply_queue.py`, `tools/content_queue.py`, `tools/reply_state_lock.py`, `tests/test_action_ledger.py`. Se contrastó el árbol de `davidpd89/rrss-davidporto-CODE` en `integracion/crecimiento-2026-10`: además dispone de `tests/test_r51_round_replay.py`, `tests/test_pr60_queue_recovery.py`, `tests/test_r8_atomic_chain_lock.py`, `tests/test_r8_corrupt_queue_json.py`, `00_OPERATIVO/ROBUSTEZ_R6_3_COLAS_CANARIO.md` y propuestas `.github/pr-scopes/2026-10-26-round-queue.md` / `2026-10-28-reply-queue-reliability.md`, ausentes en el espejo. No se trasvasa material privado al público.

**Problema comprobable:** el ledger reserva (kind,target) y protege duplicados, pero un `reserved` caducado puede reintentarse sin saber si el proceso inició la operación remota. Por otro lado, las colas JSON/CSV/Markdown registran trabajo sin contrato uniforme de paso de «pendiente» a «despachado». La PR no cambia el ledger ni las colas existentes: aporta un **contrato SQLite autónomo** para una adopción graduada. No se confunde confirmación faltante con fallo ni se reintenta automáticamente lo incierto.

## Alternativas

### Investigación de reutilización (refs inmutables y licencias)

| Alternativa | Ref verificada | Licencia / mantenimiento | Compatibilidad y decisión |
| --- | --- | --- | --- |
| [persist-queue](https://github.com/peter-wangxu/persist-queue/tree/b4fb6d186e375850b2d9ac49fc635779be95f173) | `b4fb6d186e375850b2d9ac49fc635779be95f173` (2025-10-25; repositorio actualizado 2026-01-08) | BSD-3-Clause, activo | Compatible Python 3.11/Windows. SQLiteAckQueue útil, pero la API de ACK no certifica si hubo efecto remoto. No se añade dependencia por ese hueco. |
| [Huey](https://github.com/coleifer/huey/tree/817e0fdddf356f1129764bae7083628ff4363729) | `817e0fdddf356f1129764bae7083628ff4363729` (2026-10-03) | MIT, mantenido; SQLite y retries | Compatible 3.11 (biblioteca estándar para SQLite). Ofrece worker y scheduling, sobredimensionado frente a un ledger existente y no resuelve la incertidumbre remota sin adaptación. |
| [litequeue](https://github.com/litements/litequeue/tree/9e286af166f1c483057e28ab5fb45e1c38943f21) | `9e286af166f1c483057e28ab5fb45e1c38943f21` (2026-07-31) | MIT, activo | Requisito explícito `Python >=3.12`; descartado para 3.11. Referencia conceptual de `claim_id` como fence, **sin copiar código**. |
| [taskq](https://github.com/ifleonlabs/taskq/tree/5c55eeab574c1f973ee4ef24ba541b476c960f24) | `5c55eeab574c1f973ee4ef24ba541b476c960f24` (2026-06-04) | Licencia declarada MIT en README; metadato SPDX de GitHub ausente, revisar antes de copiar | Patrón `BEGIN IMMEDIATE` de despacho y retries; no se copia. Comunidad y mantenimiento aún poco demostrados. |
| `ActionLedger` propio | espejo `95fdd37d40bb14cff63282f1468877a65eb13170` | propio, ya desplegado | Gana como fuente del resultado de interacción; no sustituir. Falta delimitar «antes/después» de I/O. |

## Licencias y procedencia

Fuente primaria: https://github.com/peter-wangxu/persist-queue/tree/b4fb6d186e375850b2d9ac49fc635779be95f173
Fecha de consulta: 2026-10-10
Licencia SPDX: BSD-3-Clause
Referencia inmutable: N/A (sin codigo incorporado)

No se incorporan archivos de los candidatos; los hashes, licencias y descartes están en la tabla anterior. La bandeja nueva es código original sobre SQLite de biblioteca estándar.

## Decisión

**Elección:** ampliar mediante composición con SQLite estándar, sin reescribir el ledger existente ni incluir librería adicional. Inspiración de patrones documentados (transactional claim y fencing) no es copia de archivos. Atribución arriba. Se reduce el coste operativo: **0 dependencias, 0 procesos extra obligatorios**, misma tecnología que `ActionLedger`.

## Contrato y límites

- `enqueue(network, channel, intent_key, kind, target, payload, due, expires_at)`: persistencia y deduplicación estricta `(network, intent_key)`. El productor define la clave **estable**; un reintento con cuerpo o metadatos incompatibles levanta `IdempotencyConflict`.
- `claim(channel, owner)`: `BEGIN IMMEDIATE`, selección por prioridad y fecha, incremento monotónico de fence, lease por canal. Cada red puede elegir el canal según su transporte; no se fija X a WEB o Facebook a API.
- `mark_dispatched(ticket)`: **commit obligatorio antes de toda petición o click**. Si el proceso cae tras esa frontera, `recover` mueve a `uncertain`, nunca a disponible. Si cae antes, recola de forma segura. Ventana «commit antes de I/O pero no se realizó» produce un incierto conservador, no un doble envío.
- `confirm(ticket, evidence)`: exige evidencia positiva y fence vigente; acepta confirmación tardía del mismo token, no la de otro propietario.
- `no_effect(ticket, evidence)`: solo para rechazo definitivamente sin efecto. Reintento con backoff exponencial y jitter acotado o `dead` por intentos/edad.
- `reconcile(item_id, verdict, evidence)`: exclusivamente para `uncertain`. `unknown` no libera; `confirmed` cierra; `not_applied` recola o manda a dead-letter. La llamada **no consulta por sí sola la red**, debe alimentarla un adaptador con evidencia verificable.
- `expires_at` es el deadline provisto por el adaptador, calculado desde la fecha del post/perfil para evitar necroposting. No se infiere una fecha inexistente. Si expira **antes** del despacho, va a `dead`. Un despacho ambiguo anterior permanece incierto.
- No enviar passwords, cookies, tokens o datos privados al payload/evidencia. SQLite local, no cifrado. No hay garantía de exactly-once frente a fallos externos sin idempotencia remota; se promete exclusión transaccional **local**, y at-most-once *auto-retry* después del límite de despacho.

## Pruebas

### Despliegue gradual y retirada

1. **Pruebas sintéticas** en `tests/test_intent_queue.py`: `python -m pytest tests/test_intent_queue.py -q`. Se incluyen 9 redes, 3 canales, doble consumidor, reintento de productor, fence, ACK tardío, fault injection con `os._exit`, conciliación, TTL, DLQ, jitter y aislamiento.
2. El módulo **no se activa** automáticamente. Piloto: emitir `intent_key` desde una sola ruta offline, comparar número de candidatos/ACK con ledger; activar adaptador en un canario supervisado con verificación de estado remoto antes de cualquier reintento dudoso.
3. Medir `unconfirmed / dispatched`, `claimed expiradas`, duplicados suprimidos, latencia `enqueue→claim`, recola segura y volumen confirmado por red/canal. Aún **no hay métrica de mejora productiva**: ninguna red real fue tocada.
4. Retirada: desactivar la adaptación; conservar el fichero SQLite para auditoría/exportación; no borrar ni reescribir `ActionLedger` ni CSV. El esquema está aislado en una base nueva; no hay migración automática o irreversible.

## Retirada

La integración está desactivada de fábrica y no escribe en el estado del sistema productivo. Para revertir un canario: retirar el adaptador del productor/consumidor, conservar el archivo SQLite para auditoría, comprobar que los ejecutores originales siguen usando ledger y locks previos. Nunca migrar automáticamente pendientes inciertos a acciones reintentables. Responsable y autorización final: Claude/controlador, tras revisión del código oficial.

## Segunda revisión adversarial

- Riesgo clásico de stale ACK: bloqueado con `fence` y propietario en todas las transiciones del ejecutor.
- Doble productor con igual clave y distinto contenido: rechazo, jamás sobrescritura silenciosa.
- Crash antes/después del dispatch: `claimed` recuperable; `in_flight` incierto. Reconciliación manual/evidencial.
- Deadlines: no ejecutar un objetivo caducado; nunca convertir en `dead` un dispatch ambiguo.
- Límites: solo contrato/cola offline; no enchufado a ejecutores, porque conectarlos a red sin canario y pruebas de Windows/Edge/móvil daría falsa garantía. Faltan canario supervisado, medición de carga real, recuperación ante corte de disco y verificación de la fuente remota. El servidor CI Ubuntu/Windows debe confirmar compatibilidad; ninguna prueba local sustituye esos equipos.

## Antes/después verificable

Antes: no existe `tools/intent_queue.py` ni control por fence de paso **pre-I/O** en las tres colas compartidas. Después: nuevo módulo estándar, 0 dependencias, invariantes reproducibles (1 ganador por intención; 0 redespachos automáticos de incertidumbre; reintento seguro para no enviados); pruebas offline. Esto **no significa** reducción demostrada de duplicados reales ni mejora de throughput en producción.
