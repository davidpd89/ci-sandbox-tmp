# PR #120 — trayectorias relacionales verificables (10/10/2026)

Fuente primaria: https://github.com/retentioneering/retentioneering-tools
Fecha de consulta: 2026-10-10
Licencia SPDX: Apache-2.0
Referencia inmutable: https://github.com/retentioneering/retentioneering-tools/tree/fda32f26fc11119dc950ef6ad720eb5aeefe86a1

## Problema
El sistema oficial (`integracion/crecimiento-2026-10`) ya tiene `relationship_policy.py`, `reciprocity.py`, `loyalty.py`, `loyalty_events.py` y `action_ledger.py`. No crear otro CRM, otra puntuación ni sustituir la norma actual de follow/segundo intento/comentarios. En el mirror ya están en desarrollo **#60** (estados), **#69** (fidelización entrante), **#71 / #103** (priorización + puentes), **#84 / #108** (ledger y evidencia nativa), **#85 / #110** (identidad); las PR #57-59 y #65 abarcan reciprocidad. La cobertura nativa no está acreditada en todas las redes.

## Decisión

**Hueco independiente implementado aquí:** reproducir trayectorias y observaciones de followback a partir de la fuente de eventos confirmados de #84, de modo completamente offline, sin alterar sus escrituras, sin atribuir ausencia de observación a rechazo y sin recrear la lógica operativa. `tools/relationship_journey.py` implementa un lector SQLite en modo read-only, normaliza nueve redes, crea transiciones estrictamente ordenadas, calcula un límite inferior de followbacks observados en cohortes D+7/D+30 (sin interpretarlo como tasa global de conversión), y permite exportar CSV para análisis exploratorio. El orden de eventos con solo precisión de día **no** se inventa; se excluyen de secuencias.

## Alternativas

## Licencias y procedencia
| Proyecto | Evidencia al 10/10/2026 | Decisión |
|---|---|---|
| [Retentioneering](https://github.com/retentioneering/retentioneering-tools/tree/fda32f26fc11119dc950ef6ad720eb5aeefe86a1) | Apache-2.0, `pyproject.toml` v5.2.4, `requires-python >=3.10`, clasificadores Windows/OS independiente + Python 3.11; commit **fda32f26fc11119dc950ef6ad720eb5aeefe86a1** 07/10/2026 | **Reutilización directa y opcional**: `to_eventstream()` instancia `retentioneering.Eventstream` desde `pandas.DataFrame`, según API del proyecto. No se copia código. Dependencia pesada (pandas, DuckDB, pyarrow, sklearn, widget, MCP...), fuera de `requirements-ci.txt` y del proceso operativo. Windows declarado, ejecución real de la librería en Windows **no verificada**. |
| [PingCRM](https://github.com/sneg55/pingcrm/tree/f60cbdde7104a80aefacb676a804c7bb7f5ea53a) | AGPL-3.0, commit **f60cbdde7104a80aefacb676a804c7bb7f5ea53a** de 29/09/2026; FastAPI, PostgreSQL, Redis, Celery y UI | Referencia de modelo de producto, **sin copiar ni importar** código; incompatibilidad operativa y obligaciones a revisar si se adopta AGPL. |
| [HasData social-listening-tool](https://github.com/HasData/social-listening-tool/tree/086ddc5894c6c3c8b48841496f1dc339db299899) | MIT; commit **086ddc5894c6c3c8b48841496f1dc339db299899** 05/04/2026; requiere API de búsqueda, LLM y opcionalmente Telegram | No incorporar a CRM ni hacer llamadas reales: su extracción de snippets no acredita eventos de seguimiento. |
| [Frappe CRM](https://github.com/frappe/crm) | AGPL-3.0 y actividad reciente; orientado a ventas | Descartado por peso y solapamiento con colas existentes. |
| [Socioboard](https://github.com/thinkgandhi/socioboard) | último push de 2014, licencia no acreditada en metadatos | Descartado. |
| [InfluencerHub](https://github.com/Crynge/InfluencerHub) | TypeScript, push julio 2026; no se encontró LICENSE en raíz | Sin reutilización de código sin licencia demostrable. |
| [Laudspeaker](https://github.com/laudspeaker/laudspeaker) | TypeScript, licencia reportada `NOASSERTION`, push julio 2026 | No importar ni copiar. |

**Atribución:** el código nuevo de `relationship_journey.py` es implementación original de un *adaptador* que consume la API documentada de Retentioneering. No incluye archivos modificados de Retentioneering, PingCRM ni otros proyectos. La reutilización ejecutable (`to_eventstream`) necesita que la persona encargada del análisis instale la dependencia opcional; no se afirma que esté instalada ni que se hayan ejecutado sus visualizaciones.

## Pruebas
- Nueve redes: X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram. Un único `read_ledger()`; los adaptadores nativos alimentan #84 a través de #108, **no de este módulo**.
- Lee **solo** la tabla `relationship_events` del esquema #84 v1 con SQLite URI `mode=ro`; no modifica ActionLedger ni ejecuta acciones. Rechaza bases incompatibles y timestamps sin zona; cierra explícitamente conexiones en Windows.
- Usa `network+subject` como trayectoria *por cuenta/red*; no inventa identidad interplataforma. No infiere que los replies confirmados hayan sido *recibidos* (el ledger actual carece de dirección inequívoca).
- Solo acciones `confirmed` y observación `followback.present`. Excluye fallidas, inciertas, ausentes, no verificadas y eventos de precisión diaria. No trata dos sucesos simultáneos como una transición ordenada. Colapsa snapshots `followback.present` repetidos por trayectoria. El CSV local solo se escribe con `--export-csv`.
- Las cohortes usan sujetos únicos con primera acción `follow.confirmed` y ventana cerrada al `as_of` indicado; la cifra positiva es **mínimo observado**, no tasa de followback ni prueba de no reciprocidad para ausentes.
- Pruebas herméticas en `tests/test_relationship_journey.py`: cobertura parametrizada de nueve redes, deduplicación, resultados inciertos, identidad separada, censura D7/D30, evidencia anterior al follow, orden simultáneo, lectura sin crear fichero, rechazo de esquema/timestamp, exportación CSV y prueba de interfaz del adaptador mediante dobles de `pandas/retentioneering` sin instalarlos.

Ejemplo puramente local con ledger **sintético o aprobado** (la PR #84 todavía no está integrada):

```bash
python tools/relationship_journey.py /ruta/ledger.sqlite --as-of 2026-10-10 --export-csv /ruta/journey.csv
python -m pytest tests/test_relationship_journey.py -q
```

En un **entorno analítico separado**, si se decide instalar `retentioneering==5.2.4`, se puede invocar `to_eventstream(rows).transition_graph()`. No activar automáticamente ni añadirlo a los workers. Ejemplo solo para desarrollo offline, nunca para las bases de producción.

## Retirada
**Precondición:** verificar versión y consistencia de #84 y los puentes #108; si cambia el esquema, detener este lector en vez de adaptar silenciosamente. Mantener este módulo desconectado de `mechanical_round`, `loyalty`, ejecutores y cualquier recontacto. La PR complementa #60/#69/#71 y no pretende reemplazarlas.

**Rollback:** retirar `tools/relationship_journey.py`, sus tests y esta documentación; ningún estado operativo ha sido migrado ni modificado. El CSV exportado es un artefacto analítico opcional. Revisar privacidad antes de compartirlo, porque `user_id` incluye identificadores de cuenta.

## Pendientes de Claude
Validar revisión completa de #84 y #108 frente a esquema real, posible solapamiento con informes de #71/#86, suite **completa** y CI del HEAD actual, Python 3.11/Windows (cierre de SQLite y rutas), análisis real con `retentioneering==5.2.4` instalado por separado, y paridad de productores nativos en Edge/API/Android. Sin pruebas en cuentas ni afirmaciones de resultados reales de captación. **No merge**.
