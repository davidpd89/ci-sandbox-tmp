# PR #122 — Adaptador X reciente, lectura opcional

Fecha de auditoría: 10/10/2026. La PR original aporta docs/perplexity/crecimiento-x.md. No se ha ejecutado ninguna acción en redes ni utilizado credenciales.

## Verificación de fuentes y reutilización

- **Tweepy 4.17.0:** [PyPI](https://pypi.org/project/tweepy/) verifica publicación 02/07/2026, Python >=3.9, distribución py3-none-any (compatible por metadatos con Windows/Python 3.11). [MIT](https://github.com/tweepy/tweepy/blob/c1978d643ecce491929084e4290b35f57e4921ad/LICENSE); commit de publicación c1978d643ecce491929084e4290b35f57e4921ad. Actividad GitHub: push 02/07/2026. **Reutilizado** como biblioteca opt-in por su método público Client.search_recent_tweets; NO copiamos código.
- **twscrape 0.20.1:** [PyPI](https://pypi.org/project/twscrape/0.20.1/) confirma 25/08/2026, Python >=3.10, py3-none-any y [MIT](https://github.com/vladkens/twscrape/blob/5271cbdc5da1095b765a2a7ec750b4ac686d581f/LICENSE). Commit verificado de la distribución 5271cbdc5da1095b765a2a7ec750b4ac686d581f, push GitHub 05/10/2026. **Descartado:** necesitaría sesiones/captura no oficiales, almacén duplicado y nuevas pruebas de estabilidad.
- **XActions:** licencia [Apache-2.0](https://github.com/nirholas/XActions/blob/main/LICENSE), push GitHub 09/10/2026; principalmente JavaScript/browser. **Descartado** por solapamiento con x_interact y fragilidad.
- **Ejemplos X API:** la URL xdevplatform/Twitter-API-v2-sample-code se resuelve ahora en [xdevplatform/samples](https://github.com/xdevplatform/samples); referencia sin copiar ni asumir licencia de ejemplo concreto.
- **Fórmula del informe 0,30/0,20/...:** descartada por falta de dataset/backtest. Ya existen browser_pool.pick, growth_attribution, discovery_ranking, source_rotation y PR relacionadas (#50 oficial, #66/#116 del espejo).

## Qué se implementó

- tools/x_recent_api.py: consultas limitadas (Unicode NFC, dedupe, español, sin retweets, 512 caracteres conservadores), cliente Tweepy inyectado solo para lectura, paginación finita y sin reintentos ante 429, normalización con identidad remota author_id + includes.users, fechas UTC, exclusión de cuenta propia, dedupe por ID, control de errores parciales y salida del mismo formato de x_pool.record_posts.
- tests/test_x_recent_api.py: 16 pruebas aisladas de queries, fechas, identidad, filtrado, modelos tipo Tweepy, errores, paginación, cuotas y contrato de x_pool.
- requirements-x-api-optional.txt: pin opcional tweepy==4.17.0 fuera de requirements-ci.txt.
- El flujo de X ya tenía SEARCH_POOL, CONVERSATION_SEARCHES, TRIAL_SEARCH_POOL y reserva SQLite. Se **conservan**. El adaptador no crea otro motor de ranking ni otra tabla de acciones.

Ejemplo de uso **únicamente offline** con JSON previamente adquirido de manera autorizada:

```python
from x_recent_api import build_queries, normalize_page, stage_in_existing_pool
import x_pool
queries = build_queries(['fantasía juvenil', 'romantasy', '#BookTok', 'slow burn'])
rows = normalize_page(fixture_payload, now=aware_datetime_utc)
db = x_pool.connect('/ruta/temporal/pool.sqlite3')  # nunca DB productiva en QA
try:
    added = stage_in_existing_pool(db, rows, today='2026-10-10')
finally:
    db.close()
```

Integración opcional futura: un componente autorizado crea un Tweepy Client de solo lectura externamente y llama collect_recent(client, queries, max_pages=1, max_results=25). Este módulo no obtiene tokens, no arranca sesiones y no llama a follow/reply/repost/like. **No hay integración automática con mechanical_round**: conectar sin acreditar permisos, coste, cuota, deduplicación y controles cruzados sería incorrecto.

## Aplicación a nueve redes, revisión y límites

Se usa el patrón común actual «fuente observada → identidad/procedencia → reserva preexistente → filtros/ranking preexistentes → revisión», sin fabricar autores a partir de menciones y sin nuevas escrituras. Los catálogos por red ya están en discovery_terms / 00_OPERATIVO/descubrimiento_gpt.json. Esta PR añade **solo** el adaptador específico de X, no nueve adaptadores ficticios. #115/#117/#132 y PR oficiales de grafo/discovery contienen el trabajo transversal pendiente.

Revisión adversarial: una página parcial con errors aborta; fecha desconocida/futura/>7 días no se acepta; 429/401/403 se propagan; ningún resultado pasa automáticamente a una cola o plan. El límite de 512 caracteres del builder es conservador, **no** una afirmación de límite contractual actual. La disponibilidad/coste de API y el uso real del cliente no se han probado.

**Pruebas locales:** 16/16 (unittest, Python 3.13.5 Linux, sin red), compileall sin errores. La primera pasada destapó y corrigió un control de newline en consultas. Se revisaron las fuentes reales de x_pool, browser_pool, x_scan, x_build_plan y x_acquisition_audit del repo oficial en la rama de integración (HEAD observado 5449513d9b545d0a6a72abf066ab6a779bfdad71).

**Solo Claude puede comprobar:** pytest de esta PR junto a la suite completa real, Windows/Python 3.11/PowerShell/Edge/móvil, permisos X/API, compatibilidad con PR oficiales y CI espejo saneado del SHA exacto. En Windows: python -m pytest tests/test_x_recent_api.py -q -p no:cacheprovider; luego python -m pytest tests -q -p no:cacheprovider y python -m compileall -q tools tests. Sin apply ni cuentas.

**Rollback:** revertir los cuatro archivos nuevos de esta PR; conservar SQLite, historiales, ACK y cooldown. **NO MERGE** hasta revisión del controlador.