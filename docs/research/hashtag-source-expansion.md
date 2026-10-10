# PR #63 — Expansión inteligente de hashtags (10/10/2026)

Fuente primaria: https://github.com/rapidfuzz/RapidFuzz/blob/db6e504539a9c895180b266a06b36a32cb6029ee/LICENSE
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/rapidfuzz/RapidFuzz/tree/db6e504539a9c895180b266a06b36a32cb6029ee

## Problema

No había ranking multired con fuentes y caducidad compartidas. Véase diagnóstico siguiente.

## Alternativas

Contraste de RapidFuzz, YAKE, trendspyg y NetworkX en la tabla inferior.

## Licencias y procedencia

Se examinaron ficheros LICENSE y commits inmutables; no se copió código externo.

## Decisión

Mantener los adaptadores existentes y añadir una capa offline incremental de biblioteca estándar.

## Pruebas

Tests sintéticos y workflow Python 3.11 Ubuntu/Windows; resultados y limitaciones abajo.

## Retirada

Borrar la caché opcional y revertir el cambio aditivo en discovery_terms; no hay migración.

## Diagnóstico y fuente oficial

En el espejo, tools/discovery_terms.py solo lee bancos estáticos del JSON 00_OPERATIVO/descubrimiento_gpt.json (que no está incluido en el espejo). Bluesky tiene un minero propio en tools/bluesky_vocab_miner.py que cuenta autores distintos y Mastodon dispone de tools/hashtag_report.py para métricas semanales. Las demás redes tienen pools de búsqueda independientes, pero no existía un sistema común de coocurrencia, resultados, procedencia y caducidad.

**Contexto adicional del privado verificado**: davidpd89/rrss-davidporto-CODE, rama integracion/crecimiento-2026-10, commit 5449513d9b545d0a6a72abf066ab6a779bfdad71. En este commit, tools/discovery_terms.py tiene además EVIDENCE_ROLES, NETWORKS y tag_seeds (tarea #48), que NO figuran en la base del espejo. Claude debe conservarlos al integrar #63; no sustituir completamente el archivo oficial. No se han trasladado archivos privados ni estados reales.

## Código implementado

tools/hashtag_expansion.py implementa una capa 100 % offline de biblioteca estándar Python 3.11, con observaciones proporcionadas explícitamente por adaptadores: network, source, post_id, author_id, created_at, text y tags opcionales. Cuenta posts una sola vez por (red, ID), reúne procedencias y exige autores únicos. Extrae hashtags Unicode, normaliza acentos, exige coincidencia con semillas (fantasía, lectura, escritura, libro y actualidad, ampliables con JSON); mínimo dos autores y asociación temática de 0,60. Ignora posts con edad superior a 14 días, fechas futuras o sin zona horaria.

Ranking: asociación temática 55 %, autores distintos 20 %, frescura 15 % y resultados agregados 10 %. El feedback opcional contiene por red/etiqueta eligible, engaged, replies y followers. Realiza rotación determinista diaria entre etiquetas de puntuación cercana y reparto por temas; máximo 10 por red. El snapshot solo almacena puntuaciones, fuentes y agregados, sin identidades de autores ni posts.

Integración aditiva: tools/discovery_terms.py suma el vocabulario local ya calculado cuando existe un JSON válido en 00_OPERATIVO/hashtag_expansion.json (48 h de validez). Conserva las entradas estáticas; si falta la caché, caduca o está rota, no altera el comportamiento existente. La exportación se realiza únicamente si alguien ejecuta la CLI. No se accede a API, Chrome, móvil, credenciales, publicaciones ni estado de cuentas.

Uso offline con ficheros de datos sintéticos:

    python tools/hashtag_expansion.py --observations entradas.json --seeds temas.json --feedback resultados.json --now 2026-10-10T12:00:00+00:00 --output 00_OPERATIVO/hashtag_expansion.json

**Rollback**: eliminar el JSON opcional y revertir la incorporación a discovery_terms. No hay migración, escrituras sociales ni cambios a las colas WEB/API/MOBILE.

## Paridad por plataforma

| Red | Fuente de descubrimiento existente | Contrato nuevo |
| --- | --- | --- |
| Bluesky | Jetstream/minero, tag_queries | etiquetas y búsquedas |
| Mastodon | growth_config.hashtags, histórico semanal | etiquetas y búsquedas |
| X | consultas y buscador propio | etiquetas y búsquedas; ningún auto-like |
| Threads | SEARCH_POOL y perfiles | etiquetas y búsquedas |
| Facebook | consultas de discovery | etiquetas y búsquedas |
| Pinterest | SEO y búsquedas | etiquetas y búsquedas |
| Reddit | subreddits y búsquedas | búsquedas equivalentes, nunca hashtag nativo |
| TikTok | descubrimiento y móvil | etiquetas y búsquedas |
| Instagram | búsquedas y pruebas de hashtags | etiquetas y búsquedas |

La salida del motor es un inventario léxico, no una petición a cada plataforma; adaptadores que no llamen actualmente a discovery_terms todavía no reciben nuevos términos. El motor no cambia el filtrado de antigüedad de los destinos.

## Repositorios públicos contrastados a 10/10/2026

| Repositorio (commit fijo) | Licencia SPDX verificada | Mantenimiento, dependencias y decisión |
| --- | --- | --- |
| [RapidFuzz db6e504](https://github.com/rapidfuzz/RapidFuzz/tree/db6e504539a9c895180b266a06b36a32cb6029ee) | MIT | Última actividad 12/09/2026, Python >=3.11 y wheels Windows; requiere runtime Visual C++. La coincidencia exacta de etiquetas no necesita su motor C++ |
| [YAKE f7944f6](https://github.com/INESCTEC/yake/tree/f7944f645106d8c37c6999a1ba66d222f215a151) | AGPL-3.0 según LICENSE; pyproject indica LGPLv3 (metadatos contradictorios) | 09/02/2026; Python >=3.10, numpy/networkx/jellyfish; extracción de keywords sin procedencia ni métricas. No se copia |
| [trendspyg 9f07b25](https://github.com/flack0x/trendspyg/tree/9f07b2573e7287df85df9202da206569024723e9) | MIT | 01/10/2026; Python >=3.8 y navegador opcional; fuente de tendencias potencial pero no necesaria para procesamiento offline |
| [NetworkX 6da4704](https://github.com/networkx/networkx/tree/6da4704cbf32ba6f50f6d9c46cc0a071e3a87985) | BSD-3-Clause | 06/10/2026; multiplataforma. Para este contador de coocurrencias un grafo general añade dependencia sin beneficio medido |

**Decisión:** reutilizar y generalizar el patrón de autores únicos y filtros ya presente en el código del proyecto, sin copiar líneas de terceros ni introducir dependencias nuevas. El ranking semántico más caro no se justifica sin corpus etiquetado.

## Test y revisión adversarial

Ejecución verificable:

    python -m compileall -q tools/hashtag_expansion.py tools/discovery_terms.py
    python -m unittest discover -s tests -p test_hashtag_expansion.py -v

Workflow dedicado en Ubuntu y Windows con Python 3.11 y sin conexión a redes sociales. Regresiones sintéticas: nueve plataformas, idempotencia por post, múltiples fuentes, autores únicos, contenido sin tema, hashtags con ñ y acentos, feedback cuantitativo, mezcla de temas, timestamps stale/future/naive, caché corrupta/caducada, fallback estático y CLI. En un fixture con dos etiquetas positivas y dos negativas, precisión y recall observados de la expansión son 1,0 y 1,0; recall de nuevas etiquetas del banco estático era 0,0. **Estas cifras son solo sobre datos sintéticos de test y no acreditan resultados de producción.**

**Segunda revisión adversarial (puntos revisados)**: no contar el mismo post dos veces, ni la misma cuenta como varios autores; no promover hashtags que solo aparecen junto a fútbol; no filtrar historiales de otras redes; fallar a cache estática tras vencimiento; mantener límites del escáner destino. Las pruebas no ejecutan una ronda WEB/API/MOBILE. Mantenida la diferencia entre simulación y canario supervisado.

**Pendientes para Claude**: incorporar datos anonimizados de colectores, reconciliar tag_seeds del oficial (#48), comprobar formato de búsqueda por red y medir rendimiento de forma prospectiva (aceptados/obtenidos, respuestas, seguidores) con grupo estático de control. Validación viva de Edge, Windows de trabajo y Android pendiente. No hay secretos, acciones en redes ni merge. SPDX del código propio: ninguna dependencia incorporada o vendorizada.
