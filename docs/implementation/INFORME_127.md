# INFORME 127 — Implementación verificada (10/10/2026)

## Resultado real

- Nuevo `tools/bluesky_feed_preview.py`: vista **local, solo lectura** del feed de nicho desde la **misma** tabla `posts` creada por `tools/bluesky_jetstream_collect.py`, sin introducir otro crawler, credenciales, base de datos ni acciones sociales.
- Formato `getFeedSkeleton`: `{"feed":[{"post":"at://..."}],"cursor":"..."}`, con cursor keyset `time_us::at_uri`; los empates se resuelven por URI (no `OFFSET`), fin de resultados `eof`.
- Filtro conservador: publicaciones originales, fecha de creación y observación reciente, idioma `es`/`es-*` o vacío previamente aceptado por Jetstream, coincidencias de nicho y validación sintáctica de AT URI. Al consultar la caché se respetan borrados ya observados por el recolector.
- `tests/test_bluesky_feed_preview.py`: seis pruebas unitarias y 14 subpruebas, sin servidor, API, sesiones ni datos reales.

**No es un feed alojado/publicado.** Falta validar remotamente que cada post sigue existiendo y es visible en el AppView antes de exponerlo como servicio público; los borrados perdidos durante una desconexión de Jetstream no pueden inferirse de una caché local. No ejecutar `publish_feed.py` ni registrar un feed hasta completar ese requisito.

Uso offline:
```powershell
python tools/bluesky_feed_preview.py --db SISTEMA_DIARIO_BLUESKY/cache/jetstream.sqlite3 --limit 30 --max-age-hours 48 --min-matches 1
python -m pytest -q tests/test_bluesky_feed_preview.py
```
Una caché ausente provoca `FileNotFoundError` (no se confunde con 0 posts).

## Origen de código reutilizado y verificación

| Repositorio | Commit verificado | Comprobación | Decisión |
| --- | --- | --- | --- |
| [MarshalX/bluesky-feed-generator](https://github.com/MarshalX/bluesky-feed-generator) | `be500ba5be2c2006f0649c8ce8862943ac7966c3` (19/08/2026) | MIT; servidor Python + SQLite; `server/algos/feed.py` ordena por fecha/identificador y expone `feed`/`cursor`. | **Adaptado** el algoritmo de paginación estable y la salida skeleton a `time_us + uri` del recolector que YA existe. Se atribuye upstream en docstring; sin Flask, Peewee ni autenticación nueva. |
| [MarshalX/atproto](https://github.com/MarshalX/atproto) | `4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8` (02/10/2026) | MIT; `pyproject.toml` declara Python >=3.9,<3.15 y 3.11. | No se añade dependencia: la integración actual usa REST/XRPC con tests y caché de sesión. El SDK arrastraría Pydantic/httpx/websockets, sin beneficio en esta PR. |
| [bluesky-social/feed-generator](https://github.com/bluesky-social/feed-generator) | `70e172e16c659167707a7ef65eef7e37fdb606ff` (25/09/2026) | MIT; kit oficial TypeScript, devuelve `feed` y `cursor`. | Contrato de referencia, **no** portado TypeScript ni lanzado servicio. |
| [OSINTCabal/OSINTSky](https://github.com/OSINTCabal/OSINTSky) | `c94536071ed2175a70a00c8cc56cdef409cf3cb6` (15/01/2026) | No hay archivo LICENSE verificable ni licencia declarada en GitHub; actividad limitada. | Se descarta copiar. El motor ya descubre perfiles y expande grafos. |
| [brainsnorkel/hourstats-bsky](https://github.com/brainsnorkel/hourstats-bsky) | `57a70260748a69bb1e0ec243bddf05ba8324db67` (02/10/2026) | MIT, pero escrito en Go. | Se descarta: Jetstream, ventanas y ranking ya existentes. |
| [pwillia7/Bsky_Spreadsheet_Poster](https://github.com/pwillia7/Bsky_Spreadsheet_Poster) | `61427c4068e72cd39b0ea6674703329315ffc5bf` (07/08/2025) | MIT; publicación desde Sheets y follows. | Se descarta: la cola/ledger SQLite y políticas globales ya existen. |
 
La compatibilidad de sintaxis con Python 3.11 se verificó con `ast.parse(feature_version=(3,11))`; no equivale a ejecución real en Windows 3.11. El módulo solo usa biblioteca estándar (sqlite3 con JSON1 de SQLite), `pathlib.as_uri()` y ficheros locales.

## Comparación con el código oficial y PR

Se consultaron el árbol de `davidpd89/rrss-davidporto-CODE@integracion/crecimiento-2026-10`, sus `tools/bluesky_growth_scan.py`, `bluesky_interact.py`, `bluesky_pool.py`, `bluesky_jetstream_collect.py`, `growth_config.json` y pruebas relevantes, así como PR abiertas/fusionadas. Ya existen:

- búsqueda V2 con fallback V1, frases/hashtags, consultas y términos rotativos;
- seguidores, seguidos, notificaciones, starter packs, feeds sugeridos/guardados/por autor, Jetstream y co-likers;
- scoring del candidato, memoria SQLite, dedupe de objetivos/acciones, límites, QA del español, aprendizaje de resultados y planificación por red.

No se reescriben ni se cambia el volumen operativo: solapa con **PR #115** (descubrimiento), **#116** (ranking), **#117** (paridad), **#136** (puente Jetstream) del espejo y múltiples PR fusionadas en el repo oficial. El ejemplo de Perplexity sobre "200 posts útiles por día" y porcentajes de conversión no constituye evidencia reproducible. No se usan como umbrales.


## Corrección integrada en descubrimiento EXISTENTE

La segunda pasada encontró en `tools/bluesky_growth_scan.py::_search_popular_feeds` un fallo que desperdiciaba lecturas: elegía `feeds[:2]` **antes** de comprobar relevancia y aceptaba feeds irrelevantes si el término de la propia consulta era literario (`_hits(query) > 0`). Ahora:

- filtra por términos en **nombre y descripción del feed** y excluye metadatos políticos;
- ordena por número de señales de nicho, después popularidad y URI;
- elimina URIs repetidas antes de consumir las dos lecturas de feeds;
- tolera `likeCount` no numérico, y desempata por orden de aparición para no comparar diccionarios;
- mantiene presupuestos, métricas, `Collector.add_post` y resto del contrato de las nueve redes.

Regresión añadida al archivo original `tests/test_bluesky_growth_scan.py`: mezcla de feed ajeno muy popular, feed literario más relevante, duplicados idénticos y contador malformado. **Esta prueba de integración del escáner no pudo ejecutarse localmente**, porque no se materializó el árbol completo del repositorio privado. Claude debe incluirla en la suite del repo oficial. No hay métricas reales de mejora obtenidas aún.

## Norma global y adaptadores

Regla común para las **nueve redes**: todo candidato proviene de fuente identificable, posee identidad de post/cuenta, fecha verificable, idioma/tema y estado de interacción; las lecturas no autorizan escrituras; cada adaptador traduce señales propias al motor existente de candidatos, dedupe, ranking, QA y resultados confirmados. Nunca trasladar como fórmula global los contadores de likes/replies de Bluesky a Pinterest o Reddit.

Adaptadores existentes: Bluesky (AT URI, Jetstream, feeds; solo este módulo de previsualización); Mastodon (URI federada, instancias); X y Threads (posts y conversaciones); Instagram y TikTok (posts/reels/videos y comentarios); Facebook (páginas/grupos/hilos); Pinterest (pines/guardados); Reddit (subreddits/hilos). La exportación `getFeedSkeleton` es **específica de Bluesky**, no debe imponerse al resto. El resto mantiene `tools/network_policy_contracts.py`, `tools/candidate_identity.py`, `tools/growth_policy.py` y las PR comunes, en lugar de duplicar lógica aquí.

## Pruebas y revisión en varias pasadas

1. **Implementación:** paginación keyset, filtro de posts recientes/español, lectura SQLite en modo RO.
2. **Autorrevisión ajena:** detectados un falso fallo del test (`now_us` duplicado) y un posible descriptor SQLite abierto que afecta a Windows; corregidos y reejecutados.
3. **Alternativas:** descartados servidor Python completo del feed generator, SDK nuevo y scraper OSINT por duplicar el sistema o exigir servicios; la extracción offline es reversible.
4. **Resultado local:** `python -m unittest discover -v -s tests -p test_bluesky_feed_preview.py` → **6/6 OK**. `python -m pytest -q tests/test_bluesky_feed_preview.py` → **6 passed, 14 subtests passed**, con copia local equivalente. `py_compile` y sintaxis Python 3.11 → OK. Entorno real del ensayo: Python **3.13.5** / SQLite **3.46.1** / pytest **9.0.2** / Linux.
5. **No verificado aquí:** suite completa del repo privado, runtime real en Python 3.11/Windows/Edge/móvil, recuperación ante desconexiones reales, feeds ajenos en línea, instalación de dependencias del proyecto y exposición/publicación pública. **Claude debe ejecutar esos escenarios** con datos anonimizados.

**Sin merge, sin secrets, sin acciones reales en redes, sin activar colectores.**


## Ampliación tras auditoría del 10/10/2026 (revisión adicional)

- Se comprobó contra el código upstream real `MarshalX/bluesky-feed-generator@be500ba5be2c2006f0649c8ce8862943ac7966c3` y su archivo `LICENSE`: MIT, copyright (c) 2023 Ilya Siamionau. Se adaptó el patrón de orden descendente y cursor compuesto, no su servicio ni un nuevo SDK.
- **Defecto detectado y corregido:** si `LIMIT` se aplicaba antes de verificar la sintaxis de URI, una tanda de registros importados corruptos podía producir `eof` falso. Ahora se avanza internamente en lotes keyset, sin saltar registros válidos y manteniendo en la respuesta el cursor de la última URI válida. Una regresión inyecta 115 URI inválidas antes de una válida.
- Exportador opcional `--export-json ./salida/feed.json`, siguiendo el patrón de skeleton estático citado en la revisión de Perplexity; sigue siendo **solo local**, no constituye publicación ni feed servido. No cambia la ruta por defecto ni abre red.
- Regresiones adicionales: inserción tardía detrás del cursor; exportación UTF-8 y directorios nuevos, opt-in de CLI. Total esperado del módulo aislado: 9 casos `unittest` (más sus subtests existentes). La confirmación con suite privada y en Windows/Python 3.11 corresponde a Claude.
- No se incorpora aquí un validador AppView: ya hay una PR específica, **#146**, que evita duplicar código. La posible indexación compuesta de la tabla Jetstream se separa por afectar al recolector compartido.
