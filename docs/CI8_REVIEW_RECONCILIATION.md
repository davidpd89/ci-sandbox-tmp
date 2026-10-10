# CI #8 — conciliación de revisiones (10/10/2026)

## Decisión sobre el árbol

La versión histórica de la PR #8, HEAD `9a83ffcc46577da569c91104ec16c1d06d653269`, tenía **42 commits y 29 archivos** sobre la base obsoleta `ci/test-campaign-parent`. Claude y varias revisiones advirtieron que **no se podía fusionar íntegra**: el árbol sincronizado desde el repositorio oficial ya conserva ejecutores con certificados, ledger, verificación de procedencia y contrato POST→ACK→TTL. La política común también existe y fue desarrollada en el oficial mediante #153. La rama histórica queda archivada en `ci/post-age-policy-archive-20261010`; no se perdió ninguna aportación.

En lugar de llevar código obsoleto a producción, se ha reconstruido **esta misma PR #8** sobre `research/public-reuse-parent` vigente en la conciliación (`250ccb019fb8683311df48c7d02d6c6d2b73a47b`). El diff se limita a **un test de contrato y este documento**, sin reemplazar ningún ejecutor, sin nueva implementación de la política y sin tocar credenciales, estado operativo, red social ni certificados.

## Tratamiento de todos los comentarios y revisiones

- Revisiones de Claude: **aceptadas**. No se puede sustituir en bloque `tools/`. Se preserva exactamente el árbol operativo de la base y se rescatan solo pruebas adicionales.
- Hallazgo crítico **Threads WEB, misma frase/diferente post (1/40 días)**: **aceptado** y segregado en [#177](https://github.com/davidpd89/ci-sandbox-tmp/pull/177), que valida autor/permalink antes del compositor. No se reintroduce el ejecutor antiguo desde #8; la aceptación real en Edge queda pendiente de Claude.
- Origen temporal, prioridad URL X, TID Bluesky, shortcode Threads, `save` Pinterest y follow-ups API: cambios de producción tratados por [#169](https://github.com/davidpd89/ci-sandbox-tmp/pull/169); **no duplicados** aquí.
- Reacciones y guardados de **edad desconocida**: la política actual conserva su compatibilidad y permite algunas acciones sin fecha. Se documenta como decisión pendiente de producto; no se presenta como garantía de cero necroposting.
- Diferencia entre `created_at` del destino, `first_seen`, cola, indexación o edades relativas: el test nuevo exige `post_created_at` desde las filas fuente para Bluesky, Mastodon, Threads y TikTok. Sin fecha, no se inventa un origen verificable. Falta contraste real de WEB/MOBILE.
- Revisión temporal de [#204](https://github.com/davidpd89/ci-sandbox-tmp/pull/204): capa de DST/time_utils de programación **no sustituye** fecha de publicación del objetivo; pruebas de UTC con reloj fijo, sin reimplementar #98/#155.
- Test de la cola multiproceso 19/20 en Windows: desviación real pero fuera de este diff; quedó registrada en la auditoría de [#169](https://github.com/davidpd89/ci-sandbox-tmp/pull/169) y no se maquilla como evidencia positiva.
- Comentarios anteriores que daban “lista con reservas” eran correctos **solo para el árbol viejo**, no bastan para integrar al oficial actual; esa aprobación quedó superada por las revisiones de Claude.

## Prueba nueva y límites

`tests/test_ci8_target_date_pipeline.py` verifica 3 tipos de ruta API/MOBILE con fechas antiguas/recientes/desconocidas y Threads WEB con fecha explícita/ausente en el constructor. No realiza escrituras ni acciones en redes. Esta prueba no reemplaza los canarios de Edge, API autenticada ni móvil. Claude debe verificar además la integración final de #169/#177 en el oficial más reciente, el comportamiento del ledger y los datos de origen reales, con todo el circuito POST→ACK→TTL intacto.

**No hacer merge automático**. Esta PR reducida solo añade regresiones sobre la base ya sincronizada; su alcance es distinto de #169/#177. Verificar el CI contra su HEAD exacto y el estado de la base antes de fusionar.
