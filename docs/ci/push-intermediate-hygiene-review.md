# PR #93 — higiene del historial intermedio de `push`

Auditoría y segunda revisión adversarial: **09/10/2026**. Rama: `ci/push-intermediate-commit-hygiene`; base: `ci/test-campaign-parent`. No se ha hecho merge ni realizado ninguna acción social.

## Contrato ejecutable

1. `tools/push_commit_hygiene.py` lee `GITHUB_EVENT_PATH` (JSON local de GitHub), valida SHA completos `before` y `after`, coincidencia de `after` con `GITHUB_SHA` y HEAD, además de `refs/heads/main`. No interpola los datos del evento en shell.
2. `tools/git_history_paths.py` aporta un **núcleo reutilizable para #89**: `commits_in_range`, `touched_paths`, `scan_history`. Ejecuta Git nativo (`rev-list --missing=error --full-history --topo-order --parents`; `diff-tree -r --no-renames --no-ext-diff --no-textconv -z --diff-filter=AMT`), no inventa parser de Git ni lee blobs o contenido.
3. En merges, compara rutas contra **todos los padres** e interseca resultados para no marcar por mera herencia un fichero histórico. Los commits incorporados desde el segundo padre están también en el rango alcanzable y se inspeccionan. Detecta altas, modificaciones y typechanges; ignora borrados puros. Alta seguida de borrado queda registrada. `repo_hygiene.forbidden_path` es la política compartida entre redes, sin duplicación de listas.
4. Rango FF: commits alcanzables desde `after` pero no `before`. Force-push no FF: misma diferencia de alcanzabilidad, sin heurística de merge-base. Primera creación con `before` cero: **todo el historial alcanzable** (no basta inspeccionar el árbol final). Ausencia de `before`, checkout superficial, errores Git, diferencias de SHA, rango vacío, SHA no válidos o más de 20.000 commits producen **exit 2**, nunca falso aprobado. Exit 1 = infracciones, 0 = correcto.
5. Logs de hallazgos: solo SHA abreviado y contador; nombres y contenidos ocultos, máximo 30 líneas de commits. El detector no hace operaciones reales en redes, ni requiere credenciales, ni escribe en Git.

## Integración de CI

Workflow nuevo e independiente: `.github/workflows/push-intermediate-hygiene.yml` para no sustituir los workflows de #2, #88 o #89. En cada PR ejecuta tests Git sintéticos en **Ubuntu y Windows, Python 3.11**. En `push` a `main`, además revisa el historial del evento con `fetch-depth: 0`, sparse checkout `tools`, permiso `contents: read`, `persist-credentials: false` y acciones fijadas a SHA. `workflow_dispatch` no certifica un push.

[CI de regresión #93](https://github.com/davidpd89/ci-sandbox-tmp/actions/workflows/push-intermediate-hygiene.yml) y [run verde de Ubuntu/Windows en 4b9794d](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37989550131) (antes de ampliar a 22 tests; revisar la CI del último HEAD). La comprobación real de `push-history` de main no se ha ejecutado, porque **esta PR no se fusiona**.

## Contraste de código público (09/10/2026)

| Alternativa | Licencia / actividad / Windows y Python 3.11 | Decisión |
| --- | --- | --- |
| [Git rev-list](https://git-scm.com/docs/git-rev-list) y [diff-tree](https://git-scm.com/docs/git-diff-tree) | Git GPL-2.0 con excepciones; activo, preinstalado Windows/Ubuntu, invocable desde Python 3.11 | **Reutilizado por CLI**, ninguna implementación propia de DAG/diff |
| [actions/checkout](https://github.com/actions/checkout) | MIT; oficial y activo; documentación confirma `fetch-depth: 0` y sparse checkout en Windows/Linux | **Reutilizado** con pin SHA; fetch de DAG completo |
| [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks/releases) | MIT; release v8.30.1 marzo 2026, binarios Windows/Linux; Go | Escáner de *contenido*, complementa #87, no clasifica rutas como `metricas.csv` |
| [betterleaks/betterleaks](https://github.com/betterleaks/betterleaks/releases) | MIT; estable 1.9.0 (29/09/2026), RC 2.0.0-rc.1 (30/09/2026); Go Windows/Linux | Contenido/credenciales, CLI en transición. No conviene introducirlo para un escaneo de rutas |
| [Yelp/detect-secrets](https://github.com/Yelp/detect-secrets/releases) | Apache-2.0; 1.5.0 incluye Python 3.11, multiplataforma | Baselines/contenido, mayor carga sin sustituir el clasificador existente |
| [PR #89](https://github.com/davidpd89/ci-sandbox-tmp/pull/89) | Código interno de historial de PR, todavía en rama separada | Unificar su `changes()` con `git_history_paths.touched_paths()` en integración, sin copiar políticas |

Se comprobó el repositorio oficial privado `davidpd89/rrss-davidporto-CODE` en `integracion/crecimiento-2026-10` para el contexto. No se transfirió código privado innecesario. No se copió código ajeno, por lo que no se necesitan nuevas obligaciones de redistribución de componentes.

## Evidencia, revisión A y B

- Suite local real: **24 tests** con repos Git sintéticos efímeros en Linux, Git 2.47.3, Python 3.13.5; resultado: **OK**. La suite de **17 tests iniciales** se ejecutó y concluyó satisfactoriamente en GitHub Actions Ubuntu y Windows con Python 3.11, [run 37989550131](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37989550131).
- Casos: alta-baja dentro del push con delta neto vacío; tres commits inocuos; deuda histórica no tocada y modificada; renombrado; borrado puro; cambio a gitlink; segundo padre de merge; merge con deuda heredada; resolución de merge; historia divergente, nueva rama y raíz sensible; límite de commits; shallow real y simulado; `before` perdido; igualdad before/after; entradas inválidas y SHA discordantes; nombres con espacios/salto de línea NUL; mayúsculas Windows; CLI sin fuga de rutas.
- Revisión adversarial 1: el diff final no detecta alta-baja; se corrigió pasando a revisión del DAG. `HEAD^1` es semántica de merge PR, no de push. En merges, un diff contra un solo padre marca deuda heredada: corrección intersección de rutas y recorrido de la segunda rama.
- Revisión adversarial 2: se comprobó historial incompleto con **clon superficial real** además del mock, force-push **sin ancestría compartida**, revisión de commit raíz, no aprobación en rango vacío y manejo de rutas imposibles en NTFS mediante `-z` sintético. El test con `git checkout --orphan` requirió forzar `git rm -rf`, porque un index staged recién creado no se elimina con `git rm -r`; se corrigió el fixture.
- Tercera pasada adversarial: se deshabilitó `GIT_NO_LAZY_FETCH` para impedir recuperación implícita de objetos desde un remoto, `GIT_TERMINAL_PROMPT=0` para evitar prompts, y `GIT_NO_REPLACE_OBJECTS=1` para que refs de sustitución de Git no alteren silenciosamente la historia auditada. Dos regresiones adicionales prueban el reemplazo adversarial y el entorno del proceso; **24/24** tests locales en Linux.\n- Limitación de la simulación: local es Linux Python 3.13 (sin entorno Windows físico); GitHub Actions valida Windows/Python 3.11. No se ha simulado un evento `push` real a main ni realizado canario supervisado.

## Costes, brechas y coordinación

`fetch-depth: 0` trae el DAG completo; el sparse checkout reduce el árbol de trabajo, **no garantiza una descarga blobless**. Un git `diff-tree` por commit (y uno por padre de merge) tiene coste lineal en commits y padres; límite de 20.000 para no aprobar una revisión incompleta. Un `before` tras push forzado puede ser inaccesible en el remoto: devuelve error y requiere recuperación/inspección explícita, no se finge verificación. Es detección posterior al push, no elimina retrospectivamente un blob público.

Al integrar: **#2 → #88 → #89 → #93**; resolver la función común de #89 y confirmar que se mantienen los dos jobs independientes para push final e intermedio. #87 detecta contenido; #92 protege el verificador; #90 comprueba workflows. [PR #88](https://github.com/davidpd89/ci-sandbox-tmp/pull/88) y [#89](https://github.com/davidpd89/ci-sandbox-tmp/pull/89) seguían abiertas al iniciar. **Claude debe revisar el HEAD final, CI Windows/Ubuntu, tests tras la integración y un canario supervisado de push seguro sobre un entorno aislado**. Sin migraciones ni datos operativos; rollback mediante revertir commits de esta PR.

**Brecha derivada sin solapamiento:** [PR #97](https://github.com/davidpd89/ci-sandbox-tmp/pull/97) describe un trabajo de implementación futura para auditar eventos de push de ramas públicas de trabajo. #93 permanece delimitada a `main`; #97 no se declara implementada. Licencias y mantenimiento externos ratificados en GitHub el 09/10/2026 (checkout MIT, Gitleaks MIT, Betterleaks MIT, detect-secrets Apache-2.0).
