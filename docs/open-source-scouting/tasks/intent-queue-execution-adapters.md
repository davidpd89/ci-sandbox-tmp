# Puentes de ejecución para la bandeja de intenciones común

## Encargo para GPT

**Origen:** [PR #26](https://github.com/davidpd89/ci-sandbox-tmp/pull/26) incorpora `tools/intent_queue.py` con SQLite WAL, claves idempotentes, lease/fence, frontera duradera pre-I/O, estados inciertos y reconciliación. **Esta tarea es implementación posterior, no repetir la investigación del almacén.** Depende de aprobar #26.

### Hueco concreto

El contrato de #26 es opt-in y no convierte por sí solo `round_queue`, `reply_queue`, `content_queue`, `action_ledger` ni los despachadores reales en productores de la bandeja. Integrar sin un puente explícito podría duplicar el envío o confundir un resultado desconocido con un fallo. Evitar mezclar las funciones con los adaptadores de observaciones de #107/#108.

### Implementación obligatoria

1. Leer `docs/open-source-scouting/PROTOCOL.md`, #26 HEAD actualizado y el código de las nueve redes del repositorio privado `davidpd89/rrss-davidporto-CODE` solo para contexto, sin trasladar credenciales ni estados reales al público.
2. Adaptador **genérico** productor → `enqueue` con claves derivadas de evento lógico estable, fecha de caducidad de destino a partir de metadatos fiables; declarar evidencias ausentes, nunca inventarlas. Transporte configurable por ejecución, colas WEB/API/MOBILE independientes.
3. Adaptador **genérico** `claim→mark_dispatched` que persista antes del primer I/O, con callback **falso/simulado** por defecto (sin entrar a redes). Encolar X `like/favourite` debe seguir vetado; no ejecutar acciones reales en esta PR.
4. Adaptador de acuse/conciliación basado en evidencia remota válida para `confirmed`, `not_applied`, `unknown`, sin reintentar uncertain automáticamente. Correlacionar con el ledger histórico sin alterar su esquema en esta fase.
5. Test matrix sintética para X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok, Instagram × WEB/API/MOBILE según canales compatibles; carreras entre procesos, reintentos de productor, dos workers, crash antes/después de dispatch, ACK tardío, edad máxima, ningún API/Edge/ADB real.
6. Investigación pública actual de adaptadores/outbox compatible Windows/Linux Python 3.11 (SPDX, fechas, SHAs, comparativa), código, tests, informe `docs/research/`, CI verde y segunda revisión adversarial. Migración reversible con flag **desactivado**; canario supervisado reservado a Claude. No merge.

### Criterios de aceptación

La misma acción lógica reaparece tras reinicio sin segunda intención ni segundo despacho automático; la falta de ACK no genera reintentos; cada red/canal dispone de una evidencia de compatibilidad o un límite explícito. Ni llamadas sociales, ni credenciales, ni datos reales. Documentar rendimiento sintético y claramente separar canario pendiente.
