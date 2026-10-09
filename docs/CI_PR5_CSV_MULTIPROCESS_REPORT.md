# PR #5 — CSV multiproceso: diagnóstico, fix y revisión adversarial

Fecha de revisión: 2026-10-09.

## Alcance y contexto leído

- PR objetivo: https://github.com/davidpd89/ci-sandbox-tmp/pull/5
- Base confirmada: `ci/test-campaign-parent`.
- Rama confirmada: `ci/csv-multiprocess-recovery`.
- El cuerpo actual de la PR no contiene una sección literal `## Encargo para GPT`; se tomó como contrato el cuerpo completo de la PR.
- `docs/open-source-scouting/PROTOCOL.md` no existe en esta rama.
- Se leyó `docs/CI_TEST_CAMPAIGN.md`.
- Como contraste mínimo del repositorio oficial se leyó `tools/round_queue.py` de `davidpd89/rrss-davidporto-CODE@integracion/crecimiento-2026-10`. No se modificó el repo oficial.

## Fallo reproducido

El primer intento de la PR serializaba correctamente a los escritores, pero no recuperaba una escritura interrumpida. Si un proceso moría dejando una fila sin terminador de línea, el siguiente proceso abría en append y pegaba su fila a esa cola incompleta. Resultado: una fila mezclada/malformada, justo el caso que la PR pretende evitar.

También había dos debilidades de test:

1. el caso de lock denegado podía consumir los 15 s completos de timeout;
2. la primera versión del test de muerte del propietario esperaba con `stdout.readline()` sin timeout y podía colgar CI si el hijo fallaba antes de anunciar el lock.

## Implementación

Commits propios:

- `0e2847d91bad357310670dcc1d3e271af963e935` — recuperación conservadora de cola CSV incompleta, escritura binaria durable y validación de ancho de fila;
- `02d19d0a88f361640b767637e666cce1b6808069` — regresiones para cola parcial, preservación del estado previo, muerte del lock holder y exact-once entre procesos;
- `532acfacf1bd1d68e90e4235c85bd05e6de719a5` — segunda revisión adversarial: el probe de crash pasa a señal por fichero con espera acotada.

La recuperación se hace dentro del mismo lock interproceso ya existente. Se conservan los registros completos, incluso la última fila válida sin terminador de línea; si el tail no supera validación estructural, se descarta únicamente ese tail. Después se añade cabecera si el fichero queda vacío, se escribe la nueva fila y se hace `flush + fsync`.

En la segunda auditoría se amplió el alcance para cerrar cuatro fallos de interacción que la revisión inicial no detectó:

1. Lecturas de `done_today()` y `retry_snapshot_today()` sincronizadas con escritores, usando el guard y mutex existentes;
2. snapshot de cuotas **después** de adquirir el lock de la cadena, para evitar replays por contabilidad obsoleta entre propietario anterior y nuevo;
3. CSV histórico de tres columnas legible, pero escritura incompatible rechazada sin mutarlo; también se preservan filas legacy sin salto final;
4. arranque desde directorio ausente, lectura de cabecera corrupta con error explícito y rechazo de saltos embebidos que comprometerían la recuperación por líneas.

También se impide que un fallo al cargar el ledger relance una cola no inicializada, y se evita unir un heartbeat cuyo `start()` hubiera fallado.

## Reutilización de código público

Se compararon alternativas públicas actuales antes de ampliar la implementación propia:

| Proyecto | Estado a 2026-10-09 | Licencia / Python | Windows/Linux | Decisión |
| --- | --- | --- | --- | --- |
| wolph/portalocker | 4.4.0, publicada 2026-09-19; repo activo | BSD-3-Clause; Python >=3.10 | Sí; lock exclusivo Windows sin dependencia extra | No añadir: resolvería el lock, pero la rama ya posee un guard nativo compartido con otros locks y seguiría faltando la reparación de cola CSV |
| tox-dev/filelock | 4.0.12, publicada 2026-10-05; commits 2026-10-08 | MIT; Python >=3.10 | Sí; LockFileEx en Windows y flock en Unix | No añadir: librería sólida y mantenida, pero supone una dependencia nueva para un primitive que el repo ya implementa; no resuelve por sí sola la cola CSV truncada |
| harlowja/fasteners | 0.20, actividad reciente 2025-09 | Apache-2.0 | Sí; fcntl / msvc locking | No añadir: compatible, pero menos reciente y mismo coste de dependencia |

Referencias: https://github.com/wolph/portalocker, https://pypi.org/project/portalocker/, https://github.com/tox-dev/filelock, https://pypi.org/project/filelock/, https://github.com/harlowja/fasteners.

No se copió código de terceros. Gana la continuidad de `_recovery_guard`: cero dependencia nueva, misma semántica ya usada por la cola y parche menor. La parte nueva específica de CSV —recortar una cola no terminada— no la cubren esas librerías.

## Pruebas ejecutadas

No se hicieron acciones reales en redes, ni se usaron credenciales o datos operativos.

En Linux local aislado se ejecutó un harness con la misma lógica modificada:

- `python -m compileall -q round_queue.py test_csv.py`;
- 5 regresiones focales: cola parcial, lock denegado sin mutación, muerte abrupta del lock holder, 6 procesos concurrentes exact-once y rechazo de ancho inválido: **5/5 OK** en 3,263 s;
- estrés adicional: **3/3 rondas**, 8 procesos por ronda, una cabecera, 8 filas únicas y 10 columnas por fila: **OK**.

La consulta inicial de CI filtraba solo ejecuciones de tipo pull_request y omitía las de tipo push: era un error de observabilidad del informe, no ausencia de CI. Se verificó el workflow de push por la API de GitHub Actions.

**Validación del código corregido** (commit `392304a3c74c2d16d8256dede5cfd37dee68dbc6`): https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37982561225

- Ubuntu, Python 3.11: **1707 passed, 8 skipped, 8 deselected, 665 subtests passed**, workflow OK;
- Windows, Python 3.11: **1710 passed, 5 skipped, 8 deselected, 665 subtests passed**, workflow OK;
- no navegador, móvil ni red social real; procesos Python reales y archivos temporales sintéticos;
- las 8 exclusiones del workflow son las ya declaradas en la línea base de `docs/CI_TEST_CAMPAIGN.md`, no una eliminación de cobertura creada por esta PR.

La prueba de Windows real del CSV y su lock está completada en GitHub Actions. Queda fuera de alcance un canario supervisado del entorno operativo real (Edge/móvil/Windows del usuario), no necesario para estas regresiones puramente de fichero.

## Segunda revisión adversarial

Se revisó el diff completo después del primer fix. Hallazgo corregido: el test de crash podía bloquearse esperando stdout. Se sustituyó por un fichero de señal y una espera máxima de 5 s.

Supuestos deliberados:

- las filas producidas por `round_queue.py` terminan siempre en salto de línea;
- el esquema actual no introduce saltos de línea embebidos en campos; por eso buscar el último byte `\n` es una recuperación segura para este CSV concreto;
- una fila **válida** sin terminador se preserva y se termina antes del siguiente append; solo se descarta la cola no validable;
- se admite la lectura del formato histórico `fecha,red,estado`, pero se rechaza escribir registros de diez columnas bajo esa cabecera;
- no se añaden separadores o IDs ficticios de acciones remotas; una escritura CSV exitosa no acredita una transacción remota atómica.

## Limitación importante

Esto no puede prometer exactly-once de acciones remotas. Existe una ventana inevitable si una red confirma una acción y el proceso muere antes de persistir su fila. El fix garantiza integridad del CSV y evita mezclar/truncar registros previos, pero no convierte una llamada remota y el ledger local en una transacción atómica.

Esa ventana merece un trabajo separado de idempotencia/ledger; no debe ocultarse bajo esta PR.

## Estado de merge

No se hizo merge. La PR queda lista para revisión de código por Claude/controlador: el workflow offline sobre el código reparado fue verde en Ubuntu y Windows. Esto no equivale a certificar ejecución remota, recuperación ante corte físico de energía o exactly-once de acciones reales.


## Follow-up

No se abrió una PR nueva para la ventana «acción remota confirmada -> ledger durable» porque ya existe una PR abierta que cubre colas, idempotencia y recuperación: https://github.com/davidpd89/ci-sandbox-tmp/pull/26. Abrir otra habría duplicado trabajo, contra el mandato de esta ronda.


## Segunda auditoría ampliada (09-10-2026)

El objetivo no era solo pasar pruebas propias: el primer run de la revisión amplificada falló por una incompatibilidad real con `tests/test_r8_atomic_chain_lock.py::test_partial_ledger_from_integration_is_preserved`, que utiliza el formato CSV histórico de tres columnas. Se corrigió la lectura legacy sin mezclar esquemas en escritura.

Una ejecución posterior detectó un error de sintaxis introducido al refinar la validación de colas legacy. Se corrigió y se volvió a lanzar la suite; el run `37982561225` terminó **verde en ambos sistemas**. Es importante conservar esta historia: el control adversarial y la CI encontraron fallos que la inspección individual no había anticipado.

Fuentes técnicas contrastadas a fecha 09-10-2026: portalocker 4.4.0 (BSD-3-Clause, https://pypi.org/project/portalocker/); filelock 4.0.12 (MIT, https://pypi.org/project/filelock/); fasteners (Apache-2.0, https://github.com/harlowja/fasteners); SQLite WAL (https://www.sqlite.org/wal.html). La elección de seguir con `_recovery_guard` de la base es deliberada: reutiliza un guard ya probado y evita dependencia ajena; un ledger SQLite transaccional sería otra arquitectura y encaja con el trabajo ya abierto sobre idempotencia de la PR #26.

**Limitación residual concreta:** no se conoce de forma atómica si una acción remota se confirmó justo antes de que fallara la persistencia local. Ni el lock CSV ni `fsync` pueden resolverlo por sí solos. Claude debe conciliar ese contrato con la capa de ledger/acción confirmada del repositorio oficial antes de interpretar una repetición como segura.
