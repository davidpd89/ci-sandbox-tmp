# CI #29 — Contrato de skills, checkpoints y aprobación, 10-10-2026

## Problema

En `davidpd89/ci-sandbox-tmp` (HEAD inicial `94110ff157a03bc52981101c074a5df37656cb4e`), `tools/mechanical_round.py` contiene `PIPELINES` por red y ejecuta `pre/build/execute/post`; `round_queue.py` ya serializa recursos WEB/API/MOBILE; `content_publisher.py` valida fichas y hace publicaciones por adaptador. No procede sustituirlos por un motor de agentes. En el **privado**, rama `integracion/crecimiento-2026-10`, HEAD consultado `5449513d9b545d0a6a72abf066ab6a779bfdad71`, los prompts `00_OPERATIVO/PROMPTS_GPT_RONDA_2026-10-09.md` separan GPT escritor, Claude revisor y Windows canario; `00_OPERATIVO/RUNBOOK_OPERACION_VERIFICADA.md` aclara el fallback móvil de Instagram y la necesidad de respetar ACK incierto. Este detalle privado se consultó **solo en lectura** y no se copiaron estados, cuentas ni secretos. El espejo puede mostrar una ruta histórica para Instagram: el inspector de pipeline es orientativo, no prevalece sobre el scheduler desplegado.

Falta un **contrato neutral y comprobable** entre investigar, planificar, escribir, validar, aprobar y pasar una intención al ejecutor, con huellas de skills, datos mínimos para replay y distinción estricta de confirmación frente a incertidumbre. Sin él es fácil confundir un prompt, un plan, una aprobación y un ACK en scripts diferentes. Un agente autónomo de publicación añadido aquí duplicaría la cola y el publicador actuales.

## Alternativas

## Licencias y procedencia

Fuente primaria: https://github.com/pytransitions/transitions/tree/bd42b38f3627e6bca7274fb4d9af2e105f75da7c
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/pytransitions/transitions/commit/bd42b38f3627e6bca7274fb4d9af2e105f75da7c

Alternativas adicionales, licencias y revisión de mantenimiento verificadas el 10-10-2026. La licencia anterior corresponde a la fuente primaria de la comparación, **no** a código externo copiado (no hay código externo incorporado).

| Proyecto, referencia inmutable | Licencia | Actividad comprobada | Python 3.11/Windows | Decisión |
| --- | --- | --- | --- | --- |
| [pytransitions/transitions `bd42b38`](https://github.com/pytransitions/transitions/tree/bd42b38f3627e6bca7274fb4d9af2e105f75da7c) | MIT | último commit consultado 09-09-2025; repo no archivado | Python 3 compatible; no probada en Windows aquí | Inspiración de transiciones explícitas; no importar la librería para siete pasos fijos |
| [LangGraph `6aa0afb`](https://github.com/langchain-ai/langgraph/tree/6aa0afba682b0308fbcace31f66fb532978d4dca) | MIT | commit 10-10-2026 | `requires-python >=3.10`, dependencias langchain-core/checkpoint/pydantic; Windows NO ensayado | Checkpoints e interrupciones útiles si se integran agentes reales; sobrecoste sin proveedor/modelo actual |
| [Pydantic AI `4c6fc3c`](https://github.com/pydantic/pydantic-ai/tree/4c6fc3ce0ae28d4a69533ff1aa20695210b03d97) | MIT | commit 10-10-2026 | `requires-python >=3.11`; backend de durabilidad externo opcional; Windows NO ensayado | Modelo y herramientas tipados interesantes; aquí no hay llamada real al LLM que justifique integrar runtime |
| [Prefect `e9bc082`](https://github.com/PrefectHQ/prefect/tree/e9bc08239af12f2bbfccab7a8e15b9f0a0ec6865) | Apache-2.0 | commit 09-10-2026 | `requires-python >=3.11,<3.15`; Windows NO ensayado | Scheduling/reintentos ya cubiertos por `round_queue`; descartado como duplicado |

**Elección:** seguir con la arquitectura actual y reutilizar el **patrón** de FSM/checkpoint; no copiar código de terceros ni añadir dependencias. Coste adicional de instalación: **0** paquetes; no se deben reproducir avisos/locks/estado que ya tiene el sistema. Código local propio, sin archivos externos incorporados y sin obligación de atribución por copia. Para una futura orquestación con tool-calling realmente autónomo, reevaluar LangGraph/Pydantic AI con una prueba contra el sistema existente (no instalar sin esa evaluación).

## Decisión e implementación en esta PR

`tools/agent_workflow.py`: flujo puro de siete etapas `research → plan → write → validate → approval → dispatch → verify`. Cada transición registra `event_id` único, `tool_id` opaco, SHA-256 de evidencia, revisión y, cuando procede, atestación humana o resultado de ejecución. La revisión escrita tiene un fingerprint estable; QA y aprobación deben referirse a **esa misma revisión**. `handoff()` produce **datos**, nunca invoca redes ni ejecutores. `intent_key()` fija una clave de idempotencia por ejecución/red/cola/revisión. La etapa `verify` acaba en **complete**, **failed** o **uncertain** según ACK explícito, sin reintentos automáticos de resultado incierto.

`to_json/from_json`: checkpoint transferible y estricto, versión y checksum, replay de todas las transiciones, rechazo de eventos repetidos, desordenados, campos extra y revisiones obsoletas. El checksum no prueba autoría ni protege frente a modificación maliciosa con nuevo hash: el repositorio de checkpoints debe dar autenticación, control de concurrencia y escritura atómica. No se almacenan texto, prompts, tokens, URLs privadas ni salida bruta: solo hashes y metadatos con IDs restrictivos. Incluso un digest de texto corto puede revelar información por diccionario; custodiar checkpoints.

`inspect_pipeline(network, PIPELINES)` y CLI `python tools/agent_workflow.py --inspect x`: vista **solo lectura** del pipeline existente, basenames de scripts sin argumentos, separando prepare/plan/execute/post. La cola inferida refleja los flags locales y puede no coincidir con `round_queue.py` desplegado; no es una autorización, ni una migración, ni un cambio de calendario. Para Reddit u otra red fuera de `PIPELINES`, la CLI indica `not-managed-by-mechanical_round`; el contrato `Workflow` sí acepta las nueve redes y las tres colas.

## Ejemplo offline de interoperabilidad

```python
from agent_workflow import Workflow, Event, digest
flow = Workflow('run-42', 'threads', 'WEB')
for name in ('research', 'plan', 'write'):
    flow = flow.append(Event(name, name, digest('synthetic-' + name), tool_id='skill:' + name))
draft = flow.events[-1].evidence
flow = flow.append(Event('qa', 'validate', digest('qa-evidence'), revision=draft, tool_id='skill:qa'))
flow = flow.append(Event('human', 'approval', digest('approval-reference'), revision=draft, actor='human:reviewer'))
intent = flow.handoff()  # solamente diccionario: NO PUBLICA
saved = flow.to_json()   # persistencia externa atómica requerida antes de salir
flow = Workflow.from_json(saved)
# Nunca llamar a un ejecutor sin su preflight independiente, reserva y aprobación reales.
```

El adaptador consumidor deberá mantener por su cuenta la identidad real del aprobador, política de antigüedad, registro/ledger y preflight de red, reserva de cola, comprobación de cuenta, dedupe en el servidor, trazabilidad del ACK y controles de interrupción. `human:reviewer` es una etiqueta, **no autentica** a un humano. No usar `handoff()` como permiso operativo. Ninguna acción real se ha conectado.

## Pruebas y línea base

- Antes: 0 módulo de contrato transversal de etapas/checkpoints en el espejo; existen ejecutores y colas, que se conservan.
- Después: 9 redes × 3 canales = 27 combinaciones de esquema, validación de revisión obsoleta, replay idéntico vs conflicto, digest/ID malformados, checkpoint alterado, JSON con claves repetidas, ACK `confirmed/failed/unknown`, ausencia de texto/argumentos privados e inventario de scripts sintéticos.
- Comando local en contenedor Python 3.13.5: `python -m unittest discover -s tests -p test_agent_workflow.py -v`. Resultado al preparar la PR: 14 pruebas (`OK`). El resto de la suite no está disponible en el checkout parcial local; verificar Actions sobre el HEAD real.
- Pendiente Claude: suite completa en Windows 3.11 y Ubuntu, importación real de `mechanical_round.PIPELINES`, rutas y bloqueos de los tres canales, revisión de que el contrato no se considera un permiso de publicar; prueba canario supervisado **solo tras** integración futura y aprobación.

## Segunda revisión adversarial y límites

1. Se detectó inicialmente que ACK desconocido podía quedar etiquetado `complete`; se corrigió a `uncertain` (no cuenta como éxito ni habilita reintento). ACK fallido finaliza `failed`.
2. Se detectó que `json.loads` aceptaba claves duplicadas, incluso con checksum correcto; se añadió rechazo estricto de claves duplicadas y prueba.
3. Se incorporó `tool_id` opaco para documentar qué skill produjo cada evidencia sin guardar salida sensible.
4. No hay persistencia durable proporcionada aquí, compare-and-swap ni token de aprobación verificable. Son responsabilidades del adaptador/almacén y no se presentan como implementadas.
5. No hay integración con publisher/LLM/Edge/Android, ni medición real de tokens ahorrados; el contrato evita repetir evidencias completas en checkpoints pero el ahorro en producción **no está cuantificado**.

## Retirada y activación

Por defecto es **inerte**. No se importa en la ruta de ejecución del scheduler, ni modifica el estado de redes. La CLI solo lee configuración estática. Para un experimento futuro, inyectar el contrato *antes* de un paso humano y guardar checkpoints en almacén provisional segregado, sin habilitar `dispatch` en vivo. Retirada: dejar de importar el módulo y descartar únicamente snapshots sintéticos creados por el experimento; **nunca** resetear locks, ACK inciertos, sesiones, historiales o breakers. No hay migración sobre datos reales.
