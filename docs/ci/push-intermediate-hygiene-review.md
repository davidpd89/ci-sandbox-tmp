# PR #93 — revisión de integración CI (10/10/2026)

Rama `ci/push-intermediate-commit-hygiene` → `ci/test-campaign-parent`. **Sin merge.** Informe actualizado tras leer toda la conversación, reviews y el hilo inline de la PR; sustituye conclusiones históricas anteriores a la nueva base.

## Implementación y alcance

- `tools/git_history_paths.py` reutiliza Git nativo con `rev-list --missing=error`, `diff-tree -z --diff-filter=AMT --no-renames` y UTF-8 estricto. Rechaza historia superficial, SHA inválido y más de 20.000 commits. Establece `GIT_NO_LAZY_FETCH=1`, `GIT_NO_REPLACE_OBJECTS=1` y `GIT_TERMINAL_PROMPT=0`. No lee contenidos ni publica rutas/credenciales en logs.
- `tools/push_commit_hygiene.py` valida `before`/`after`/`GITHUB_SHA`/HEAD/ref real de `push` a `main`. Busca commits nuevos incluso en ramas de un merge, cambios transitorios de rutas, typechanges y renombrados a nombres prohibidos. En force-push con rewind exacto a un ancestro, examina el diff de árboles para no fallar ante retrocesos inocuos y rechazar rutas restauradas. No usa `HEAD^1` ni escanea deuda antigua no tocada.
- Política de rutas: **`repo_hygiene.forbidden_path`** heredada de la base (AMT/UTF-8 estricto, sin excepciones por red). Útil para las nueve redes y tres colas: WEB/API/MOBILE; no toca su ejecución.
- `touched_paths(..., merge_policy="first_parent")` es la semántica por defecto **para push**: detecta una ruta sensible resucitada desde un segundo padre previamente alcanzable que se elimina en otro commit. `merge_policy="all_parents"` expone la intersección para reutilización por el adaptador PR. **No trasplantar directamente el primer padre a #89**: la PR puede heredar una ruta de una base avanzada. El adaptador PR debe conservar además la condición de base y segundo padre de `scan_pr()` de #89. Test sintético específico de divergencia de atribución en `test_merge_attribution_differs_for_pr_and_push`.
- `.github/workflows/push-intermediate-hygiene.yml` corre la suite sintética en Ubuntu y Windows Python 3.11 en PR, y el verificador de eventos reales **solo** para `push` a `main`, con checkout de historial completo y credenciales no persistidas. Permiso `contents: read`.

## Revisión de comentarios y correcciones

| Comentario | Tratamiento y evidencia |
| --- | --- |
| P1: falso negativo del merge + force-push | Corregido en `636786b`; regresión `test_force_merge_resurrects_already_reachable_sensitive_path`. |
| P2: atribución PR frente a push | Válido: dos estrategias explícitas en el núcleo y nuevo test de base avanzada. El **uso por #89** requiere integración coordinada, sin copiar su detector. |
| Rewind limpio o restauración sensible | Corregido en `7992cb8`; tests de ambos casos. `before == after`, shallow, SHA perdido siguen devolviendo error. |
| UTF-8 inválido | Rechazo estricto en `7d88147`, con regresión. |
| Base actualizada y conflicto `tests/test_tiktok_safety.py` de #87 | Sincronizada con merge a `3d0304c`; se conserva **íntegra la versión de la base** del fixture (incluida su aclaración de fecha), sin editar comportamiento de TikTok. Diff de #93 vuelve a quedar exclusivamente en **seis ficheros propios** y 0 behind respecto a esa base. |
| Aviso Claude de espejo/entorno oficial | #93 permanece exclusivamente en espejo CI. El repo oficial ya contiene adaptador para ramas de trabajo que depende del núcleo aquí incorporado; retirar bootstrap provisional tras integración controlada. |
| Riesgo de duplicación con #88/#89/#92/#96/#97 | #88 árbol final; #89 historia PR; #93 historia push main; #92/#96 confianza de checks. #97 ya cerrada sin merge en sandbox con adaptación al oficial. Ningún nuevo PR duplicado. |
| Canario del evento real, requerido por controlador | **Pendiente**. Una PR dispara la suite sintética; `push-history` debe aparecer skipped y solo puede certificarse con push sintético controlado a main en un **repositorio aislado**, después de instalar el workflow. |

## Evidencia y pruebas

- 29 pruebas Git sintéticas en `tests/test_push_commit_hygiene.py` tras corrección P2; **la aprobación de CI del HEAD final debe verificarse tras este último commit**. Se conservan regresiones transitorias, divergencias, renombres, tipo de archivo, merges, UTF-8 inválido y salida sin nombres.
- Evidencia del HEAD anterior `7992cb8`: [28/28 Ubuntu + Windows, Python 3.11](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38057244841), [suite general verde Ubuntu/Windows](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38057244810). Estos checks **no certifican commits posteriores**.
- Compatibilidad de Git y checkout documentada en sus referencias oficiales: [git-rev-list](https://git-scm.com/docs/git-rev-list), [git-diff-tree](https://git-scm.com/docs/git-diff-tree), [actions/checkout](https://github.com/actions/checkout) (MIT, actividad 2026). Git GPL-2.0 con excepciones se **invoca como CLI**, no se redistribuye código modificado.
- Alternativas actuales contrastadas: [Gitleaks](https://github.com/gitleaks/gitleaks) (MIT), [Betterleaks](https://github.com/betterleaks/betterleaks) (MIT), [Yelp/detect-secrets](https://github.com/Yelp/detect-secrets) (Apache-2.0). Son escáneres de secretos **por contenido**, cubiertos en #87, no sustituyen la clasificación de rutas. Git/checkout funcionan en runners Windows/Ubuntu y Python 3.11 sin bibliotecas Python adicionales.

## Checklist de integración para Claude

1. Mantener los workflows de #87 (Gitleaks) y #88 (diff final) intactos, además del de #93; no reemplazar el clasificador de la base por una versión anterior del repo privado.
2. Al integrar #89, compartir ejecución de Git, parser NUL y recorrido; conservar las dos atribuciones distintas de merges. Ejecutar `test_pr_commit_hygiene.py` y `test_push_commit_hygiene.py` juntos y la suite general en Windows/Ubuntu Python 3.11. Resolver el hilo P2 después de comprobar ambos tests.
3. Contrastar #92/#96 para que los checks requeridos procedan de workflows confiables. No asumir que un check verde de un workflow de PR garantiza el evento de push.
4. En canario **aislado** con datos inventados y workflow instalado antes del evento, un push de alta+baja a `main` debe producir fallo; push inocuo y rewind inocuo deben pasar; rewind que restaura ruta sensible debe fallar. Validar `GITHUB_EVENT_PATH`, `before`, `after`, `GITHUB_SHA` reales y ambos sistemas.
5. No hay acciones en redes ni credenciales. El CI detecta después del push, no elimina archivos ya hechos accesibles en la historia; `before` inaccesible devuelve error explícito. Rollback: revertir la PR sin migraciones.

Estado: **código de #93 preparado para revisión de integración**, pendiente solo de CI del HEAD más reciente y de verificaciones conjuntas de otros PR/canario que dependen de Claude. No declarar 100 % de cobertura antes de esas comprobaciones.
