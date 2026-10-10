# PR #60 · Máquina de estados multired (10/10/2026)

## Problema
La clasificación de relaciones existente carecía de una transición auditable y persistente; se añade una proyección opcional sin duplicar la política.

## Alternativas
Se comparan los proyectos públicos y la continuidad local en la tabla de esta misma memoria.

## Licencias y procedencia
Fuente primaria: https://github.com/fgmacedo/python-statemachine
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/fgmacedo/python-statemachine/commit/525bcddcc5bb9793ce03d7b3e560f9c2ec0c5ee2
El sistema mantiene el contrato de dominio propio y no incorpora código externo.

## Decisión
Conservar `relationship_policy` y `action_ledger`; añadir una máquina de proyección opcional implementada con sqlite3 y funciones puras.

## Pruebas
Suite sintética `tests/test_relationship_machine.py` en Python 3.11, Ubuntu y Windows, con secuencias generadas y reinicio.

## Retirada
Desconectar los adaptadores opt-in y eliminar la base aislada; ningún CSV ni SQLite operativo cambia.

## Hueco real y procedencia

Se compararon en lectura **mirror** `davidpd89/ci-sandbox-tmp` y el oficial privado
`davidpd89/rrss-davidporto-CODE`, rama `integracion/crecimiento-2026-10`,
sin copiar datos ni credenciales. En ambos, `tools/relationship_policy.py`
tiene blob `ca294952069ebab608de677c93a87101b4033b95` y aporta cooldown
de 21 días, máximo de 3 oportunidades, 7 días de gracia y reciprocidad
de comentarios. También existen `tools/reciprocity.py` (predicción de
followback), `tools/loyalty.py` (notificaciones), `tools/action_ledger.py`
(reservas y resultados) y `tools/unfollow_cleanup.py` (verificación previa
a unfollow). **Ninguno era un historial de estados verificable, transaccional,
reiniciable y común para las nueve redes**. La solución no duplica sus reglas
de negocio ni sustituye sus ejecutores.

Candidato seleccionado: **continuidad + patrón event log/proyección SQLite
de la biblioteca estándar**. Es el contrato de dominio mínimo que falta;
no se copia código externo: se reutiliza `relationship_policy.norm` en la
auditoría de CSV y se preservan `action_ledger`, políticas y colas existentes.
La interfaz `settled_action_event` traduce resultados verificados de
productores WEB/API/MOBILE en eventos; no ejecuta nada. El origen de los
eventos debe aportar el ID estable, la identidad y, para señales observadas,
prueba independiente. Ningún archivo operativo se abre por defecto.

## Alternativas públicas examinadas (commits fijos)

| Alternativa | Licencia, mantenimiento y Python 3.11/Windows | Aplicación evaluada |
| --- | --- | --- |
| [pytransitions/transitions @ bd42b38](https://github.com/pytransitions/transitions/commit/bd42b38f3627e6bca7274fb4d9af2e105f75da7c) | MIT verificada en LICENSE, repo público no archivado, API de estados y extensiones de colas/diagrama; última actividad conocida del repositorio en 2025/2026; Python puro, Windows viable | Motor genérico útil si aparecen reglas jerárquicas, pero no aporta de serie event IDs, prueba cruzada de dos follows, out-of-order ni transacción conjunta estado+evento. Diagramas avanzados necesitan extras. |
| [fgmacedo/python-statemachine @ 525bcdd](https://github.com/fgmacedo/python-statemachine/commit/525bcddcc5bb9793ce03d7b3e560f9c2ec0c5ee2) | MIT verificada, versión [3.2.1 del 01/08/2026](https://pypi.org/project/python-statemachine/), Python >=3.10 (incluye 3.11), wheel `py3-none-any`, repo activo | Excelente alternativa: Mermaid, validación y [ejemplo SQLite/historia](https://python-statemachine.readthedocs.io/en/stable/auto_examples/sqlite_persistent_model_machine.html). Añadir dependencia y adaptar callbacks/configuración para 12 eventos sería más superficie que la tabla de transición local. |
| [Hypothesis @ 1484f6d](https://github.com/HypothesisWorks/hypothesis/commit/1484f6dd4c0a220f68e2698afed29e2a16a3f654) | MPL-2.0; `RuleBasedStateMachine`, mantenido y compatible con Python 3.11/Windows | Interesante para generar y minimizar secuencias adversariales. Optamos por 6.000 secuencias pseudoaleatorias reproducibles con semilla y cero dependencias nuevas. No se afirma equivalencia al shrinking de Hypothesis. |

La licencia de terceros autoriza su uso conforme a sus condiciones; no se
distribuyen copias modificadas ni binarios de esas bibliotecas en esta PR.
La ausencia de dependencia extra evita resolver versiones y extras Graphviz
en Windows. Procedencia precisa: enlaces permanentes anteriores y
[documentación de Hypothesis](https://hypothesis.readthedocs.io/en/latest/stateful.html).

## Entrega y contrato

Archivos:
- `tools/relationship_machine.py`: `step` puro, modelo de 9 estados,
  `RelationshipStore` SQLite, `settled_action_event`, auditor de productores
  CSV solo lectura, visualización textual Mermaid.
- `tests/test_relationship_machine.py`: 6.000 secuencias deterministas,
  comportamiento por las 9 redes x 3 colas, persistencia tras reinicio,
  duplicados, colisión de IDs, transiciones imposibles, concurrencia, crash
  inyectado, adulteración y entradas reales de formato (pero sintéticas).
- `.github/workflows/relationship-state-machine.yml`: prueba en Ubuntu y
  Windows, **Python 3.11**, sin servicios ni cuentas.

Estados: `descubierto → candidato → seguido → reciproco → activo → fiel
→ inactivo → reactivado → cerrado` como trayectoria de ejemplo. También
existen ciclos explícitos `inactivo → candidato` para retry aprobado por la
política existente, `inactivo → reactivado → activo` y eventos de pérdida de
followback. `cerrado` es terminal: no se resucita con un follow repetido.
La reciprocidad, actividad y fidelidad no se suponen por likes ni por contadores;
hay eventos distintos y guardas de confirmación. Reactivación mutua exige
`following` y `follows_me`. `inactivo` puede conservar un follow (baja
actividad) o quedar sin él (unfollow confirmado); esos booleanos impiden
confundir ambos casos.

La identidad de la proyección es `(red, ID estable de cuenta del proveedor)`.
Conservar el dominio en el identificador federado; no fusionar IDs entre
redes. Los tres carriles `WEB/API/MOBILE` se conservan en cada evento,
pero **no** particionan la relación: un follow confirmado desde WEB y una
observación verificada desde API pertenecen al mismo sujeto de esa red.
Event ID estable por productor y fuente; la misma clave repetida con el
mismo contenido no cambia nada, con payload distinto se rechaza.
`occurred_at` es ISO 8601 con zona y se normaliza a UTC; un evento antiguo
no se reinterpreta ni se reordena silenciosamente.

El almacenamiento no tiene ruta por defecto y usa `BEGIN IMMEDIATE`.
Cada evento y su estado se confirman en la misma transacción. La lectura
`verify_replay` comprueba historial, estados anterior/posterior, versiones y
proyección en una misma instantánea. `mermaid_diagram()` devuelve texto,
sin Graphviz ni escritura a disco.

### Adaptadores y reparación de productores

`settled_action_event(network=..., account=..., event_id=..., action=...,
outcome=..., lane=..., occurred_at=...)` devuelve un `Event` **solo para**
`confirmado`, `publicado` o `verified`; cualquier salto, intento o
resultado incierto devuelve `None`. Las observaciones
`followback/activity/loyalty/inactive/reactivation/followback_lost/retry`
requieren adicionalmente `independently_verified=True`. Entonces
`RelationshipStore(path_sintetica).apply(event)` valida la transición.
La orden de unfollow nunca se ejecuta aquí; primero debe existir su
confirmación independiente del ejecutor.

`audit_legacy_rows(network, rows, lane=...)` hace una auditoría sin
escritura de registros de follow/unfollow/bloqueo confirmados. Normaliza
handles con la política existente, muestra anomalías con número de fila
y **no inventa** un follow ausente ni deduce reciprocidad a partir de un
comentario. Ejemplos de anomalía realista: unfollow huérfano, follow
duplicado con otro evento ID, fila de fecha inválida o fuera de orden.
Se conservan incertidumbres, no se borra ni corrige el histórico de forma
automática. Las correcciones productivas por red requieren comparar
evidencias y confirmaciones de los ejecutores durante integración, evitando
afectar cuentas.

## Ejecución reproducible

```sh
python -m unittest discover -s tests -p test_relationship_machine.py -v
python -m py_compile tools/relationship_machine.py
python tools/relationship_machine.py
```

Las pruebas no dependen de Selenium/Playwright, credenciales, red ni datos
personales. Sólo escriben en `TemporaryDirectory()` con cuentas ficticias.
Medida antes/después: antes había **0** eventos/estados transaccionales
de relaciones en el espejo; después se prueban 9 estados, 12 tipos de
eventos, 9 redes y 3 colas, 6.000 secuencias aleatorias controladas y
replay idempotente. No es una medición de incremento de seguidores.

## Migración, activación y reversión

1. Integrar sin activar productores: módulo totalmente opt-in; el sistema
   de follow/cooldown/comentarios original sigue siendo autoridad.
2. En canario supervisado, proyectar sólo un lote **sintético** o una
   copia anonimizadora a una ruta nueva y privada; comparar transiciones
   y anomalías con las confirmaciones fuente sin escribir al origen.
3. En fase posterior, enviar únicamente eventos confirmados de cada
   adaptador a una base nueva, con IDs estables y orden reconciliado.
   Mantener las reglas de `relationship_policy` y `action_ledger` intactas.
4. Reversión: dejar de emitir eventos y retirar el módulo/opción de
   proyección. No existe migración de esquema de los CSV previos ni
   se necesita alterar el SQLite de `action_ledger`.

## Revisión adversarial, segunda pasada

- **Hallazgo y corrección confirmada**: IDs terminados en newline pasaban
  al hacer `strip()` antes de comprobar controles. Ahora el contenido
  original se valida; regresión añadida.
- **Hallazgo y corrección**: replay sólo contrastaba snapshot y secuencia
  de eventos. Ahora comprueba adicionalmente el historial materializado
  (before/after/version) y lee todo en una transacción; tests de adulteración
  de evento y proyección.
- **Hallazgo y corrección**: auditor CSV distinguía `@ANA` y `ana`
  pese al contrato anterior. Ahora reutiliza `relationship_policy.norm`.
- **Hallazgo y corrección**: `sqlite3.connect(':memory:')` crea una base
  nueva por conexión en este diseño. Se rechaza con mensaje preciso.
- **Límite sin ocultar**: no se ha ejecutado un canario de Edge/CDP,
  móvil Android ni red social; CI ejecuta únicamente simulaciones en
  Python 3.11. No existen fuentes universales de followback para todas
  las redes. Las observaciones incompletas se diagnostican, no autorizan
  promoción/desfollow. Las reglas de cooldown y máximo de intentos
  permanecen en `relationship_policy`, no se reimplementan aquí.
- **Límite de secuencias**: las 6.000 son deterministas y no realizan
  shrinking como Hypothesis. El orden de eventos tardíos necesita
  reconciliación por fuente antes del commit. No se declara garantía del 100 %.

## Integración pendiente para Claude

Revisar el HEAD real del oficial y ordenar el encaje con #25 (CRM),
#35 (testing FSM), #57 (ciclo followback) y #59 (memoria de
no reciprocidad). No duplicar sus trabajos. No hubo merges, cambios en
el repo privado ni actividad social. Las verificaciones Windows/Edge/móvil
productivas quedan como canario supervisado posterior, no se presentan
como pruebas realizadas.


## Comprobación adicional adversarial (10/10/2026)

La apertura de una base SQLite preexistente valida el esquema antes de escribir: nombres y orden de columnas, tipos, nulabilidad y claves primarias de ambas tablas. No realiza migraciones implícitas. Una base ajena/incompatible se rechaza con `ValueError`, en lugar de permitir una PK de idempotencia equivocada o fallar a mitad de una transacción. Incluye dos casos de regresión sintéticos para tabla de estado truncada y PK de eventos alterada. Sigue pendiente coordinar la autoridad del ledger de #84; este cambio **no** resuelve los bloqueos de procedencia, exclusión permanente ni seguidor entrante de la revisión previa.

La misma comprobación impide abrir en la proyección un fichero SQLite que contenga la tabla operativa `actions` o la tabla append-only `relationship_events` de #84. Es una barrera contra el uso accidental de dos almacenes independientes en la misma base, no una integración entre ambos.

## Alternativa madura adicional revisada en auditoría final

Se examinó [pyeventsourcing/eventsourcing](https://github.com/pyeventsourcing/eventsourcing) (biblioteca pública no archivada; rama principal 9.5; licencia [BSD-3-Clause](https://github.com/pyeventsourcing/eventsourcing/blob/9.5/LICENSE), verificada; [commit de referencia 575d42c](https://github.com/pyeventsourcing/eventsourcing/commit/575d42c10a821828639b90178ed56703abe9c9f1)). Aporta eventos de dominio versionados, snapshots, control de concurrencia y proyecciones, por lo que es **más completa que la FSM local como infraestructura de event sourcing**, especialmente si el sistema crece. No demuestra por sí misma semántica de reciprocidad de nueve redes, evidencia de listas completas ni integración con ActionLedger. Adoptarla ahora duplicaría el alcance del ledger append-only de #84; se recomienda primero decidir la autoridad única y evaluar la migración con fixtures, en vez de añadir dependencia y una tercera representación de relaciones. No se copia código externo.
