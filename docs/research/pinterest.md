# Pinterest: preflight local y decisión de reutilización

**Consulta:** 2026-10-09 (Europa/Madrid). **PR:** https://github.com/davidpd89/ci-sandbox-tmp/pull/17. **Rama:** `research/07-pinterest`; base verificada `research/public-reuse-parent`. No se ha conectado a Pinterest ni se ha publicado.

## Problema y reproducción del flujo real

En el mirror, `tools/pinterest_publish.py:publish_pin` aceptaba en modo dry-run cualquier fichero existente: un GIF renombrado a PNG, un PNG truncado o una imagen de más de 20 MB obtenían «ensayo». El mismo error se trasladaba a `--apply` después de abrir el navegador. Tampoco validaba allí el enlace ni la presencia real de ALT y descripción. Antes: **0 de 3 entradas deliberadamente inválidas bloqueadas por el control de imagen** (según inspección del predicado `os.path.exists`, no benchmark de una ejecución histórica). Ahora: esos **3 casos fallan antes de Playwright**, probado en el contrato offline; el test de cableado queda sujeto a CI del checkout real.

Ruta operativa del mirror: ficha `publicaciones Pinterest GPT/*/publicacion.md` o páginas del sitio → `tools/content_queue.py` o `tools/pinterest_daily_pins.py` → selección de tablero/copy/asset → `pinterest_publish.publish_pin` → validación nueva → (solo con `--apply` aprobado) Playwright/CDP y verificación de campos → clic → comprobación en tablero/permalink → `pins_auto.csv`/cola y estado `pendiente_verificacion` ante confirmación ambigua. `tools/action_ledger.py` coordina el navegador. El origen y la persistencia de la deduplicación están en `pinterest_daily_pins.used_links`, `today_count` y la prueba `tests/test_r7_pinterest_post_wait_revalidation.py`: no se reintenta ciegamente un clic de resultado incierto.

El mirror contiene además `pinterest_growth.py`, `pinterest_boards.py`, `pinterest_profile_audit.py` y `pinterest_api_audit.py`. No son el flujo de subida. En `davidpd89/rrss-davidporto-CODE@main`, los archivos `tools/pinterest_scan.py`, `tools/pinterest_execute.py` y `tools/pinterest_api_audit.py` representan la etapa anterior, manual/nativa, y `SISTEMA_DIARIO_PINTEREST/PROCESO.md` prohíbe publicar automáticamente: **no inferir que main oficial ejecuta la versión del mirror**. `AI_REVIEWER_BRIEF.md` es histórico. Cualquier promoción al repositorio privado necesita revisión de la diferencia de versiones y autorización; no se ha hecho aquí.

## Alternativas comparadas

| Baseline | Candidato 1 | Candidato 2 | Elección | Razón y riesgo |
|---|---|---|---|---|
| Publicador web propio + comprobación de existencia | Pinterest Python SDK oficial: [Apache-2.0; 7daaa25](https://github.com/pinterest/pinterest-python-sdk/tree/7daaa25e018e46ac960187655e8bed6680f6c8cf) | [oapicf/pinterest-sdk](https://github.com/oapicf/pinterest-sdk/tree/eafc994ce3fba4069e947140b52354ba122026f6), MIT, generado | **C: patrón mínimo de validación local con Pillow ya declarada en requirements-ci.txt** | Sin token/OAuth ni cambios de transporte, sin dependencias nuevas. Riesgo: UI/CDP sigue frágil y no se garantiza publicación. |
| — | [Cliente oficial generado](https://github.com/pinterest/pinterest-python-generated-api-client/tree/9480d8c0888b401f018828f19fbcf49d28a4a953), cliente amplio generado; **licencia por verificar**, no se redistribuye | Conservar existencia sin comprobar imagen | Descartadas | SDK oficial orientado principalmente a gestión de campañas y con issue abierto de creación de pin; SDKs amplios necesitan mantenimiento OAuth, cuotas y dependencias transitivas. Simple existencia es insuficiente. |

**Suite completa contrastada:** [Postiz, commit 91c91f6 del 09-10-2026](https://github.com/gitroomhq/postiz-app/tree/91c91f633a0175fb3914dba64c932928c514b72a), licencia [AGPL-3.0](https://github.com/gitroomhq/postiz-app/blob/91c91f633a0175fb3914dba64c932928c514b72a/LICENSE), sería una alternativa de programación multirred mucho mayor que un comprobador de imágenes. No se incluye código ni se despliega: multiplicaría operaciones, superficie de secretos y obligaciones de licencia sin superar el baseline para el fallo de tipos/peso. En esta PR la opción de componente pequeño resulta superior a la suite por reducción demostrable de alcance/dependencias; no es un benchmark de rendimiento ni un juicio general sobre Postiz.

Fuentes de mantenimiento del SDK oficial: README en el commit citado y [issue #130](https://github.com/pinterest/pinterest-python-sdk/issues/130) (creación de Pin), [issue #172](https://github.com/pinterest/pinterest-python-sdk/issues/172) (urllib3; vulnerabilidad alegada en el issue, no evaluación CVE independiente). No se ha instalado ni copiado código de terceros. Licencia del componente nuevo: código original de esta PR; compatibilidad del repositorio con Pillow ya presente en CI. Verificar licencia global del mirror antes de redistribuirlo fuera de GitHub; no se incorporan activos de otras licencias.

La [guía oficial de pines orgánicos](https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/) admite crear pines mediante API con app/token autorizado y scopes `boards:read`, `boards:write`, `pins:read`, `pins:write`. También señala restricciones de acceso a pines y tableros según autorización, en especial apps recientes. La API no elimina por sí sola problemas de aprobación, cuotas o permisos. [Límites oficiales](https://developers.pinterest.com/docs/reference/rate-limits/) dependen de Trial/Standard y categoría. No se han verificado scopes, permisos ni cuotas disponibles en la cuenta real. No programar, comentar, reaccionar ni realizar acciones reales.

## Licencias y procedencia

Se evaluaron las etiquetas Apache-2.0 y MIT consultando los archivos LICENSE de los repositorios público-oficial y alternativo indicados en la tabla. La licencia del cliente generado no quedó constatada y por ello no se incorpora. No se copió código ni se adoptó componente de esos proyectos. `tools/pinterest_media_guard.py` y los tests son código nuevo escrito para este cambio; reutilizan exclusivamente Pillow, previamente declarada por el proyecto en `requirements-ci.txt`. Los identificadores y rutas del repositorio privado se mencionan solo como trazabilidad técnica; no se transfirieron secretos, contenidos de terceros ni archivos privados.

## Decisión aplicada

Se añadió `tools/pinterest_media_guard.py` y se cableó a `tools/pinterest_publish.py` antes de iniciar Playwright y de nuevo justo antes de subir el asset al DOM. Se examinan realmente firma/decodificación con Pillow, dimensiones y peso, en lugar de confiar en la extensión; tipos admitidos BMP/JPEG/PNG/TIFF/WEBP, máximo web conservador 20.000.000 bytes, archivo no vacío. `aspect_2_3` es **indicador de relación recomendada**, no restricción ni falsa afirmación de que Pinterest exija 2:3. El guard valida título hasta 100, descripción hasta 800, ALT obligatorio y enlace HTTPS sin credenciales, puertos ni controles. Devuelve error local antes de navegador cuando falla. El publicador conserva `PinterestPublishError` de cara al llamador.

[Especificación oficial de Pines](https://help.pinterest.com/en/article/review-pin-specs) a fecha de consulta: los límites descritos son para **subida web** de imagen, no para apps móviles ni vídeo. No crear una cola paralela, nuevos tableros, nuevo ledger o transporte API. La UI real no es verificada aquí y los selectores pueden cambiar.

## Pruebas y medición, sin cuentas

Comando ejecutado en entorno local con Python 3.13 y Pillow disponible:
```sh
python -m unittest discover -s /mnt/data/pinterest_pr17/tests -p test_pinterest_media_guard.py -k PinterestImageContractTests -v
```
Resultado ejecutado inicialmente: **7 pruebas pasadas, 0 fallidas** sobre PNG sintético real, paisaje válido, GIF no admitido, archivo corrupto/truncado, exceso de 20 MB, rutas ausentes y variantes de campos/HTTPS. La primera ejecución de suite completa en este entorno falló al importar `pinterest_publish` porque **no hay checkout del mirror**: `ModuleNotFoundError: No module named 'pinterest_publish'`. Se corrigió la carga diferida para permitir ejecutar las 7 pruebas puras. Las **3 pruebas de integración** nuevas usan la función real `publish_pin` y bytes reales, y verifican con parche del punto de entrada `sync_playwright` que en `--apply` inválido y dry-run válido no se abre navegador: **pendientes de ejecución CI**. No declarar test completo verde.

En checkout CI usar los comandos realmente existentes en `.github/workflows/validate-social-tools.yml`:
```sh
python -m pip install --disable-pip-version-check -r requirements-ci.txt
python -m compileall -q tools tests
python -m pytest tests/test_pinterest_media_guard.py tests/test_web_publish.py tests/test_pinterest_schedule_response.py tests/test_r7_pinterest_post_wait_revalidation.py -q -p no:cacheprovider
```
La suite global CI ya está definida en ese workflow (con exclusiones específicas); revisar logs del commit final antes de merge. Compatible estructuralmente con rutas Windows/Linux mediante `os.PathLike` y `pathlib`; no probado en Windows local. No se ejecutó prueba de subida remota ni benchmark de velocidad, que carecen de valor para un control puramente local.

**Regresión de la suite global reproducida y corregida:** el run [37978609323](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978609323) detectó **5 fallos** de tests antiguos en Ubuntu/Windows: simulaban `os.path.exists("pin.png")` sin crear ningún fichero. Se modificó `tests/test_r7_pinterest_post_wait_revalidation.py` para que esos cinco escenarios creen **PNG reales y temporales**, sin quitar la comprobación nueva; run [37979024672](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37979024672) **success en Windows y Ubuntu** después de esa corrección. Revisión hostil posterior: un JPEG truncado sin marcador terminal superaba `Image.verify()` pero fallaba con `Image.load()`, reproducido con Pillow real. Se añadió decodificación real y el test `test_jpeg_truncation_cannot_pass_structural_verify` en los commits `eed77d4` y `57346bc`; la última suite offline [run 37979404865](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37979404865) finalizó con **success** en ambos sistemas: **Ubuntu 1699 passed, 8 skipped, 8 deselected, 2 warnings, 678 subtests passed**; **Windows 1702 passed, 5 skipped, 8 deselected, 2 warnings, 678 subtests passed**. Estas cifras corresponden al SHA `3c72db7e6dea09b4c897e738b6719a54b33d3628`, cuyo código es idéntico al de este cambio documental posterior. No se ha medido latencia/carga de red, ni se afirma que las suites de pruebas sustituyan pruebas de publicación real.

## Idempotencia, atribución y las PR hermanas

**#20** publicación: propietaria de cola/calendarios/reintentos; no se modificó `content_queue.py`. **#23** analítica: propietaria de atribución/clics web; no se crearon métricas. **#28** assets: podrá reutilizar la idea de límite por canal, evitando trasladar 20 MB a otras redes. **#41** drift: podrá vigilar cambios oficiales en límites/esquemas sin incluir este guard en un mock de API. Los cuatro diffs estaban limitados a documentos de encargo en la fecha de consulta, por lo que no hubo colisión de código; reconsultarlos antes del merge. Otras redes conservan su guard y sus políticas.

`pin_metrics` de [List Pins](https://developers.pinterest.com/docs/api/v5/pins-list/) y [Organic Reporting](https://developers.pinterest.com/docs/analytics-and-reports/organic-reporting/) puede exponer métricas orgánicas autorizadas, no pruebas de visitas de lectores o ventas. [Glosario oficial](https://developers.pinterest.com/docs/analytics-and-reports/metrics-glossary/): `outbound clicks` es un evento que conduce fuera de Pinterest. No equivale a una sesión verificada del sitio: esta última requeriría analítica de servidor/web con consentimiento y conciliación de UTM. Sin acceso al token ni logs web, **tráfico verificado = desconocido, ventas = desconocidas, datos no disponibles ≠ cero**.

## Dos revisiones adversariales

1. **Archivo de 25 MB con extensión .png:** antes existía y superaba preflight; ahora se rechaza por bytes antes de abrir imagen/CDP. Probado con fichero temporal truncado a tamaño declarado sin reservar 25 MB en RAM.
2. **Imagen .png malformada / GIF renombrado:** una extensión permitida no garantiza media válida. Ahora se comprueba firma, decodificación y formato real; pruebas con bytes sintéticos ejecutadas. Persisten ataques TOCTOU entre validación y `set_input_files`; mitigación parcial: revalidación inmediatamente antes de subir.
3. **Enlace de credenciales/HTTP/control o ALT vacío:** antes el publicador web no rechazaba esos casos, ahora `PinPreflightError` se traduce a `PinterestPublishError` sin abrir navegador. Pruebas unitarias ejecutadas; integración aún por CI.
4. **Doble envío o respuesta incierta:** no resolver con la validación de media. Ya se mantiene `pendiente_verificacion` y el dedupe por URL en `pinterest_daily_pins.py`; tests existentes `test_r7_pinterest_post_wait_revalidation.py`. No reutilizar mocks como demostración de un post real.
5. **Diferencia entre ramas:** código del mirror más nuevo que la publicación manual del oficial; no se ha promovido código a privado, y eso impide certificar producción aunque CI de mirror pase.

## Retirada, rollback y costes

Retirada reversible: revertir los commits de esta rama que añaden `pinterest_media_guard`, tests y la llamada desde `pinterest_publish`. No hay migraciones, secretos, estado remoto, cambios de CSV ni llamadas de red. Coste de servicios: 0 nuevas llamadas de API, 0 licencias externas de pago; coste local: apertura/validación de cada imagen con Pillow (tiempo no medido, no inventar benchmark). Si un fichero legítimo queda bloqueado por la política web, hay que reproducirlo y revisar la fuente oficial antes de relajar el guard.

## Cobertura y bloqueos para Claude

| Criterio | Evidencia | Estado |
|---|---|---|
| Tipo y peso de imagen | guard + 8 tests unitarios reales, incluido JPEG truncado; run 37979404865 | PASA en Ubuntu y Windows |
| Dimensiones/proporción | guard informa dimensiones, 2:3 no obligatorio | PASA (unitario local) |
| URL y metadatos | validación HTTPS, longitud, título, ALT, test de integración offline | PASA en CI Ubuntu/Windows en run 37979024672 |
| Idempotencia de pin | `used_links`, pendiente y tests existentes ejecutados por suite offline | PASA en CI en run 37979024672; confirmación remota real no ejecutada |
| Confusión métricas vs tráfico verificado | documentación explícita sin falsas conversiones | PASA (documental) |
| API scopes/acceso real | documentación oficial, sin token | PENDIENTE de credenciales y autorización |
| No acciones reales | cambios offline, sin `--apply` | PASA en ejecución local |
| CI de la rama final y Windows/Linux | workflow offline success 37979404865, Ubuntu/Windows; gate de campaña run 37979411549 failure (46/76) | PASA regresiones; FALLA gate padre |
| Integración con repositorio oficial privado | versiones divergentes | BLOQUEADA para promoción, no para review del mirror |

**BLOQUEOS_PARA_CLAUDE**: La rama final y SHAs deberán leerse de GitHub tras el último commit; el análisis partió de #17 `6c0d343d3df1d0923983f41aa39988ca9a05f5b2`, padre `4da0584f270bdbec6cf37286cc86396a08e11bab` y source oficial `main` consultado el 09-10-2026. En esta sesión no se dispone de checkout clonado ni tokens Pinterest; el intento `git ls-remote https://github.com/davidpd89/ci-sandbox-tmp.git HEAD` falló: `Could not resolve host: github.com`. Acceso GitHub mediante conector con escritura en rama hija; acceso API Pinterest no usado. Claude debe: (1) actualizar/refetch la rama, (2) ejecutar comandos CI anteriores y suite global con fixtures offline, (3) inspeccionar logs Ubuntu/Windows y diffs completos, (4) comparar cuidadosamente el estado del repositorio privado con el mirror antes de cualquier port, (5) confirmar revisión humana y cumplimiento del protocolo antes de merge. No forzar pushes ni publicar Pines.

**Estado del gate de campaña verificado y persistente a 09-10-2026 (run 37979411549):** [traza de referencia 37978617623](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978617623), jobs Ubuntu y Windows finalizados con `failure`. En ambos `python -m unittest discover -s tests -p test_open_source_campaign.py -v` pasó, pero el paso `python tools/validate_open_source_campaign.py` falló: `campaign: 76 children; 3 errors`, `expected 46 children, got 76`, `missing, extra or duplicate PR numbers`, `protocol index is incomplete or duplicated`. Es drift de la rama padre #10: el índice/manifiesto ahora contienen 76 hijas, pero el script de validación tiene `RANGE = set(range(11, 57))` y comprueba `len(children) == 46`. **No alterar el padre desde la hija #17.** Tras corregir la validación en la PR padre, volver a comprobar el workflow en la rama hija. El éxito de los tests del protocolo no significa ejecución de los tests nuevos de Pinterest.

**Veredicto: BLOQUEADA para merge**, aunque los cambios específicos de Pinterest quedan preparados para revisión: corregir puerta común en #10, ejecutar tests del nuevo guard con checkout real y validar contra repositorio oficial privado.
