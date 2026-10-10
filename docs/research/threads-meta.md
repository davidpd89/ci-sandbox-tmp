# Threads: auditoría de reutilización y cierre de PR #14
Fecha de revisión: 2026-10-10 (Europe/Madrid).
PR de origen: https://github.com/davidpd89/ci-sandbox-tmp/pull/14
Base sincronizada inspeccionada: `250ccb019fb8683311df48c7d02d6c6d2b73a47b`.
Rama operativa privada inspeccionada: `integracion/crecimiento-2026-10`, HEAD
`1bbba096c1258ff85da191a88f7ad1e79c322c63`.

## Problema

La variante de Threads diseñada originalmente en la PR #14 partía de un
espejo anterior a la sincronización de Claude del 10/10. Sus ficheros
`tools/threads_api.py` y `tools/threads_execute.py` reemplazaban
sin querer el publicador privado, que ya contiene certificado contextual
`reply_provenance`, GET de comprobación del destinatario,
`conversation_turn_policy`, `action_ledger` y estado `UNCERTAIN`
para ACK ambiguo. Sus checks verdes no demostraban equivalencia con la
base nueva. **No se reutiliza el diff original de esos ejecutores.**

Los tres comentarios inline recibidos señalaron problemas reales:
(a) registro incierto en pool sin clave del destino API ni prueba tras
reinicio; (b) métrica desconocida que congelaba «Última sesión»; y
(c) helper de dispatcher que el CLI no ejecutaba. La revisión del
10/10 exigió corregirlos sin copiar el código anterior sobre producción.

## Alternativas

1. Fusionar los 5 ficheros originales: descartado, porque reemplazaba
   controles existentes en la base sincronizada.
2. Introducir un SDK completo: descartado. La implementación oficial
   `fbsamples/threads_api` es una muestra Node/Express; PyThreads es
   asíncrono; `meta-threads-sdk` no aporta la persistencia existente.
   `ThreadsPipe-py` proporciona ideas sobre `top_levels`/`reverse`,
   pero su contrato no sustituye nuestro barrido paginado y reconciliado.
3. Mantener la base protegida y extraer cambios pequeños: elegida.
   Se prepararon #172 (lectura, cursor, contexto), #179 (identidad de
   reply API) y #186 (métricas no destructivas), sin borrar protecciones.
   Las tres PR fueron cerradas SIN merge en el mirror; sus comentarios
   indican integración por separado en el repositorio privado:
   #172 commit `26376b6f`; #179 y #186 commit `a2ad6a78`.
   No deben volver a introducirse aquí como código duplicado.
   #177 trata el destino verificable de respuestas WEB.

## Licencias y procedencia

Fuente primaria: https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api
Fecha de consulta: 2026-10-10
Licencia SPDX: NOASSERTION
Referencia inmutable: N/A (sin codigo incorporado)

Se han contrastado fuentes oficiales de Meta y repositorios públicos, sin
copiar código de terceros. Muestra oficial comprobada:
https://github.com/fbsamples/threads_api/tree/854fc140a37e20f6a7086cf3ee0065f99d41f646
(su `LICENSE` tiene condiciones específicas de Meta; `package.json`
declara ISC). También se consultaron
https://github.com/paulosabayomi/ThreadsPipe-py ,
https://github.com/marclove/pythreads y
https://github.com/MetaThreads/meta-threads-sdk .
Las referencias anteriores son comparables, no dependencias nuevas.

## Decisión

Actualizar #14 mediante merge **sin asumir los ficheros ejecutables de
la rama vieja**: resolver a favor de la base sincronizada el código
`tools/` y los tests de la implementación antigua. Mantener únicamente
el documento de investigación, el encargo y un contrato offline que
proteja las invariantes existentes del publicador y la edad del destino.
Esta PR queda como **cierre documental auditable**, no como port de
producto. Revertir esta PR no revierte #172/#179/#186 en privado.

Respuesta a los hilos:
- Idempotencia: válida la crítica. El pool WEB no puede sustituir al
  `ActionLedger` API. La rama privada usa clave `reply_to_id` y
  `UNCERTAIN`; test de dos procesos/ACK ambiguo en la suite privada,
  sin segundo POST, queda para el integrador. No se introduce un ledger
  paralelo ni un parche al publicador del espejo.
- Métricas: válida. El helper anterior congelaba «Última sesión».
  La corrección transversal está en #186, informada como integrada en
  privado; ningún parche antiguo a `threads_execute.py` entra aquí.
- CLI: válida. El helper no era ruta operativa. Se descarta íntegro
  `_run_by_transport` del diff anterior; corresponde probar API-only
  y WEB mixto sobre el ejecutor protegido real, no en esta variante.
- La propuesta de Perplexity de `graph_paginate` compartido se
  considera diseño para #41 y adaptadores #15/#16; no hay evidencia
  de que copiar ahora otro paginador supere el port ya integrado.
  La recomendación de `--max-conversations`, cursor durable,
  ordenación `reverse` y presupuesto global se registra como
  trabajo potencial transversal, sin truncado silencioso.
- #204 relaciona las PR familiares. No abrir una cuarta PR por el
  mismo hueco que ya tiene responsable.

## Pruebas

`python -m pytest tests/test_threads_pr14_protected_contract_2026.py -q`
`python -m pytest tests -q -p no:cacheprovider`
`python -m compileall -q tools tests`

Los tests nuevos son sintéticos y no hacen solicitudes HTTP. Comprueban
que el publicador protegido exige procedencia antes de cualquier POST y
que la fecha del destino continúa protegida por la política común.
La integración privada de #172/#179/#186 y la ausencia de segundo POST
tras reinicio no se afirman por estas pruebas: exigen la suite operativa
y canario GET supervisado, sin escribir en redes.

## Retirada

Revertir el commit de cierre de #14 elimina únicamente documento/encargo
y test offline. No altera `tools/` de la base ni revierte los ports ya
integrados en privado. No fusionar el historial anterior como
cherry-picks ni sustituir el publicador protegido.

## Comprobaciones pendientes de Claude

1. En el privado actual, confirmar `publish_reply(..., proof_action=...)`,
   comprobación GET ID/permalink/texto y
   `ActionLedger.reserve/settle(UNCERTAIN)` sin cambiar POST→ACK→TTL.
2. Simulación **entre procesos**: `build -> preflight -> ACK ambiguo ->
   reinicio -> replan` y cero segundo POST; revisar semántica TTL y
   reconciliación GET antes de reactivar una acción incierta.
3. Canarios supervisados de **solo lectura** de `me/replies`,
   `/{id}/conversation`, `replied_to`, cursores con/sin `next`,
   `followers_count`, destinos viejos y replies anidadas.
4. Edge real en Windows para lotes exclusivamente API y lotes mixtos,
   sin publicación ni comentarios reales, más suite privada Windows y
   Linux. Confirmar compatibilidad con #177 y con política de edad.
5. Comprobar SHA exacto y checks de este nuevo HEAD; sin merge
   automático. El estado de la base puede cambiar de nuevo.
