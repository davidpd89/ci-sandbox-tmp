# PR #70 — Audiencias desde likes, comentarios y reposts (10/10/2026)


## Problema
Identidades e interacciones capturadas en formatos incompatibles, sin deduplicación transversal ni métricas por superficie/semilla. No confundir contadores agregados con una lista de cuentas.

## Alternativas
Se compararon atproto, Mastodon.py, PRAW, instagrapi y granary (commits fijos en la tabla inferior), frente a conservar los colectores actuales y añadir únicamente una capa común de importación sin nuevas dependencias.

## Licencias y procedencia
Fuente primaria: https://github.com/MarshalX/atproto/tree/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: N/A (sin codigo incorporado)

Las alternativas detalladas abajo tienen MIT, BSD-2-Clause y CC0-1.0 según fuente (instagrapi declara MIT en su LICENSE, mientras GitHub metadata no expresa SPDX). No se han copiado archivos ni fragmentos de terceros: la capa Python/SQLite es nueva y los clientes permanecen fuera de este cambio.

## Decisión
Mantener los capturadores propios para WEB/API/MOBILE e introducir `audience_discovery.py` junto con `audience_adapters.py`: este último traduce listas de actores ya recuperadas en las 9 redes a páginas comunes; rechaza exportaciones anónimas y comentarios sin ID. Los adaptadores no ejecutan operaciones externas. La cola del producto no se modifica.

## Pruebas
`python -m unittest discover -s tests -p 'test_audience_*.py' -v`, con fixtures sintéticos. El workflow `Audience discovery offline (PR 70)` ejecuta Windows y Ubuntu, Python 3.11. Las regresiones específicas prueban identidad, replays, caducidad, paginación y listas nativas de 9 redes.

## Retirada
Borrar los dos módulos `tools/audience_*.py`, las dos suites `tests/test_audience_*.py` y el workflow `.github/workflows/audience-discovery-offline.yml`. No se ha migrado ninguna tabla operativa. Las bases SQLite temporales creadas por ensayos son independientes y se pueden retirar sin pérdida del estado original.


## Necesidad y comparación con el código real
El espejo público y la rama oficial privada `integracion/crecimiento-2026-10` fueron consultados **en lectura**. Comprobación de contratos existentes: `tools/instagram_commenters_scan.py` (parsing de comentaristas y scoring Instagram), `tools/tiktok_discovery.py` (superficies mobile y candidatos), `tools/bluesky_taste_collect.py` (likes Jetstream -> SQLite), `tools/bluesky_jetstream_collect.py` (feeds), `tools/candidate_identity.py` (identidades de ejecutores Bluesky/Mastodon), `tools/scan_common.py` (cribado común) y `tools/round_queue.py` (WEB/API/MOBILE). **No se copiaron datos del privado al espejo**. Los nombres y formas de filas se contrastaron; los datos sintéticos son inventados. La rama oficial no se modifica.

**Hueco comprobado:** cada fuente expone señales y contadores propios pero falta un contrato compartido para conservar actor, fuente, evento, edad del post y estado de paginación; contar candidatos entre varias superficies y clasificar su afinidad sin tratar un `like_count` como lista de personas.

## Superficies por red (capacidad condicionada a la fuente concreta)

| Red | Likes/boosts/reposts con actor | Comentarios/conversaciones con actor | Cola y grado de adaptación |
| --- | --- | --- | --- |
| Bluesky | `app.bsky.feed.getLikes`, `getRepostedBy`, likes Jetstream de DIDs seleccionados | thread/replies por API | API; hidratación del post y normalización |
| Mastodon | `statuses/:id/favourited_by` y `reblogged_by` con paginación `Link` | `statuses/:id/context` | API; ID local siempre acompañado por instancia |
| Reddit | Votantes de posts **no identificables** a partir del contador | comments/replies, autor por respuesta | API; `None` para likers, no cero |
| X | Listas cuando se obtienen identificadores visibles/API, no inferir desde contadores | replies/quotes de lectura | WEB/export existente; ID estable cuando disponible |
| Threads | No asumir roster de likers desde número de likes | respuestas propias/visibles según superficie | WEB/API; los datos ausentes se etiquetan |
| Facebook | Algunas vistas de reacciones aportan actor, otras solo conteo | comentarios de página/post por superficie | WEB/API; no fabricar identidad de un total |
| Pinterest | métricas agregadas de Pin no aportan por sí mismas autor de likes | solo export observado con autor, si existe | WEB; sin roster inferido |
| TikTok | Research Video API publica `like_count`, no lista de autores | interfaz móvil sí puede revelar usuarios; Research Comments API devuelve ID/texto sin identidad del autor | MOBILE; no generar seguidores desde Research API |
| Instagram | interfaz con cuentas visibles, si accesibles | escáner existente de comentaristas sobre posts-semilla | WEB; requiere post y comentario identificados para importar eventos |

**Fuentes:** [Bluesky API](https://docs.bsky.app/docs/api/app-bsky-feed-get-likes), [Mastodon método oficial](https://docs.joinmastodon.org/methods/statuses/), [Mastodon IDs locales](https://docs.joinmastodon.org/client/public/), [TikTok comments Research](https://developers.tiktok.com/docs/en/research-api-specs-query-video-comments), [TikTok Research Codebook](https://developers.tiktok.com/docs/en/research-api-codebook), [Pinterest Pin API](https://developers.pinterest.com/docs/api/v5/pins-list/), y código oficial/espelho antes citado. Confirmar capacidades en canario por cuenta y región; no hay garantía universal de acceso a cada roster.

## Comparación de repositorios públicos (consultados el 10/10/2026)

| Candidato / commit fijo | Licencia/actividad | Valor y coste de integración | Decisión |
| --- | --- | --- | --- |
| [MarshalX/atproto @ 4c17895](https://github.com/MarshalX/atproto/tree/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8) | MIT; actividad 02/10/2026; Python 3.11 | XRPC, tipado lexicon y paginación para Bluesky; SDK opcional existente según superficie | Reutilizar en futuros fetchers donde ya está instalado, **no copiar** núcleo |
| [halcy/Mastodon.py @ 336a62d](https://github.com/halcy/Mastodon.py/tree/336a62d850a28f6f066a26b83506ed70f0f4b906) | MIT; actividad 07/10/2026 | paginación, API y errores; Python multiplataforma | Reusar para fetch de `favourited_by`, sin dependencia en módulo genérico |
| [praw-dev/praw @ 4a9eb7e](https://github.com/praw-dev/praw/tree/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1) | BSD-2-Clause; actividad 09/10/2026 | comments/replies y MoreComments; no permite identificar votantes | Mantener cliente del ejecutor/API, no copiar el ORM |
| [subzeroid/instagrapi @ 11f8fd5](https://github.com/subzeroid/instagrapi/tree/11f8fd5e0c5bef9eeae0183e0c2d530e07f8e8a1) | licencia MIT en fichero LICENSE; GitHub metadata `NOASSERTION`; actividad 09/10/2026; Python 3.10+ | API privada compleja, dependencias de transporte/dispositivo | No añadir: el escáner WEB ya extrae comentaristas sin nuevo SDK |
| [snarfed/granary @ 7c07cb9](https://github.com/snarfed/granary/tree/7c07cb988af889618d6bc4c1d9667b52e8c89f0c) | CC0-1.0; actividad 08/10/2026 | modelo ActivityStreams multired, dependencias de traducción | Patrón de *normalización* útil, pero innecesario copiar transformaciones completas |

Todas estas alternativas permiten estudiar el patrón y/o usar sus bibliotecas bajo sus licencias; **no se ha copiado código externo**. Sin nuevas dependencias se reduce el coste de instalación en Windows/Python 3.11. Licencias y commits quedan fijados arriba para reproducir la comparación. La actualización de APIs remotas deberá validarse cuando se conecten colectores reales.

## Implementación de esta rama

- `tools/audience_discovery.py`: `normalize` convierte observaciones *ya capturadas* con `actor`/`user`/`account`/`author`, `event_id`, fuente, post y reloj explícito a un contrato único. Identidad estable cuando existe (`did`, `id`, etc.) y provisional etiquetada si solo hay handle. En Mastodon el ID local se califica por instancia. No confunde autor de post con actor de engagement.
- `AudienceStore` persistente SQLite **separado** del estado real. Índices, transacciones por página, idempotencia, tomas sucesivas, eventos borrados/tombstone y rechazo de replay anterior. `new_people`, `new_events`, `replays`, `stale_posts` y `unverified_age` permiten auditar el rendimiento.
- `collect_pages`: recibe una función de lectura inyectada, maneja paginación parcial, checkpoint por red/superficie/semilla y cursor cíclico o inválido. Si falla la segunda página, queda la primera confirmada.
- `ranked`: score transparente por comentario/reply/like/repost, texto del nicho, diferentes posts y distintas superficies; orden determinista, límite y recálculo de edad. No genera textos, follows ni acciones. Al ser un componente pasivo no altera las 3 colas.
- `CAPABILITIES`: `None` cuando no hay roster, evita convertir conteos de reacciones en personas ficticias.

**Antes/después (evidencia, no predicción):** antes los escáneres/collectors mantenían formatos y memorias independientes; ahora una observación normalizada de cualquiera de las 9 redes admite misma deduplicación, conteo y ranking. La suite reproduce dos observaciones idénticas sin doble evento, cambio de handle conservando DID, eventos posteriores y antiguos fuera de orden, y dos superficies sumando señales sin duplicar persona. No existe aún una medición real de nuevos seguidores **atribuibles** al nuevo núcleo: instalar bridges de datos es un paso separado y requiere canario.

**Contrato de integración para Claude:** (1) leer desde el colector que corresponda sin acciones sociales, (2) añadir `actor` (ID estable + handle cuando se conozcan), `event_id` real para comentario/reply; para like/repost basta actor estable + post, (3) suministrar `post_key` y `post_created_at` del post original, `observed_at` con zona, (4) pasar páginas a `collect_pages` con fetcher inyectado, (5) usar `ranked` como fuente de selección, manteniendo el filtro y control de acciones en escáner/ejecutor. **No mezclar el resultado con una orden de seguir automáticamente.** Los actuales JSON de Instagram no incluyen ID de comentario/post y los likes de taste necesitan hidratar fecha original: no atribuirles eventos individualizados inventando claves.

## Pruebas, rollback y revisión adversarial

Ejecución: `python -m unittest discover -s tests -p test_audience_discovery.py -v`; workflow independiente en `.github/workflows/audience-discovery-offline.yml` sobre Windows/Ubuntu Python 3.11. Sin red, estado productivo, tokens ni cuentas. Probar con datos de prueba controlados. El workflow de validación de campaña exigía este documento de evidencias, corregido en esta revisión.

**Revisión 1:** identidades locales de Mastodon, eventos duplicados, paginación interrumpida, timestamps sin timezone, cambio de handle, rollback de lote inválido, canarios sintéticos de las 9 redes. Detectado defecto en fixture: una prueba de likes usaba `own_post` como superficie mientras la observación decía `liked_by`; reparado, no relajando el control.

**Revisión 2 (adversarial):** (a) detectado riesgo de resucitar un like borrado por replay tardío: comparación de *event time* cuando disponible; (b) evitar ranking sobre un post que envejece después de su inserción: revisión de caducidad a la lectura; (c) falta de ID estable: se marca `stable_identity=False`, sin fusionar personas basándose en un handle renombrado. Regresiones añadidas.

**Limitaciones explícitas:** los adaptadores de lectura real a cada API/Edge/MOBILE aún no están conectados; disponibilidad variable por red/superficie; comentarios sin `event_id` real se rechazan; lista sin fecha verificable se guarda pero no se propone para acción; `occurred_at` debe representar reloj consistente de la mutación en fuentes de streaming; los resultados de ranking son heurísticos, no estimaciones de reciprocidad calibradas; no se ha probado Edge ni Android ni se ha ejecutado canario supervisado. No se asegura cobertura 100 %. Integración real debe respetar las PR abiertas #11, #21, #25, #26, #60, #63, #65, #69 y #95 sin copiar ni sustituir sus contratos.

**Rollback:** eliminar `tools/audience_discovery.py`, sus pruebas y su workflow; ninguna tabla operativa cambia. Si se creó un archivo SQLite específico de ensayo, archivarlo o eliminarlo manualmente; no comparte DB por defecto con Jetstream, queue ni perfiles. No hay migración irreversible.


## Evidencia CI verificable (HEAD de código 3a322789, 10/10/2026)

- [Audience discovery offline / run 38015734972](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38015734972): **41/41 tests** sintéticos en Python 3.11 sobre Ubuntu y Windows, ambos jobs `success`.
- [Validador de campaña / run 38015734930](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38015734930): **success en Ubuntu y Windows** tras corregir las reservas de dominios sintéticos y aportar metadatos de investigación.
- [Suite general de herramientas RRSS / run 38015732119](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38015732119): iniciada y todavía en ejecución al redactar este bloque; no se anticipa su resultado.
- El test de tres colas es de **importación y persistencia offline**. No se verificó Edge ni TikTok móvil ni un canario con cuentas; queda para Claude.

**Hallazgo no resuelto en esta PR:** los endpoints que enumeran likers/boosters como snapshots completos no anuncian necesariamente un evento `delete` cuando una cuenta desaparece de la siguiente captura. No se debe inferir ausencia hasta terminar todas las páginas; necesita reconciliación específica con watermark, aislamiento por post y rollback ante páginas faltantes. Es distinto del replay del listener Jetstream cubierto por #95.

## Auditoría de control posterior (10/10/2026)

Se revisaron cuatro observaciones inline del HEAD inicial de la PR y se corrigieron
con pruebas de regresión offline. El identificador canónico de cada evento deja
de depender de la superficie; `audience_sightings` conserva las procedencias
por superficie y semilla. Un evento repetido mantiene **una señal y un único
incremento de afinidad**, aunque aparezca en varios listados.

La promoción provisional→estable exige evidencia del **mismo evento remoto**
y del mismo handle. Una coincidencia de handle en eventos diferentes **no**
es prueba suficiente, especialmente ante reciclado de nombres. Un replay
provisional posterior no revierte una promoción. Esta restricción no equivale
a un servicio general de resolución de alias; coordinar con #85.

La historia de cursores por (red, superficie, semilla) persiste en SQLite durante
capturas parciales y se limpia solo al alcanzar el final. Se rechazan ciclos que
crucen varias ejecuciones con `max_pages=1`. La capa de importación acepta
respuestas `thread.replies` anidadas de Bluesky (sin atribuir el post raíz),
`descendants` de Mastodon y árboles Reddit ya expandidos. Un placeholder
`BlockedPost`/`NotFoundPost` hace que `coverage_complete=False`, y el
resultado de `collect_pages` no debe darse por snapshot completo. Los
`MoreComments` de Reddit sin expandir se rechazan. Los registros posteriores
sin fecha de post/texto no borran valores anteriormente verificados.

**Compatibilidad y límites:** no hubo migración de tablas operativas porque estos
módulos no están conectados al producto. Las SQLite experimentales hechas con
commits antiguos de esta PR usaban claves de evento que incluían `surface`;
**no reutilizarlas sin migración**. Para pruebas sintéticas, archivar/eliminar
únicamente esa SQLite experimental y crear otra; nunca borrar estados de
producción. Antes de activar lectores reales, preparar migración explícita
desde cualquier prototipo persistente, backfill y rollback. Los nueve nombres
de red no equivalen a nueve puentes operativos: contrastar la cobertura
con #100, #66, #85 y el código oficial. Las capturas de snapshots de likes
incompletos y `unlike` siguen delegadas a #102; no resolverlo mediante
desapariciones inferidas.

La comparativa de clientes permanece: el SDK
[atproto](https://atp.readthedocs.io/en/latest/guides/reading/)
ya describe `get_post_thread`, `get_likes` y `get_reposted_by`;
[Mastodon.py](https://mastodonpy.readthedocs.io/en/stable/05_statuses.html)
ofrece `status_favourited_by` y `status_reblogged_by` como listados de
cuentas (no asumir una paginación genérica del wrapper); PRAW resulta útil
para comentarios y `MoreComments` pero no revela votantes;
[granary](https://github.com/snarfed/granary) aporta conversiones
multiplataforma con más complejidad de la necesaria para esta capa de
normalización. No se incorpora código ni dependencia nueva.

### Comprobaciones para el integrador (sin sesiones ni acciones sociales)

1. En un checkout limpio de la rama, verificar `git rev-parse HEAD`,
   `git diff --check origin/research/public-reuse-parent...HEAD`
   y `git rev-list --left-right --count origin/research/public-reuse-parent...HEAD`.
   Antes de integrar, actualizar/sincronizar la base y repetir los checks del
   merge resultante, pues la rama base avanzó durante esta auditoría.
2. En Linux: `python3.11 -m unittest discover -s tests -p 'test_audience_*.py' -v`;
   `python3.11 -m compileall -q tools/audience_discovery.py tools/audience_adapters.py`.
   En Windows PowerShell: `py -3.11 -m unittest discover -s tests -p 'test_audience_*.py' -v`;
   `py -3.11 -m compileall -q tools/audience_discovery.py tools/audience_adapters.py`.
3. En el checkout del repositorio privado, con fixtures y dependencias propias,
   lanzar la suite general definida por su CI. No suponer que esta suite
   aislada valida `round_queue`, escáneres Edge, Android ni ejecución real.
4. Contrastar payloads **de lectura** de cuentas de prueba para Bluesky
   `getPostThread/getLikes/getRepostedBy`, Mastodon
   `status_context/favourited_by/reblogged_by`, Reddit `MoreComments`
   y los exports WEB/MOBILE. Verificar `actor`, `event_id`, `post_key`,
   `post_created_at`, `coverage_complete` y cambio de handle.
5. Antes de cualquier conexión productiva, comprobar independencia de la
   SQLite de audiencia, permisos de lectura, snapshot parcial e interrupción
   tras la primera página; no activar follows, comentarios ni publicaciones.
