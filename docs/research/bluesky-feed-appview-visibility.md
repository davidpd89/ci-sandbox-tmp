## Encargo para GPT

### Objetivo

Antes de publicar un feed literario Bluesky, añadir **verificación de existencia/visibilidad real de posts** sin confiar exclusivamente en Jetstream. La vista previa **offline** de la PR #127 es solo un prototipo; la caché puede conservar posts borrados durante un corte de conexión, ocultados en AppView o etiquetados después.

### Código y PR a revisar ANTES de cambiar nada

- `davidpd89/rrss-davidporto-CODE`, rama `integracion/crecimiento-2026-10`:
  `tools/bluesky_jetstream_collect.py`, `tools/bluesky_growth_scan.py`,
  `tools/bluesky_interact.py`, `tools/candidate_identity.py`, pruebas.
- PR #127 del espejo: `tools/bluesky_feed_preview.py`; es una dependencia conceptual, no copiar sin revisar.
- PR #94, #95 y #136 del espejo: recuperación e ingesta Jetstream. Evitar duplicarlas.
- Referente upstream [bluesky-social/feed-generator](https://github.com/bluesky-social/feed-generator/tree/70e172e16c659167707a7ef65eef7e37fdb606ff);
  verificación de metadatos mediante métodos públicos XRPC; revisar lexicon actual.

### Entregable implementable

1. Añadir revalidación por lotes `app.bsky.feed.getPosts` solo lectura, desde el adaptador Bluesky existente: comparar el conjunto solicitado con el devuelto, tratar no encontrados/borrados/ocultos como **no aptos para feed**, no como 0 engagement. Sin consultas por post individuales.
2. No publicar, no dar likes, no seguir, no contestar, no crear registros propios ni credenciales. Diseñar caché TTL de validación con clave AT URI, evitando que un cambio de DID/handle contamine la identidad.
3. Pruebas 100% offline con respuestas sintéticas: borrado durante hueco Jetstream; post oculto; error HTTP/parcial (fail closed); 25+ URIs paginadas y deduplicadas; reaparición; cache vencida; cierre de conexión; Windows + Python 3.11.
4. Salida auditable y exportable, sin contenido personal ni tokens. Contadores de candidatos aptos/no aptos/indeterminados y motivo.
5. **Norma global para nueve redes:** todo adaptador que ofrezca un candidato para acciones externas o exposición pública debe distinguir presencia confirmada, ausencia confirmada e indeterminado. No forzar endpoint Bluesky ni disponibilidad de `getPosts` en las otras ocho redes: adaptar capacidades reales.
6. Añadir documentación breve con repositorio/commit/código reutilizado y pruebas; contrastar con PR abiertas antes de implementar.

### Criterios de aceptación

- Ningún post que ha desaparecido del AppView entra en el feed público.
- Error de AppView no degrada a publicar datos potencialmente obsoletos ni autoriza nuevas acciones.
- Tests locales reproducibles, sin red; decisión explícita para hidratación por lotes.
- PR pequeña; base `research/public-reuse-parent`; **no hacer merge**.

### Fuera de alcance

Alojar `getFeedSkeleton` público, registrar feed real, analizar usuarios privados, campañas de follow, cambiar los motores de ranking ya operativos. Es un paso previo independiente de la publicación.
