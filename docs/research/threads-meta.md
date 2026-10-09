# Threads API: paginacion de replies y publicacion ambigua

Consulta: **2026-10-09** (Europe/Madrid). Alcance exclusivo: mirror
`davidpd89/ci-sandbox-tmp`, PR **#14**, rama `research/04-threads-meta`
sobre `research/public-reuse-parent`. No se interactuo con cuentas ni se usaron credenciales.

## Problema y reproduccion

1. Baseline `tools/threads_api.py::followups`: solo `me/threads` con
   `limit=25` y una pagina de `/{id}/replies`. En la API Graph las
   respuestas son paginadas: una pregunta en pagina 2 no se ve. Ademas se
   buscaban replies propias en la lista de Threads, no en el endpoint oficial
   `me/replies`: podia reaparecer una pregunta ya contestada.
2. Baseline `tools/threads_api.py::publish_reply` + `threads_execute.run_plan`:
   tras solicitar `/threads_publish`, un HTTP 200 sin `id`, timeout o
   respuesta malformada terminaba como `fallo`/KeyError. No prueba que no
   se publicara: reintentar podria duplicar contenido.
3. Como fuente de estructura (no una API falsa): Postman oficial de Meta documenta
   `data`, `paging.cursors.after`, `paging.next`, `me/replies`,
   `/{thread_id}/replies`, `replied_to`, contenedor y `threads_publish`.
   No se realizaron peticiones live por no disponer de autorizacion explicita
   para acciones reales; los tests inyectan respuestas con esa estructura.

## Ruta end-to-end real y alcance

- **Mirror publico (estado inspeccionado 09-10-2026)**:
  `tools/threads_scan.py` -> pool `tools/threads_pool.py` ->
  `tools/threads_build_plan.py` / `tools/threads_reply_queue.py` ->
  `tools/threads_execute.py::_preflight_plan/run_plan` ->
  API `tools/threads_api.py` (`meta_common.graph_get/post`) o navegador
  `tools/threads_interact.py` -> callbacks de resultados,
  `_append_registro`, metricas y estado del sistema.
- Via directa de conversacion propia: `threads_api.py followups` ->
  `threads_api_followups.json` -> decision humana `build` -> plan con
  `reply_to_id` -> `threads_execute.py`. La API se reserva para
  IDs propios reconocidos; permalink de publicaciones ajenas no equivale
  a un ID reconocido. No se amplia el acceso del navegador ni se sortea
  `threads_keyword_search`.
- **Repositorio oficial privado (rama operativa
  `integracion/crecimiento-2026-10`, inspeccion 09-10-2026)**:
  `tools/threads_api.py` (blob
  `0a86f1e6943d486b45722cd09d0b40248c986861`) y
  `tools/threads_execute.py` (blob
  `b55dc1a048fffef135cca550605f0e7d2f315d01`) **si existen**.
  El publicador oficial ya utiliza `reply_provenance` (firma, ID,
  permalink y texto comprobados contra GET del destino),
  `conversation_turn_policy` y reservas atomicas de
  `action_ledger`, con estado `UNCERTAIN` para ACK ambiguo.
  La copia publica **no** contiene esas guardias de forma equivalente:
  **nunca sustituir** el publicador privado por `publish_reply` del mirror.
  Portar solo paginacion y contrato de lectura a ese archivo privado,
  preservando la firma y el ledger. El comentario anterior sobre ausencia
  de `threads_api.py` correspondia a main, no a la rama operativa.
- Integridad: `pendiente_verificacion` queda disponible para ledger,
  sin afirmar `confirmado`. Un fallo 401/403 o paginacion truncada
  interrumpe la lectura sin generar una bandeja parcial que se interprete
  como completa.

## Comparativa y eleccion

| Solucion | Estado/coste de adopcion | Licencia | Riesgo | Decision |
| --- | --- | --- | --- | --- |
| Baseline `meta_common` + `threads_api.py` | HTTP estandar sin instalacion extra; falta cursor y ambiguedad | codigo propio | omisiones y duplicados | corregir |
| PyThreads `marclove/pythreads` | SDK asincrono, pre-release; dependencias `aiohttp`, `python-dotenv`, `requests`, `requests-oauthlib` | MIT (SPDX) | interfaz pre-1.0, migracion async, ultima version publicada PyPI 0.2.1 en 2024 | no adoptar |
| Inoue AI Threads SDK | async `aiohttp` + Pydantic 2; version 0.1.0, ultimo commit inspeccionado 2026-04-26 | MIT (SPDX) | reescribir cliente sin ventaja sobre estos dos errores | no adoptar |
| MetaThreads SDK | async `httpx` + Pydantic 2; exige Python >=3.12 y declara pytest como dependencia de runtime; CI usa 3.11 | MIT (SPDX) | incompatibilidad version y superficie extra | no adoptar |
| **Adaptar el patron del cursor oficial** | dos cambios acotados en Threads y un test contractual offline, sin dependencia nueva | autoria interna | maximo de paginas configurable, cobertura acotada | **elegida: C** |

No se copio codigo de terceros: se implementaron cursores propios usando
solo la forma documentada de Meta. No hay obligaciones nuevas de copyright
de terceros, ni dependencias transitivas ni CVE de dependencias añadidas.
No se verificaron exhaustivamente advisories historicos de cada SDK,
pues ninguno se incorpora. Comparativa de coste: **0 paquetes nuevos**,
**0 llamadas nuevas para respuestas de una sola pagina** excepto la consulta
necesaria `me/replies`; en historiales paginados, una solicitud adicional
por pagina. No se inventa un benchmark de latencia.

### Referencias verificadas (09-10-2026)

- Meta, workspace oficial: https://www.postman.com/meta/threads/overview
- Meta, coleccion oficial y advertencia de changelog incompleto:
  https://www.postman.com/meta/threads/collection/dht3nzz/threads-api
- Meta, docs oficiales de replies/cursores/publicacion:
  https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api
- Meta, changelog prioritario si contradice el Postman:
  https://developers.facebook.com/docs/threads/changelog
- Meta, scopes requeridos; entre ellos `threads_basic`, `threads_content_publish`,
  `threads_read_replies`, `threads_manage_replies`,
  `threads_manage_insights`; tokens de larga duracion renovables
  **antes de expirar**. No suponer permisos concedidos por documentacion.
- PyThreads, commit revisado `a75fb277377ce73d92cca7eb464c78090150bfd3`:
  https://github.com/marclove/pythreads/tree/a75fb277377ce73d92cca7eb464c78090150bfd3
  ; licencia y dependencias en `pyproject.toml`, package MIT.
- Inoue AI, commit `e2b050d9313771be547328ba260dbf5738f546d1`:
  https://github.com/Inoue-AI/Inoue-AI-Threads-SDK/tree/e2b050d9313771be547328ba260dbf5738f546d1
  ; `LICENSE` MIT y `pyproject.toml`.
- MetaThreads, commit `1444ac58c7559a877bbcb566bf58ff2b77aa2f16`:
  https://github.com/MetaThreads/meta-threads-sdk/tree/1444ac58c7559a877bbcb566bf58ff2b77aa2f16
  ; `LICENSE` MIT y `pyproject.toml`.
- OWASP, componentes y procedencia:
  https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html
- GitHub, branch protection y checks:
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches

## Decision aplicada y reversibilidad

- `tools/threads_api.py::paginated`: solo reusa el endpoint original y
  `after` obtenido en `paging.cursors`; nunca abre `paging.next` como URL
  (evita SSRF/fuga del token a hosts suministrados por una respuesta).
  Deduplicacion por `id`; continuacion tambien cuando solo hay
  `paging.cursors.after` en una pagina llena, aun sin `paging.next`
  (formato ilustrado en Postman oficial). Rechazo de pagina llena sin
  cursor util, cursor malformado/repetido y limite de cinco paginas
  con error explicito. El error
  **interrumpe todo el barrido**, no entrega resultados parciales.
- `followups`: lee threads propios, `me/replies` y conversaciones
  paginadas por `/{id}/conversation`, documentado por Meta para el contexto
  completo. Reconstruye la cadena de padres `replied_to.id` hasta la raiz;
  solo selecciona preguntas directamente dirigidas a posts o respuestas
  nuestras (no debates entre terceros), descarta las ya contestadas y
  conserva `thread_turns`, `target_created_at` y URL en la decision.
  Sin padre, historial o texto verificable, error explicito en vez de
  inventar contexto. No realiza POST.
- El publicador del mirror desactiva `auto_publish_text` durante la
  creacion de contenedor (para mantener el modelo de dos POST), valida
  `id` no vacio de tipo `str` y distingue `ReplyNotCreated`
  previo a publicacion de `ReplyPublishUncertain` despues de un intento.
  No copiar esta version sobre la rama privada, que usa ledger/firma.
  `threads_execute.run_plan` guarda resultado `pendiente_verificacion`.
  **No reintentar manualmente ni reprogramar un pendiente sin comprobar
  primero `me/replies` contra parent ID/texto**. Los mecanismos
  persistentes/idempotencia entre procesos pertenecen a #26.
- Rollback sin migracion de esquema: revertir los commits de esta PR
  de `tools/threads_api.py` y `tools/threads_execute.py`.
  No se modifican registros operativos, tokens o archivos de cuentas.
- Sin webhook nuevo ni media/insights: requieren scope y validacion
  especificos; para este bug no mejoran el baseline. Se han verificado
  rutas documentadas, no disponibilidad real en una app.
- API oficial prioritaria. Fallback navegador solo cuando los IDs de
  Threads no estan legitimamente disponibles: nunca convertir 401/403
  en permiso para esquivar restricciones o duplicar respuestas.

## Evidencia offline, limites y aceptacion

Test nuevo: `tests/test_threads_api_contract_2026.py`. Estructuras sinteticas
con `data` y `paging` como las respuestas de Meta; no se prueba con tokens
reales ni se simula un exito de autenticacion inexistente.

| Criterio | Evidencia | Estado previo al cierre |
| --- | --- | --- |
| Tokens vencidos y permisos denegados | test `test_denied_permissions_and_expired_token_never_return_empty_inbox`, `test_refresh_expired_token_does_not_overwrite_on_401` | ejecutar CI |
| Paginacion y cursores | tests `test_after_cursor_and_deduplication_no_next_url_fetch`, `test_repeated_cursor_and_page_budget_fail_closed`, `test_missing_data_and_missing_cursor_fail_closed` | ejecutar CI |
| Reconciliacion de replies | `test_reconciles_own_replies_and_paginated_inbound_questions` | ejecutar CI |
| Publicacion sin confirmacion | `test_accepted_without_id_is_uncertain_not_confirmed`, `test_timeout_after_publish_sent_is_uncertain`, `test_executor_marks_ambiguous_reply_for_reconciliation` | ejecutar CI |
| Fallo antes de crear post | `test_failed_creation_never_attempts_publish` | ejecutar CI |
| Windows/Linux, suite global | `.github/workflows/validate-social-tools.yml` (push, Python 3.11, compileall + pytest, Ubuntu/Windows) | consultar run del ultimo SHA |
| Media, insights, webhooks, cuotas y paginacion ilimitada | fuera del cambio vertical; docs oficiales + permisos | pendiente comprobacion con app real |
| Prueba real de Meta | prohibida sin autorizacion operativa expresa | pendiente externo |

Comandos definidos por workflow: `python -m pip install --disable-pip-version-check -r requirements-ci.txt`,
`python -m compileall -q tools tests`, `python -m pytest tests -q -p no:cacheprovider`
con las ocho excepciones expresas del workflow. Prueba focal:
`python -m pytest tests/test_threads_api_contract_2026.py tests/test_threads_api.py tests/test_threads_execute_api.py -q`.
Se deben consultar los logs de Actions para afirmar verde; el mero
`mergeable=true` no valida integracion.

### Autorrevision adversarial

1. **Pagina fraudulenta o circular**: `paging.next` podria apuntar a
   dominio ajeno o repetir cursor. Defensa: nunca abrir URL, solo cursor
   en endpoint fijo, detectar bucles. Contract tests sintéticos.
2. **Post aceptado, respuesta HTTP perdida**: el ledger podria decir
   fallo y reenviar la misma respuesta. Defensa: `ReplyPublishUncertain`
   y `pendiente_verificacion`; riesgo residual en nuevos procesos si
   el operador reintenta sin reconciliar (coordinacion #26).
3. **Token revocado o volumen mayor al cupo**: una bandeja parcial se
   tomaria por completa. Defensa: error 401/403 propagado; limite de
   paginacion falla cerrado, con instrucciones para ampliar solo tras
   medir cuotas/volumen real.
4. **Drift / retrocompatibilidad**: `me/replies` requiere permisos
   y entrega `replied_to` segun contrato vigente. Fallara cerrado
   sin `threads_read_replies`. Coordinar con #41 y validar con app
   de prueba autorizada antes del merge productivo.

### Colisiones y orden de integracion

Al consultar #15, #16, #20, #26 y #41 el 09-10-2026, las cinco PR
estaban abiertas y sus diffs solo contenian el fichero de encargo
(`docs/open-source-scouting/tasks/...`), sin cambios en los
adaptadores Meta o ledger. Potencial futuro:

- #15 Facebook y #16 Instagram: comparten `meta_common.py` y
  preocupaciones de permisos/errores, pero **no** se cambia ese modulo.
- #20 publicacion/programacion: coordinar semantica del estado
  `pendiente_verificacion` antes de consumirlo.
- #26 colas/idempotencia: ownership de reconciliacion persistente y
  reintentos; no clonar ahi esta implementacion de Threads.
- #41 drift/contratos: reusable el patron de respuestas JSON, sin
  crear utility comun ahora. Si #41 adopta una, integrar tras revisar diff.

Orden sugerido: fusionar el fix local de #14 **solo despues de**
verificar CI y compatibilidad con repo oficial, luego coordinar la
semantica compartida con #20/#26 y tests de drift de #41.

## BLOQUEOS PARA CLAUDE / integracion

1. Mirror **publico y efimero**, README advierte que se regenera desde
   repo **privado** y sobrescribe cambios; no adoptar directamente
   como fuente de produccion. Comparar SHA de `main` del repo privado
   y ramas activas, y trasladar solo cambio saneado, con permiso del
   responsable, manteniendo datos personales fuera del mirror.
2. No hay token real, scopes concedidos, entorno Windows local ni
   ejecucion end-to-end autorizada. Nunca publicar para comprobar.
3. Antes de merge: confirmar checks de ultimo `head_sha`, revisar
   diferencias con version operativa privada de `threads_api.py`
   (no presente en main inspeccionada) y hacer pruebas de contratos
   en entorno autorizado (solo GET /me/replies), incluyendo cambios
   de Meta documentados mas recientemente en el changelog.
4. Confirmar que la cola no trata `pendiente_verificacion` como
   fracaso reintentable, tanto en ronda como tras reinicio; eso no se
   soluciona con un mock de una llamada aislada. Si existe auto-retry
   en produccion, **bloquear merge** hasta guardia durable.
5. El formato de error `meta_common.graph_get/post` no expone
   un tipo especifico para 429/5xx/timeout. La politica transversal
   de retries y backoff queda para #26/#41, sin introducir reintentos
   automaticos de POST aqui.

**Veredicto tecnico recomendado: BLOQUEADA para merge productivo**
hasta portar al repo privado vigente, revisar resultados de CI y
cerrar el riesgo de reintento persistente. Las correcciones del mirror
quedan en su propia PR para revision independiente, nunca merge automatico.

## Segunda revision independiente: evidencias y puntos de integracion (09-10-2026)

- Los ejemplos **oficiales de Meta** para listados y replies contienen
  `paging.cursors.after` sin `paging.next`:
  https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api .
  Se añade fallback solo para **pagina llena con cursor**, manteniendo
  finalizacion en pagina corta y error si la pagina llena carece de cursor.
  Es una heuristica documentada, no garantia de completitud de un servidor
  que omita cursores: requiere canario de solo lectura antes de portar.
- Contratos extra offline: cursor sin `next`, pagina llena sin cursor,
  estructura de cursor corrupta, `auto_publish_text=false`, timeout
  durante creacion de contenedor e ID no textual en ACK.
  No se instalan SDKs; permanece la comparacion MIT/Python 3.11 anterior.
- Hallazgo de prioridad **alta** en el privado:
  `threads_api.py` tiene una verificacion de procedencia y ledger de
  acciones de las que carece el espejo. La implementacion de `#14` **no
  es un cherry-pick directo**: aplicar manualmente la lectura y tests
  sobre la version operativa, sin borrar las protecciones existentes.
- No crear un ledger nuevo desde esta PR: la rama privada ya incorpora
  `action_ledger` comun y `WriteOutcomeUnknown` en ejecutores.
  `#26` debe confirmar semantica transversal sin duplicar ese contrato.
- La CI de contrato de campaña fallo en ambos SO para el HEAD anterior:
  parent con 76 hijas frente a 46 esperadas y un indice atrasado; el padre
  se actualizo despues. El test offline RRSS del mismo SHA paso en Ubuntu y Windows. Estos estados
  anteriores no se trasladan como afirmaciones sobre futuros HEAD.
- El caso de pregunta anidada se cubre ahora offline con
  `/{id}/conversation`: se comprueban la cadena de padres, los turnos
  nuestros/ajenos, la fecha del destino, los debates entre terceros y
  la ausencia de `replied_to`. **Pendiente para Claude**: validar el
  contrato de este endpoint con GET supervisado y volumen/costos reales.
- Retirada: revertir los cambios de paginacion y casos nuevos;
  `auto_publish_text=false` es exclusivamente defensa en el mirror.
  No ejecutar rollback sobre el codigo privado protegido.

## Alternativas

Se compararon tres bibliotecas MIT en Python (PyThreads, Inoue AI Threads
SDK y MetaThreads), ademas de la muestra oficial de Meta. La ruta elegida es
mantener `meta_common` y adaptar el contrato paginado sin dependencias.
Ningun SDK sustituye el ledger y los certificados propios de la rama
operativa. Windows/Python 3.11: la muestra Meta requiere Node; MetaThreads
requiere Python 3.12 o superior; las otras dos requieren convertir a async.

## Licencias y procedencia

Fuente primaria: https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api
Fecha de consulta: 2026-10-09
Licencia SPDX: NOASSERTION
Referencia inmutable: N/A (sin codigo incorporado)

El metadato `NOASSERTION` indica que esta PR no incorpora codigo de
terceros; **no** se atribuye esa licencia a la documentacion de Meta.
Las tres bibliotecas evaluadas declaran MIT (commits y restricciones de
version detallados abajo). Tambien se inspecciono la muestra oficial
https://github.com/fbsamples/threads_api/tree/854fc140a37e20f6a7086cf3ee0065f99d41f646 :
su `package.json` declara ISC, pero el archivo `LICENSE` tiene texto
especifico de Meta. Es una aplicacion Node/Express de demostracion,
con dependencias ajenas al runtime Python 3.11 y sin tests funcionales
(`npm test` es placeholder). No se ha copiado codigo de esta muestra.

## Decisión

Mantener cliente HTTP existente. Reutilizar el formato oficial de cursores,
continuar en paginas llenas que solo traen `paging.cursors.after`, y validar
la separacion entre creacion de contenedor y publicacion. Portar solo este
contrato al cliente privado vigente, preservando `reply_provenance` y
`action_ledger`, sin nueva capa comun prematura.

## Pruebas

`python -m pytest tests/test_threads_api_contract_2026.py
tests/test_threads_api.py tests/test_threads_execute_api.py -q` (offline);
suite completa por Actions Ubuntu/Windows. Los resultados corresponden a
cada HEAD, no a la existencia de un workflow. El gate de campaña comprueba
tambien entregables con origen SPDX y privacidad.

## Retirada

Revertir commits específicos de la PR en el mirror; para produccion,
retirar unicamente la rutina de paginacion portada si falla el canario
GET supervisado. Nunca revertir certificados ni ledger privados.

## Nueva revisión adversarial: lectura de conversaciones en conjunto

Consulta externa (09-10-2026):
- Meta, request de conversaciones: 
  https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api
  (Read and Manage Threads Replies > GET Get Threads Conversations).
  `/{id}/replies` lista respuestas de nivel superior y
  `/{id}/conversation` devuelve el contexto conversacional. El esquema
  publicado incluye `replied_to.id`, `root_post.id`,
  `is_reply_owned_by_me` y cursores.
- Meta, GET replies propias:
  https://www.postman.com/meta/threads/request/34203612-b02f08fa-a8c3-4b9c-9848-e83e95a1e237 .
- Meta, creacion de texto:
  https://www.postman.com/meta/threads/request/jkuogpa/1-1-create-text-container ,
  `auto_publish_text` optativo; el caso de dos POST requiere evitar
  la autopublicacion durante el primero.
- Muestra oficial https://github.com/fbsamples/threads_api/tree/854fc140a37e20f6a7086cf3ee0065f99d41f646 .
  Se contrasta la semantica, no se incorpora ni distribuye su codigo.

### Nuevos riesgos resueltos

1. **Replies de segundo nivel perdidas**: antes se consultaba
   `/{id}/replies` y una pregunta posterior a nuestra respuesta
   permanecia invisible. Ahora se consulta la conversacion completa
   y se reconstruye una cadena de padres verificable.
2. **Responder a lectores que hablaban entre ellos**: no basta
   detectar pregunta dentro de una conversacion. Se exige que el
   padre inmediato sea nuestro; una replica a un tercero se excluye.
3. **Texto sin historial**: si un nodo necesario no aparece en el
   resultado de Meta, se considera lectura incompleta y no se crea
   un falso certificado contextual.
4. **Plan sin fecha de destino**: `build_plan` pasa el timestamp de la
   pregunta como `target_created_at` para la politica comun
   `post_age_policy`, mantiene `thread_turns` para
   `conversation_turn_policy` y `url` para la cadena de procedencia
   verificada en la rama privada. No reutilizar la implementacion del
   publicador del espejo para el privado.

### Tests offline añadidos en esta revisión

- `test_nested_question_to_our_reply_preserves_verified_ancestry`
- `test_unverifiable_nested_parent_is_not_treated_as_available`
- `test_own_reply_without_parent_does_not_mask_duplicate_risk`
- `test_missing_parent_on_inbound_question_fails_closed`

### Impacto transversal

El adaptador Threads puede emitir `thread_turns` en el mismo contrato
que Bluesky/Mastodon, con un role `ours/theirs` y `post_id` enlazado.
No crear una politica de conversacion nueva: reutilizar la existente,
y coordinar tests/capacidades con #77. El limite de paginas de la rutina
`paginated` sigue siendo un presupuesto intencionado; una paginacion
truncada debe informar y no convertirse en una falsa cola vacia. La
comprobacion live del volumen y del ordenamiento real sigue pendiente.
