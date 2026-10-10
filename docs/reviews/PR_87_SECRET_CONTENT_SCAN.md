# PR #87 — detección de secretos por contenido del mirror

Fecha de revisión: **09-10-2026**. PR: https://github.com/davidpd89/ci-sandbox-tmp/pull/87
Rama: `ci/secret-content-scan`; base: `ci/test-campaign-parent`.

## Diagnóstico y fuentes

El comprobador actual `tools/repo_hygiene.py` controla rutas añadidas y modificadas, pero no contenido en archivos permitidos. Se leyeron el encargo de la PR y `docs/ci/tasks/secret-content-scan.md`, el trabajo de [PR #2](https://github.com/davidpd89/ci-sandbox-tmp/pull/2) y su documento `docs/reviews/PR_2_MIRROR_PR_CONTRACT.md`. El protocolo `docs/open-source-scouting/PROTOCOL.md` no está presente en la rama #87: se consultó en `research/public-reuse-parent` (#10). El mirror contiene todo el código necesario para este cambio; no se copiaron ficheros del repositorio privado.

## Reutilización pública comparada el 09-10-2026

| Alternativa | Licencia y mantenimiento | Windows / Python 3.11 | Decisión |
| --- | --- | --- | --- |
| [Gitleaks CLI v8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) | MIT, © 2019 Zachary Rice; release 21-03-2026. Proyecto feature-complete, con mantenimiento de seguridad. | Binarios Linux y Windows x64 independientes de Python. | **Integrado**: scanner Git preexistente, sin reimplementar reglas y con hash de release. La Action separada no se utiliza. |
| [Yelp detect-secrets v1.5.0](https://github.com/Yelp/detect-secrets/releases/tag/v1.5.0) | Apache-2.0; última release 06-05-2024. | Soporte explícito de Python 3.11. | Viable, pero añade dependencias, baseline/hook y no simplifica el análisis del patch del merge. |
| [TruffleHog](https://github.com/trufflesecurity/trufflehog) | AGPL-3.0, desarrollo activo. | Ejecutables multiplataforma. | Mayor coste operativo y funciones de verificación remota que aquí no se necesitan. |
| [Betterleaks v1.9.0](https://github.com/betterleaks/betterleaks/releases/tag/v1.9.0) | Actividad reciente: v1.9.0 29-09-2026; 2.0.0-rc.1 30-09-2026. | Multiplataforma. | Mejoras prometedoras, pero la RC modifica CLI/esquemas. Preferimos Gitleaks estable y un contrato pequeño. |
| Continuidad de `repo_hygiene.py` | Sin dependencias, mantenido localmente. | Sí. | Complementa el control de contenido; no escribir scanner de regex casero. |

Gitleaks se ejecuta desde su release sin copiar su código fuente. Atribución: licencia [MIT](https://github.com/gitleaks/gitleaks/blob/master/LICENSE), © 2019 Zachary Rice. Fuente de contrato `git log -p`: [README de Gitleaks](https://github.com/gitleaks/gitleaks#git), [documentación de Git sobre merges](https://git-scm.com/docs/git-log).

## Implementación y protección del contexto

El workflow añade `pull_request`, preserva `push` y `workflow_dispatch`, fija las acciones por commit SHA, mantiene `contents: read` y `persist-credentials: false`, y valida Ubuntu + Windows con Python 3.11. Ejecuta higiene de rutas, descarga verificada y Gitleaks **antes** de pip. No utiliza `pull_request_target`, tokens de usuario ni verificación de secretos contra servicios.

El instalador descarga **exclusivamente Gitleaks CLI v8.30.1** y valida el SHA-256 del archivo **antes** de extraer un único ejecutable en el temporal del runner; no descarga `latest`.

- Linux x64: `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`.
- Windows x64: `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e`.

`tools/pr_secret_content_scan.py` rechaza también `.gitleaks.toml` dentro del árbol revisado cuando ejecuta CI sin configuración explícita: Gitleaks upstream cargaría automáticamente ese fichero y una PR podría debilitar las reglas predeterminadas. La regla sintética de integración, pasada explícitamente con `config`, sigue permitida solo en los tests. Cobertura: `test_pr_supplied_gitleaks_config_cannot_disable_default_rules`. No sustituye al verificador independiente encargado en #92.

### Revisión adversarial adicional — 10/10/2026

Se verificó directamente el código de `gitleaks/gitleaks@v8.30.1` (`cmd/root.go`, `detect/detect.go`, `sources/git.go`) y se corrigieron otras tres vías de omisión:

- **Fichero `.gitleaksignore`**: Gitleaks lo carga automáticamente desde el repositorio *aunque* se especifique otra ruta para ignorados; por eso se rechaza en el escaneo de CI, igual que `.gitleaks.toml`. Esto sacrifica excepciones por fichero completo y es intencional para el mirror. Debe reconsiderarse si alguna base futura ya trae este archivo, sin abrir deuda histórica accidentalmente.
- **Anotación `gitleaks:allow`**: el motor descarta el hallazgo de la línea de origen por defecto; la ejecución de CI fuerza `--ignore-gitleaks-allow` para impedir excepciones insertadas por una PR. Se añadió variante sintética de integración que debe devolver detección aun con la anotación.
- **Entorno y atributos Git**: se eliminan `GITLEAKS_CONFIG` y `GITLEAKS_CONFIG_TOML` del entorno heredado del subproceso. Una prueba Git demostró que `*.py -diff` en `.gitattributes` oculta un marcador del patch convencional; `--text` hace visible de nuevo esa línea. Esto puede ampliar el escaneo a diffs binarios grandes: vigilar consumo de CI y fallar de forma explícita si sobrepasa el tiempo del job.

Las pruebas usan exclusivamente marcadores inventados. Ninguna de estas protecciones reemplaza el control del workflow/script desde un ref de confianza (#92).

`tools/pr_secret_content_scan.py` exige `HEAD` con **dos padres**, propio de un merge sintético de PR. Escanea `HEAD^1..HEAD` usando `--text --first-parent --diff-merges=first-parent --no-renames --diff-filter=AMT --no-ext-diff --no-textconv --unified=0`. Si falta el merge no cae a un escaneo de todo el histórico: falla cerrado. Los renombrados hacen visible el destino como fichero nuevo; borrados y contenido histórico inalterado no entran en el patch. El motor suprime salida stdout/stderr y activa `--redact=100`, para que los logs no expongan valores potencialmente reales. Un código distinto de cero bloquea la PR; en esta versión de Gitleaks, `1` también puede indicar error de escaneo, por lo que no se etiqueta inequívocamente como hallazgo.

## Pruebas

`tests/test_pr_secret_content_scan.py` crea repositorios Git completamente sintéticos en temporales: nuevos hallazgos, secreto histórico no modificado, modificación ajena al secreto, renombrado y borrado; merge inválido, hash alterado, exceso de tamaño, SO incompatible y supresión de salida. La regla exclusiva de test `tests/fixtures/gitleaks-synthetic.toml` detecta un marcador deliberadamente inventado, **no** credenciales con formato utilizable. En CI, la prueba se ejecuta contra el Gitleaks real instalado; localmente sin el binario se salta explícitamente (no simula un resultado verde). `tests/test_pr_secret_workflow_contract.py` comprueba permisos, acciones SHA, eventos, Linux/Windows, orden de pasos y diff exacto.

Repetición offline: `python -m unittest discover -s tests -p "test_pr_secret*.py" -v`. El resto de `pytest` se conserva en el workflow; la regresión de rutas anteriormente excluida vuelve a ejecutarse con `fetch-depth: 2`.

## Falsos positivos y rollback

Ante un hallazgo, revisar **localmente** con redacción completa, sustituir el valor por una muestra inequívocamente falsa o eliminarlo; si fuese una credencial real, revocarla y gestionar su exposición fuera de la PR pública. Toda excepción exige justificación granular: evitar exclusiones completas de carpetas y reglas. Actualizar versión/digests sólo con release fijada, prueba de integridad y tests en ambos runners. Rollback: revertir el commit de implementación y tests de esta PR; el control original por rutas permanece disponible.

**Límites**: no elimina un secreto de un historial público ya publicado; binarios y archivos no representables como patch textual no tienen cobertura garantizada; las reglas de detección tienen falsos negativos. La búsqueda de commits intermedios (#89), los rangos push (#88), el parseo de workflow (#90) y el verificador de confianza (#92) son trabajos abiertos independientes; no duplicar. Claude debe coordinar #2 y el orden de integración.

## Segunda revisión adversarial

- [x] Diff de primer padre con merge de dos padres; no se reabre el histórico ajeno.
- [x] Renombrados se verifican como contenido nuevo; borrados se excluyen.
- [x] Digest erróneo, binario no disponible, commit sin merge y error del scanner fallan cerrados.
- [x] No se imprime contenido de archivos, valores de secretos ni salida del binario.
- [x] Acciones en SHA, permisos read-only y sin contacto con redes sociales.
- [ ] Verificar CI real Ubuntu/Windows sobre HEAD final y registrar evidencia.
- [ ] Revisión final de coexistencia con #2, #89, #90 y #92 por Claude.

## Ejecución

El resultado anterior (9 pruebas, 8 OK y 1 omitida) corresponde al HEAD previo `65beaf2`. La suite ampliada incorpora las regresiones de `.gitleaksignore`, `gitleaks:allow`, variables de entorno y `.gitattributes`. Confirmar el estado sobre el HEAD final de esta revisión en GitHub Actions antes de integrar.
