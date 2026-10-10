# INFORME 115 — implementación y auditoría offline (10/10/2026)

## Decisión sobre el código existente

El repositorio privado, rama `integracion/crecimiento-2026-10` (HEAD de referencia `5449513d9b545d0a6a72abf066ab6a779bfdad71`), dispone de búsquedas, Jetstream, `discovery_terms`, `source_rotation`, `discovery_graph`, `discovery_attribution` y `discovery_ranking`. El catálogo `00_OPERATIVO/descubrimiento_gpt.json` tiene entradas para ocho redes, pero no Instagram; el espejo público no incorpora el JSON. Evitar duplicar motores/colas/tablas y coordinar #21 (fuentes), #63 (hashtags), #66 (ranking), #99 (observaciones), #100 (ingesta), #101 (consumidores), y #49/#50/#71/#72 del oficial.

## Implementación

`tools/niche_query_bank.py`: taxonomía de seis intenciones lectoras y extensiones por red. `tools/discovery_terms.py`: los consumidores de `terms(network, "busquedas", suffix, skip)` añaden las consultas tras las existentes y deduplican sin eliminar tildes, con opción reversible `include_niche=False`. No cambia hashtags, hubs, semillas, ejecución, ranking ni cadencias. En el snapshot leído, X, Threads, Facebook y Pinterest ya llaman al helper; para las otras cinco redes, la conexión efectiva queda pendiente de integración de #101. No presentar la lista como paridad de ejecución ya confirmada.

## Fuentes públicas verificadas

- [bluesky-social/jetstream@f42df08](https://github.com/bluesky-social/jetstream/tree/f42df08ba0ca9e4287020139aefbcfe24506d1ef): 09/10/2026; MIT **o** Apache-2.0 (`LICENSE-DUAL`), servidor Go; no añadir un segundo servidor frente al existente.
- [ruggsea/bluesky-firehose-py@5c27917](https://github.com/ruggsea/bluesky-firehose-py/tree/5c279172c40b7f5ceab0b8ae97f1e0a83b07be69): MIT; 03/02/2025; dependencias ancladas antiguas, sin verificación de Windows/Python 3.11. Rechazar worker redundante. JSONL puede merecer adaptador de importación separado.
- [instaloader/instaloader@7efc78d](https://github.com/instaloader/instaloader/tree/7efc78de12e02feb1794b71125a48e66250f0db0): MIT; 06/09/2026; documentación Python >=3.8 y Windows. No introducir un segundo cliente Instagram antes de resolver #100.
- [JustAnotherArchivist/snscrape@614d4c2](https://github.com/JustAnotherArchivist/snscrape/tree/614d4c2029a62d348ca56598f87c425966aaec66): GPL-3.0; último commit de rama principal 22/06/2023; compatibilidad actual con X sin verificar. No integrar.
- `facebook-pages-scraper` y `social-media-profile-scrapers`: el informe no identifica de forma inequívoca repo+licencia+commit. No instalar sin resolverlo.

**Reutilización efectiva:** se amplía el helper compartido de búsqueda y se mantienen los escáneres/rotación del proyecto original. No se ha copiado código de terceros ni se añade dependencia; las fuentes se usaron para comparación técnica, no para reclamar vendorización inexistente.

## Pruebas y auditoría adversarial

`python -m unittest discover -s tests -p test_niche_query_bank.py -v`: **7/7 OK**. `python -m pytest -q tests/test_niche_query_bank.py`: **7/7 OK**; `python -m compileall -q tools tests`: OK; Linux Python **3.13.5**. Datos totalmente sintéticos, nueve redes (24–27 consultas adicionales en cada una), orden original y Unicode, control de duplicados, JSON ausente/corrupto y conservación de hashtags. El número de candidatos/seguidores obtenidos no se ha medido.

**Falta para Claude:** ejecutar la suite privada y Windows/Python 3.11, reconciliar el posible conflicto de `discovery_terms.py` con #63, comprobar consumos de las nueve redes tras #101 y realizar comparación real por fuente sin interactuar durante QA. Ninguna red fue utilizada, no se accedió a secretos, no se ha hecho merge.
