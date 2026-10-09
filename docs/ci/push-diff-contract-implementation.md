# PR #88 — contrato ejecutable de higiene en push

Fecha de contraste: **2026-10-09**. Rama `ci/push-diff-contract`; base `ci/test-campaign-parent`.

## Semántica de los eventos

- `pull_request`: mantener `tools/repo_hygiene.py --base HEAD^1` sobre el merge sintético. El primer padre es la base de la PR, no el límite de un push. Checkout con profundidad 2. Se conserva por compatibilidad el contrato de la PR #2 (aún independiente y abierta).
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

`python -m unittest discover -s tests -p 'test_push_hygiene.py' -v`: **15 pruebas correctas** en Linux/Python 3.13; 6 subcasos adicionales de entrada inválida. `pytest -q -p no:cacheprovider tests/test_push_hygiene.py`: **15 passed**. Repositorios Git efímeros, datos sintéticos. Cubren multicommits, deuda histórica intacta, SHA cero, fuerza, `before` ausente, `after` y HEAD discordantes, rama ajena, evento borrado, renombrado a ruta prohibida, eliminación, CLI y contrato estático de workflow. `compileall`: correcto.

**Revisión adversarial (segunda pasada):**

1. No interpolar SHA ni JSON del evento en el shell: el fichero del evento lo suministra el runner. Validar SHA, ref, Git HEAD y disponibilidad del objeto anterior.
2. `fetch-depth: 0` cubre rangos largos, **no garantiza** objetos `before` inalcanzables tras reescribir historial. Error verificable, no falso verde; Claude puede estudiar recuperación o canario.
3. Los cambios de tipo `T` y renombrados se tratan como modificación/nueva ruta (`--no-renames`); separador NUL. No se escanea ni se imprime el contenido de ficheros.
4. La rama incluye provisionalmente el contrato de `pull_request` de #2 porque esa PR aún no está en la base. **Integrar #2 antes y resolver cualquier solapamiento en YAML**, manteniendo condiciones distintas por evento. No hacer merge automático.
5. **Pendiente de Claude:** CI GitHub real en Windows y Ubuntu con Python 3.11; comprobación con actionlint (#90); canario supervisado de push a main sobre espejo sin datos reales; revisión cruzada #2/#87/#89/#92. No se han generado acciones sociales ni pushes a main.

**Rollback:** revertir los commits de #88; sin migraciones, cambios de cuentas ni estados operativos.
