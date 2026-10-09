# Instagram — idempotencia ante confirmaciones ambiguas (09-10-2026)

## Problema y alcance

La PR #16 se desarrolla en el **mirror público** `davidpd89/ci-sandbox-tmp`, rama `research/06-instagram`. Se inspeccionó también `davidpd89/rrss-davidporto-CODE` (privado, rama `main`, 09-10-2026). Este último **no contiene todavía** `tools/content_publisher.py`, `tools/meta_publish.py` ni `tools/action_ledger.py` en su `main`: no confundir la implantación del mirror con un despliegue del repositorio oficial. No se han copiado historiales, credenciales ni datos de terceros.

**Entrada → plan → ejecución → registro:** `content_publisher.run` lee fichas mediante `content_queue`, aplica validación editorial y caducidad, consulta `content_queue_alert.classify` para detectar publicaciones ya existentes, y envía una sola ficha con `content_publisher.publish_instagram`. Este último crea URLs JPEG mediante `meta_publish.public_image_url` (fotos en Facebook sin publicar), genera contenedores individuales/carrusel, espera `FINISHED`, llama a `media_publish`, obtiene permalink, marca la ficha y registra en `00_OPERATIVO/publicaciones_automaticas.csv`. El flujo diario **distinto** del oficial (`instagram_scan.py` → plan → `instagram_execute.py` → CSV/métricas) no se altera.

**Reproducción lógica anterior:** si Meta publica correctamente pero se pierde la respuesta de `media_publish` o cae el proceso antes de marcar la ficha, la verificación posterior puede fallar, paginar de forma incompleta o no localizar aún la publicación. Antes la misma ficha podía volver a enviarse en el siguiente `--apply`. La comprobación textual de los últimos 50 posts no constituye confirmación transaccional. El riesgo no queda solucionado usando navegador/móvil como fallback: añadiría otra ruta capaz de duplicar.

## Alternativas

| Baseline | Candidato 1 | Candidato 2 | Elección | Evidencia y coste | Riesgo |
| --- | --- | --- | --- | --- | --- |
| `requests`/`urllib`, comprobación textual tras excepción | Meta Business SDK Python 26.0.2 (licencia propia Meta; SDK amplio) | `instagrapi` 3.0.20 (MIT; endpoints no oficiales de app móvil) | **C: adaptación mínima del `ActionLedger` existente** | Nueva dependencia externa: **0**; una reserva SQLite y checkpoint por publicación; tests sintéticos de doble envío y concurrencia | Reconciliación manual de resultados inciertos; ruta de ficha estable y journal persistente |

Tercera alternativa: publicación manual/nativa desde la app, aceptable cuando Meta no autoriza un tipo de publicación, pero no sustituye la protección de idempotencia del flujo automático. No se importó ni copió código de ningún OSS externo. Se descartó Meta SDK por superficie, dependencias y política de licencia frente al bug concreto; `instagrapi` por depender de APIs privadas y aumentar el riesgo de bloqueo/cambio de contrato. Versión 3.0.20 de instagrapi publicada el 04-10-2026 (tag firmado, revisión de credenciales/dispositivo) y comprobada en PyPI y GitHub; actividad reciente **no** elimina el problema de usar endpoints privados. No se inventan benchmarks de red: el mismo fixture de Graph `FINISHED` + timeout tras `media_publish` genera **2 intentos de envío** sin journal y **1** con el journal; test `test_same_fixture_baseline_two_posts_guard_one`. No demuestra que Instagram haya creado posts reales. Es medición de comportamiento del doble intento, no una cifra de rendimiento de Instagram.

## Decisión

Se elige **C: adaptar un patrón de idempotencia ya mantenido en el proyecto**. El camino oficial es el único autorizado para este publicador; se evita añadir SDK y ninguna vía web o móvil suplanta automáticamente un resultado incierto. La configuración conserva Instagram desactivado por defecto y no requiere migración del esquema del ledger compartido.

## Cambio implementado

* `tools/instagram_publish_guard.py`: reserva atómica por SHA-256 de `IG_USER_ID` y ruta absoluta normalizada de la ficha; SQLite `ActionLedger.reserve` usa `BEGIN IMMEDIATE`, protegido por el candado `action_ledger.exclusive` **por archivo de journal, no solo por ficha**, desde antes de inicializar WAL para evitar una carrera real entre procesos de Linux (reproducida en CI anterior). El journal no guarda capturas, texto, token ni imagen.
* `tools/meta_publish.py`: callback opcional `before_publish(container_id)`, invocado exclusivamente tras verificar `FINISHED` y **antes** del POST `/media_publish`. Los errores de preparación, de permisos o de contenedor (`ERROR`, `EXPIRED`, timeout procesando) ocurren antes de este punto.
* `tools/content_publisher.py`: integra callback/journal solo para Instagram. Un fallo antes del checkpoint es reintentable; desde el checkpoint `UNCERTAIN` bloquea nuevos intentos incluso tras timeout, caída, error al marcar la ficha o reinicio. Si la lectura inicial de Instagram es inverificable, `--apply` falla cerrado, sin enviar.
* `.gitignore`: excluye `00_OPERATIVO/instagram_publish_intents.sqlite3*` y ficheros SQLite asociados.
* `tests/test_instagram_publication_guard.py`: contratos offline con cuenta, tokens, URLs y materiales sintéticos; incluye concurrencia real con **dos procesos**. Los tests preexistentes de `test_meta_publish.py` verifican creación de JPEG y carrusel.

El modo `--apply` y `auto_publicacion.json` siguen siendo los controles de activación; Instagram está deshabilitado por defecto en la configuración del mirror. El código no habilita publicación automáticamente, no llama a Instagram durante los tests y no autoriza una ejecución real. No protege deliberadamente el CLI autónomo `instagram_api.py`: tiene flujo de aprobación propio y no debe considerarse cubierto.

## Retirada y recuperación

Ruta: `00_OPERATIVO/instagram_publish_intents.sqlite3` (incluidos sus sidecars cuando existan). El estado `UNCERTAIN` es irreversible **automáticamente**: tras caída, red caída, 5xx, permiso negado al leer, ausencia en una página parcial o respuesta ambigua, **no se debe cambiar a FAILED ni activar fallback web/móvil**.

Procedimiento humano: (1) detener el worker Instagram, (2) identificar cuenta, ficha y el contenedor anotado por el intento; (3) confirmar directamente en Instagram si hay post, obteniendo media ID/permalink, (4) si existe, marcar la ficha y conservar journal; (5) solo si se demuestra ausencia, respaldar el SQLite y liberar la reserva de esa ficha tras aprobación documentada. Ejemplo de API administrativa, **no ejecutar sin revisión**: `ActionLedger(db).release("instagram_publish", _key(ig_user_id, path_ficha))`. El test `test_corrupt_journal_fails_closed_without_sending` verifica que la corrupción detiene la operación antes del POST. Tras detectar en Windows un manejador heredado de SQLite que permanecía abierto cuando fallaba la activación de WAL, el adaptador realiza `PRAGMA quick_check` en una conexión con cierre explícito **antes** de crear `ActionLedger`; esta comprobación también cierra ante corrupción. Si se pierde, corrompe o mueve la base, detener la publicación y reconstruir la reconciliación antes de continuar; no borrar el journal al revertir el código. Si cambia la ruta física de una ficha o el identificador de cuenta, cambia la clave: requiere reconciliación explícita. Snapshot/backups de SQLite mediante la API de respaldo SQLite, no copiar un archivo abierto sin asegurar consistencia.

**Rollback:** revertir los cambios de este adaptador y desactivar Instagram en `auto_publicacion.json`; preservar journal y marcas de fichas. Cualquier integración en el oficial deberá mapear rutas y aprobación, pues `main` allí no tiene el mismo publicador.

## API oficial y límites de acceso (consulta 09-10-2026)

La colección oficial de Meta explica dos modalidades distintas: **Instagram Login**, para cuentas profesionales Business/Creator, con permisos tales como `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`; y **Facebook Login**, con Página vinculada y permisos distintos (`instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `pages_show_list`, `pages_read_engagement`). No hay acceso universal a posts de terceros ni se debe asumir autorización de comentarios/menciones, webhooks, insights o mensajes. La disponibilidad de cada endpoint exige revisar versión y scopes realmente concedidos. El puente actual sube JPEG a una Página de Facebook sin publicarla: aunque la publicación vaya a `graph.instagram.com`, sigue necesitando token y Página Facebook para alojar el asset. La estabilidad de esa URL CDN y los permisos reales no se comprobaron con cuenta.

Para media, Meta exige que el asset alojado pueda descargarse desde una URL accesible; los contenedores deben finalizar procesamiento antes del POST final. Carruseles y Reels tienen contratos y límites de formato diferentes. Esta PR prueba JPEG/carrusel y errores de contenedor **offline**; no afirma haber verificado en vivo codecs, ratio, cuotas, webhooks, insights, menciones ni permisos de producción.

Referencias primarias:
* [Meta — Instagram API with Instagram Login](https://www.postman.com/meta/instagram/folder/1z5vxzu/instagram-api-with-instagram-login)
* [Meta — Instagram API with Facebook Login](https://www.postman.com/meta/instagram/folder/u4g5a2a/instagram-api-with-facebook-login)
* [Meta — Instagram API: endpoints y contratos de media](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
* [Meta Business SDK Python 26.0.2](https://github.com/facebook/facebook-python-business-sdk/tree/26.0.2), [licencia del tag](https://github.com/facebook/facebook-python-business-sdk/blob/26.0.2/LICENSE): concede uso/distribución relacionado con las APIs de Facebook; no denominar MIT.
* [instagrapi 3.0.20](https://github.com/subzeroid/instagrapi/tree/3.0.20), [licencia MIT del tag](https://github.com/subzeroid/instagrapi/blob/3.0.20/LICENSE); no se usa API privada.
* [OWASP, seguridad de la cadena de suministro](https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html).
* [GitHub, comprobaciones y protección de ramas](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

La comparativa considera compatibilidad Windows/Linux (Python 3.11 y `sqlite3`), un grafo de dependencias externas sin cambios y minimización de datos. No se midieron CVE/depencencias transitivas de componentes no incorporados como pretexto para declararlos seguros.

## Licencias y procedencia

Fuente primaria: https://www.postman.com/meta/instagram/folder/1z5vxzu/instagram-api-with-instagram-login
Fecha de consulta: 2026-10-09
Licencia SPDX: NOASSERTION
Referencia inmutable: N/A (sin codigo incorporado)

El campo `NOASSERTION` significa que **no se afirma licencia SPDX del código del repositorio propio**; el cambio es código propio y no se ha importado software público ajeno. Los componentes *evaluados* sí tienen licencias contrastadas: `instagrapi` 3.0.20 es MIT, según el fichero LICENSE del tag; el Business SDK 26.0.2 posee licencia específica de Meta, no MIT. Procedencia del patrón: `tools/action_ledger.py` ya presente en el mirror antes del HEAD original `5d00c7f23b75a56ff790ea768029b930adbd70bb`. Sus ficheros se citan por rutas/SHAs de este repo, sin copiar código del privado. Enlaces inmutables de candidatos en la sección API anterior.

## Pruebas, refutación y coordinación

Comandos existentes de CI: `python -m pip install -r requirements-ci.txt`; `python -m compileall -q tools tests`; `python -m pytest tests -q -p no:cacheprovider` (con los `--deselect` del workflow). Subconjunto recomendado: `python -m pytest -q tests/test_instagram_publication_guard.py tests/test_meta_publish.py tests/test_content_publisher.py`. Los resultados reales de CI se documentan en `BLOQUEOS_PARA_CLAUDE.md`, no se presume éxito por la existencia del test.

Escenarios adversariales:
1. Timeout tras envío confirmado o ambiguo + segundo worker: journal `UNCERTAIN`, segundo POST bloqueado.
2. Dos procesos simultáneos: solo uno obtiene reserva del SQLite; el segundo no entra en `submit`.
3. Permiso o contenedor defectuoso **antes** de publicar: fallo reintentable, sin llamar al POST final; si verificación del perfil no funciona, el plan `--apply` se detiene.
4. Crash tras envío y antes de `mark_done`: se conserva `UNCERTAIN` y se impide duplicación.
5. Fichero SQLite corrupto o almacenamiento no persistente: error debe detener publicación; no borrarlo para «arreglarlo».

Coordinación: #15 Facebook comparte `meta_publish.py` pero los endpoints FB no cambian; #19 TikTok comparte el riesgo conceptual pero no código; #27 controla navegador/móvil y no debe usarse de fallback automático; #28 formatos multimedia y assets conserva su ámbito. En la fecha de consulta sus diffs eran únicamente fichas de encargo. También existen #20 publicación y #26 colas/recuperación; una eventual utilidad compartida requiere revisión conjunta y **no** incorporar cambios de esas ramas aquí. Riesgo pendiente: no haber verificado el ensamblaje de este mirror adelantado con el `main` privado del oficial; comprobación imprescindible antes del merge/despliegue.
