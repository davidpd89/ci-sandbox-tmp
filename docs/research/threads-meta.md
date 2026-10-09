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
- **Repositorio oficial privado (inspeccionado main)**:
  `tools/threads_scan.py`, `tools/threads_execute.py`,
  `tools/threads_interact.py`, `tests/test_threads_post_confirmation.py`,
  `SISTEMA_DIARIO_THREADS/PROCESO.md`.
  El listado del directorio `tools/` de main **no incluye**
  `threads_api.py` ni `threads_build_plan.py`: el mirror no es una copia
  equivalente del main oficial. Hay que comparar con ramas operativas
  reales antes de sincronizar/portar; no atribuir ausencia de funciones
  al proyecto sin esa comparacion.
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
  Deduplicacion por `id`; rechazo de respuestas/cursor malformados,
  repetidos y limite de cinco paginas con error explicito. El error
  **interrumpe todo el barrido**, no entrega resultados parciales.
- `followups`: lee threads propios, `me/replies` y las paginas de
  respuestas recibidas; cruza `replied_to.id`, excluye roots que son
  replies propias, deduplica y ordena. No intenta crear respuestas.
- `publish_reply` distingue `ReplyNotCreated` previo a publicacion
  de `ReplyPublishUncertain` despues de un intento.
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
