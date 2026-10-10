# PR #88 — contrato ejecutable de higiene en push

Fecha de contraste: **2026-10-09**. Rama `ci/push-diff-contract`; base `ci/test-campaign-parent`.

## Semántica de los eventos

- `pull_request`: mantener `tools/repo_hygiene.py --base HEAD^1` sobre el merge sintético. El primer padre es la base de la PR, no el límite de un push. Checkout con profundidad 2. Se conserva el contrato de la PR #2, ya incorporado a la base vigente.
- `push` **a `main`**, sin filtros de rutas: obtener del fichero local `GITHUB_EVENT_PATH` los SHA `before` y `after`. Exigir que `event.after == GITHUB_SHA == HEAD`, con formato de SHA y `ref=refs/heads/main`. Comparar árboles `git diff --diff-filter=AMT --no-renames before HEAD --` usando `repo_hygiene.changed_paths`, después `violations_for_paths`. **No usar `HEAD^1` en push**. Checkout con profundidad 0, credenciales no persistidas.
- `before = 000...000` (referencia recién creada): no existe árbol anterior; inspeccionar todas las rutas rastreadas del árbol `HEAD` con `git ls-tree -r -z --name-only HEAD`. Deliberadamente más estricto: podrían entrar rutas heredadas de una rama anterior.
- Push **forzado/rewrite** con `before` accesible: comparar los dos árboles explícitos aunque no sean antecesor y descendiente; no adivinar merge-base ni rango de commits. Un archivo operativo nuevo queda detectado aunque sea introducido en el segundo de tres commits y permanezca en el árbol final.
- `before` omitido, malformado, recolectado o no descargado: devolver **código 2, no aprobado**. No caer a `HEAD^1` ni a una revisión vacía. Para resolver, repetir con historial válido/completo y comprobar si aún existe el objeto anterior. Sin acceso a ese árbol no es posible una comparación exacta sin falsos positivos contra deuda histórica.
- `workflow_dispatch`: ejecutar **solo la suite offline**, no una revisión de cambios. No presenta el resultado como «PR/push revisado». Un dispatch con rango opcional necesitaría entradas explícitas y contrato nuevo.

**Alcance del diff:** se evalúa el estado final respecto al árbol anterior; se ignoran las eliminaciones. Un archivo añadido y posteriormente borrado dentro de la misma tanda no aparece en el árbol final. El análisis de commits intermedios de PR corresponde a #89 y el de secretos *dentro del contenido* a #87. Esta PR cubre **rutas**, no contenido. El detector compartido sigue siendo genérico para todos los adaptadores/colas.

## Alternativas públicas comprobadas

| Proyecto | Licencia y mantenimiento al 09/10/2026 | Compatibilidad y decisión |
|---|---|---|
| [actions/checkout](https://github.com/actions/checkout) | MIT; actividad 29/09/2026; oficial | Ya utilizado y fijado por SHA. Soporta `fetch-depth: 0` y runners Linux/Windows; no requiere Python. **Reutilizado**, profundidad por evento. |
| [Git](https://git-scm.com/docs/git-diff): `diff`, `ls-tree`, `cat-file` | GPL-2.0 con excepciones; repo activo 08/10/2026 | Instalado en runners Windows/Ubuntu. Invocado como proceso, sin shell; no se copia código fuente. **Reutilizado**. |
| [rhysd/actionlint](https://github.com/rhysd/actionlint) | MIT; actividad 16/07/2026, release v1.7.12 (30/03/2026) | Binarios Windows/Linux (Go); comprueba YAML/expresiones, **no** calcula el rango Git. PR #90 cubre esta integración separada. |
| [zizmorcore/zizmor](https://github.com/zizmorcore/zizmor) | MIT; actividad 09/10/2026 | CLI Rust; auditoría estática de workflows, no del diff `before..after`; complemento posible de #90/#92. |
| `tools/repo_hygiene.py` existente | Código interno; sin dependencias | Ya contiene la política por ruta, diff delimitado por NUL y tests; **ganador para la regla de negocio**. Solo se amplía a `AMT` y `--` conforme a #2, sin duplicar el clasificador. |

Fuentes: [webhook push de GitHub](https://docs.github.com/en/webhooks/webhook-events-and-payloads#push), [eventos de Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push), [Git diff](https://git-scm.com/docs/git-diff), [checkout](https://github.com/actions/checkout#fetch-all-history-for-all-tags-and-branches). Licencias y actividad contrastadas en los repositorios públicos con fecha 09/10/2026.

## Validación y segunda revisión adversarial

`python -m unittest discover -s tests -p 'test_push_hygiene.py' -v`: **24 pruebas de regresión (estado 10/10)** en Linux/Python 3.13; 6 subcasos adicionales de entrada inválida. `pytest -q -p no:cacheprovider tests/test_push_hygiene.py`: **24 casos definidos, sujetos a los checks del HEAD actualizado**. Repositorios Git efímeros, datos sintéticos. Cubren multicommits, deuda histórica intacta, SHA cero, fuerza, `before` ausente, `after` y HEAD discordantes, rama ajena, evento borrado, renombrado a ruta prohibida, cambio de tipo a gitlink, eliminación, CLI y contrato estático de workflow. `compileall`: correcto.

**Revisión adversarial (segunda pasada):**

1. No interpolar SHA ni JSON del evento en el shell: el fichero del evento lo suministra el runner. Validar SHA, ref, Git HEAD y disponibilidad del objeto anterior.
2. `fetch-depth: 0` cubre rangos largos, **no garantiza** objetos `before` inalcanzables tras reescribir historial. Error verificable, no falso verde; Claude puede estudiar recuperación o canario.
3. Los cambios de tipo `T` y renombrados se tratan como modificación/nueva ruta (`--no-renames`); separador NUL. No se escanea ni se imprime el contenido de ficheros.
4. La base actual contiene #2 y #87. La sincronización conserva íntegros el clasificador de #2 (ancestros, UTF-8, escape de diagnósticos), las comprobaciones de Gitleaks de #87 y separa las condiciones por evento. El conflicto del fixture TikTok se resuelve manteniendo exactamente la versión de la base (sin modificaciones operativas). No hacer merge automático.
5. **Pendiente de Claude:** canario supervisado de evento push real en un repositorio temporal saneado; no se sustituye por checks de pull_request. Comprobación cruzada de integración con #89/#92/#93; actionlint (#90 cerrada, sin fusionar) es complemento de validación, no detector de diff. No se han generado acciones sociales ni pushes a main.

**Rollback:** revertir los commits de #88; sin migraciones, cambios de cuentas ni estados operativos.

## Sincronización y pruebas adicionales (10/10/2026)

La rama se ha incorporado a la base actual `ci/test-campaign-parent` mediante commit de reconciliación, usando la versión más estricta de `tools/repo_hygiene.py` de la base. Se añaden regresiones para UTF-8 inválido en el primer push, ancestros sensibles, `before == after` y ausencia de filtros `paths` en el evento `push`. El análisis de commits transitorios sigue separado en #93. La validación de esta revisión corresponde a los nuevos checks del HEAD, no a los checks históricos de 09/10.


## Actualización tras comentarios de Claude y revisores — 10/10/2026

Se leyeron **las nueve entradas de conversación**, **dos reviews** y los hilos inline (**cero**) de la PR. No se encontró comentario sin clasificar. Los comentarios REV 88 de 09/10 y 10/10 se atienden del siguiente modo:

| Punto | Resolución verificable |
| --- | --- |
| Integrar sobre la base vigente, sin perder #2 | Commit de reconciliación con dos padres: `6d0ad82486c91eba9b4c6007fac5192a08708535`; base actualizada a `3d0304c0704e31c8a1ecbd62944d22c330bd7ea5`; clasificador `tools/repo_hygiene.py` heredado de la base, sin cambio en el diff final. |
| Conflicto de #87 en `tests/test_tiktok_safety.py` | Se eligió **la versión de la base**: contiene el uso de fecha actual y conserva todos los tests y controles de TikTok. El fichero **no aparece en el diff final** de #88. |
| Preservar escaneo de contenido de #87 | El YAML sincronizado conserva `install_gitleaks_ci.py` y `pr_secret_content_scan.py` bajo `pull_request`, tras el gate de rutas y antes de `pip`. Ningún detector se duplica. |
| No filtrar pushes por `tools/**` o `tests/**` | Corregido: `on.push` solo contiene `branches: [main]`, **sin `paths`**. El test `test_push_trigger_is_not_filtered_by_paths` evita regresiones. Se descubrió este defecto al revisar la reconciliación, y se corrigió antes de la entrega. |
| Mantener semántica de eventos | `HEAD^1` y Gitleaks solo en PR; `before..after` de evento y checkout completo solo en push; dispatch ejecuta únicamente la suite offline. Permisos de solo lectura y acciones fijadas. |
| Logs, UTF-8 inválido, ancestros, SHA cero y renombres | Corregidos en rondas anteriores. Se conserva escape `!r` en logs; pruebas incluyen UTF-8 inválido, ancestros sensibles y tipo Gitlink. Se añaden prueba Git real de **rutas con espacios** y error 2 ante **JSON truncado**. Prueba de ruta con salto de línea se hace con inyección sintética para evitar crear nombres no válidos en Windows. |
| PRs relacionadas y repo real | #89 cubre historial de PR, #93 historial intermedio push, #92 aislamiento del verificador y #87 contenido. No se abren PR redundantes. **Decisión actual de Claude:** esta higiene pertenece al mirror CI; **no se porta sin adaptación** el workflow ni sus tests al repositorio privado. Se descarta la sugerencia anterior de modificar inmediatamente el repo real. |
| Canario real de push | **No ejecutado**: CI de esta PR usa `pull_request`, por lo que no acredita la rama `if: push`. Única validación de integración externa pendiente: Claude puede realizar push supervisado a `main` en **un repositorio canario saneado**, sin probar con cuentas ni mover `main` del espejo de trabajo. La suite Git sintética cubre `before..after` y fallos antes de ese ensayo. |
| Ejecución y checks | Revisar el run del **último HEAD**, no runs históricos. Las pruebas sintéticas y de workflow son multiplataforma; el workflow completo se ejecuta en Windows/Ubuntu Python 3.11. El control del evento push real queda explícitamente aparte. |

**Riesgo residual que no afecta al alcance de #88:** rutas añadidas y eliminadas en commits intermedios no se observan en diff final (implementación encargada en #93). El core compartido se reutilizará al integrar #89 y #93; no debe duplicarse en #88. No se crean PR nuevas. Merge a cargo de Claude.
