# Reddit: control offline de contexto antes de comentar
Fecha de consulta: **2026-10-09**. Rama: `research/08-reddit` (mirror público).
Decisión: **C — patrón propio mínimo, sin añadir SDK ni publicar**.

## Problema

El preflight operativo original no verificaba un snapshot estructurado de hilo, comentarios y revisión humana antes del envío. Una aprobación de subreddit se podía reutilizar con otro texto o hilo; los `t1` tampoco acreditaban por sí solos pertenecer al `t3` previsto.

## Alternativas

Se contrastaron PRAW 8.0.3 y Async PRAW 8.0.3 (BSD-2-Clause), RedditWarp (MIT; último commit principal verificado de julio de 2024), Devvit y continuidad del CDP actual. Ninguna dependencia externa aportaba un preflight offline mejor con coste operativo inferior. La matriz, versiones, procedencias y alternativas rechazadas están desarrolladas más abajo.

## Licencias y procedencia

Fuente primaria: https://www.reddit.com/dev/api/
Fecha de consulta: 2026-10-09
Licencia SPDX: NOASSERTION
Referencia inmutable: N/A (sin codigo incorporado)

No se reutilizan archivos ni dependencias de Reddit/PRAW/RedditWarp/Devvit. El análisis de la forma pública del objeto `Listing` inspira validaciones propias implementadas con biblioteca estándar; las licencias concretas de los candidatos figuran en la comparación detallada.

## Decisión

Salida **C**: conservar el ejecutor/CDP existente y añadir un comprobador offline puro, sin comunicación con Reddit. Toda aprobación está ligada a post, texto y revisión reciente; el resultado positivo **no concede permiso para publicar**. En el repositorio oficial, la integración bajo bloqueo y la reconciliación de intentos permanecen pendientes.

## Pruebas

`python -m compileall -q tools tests` y `python -m pytest tests -q -p no:cacheprovider` (en CI con ocho tests generales expresamente deseleccionados por dependencias históricas del mirror). Casos sintéticos de identidad, anidamiento, censura, estado HTTP, caducidad y CLI inválido. Ver [workflow del HEAD](https://github.com/davidpd89/ci-sandbox-tmp/actions/workflows/validate-social-tools.yml) y resultados específicos de la PR; nunca se prueba aquí una sesión de producción.

## Retirada

Revertir el módulo, la fixture, ambos archivos de tests y este informe en la rama del mirror. No hay base de datos modificada, cambios en estados operativos ni red. Si se adapta al oficial en el futuro, mantener ese cambio como integración separada y reversible con test de bloqueo antes de escritura.

## Problema y reproducción

El mirror `davidpd89/ci-sandbox-tmp` no incluye los ejecutores `tools/reddit_*.py`. Se inspeccionó el repositorio oficial **privado**, rama `main`, commit `db0edb9328358e0181e67573fa1bd71c55b04fec` (09-10-2026): `tools/reddit_scan.py`, `tools/reddit_execute.py`, `tools/reddit_interact.py`, `SISTEMA_DIARIO_REDDIT/{PROCESO,REGLAS,ESTADO}.md`, `tests/test_reddit_thread_url.py`, `AI_REVIEWER_BRIEF.md` y los puntos de entrada generales. El mirror solo reproduce parte del código anonimizado; no se portan fuentes privadas ni identificadores personales.

El recorrido real es: `reddit_scan.scan` (subreddits mapeados; `shreddit-post`) → lectura manual de hilo con `reddit_interact.dump_thread` → plan JSON editorial → `reddit_execute._preflight_plan` (URL, idioma, duplicados en el plan) → `run_plan` → `reddit_interact.comment` (CDP, cuenta activa, CSV, DOM del hilo y confirmación visual tras recarga) → `_append_registro` solo para estados confirmados → métricas y ESTADO. El consumidor del resultado es `reddit_execute.run_plan`; el `scan` usa la identidad canónica del hilo y el CSV para descartar objetivos repetidos. El proceso común de otras redes usa `scan_common`; los controles propios de Reddit NO deben hacerse globales sin evidencia de paridad.

**Hueco comprobado por inspección**: el `preflight` del plan no usa estado HTTP, antigüedad, `locked`, `archived`, retirada por moderación, contenido de citas o integridad de árbol de comentarios. `comment()` revisa el navegador, pero no un contrato estructurado de esas señales antes de abrir el compositor. Además, `run_plan` captura excepciones genéricas, continúa con otras acciones y `_append_registro` omite los intentos ambiguos: no equivale a reconciliación duradera. Esto último precisa integración privada y no se resuelve desde esta PR.

## Decisión aplicada y alternativas

| Baseline | Candidato 1 | Candidato 2 | Elección | Motivo / riesgo |
| --- | --- | --- | --- | --- |
| CDP + validación de URL/CSV/DOM ya operativa | PRAW 8.0.3 (BSD-2-Clause) para OAuth sincrónico | Async PRAW 8.0.3 (BSD-2-Clause) / Devvit (API de comunidad, otro ámbito) | **C: verificador Python estándar de Listings y revisión humana; conservar CDP sin ampliarlo** | No hay autorización API verificada ni equivalencia de actuar como esta cuenta en comunidades externas; un SDK añade OAuth, costes de mantenimiento y superficie de datos, sin resolver por sí solo la política editorial. El verificador aislado aún no está conectado a producción. |

No se integra código de PRAW, Async PRAW ni Devvit: no se generan obligaciones de atribución de librería redistribuida en la implementación nueva. Las alternativas tienen licencias permisivas, pero esa compatibilidad **no concede permiso para usar la API**. `PRAW` y `Async PRAW` tienen release `v8.0.3` de 12-08-2026; son mantenidas, con interfaz Python 3.10+. Async PRAW añade `aiohttp`/`asyncprawcore` y complejidad asíncrona improductiva para una revisión humana de pocas sesiones. PRAW añade `prawcore` y autenticación OAuth. Devvit usa permisos de la app instalada en la comunidad; su modelo no sustituye automáticamente una sesión de usuario en subreddits ajenos. `prawcore` directamente daría control a nivel HTTP, pero duplicaría trabajo del wrapper. Se contrastó política y actividad, no se inventa un benchmark de API sin credenciales.

Procedencia y referencias permanentes:
- PRAW: [tag 8.0.3](https://github.com/praw-dev/praw/releases/tag/v8.0.3), [commit 4a9eb7e](https://github.com/praw-dev/praw/commit/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1), [licencia BSD simplificada](https://github.com/praw-dev/praw/blob/main/LICENSE.txt).
- Async PRAW: [tag 8.0.3](https://github.com/praw-dev/asyncpraw/releases/tag/v8.0.3), [commit a669548](https://github.com/praw-dev/asyncpraw/commit/a669548484596492714f806652ea9c52ccee190e), [dependencias/licencia](https://github.com/praw-dev/asyncpraw/blob/main/pyproject.toml).
- Devvit: [commit 2aac5a4](https://github.com/reddit/devvit/commit/2aac5a4b5742045de43ee65238b0fa0eb38692da), [documentación API, commit 7557a3b](https://github.com/reddit/devvit-docs/blob/7557a3b3ca9faf9c63c7e0b264b8ad1460b3511a/docs/capabilities/server/reddit-api.mdx), [Devvit Rules](https://github.com/reddit/devvit-docs/blob/main/docs/devvit_rules.md). Es una plataforma con licencia/condiciones por componentes; no se ha importado su código.
- Contrato y restricciones: [API de Reddit, Listings](https://www.reddit.com/dev/api/), [Data API Terms, revisión 20-07-2026](https://redditinc.com/policies/data-api-terms), [Developer Terms](https://redditinc.com/policies/developer-terms), [AutoModerator, 02-10-2026](https://support.reddithelp.com/hc/es-es/articles/52866343172500-Documentaci%C3%B3n-completa-sobre-el-automoderador), [OWASP supply chain](https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html).
- Versión oficial inspeccionada (acceso privado): [reddit_execute.py](https://github.com/davidpd89/rrss-davidporto-CODE/blob/db0edb9328358e0181e67573fa1bd71c55b04fec/tools/reddit_execute.py) y [reddit_interact.py](https://github.com/davidpd89/rrss-davidporto-CODE/blob/db0edb9328358e0181e67573fa1bd71c55b04fec/tools/reddit_interact.py). Enlaces solo para autorizados; no trasladar contenido al mirror público.

## Qué se implementó y contrato

- `tools/reddit_snapshot_preflight.py` evalúa sin red un `plan` de comentario raíz, un envelope `{http_status,retrieved_at,body}` y una revisión humana explícita de normas/lectura/historial. `body` debe tener **dos Listings** de `/comments/<id>.json`: `t3` del hilo y `t1` de comentarios, con `more` bloqueado.
- Valida origen HTTPS canónico y coincidencia exacta de ID/subreddit, vigencia de snapshot (5 min), ventana de **3 días** para comentarios raíz externos (alineada con `post_age_policy.MAX_AGE_DAYS['comment']` de la rama oficial, **no límite de Reddit**; los 7 días de seguimiento son otro tipo de acción), `locked`, `archived`, retirada, restricción de subreddit, revisión de reglas vigente (7 días), CSV informado como `history_state=none`, duplicado por autor, citas con ID existente y no eliminado, AutoModerator que anuncia retirada y contexto de comentarios incompleto.
- Una respuesta HTTP `429`, campos desconocidos o un error de parsing siempre **bloquean**, sin reintento. No envía comentarios, no abre navegador, no registra datos identificables y no gestiona credenciales.
- `tests/fixtures/reddit_snapshot_preflight.json`: estructuras sintéticas con nombres ficticios y campos `Listing/t3/t1` alineados con el JSON de la API; `tests/test_reddit_snapshot_preflight.py`: pruebas de bloqueo, caso válido, comprobaciones adversariales y CLI con proceso real. No es un mock de un endpoint OAuth: **no prueba** la autenticación, cuota, propagación de moderación o veracidad de la revisión humana.

Ejemplo de ejecución offline (tras escribir los tres archivos JSON propios, sin tokens):
```sh
python -m pytest tests/test_reddit_snapshot_preflight.py -q
python tools/reddit_snapshot_preflight.py --plan plan.json --snapshot reddit_listing.json --review revision.json
```
El primer comando tiene el mismo criterio que pytest, pero `python -m pytest tests/test_reddit_snapshot_preflight.py -q` es el comando de CI. CLI devuelve 0 para *apto para revisión*, 2 si bloquea. **Nunca autoriza por sí sola publicar**; el snapshot debe adquirirse de modo autorizado y revalidarse bajo el candado de escritura.

**Paridad de antigüedad (REV 18, 10-10-2026):** el preflight original aceptaba 7 días para un comentario raíz, mientras el contrato común del oficial (`tools/post_age_policy.py`) establece 3 días para `comment` y 7 solo para `follow-up`. Se acota ahora a 3 días con prueba de 4 días bloqueado y 3 días permitido. Al integrar en el privado, **importar** la política compartida y no mantener dos fuentes de verdad. Este módulo sigue siendo offline y no autoriza publicación.\n\n## Riesgos, alcance y retirada

- TOS: cualquier API requiere OAuth autorizado, agente de usuario honesto, consentimiento/aprobación que corresponda y respeto a cuotas; el wrapper no elude estas obligaciones. Devvit puede exigir revisión. Sin acuerdo/permisos confirmados, no consultar la API desde esta PR.
- Privacidad: no guardar cuerpos de mensajes de usuarios, enlaces a perfiles, tokens, correos, cookies ni cookies CDP en este mirror. El snapshot de prueba es **inventado**. El repositorio privado contiene identificadores en el código antiguo; NO se portan.
- Autenticación: el JSON puede alterarse; un booleano `approved_by_human` no es prueba criptográfica de revisión. Esta utilidad es auxiliar, no barrera final independiente; bloquear ejecución hasta integrar una fuente fiable y comprobaciones de estado bajo lock.
- Datos: comentario moderado tras la lectura, respuestas cargadas parcialmente, API 429, estados `deleted` y UI que no refleja el backend pueden dar falsos positivos o negativos. Se opta por bloqueo conservador; los avisos de AutoModerator no tienen frase universal, se necesita revisión humana.
- Coste: **cero dependencias Python externas**, cero solicitudes y cero tokens nuevos; coste de revisión del contrato y de validar API/DOM en integración futura. No hay cifras de rendimiento comparables ni estimaciones monetarias de API.
- Rollback: revertir los commits de `tools/reddit_snapshot_preflight.py`, `tests/test_reddit_snapshot_preflight.py`, `tests/fixtures/reddit_snapshot_preflight.json` y este documento; no hay cambios en base de datos ni estado de producción.

## Coordinación

Las PR mirror [#21](https://github.com/davidpd89/ci-sandbox-tmp/pull/21) (selección), [#22](https://github.com/davidpd89/ci-sandbox-tmp/pull/22) (texto/contexto), [#25](https://github.com/davidpd89/ci-sandbox-tmp/pull/25) (memoria) y [#41](https://github.com/davidpd89/ci-sandbox-tmp/pull/41) (drift API) siguen abiertas y, a la consulta, solo cambian sus encargos. Esta PR no modifica `scan_common`, colas, `ledger`, puntuaciones, writer, historial ni parseadores compartidos. La PR **#44 del repositorio oficial** (otra numeración) fue **fusionada el 09-10-2026 a las 19:54 UTC** en `integracion/crecimiento-2026-10` (merge `d67643cfde384d635592924adcba819bad643c63`). Releer su política de fidelización ya integrada antes de adaptar la utilidad; nunca sobreescribirla.

Orden recomendado: partir de la fidelización ya fusionada en la rama oficial; adaptar luego el verificador a un transport autorizado/DOM bajo lock; solo después extender evaluación/ranking y drift. Una API compartida de status/snapshot deberá pertenecer a #41, no se crea aquí.

## Autorrevisión adversarial

1. **Un plan válido puede comentar tras ser archivado.** Corrección: la función bloquea `archived`/`locked` y snapshots de más de 5 minutos; riesgo residual de carrera entre snapshot y clic **no resuelto**, requiere revalidación bajo lock.
2. **Una respuesta HTTP 200 puede llevar un hilo distinto o árbol incompleto.** Corrección: identidad exacta de `t3` y rechazo de `more` y `num_comments` que supera los `t1` leídos; recuentos de Reddit pueden diferir, así que puede haber bloqueos conservadores.
3. **AutoMod puede retirar sin cambiar un campo que vemos.** Corrección: señal `removed_by_category`, comentarios con avisos inequívocos de AutoModerator y aprobación humana obligatoria; el lenguaje de avisos no es exhaustivo, por tanto no se prometen detecciones universales.
4. **Un fallo posterior al clic puede dejar una respuesta publicada sin ledger.** No lo corrige un verificador previo: se exige reservar intento/reconciliar estado ambiguo antes de cualquier reintento en el repo privado.
5. **Falsa sensación de seguridad por flags manuales.** La utilidad no publica y la documentación exige fuente auténtica, frescura y revisión humana; no sustituye cumplimiento ni revisión editorial.

## Evidencia y pendiente para integración real

El baseline oficial **no se ejecutó en este mirror**: faltan sus módulos. Por inspección de `_preflight_plan` no existe entrada para `Listing` ni HTTP 429; por tanto no puede compararse rendimiento antes/después con idéntico fixture. La nueva prueba reproduce el contrato offline con casos negativos y verifica que el CLI devuelve 2; resultados de ejecución de CI deben asociarse al SHA final de la rama. No contabilizar como pruebas de producción ni como resultado de una consulta a Reddit.

**Estado: BLOQUEADA para producción** hasta llevar una comprobación equivalente al repo privado, auditar permisos API, consumir un snapshot real autorizado (o señales DOM verificadas), enlazarla a `comment()` bajo lock y guardar intentos ambiguos. La PR de investigación puede revisarse como pieza auxiliar independiente, pero no debe llamarse protección instalada en la cuenta real.

## Segunda revisión y medición (CI real, 09-10-2026)

**Revisión 1 — corrección/seguridad:** se reabrió el diff completo: solo cinco archivos (encargo, módulo independiente, test, fixture y este informe); no hay credenciales, cookies, perfiles, identificadores humanos ni llamadas de red. Se corrigió una expresión regular para detectar citas Markdown, y se endurecieron `num_comments` y avisos de AutoModerator. El programa nunca hace escrituras remotas. Su salida 0 significa *apto para revisión*, no autorización de ejecución.

**Revisión 2 — arquitectura/otras PR:** no se modifica `tools/reddit_interact.py`, que también cambia la PR #44 del repo **oficial**. No hay migraciones, bloqueos multiproceso ni cambios de historial/ledger: el módulo es puro salvo lectura de tres archivos JSON por CLI. La concurrencia de dos lectores sobre fixtures inmutables no introduce escrituras, pero no demuestra idempotencia del ejecutor real. La rama padre ha evolucionado y se ha detectado divergencia respecto a la hija; resolver integración corresponde a revisión expresa.

**Medición reproducible:** usando la misma matriz sintética, el control nuevo rechaza **15/15 variantes peligrosas** y admite **2/2 escenarios autorizados para revisión** (baseline + cita válida). No se presenta como comparación cuantitativa contra producción: `reddit_execute.py` oficial no está disponible en mirror y su baseline no se ejecutó con esta matriz. El control previo no evaluaba snapshots estructurados por inspección de fuente; la medición comparada sobre el ejecutor privado está **pendiente**.

| Workflow sobre SHA `6f6a6d5` | Resultado real |
| --- | --- |
| `Validar herramientas RRSS sin acceso a cuentas`, Ubuntu | **SUCCESS**: 1695 passed, 8 skipped, 8 deselected, 2 warnings, 686 subtests passed; [run 37978740553](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978740553) |
| Mismo workflow, Windows | **SUCCESS**: 1698 passed, 5 skipped, 8 deselected, 2 warnings, 686 subtests passed; mismo run |
| `Validar protocolo de campaña pública`, Ubuntu/Windows (run histórico, SHA anterior) | **FAILURE histórico** [run 37978747389](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978747389). No extrapolar al HEAD actual: el validador padre se actualizó; la siguiente regresión identificó encabezados obligatorios en el propio informe Reddit, corregidos aquí. |
| Tests de producción privados / OAuth / DOM / conexión CDP | **NO EJECUTADOS**: no hay fixtures privados ni autorización API en este mirror. |

### Cobertura de criterios de esta PR

| Criterio | Evidencia | Estado |
| --- | --- | --- |
| Rama/base, SHA, mirror y repo oficial | `get_pr_info`, árbol `main` oficial `db0edb9`, PROTOCOL | PASA (lectura); mergeability **pendiente** |
| OAuth, PRAW, Async PRAW, Devvit, términos, licencia | Comparativa y URLs primarias anteriores | PASA (investigación); acceso autorizado **pendiente** |
| Contexto, edad, cerrado, reglas, subreddit restringido | `evaluate`; fixtures `stale_thread`, `closed_thread`, `rules_undocumented`, `restricted_subreddit` | PASA offline |
| AutoMod y respuesta retirada | Fixtures `automod_removed`, `automod_notice`, `own_reply_removed` | PASA offline; detección universal **no garantizada** |
| 429, eliminación, árbol incompleto | Fixtures `http_429`, `partial_tree_count`, `unexpanded_children` | PASA offline |
| Citas, duplicados, idempotencia | `quoted_message_valid`, `quoted_message_missing`, `cited_deleted`, `uncertain_history`; CLI bloquea 429 | PASA offline; persistencia tras envío **pendiente** |
| Bloqueo de escritura real | No hay enlace al ejecutor privado | PENDIENTE |
| CI global Ubuntu/Windows | Run 37978740553 | PASA para herramientas (con skips) |
| Campaña padre, reviews, conflictos | Gate antiguo fallido; nueva evidencia con esquema completo y checks por SHA final | REVALIDAR HEAD |
| Privacidad y no interacción real | Diff revisado, fixtures sintéticos | PASA por inspección |

### BLOQUEOS_PARA_CLAUDE — pasos exactos

1. En la máquina autorizada del repositorio privado, comprobar `git status`, SHA y rama propia. **No** fusionar de oficio este mirror público sobre `main`, ni copiar historiales o sesiones. Revisar primero cambios ya fusionados de PR oficial #44 (`tools/reddit_comments.py`, `tools/reddit_interact.py`) y su aprobación humana.
2. Inspeccionar con cuidado `tools/reddit_execute.py::_preflight_plan`, `run_plan`, `_append_registro`, `tools/reddit_interact.py::comment`, `_comment_history_state` y tests de regresión Reddit. Adaptar la comprobación antes del envío **dentro del lock de navegador**, sin importar código privado al mirror. En el contrato oficial no se admite reintento tras 429/timeout/confirmación ambigua.
3. Resolver preservación de intentos ambiguos en ledger antes de habilitar escrituras; cotejar con el cambio de #44. No tratar un fallo como si nada hubiese sucedido.
4. Solo si existen permisos OAuth reales y revisión de términos, conectar lectura de `/comments/<id>.json`, reglas y estado de usuario; de otro modo utilizar señales DOM comprobables sin ampliar acciones automatizadas. Nunca consumir la fixture como dato real.
5. Ejecutar en el mirror: `python -m compileall -q tools tests` y `python -m pytest tests/test_reddit_snapshot_preflight.py -q -p no:cacheprovider`; luego su workflow global. Ejecutar en el privado **los comandos de tests existentes según sus archivos**, incluyendo `tests/test_reddit_thread_url.py` y `tests/test_r7_reddit_revalidate_under_browser_lock.py` en la rama que realmente los tenga. Probar fallos posteriores al clic, reinicios y dos ejecutores bajo lock. Registrar SHAs y resultados, no inventarlos.
6. Verificar el gate de campaña sobre el HEAD final. El gate actualizado detectó que faltaban seis encabezados y cuatro campos de evidencia en este informe; se añadieron en esta PR, sin modificar manifiesto ni validador padre. La rama difiere de la base: revisar el merge sintético de GitHub antes de integrar y no forzar push.
7. Bloqueos técnicos vigentes: no hay sesión autorizada Reddit para probar la adquisición real del snapshot; el mirror carece del ejecutor/CDP/ledger de producción; falta adaptación y canario supervisado en el privado. La compatibilidad GitHub y CI se reevalúan contra cada SHA. No hubo escritura en Reddit ni prueba real de OAuth.

**Veredicto de integración real: BLOQUEADA.** El verificador independiente y sus regresiones sí están listos para revisión de código, pero no debe describirse como protección ya operativa en la cuenta.

## Revisión adversarial adicional: procedencia del comentario y del consentimiento (09-10-2026)

**Fallo reproducible anterior**: el objeto de revisión exigía `subreddit` y flags humanos, pero no estaba ligado a un **post concreto ni al texto exacto**. Una ficha de revisión válida podía trasladarse a otra conversación dentro de `r/libros` o a un mensaje editado, manteniendo el resultado `allowed=True` si el resto del snapshot coincidía. Además, el recorrido previo aceptaba `t1` de otros hilos al no comprobar `link_id` ni la relación `parent_id` de los nodos anidados. Las citas y comprobaciones de autor podían entonces resolverse sobre objetos ajenos. Son defectos de identidad, no de acceso a la API.

**Corrección aplicada en esta misma PR**:

- El esquema de revisión añade `post_id`, `plan_sha256` (SHA-256 UTF-8 del texto exacto) y `context_checked_at`. El instante de lectura humana debe ser posterior o igual al del snapshot, no futuro y no superar cinco minutos. Cambiar el texto o el hilo obliga a una nueva revisión; el digest **no autentica** a la persona que rellenó el JSON.
- El recorrido de Listings ahora es iterativo (no recursivo), comprueba por cada `t1` el `id` único, `link_id=t3_<post>`, `parent_id` del contenedor, autor y cuerpo. Rechaza `more`, hijos ausentes, duplicados, profundidad mayor que 64 y más de 10 000 comentarios. Esta cota evita desbordamientos con JSONs sintéticos o dañados y no pretende cubrir todo hilo gigantesco.
- Las marcas temporales requieren zona horaria explícita y números finitos; se evita interpretar silenciosamente una hora ingenua usando la zona local de Windows/Ubuntu.
- `tests/test_reddit_snapshot_provenance.py` cubre revisión reutilizada en otro hilo/texto, lecturas caducadas, nodos injertados, duplicados, árbol anidado legítimo, `more`, profundidad adversarial y timestamps anómalos. `tests/test_reddit_snapshot_preflight.py` comprueba cita Markdown incluso con digest de revisión actualizado. La fixture y todos los casos son inventados.
- Migración: **no hay migración de datos reales**. Los consumidores offline que construyan un `review` deben añadir las tres claves; omitirlas bloquea la decisión de forma explícita. No reutilizar automáticamente fichas anteriores como aprobaciones.
- Rollback: revertir los commits de módulo/tests/fixture de esta revisión; no existe escritura en bases de datos, usuarios ni navegador.

**Reutilización pública (comparación ampliada):** se contrastó también [RedditWarp, MIT](https://github.com/Pyprohly/redditwarp/blob/c117c4e677a397c3779c1b9d7017926587110fda/LICENSE), commit [`c117c4e` del 01-07-2024](https://github.com/Pyprohly/redditwarp/commit/c117c4e677a397c3779c1b9d7017926587110fda), sin commits posteriores en la rama principal según GitHub al 09-10-2026. Ofrece wrappers tipados Python >=3.8, compatibles de forma declarada con Python 3.11/Windows. Frente a PRAW/Async PRAW, mantenidos con `v8.0.3` de agosto de 2026, no justifica incorporar una tercera capa de autenticación/red a un verificador de snapshots inerte. Se reutilizó el **contrato público** de Listings `t3/t1/more` de la [documentación de Reddit](https://www.reddit.com/dev/api/), no código externo ni una dependencia nueva.

**Aplicación transversal:** conservar el patrón `identidad del objetivo + fingerprint del borrador + evidencia humana posterior al snapshot` como contrato de adaptador para las colas WEB/API/MOBILE cuando se construya una capa común de revisión. No extraerlo aquí a `scan_common` porque las PR [#22](https://github.com/davidpd89/ci-sandbox-tmp/pull/22) (redacción/contexto), [#25](https://github.com/davidpd89/ci-sandbox-tmp/pull/25) (historial) y [#8](https://github.com/davidpd89/ci-sandbox-tmp/pull/8) (antigüedad) ya tienen jurisdicciones relacionadas. No confundir el fingerprint de aprobación con la confirmación idempotente del envío.

**Límite residual y segunda pasada:** JSON de snapshot/revisión no firmado; no se acredita ni la procedencia de la API ni la autenticación del revisor, y existe carrera entre la última lectura y el clic. El ejecutor privado fusionado debe adquirir el snapshot bajo lock y registrar/reconciliar cualquier intento ambiguo. Por ello, `allowed=True` sigue significando exclusivamente *apto para revisión manual*. No publicar, reintentar ni votar automáticamente a partir de esta salida.

La PR del espejo sigue sin ser integración en producción. El fallo observado en un SHA intermedio del gate era **del esquema de evidencias de esta hija**, no un déficit del índice padre: se corrigieron los encabezados/campos exigidos por `check_child_deliverables`. Las comprobaciones Ubuntu/Windows del último HEAD son la evidencia autoritativa. El CLI también devuelve código 2 y JSON estable para entrada ausente, malformada o no UTF-8 sin exponer su ruta ni traceback.
