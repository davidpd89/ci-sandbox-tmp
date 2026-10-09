# CI: auditar historia transitoria de pushes en ramas de trabajo

## Encargo para GPT

**PR de implementación derivada de la revisión adversarial de [#93](https://github.com/davidpd89/ci-sandbox-tmp/pull/93) (09/10/2026).** Dejar código real, tests Git sintéticos, workflow Windows/Ubuntu Python 3.11, documentación y una segunda revisión adversarial. No hacer merge.

### Brecha reproducible

Un push de dos commits en una rama pública `ci/...`, `research/...` o `feature/...` crea `secrets/transient.json` y después lo borra. El blob sigue publicado en la historia del branch remoto. #93 valida solo `push` a `main`; #89 valida commits alcanzables desde el HEAD **actual** de la PR y no reconstruye pushes previos reescritos. Una rama que luego hace force-push limpio puede ocultar al revisor de PR que la ruta fue expuesta antes.

### Entregable

1. Extender el adaptador de evento de #93 para `refs/heads/*`, sin copiar `git_history_paths` ni `repo_hygiene`. Mantener validación de `before/after/GITHUB_SHA/HEAD`; no usar `HEAD^1`. Coordinar para no duplicar workflows.
2. Capturar y validar **pushes a todas las ramas públicas relevantes**, distinguiendo ramas creadas (SHA cero), actualizaciones FF, reescrituras no FF, merges y pushes de borrado de rama. Documentar expresamente qué *no* garantiza un chequeo posterior al push y cómo identificar eventos omitidos cuando un workflow aún no existe en la ref.
3. Tests con repositorios Git sintéticos: alta-baja dentro del push, múltiples pushes/force-pushes (incluido el SHA anterior inaccesible), rama nueva desde commits antiguos, merge con segundo padre, deuda histórica no tocada, nombres NUL/espacios, error fail-closed cuando no haya objetos. Sin credenciales ni datos reales.
4. Aprovechar Git nativo, actions/checkout fijado, clasificador del mirror; contraste de Git, Gitleaks, Betterleaks y detect-secrets actualizado a fecha de implementación con licencias y compatibilidad Windows/Python 3.11.
5. Evitar ejecuciones redundantes con #2/#88/#89/#92/#93 y conflictos de integración. Permisos mínimos de lectura, `persist-credentials: false`, sin acciones sociales reales.
6. Diferenciar suite de simulación offline y canario supervisado con repositorio sintético. No presentar tests de PR como prueba de webhook `push` real. Anotar costes/rollback/límites.
7. Inspeccionar rama oficial `integracion/crecimiento-2026-10` solamente para contexto necesario; nunca publicar estado o ficheros privados.

### Separación

- **#93:** historia intermedia de push **a main** y núcleo común de Git; no duplicar ese trabajo.
- **#89:** historial de PR en su tip actual.
- **Esta PR:** historia de *eventos push a ramas de trabajo*; detectar exposiciones que preceden a la revisión PR.
- **#87:** secretos por contenido. **#88:** árbol final. **#92:** confianza del verificador.

Base obligatoria `ci/test-campaign-parent`. Claude integra dependencias, sin merge aquí.