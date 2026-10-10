# PR #99 — Puentes offline de observaciones de hashtags
Fecha de contraste: **2026-10-10**. Rama `research/hashtag-observation-adapters`.
SPDX del código propio nuevo: **MIT**. No se han copiado líneas de terceros.

## Necesidad y decisión

La PR [#63](https://github.com/davidpd89/ci-sandbox-tmp/pull/63) acepta `network/source/post_id/author_id/created_at/text/tags` y un feedback agregado `network/tag/eligible/engaged/replies/followers`, pero los colectores aún no le entregan el mismo formato. #99 **no** modifica el motor de #63 ni la selección/acciones de #21, #23, #70 o la PR #101.

Se implementó `tools/hashtag_observation_adapters.py`: normalizador determinista read-only, sin llamadas de red ni I/O. Cada `add_posts(network,queue,source,rows)` recibe lecturas proporcionadas por el colector; `to_engine_rows()` construye observaciones **transitorias que contienen identidades** y se pasan **en memoria** a `build_snapshot` de #63 cuando se integre. No guardar dichas filas ni incorporarlas al espejo; el exportable permitido aquí es `aggregate_report()` y `feedback_aggregates()`. Descartar la instancia equivale al rollback del estado.

El valor añadido es la normalización de nueve contratos heterogéneos y 27 rutas lógicas (9 redes × 3 colas) sin acoplar cola, política de publicación ni permisos de un servicio. **Las 27 rutas probadas son entradas sintéticas; no se han activado 27 productores reales.** Los `source` se prefijan por cola (ej. `API:search`) para conservar procedencia. La misma identidad de post en fuentes distintas se entrega por cada fuente y #63 la reúne sin doble recuento.

## Matriz de extracción y cobertura real pendiente

| Red | Post ID | Autor estable | Fecha autoritativa | Texto | Tags nativos | Colector contrastado / puente vivo |
| --- | --- | --- | --- | --- | --- | --- |
| X | id_str/rest_id/id | user.id_str/id | created_at (ISO o RFC 2822) | full_text/text | No: literal # del texto | `tools/x_scan.py` (privado): WEB; su salida URL+texto no garantiza autor ID ni fecha; pendiente |
| Threads | id | user_id/user.id | timestamp | text/caption | No: literal # del texto | `tools/threads_scan.py` WEB y API disponibles parcialmente; pendiente |
| Facebook | id | from.id | created_time | message/text | No: literal # del texto | `tools/facebook_scan.py` WEB, `facebook_api.py`; pendiente |
| Pinterest | id | creator.id/owner.id | created_at | description | tags[] | `pinterest_scan.py` se declara retirado; validar productor alternativo `pinterest_growth.py` |
| Reddit | name (t3_) | author_fullname, author.name o username | created_utc UNIX UTC | title+selftext | **Ninguno** (no nativo) | `reddit_scan.py` WEB; enriquecer IDs/fecha mediante lector real |
| Bluesky | at:// URI | author.did | record.createdAt | record.text | record.tags y facets tag | `bluesky_growth_scan.py` API guarda posts; añadir exportación en memoria |
| Mastodon | URL global del post | account.url global | created_at | HTML content→texto | tags[].name | `mastodon_growth_scan.py` API guarda statuses; añadir exportación en memoria |
| TikTok | id/aweme_id | author.uid/id | createTime UNIX UTC | desc/caption | challenges/title, textExtra/hashtagName | `tiktok_growth_scan.py` MOBILE; muchas capturas carecen de fecha/uid: omitir |
| Instagram | id/pk | user.id/owner.id | timestamp o taken_at UNIX UTC | caption.text | hashtags[] cuando los hay | `instagram_commenters_scan.py` WEB/MOBILE, falta fecha/post ID fiables en resultados |

**Compatibilidad en cola ≠ soporte nativo disponible.** WEB, API y MOBILE se contabilizan por separado; un productor puede omitir datos sin que otro fabrique la fecha, autor, etiqueta o la cola. Etiquetas vistas en una búsqueda no se asignan al post. Las tildes y la ñ se mantienen en NFC: `#año` no se convierte en `#ano`. Reddit puede contener un `#hashtag` literal en el texto, pero no se registra como etiqueta nativa.

Se leyó la rama oficial `davidpd89/rrss-davidporto-CODE:integracion/crecimiento-2026-10` únicamente para confirmar los contratos de los colectores; **no** se copiaron datos, estados, configuraciones ni secretos. El espejo no tiene toda la instrumentación operativa del privado. Preservar `tag_seeds()` de `discovery_terms.py` del oficial al integrar #63 y #99; no reemplazar ese módulo por el del espejo.

## Identidad, calidad, feedback y límites

- Deduplicación por `(network,post_id)`. IDs homónimos entre redes no colisionan. Mastodon exige URL global de post y de autor para no mezclar servidores. Cuando dos versiones del mismo post discrepan en texto, autor o fecha, se excluye la identidad conflictiva entera; las fuentes idénticas se acumulan sin doble sumar el post.
- Fechas necesariamente conscientes de zona, pasado conocido y antigüedad **máxima de 14 días**. Se omiten futuras, sin fecha, ambiguas o antiguas. Esto filtra **observaciones para el ranking**, no sustituye el control más estricto de edad antes de responder o dar like a un destino. No añade acciones en redes; en X tampoco auto-like.
- Tamaño máximo: 10.000 filas por llamada y 10.000 caracteres por texto. Ninguna lista de observaciones se persiste por el módulo; metadatos agregados y contadores no contienen IDs/texto.
- Feedback requiere `event_id` estable, `window` con zona, etiqueta y los cuatro enteros no negativos **explícitos** (incluido `eligible`). `engaged <= eligible`; eventos repetidos en distintas colas cuentan una vez; valores contradictorios invalidan toda la identidad, sin orden arbitrario. Sin denominador o con resultados y cero elegibles se rechaza, nunca se imputan seguidores o respuestas.
- El exportable `feedback_aggregates()` solo contiene por red/etiqueta los cuatro números aceptados; ni evento, ni ID de publicación, ni ventana, ni credencial. **No ofrece atribución causal**: el productor debe determinar y verificar previamente qué evento corresponde a qué hashtag; este puente jamás infiere éxito desde un like.
- La salida `to_engine_rows()` es delicada y debe permanecer en memoria durante el procesamiento. No imprimirla, no volcar a un fichero, no adjuntarla a CI. `aggregate_report()` expone cobertura por red/cola y causas de descarte sin perfiles ni mensajes.

## Comparación de software público (commits fijos y licencias comprobadas)

| Candidato | Referencia inmutable, licencia | Estado / Python Windows 3.11 | Decisión |
| --- | --- | --- | --- |
| [MarshalX/atproto](https://github.com/MarshalX/atproto/tree/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8) | [MIT](https://github.com/MarshalX/atproto/blob/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8/LICENSE) | Commit 02/10/2026, SDK >=3.9 <3.15, multiplataforma; PyPI 0.0.72 (10/09/2026) | Reutilizar la estructura `record/facets` como contrato de entrada. No añadir cliente para procesado offline |
| [halcy/Mastodon.py](https://github.com/halcy/Mastodon.py/tree/336a62d850a28f6f066a26b83506ed70f0f4b906) | [MIT](https://github.com/halcy/Mastodon.py/blob/336a62d850a28f6f066a26b83506ed70f0f4b906/LICENSE) | Commit 07/10/2026; entradas tipo status, soporta Python moderno; SDK solo se usa en el colector existente | Consumir la forma `status/account/tags`; no vendorizar |
| [praw-dev/praw](https://github.com/praw-dev/praw/tree/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1) | [BSD-2-Clause](https://github.com/praw-dev/praw/blob/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1/LICENSE.txt) | Commit 09/10/2026, `requires-python >=3.10`, classifiers Windows-independent; dependencias prawcore, requests vía dependencias indirectas | Compatible si el colector lo adopta; aquí aceptar `name/created_utc/author` sin instalarlo |
| [Motor interno #63](https://github.com/davidpd89/ci-sandbox-tmp/pull/63) | Código del proyecto | Python 3.11, stdlib; probado Ubuntu/Windows en su PR | Conservar ranking y sus límites. Añadir solo puente de lectura en esta PR |

Fecha y actividad corresponden a los commits indicados; se comprobaron los ficheros LICENSE de los tres primeros, sin extraer código. Licencia propia declarada MIT siguiendo el proyecto; no hay dependencias ni imágenes vendorizadas. Motivo para continuidad: importar SDKs para un paso offline sumaría transporte, autenticación y actualización sin mejorar la normalización de observaciones suministradas; depender de ellos aquí podría romper el aislamiento de colas.

## Prueba ejecutable y entrega

```bash
python -m compileall -q tools/hashtag_observation_adapters.py
python -m unittest discover -s tests -p test_hashtag_observation_adapters.py -v
python tools/validate_open_source_campaign.py
```

Workflow: `.github/workflows/hashtag-observation-adapters.yml` (Ubuntu y Windows Python 3.11, fixtures creados dentro del test; sin cuentas ni acceso social). Cubre 9×3 caminos sintéticos, contratos, idempotencia, colisiones entre redes/fuentes, conflicto, Unicode, texto HTML, fechas nulas/naive/futuras/viejas, entradas vacías, feedback insuficiente, error de forma, rollback mediante destrucción de objeto y exportaciones libres de IDs. Estos tests muestran corrección del adaptador **solo sobre fixtures artificiales**, no resultados reales de crecimiento.

### Segundo code review adversarial (tras el primer verde)

1. **Descubrimiento:** los datos tipo PRAW pueden aportar `author.name` en vez de `author_fullname`; añadida compatibilidad para username estable, sin crear un ID ficticio.
2. **Descubrimiento:** un feedback con `eligible=0` y `replies>0` era aceptado, pese a no tener denominador atribuible; ahora se excluye y tiene regresión.
3. **Descubrimiento:** `record.facets[].features` con estructura distinta de lista invalidaba el post completo; ahora se ignora la lista inválida y conserva la observación principal.
4. **Contención:** dos versiones discordantes de un post y de un evento de feedback no se resuelven por orden de llegada, sino descartando el elemento ambiguo y contando conflictos.
5. **No alcance:** no se conectaron colectores al flujo de operación real ni se ha medido conversión. Falta el ensayo de integración de #63/#99, no un parche en el ranking.

### Plan de integración, canario y retirada

Tras aceptar #63, Claude puede insertar adaptaciones **solo de lectura** inmediatamente después de las lecturas de cada colector y antes del plan de acciones, comprobando que ID, autor, fecha y texto provengan del post y no del resultado de búsqueda. Usar instancias por ronda/ventana; si se necesita fusionar colas, alimentar una instancia común para evitar doble conteo. Ejecutar `snapshot = build_snapshot(bridge.to_engine_rows(), feedback=bridge.feedback_aggregates(), now=...)` **sin guardar observaciones**; persistir únicamente el snapshot agregado ya definido en #63. Backfill <=14 días y sin tocar métricas históricas. Si no hay datos fiables, lista vacía y comportamiento estático de #63.

Canario **supervisado pendiente para Claude**: Windows de trabajo (Unicode/paths), Edge (lector WEB), dispositivo Android (MOBILE), lecturas reales API autorizadas, normalización de Reddit/Pinterest/Instagram/X sin timestamp, colisiones federadas y benchmarking de aceptados/descartados por fuente; comparar ranking estático y nuevo sin publicar/seguir/comentar. No confundir este canario con la simulación de CI.

Rollback reversible: retirar las llamadas propuestas a `add_posts` y `add_feedback`, dejar deshabilitada la generación de snapshot opcional #63 y descartar el objeto en memoria. No se requieren migraciones ni modificar bases de datos.

## Límites explícitos

No existe garantía de crecimiento; falta evidencia operacional de los colectores y de la atribución de feedback. Los nombres de campos de los SDKs deben verificarse contra payloads actuales reales **antes** de conectar. Las tres colas se modelan por contrato, no se han ejecutado rondas WEB/API/MOBILE. Sin interacciones sociales, credenciales, escrituras de estado ni merge.
