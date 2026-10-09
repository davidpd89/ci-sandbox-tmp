# PR #92 — verificador de rutas independiente

Fecha de contraste: 2026-10-09. Fuente de confianza: **workflow y Python desde `main`**, NO el merge/head de la PR.

## Contrato implementado

- Los workflows están **separados** para impedir checks omitidos que aparezcan verdes:
  - `.github/workflows/trusted-pr-hygiene.yml`: `trusted-pr-paths` sobre `pull_request_target`: checkout **explícito** de `github.event.repository.default_branch` sin persistir credenciales; Python 3.11; consulta REST de metadatos con token de solo lectura (`contents: read`, `pull-requests: read`); ningún checkout, instalación o ejecución de archivos de la PR.
  - `.github/workflows/trusted-pr-hygiene-tests.yml`: `trusted-hygiene-tests (ubuntu/windows)` sobre `pull_request` y push de la rama de trabajo: **solo tests sintéticos**, código bajo revisión, y no constituye un check confiable.
- El verificador (`tools/trusted_pr_hygiene.py`) **reutiliza** `repo_hygiene.violations_for_paths()` desde el checkout de confianza. No hay dos listas de rutas divergentes. Consulta API por páginas de 100, compara SHA de head/base en dos lecturas, exige conteo completo, ignora solo rutas realmente eliminadas y falla ante cambios de tipo, renombrados hacia destinos prohibidos o respuestas inconsistentes. Rechaza `>=3000` rutas por truncamiento documentado del endpoint.
- Tokens solo en `env` del paso, sin eco, sin credenciales persistentes, sin descargas ni dependencias Python del head. La inspección es **de metadatos**, nunca contenido ni ejecución. Las rutas del diagnóstico se escapan con `repr`.

## Escenario adversarial de regresión

La prueba `test_changed_or_deleted_self_checker_cannot_override_trusted_decision` coloca en un directorio efímero un falso `tools/repo_hygiene.py` que siempre admite todo y un YAML `jobs: {}`. Se simulan modificaciones o borrados de ambos dentro de la PR junto a una ruta prohibida. El dictamen continúa saliendo de la política de confianza y **rechaza** esa ruta. Se realizan además pruebas de paginación >200 rutas, límite 3000, eliminación histórica, renombrado, cambio de tipo, SHA modificado a mitad, metadatos inválidos y sanitización de mensajes.

El falso fichero en disco nunca se importa ni ejecuta. Una PR que contenga solo cambios a los dos verificadores puede pasar el chequeo *de rutas*, pero no altera el workflow de confianza instalado: esta es la separación buscada. Su revisión de contenido y aprobación sigue correspondiendo al integrador.

## Comparación con código público mantenido

| Alternativa | Licencia / actividad comprobada | Windows / Python 3.11 | Decisión |
| --- | --- | --- | --- |
| GitHub API REST + `urllib` y política `repo_hygiene` | API oficial, biblioteca estándar, sin licencia externa adicional | Python 3.11 nativo en Ubuntu/Windows | **Elegido**: mínimo código nuevo (solo transporte/consistencia), misma política de rutas existente |
| [rhysd/actionlint](https://github.com/rhysd/actionlint) | MIT, no archivado, actualización observada julio 2026, release v1.7.12 (marzo 2026) | Binarios Linux/Windows; independiente de Python | Validación estática de YAML, no aísla la identidad del workflow; cubierta por [#90](https://github.com/davidpd89/ci-sandbox-tmp/pull/90) |
| [zizmorcore/zizmor](https://github.com/zizmorcore/zizmor) | MIT, no archivado; actividad 09/10/2026 | Binarios multiplataforma; no depende de Python | Análisis de patrones de riesgo; **no reemplaza** ejecución de verificador de confianza |
| `git diff` de merge sintético | Git nativo en runners | Disponible en Windows/Ubuntu | Conservar en [#2](https://github.com/davidpd89/ci-sandbox-tmp/pull/2) como test funcional; no es un anclaje de confianza |

La reutilización consiste en la política de rutas existente y las acciones oficiales fijadas por SHA; no se copia ni redistribuye código de terceros.

Fuentes primarias:
- https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files
- https://github.com/rhysd/actionlint/blob/main/LICENSE.txt
- https://github.com/zizmorcore/zizmor

## Segunda revisión adversarial — criterios para Claude

1. **Suplantación del workflow y skipped checks**: GitHub trata jobs omitidos por `if:` como satisfactorios. Por ello **el workflow con `trusted-pr-paths` no contiene `pull_request` ni `push` ni un `if:` que omita el job**; las pruebas viven en otro YAML con otro nombre de check. No reutilizar el nombre `trusted-pr-paths` en otros workflows (GitHub advierte de resultados ambiguos con nombres duplicados). Una PR capaz de crear otro YAML con el mismo nombre de job puede intentar falsear un required check basado solo en contextos: Claude debe valorar una regla de **required workflow** que identifique el workflow confiable, si su plan lo permite.  `pull_request` sí ejecuta YAML del merge sintético; `pull_request_target` usa YAML de la default branch. La PR no puede darse a sí misma un resultado confiable cambiando ese YAML. El checkout queda explícitamente fijado a `default_branch`, no al head. Los tests sobre la rama prueban el código, **no** activan el gate independiente.
2. **Raza en API**: verificamos identidad `head.sha`/`base.sha` antes y después, conteo exacto y todas las páginas. Una actualización entre esas instantáneas que regrese exactamente a los mismos SHA no se detectaría; no se promete atomicidad transaccional de API. Exigir checks frescos al último SHA y rama actualizada al integrar.
3. **Cap API**: con 3000 o más archivos el listado puede truncarse; denegación explícita antes de paginar. Sin rutas `removed` no se reabre deuda histórica, pero los archivos sensibles ya publicados podrían persistir en commits. [#87](https://github.com/davidpd89/ci-sandbox-tmp/pull/87) (contenido), [#89](https://github.com/davidpd89/ci-sandbox-tmp/pull/89) (historial PR) y [#93](https://github.com/davidpd89/ci-sandbox-tmp/pull/93) (historial push) siguen siendo responsabilidades distintas.
4. **Dependencia #2**: `main` conserva hoy la versión antigua de `repo_hygiene.py`; mejoras de nombres de directorios, Unicode y tipo están pendientes de integrar desde #2. Este gate **no las sustituye ni las duplica**: usa la política realmente presente en la rama de confianza. Integrar #2 y verificar sus regresiones antes de reclamar cobertura equivalente.
5. **Activación real**: al 09/10, `main` no contiene el workflow nuevo. Para que sea independiente debe estar fusionado en default branch **antes** de confiar en su check, y `trusted-pr-paths` debe configurarse como required check para las ramas protegidas pertinentes. El conector devuelve HTTP 403 para branch protection y la consulta de rulesets públicos no devuelve reglas; pendiente de Claude/admin confirmar la protección y la política de eventos. No se ha hecho merge.
6. **Evento en repos públicos**: la documentación de GitHub anuncia cambios en la política predeterminada de `pull_request_target` con enforcement previsto para **02/11/2026**. Claude debe verificar que la política de Actions de este repo permite el evento; no basta con un YAML correcto. Alternativa si no se habilita: un servicio/GitHub App que cree el required check con código confiable, sin ejecutar código del head.
7. **Cobertura real**: runner GitHub Ubuntu/Windows Python 3.11, sin canarios WEB/API/MOBILE, móvil, Edge ni PC Windows propio. Un resultado verde no revoca secretos ya expuestos en la historia pública, ni sustituye un escáner de contenido.
8. **Alcance**: infraestructura transversal a X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram. No cambia volumen ni reglas editoriales/acciones de las colas.

## Validaciones

Comando reproducible sin tokens ni datos operativos:

```sh
python -m unittest discover -s tests -p test_trusted_pr_hygiene.py -v
```

Confirmar el run Ubuntu/Windows **del HEAD final** de esta PR. El job `trusted-pr-paths` no podrá verificarse como check independiente hasta instalar el workflow sobre la default branch y configurar su protección. **No confundir simulación y gate activo.**

Rollback: retirar `.github/workflows/trusted-pr-hygiene.yml` de default y quitar su required check de la configuración del repositorio; mantener #2 hasta completar migración. No hay cambios en estados, cuentas ni credenciales.
