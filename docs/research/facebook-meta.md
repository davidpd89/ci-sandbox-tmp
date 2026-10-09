# Facebook Graph API: paginación y confirmación de respuestas (PR #15)

**Consultado:** 2026-10-09. **Decisión:** C — adaptar el patrón de cursor de Graph API con stdlib, sin añadir dependencia y sin copiar código ajeno. **Alcance:** únicamente lectura de comentarios de publicaciones de una Página autorizada; no cambia la escritura de posts, likes, DMs ni el navegador.

## Problema y reproducción

En el mirror, `tools/facebook_api.py::comments_pending` leía solo los primeros 50 comentarios de cada post reciente y solo la primera página de respuestas a cada comentario. Una respuesta de la Página en una página posterior ocasionaba un **falso positivo** de «pendiente»; una pregunta en una segunda página de comentarios ocasionaba un **falso negativo**. El filtro antiguo tampoco excluía el comentario propio de nivel superior por ID de la Página.

**Antes → después, MISMO fixture sintético:** en el primer lote aparecen `c-answered` (falso pendiente) y una segunda página con `c-pending` (omitido). Tras el cambio la salida es exclusivamente `c-pending`. No se infiere ninguna mejora porcentual en producción ni benchmark de tiempo. Fuente y comprobación: `tests/fixtures/facebook_graph_contracts.json` y `tests/test_facebook_graph_contract.py`.

Ruta de lectura efectiva: `tools/meta_inbox.py::collect` → `_facebook` → `facebook_api.comments_pending` → `meta_common.graph_get` → HTTP Graph → transformación y selección de preguntas → reporte `pending/error` → salida humana/JSON. **No produce acciones ni ledger:** es una bandeja de lectura; `meta_inbox.collect` captura fallos por red y devuelve `pending=[]` + aviso en vez de presentar una lectura incompleta. Si posteriormente se redacta o responde, `facebook_api.reply_comment` hace un POST separado: un timeout tras enviar NO constituye confirmación, no hay retry automático aquí. Esta PR no automatiza esa transición ni permite que la bandeja active publicación por sí sola.

Rutas distintas que no deben confundirse:
- `tools/facebook_scan.py` → `facebook_pool.py` / `facebook_build_plan.py` → `facebook_execute.py` → `facebook_interact.py` (navegador, lectura/validación/acción, registro y métricas `SISTEMA_DIARIO_FACEBOOK/`). No modificado.
- `tools/meta_publish.py` → `content_publisher.py` para publicar material aprobado por API. No modificado.
- `tools/meta_insights.py`: métricas de contenido propio; no se altera.
- `tools/meta_common.py`: transporte compartido Threads/Instagram/Facebook, deja los errores Graph HTTP visibles al consumidor. No se altera para evitar colisiones.

El repositorio oficial privado `davidpd89/rrss-davidporto-CODE`, `main` consultado el 09-10-2026, contiene `tools/facebook_scan.py`, `tools/facebook_execute.py`, `tools/facebook_interact.py` y `SISTEMA_DIARIO_FACEBOOK/PROCESO.md`; el mirror incorpora además `facebook_api.py`, `meta_*.py`, sus tests y controles posteriores. No se ha copiado ningún dato de cuentas ni ficheros privados al mirror.

## Decisión e implementación

`_paged_rows` sigue exclusivamente el cursor `paging.cursors.after` cuando hay `paging.next`; **nunca abre la URL `paging.next`**, que puede contener un `access_token` u otros parámetros sensibles. Hace nuevas peticiones por `meta_common.graph_get` al mismo endpoint declarado. Si faltan `data`, `after` o su tipo válido, hay error Graph incrustado, cursor repetido, exceso de 10 páginas por arista o más de 100 lecturas Graph totales por exploración (1 de posts + 99), se aborta con excepción; nunca se entregan sugerencias parciales. Los elementos se deduplican por ID, los comentarios propios se excluyen por ID y solo las preguntas candidatas fuerzan la lectura de respuestas.

`posts_limit=10` conserva por diseño el alcance de los diez posts más recientes **de la primera página**; esta PR no promete analizar todo el historial. La lectura de likes con `comments_to_like` continúa limitada a su primera página; ampliarla requeriría control de idempotencia de las acciones y decisión separada. Las respuestas con envío ambiguo tampoco se reintentan automáticamente.

## Alternativas

| Baseline | Candidato 1 | Candidato 2 | Elección | Justificación y riesgo |
| --- | --- | --- | --- | --- |
| urllib/stdlib, 1 página | Meta Business SDK Python `26.0.2` | `mobolic/facebook-sdk` (Apache-2.0) | Patrón C, stdlib | SDK oficial es útil en integraciones amplias, pero añade dependencias/transporte global y licencia específica de plataforma para un único cursor; el alternativo es genérico y no hay evidencia de mantenimiento equivalente. La implementación acotada conserva mocks e interfaces existentes. |

**Fuentes contrastadas:**
- Meta Business SDK: [releases 26.0.2, 2026-09-21](https://github.com/facebook/facebook-python-business-sdk/releases/tag/26.0.2); implementación pública de `Cursor.load_next_page`: [archivo en tag 26.0.2](https://github.com/facebook/facebook-python-business-sdk/blob/26.0.2/facebook_business/api.py). Se observa en el SDK que `paging.next` indica continuidad y `paging.cursors.after` suministra el cursor. Se imita el contrato, **no se copia código**.
- Licencia oficial: [licencia específica de Facebook Platform](https://github.com/facebook/facebook-python-business-sdk/blob/26.0.2/LICENSE); no presumir MIT o Apache-2.0. Su uso está sujeto a términos de Facebook/Meta. [Guía del SDK](https://github.com/facebook/facebook-python-business-sdk/blob/26.0.2/README.md).
- Alternativa: [mobolic/facebook-sdk](https://github.com/mobolic/facebook-sdk), [código de cliente](https://github.com/mobolic/facebook-sdk/blob/master/facebook/__init__.py), [LICENSE Apache-2.0](https://github.com/mobolic/facebook-sdk/blob/master/LICENSE). La actividad y compatibilidad con Graph v26 para este flujo no quedaron verificadas con un tag moderno; no se introduce.
- Especificación primaria oficial: [Graph API](https://developers.facebook.com/docs/graph-api/), [paginación](https://developers.facebook.com/docs/graph-api/results/), [Pages API](https://developers.facebook.com/docs/pages-api/), [permisos](https://developers.facebook.com/docs/permissions/), [Webhooks](https://developers.facebook.com/docs/graph-api/webhooks/). El portal de Meta devolvió 429/bloqueo de acceso automático al consultarlo; NO se certifican las autorizaciones efectivas de la app ni se inventan cuotas. El SDK oficial y fixtures de la respuesta Graph sí se pudieron contrastar.
- [OWASP: Software Supply Chain Security](https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html); [GitHub: protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

## Licencias y procedencia

Se utiliza exclusivamente el código existente del proyecto y un patrón conocido de Graph API, sin copiar implementaciones de SDK ni incorporar componentes externos. Los SDK y sus licencias están identificados en la sección de alternativas.

## Permisos, privacidad, operaciones y deuda

Un token de Página no autoriza por sí solo todas las operaciones. Distinguir `pages_read_engagement`, `pages_read_user_content`, `pages_manage_engagement`, `pages_manage_posts`, `pages_messaging` y los productos de Messenger/Instagram y la revisión de aplicaciones según tipo de cuenta, acceso a activos, modo desarrollo/producción y aprobaciones reales. No se ha validado ninguna concesión activa con tokens reales; permisos, webhooks y DMs **no están activados por esta PR**. El modo desarrollo/rol administrador no justifica acceso general a terceros. La frase antigua «token de Página no caduca» no debe usarse como garantía operativa: los tokens pueden invalidarse o perder permisos por varias causas; falta preflight autenticado autorizado.

### Matriz de capacidad, identidad y acceso pendiente de validar

| Identidad y operación | Capacidad posible | Permiso/producto sujeto a validación | Decisión en #15 |
| --- | --- | --- | --- |
| Página administrada: publicaciones propias | Lectura de posts, comentarios, reacciones | `pages_read_engagement`, `pages_read_user_content` según tipo de contenido y endpoint; token de Página habilitado | Solo lectura paginada de comentarios |
| Página administrada: responder/reaccionar | POST autorizado en contenido de la Página | `pages_manage_engagement` y acceso suficiente al activo; errores 200/190/429 posibles | No alterar el POST ni automatizarlo |
| Página administrada: publicar fotos/feeds | Feed, álbum y media de la propia Página | `pages_manage_posts`, autorización editorial, formato endpoint | Fuera de alcance |
| Página: insights | Analítica de Página/publicaciones propias | Permisos de insights específicos (`read_insights` u otros según endpoint/producto), disponibilidad de métricas | Sin ampliar métricas |
| Página: mensajes privados | Inbox / Messenger | Producto Messenger, `pages_messaging`, acceso a Page y revisión según modo/uso | No habilitar ni recopilar DMs |
| Página: webhooks | Notificaciones de eventos suscritos | Suscripción a los campos disponibles, verificación de firma y configuración de app, posibles requisitos `pages_manage_metadata` | No habilitar webhook |
| Cuenta personal, grupo o publicación ajena | Operaciones con superficies distintas de una Página propia | No derivar permisos de un token de Página; dependen de producto, revisión y políticas de Meta | No intentar ni simular autorizaciones |
| Instagram/Threads | APIs y tipos de identidad separados | Permisos y tokens de Instagram Login/Threads API no intercambiables automáticamente con Página | Sin cambio |

Esta tabla identifica **permisos candidatos**, no concesiones verificadas: la documentación primaria de Meta no se pudo consultar de forma íntegra durante esta sesión y no se ejecutó una llamada `debug_token` con credenciales reales. Para cualquier ampliación es obligatorio contrastar endpoint, versión de Graph, modo de aplicación, rol de la cuenta, producto, autorización efectiva del token y App Review cuando corresponda. Los límites y cuotas numéricos **no se presumen**.

La API puede devolver error 190 por token inválido/caducado, error 200 por permisos, timeouts o límites de tasa. Los fixtures reproducen la envoltura `error` sin guardar valores reales. En fallos de lectura no debe fabricarse `pending=[]` como resultado válido sin aviso; `meta_inbox` informa `error`. Los campos `from`, `message` y texto de usuarios son datos personales: no crear corpus públicos ni registrar cuerpos en trazas. `paging.next` contiene posibles credenciales y no se imprime. Los fixtures de esta PR son sintéticos y no contienen identificadores de personas ni tokens operativos.

**Coste:** cero dependencias nuevas, cero escrituras nuevas, pero más lecturas cuando existan múltiples páginas; límite máximo de 100 GET por barrido (`1 + 99`, sin reintentos). La API puede facturar o limitar consumo según acceso/tipo de operación; no se garantiza gratuidad ni volumen permitido. Un presupuesto excedido produce aviso y no una lista parcial.

**Rollback:** revertir el commit funcional y los tests/docs correspondientes; no hay migraciones, estados persistidos ni cambios de permisos. La función pública `comments_pending(token, page_id, posts_limit=10)` conserva firma y esquema de salida. No tocar `main` ni la rama padre hasta revisión.

## Pruebas offline y puntos adversariales

`python -m compileall -q tools tests`; `python -m pytest tests/test_facebook_graph_contract.py tests/test_facebook_like_comments.py tests/test_meta_apis.py tests/test_meta_inbox.py -q -p no:cacheprovider`; y suite de CI `.github/workflows/validate-social-tools.yml` en Windows y Linux. **Solo marcar resultados ejecutados tras leer sus jobs; una ejecución en curso no es verde.**

1. Una respuesta de la Página está en página posterior: antes falso pendiente; ahora desaparece (fixture anidado).
2. Meta anuncia siguiente página sin cursor, repite cursor, añade error/JSON inválido o agota presupuesto: ahora excepción, el informe no confunde incompleto con vacío.
3. Token caducado/permisos denegados o timeout: error propagado a bandeja; el POST incierto se representa como timeout y se verifica que no se reintenta.
4. Revisión transversal: `meta_common`, Instagram/Threads, insight, publicación, browser, ledger y cola no se han editado; colisiones futuras se gestionan con PR #14, #16, #22 y #41.

## Retirada y coordinación de integración

- Mirror [#14](https://github.com/davidpd89/ci-sandbox-tmp/pull/14) Threads y [#16](https://github.com/davidpd89/ci-sandbox-tmp/pull/16) Instagram pueden tocar `meta_common`, `meta_inbox`, `meta_publish`: esta PR NO cambia esos ficheros.
- [#22](https://github.com/davidpd89/ci-sandbox-tmp/pull/22) respuestas/memoria puede consumir `pending`; el contrato sigue siendo lista completa o error, nunca respuestas automatizadas.
- [#41](https://github.com/davidpd89/ci-sandbox-tmp/pull/41) drift de API podría centralizar validación de `paging` si demuestra paridad en otras redes; mantener test Facebook durante la integración y no duplicar lógica por adelantado.
- Todas tenían únicamente diff de encargo al consultar el 09-10-2026; verificar sus HEADs de nuevo antes de integrar. Orden razonable: primero esta mejora aislada, después #41 para contratos generales, y #14/#16/#22 con rebase/revisión de imports y fixtures. **La numeración anterior es la del mirror**, no la del repo oficial.

## BLOQUEOS PARA CLAUDE — ejecución 2026-10-09

**Veredicto provisional: BLOQUEADA para merge, no por la corrección de Facebook sino por puerta de campaña sin sincronizar.** GitHub mantiene #15 abierta, base `research/public-reuse-parent` y head `research/05-facebook-meta`; nunca se ha mergeado ni retargeteado. La rama padre se actualizó concurrentemente mientras se auditaba: HEAD observado `c7b214ee5d250a585d8a9e1c58bcac1e57129aec`, mientras el `base_sha` que ofrecía la ficha de #15 todavía era `4da0584f270bdbec6cf37286cc86396a08e11bab`; comprobar el estado de ambos antes de integrar.

**Pruebas verificadas:** workflow [validar herramientas offline](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978492994), commit `cfc140cebf63f1d346fd384a980bd5f1269d44e6`, completado con éxito en Ubuntu/Windows (instalación, compileall, pytest del repositorio). Este no es el SHA final y deben verificarse los nuevos runs tras cada corrección. Los jobs de `Validar protocolo de campaña pública` de [run 37978388297](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/37978388297) en Ubuntu/Windows pasaron tests unitarios del validador pero fallaron la fase de índice y privacidad **antes de ejecutar privacidad del diff**: `campaign: 76 children; 3 errors; 0 warnings`; `expected 46 children, got 76`; `missing, extra or duplicate PR numbers`; `protocol index is incomplete or duplicated`. Se comprobó en padre `tools/validate_open_source_campaign.py` que `RANGE=set(range(11, 57))`, mientras el índice del protocolo ya incluye 76 entradas hasta #86. **Es un defecto del contrato del padre**; no alterar ese script, `children.json` ni las PR ajenas desde #15. No se oculta este check rojo ni se convierte `mergeable=true` en aprobación.

**Sin credenciales ni efectos reales:** no se usaron `.env`, tokens, páginas auténticas ni navegador. No se pudo ejecutar una prueba API autenticada ni certificar permisos reales, webhooks, inbox de mensajes, tarifas/cupos o renovación de token. El entorno de esta sesión no pudo clonar por red con `git`; se empleó el conector autorizado de GitHub y CI para el checkout y las pruebas. La suite corre con fixtures estrictamente ficticios, y el análisis privado se hizo mediante acceso autenticado sin copiar ficheros de datos de terceros.

**Pasos mínimos para Claude/revisor:** (1) consultar HEAD/base real y el diff entero de #15, #14/#16/#22/#41; (2) en PR padre #10, hacer que índice, manifiesto y validador de campaña concuerden respecto al número de hijas y fusionar ese arreglo de forma independiente; (3) ejecutar la puerta de privacidad en el **diff de #15**, que quedó sin ejecutar por el fallo previo, y comprobar que ninguno de los ejemplos sintéticos activa falsos positivos; (4) verificar runs offline de Ubuntu/Windows para el SHA último de #15 y revisar no regresión de `tests/test_facebook_graph_contract.py`, `test_facebook_like_comments.py`, `test_meta_apis.py`, `test_meta_inbox.py`; (5) validar en entorno autorizado de prueba Meta el acceso concreto a la Página y semántica de cursores y campos `from`/`comment_count`, sin crear acciones reales; (6) tras revisión de privacidad y permisos, decidir si el diseño debe migrarse al repositorio oficial privado sin filtrar datos del mismo.

**Autorrevisión 1 (corrección y seguridad):** lectura por páginas antiguas omite preguntas y puede inventar pendientes; corregido mediante cursor + fixture; la respuesta confirmada en página 2 impide un falso positivo. Error de permisos o cursor roto provoca lectura incompleta; corregido con excepción visible en bandeja. El token puede aparecer en `paging.next`; no se sigue ni se imprime esa URL. Se añadieron comprobaciones de autores desconocidos y presupuesto total de lecturas. **Autorrevisión 2 (arquitectura y riesgo transversal):** no duplicar un SDK completo para un único endpoint; no modificar `meta_common` compartido con Threads e Instagram; no integrar mecánicamente `like_comments` o POST de respuestas sin reconciliación e idempotencia. Las regresiones contractuales se usan como defensa; la verificación online sigue pendiente y no hay autorización de envío.

**Riesgo residual relevante:** límite de diez posts recientes, 10 páginas por arista y 100 lecturas máximas; cualquier exceso retorna error visible, no garantía de cobertura universal. `comment_count=0` se toma como ausencia de respuestas según semántica de Graph; una respuesta que Graph no exponga por permisos no es detectable. Si Meta cambia cursor/tipo de cuenta/campos, abortar y ajustar contrato, nunca asumir éxito de escritura.
