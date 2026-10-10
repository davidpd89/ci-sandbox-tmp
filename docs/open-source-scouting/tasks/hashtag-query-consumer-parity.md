# Distribución homogénea de etiquetas y búsquedas entre escáneres

## Origen comprobado (revisión #63, 10/10/2026)

La PR #63 genera términos en un snapshot `networks[red].hashtags/busquedas` y
`discovery_terms.terms()` los combina con el catálogo estático. Sin embargo,
la mayoría de adaptadores actuales no consumen esa función. Revisión del
oficial `davidpd89/rrss-davidporto-CODE`, commit
`5449513d9b545d0a6a72abf066ab6a779bfdad71`:

- X `tools/x_scan.py`, Threads `tools/threads_scan.py`, Facebook
  `tools/facebook_scan.py` y Pinterest `tools/pinterest_growth.py` añaden
  `discovery_terms.terms(..., "busquedas")` a sus pools.
- Facebook mantiene también `HASHTAG_POOL` propio; añadir búsquedas no lo
  amplía. Bluesky `tools/bluesky_growth_scan.py` usa `tag_queries` de
  configuración; Mastodon `tools/mastodon_growth_scan.py` usa
  `growth_config.hashtags` y `tools/mastodon_scan.py` un pool separado.
- Instagram, TikTok y Reddit aún usan rutas de descubrimiento específicas;
  no hay contrato probado que distribuya allí el snapshot de #63.
- PR #99 desarrolla **entrada** de observaciones/feedback hacia #63. Este
  encargo desarrolla **salida** desde #63 hacia las fuentes de búsqueda; no
  debe duplicar #99 ni el ranking de #21.

## Entrega que se pide

Crear un contrato común y adaptadores de solo lectura que transformen el
snapshot léxico de #63 en consultas pertinentes para las nueve redes, según
capacidades reales: `hashtags` donde existan, `busquedas` para descubrimiento,
comunidades/subreddits como equivalentes cuando corresponda. Conservar listas
estáticas y el presupuesto de consultas por red, deduplicar tras formar la
consulta final, codificar adecuadamente tildes/ñ/Unicode y mantener aislamiento
estricto por red. No confundir generación de vocabulario con publicación o
acciones sociales.

Primero verificar las funciones y puntos de consumo reales del repositorio
oficial. Comparar patrones públicos reutilizables y documentar licencia,
commit, compatibilidad y coste. Añadir adaptadores pequeños en vez de nueve
pipelines de ranking. Sin cambiar motor de #63, políticas de edad ni colas de
acciones.

## Criterios de aceptación

1. Matriz verificable para las 9 redes con lectura efectiva y tipo de consulta,
   explicando limitaciones y modo de degradación a estático.
2. Pruebas sintéticas por red (Python 3.11 Windows/Ubuntu) que inyecten un
   snapshot fresco, vencido, corrupto y vacío. Probar que cada consumidor
   recibe términos nuevos sin duplicar ni sustituir semillas estáticas.
3. Tests de formato de consultas `lang:es`, hashtag real, keywords y
   rutas móviles, Unicode `#año`/`#ano`, presupuestos, orden y rotación.
4. Contratos de las tres vías WEB/API/MOBILE que preserven deduplicación,
   idempotencia y filtrado temporal. Ejecución offline sin cuentas, secretos,
   APIs sociales, follows, comentarios o publicaciones.
5. Informe `docs/research/` con antes/después medido como cobertura
   sintética de consultas y un plan de canario supervisado (número de
   candidatos útiles, tasa de duplicados, respuestas y seguidores), más rollback.
6. Comparar con #63, #99, #21 y los loaders de vocabulario Bluesky/Mastodon:
   no duplicar lógica existente, coordinar integración con Claude. No merge.

Orden de integración recomendado: #63 (motor), #99 (entrada) y esta PR
(consumidores), con validación adicional en el repositorio oficial.
