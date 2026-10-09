# PR #96 — procedencia de required checks: implementación y revisión adversarial

Contraste externo: **09/10/2026**. Alcance: infraestructura de CI transversal a nueve redes; no modifica datos ni algoritmos de crecimiento.

## Resultado y límites de confianza

**Implementación entregada** (en esta rama, sin merge):

- `tools/required_check_provenance.py`: gate de lectura que, cuando se ejecute desde **default branch**, obtiene la lista completa de YAML del **HEAD actual** de la PR vía GitHub Contents API y la interpreta **solo como datos**. Exige un origen único para `trusted-pr-paths` (#92) y `trusted-check-provenance` (#96). Bloquea un job nuevo o modificado que pueda producir exactamente esos nombres, incluyendo `name` dinámico, nombre derivado del job ID, otro evento, YAML duplicado, `if:` en el job esperado, trigger ampliado o job omitido. Permite cambios no relacionados de CI. Inspecciona dos instantáneas PR head/base antes y después.
- `.github/workflows/required-check-provenance.yml`: `pull_request_target`, checkout **explícito de default branch**, sin checkout ni ejecución del HEAD, token `contents:read/pull-requests:read`, Python 3.11 y PyYAML 6.0.3. Job de nombre estable `trusted-check-provenance` sin condicional.
- `.github/workflows/required-check-provenance-tests.yml`: simulaciones offline para Windows/Ubuntu Python 3.11. **No es un check de confianza**.
- `tools/required_check_evidence.py`: inspección **real pero de solo lectura** para operador, una vez instalado el gate. Comprueba los check runs observados en el SHA explícito de head o merge, ausencia de status contexts colisionantes, conclusión exactamente `success` (no `skipped` ni `neutral`), vínculo a run y job, evento `pull_request_target`, ruta esperada, `check_suite_id`, aplicación `github-actions`, PR/head asociados y dos lecturas de PR sin movimiento. Falla ante datos ausentes o ambiguos. **No configura branch protection ni certifica por sí solo enforcement**.
- `tests/test_required_check_provenance.py` y `tests/test_required_check_evidence.py`: fixtures inertes; ningún token, permiso de escritura ni interacción social.

**Dependencia funcional explícita:** #92 todavía está abierta y su `trusted-pr-hygiene.yml` no se encuentra en `ci/test-campaign-parent`. El inspector **falla cerrado** si ese workflow está ausente; no activar el gate de #96 en default antes de integrar la identidad requerida de #92 y revalidarla. La ruta fija de #92 debe conservar `pull_request_target` y `trusted-pr-paths`.

## Evidencias que NO debemos confundir

1. **Tests sintéticos**: comprueban reglas de extracción, colisión y rechazo; no simulan que GitHub haya habilitado branch protection.
2. **Inspector en default branch**: tras instalación, observa YAML de la PR sin ejecutarlo. Puede avisar de colisiones, pero **un required status check nombrado solo por el contexto** sigue siendo vulnerable a suplantación; un workflow nuevo de la PR podría emitir el mismo nombre *antes* de que el inspector de confianza se vuelva obligatorio.
3. **Verificador de provenance del check run**: permite a Claude/admin inspeccionar *un resultado realmente observado*, asociando `check_run -> Actions job -> Actions run -> workflow path/event -> current PR`. Requiere permisos de **solo lectura** adicionales (`checks:read, actions:read, statuses:read, pull-requests:read`). No debe formar parte del check de confianza ya que la evidencia de su propia ejecución podría no estar publicada antes de terminar.
4. **Enforcement externo**: lo único que impide la sustitución silenciosa de un check por nombre es un anclaje externo no controlado por el HEAD: preferiblemente la regla **Require workflows to pass before merging** de una organización/empresa por identidad de archivo + repositorio/rama, o un GitHub App distinto que emita el estado y esté configurado como fuente esperada. Seleccionar `GitHub Actions` como expected source **no discrimina entre dos workflows de Actions**.

## Runbook obligatorio para Claude / administrador

Precondiciones: asegurarse de que #92 y #96 pasan revisión de código, de que los workflows y scripts de confianza existen en default branch y de que las rutas esperadas no son editables por HEAD durante su ejecución. No se ha realizado ninguna operación sobre configuración, protección ni rama principal.

1. **Inspeccionar la configuración real**: `Settings -> Rules -> Rulesets` y `Settings -> Branches -> Branch protection rules`, y la política Actions del repositorio. Verificar reglas **activas** y alcance exacto de ramas protegidas; `evaluate` no impide merge. La consulta GET a branch protection con este conector dio **403**, y `GET /rulesets` devolvió **[]** el 09/10/2026. No se afirma que haya una regla exigible hoy.
2. **Opción de preferencia (si el plan/organización la ofrece):** en la organización, `Settings -> Repository -> Rulesets -> New branch ruleset -> Require workflows to pass before merging -> Add workflow`; seleccionar **el repositorio fuente, la rama protegida de origen y cada workflow de confianza**. Scope sobre el destino `ci/test-campaign-parent` cuando ese sea el branch que realmente se protege; en despliegue final, `main` y las demás ramas requeridas. Activar, no solo evaluar. Los required workflows de GitHub son reglas a nivel **organización/empresa**; no confundir con rule de check string del repositorio personal.
3. **Si no existe required workflow por identidad**: exigir el resultado de un **GitHub App diferenciado** ejecutado con código confiable, y fijar su `expected source`; alternativamente, mantener **retención manual** del merge y verificar con el operador. Un check de `GitHub Actions` con nombre reservado y el scanner de YAML son **defensa en profundidad**, nunca garantía autónoma. No declarar resuelto el requisito de no suplantación hasta existir la protección externa.
4. **Verificar runtime, sin tocar datos sociales**: abrir PR canario sintética desde una rama desechable contra la rama protegida, con workflow adicional `on: pull_request` y `jobs.fake.name: trusted-pr-paths` (y otro caso `trusted-check-provenance`). No merge. Constatar que el workflow **de confianza** rechaza la colisión, que el required workflow externo es inequívoco y que el botón merge queda bloqueado aunque un job impostor muestre `success`. Repetir con trigger `pull_request_target`, `if: false`, job renombrado, sin workflow, una actualización del HEAD y un check `skipped`. Registrar el URL de ejecución, el SHA exacto y captura/configuración de reglas activas. Borrar solo la rama canario tras revisar.
5. **Inspeccionar el check observado:** con token de lectura y el SHA seleccionado por el cuadro de checks (head o test merge), ejecutar:
   `python tools/required_check_evidence.py --repo OWNER/REPO --number N --head HEAD_SHA --base BASE_SHA --ref REQUIRED_SHA`.
   Si GitHub no vincula las ejecuciones `pull_request_target` al head real en `run.pull_requests`, o el check no se presenta en ese SHA, el diagnóstico falla; **no sustituir por éxito presunto**. Determinar la opción de enforcement correcta antes de aprobar.
6. **Freshness/reintento**: cuando cambie el HEAD o la base, exigir un run posterior y repetir la verificación; comprobar la vista `Showing checks for the merge commit` cuando proceda. Si se habilita merge queue, `merge_group` requiere diseño y ejecución independiente (los YAML trusted actuales no se disparan por ese evento). No afirmar cobertura de merge queue sin canario.
7. **Rollback**: retirar la regla externa **tras** suspender merges y dejar un check de sustitución operativo; retirar los archivos de workflow de default solo coordinadamente. No basta con quitar un script si una regla sigue exigiendo su resultado.

## Comparación con proyectos públicos (revisada 09/10/2026)

| Proyecto/alternativa | Mantenimiento/licencia/portabilidad | Reutilización/decisión |
|---|---|---|
| [PyYAML](https://github.com/yaml/pyyaml), 6.0.3 | MIT; wheels Windows x64/Linux y Python 3.11; parser YAML probado | **Usado** con loader estricto para conservar la clave `on` y detectar claves duplicadas; no se implementa parser YAML casero. En Windows ARM64 Python 3.11 no se garantiza wheel nativo; los runners Windows elegidos son x64. |
| [rhysd/actionlint](https://github.com/rhysd/actionlint), v1.7.12 (30/03/2026) | MIT, activo, binarios Linux/Windows | Validación general de sintaxis/esquema ya cubierta en #90; no aporta atribución de workflow a una ejecución de check ni protección contra un workflow distinto. No duplicar. |
| [zizmorcore/zizmor](https://github.com/zizmorcore/zizmor), v1.30.1 (09/09/2026) | MIT, activo, binarios multiplataforma | Auditoría de Actions y patrones de seguridad; **no** resuelve por sí solo required-check provenance. Complementario a #31. |
| GitHub REST API Checks / Actions / Contents | API oficial; biblioteca estándar `urllib` multiplataforma | **Usada** para evidencia real y para inspección read-only del YAML de HEAD. No hay licencia externa por usar API; no se reutilizan fuentes privadas. |
| Ruleset workflow por identidad | Función oficial, configuración a nivel org/enterprise | **Preferible** si disponible; exige activación administrativa y evidencia de bloqueo real. |
| Required status check solo por nombre + expected app = GitHub Actions | Disponible en branch protection | **Insuficiente como protección única**: la misma app puede publicar varios jobs con el mismo contexto. |

Ningún código de terceros se copia o redistribuye; los comandos importan PyYAML conforme a su licencia MIT. Los archivos del espejo y el privado `davidpd89/rrss-davidporto-CODE` comparten `tools/repo_hygiene.py` (SHA blob `9987782b1a94a4fd152f0f0cb5e2b42a044d9ae4`), pero aquí **no** se replica la higiene de rutas. Todo lo específico de redes WEB/API/MOBILE queda fuera de alcance.

Referencias: [troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks), [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches), [required workflows/rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets), [ruleset troubleshooting](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules), [PyYAML](https://github.com/yaml/pyyaml), [actionlint MIT](https://github.com/rhysd/actionlint/blob/main/LICENSE.txt), [zizmor MIT](https://github.com/zizmorcore/zizmor/blob/main/LICENSE).

## Segunda revisión adversarial independiente

- **Punto de ruptura #1 (cadena de arranque):** HEAD de #96 contiene el gate #96 pero no el workflow #92 aún no integrado: correcto **fallar cerrado**. La dependencia temporal de integrar #92 antes que #96 debe resolverse por Claude sin ejecutar gate ficticio.
- **#2 (origen):** todas las lecturas HEAD son por `contents?ref=SHA`, no checkout de scripts de PR; el checkout ejecutable proviene explícitamente de la rama de confianza. No se elevan permisos para ejecutar contenido del HEAD.
- **#3 (bypass de YAML):** nombre de job implícito, matrices/expresiones que podrían resolver al nombre reservado, duplicados de keys, casos `on` boolean YAML 1.1, archivos añadidos o renombrados y jobs omitidos están cubiertos. No se bloquean cambios ordinarios de CI por defecto.
- **#4 (race):** snapshot SHA head/base antes y después, y el ref de contenido anclado al SHA. Entre inspección y merge cabe un HEAD nuevo; hace falta required check actualizado y cumplimiento externo. La API no da una transacción multi-endpoint.
- **#5 (API incompleta):** HTTP/permiso ausente, directorio ilegible, YAML grande, paginación de checks inconsistente, job ausente o status `neutral/skipped` → error explícito. No se usa `continue-on-error` ni `if:` para el required job.
- **#6 (no-code-free guarantee):** un actor capaz de emitir un job del mismo nombre y conseguir que GitHub acepte solo el string sigue siendo amenaza si el administrador no configura anclaje externo. El resultado verde de los tests no es una prueba de enforcement; **BLOQUEO DE ACTIVACIÓN**.
- **#7 (limitaciones):** pruebas de CI Windows-latest x64 y Ubuntu Python 3.11 son simulaciones. Sin Windows propio, Edge, móvil, cuentas, secretos, canario de bloqueo/merge real ni branch protection administrada. `docs/open-source-scouting/PROTOCOL.md` no existe en la base de esta PR.

## Ejecuciones

```sh
python -m unittest discover -s tests -p 'test_required_check*.py' -v
python -m pytest tests/test_required_check_provenance.py tests/test_required_check_evidence.py -q
```

Registrar abajo el último HEAD y los jobs de GitHub **después** de la última modificación. Los tests offline tienen resultados comprobables; la prueba de bloqueo real se deja expresamente pendiente para Claude.
