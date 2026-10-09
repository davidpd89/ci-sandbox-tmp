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

La recuperación se hace dentro del mismo lock interproceso ya existente. Solo se elimina la cola posterior al último `\n`; nunca se reescriben filas completas previas. Después se añade cabecera si el fichero queda vacío, se escribe la nueva fila y se hace `flush + fsync`.

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

El workflow del mirror está configurado para Ubuntu y Windows con Python 3.11, pero los commits realizados mediante el conector no han generado una ejecución visible de GitHub Actions para este HEAD. Por tanto, Windows vivo y la suite completa del mirror quedan como validación necesaria para Claude/controlador antes de integrar.

## Segunda revisión adversarial

Se revisó el diff completo después del primer fix. Hallazgo corregido: el test de crash podía bloquearse esperando stdout. Se sustituyó por un fichero de señal y una espera máxima de 5 s.

Supuestos deliberados:

- las filas producidas por `round_queue.py` terminan siempre en salto de línea;
- el esquema actual no introduce saltos de línea embebidos en campos; por eso buscar el último byte `\n` es una recuperación segura para este CSV concreto;
- una fila sin terminador se considera no durable y se descarta antes de continuar.

## Limitación importante

Esto no puede prometer exactly-once de acciones remotas. Existe una ventana inevitable si una red confirma una acción y el proceso muere antes de persistir su fila. El fix garantiza integridad del CSV y evita mezclar/truncar registros previos, pero no convierte una llamada remota y el ledger local en una transacción atómica.

Esa ventana merece un trabajo separado de idempotencia/ledger; no debe ocultarse bajo esta PR.

## Estado de merge

No se hizo merge. La PR queda para revisión e integración por Claude/controlador.
