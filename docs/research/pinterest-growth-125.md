# PR #125 — Pinterest: descubrimiento e insights orgánicos verificables

Fuente primaria: https://github.com/pinterest/api-quickstart/blob/592b4bacd85e5bb483bef2e2145aa841ae37ac5a/python/src/pin.py
Fecha de consulta: 2026-10-10
Licencia SPDX: Apache-2.0
Referencia inmutable: https://github.com/pinterest/api-quickstart/tree/592b4bacd85e5bb483bef2e2145aa841ae37ac5a

Fecha: 10/10/2026. Base `research/public-reuse-parent`. No merge, tokens, acceso a cuentas, publicación ni interacciones en redes.

## Diagnóstico contra integración oficial

Fuente contrastada: `davidpd89/rrss-davidporto-CODE@integracion/crecimiento-2026-10`.
Ya existen: `tools/pinterest_growth.py` (pool rotatorio, filtros de español/nicho, scan/plan/run, deduplicación básica), `pinterest_daily_pins.py` (cuota, revalidación y consentimiento, PR oficial #125 ya fusionada), `pinterest_api_audit.py` (List Pins opcional, lectura de `pin_metrics`, comprobación de cuenta, paginación), `discovery_terms.py`, `discovery_ranking.py` (Pinterest deliberadamente no instrumentado para atribución de seguidores). No crear un segundo scheduler, ledger, respuesta prefabricada, API writer ni scraper con navegador adicional.

La PR pública [#17](https://github.com/davidpd89/ci-sandbox-tmp/pull/17) añade control de medios con Pillow: no duplicarlo. También se han contrastado los encargos [#63](https://github.com/davidpd89/ci-sandbox-tmp/pull/63), [#66](https://github.com/davidpd89/ci-sandbox-tmp/pull/66), [#99](https://github.com/davidpd89/ci-sandbox-tmp/pull/99), [#100](https://github.com/davidpd89/ci-sandbox-tmp/pull/100), [#101](https://github.com/davidpd89/ci-sandbox-tmp/pull/101), [#115](https://github.com/davidpd89/ci-sandbox-tmp/pull/115), [#116](https://github.com/davidpd89/ci-sandbox-tmp/pull/116) y [#134](https://github.com/davidpd89/ci-sandbox-tmp/pull/134). Reglas y adaptadores generales corresponden a esas ramas, no a una implementación paralela desde Pinterest.

## Fuentes primarias, versión, licencia y decisión

| Fuente | Commit verificado | Licencia | Decisión |
|---|---|---|---|
| [pinterest/api-quickstart](https://github.com/pinterest/api-quickstart) | `592b4bacd85e5bb483bef2e2145aa841ae37ac5a` | Apache-2.0 | **Adaptación** del recorrido `Pin.max_resolution_image_url` (python/src/pin.py) con selección por área, desempate y validación de origen. Referencia explícita en código. Es código Python estándar compatible con 3.11/Windows. |
| [pinterest/api-description](https://github.com/pinterest/api-description) | `51aca009f10a90283ccdf3956d509fc995ebac23` | MIT | **Reutilización de esquema** OpenAPI de `pin_metrics`, sin generar cliente ni incorporar dependencias. |
| [pinterest/pinterest-python-sdk](https://github.com/pinterest/pinterest-python-sdk) | `7daaa25e018e46ac960187655e8bed6680f6c8cf` (02/09/2026) | Apache-2.0 | Descartado como dependencia: README prioriza campañas y anuncia orgánico como trabajo futuro. |
| [bstoilov/py3-pinterest](https://github.com/bstoilov/py3-pinterest) | `fdbe3bc64e2ec5bf0e58da01be364d81b6ce689d` (30/04/2026) | MIT | Referencia conceptual solamente: endpoints internos y login frágil. El informe lo calificaba de abandonado según release, pero existe commit posterior; no confundir release con actividad. |
| [SoCloseSociety/PinterestBulkPostBot](https://github.com/SoCloseSociety/PinterestBulkPostBot) | `5c6d84160c82f639e848b343600307ca136978f8` | MIT | Descartado: publicador Selenium duplicaría el flujo de publicación existente. |
| [xmokecursed/pinterest-scraper](https://github.com/xmokecursed/pinterest-scraper) | `19cdcce7aa7845a4650cbac9e8323e85ebd30b45` (10/08/2026) | MIT | Sin integración: extracción de imágenes por Playwright, sin aportar identidad/fecha/relevancia fiable para un candidato. |
| `hanspaa2017108/pinterest-scraper` citado en informe | No se pudo resolver ese repositorio | No verificada | Descartado: nombre y licencia no demostrados en ese origen. |

Se consultaron metadatos de GitHub, archivos LICENSE y código fuente, no solo fichas agregadas. Compatibilidad Windows 3.11 de **nuestros módulos nuevos**: sin imports de sistema ni dependencias añadidas; la ejecución efectiva debe confirmarse en matriz CI y equipo del titular. No se reivindica compatibilidad del ejecutor CDP por ello.

## Implementado

1. `tools/pinterest_niche.py`: 20 búsquedas adicionales de intención lectora en español (fantasía, romantasy, tropes, autores y clubes), deduplicadas con Unicode NFKC; adaptación atribuida de la mejor imagen a partir del metadato API, sin descargar nada.
2. `tools/pinterest_growth.py`: conecta las búsquedas al `QUERY_POOL` nativo, conserva 8 consultas/ronda, tres rondas diarias y límites existentes; el filtro de nicho reconoce `romantasy` y `fantasía romántica` sin suprimir requisitos de español ni filtros comerciales.
3. `tools/pinterest_organic_insights.py`: CLI `--demo` o `--input archivo.json` completamente offline, o `--api-read` de solo lectura **opcional** que reutiliza el auditor existente con verificación de cuenta y paginación. Los resultados son descriptivos de Pines propios, con ventanas `90d` o `lifetime_metrics`, valores ausentes nulos, umbral mínimo 100 impresiones y tasa `clickthrough / impression` (sin atribuir ventas). Los datos de proporción 2:3 solo sirven para auditoría visual, no para adivinar calidad.
4. `tests/test_pinterest_research_125.py`: 13 pruebas unitarias offline, incluyendo import y llamada al filtro real, deduplicación, dimensión, host de imágenes, métricas ausentes, duplicados, ventanas, controles de la CLI y ausencia de red en demo.

Ejemplos: `python tools/pinterest_organic_insights.py --demo`; `python -m pytest tests/test_pinterest_research_125.py tests/test_pinterest_growth.py tests/test_pinterest_api_audit.py -q`.

## Normas transversales y límites

El reporte incluye `network` y `source` legibles para futuros adaptadores. **No se fuerza** un porcentaje de score 0–100 inventado ni una supuesta conversión causal. La correspondencia con las otras ocho redes debe conservar la distinción entre observación, evidencia, decisión e interacción confirmada: integrar con #66/#100/#116/#134 tras contrastar sus contratos; no falsear capacidades. No se incluye planificación ni acción real.

Revisión adversarial en varias pasadas: se corrigió el primer commit que insertaba `\\n` literal en el import, y una colisión de nombre entre proporción visual y tasa de clics. El workflow del mirror verifica `compileall` y ejecuta la suite offline en Python 3.11 Ubuntu/Windows.

## Pendiente exclusivamente para Claude / equipo titular

Confirmar HEAD en CI y en Windows nativo, correr suite completa de `rrss-davidporto-CODE`, evaluar concurrencia y divergencias del espejo respecto a integración privada, verificar DOM real Edge/9223 y Android solo si se cambia una ruta de ejecución (no modificada aquí), comprobar esquema real de Pinterest API si algún día se dispone de credenciales y autorización y ensayar `--api-read` en entorno aprobado. **No se ha accedido a ninguna red social** ni emitido llamadas autenticadas.

## Problema
El escáner Pinterest aceptaba términos genéricos, pero no consultaba suficientes tropos de romantasy; el filtro `NICHE` no reconocía `romantasy` como concepto. Había metadatos `pin_metrics` legibles pero ningún comparador puro con evidencias numéricas y ventanas separadas.

## Alternativas
Sustituir el escáner por Playwright de terceros, incorporar SDK oficial completo o aprovechar el escáner existente con semillas y un informe offline. Se eligió la tercera opción por reducir conflictos con turnos Edge, colas existentes y dependencia de endpoints privados.

## Licencias y procedencia
La única rutina adaptada de código público es la selección de máxima resolución de `Pin.max_resolution_image_url` de Pinterest Quickstart, Apache-2.0, commit fijado arriba; conserva cita y explica modificaciones. El contrato `pin_metrics` procede del esquema MIT `pinterest/api-description@51aca009f10a90283ccdf3956d509fc995ebac23`. El resto es implementación original; no se distribuye navegador, assets ni SDK.

## Decisión
Conservar `pinterest_growth.py` como ejecutor existente y conectar semillas adicionales deduplicadas; añadir un reporte offline que separa origen sintético, JSON sin verificar y datos API leídos con autenticación; las métricas no ordenan acciones de engagement. Adaptadores equivalentes para otras redes son responsabilidad de los contratos comunes abiertos (#100/#116/#134).

## Pruebas
`python -m pytest tests/test_pinterest_research_125.py tests/test_pinterest_growth.py tests/test_pinterest_api_audit.py -q` y `python -m compileall -q tools tests`. Evidencia definitiva: workflow `validate-social-tools.yml` del HEAD (Python 3.11 Ubuntu + Windows). Se corrigieron dos problemas durante autorrevisión, incluidos saltos de línea y la variable del ratio visual; no adjudicar resultados de CI de commits anteriores.

## Retirada
Revertir las adiciones a `pinterest_growth.py` y retirar `tools/pinterest_niche.py`, `tools/pinterest_organic_insights.py` y su test. No requiere migración SQLite/CSV, acciones en red ni borrado de datos reales. Si el API no suministra métricas comparables, el informe devuelve `unranked` y nunca introduce una puntuación estimada.
