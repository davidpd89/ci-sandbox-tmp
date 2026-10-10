# #101 — Paridad de consumidores de búsquedas y hashtags

Fecha: 2026-10-10. Estado: propuesta de integración, **sin merge**. Las únicas operaciones ejecutadas aquí son lectura GitHub, generación de código y pruebas offline. Referencia oficial privada consultada **solo en lectura**: `davidpd89/rrss-davidporto-CODE@5449513d9b545d0a6a72abf066ab6a779bfdad71`. No se han trasladado configuraciones, perfiles, registros ni credenciales de ese repositorio.

## Problema y solución

La PR [#63](https://github.com/davidpd89/ci-sandbox-tmp/pull/63) introduce `hashtag_expansion.snapshot_terms` y mezcla su salida en `discovery_terms.terms(network,kind)`, con caché JSON, schema/TTL y conservación del catálogo. La presente rama tiene un `discovery_terms.py` anterior a ese cambio, de modo que **la cobertura de snapshots reales está pendiente de integrar #63**. Este trabajo no copia ni rehace #63; lee su interfaz pública desde `tools/hashtag_query_consumers.py` en cada ronda o carga de configuración.

Antes: cuatro escáneres añadían `discovery_terms.terms(..., "busquedas")` durante el *import* (X, Threads, Facebook, Pinterest), otros ocho puntos de consumo —incluidos hashtags de Facebook— seguían separados. Un proceso abierto no observaba un snapshot posterior. Ahora: función única de normalización + selección, invocada en los escáneres operativos o en sus loaders. Unicode NFC, deduplicación de consulta final, presupuesto intacto, rotación determinista con plaza para exploración y degradación a semillas cuando falta el proveedor. No hay ejecución social en el adaptador.

## Matriz comprobable de rutas

| Red | Cola y fichero | Tipo / destino de lectura | Reserva, presupuesto y límite |
|---|---|---|---|
| X | WEB, `x_scan.py` | `_lexical_queries` → `x.open_search`, keywords `lang:es` y `#tag lang:es` | Misma cuota `stage["searches"]`; resto de consultas conversacionales intacto; sin auto-like |
| Threads | WEB, `threads_scan.py` | `_rotate_searches` → pestañas de búsqueda, texto y #tag | Misma `n_searches`; keywords de perfil independientes |
| Facebook | WEB, `facebook_scan.py` | `_rotate_searches` → `get_search_data`; `_rotate_hashtags` → `get_hashtag_data` | Cuotas 10 búsquedas y 8 hashtags por defecto; etiquetas sin # en el adaptador de API |
| Pinterest | WEB, `pinterest_growth.py` | `day_queries` → consultas de pins; keywords y #tag | Misma cuota de 8 por ronda y tableros existentes sin mutación |
| Reddit | WEB, `reddit_scan.py` | `_discovery_sources` → `_dump_subreddit` o `_dump_search` del cliente existente | Dos superficies por ronda; en rondas alternas se intercala una búsqueda léxica; hashtags **no** son nombres de subreddits |
| Bluesky | API, `bluesky_growth_scan.py` y `bluesky_scan.py` | loader → `query_families` y `tag_queries`; ruta legacy → `_search_posts` | `coverage` no se toca; scoring existente decide prioridad |
| Mastodon | API, `mastodon_growth_scan.py` y `mastodon_scan.py` | loader → `query_families`, `hashtags`; legacy → `get_hashtag_statuses` | `coverage` y `budgets` sin cambios; metadatos de alcance intactos |
| TikTok | MOBILE, `tiktok_growth_scan.py` | loader → `actor_queries` / `video_queries` → `tiktok_discovery.run_surface` | `budgets` por superficie intactos; sin acceso a dispositivo en CI |
| Instagram | WEB, `instagram_scan.py` | `_rotate_queries` → `_search_accounts` con búsquedas nuevas y tags como keywords | Dos consultas verificadas + una **trial**; ninguna observación nueva se promociona automáticamente |

El contrato transversal declara `NETWORK_QUEUE` para las tres vías independientes. Solo transforma consultas de lectura: identidad del candidato, deduplicación de posts, política temporal de destino y ejecución quedan en los colectores y guards existentes. La consulta se conserva como Unicode; **su URL encoding se hace en la capa de transporte**, ver `reddit_interact._dump_search` y pruebas `urllib.parse.quote/unquote`. No construir URL con concatenación sin escapado.

## Medición sintética antes/después

Fixtures deterministas: por red 2 semillas (`lectores`, `escritores`) + 2 términos nuevos (`fantasía juvenil`, `lectura ñ`), 2 variantes de etiquetas (`#año`, `#ano`) y entradas duplicadas/inválidas. *Antes del adaptador nuevo*, solo cuatro redes consumían listas GPT de keywords en importación y ninguna aseguraba observar nuevos términos de #63 en cada ronda. *Después*, 9/9 contratos de red reciben **2/2** nuevos términos en `combine` con lector sintético; 8/8 redes con hashtags conservan **2/2** etiquetas distintas. Reddit rechaza la superficie hashtag pero consume texto (equivalente funcional). Con `select` y presupuesto >=2 se reserva al menos una semilla y una novedad si ambas existen; presupuesto=1 alterna cohortes. El número de búsquedas efectivamente lanzadas nunca supera el presupuesto original. No es medida de volumen de candidatos reales ni se afirma mejora de seguidores.

Las pruebas simulan salida válida, caducada (lista vacía del loader #63), corrupta y ausente. El fallo/TTL *interno* de `hashtag_expansion.snapshot_terms` lo comprueba #63 y debe ejecutarse como prueba conjunta al integrar ramas. `unittest` ejecuta además funciones originales aisladas por AST (sin importar sesiones) para probar la conexión real de las entradas. Sintaxis de los once consumidores: `compileall`.

## Comparación de componentes públicos, revisión del 10/10/2026

| Candidato y procedencia inmutable | SPDX / mantenimiento comprobado | Compatibilidad y coste | Decisión |
|---|---|---|---|
| [atproto@4c17895](https://github.com/MarshalX/atproto/tree/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8) [pyproject](https://github.com/MarshalX/atproto/blob/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8/pyproject.toml) | MIT; último cambio observado 02/10/2026 | Python 3.9–3.14, independiente de SO; SDK de red y dependencias voluminosas | Conservar transporte de Bluesky existente; no instalar SDK para unir listas |
| [Mastodon.py@336a62d](https://github.com/halcy/Mastodon.py/tree/336a62d850a28f6f066a26b83506ed70f0f4b906) [licencia](https://github.com/halcy/Mastodon.py/blob/336a62d850a28f6f066a26b83506ed70f0f4b906/LICENSE) | MIT; commit observado 07/10/2026 | Wrapper HTTP independiente del SO; extras opcionales de Windows | La API del proyecto ya soporta hashtags; evita otra librería |
| [PRAW@4a9eb7e](https://github.com/praw-dev/praw/tree/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1) [pyproject](https://github.com/praw-dev/praw/blob/4a9eb7ee3ac5743ce8b848e9f7b187eae4826da1/pyproject.toml) | BSD-2-Clause; commit observado 09/10/2026 | Python >=3.10, multiplataforma, cliente HTTP con dependencias | `reddit_interact._dump_search` existente basta; no cambiar el transporte |
| Implementación actual y #63, [HEAD #63](https://github.com/davidpd89/ci-sandbox-tmp/pull/63) | Código ya mantenido en el proyecto; sin licencia de terceros añadida | Python 3.11, `unicodedata`, `copy`, sin paquetes nuevos ni credenciales | **Elegida**. Adaptar un contrato pequeño, reutilizar #63 y puntos de lectura actuales |

No se copiaron fragmentos de estos repositorios externos: comparación de API, mantenimiento, coste y adecuación. Una librería cliente resuelve solicitudes de red, no la mezcla de términos ni el presupuesto de nueve consumidores; instalarla aquí crearía trabajo de transporte fuera del alcance. Las licencias permitirían su uso con sus obligaciones de atribución cuando corresponda.

## Segunda revisión adversarial y correcciones

- **Snapshot renovado**: los cuatro consumidores de importación ahora consultan al ejecutar. Si el loader #63 devuelve vacío o lanza un error de datos, se conservan semillas.
- **Unicode**: `#año` y `#ano` nunca se fusionan; NFC sí identifica secuencias compuestas equivalentes. `lang:es` solo una vez en X; se deduplica tras formatear.
- **Presupuesto**: las rutas de búsqueda dinámicas se intercalan sin añadir una consulta a los contadores de turno. Facebook tiene presupuestos independientes de tags/texto. Reddit mantiene dos superficies, por lo que la búsqueda desplaza temporalmente una visita al subreddit, no la elimina del pool.
- **Mutación y repetición**: `extend_native_config` hace copia profunda y es idempotente incluso con múltiples cargas; se corrigió la pérdida de listas cuando el campo no existía. Un payload no-lista/lector con fallo degrada a estático.
- **Separación**: `#63` produce léxico, `#99` introduce observaciones, `#21` descubre/rankea; #101 **solo** consume términos. No cambia la evaluación de antigüedad, la selección final, ni las colas de escritura.
- **Huecos que siguen abiertos**: en Instagram el hashtag no se convierte en búsqueda de publicaciones con autores verificados; solo alimenta una trial de perfiles. La selección nativa de Bluesky/Mastodon/TikTok sigue su ranking/budgets y puede posponer un término; `combine` garantiza presencia en el pool, no ejecución en cada ronda. La comprobación conjunta de TTL real requiere fusionar primero #63, y la ruta móvil no se ha ensayado en Xiaomi/Edge/Windows interactivo.

## Secuencia de integración, canario y rollback

1. Revisar #63 (motor) y #99 (entrada), integrar después el contrato #101 conservando la API legada `discovery_terms.terms` de la rama oficial. Revisar cherry-pick de archivos y posibles conflictos con cambios posteriores a `5449513d`.
2. Ejecutar Python 3.11 en Ubuntu y Windows: `python -m unittest discover -s tests -p 'test_hashtag_query_*.py' -v`. Correr también pruebas de #63 sobre snapshot JSON real **sintético** y tests de scans/rotación ya existentes; confirmar diferencias de #21 y loaders de vocabulario.
3. Canario **supervisado**, no ejecutado aquí: primero shadow mode solo lectura por cola WEB/API/MOBILE; comparar consultas emitidas, candidatos útiles únicos, % duplicados, % dentro de ventana de edad, falsos positivos y tasas de respuesta/seguimiento confirmadas a varios días. Separar métricas por red y consulta; no atribuir followers sin evidencia.
4. Confirmar en Windows/Edge y dispositivo móvil los tiempos, Unicode y búsquedas por hashtags. Si cae calidad o aumenta ruido/repetición, desactivar el consumo dinámico por red (pasar `reader=lambda *_: []` en el adaptador), **sin eliminar semillas** ni tocar la cache de #63; o revertir exclusivamente los commits #101. Ningún rollback exige cambios en estados reales de redes.

**Bloqueos de validación**: pruebas offline no sustituyen canario supervisado; integración conjunta con #63/#99 y validación de Edge/móvil queda para Claude. PR no fusionada.
