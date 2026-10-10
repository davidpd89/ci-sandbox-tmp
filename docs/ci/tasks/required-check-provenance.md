# CI: procedencia auditable del required check

## Reproducción del hueco

En #92 se eligió un workflow separado en default branch con job `trusted-pr-paths`. Sin embargo, un required status check basado solo en su **nombre** puede colisionar con un job definido en un YAML nuevo/modificado por la PR, cuyo `pull_request` se ejecute desde el merge sintético. GitHub advierte que checks duplicados por nombre son ambiguos y que `skipped` puede aceptarse como éxito.

## Implementar

1. Verificar con fuentes oficiales actuales las reglas de required status checks y required workflows de GitHub, su disponibilidad en este repositorio y semántica sobre SHA del head/merge y eventos.
2. Producir fixtures/ensayos sintéticos con dos workflows de igual `name` de job pero diferente evento y origen; la cobertura distingue falsos positivos por `skipped`, duplicados, jobs renombrados y updates del head.
3. Conservar el gate separado de #92. Si hay capacidad de ruleset para requerir el *workflow concreto*, escribir la configuración/guía de activación con verificaciones posteriores y pruebas. Si no, implementar control mínimo que impida que una PR proponga falsificar el nombre exigido, leyendo YAML de la PR **solo como datos** desde checkout de confianza, sin ejecutar head y sin parser casero si hay alternativa mantenida.
4. Evitar prohibiciones generales de ediciones de CI; bloquear solo las colisiones verificadas de identidad.
5. Tests Ubuntu/Windows Python 3.11, sin red ni credenciales en fixtures, informe adversarial, licencias/atribuciones y dependencia explícita de aprobación de administrador cuando aplique.

Fuentes:
- https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target

**Condición de cierre:** ningún check creado desde el head de una PR puede sustituir silenciosamente el required check de confianza. No se aceptan solo pruebas textuales del YAML.

## Implementación y evidencia

La implementación de #96 reside en `tools/required_check_provenance.py` (inspección estática de YAML sobre contenidos de la PR sin ejecutarlos), `tools/required_check_evidence.py` (canario de evidencia **real** del workflow/job/check observado) y sus pruebas `tests/test_required_check*.py`, con workflows separados para gate de default branch y pruebas sintéticas Ubuntu/Windows.

El informe de licencias, comparables, análisis adversarial, limitaciones y runbook de instalación **está en** [docs/ci/reports/required-check-provenance-review.md](../reports/required-check-provenance-review.md).

**Dependencia:** integrar primero #92, cuyo archivo de workflow no existe en esta base; de lo contrario el detector falla cerrado. **Prohibido declarar enforcement activo** por el mero hecho de que pase la CI sintética o se configure un required status check solo por nombre: se necesita la regla externa por identidad, o app distinta con origen esperado, y canario de bloqueo real comprobado por Claude. No se hizo merge.
