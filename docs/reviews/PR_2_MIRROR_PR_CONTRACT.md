# Revisión PR #2 — contrato CI del mirror público

Fecha de revisión: 2026-10-09  
PR: https://github.com/davidpd89/ci-sandbox-tmp/pull/2  
Rama: `ci/mirror-pr-contract`  
Base declarada: `ci/test-campaign-parent`

## Alcance y fuentes

Se revisaron el cuerpo y diff de la PR, `.github/workflows/validate-social-tools.yml`,
`tests/test_mirror_windows_ci_contract.py`, `tests/test_r10_repo_hygiene.py`,
`tools/repo_hygiene.py` y `docs/CI_TEST_CAMPAIGN.md`.

`docs/open-source-scouting/PROTOCOL.md` no existe en la rama de la PR ni en su
base actual, por lo que no pudo formar parte del contrato de esta PR.

Para no rebajar el contrato por carencias del mirror se consultó también la rama
`integracion/crecimiento-2026-10` de `davidpd89/rrss-davidporto-CODE`. El
`repo_hygiene.py` y su prueba de rutas son iguales al snapshot del mirror; el
workflow privado contiene además comentarios de intención y ejecuta la suite
completa sin las exclusiones que el mirror aún necesita.

## Diagnóstico inicial

1. Al comenzar la primera revisión ampliada, la PR ya incorporaba `pull_request`, permisos `contents: read`,
   credenciales de checkout no persistentes, Python 3.11 y acciones fijadas por
   SHA. El run 37971377243 había terminado correctamente en
   `ubuntu-latest` y `windows-latest`.
2. La prueba de contrato solo buscaba cadenas. Podía seguir en verde si una
   condición peligrosa se añadía junto a las cadenas esperadas o si una cadena
   quedaba en un comentario.
3. La regresión de higiene solo comprobaba que el YAML mencionase
   `fetch-depth: 2`; no demostraba que un checkout con merge commit y
   `HEAD^1` ignorase basura histórica pero bloqueara una ruta sensible nueva.
4. El nombre del paso afirmaba bloquear «secretos», pero
   `repo_hygiene.py` inspecciona nombres/rutas, no contenido de archivos
   permitidos. El propio módulo ya documenta esa limitación.

## Reutilización pública evaluada

Se priorizó reutilizar componentes existentes y no inventar un scanner nuevo.

| Opción | Licencia / mantenimiento | Windows / Py 3.11 | Riesgo o coste para esta PR | Decisión |
| --- | --- | --- | --- | --- |
| `actions/checkout` v7 y `actions/setup-python` v7 | Acciones oficiales, ya fijadas por SHA | Sí | Mínimo; ya forman parte del contrato | Mantener |
| Gitleaks CLI | MIT. El proyecto declara que está feature-complete y mantiene parches de seguridad; dispone de binarios multiplataforma | Windows nativo; independiente de Python | Añade binario/descarga y reglas de contenido. La Action moderna usa una licencia propia y puede interactuar con la API de GitHub | No introducir en #2 |
| Yelp `detect-secrets` | Apache-2.0; release estable 1.5.0, con soporte declarado para Python 3.11 | Sí | Dependencia Python adicional y baseline/política que exceden el contrato de rutas de esta PR | No introducir en #2 |
| TruffleHog | AGPL-3.0; desarrollo activo, releases y commits en 2026 | Windows mediante binario/Docker | Su fortaleza incluye verificación de credenciales mediante red; eso contradice el objetivo offline si no se configura con cuidado | No introducir en #2 |

Fuentes consultadas el 09-10-2026:

- https://github.com/actions/checkout
- https://github.com/gitleaks/gitleaks
- https://github.com/gitleaks/gitleaks-action
- https://github.com/Yelp/detect-secrets
- https://github.com/trufflesecurity/trufflehog

La continuidad del comprobador local gana aquí porque el riesgo inmediato es
validar el *diff de rutas* antes de instalar dependencias, sin red ni secretos.
El escaneo de contenido debe ser un trabajo separado con política de falsos
positivos, fixtures sintéticos y elección explícita de herramienta/licencia.

## Cambios realizados

- Se añadió `--` al final del `git diff` de `changed_paths()` para cerrar
  explícitamente la lista de revisiones antes de cualquier pathspec.
- Se añadieron dos pruebas con un repositorio Git temporal:
  - un archivo sensible ya existente en la base no vuelve a bloquear una PR;
  - una ruta sensible añadida por la PR sí bloquea.
- Se reforzó el contrato del workflow para comprobar:
  - `pull_request` y ausencia de `pull_request_target`;
  - Ubuntu + Windows en el mirror;
  - permisos sin `write`;
  - ausencia de referencias a `secrets.*`;
  - `persist-credentials: false`, `fetch-depth: 2`;
  - todas las acciones `uses:` fijadas por SHA completo;
  - higiene antes de instalar dependencias;
  - ausencia de entrypoints obvios de descarga en los pasos `run:`.
- Se aclararon comentarios del workflow y el nombre del paso de higiene para no
  prometer escaneo de contenido.

## Segunda revisión adversarial

Se revisó la solución suponiendo una PR maliciosa o un cambio accidental:

- Un cambio a `pull_request_target` haría fallar el contrato.
- Cualquier permiso explícito `*: write` haría fallar el contrato.
- Una acción sin SHA de 40 hexadecimales haría fallar el contrato.
- Persistir credenciales o introducir `secrets.*` haría fallar el contrato.
- El comparador se prueba contra un merge real con dos padres, no contra una
  cadena simulada del YAML.
- Los fixtures son sintéticos y se crean en `TemporaryDirectory`; no se leen
  estados, cookies ni credenciales reales.

### Limitaciones que permanecen

- `repo_hygiene.py` no detecta un token pegado dentro de, por ejemplo,
  `tools/example.py`. Eso requiere secret scanning por contenido y no debe
  maquillarse como cubierto.
- Esta revisión puede verificar GitHub-hosted Windows mediante Actions, pero no
  Edge real, perfiles de navegador, móvil ni un PC Windows del usuario.
- La base `ci/test-campaign-parent` avanzó durante la campaña con un commit de
  documentación. No toca los archivos de #2; se comprobó el compare de ramas.

## Validación

Antes de esta revisión:
- workflow run 37971377243: éxito en Ubuntu y Windows.

Después de los cambios:
- el nuevo workflow se deja ejecutar sobre el HEAD final de la PR;
- los jobs y logs de ese HEAD deben ser la evidencia definitiva para Claude.

No se realizó ninguna acción real en redes sociales, no se usaron credenciales
ni datos de producción y no se hizo merge de la PR.


## Tercera revisión independiente — evento push vs. PR (09/10/2026)

**Fallo adicional reproducible por inspección:** el workflow ejecutaba
`python tools/repo_hygiene.py --base "HEAD^1"` en todos los eventos.
La semántica `HEAD^1` = primer padre del merge sintético de PR solo es
aplicable al checkout por defecto de `pull_request`: en `push` compara
contra el commit anterior, y en `workflow_dispatch` hace algo distinto
a revisar una PR (o puede carecer de padre).

**Corrección aplicada:** el paso de higiene tiene ahora
`if: github.event_name == 'pull_request'` y un test de contrato dedicado.
Esto mantiene las suites de Ubuntu/Windows en `push` y
`workflow_dispatch`, evitando atribuirles el significado de una PR.
El control de rutas en merges sigue cubierto por el evento
`pull_request`; comprobar cambios de `push` por rango de commits
es un contrato diferente, pendiente de diseñar con el SHA `before`
y cobertura para primer commit/force push si se considera necesario.

Referencia oficial: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
(`pull_request` usa `refs/pull/<n>/merge` y `GITHUB_SHA` es el
commit sintético). La documentación oficial de `actions/checkout`
confirma `fetch-depth: 2` para acceder a `HEAD^`:
https://github.com/actions/checkout/blob/main/README.md

Revisión cruzada: esto es un contrato de infraestructura reutilizable por
todas las redes (WEB/API/MOBILE), no se necesitan excepciones por plataforma.
No añade restricciones a frecuencia, descubrimiento o contenido social.


## Cuarta revisión adversarial: cambios de tipo y alcance del historial (09/10/2026)

La documentación de Git [diff-options](https://git-scm.com/docs/diff-options)
distingue explícitamente `A` (añadido), `M` (modificado) y `T` (cambio de
tipo: archivo, enlace simbólico, submódulo). El comparador anterior filtraba
solo `AM`, por lo que **omitía un cambio de tipo de una ruta sensible**.

Reproducción local con Git real y archivos **completamente sintéticos**:

1. Crear y confirmar `credentials.json` como archivo normal.
2. Crear un blob sintético con `git hash-object -w` y cambiar el modo
   del path existente mediante
   `git update-index --cacheinfo 120000,<blob>,credentials.json`.
3. Confirmar el cambio. `git diff --name-status HEAD^1 HEAD` devuelve
   `T credentials.json`.
4. `git diff --name-only --diff-filter=AM HEAD^1 HEAD` devuelve una lista
   vacía; con `--diff-filter=AMT`, vuelve `credentials.json`.

**Corrección implementada:** `repo_hygiene.changed_paths` filtra `AMT`,
sin detectar renombrados como una sola operación (`--no-renames` conserva
el destino como `A`). Se añaden regresiones con Git temporal para:

- Cambio de tipo de un nombre sensible (sin crear enlaces del SO: compatible
  con Windows sin privilegios adicionales).
- Renombrado de un archivo permitido hacia `credentials.json`.
- Borrado de `secrets.json` heredado: no reabre deuda histórica.
- Las pruebas existentes continúan cubriendo merges de PR y rutas nuevas.

### Evidencia del último HEAD de código

GitHub Actions run
[37980990016](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37980990016),
`ubuntu-latest` y `windows-latest` concluyeron **success**. El paso de
higiene también pasó en ambos runners:

- Ubuntu: **1700 passed, 8 skipped, 7 deselected, 665 subtests passed**.
- Windows: **1703 passed, 5 skipped, 7 deselected, 665 subtests passed**.
- Dos advertencias existentes por secuencias de escape de Android, no
  relacionadas con esta modificación.
- Los siete casos excluidos permanecen segregados de esta PR; requieren
  validación independiente de su contexto real antes de reducir las exclusiones.

### Limitaciones encontradas con una perspectiva transversal

1. El diff del **árbol final** no detecta rutas sensibles añadidas en un
   commit intermedio y eliminadas antes de abrir la PR. El objeto puede
   permanecer en Git. Se abrió la PR de **implementación**
   [#89](https://github.com/davidpd89/ci-sandbox-tmp/pull/89) para comprobar
   todos los commits relevantes sin falsos positivos sobre la base histórica.
   No se confunde protección de merge con prevención de exposición previa.
2. Los contratos textuales de YAML no sustituyen un parser de workflows.
   Comparativa actual: [actionlint](https://github.com/rhysd/actionlint)
   (MIT, Go, release v1.7.12 de marzo de 2026, binarios para Windows/Linux)
   y [zizmor](https://github.com/zizmorcore/zizmor) (MIT, Rust, modo offline,
   activo en octubre de 2026). Se abre [#90](https://github.com/davidpd89/ci-sandbox-tmp/pull/90),
   **implementación**, para añadir validación estructural mantenida, con
   verificación de integridad y CI sin autenticación.
3. Sigue vigente [#87](https://github.com/davidpd89/ci-sandbox-tmp/pull/87)
   para escaneo de contenido de archivos permitidos y
   [#88](https://github.com/davidpd89/ci-sandbox-tmp/pull/88) para rangos
   de `push` multicommits. No se han confundido ni mezclado con #2.
4. Esto refuerza por igual las tres colas WEB/API/MOBILE y todas las redes:
   es un contrato de **repositorio y CI**, sin excepciones particulares ni
   cambios de comportamiento en redes sociales.

5. El workflow y el comprobador que ejecuta `pull_request` provienen
   del checkout propuesto. Una PR que modifique su YAML o
   `repo_hygiene.py` puede modificar la propia validación. Esto requiere
   un verificador independiente anclado a código de confianza, sin ejecutar
   código de forks con credenciales privilegiadas. Se abre la PR de
   implementación [#92](https://github.com/davidpd89/ci-sandbox-tmp/pull/92).
   Claude deberá confirmar required checks o protecciones administrativas.

### Recomendación para el integrador

Integrar la #2 solo tras revisar la CI del último HEAD y contrastar la rama
`ci/test-campaign-parent`. El uso de `HEAD^1` depende de mantener el
checkout del merge sintético de `pull_request`, no del head de la rama.
No afirmar garantías absolutas: el pipeline de #2 protege rutas del árbol
final, mientras #87, #88, #89, #90 y #92 cubren responsabilidades adicionales.


## Quinta revisión: integridad de los logs y mantenimiento de dependencias (09/10/2026)

### Hallazgo y corrección

El programa mostraba directamente nombres devueltos por Git con
`print(f"  - {path}")`. Git permite nombres de fichero que contienen
saltos de línea y secuencias de control en plataformas compatibles; si se
muestran sin escapar pueden generar **líneas falsas o visualizaciones
equívocas en los logs**. GitHub Actions reconoce instrucciones especiales
en las líneas de salida con prefijo `::`. No se atribuye a este caso un
escalado de privilegios, pero sí una debilidad en la fidelidad del diagnóstico.

La corrección imprime los nombres rechazados con `{path!r}` y los mensajes
de fallo Git con `{str(exc)!r}`. Así se representan los caracteres de control
con secuencias visibles y se preserva **una sola línea de diagnóstico por
elemento**. No cambia la política de rutas ni los resultados admitido/rechazado.

Se añadieron dos pruebas con cadenas completamente sintéticas y
`unittest.mock.patch`:

- Un nombre `.env` seguido de salto de línea, una falsa anotación de
  workflow y un escape ANSI, sin imprimir ni ejecutar dichas secuencias.
- Un error de Git con salto de línea seguido de una supuesta advertencia,
  verificando que permanece escapado.

La lógica permanece en la biblioteca estándar: no requiere bibliotecas de
red, nuevos procesos ni compatibilidad especial con ninguna red social.

Fuente primaria sobre comandos del runner:
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
Fuente del formato de rutas de Git:
https://git-scm.com/docs/git-diff

### Revisión de reutilización pública actualizada

El análisis adicional de la PR #90 encontró una diferencia de mantenimiento
relevante, comprobada en GitHub el 09/10/2026:

- `rhysd/actionlint` (MIT, licencia `LICENSE.txt`): último commit
  observado **19/04/2026**; se ha señalado en el propio repositorio que
  existe un fork mantenido.
- `kjanat/actionlint` (MIT, licencia `LICENSE.txt`): último commit
  observado **04/10/2026**, con desarrollo activo y evolución del formato
  de resultados. Evaluar releases, binarios Linux/Windows, sumas de
  integridad y posibles cambios incompatibles antes de fijar versión.
- `zizmorcore/zizmor` (MIT): actividad verificada **08/10/2026**;
  complementa auditoría de seguridad, no reemplaza necesariamente todos
  los análisis de sintaxis/expresiones de actionlint.
- `betterleaks/betterleaks`: actividad verificada **08/10/2026**;
  investigarlo en la PR #87 relativa a contenido, no integrarlo aquí.

Se **mantiene el comprobador local de rutas**, porque el defecto detectado se
corrige en dos representaciones de salida y no justifica instalar software
externo. La comparación del fork se añade como criterio de selección para
la PR #90 ya abierta; no se crea otro encargo duplicado.

### Limitaciones y segunda mirada sobre este cambio

Los tests usan cadenas simuladas, no nombres con caracteres de control en el
sistema de ficheros de Windows, donde esas rutas pueden no ser representables.
La verificación GitHub-hosted Ubuntu y Windows demuestra el comportamiento
del código en ambos runners, no la ejecución de un canario sobre un PC
Windows real. La excepción del error Git podría contener datos inesperados;
por eso también se escapan saltos de línea, aunque no se promete redactar
datos arbitrarios que Git pudiera incluir en un mensaje.

No se han realizado operaciones de publicación ni de interacción sobre
X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok o Instagram.
La revisión se limita al contrato del mirror y a fixtures sintéticos.

## Sexta revisión adversarial: componentes de rutas y UTF-8 (09/10/2026)

### Defectos reproducidos

El analizador evaluaba el **último componente** del archivo y una pequeña
lista de nombres de directorio. Aceptaba, entre otros:

- `.env.local/settings.py`, porque `.env.local` no estaba en la lista de
  directorios aunque fuese un nombre de entorno secreto prohibido como archivo;
- `credentials.json/sessions.py` y `metricas.csv/one.py`, porque no evaluaba
  los nombres prohibidos de archivo si se utilizaban como carpetas;
- `.env.example ` (con espacio final), porque el `strip()` global convertía
  este **nombre diferente** en el único nombre autorizado `.env.example`.

Además, `git diff --name-only -z` devuelve nombres delimitados por NUL como
**bytes**. La decodificación anterior `decode("utf-8", "replace")` sustituía
bytes inválidos por U+FFFD y validaba un nombre distinto del original.

### Correcciones comprobables

1. Cada segmento ancestro se compara con nombres de carpetas de ejecución y
   también con la política de nombres sensibles de archivo. Se bloquea un
   directorio que empiece por `.env`, incluso si el último componente dentro
   se llama `README.md`. Las plantillas `.env.example/.sample/.template`
   solo se exceptúan cuando son archivos independientes.
2. Se evalúan componentes con espacios circundantes para impedir eludir un
   nombre sensible y **se deniega** presentar una plantilla con espacios en
   su propio componente. Siguen permitidos nombres seguros y los espacios
   interiores habituales.
3. El lector Git conserva `-z`, pero decodifica UTF-8 en modo estricto. Si
   una ruta tiene bytes inválidos, se devuelve **error 2** sin aprobar un
   nombre reconstruido ni imprimir sus bytes originales.
4. Regresiones nuevas para diez rutas protegidas anidadas, tres variantes
   con espacios, cinco rutas seguras, un merge sintético real de PR que
   añade `.env.local/settings.py`, un `git diff` simulado con bytes
   inválidos y un merge real cuyo nombre contiene las letras españolas
   `ñ` y `ó`. Todos los fixtures son ficticios.

### Reutilización de código público examinada

- [Git `git-diff`](https://git-scm.com/docs/git-diff): `-z` devuelve
  nombres sin escapes y separados por NUL; los nombres están **a menudo**,
  no necesariamente siempre, codificados en UTF-8. Se mantiene Git nativo.
- [`cpburnz/python-pathspec`](https://github.com/cpburnz/python-pathspec):
  MPL-2.0, activo el **09/10/2026**, soporta Python 3.11 y Windows; implementa
  patrones tipo `gitignore`. Es útil para glob/wildmatch, pero aquí ya se
  reciben rutas exactas del `git diff` y se comparan componentes literales.
  Integrarlo supondría una dependencia y complejidad nuevas sin demostrar
  una ventaja para esta regla. Por eso se mantiene la biblioteca estándar.
- La PR de investigación transversal
  [#50](https://github.com/davidpd89/ci-sandbox-tmp/pull/50)
  ya contempla Unicode/locale/codificación. La corrección local del defecto
  demostrado queda en #2, sin crear otra PR duplicada.

### Matriz de revisión e integración

Se preservaron los tests anteriores de cambios A/M/T, borrado histórico,
renombrados, espacios/controles en logs y contrato de eventos. Hay
casos positivos y negativos para evitar bloquear documentación o código
legítimo. El guard de `pull_request` permanece igual: los cambios de `push`
y el historial intermedio corresponden a #88/#89. No se modifican colas
WEB/API/MOBILE ni operaciones reales en redes.

El run iniciado sobre el código es
[37986301973](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37986301973).
Su conclusión y la del HEAD definitivo deben comprobarse en GitHub antes de
fusionar. Claude debe trasladar también estos tests al repositorio privado,
sin copiar las siete exclusiones del mirror. Los cambios solo protegen rutas
del árbol final y no sustituyen #87 (contenido) ni #92 (verificador independiente).
